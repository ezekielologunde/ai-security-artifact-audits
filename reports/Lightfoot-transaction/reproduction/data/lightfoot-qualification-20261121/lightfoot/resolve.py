"""Entity canonicalization in three cosine bands (design section 4 step 6), as a pure function of the live
surface forms.

Nodes are surface forms (type, name). For every new form, its exact cosine to every live form of the same type
(and to the other new forms of the batch) decides a link:
  >= merge_threshold (0.92)         -> auto link
  judge_threshold .. 0.92           -> batched LLM judge (config judge_votes / judge_output), decision cached per pair
  <  judge_threshold                -> no link
An entity is a connected component of the links; its id is derived from its smallest member form. Because a
link depends only on its two forms (never on which entity happened to be nearest, or on the batch), the
partition is the same for every indexing order, and deleting documents only has to recompute the components
of the forms they touched (design section 5, exactness).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import numpy as np

from .config import LightfootConfig
from .costs import CallRecord
from .llm import LLMCaller, LLMClient, LLMRefusal, make_client
from .store.base import Store


@dataclass
class Candidate:
    """A surface form seen in one chunk, with its embedding."""
    chunk_id: str
    name: str
    type: str
    description: str
    embedding: np.ndarray


@dataclass
class ResolvedEntity:
    entity_id: str
    is_new: bool
    band: str            # "exact" | "auto" | "judge" | "new"
    score: float = 0.0


@dataclass
class JudgePair:
    name_a: str
    desc_a: str
    name_b: str
    desc_b: str
    type: str


@dataclass
class ResolutionStats:
    exact: int = 0
    auto: int = 0
    judged: int = 0
    judge_merged: int = 0
    new: int = 0
    judge_calls: int = 0


# ---------------------------------------------------------------------------
# Judges
# ---------------------------------------------------------------------------
_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokens(s: str) -> set:
    """Lowercased words truncated to a 4-char stem so Corp/Corporation, Inc/Incorporated agree."""
    return {w[:4] for w in _WORD_RE.findall(s.lower())}


class MockJudge:
    """Deterministic: same entity iff one name's word set is contained in the other's,
    or the Jaccard overlap of word sets is at least 0.5."""

    def __init__(self, cost_callback: Optional[Callable[[CallRecord], None]] = None) -> None:
        self.cost_callback = cost_callback

    def judge(self, pairs: Sequence[JudgePair]) -> List[bool]:
        if self.cost_callback:
            self.cost_callback(CallRecord(kind="judge", model="mock", mock=True))
        out = []
        for p in pairs:
            a, b = _tokens(p.name_a), _tokens(p.name_b)
            if not a or not b:
                out.append(False)
                continue
            j = len(a & b) / len(a | b)
            out.append(a <= b or b <= a or j >= 0.5)
        return out


_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"pair": {"type": "integer"}, "same": {"type": "boolean"}},
                "required": ["pair", "same"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["decisions"],
    "additionalProperties": False,
}

_JUDGE_SYSTEM = (
    "You decide whether two entity names of the same type refer to the same real-world entity. Each pair gives "
    "the entity type and two names. Answer `same: true` only when they are clearly the "
    "same thing (e.g. an abbreviation, alternate spelling or longer form of one name), and false when they are "
    "merely related (a person and their company, a city and its country, two different products). Return JSON "
    '{"decisions":[{"pair":<n>,"same":<bool>}, ...]} covering every pair number.'
)


JUDGE_PROMPT_HASH = hashlib.sha256((_JUDGE_SYSTEM + json.dumps(_JUDGE_SCHEMA, sort_keys=True)).encode()).hexdigest()[:8]

# Compact output: only the numbers of the pairs that are the same entity (most pairs are not), about a third of
# the output tokens of one {"pair","same"} object per pair.
_JUDGE_SCHEMA_COMPACT = {
    "type": "object",
    "properties": {"same": {"type": "array", "items": {"type": "integer"}}},
    "required": ["same"],
    "additionalProperties": False,
}

_JUDGE_SYSTEM_COMPACT = (
    "You decide whether two entity names of the same type refer to the same real-world entity. Each pair gives "
    "the entity type and two names. A pair is the same only when the names are clearly the same thing (e.g. an "
    "abbreviation, alternate spelling or longer form of one name), not when they are merely related (a person "
    "and their company, a city and its country, two different products, two different dates or numbers). "
    'Return JSON {"same":[<pair numbers that are the same>]}; use an empty list when none are.'
)

JUDGE_PROMPT_HASH_COMPACT = hashlib.sha256(
    (_JUDGE_SYSTEM_COMPACT + json.dumps(_JUDGE_SCHEMA_COMPACT, sort_keys=True)).encode()).hexdigest()[:8]
JUDGE_OUTPUTS = ("decisions", "compact")


class LLMJudge:
    """One call judges up to `batch_size` pairs. With votes=2 the call is made twice (second time in reverse
    order) and a pair merges only if both votes agree (GraphRAG-SDK style double vote); votes=1 makes one call.
    output="decisions" asks for one {"pair","same"} object per pair, "compact" for the list of same pairs only."""

    def __init__(self, model: str, batch_size: int = 20, cost_callback=None, client=None, max_tokens: int = 1500,
                 llm: Optional[LLMClient] = None, max_retries: int = 6, concurrency: int = 1,
                 cache_dir: Optional[str] = None, votes: int = 2, output: str = "decisions",
                 cache_tag: str = "") -> None:
        """`cache_dir`: persist each pair's outcome (CachedJudge) so a re-index reuses it. The cache namespace
        includes the prompt, the vote count and `cache_tag`, so variants never share decisions."""
        if votes not in (1, 2):
            raise ValueError(f"judge votes must be 1 or 2, got {votes}")
        if output not in JUDGE_OUTPUTS:
            raise ValueError(f"judge output must be one of {JUDGE_OUTPUTS}, got {output!r}")
        self.model = model
        self.votes = votes
        self.output = output
        self.concurrency = concurrency
        self.cache = None
        if cache_dir:
            from types import SimpleNamespace
            ns = f"{model}-{JUDGE_PROMPT_HASH if output == 'decisions' else JUDGE_PROMPT_HASH_COMPACT}"
            if votes != 2:
                ns += f"-v{votes}"
            if cache_tag:
                ns += f"-{cache_tag}"
            self.cache = CachedJudge(SimpleNamespace(judge=self._judge_raw), cache_dir, ns)
        self.batch_size = batch_size
        self.cost_callback = cost_callback
        self.max_tokens = max_tokens
        self.llm = llm or make_client(raw_client=client)
        self.caller = LLMCaller(self.llm, model, cost_callback, max_retries, "low")

    def judge(self, pairs: Sequence[JudgePair]) -> List[bool]:
        return self.cache.judge(pairs) if self.cache is not None else self._judge_raw(pairs)

    def _judge_raw(self, pairs: Sequence[JudgePair]) -> List[bool]:
        batches = [list(pairs[i:i + self.batch_size]) for i in range(0, len(pairs), self.batch_size)]
        jobs = [b for batch in batches for b in ((batch, list(reversed(batch))) if self.votes == 2 else (batch,))]
        if self.concurrency > 1 and len(jobs) > 1:
            import contextvars
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=min(self.concurrency, len(jobs))) as ex:
                futs = [ex.submit(contextvars.copy_context().run, self._vote, j) for j in jobs]
                votes = [f.result() for f in futs]
        else:
            votes = [self._vote(j) for j in jobs]
        out: List[bool] = []
        if self.votes == 1:
            for v in votes:
                out.extend(v)
            return out
        for k in range(len(batches)):
            v1, v2 = votes[2 * k], list(reversed(votes[2 * k + 1]))
            out.extend(a and b for a, b in zip(v1, v2))
        return out

    def _vote(self, batch: List[JudgePair]) -> List[bool]:
        lines = []
        for n, p in enumerate(batch, 1):
            a = f"{p.name_a} -- {p.desc_a[:300]}" if p.desc_a else p.name_a
            b = f"{p.name_b} -- {p.desc_b[:300]}" if p.desc_b else p.name_b
            lines.append(f"Pair {n} (type {p.type}):\n  A: {a}\n  B: {b}")
        prompt = "\n".join(lines)
        compact = self.output == "compact"
        system, schema = (_JUDGE_SYSTEM_COMPACT, _JUDGE_SCHEMA_COMPACT) if compact else (_JUDGE_SYSTEM, _JUDGE_SCHEMA)
        try:
            data = self.caller.json("judge", system, prompt, self.max_tokens, schema) or {}
        except LLMRefusal:
            data = {}
        if compact:
            same = set()
            for n in data.get("same", []) if isinstance(data, dict) else []:
                try:
                    same.add(int(n))
                except Exception:
                    continue
            return [n in same for n in range(1, len(batch) + 1)]
        decisions = {}
        for d in data.get("decisions", []) if isinstance(data, dict) else []:
            try:
                decisions[int(d["pair"])] = bool(d["same"])
            except Exception:
                continue
        return [decisions.get(n, False) for n in range(1, len(batch) + 1)]


# ---------------------------------------------------------------------------
# In-memory entity name matrix
# ---------------------------------------------------------------------------
class EntityNameIndex:
    """All entity name embeddings of a tenant as one float32 matrix, grouped by type.

    Loaded once from the store and appended incrementally by the ledger, so a batch
    of candidates is resolved with one matrix multiply per entity type.
    """

    def __init__(self, dim: int) -> None:
        self.dim = dim
        self._cap = 1024
        self._mat = np.zeros((self._cap, dim), dtype=np.float32)
        self._ids: List[Optional[str]] = []
        self._types: List[Optional[str]] = []
        self._row: Dict[str, int] = {}
        self._n = 0
        self._type_rows: Dict[str, List[int]] = {}
        self._type_cache: Dict[str, np.ndarray] = {}

    @classmethod
    def load(cls, store: Store, tenant: str, dim: int) -> "EntityNameIndex":
        idx = cls(dim)
        keys, mat = store.all_vectors("entities", {"tenant": tenant})
        if len(keys):
            types = {e["entity_id"]: e["type"] for e in store.select("entities", {"tenant": tenant})}
            idx.upsert_many([k[0] for k in keys], [types.get(k[0], "OTHER") for k in keys], mat)
        return idx

    def __len__(self) -> int:
        return len(self._row)

    def _grow(self, need: int) -> None:
        if self._n + need <= self._cap:
            return
        cap = max(self._cap * 2, self._n + need)
        mat = np.zeros((cap, self.dim), dtype=np.float32)
        mat[: self._n] = self._mat[: self._n]
        self._mat, self._cap = mat, cap

    def upsert(self, eid: str, etype: str, vec: np.ndarray) -> None:
        self.upsert_many([eid], [etype], np.asarray(vec, dtype=np.float32).reshape(1, -1))

    def upsert_many(self, eids: Sequence[str], types: Sequence[str], mat: np.ndarray) -> None:
        mat = np.asarray(mat, dtype=np.float32)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        # rows that are already unit length are kept bit-exact (scores are recomputed exactly from them)
        norms[(norms == 0) | (np.abs(norms - 1.0) < 1e-3)] = 1.0
        mat = mat / norms
        self._grow(len(eids))
        for i, eid in enumerate(eids):
            r = self._row.get(eid)
            if r is None:
                r = self._n
                self._ids.append(eid)
                self._types.append(types[i])
                self._row[eid] = r
                self._n += 1
                self._type_rows.setdefault(types[i], []).append(r)
                self._type_cache.pop(types[i], None)
            elif self._types[r] != types[i]:
                self._type_rows[self._types[r]].remove(r)
                self._type_cache.pop(self._types[r], None)
                self._types[r] = types[i]
                self._type_rows.setdefault(types[i], []).append(r)
                self._type_cache.pop(types[i], None)
            self._mat[r] = mat[i]

    def remove(self, eid: str) -> None:
        r = self._row.pop(eid, None)
        if r is None:
            return
        t = self._types[r]
        self._type_rows[t].remove(r)
        self._type_cache.pop(t, None)
        self._ids[r] = None
        self._types[r] = None
        self._mat[r] = 0

    def get(self, eid: str) -> Optional[np.ndarray]:
        r = self._row.get(eid)
        return None if r is None else self._mat[r]

    def _rows_of(self, etype: str) -> np.ndarray:
        a = self._type_cache.get(etype)
        if a is None:
            a = np.asarray(self._type_rows.get(etype, []), dtype=np.int64)
            self._type_cache[etype] = a
        return a

    def best_by_type(self, Q: np.ndarray, types: Sequence[str]) -> Tuple[List[Optional[str]], np.ndarray]:
        """For each query row, the most similar stored entity of the same type."""
        m = Q.shape[0]
        best_ids: List[Optional[str]] = [None] * m
        best_scores = np.full(m, -1.0, dtype=np.float32)
        by_type: Dict[str, List[int]] = {}
        for i, t in enumerate(types):
            by_type.setdefault(t, []).append(i)
        for t, qi in by_type.items():
            rows = self._rows_of(t)
            if len(rows) == 0:
                continue
            S = Q[qi] @ self._mat[rows].T            # (len(qi), len(rows))
            arg = np.argmax(S, axis=1)
            for j, i in enumerate(qi):
                best_ids[i] = self._ids[rows[arg[j]]]
                best_scores[i] = S[j, arg[j]]
        return best_ids, best_scores

    def neighbors(self, Q: np.ndarray, threshold: float, k: int) -> List[List[Tuple[str, float]]]:
        """Entities (any type) with cosine >= threshold for each query row, best first, at most k."""
        n = self._n
        if n == 0 or Q.shape[0] == 0:
            return [[] for _ in range(Q.shape[0])]
        S = Q @ self._mat[:n].T
        out = []
        for i in range(Q.shape[0]):
            row = S[i]
            idx = np.nonzero(row >= threshold)[0]
            idx = idx[np.argsort(-row[idx])][:k]
            out.append([(self._ids[j], float(row[j])) for j in idx if self._ids[j] is not None])
        return out



    def type_matrix(self, etype: str) -> Tuple[List[str], np.ndarray]:
        """(ids, rows) of all live entries of one type (a copy of the rows)."""
        rows = self._rows_of(etype)
        return [self._ids[r] for r in rows], self._mat[rows]

    def pairs_above(self, Q: np.ndarray, threshold: float) -> List[List[str]]:
        """Shortlist: ids (any type) whose approximate cosine with each query row is >= threshold - SHORTLIST_EPS.
        Callers re-score the shortlist with `canonical_score`, so the decision never depends on matmul shape."""
        n = self._n
        if n == 0 or Q.shape[0] == 0:
            return [[] for _ in range(Q.shape[0])]
        S = Q @ self._mat[:n].T
        out = []
        for i in range(Q.shape[0]):
            idx = np.nonzero(S[i] >= threshold - SHORTLIST_EPS)[0]
            out.append([self._ids[j] for j in idx if self._ids[j] is not None])
        return out


# ---------------------------------------------------------------------------
# Surface forms and exact scores
# ---------------------------------------------------------------------------
FORM_SEP = "\x1e"
SHORTLIST_EPS = 1e-4   # matmul shortlist margin; float32 matmul error is ~1e-6


_DIGITS_RE = re.compile(r"\d+")


def numbers_conflict(name_a: str, name_b: str) -> bool:
    """Both names contain digit runs and the sorted runs differ ("June 4, 2017" vs "November 4, 2017",
    "1,120,000" vs "1.5 million"). Names with no digits on one side ("80" vs "eighty years") do not conflict."""
    da, db = sorted(_DIGITS_RE.findall(name_a)), sorted(_DIGITS_RE.findall(name_b))
    return bool(da) and bool(db) and da != db


def form_key(etype: str, name: str) -> str:
    """A surface form: the node of the resolution graph. Same text with a different type is a different form."""
    return f"{etype}{FORM_SEP}{name}"


def split_form(form: str) -> Tuple[str, str]:
    t, n = form.split(FORM_SEP, 1)
    return t, n


def canonical_score(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine computed with exactly rounded float64 sums: a pure function of the two vectors, independent of the
    shape of whatever matrix product produced the shortlist (float32 matmul results vary in the last bits)."""
    a64 = np.asarray(a, dtype=np.float64).ravel()
    b64 = np.asarray(b, dtype=np.float64).ravel()
    num = math.fsum((a64 * b64).tolist())
    den = math.sqrt(math.fsum((a64 * a64).tolist()) * math.fsum((b64 * b64).tolist()))
    return num / den if den > 0 else 0.0


