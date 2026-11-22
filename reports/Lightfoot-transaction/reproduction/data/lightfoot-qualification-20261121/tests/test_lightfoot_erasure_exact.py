"""Exact erasure under the conditions that broke it on real data:
a judge-band merge bridged by the deleted documents, a delete that changes another entity's nearest neighbours,
document order and batch composition, batch-dependent name embeddings, and uncached judge decisions."""
import json
import re

import numpy as np

from lightfoot import Lightfoot, LightfootConfig
from lightfoot.chunking import Chunk, chunk_id_for
from lightfoot.extract import Extraction, ExtractedEntity, ExtractedFact
from lightfoot.ledger import ChunkItem
from lightfoot.resolve import Candidate, JudgePair, LLMJudge, form_key
from lightfoot.store import SQLiteStore
from synthetic_docs import DOCS


class CountingJudge:
    """Says yes to every pair it is shown; records them."""

    def __init__(self, answer=True):
        self.answer = answer
        self.seen = []

    def judge(self, pairs):
        self.seen.extend(pairs)
        return [self.answer] * len(pairs)


def _unit(dim, coords):
    v = np.zeros(dim, dtype=np.float32)
    for i, x in coords.items():
        v[i] = x
    return v / np.linalg.norm(v)


def _index(lf, docs, vecs, embedder, batches):
    """Index hand-built extractions through the real resolver and ledger. `docs`: doc_id -> Extraction;
    `batches`: list of lists of doc ids (one resolve + one ledger transaction per inner list)."""
    for batch in batches:
        items, cands = [], []
        for d in batch:
            text = f"Document {d}."
            ch = Chunk(chunk_id_for(d, text), d, 0, text, 3)
            ex = docs[d]
            cands += [Candidate(ch.chunk_id, e.name, e.type, e.description, vecs[e.name]) for e in ex.entities]
            fe = embedder.encode([f.embed_text() for f in ex.facts]) if ex.facts else None
            items.append(ChunkItem(ch, ex, fe, embedder.encode_one(text)))
        res = lf.resolver.resolve(cands)
        with lf.store.transaction():
            for d in batch:
                lf.store.put("documents", {"doc_id": d, "content_hash": d, "tenant": lf.config.tenant, "metadata": {}, "created_at": 0})
            t = lf.ledger.upsert_batch(items, res, {})
        lf._apply_touched(t)
    return lf


def _lf(embedder, reranker, judge, **kw):
    cfg = LightfootConfig(mock=True, **kw)
    return Lightfoot(SQLiteStore(":memory:", dim=embedder.dim), cfg, embedder=embedder, reranker=reranker, judge=judge)


def _state(lf):
    return lf.graph_fingerprint(), lf.counts(), lf.graph.num_nodes, lf.graph.num_edges, len(lf.name_index)


def _bridge_fixture(dim):
    # "Acme North" and "Acme South" are 0.445 apart (no link); "Acme" is 0.85 from each (judge band): B bridges them.
    a, b = 0.85, (1 - 0.85 ** 2) ** 0.5
    vecs = {"Acme North": _unit(dim, {0: a, 1: b}), "Acme South": _unit(dim, {0: a, 1: -b}), "Acme": _unit(dim, {0: 1.0}),
            "Springfield": _unit(dim, {5: 1.0}), "Shelbyville": _unit(dim, {6: 1.0}), "Ned": _unit(dim, {7: 1.0})}
    E = ExtractedEntity
    docs = {
        "A1": Extraction([E("Acme North", "ORGANIZATION", "Northern arm."), E("Springfield", "LOCATION", "A town.")],
                         [ExtractedFact("Acme North", "based in", "Springfield", "Acme North is based in Springfield.", "based in Springfield")]),
        "A2": Extraction([E("Acme South", "ORGANIZATION", "Southern arm."), E("Shelbyville", "LOCATION", "Another town.")],
                         [ExtractedFact("Acme South", "based in", "Shelbyville", "Acme South is based in Shelbyville.", "based in Shelbyville")]),
        "B": Extraction([E("Acme", "ORGANIZATION", "The parent."), E("Ned", "PERSON", "A founder.")],
                        [ExtractedFact("Ned", "founded", "Acme", "Ned founded Acme.", "founded Acme")]),
    }
    return vecs, docs