class FormIndex(EntityNameIndex):
    """Surface-form name vectors (id = form key) plus the current form -> entity assignment.
    Loaded from alias vectors at start-up and kept in step by the ledger."""

    def __init__(self, dim: int) -> None:
        super().__init__(dim)
        self.owner: Dict[str, str] = {}
        self.members: Dict[str, Set[str]] = {}

    @classmethod
    def load(cls, store: Store, tenant: str, dim: int) -> "FormIndex":  # type: ignore[override]
        idx = cls(dim)
        types = {e["entity_id"]: e["type"] for e in store.select("entities", {"tenant": tenant})}
        keys, mat = store.all_vectors("aliases", {"tenant": tenant})
        forms, ftypes, rows = [], [], []
        for i, k in enumerate(keys):
            text, eid = k[0], k[1]
            t = types.get(eid)
            if t is None:
                continue
            f = form_key(t, text)
            idx.owner[f] = eid
            idx.members.setdefault(eid, set()).add(f)
            forms.append(f)
            ftypes.append(t)
            rows.append(i)
        if forms:
            idx.upsert_many(forms, ftypes, mat[rows])
        return idx

    def assign(self, eid: str, forms: Iterable[str]) -> None:
        fs = set(forms)
        self.members[eid] = fs
        for f in fs:
            self.owner[f] = eid

    def drop_entity(self, eid: str) -> None:
        for f in self.members.pop(eid, set()):
            if self.owner.get(f) == eid:
                del self.owner[f]

    def drop_form(self, form: str) -> None:
        self.remove(form)
        eid = self.owner.pop(form, None)
        if eid is not None and eid in self.members:
            self.members[eid].discard(form)


# ---------------------------------------------------------------------------
# Judge decision cache
# ---------------------------------------------------------------------------
def _norm_name(s: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", s).split())


def judge_pair_key(p: JudgePair, namespace: str) -> str:
    """Order-independent key of a judged pair: type plus the two normalised names (the judge sees nothing else)."""
    a, b = sorted((_norm_name(p.name_a), _norm_name(p.name_b)))
    return hashlib.sha256(json.dumps([namespace, p.type, a, b], ensure_ascii=False).encode("utf-8")).hexdigest()


class CachedJudge:
    """Persistent, deterministic judge decisions: one row per pair key in `<cache_dir>/judge/<model>/decisions.sqlite`.
    A pair is sent to the model once; every later index (including a re-index after delete) reuses the stored
    double-vote outcome, so merges are reproducible. Misses are judged in canonical (key) order."""

    def __init__(self, inner, cache_dir: str, namespace: str) -> None:
        import sqlite3
        import threading
        self.inner = inner
        self.namespace = namespace
        d = os.path.join(cache_dir, "judge", re.sub(r"[^A-Za-z0-9._-]+", "_", namespace))
        os.makedirs(d, exist_ok=True)
        self.path = os.path.join(d, "decisions.sqlite")
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("CREATE TABLE IF NOT EXISTS decisions (key TEXT PRIMARY KEY, same INTEGER, type TEXT, name_a TEXT, name_b TEXT)")
        self.hits = 0
        self.misses = 0

    def judge(self, pairs: Sequence[JudgePair]) -> List[bool]:
        keys = [judge_pair_key(p, self.namespace) for p in pairs]
        known: Dict[str, bool] = {}
        uniq = sorted(set(keys))
        with self._lock:
            for i in range(0, len(uniq), 500):
                part = uniq[i:i + 500]
                q = f"SELECT key, same FROM decisions WHERE key IN ({','.join('?' * len(part))})"
                for k, v in self.conn.execute(q, part):
                    known[k] = bool(v)
        todo: Dict[str, JudgePair] = {}
        for k, p in sorted(zip(keys, pairs), key=lambda kp: kp[0]):
            if k not in known and k not in todo:
                a, b = sorted((_norm_name(p.name_a), _norm_name(p.name_b)))
                todo[k] = JudgePair(a, "", b, "", p.type)
        self.hits += sum(1 for k in keys if k in known)
        if todo:
            self.misses += len(todo)
            verdicts = self.inner.judge(list(todo.values()))
            rows = [(k, int(bool(v)), p.type, p.name_a, p.name_b) for (k, p), v in zip(todo.items(), verdicts)]
            with self._lock:
                self.conn.executemany("INSERT OR IGNORE INTO decisions VALUES (?,?,?,?,?)", rows)
            for k, v in zip(todo, verdicts):
                known[k] = bool(v)
        return [known[k] for k in keys]


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------
def make_entity_id(tenant: str, etype: str, name: str, salt: str = "") -> str:
    return hashlib.sha256(f"{tenant}\x00{etype}\x00{name}\x00{salt}".encode("utf-8")).hexdigest()[:24]


def component_id(tenant: str, forms: Iterable[str]) -> str:
    """Entity id of a connected component of surface forms: a function of its member set only."""
    t, n = split_form(min(forms))
    return make_entity_id(tenant, t, n)


class Resolution(dict):
    """(chunk_id, name) -> ResolvedEntity, plus what the ledger needs to apply the batch:
    links: new same-entity edges [(form_a, form_b, type, score, kind)];
    groups: entity id -> (type, member forms, existing entity ids merged into it), for every component the batch touches;
    new_forms: form -> name vector for forms not yet in the store."""

    def __init__(self) -> None:
        super().__init__()
        self.links: List[Tuple[str, str, str, float, str]] = []
        self.groups: Dict[str, Tuple[str, Set[str], Set[str]]] = {}
        self.new_forms: Dict[str, np.ndarray] = {}


class _UF:
    def __init__(self) -> None:
        self.p: Dict[str, str] = {}

    def find(self, x: str) -> str:
        p = self.p.setdefault(x, x)
        while p != x:
            gp = self.p[p]
            self.p[x] = gp
            x, p = p, gp
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            if rb < ra:
                ra, rb = rb, ra
            self.p[rb] = ra


def components(nodes: Iterable[str], edges: Iterable[Tuple[str, str]]) -> List[Set[str]]:
    uf = _UF()
    for n in nodes:
        uf.find(n)
    for a, b in edges:
        uf.union(a, b)
    groups: Dict[str, Set[str]] = {}
    for n in list(uf.p):
        groups.setdefault(uf.find(n), set()).add(n)
    return [groups[k] for k in sorted(groups)]


class Resolver:
    """Entities are the connected components of a graph over surface forms (type, name). Two forms of the same
    type are linked iff their exact name cosine is >= merge_threshold, or it is in [judge_threshold,
    merge_threshold) and the (cached) judge says they are the same. Every link is a function of the two forms
    only, so the partition is a function of the set of live forms: independent of document order, batch
    composition and history, and a delete is undone exactly by recomputing the components it touched."""

    def __init__(self, store: Store, config: LightfootConfig, judge, name_index: Optional[EntityNameIndex] = None,
                 form_index: Optional[FormIndex] = None) -> None:
        self.store = store
        self.config = config
        self.judge = judge
        self.name_index = name_index if name_index is not None else EntityNameIndex.load(store, config.tenant, store.dim)
        self.form_index = form_index if form_index is not None else FormIndex.load(store, config.tenant, store.dim)
        self.stats = ResolutionStats()

    def resolve(self, candidates: Sequence[Candidate]) -> Resolution:
        cfg = self.config
        fi = self.form_index
        out = Resolution()
        if not candidates:
            return out
        # the first occurrence of a name in a chunk defines that chunk's surface form (the ledger uses the same rule)
        first: Dict[Tuple[str, str], Candidate] = {}
        for c in candidates:
            first.setdefault((c.chunk_id, c.name), c)
        nodes: Dict[str, Candidate] = {}
        for c in first.values():
            nodes.setdefault(form_key(c.type, c.name), c)
        new_forms = sorted(f for f in nodes if fi.get(f) is None)
        new_vec = {f: np.asarray(nodes[f].embedding, dtype=np.float32).ravel() for f in new_forms}

        links: Dict[Tuple[str, str], Tuple[float, str]] = {}
        to_judge: List[Tuple[str, str, float]] = []
        best: Dict[str, Tuple[float, str]] = {}

        def consider(fa: str, fb: str, va: np.ndarray, vb: np.ndarray) -> None:
            s = canonical_score(va, vb)
            if s < cfg.judge_threshold:
                return
            a, b = (fa, fb) if fa < fb else (fb, fa)
            for f in (fa, fb):
                if f in new_vec and s > best.get(f, (-1.0, ""))[0]:
                    best[f] = (s, "auto" if s >= cfg.merge_threshold else "judge")
            if s >= cfg.merge_threshold:
                links[(a, b)] = (s, "auto")
            else:
                to_judge.append((a, b, s))

        by_type: Dict[str, List[str]] = {}
        for f in new_forms:
            by_type.setdefault(split_form(f)[0], []).append(f)
        lo = cfg.judge_threshold - SHORTLIST_EPS
        for t, fs in sorted(by_type.items()):
            Q = np.stack([new_vec[f] for f in fs])
            ids, M = fi.type_matrix(t)
            if ids:
                S = Q @ M.T
                for i, j in zip(*np.nonzero(S >= lo)):
                    consider(fs[i], ids[j], Q[i], M[j])
            W = Q @ Q.T
            for i, j in zip(*np.nonzero(np.triu(W >= lo, 1))):
                consider(fs[i], fs[j], Q[i], Q[j])

        if to_judge and cfg.judge_number_guard:
            # names that both carry numbers but different ones (dates, years, counts) are different entities;
            # a pure function of the two names, so the link rule (and exact erasure) is unchanged in kind
            to_judge = [t for t in to_judge if not numbers_conflict(split_form(t[0])[1], split_form(t[1])[1])]
        if to_judge:
            to_judge.sort()
            pairs = [JudgePair(split_form(a)[1], "", split_form(b)[1], "", split_form(a)[0]) for a, b, _ in to_judge]
            self.stats.judge_calls += 1
            self.stats.judged += len(pairs)
            for (a, b, s), same in zip(to_judge, self.judge.judge(pairs)):
                if same:
                    links[(a, b)] = (s, "judge")
                    self.stats.judge_merged += 1

        judged_yes = {f for (a, b), (_, kind) in links.items() if kind == "judge" for f in (a, b)}
        # union existing entities (as units) and new forms over the links
        def unit(f: str) -> str:
            eid = fi.owner.get(f)
            return "e\x00" + eid if eid is not None else "f\x00" + f

        comps = components([unit(f) for f in nodes], [(unit(a), unit(b)) for a, b in links])
        unit_eid: Dict[str, str] = {}
        for comp in comps:
            members: Set[str] = set()
            old: Set[str] = set()
            for u in comp:
                kind, val = u.split("\x00", 1)
                if kind == "e":
                    old.add(val)
                    members |= fi.members.get(val, set())
                else:
                    members.add(val)
            eid = component_id(cfg.tenant, members)
            out.groups[eid] = (split_form(min(members))[0], members, old)
            for u in comp:
                unit_eid[u] = eid
        for (cid, name), c in first.items():
            f = form_key(c.type, c.name)
            eid = unit_eid[unit(f)]
            if f in new_vec:
                s, band = best.get(f, (0.0, "new"))
                if band == "judge" and f not in judged_yes:
                    band = "new"
            else:
                s, band = 1.0, "exact"
            out[(cid, name)] = ResolvedEntity(eid, eid not in fi.members, band, s)
        for f in new_forms:
            s, band = best.get(f, (0.0, "new"))
            if band == "auto":
                self.stats.auto += 1
            else:
                self.stats.new += 1
        self.stats.exact += len(nodes) - len(new_forms)
        out.links = [(a, b, split_form(a)[0], s, kind) for (a, b), (s, kind) in sorted(links.items())]
        out.new_forms = new_vec
        return out