def test_erasure_undoes_a_judge_bridge(embedder, reranker):
    """B's form links A's two forms through the judge band; deleting B splits the entity again, and the result
    equals a fresh index of A for every order and batching of A+B."""
    vecs, docs = _bridge_fixture(embedder.dim)
    cfg = LightfootConfig(mock=True, judge_threshold=0.80)   # the judge band is off by default
    assert float(vecs["Acme North"] @ vecs["Acme South"]) < cfg.judge_threshold
    assert cfg.judge_threshold <= float(vecs["Acme"] @ vecs["Acme North"]) < cfg.merge_threshold

    fresh = _state(_index(_lf(embedder, reranker, CountingJudge(), judge_threshold=0.80), docs, vecs, embedder, [["A1", "A2"]]))
    assert fresh[1]["entities"] == 4 and fresh[1]["form_links"] == 0   # Acme North, Acme South, two towns
    for batches in ([["A1", "A2", "B"]], [["B"], ["A1"], ["A2"]], [["A1"], ["B"], ["A2"]], [["A2", "B"], ["A1"]]):
        judge = CountingJudge()
        lf = _index(_lf(embedder, reranker, judge, judge_threshold=0.80), docs, vecs, embedder, batches)
        owner = lf.form_index.owner
        assert owner[form_key("ORGANIZATION", "Acme North")] == owner[form_key("ORGANIZATION", "Acme South")], batches
        assert lf.counts()["entities"] == 4 and lf.counts()["form_links"] == 2   # {Acme, North, South}, 2 towns, Ned
        n_calls, n_judged = len(lf.costs.records), len(judge.seen)
        lf.delete_documents(["B"])
        assert len(lf.costs.records) == n_calls and len(judge.seen) == n_judged, "delete made model calls"
        assert _state(lf) == fresh, batches
        owner = lf.form_index.owner
        assert owner[form_key("ORGANIZATION", "Acme North")] != owner[form_key("ORGANIZATION", "Acme South")]
        # facts were re-pointed to the split entities
        names = {e["entity_id"]: e["canonical_name"] for e in lf.store.select("entities")}
        assert sorted(names[f["subject_entity_id"]] for f in lf.store.select("facts")) == ["Acme North", "Acme South"]


def test_erasure_when_delete_changes_anothers_nearest_neighbours(embedder, reranker):
    """P's nearest neighbour is Q (only in B); R's is T. With a top-1 cap, P-R exists only once Q is gone, and P
    itself is not touched by the delete. After deleting B the synonym set must be what a fresh index computes
    (P-R, R-T). The cap is no longer applied: every pair above the threshold is an edge."""
    dim = embedder.dim
    vecs = {"Pell": _unit(dim, {0: 1.0}),
            "Quorn": _unit(dim, {0: 0.95, 1: (1 - 0.95 ** 2) ** 0.5}),
            "Rook": _unit(dim, {0: 0.85, 2: (1 - 0.85 ** 2) ** 0.5}),
            "Tarn": _unit(dim, {0: 0.6, 2: 0.740, 3: 0.303}),
            "Stoat": _unit(dim, {9: 1.0})}
    E = ExtractedEntity
    docs = {"A1": Extraction([E("Pell", "PERSON", "p")], []),
            "A2": Extraction([E("Rook", "LOCATION", "r"), E("Tarn", "EVENT", "t"), E("Stoat", "OTHER", "s")], []),
            "B": Extraction([E("Quorn", "ORGANIZATION", "q"), E("Stoat", "OTHER", "s again")], [])}
    fresh_lf = _index(_lf(embedder, reranker, CountingJudge(False), synonym_k=1), docs, vecs, embedder, [["A1", "A2"]])
    fresh = _state(fresh_lf)
    syn = {tuple(sorted((r["entity_a"], r["entity_b"]))) for r in fresh_lf.store.select("synonyms")}
    assert len(syn) == 2
    for batches in ([["A1", "A2", "B"]], [["B"], ["A1", "A2"]], [["A1"], ["B"], ["A2"]]):
        lf = _index(_lf(embedder, reranker, CountingJudge(False), synonym_k=1), docs, vecs, embedder, batches)
        assert lf.counts()["synonyms"] == 4   # P-Q, P-R, Q-R, R-T
        lf.delete_documents(["B"])
        assert _state(lf) == fresh, batches


def test_index_order_and_batch_size_do_not_change_the_graph(embedder, reranker, tmp_cache, tmp_path):
    """Mock pipeline end to end: forward, reversed and shuffled document order at batch sizes 1, 3 and 64."""
    import random
    states = set()
    orders = [list(DOCS), list(reversed(DOCS)), random.Random(3).sample(DOCS, len(DOCS))]
    for i, order in enumerate(orders):
        for bs in (1, 3, 64):
            cfg = LightfootConfig(mock=True, cache_dir=tmp_cache, index_batch_size=bs)
            lf = Lightfoot(SQLiteStore(str(tmp_path / f"o{i}b{bs}.db"), dim=embedder.dim), cfg, embedder=embedder, reranker=reranker)
            lf.index_documents(order)
            states.add((lf.graph_fingerprint(), json.dumps(lf.counts(), sort_keys=True), lf.graph.num_edges))
    assert len(states) == 1


def test_erasure_of_random_subsets_matches_fresh_index(embedder, reranker, tmp_cache, tmp_path):
    """Delete three different random subsets after indexing all 20 documents in mixed order; each equals a fresh
    index of the survivors."""
    import random
    for seed in (1, 2, 3):
        rng = random.Random(seed)
        order = rng.sample(DOCS, len(DOCS))
        victims = {d["doc_id"] for d in rng.sample(DOCS, 7)}
        cfg = LightfootConfig(mock=True, cache_dir=tmp_cache, index_batch_size=4)
        lf = Lightfoot(SQLiteStore(str(tmp_path / f"ab{seed}.db"), dim=embedder.dim), cfg, embedder=embedder, reranker=reranker)
        lf.index_documents(order)
        n = len(lf.costs.records)
        lf.delete_documents(sorted(victims))
        assert len(lf.costs.records) == n
        cfg2 = LightfootConfig(mock=True, cache_dir=tmp_cache, index_batch_size=64)
        lf2 = Lightfoot(SQLiteStore(str(tmp_path / f"a{seed}.db"), dim=embedder.dim), cfg2, embedder=embedder, reranker=reranker)
        lf2.index_documents([d for d in DOCS if d["doc_id"] not in victims])
        assert _state(lf) == _state(lf2), seed


def test_encode_names_is_batch_independent(embedder):
    names = ["Barack Obama", "International Business Machines Corporation", "Paris", "x"]
    alone = np.stack([embedder.encode_names([n])[0] for n in names])
    embedder._name_cache.clear()
    mixed = embedder.encode_names(["filler " * 40] + names[::-1] + ["Lyon", "Rome"])[1:5][::-1]
    assert np.array_equal(alone, mixed)


def test_judge_decisions_are_cached_and_order_independent(tmp_cache):
    from lightfoot.llm import LLMClient, Usage

    class FakeLLM(LLMClient):
        def __init__(self):
            self.calls = 0

        def complete(self, system, user, max_tokens, json_schema=None, model=None, effort=None, kind=None):
            self.calls += 1
            pairs = re.findall(r"^Pair (\d+)", user, re.M)
            # a non-deterministic judge: answers differ on every call
            return json.dumps({"decisions": [{"pair": int(p), "same": (self.calls + int(p)) % 3 != 0} for p in pairs]}), Usage(10, 5)

    fake = FakeLLM()
    judge = LLMJudge("m", batch_size=4, llm=fake, cache_dir=tmp_cache)
    pairs = [JudgePair(f"Name {i}", "", f"Name  {i} Ltd", "", "ORGANIZATION") for i in range(10)]
    first = judge.judge(pairs)
    assert fake.calls == 6   # 3 batches x 2 votes
    swapped = [JudgePair(p.name_b, "d", p.name_a, "other desc", p.type) for p in reversed(pairs)]
    again = LLMJudge("m", batch_size=4, llm=fake, cache_dir=tmp_cache).judge(swapped)
    assert fake.calls == 6, "cached decisions must be reused"
    assert again == list(reversed(first))
    # a different type is a different pair
    LLMJudge("m", batch_size=4, llm=fake, cache_dir=tmp_cache).judge([JudgePair("Name 1", "", "Name 1 Ltd", "", "PERSON")])
    assert fake.calls == 8


def test_judge_single_vote_compact_output_and_separate_cache(tmp_cache):
    """votes=1 makes one call per batch; output="compact" reads the list of same pairs; neither shares cached
    decisions with the default double-vote judge."""
    from lightfoot.llm import LLMClient, Usage

    class FakeLLM(LLMClient):
        def __init__(self):
            self.calls, self.systems = 0, []

        def complete(self, system, user, max_tokens, json_schema=None, model=None, effort=None, kind=None):
            self.calls += 1
            self.systems.append(system)
            pairs = [int(p) for p in re.findall(r"^Pair (\d+)", user, re.M)]
            yes = [p for p in pairs if "Ltd" in re.search(rf"^Pair {p} .*\n  A: (.*)\n  B: (.*)", user, re.M).group(0)]
            if json_schema and "same" in json_schema["properties"]:
                return json.dumps({"same": yes}), Usage(10, 2)
            return json.dumps({"decisions": [{"pair": p, "same": p in yes} for p in pairs]}), Usage(10, 5)

    pairs = [JudgePair(f"Name {i}", "", f"Name {i} Ltd" if i % 2 else f"Other {i}", "", "ORGANIZATION") for i in range(10)]
    expect = [bool(i % 2) for i in range(10)]
    fake = FakeLLM()
    assert LLMJudge("m", batch_size=4, llm=fake, cache_dir=tmp_cache, votes=1, output="compact").judge(pairs) == expect
    assert fake.calls == 3 and all('"same":[' in s for s in fake.systems)
    assert LLMJudge("m", batch_size=4, llm=fake, cache_dir=tmp_cache, votes=1).judge(pairs) == expect
    assert fake.calls == 6, "decisions-format single vote has its own cache namespace"
    assert LLMJudge("m", batch_size=4, llm=fake, cache_dir=tmp_cache).judge(pairs) == expect
    assert fake.calls == 12, "double vote has its own cache namespace"


def test_number_guard():
    from lightfoot.resolve import numbers_conflict
    assert numbers_conflict("June 4, 2017", "November 4, 2016")
    assert numbers_conflict("1,120,000", "1.5 million")
    assert not numbers_conflict("11 September 2014", "September 11, 2014")
    assert not numbers_conflict("80", "eighty years")
    assert not numbers_conflict("IBM", "I.B.M.")


def test_default_config_has_no_judge_band(embedder, reranker):
    """Default resolution links only at cosine >= merge_threshold: the judge is never asked."""
    vecs, docs = _bridge_fixture(embedder.dim)
    judge = CountingJudge()
    lf = _index(_lf(embedder, reranker, judge), docs, vecs, embedder, [["A1", "A2", "B"]])
    assert judge.seen == [] and lf.counts()["form_links"] == 0
