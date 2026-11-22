"""Sparse graph with Personalized PageRank (design section 6 step 2).

Two layouts, chosen by `fact_nodes`:

fact_nodes=True (original Lightfoot layout; entity, fact and chunk nodes):
  fact  -- member entities (subject, object)   weight 1
  fact  -- source chunks                       weight 1
  chunk -- mentioned entities                  weight 1
  entity -- entity synonym                     weight = cosine score

fact_nodes=False (HippoRAG 2 layout; entity and chunk nodes only, the default):
  chunk -- mentioned entities                  weight 1
  entity -- entity per fact                    weight = number of facts linking the pair (x fact_edge_weight)
  entity -- entity synonym                     weight = cosine score (added to any fact weight)

Synonym edges below `synonym_min` are skipped. Hub control at compile time: entities above the
`hub_percentile` degree percentile are cut out of the walk, and `degree_penalty` ("log" or "none")
divides the weight of every edge into an entity by log(e + degree).
The adjacency is kept as dict-of-dicts and compiled to a scipy CSR transition matrix
lazily. PPR is power iteration p = (1-d) r + d M p with dangling mass returned to r.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set, Tuple

import numpy as np
import scipy.sparse as sp

from .store.base import Store


def ent(eid: str) -> str:
    return "e:" + eid


def fact(fid: str) -> str:
    return "f:" + fid


def chunk(cid: str) -> str:
    return "c:" + cid


class GraphIndex:
    def __init__(self, damping: float = 0.5, tol: float = 1e-6, max_iter: int = 100, fact_nodes: bool = True,
                 fact_edge_weight: float = 1.0, synonym_min: float = 0.0, hub_percentile: float = 0.0,
                 degree_penalty: str = "none") -> None:
        self.damping = damping
        self.tol = tol
        self.max_iter = max_iter
        self.fact_nodes = fact_nodes
        self.fact_edge_weight = fact_edge_weight
        self.synonym_min = synonym_min
        self.hub_percentile = hub_percentile
        self.degree_penalty = degree_penalty
        self._fact_ends: Dict[str, Tuple[str, str]] = {}   # fact_id -> (subject, object) when facts are edges
        self.adj: Dict[str, Dict[str, float]] = {}
        self._index: Dict[str, int] = {}
        self._nodes: List[str] = []
        self._M: Optional[sp.csr_matrix] = None
        self._dirty = True

    @classmethod
    def from_config(cls, cfg) -> "GraphIndex":
        return cls(cfg.damping, cfg.ppr_tolerance, cfg.ppr_max_iter, fact_nodes=cfg.graph_fact_nodes,
                   fact_edge_weight=cfg.fact_edge_weight, synonym_min=cfg.graph_synonym_min,
                   hub_percentile=cfg.hub_percentile, degree_penalty=cfg.degree_penalty)

    # ---- mutation ------------------------------------------------------
    def add_node(self, n: str) -> None:
        if n not in self.adj:
            self.adj[n] = {}
            self._dirty = True

    def add_edge(self, u: str, v: str, w: float = 1.0) -> None:
        if u == v or w <= 0:
            return
        self.add_node(u)
        self.add_node(v)
        self.adj[u][v] = float(w)
        self.adj[v][u] = float(w)
        self._dirty = True

    def remove_node(self, n: str) -> None:
        if n not in self.adj:
            return
        for v in list(self.adj[n]):
            self.adj[v].pop(n, None)
        del self.adj[n]
        self._dirty = True

    def drop_edges_of(self, nodes: Iterable[str]) -> None:
        for n in nodes:
            if n in self.adj:
                for v in list(self.adj[n]):
                    self.adj[v].pop(n, None)
                self.adj[n] = {}
                self._dirty = True

    def bump_edge(self, u: str, v: str, w: float) -> None:
        """Add w to the (undirected) edge weight, creating the edge if needed."""
        if u == v or w <= 0:
            return
        self.add_node(u)
        self.add_node(v)
        nw = self.adj[u].get(v, 0.0) + float(w)
        self.adj[u][v] = nw
        self.adj[v][u] = nw
        self._dirty = True

    def clear(self) -> None:
        self.adj = {}
        self._fact_ends = {}
        self._dirty = True

    def chunk_degree(self, n: str) -> int:
        """Number of chunk neighbours of a node (for an entity: the passages that mention it)."""
        return sum(1 for v in self.adj.get(n, ()) if v.startswith("c:"))

    @property
    def num_nodes(self) -> int:
        return len(self.adj)

    @property
    def num_edges(self) -> int:
        return sum(len(v) for v in self.adj.values()) // 2

    def has_node(self, n: str) -> bool:
        return n in self.adj

    # ---- store sync ------------------------------------------------------
    def rebuild_from_store(self, store: Store, tenant: Optional[str] = None) -> None:
        self.clear()
        w = {"tenant": tenant} if tenant else None
        for c in store.select("chunks", w):
            self.add_node(chunk(c["chunk_id"]))
        for e in store.select("entities", w):
            self.add_node(ent(e["entity_id"]))
        self._add_rows(store, store.select("facts", w), store.select("fact_sources"), store.select("mentions"), store.select("synonyms", w))

    def refresh_from_store(self, store: Store, entity_ids: Iterable[str] = (), fact_ids: Iterable[str] = (),
                           chunk_ids: Iterable[str] = (), removed: Iterable[str] = ()) -> None:
        """Incremental update: re-derive all edges incident to the given nodes from the store (IN-list queries)."""
        entity_ids, fact_ids, chunk_ids = set(entity_ids), set(fact_ids), set(chunk_ids)
        removed = list(removed)
        if not self.fact_nodes:
            # facts are entity-entity edges: re-derive every edge of the entities a touched fact links (old and new)
            gone = {n[2:] for n in removed if n.startswith("f:")}
            for fid in fact_ids | gone:
                entity_ids.update(self._fact_ends.pop(fid, ()))
            if fact_ids:
                for f in store.select("facts", {"fact_id": sorted(fact_ids)}):
                    entity_ids.update((f["subject_entity_id"], f["object_entity_id"]))
            for fid, ends in list(self._fact_ends.items()):
                if ends[0] in entity_ids or ends[1] in entity_ids:
                    del self._fact_ends[fid]
            fact_ids = set()
        entity_ids, fact_ids, chunk_ids = sorted(entity_ids), sorted(fact_ids), sorted(chunk_ids)
        for n in removed:
            self.remove_node(n)
        nodes = [ent(e) for e in entity_ids] + [fact(f) for f in fact_ids] + [chunk(c) for c in chunk_ids]
        self.drop_edges_of(nodes)
        for n in nodes:
            self.add_node(n)
        facts, sources, mentions, syns = [], [], [], []
        if fact_ids:
            facts += store.select("facts", {"fact_id": fact_ids})
            sources += store.select("fact_sources", {"fact_id": fact_ids})
        if chunk_ids:
            mentions += store.select("mentions", {"chunk_id": chunk_ids})
            sources += store.select("fact_sources", {"chunk_id": chunk_ids})
        if entity_ids:
            mentions += store.select("mentions", {"entity_id": entity_ids})
            facts += store.select("facts", {"subject_entity_id": entity_ids})
            facts += store.select("facts", {"object_entity_id": entity_ids})
            syns += store.select("synonyms", {"entity_a": entity_ids})
            syns += store.select("synonyms", {"entity_b": entity_ids})
        self._add_rows(store, facts, sources, mentions, syns)
        # drop nodes that no longer exist in the store
        for table, ids, fn in (("entities", entity_ids, ent), ("facts", fact_ids, fact), ("chunks", chunk_ids, chunk)):
            if not ids:
                continue
            key = {"entities": "entity_id", "facts": "fact_id", "chunks": "chunk_id"}[table]
            alive = {r[key] for r in store.select(table, {key: ids})}
            for i in ids:
                if i not in alive:
                    self.remove_node(fn(i))

    def _add_rows(self, store: Store, facts, sources, mentions, syns) -> None:
        if self.fact_nodes:
            for f in facts:
                self.add_edge(fact(f["fact_id"]), ent(f["subject_entity_id"]))
                self.add_edge(fact(f["fact_id"]), ent(f["object_entity_id"]))
            for s in sources:
                self.add_edge(fact(s["fact_id"]), chunk(s["chunk_id"]))
        for m in mentions:
            self.add_edge(chunk(m["chunk_id"]), ent(m["entity_id"]))
        # entity-entity weights are sums (fact counts + synonym score), so dedupe rows selected twice
        seen_syn = set()
        for s in syns:
            k = (s["entity_a"], s["entity_b"])
            if k in seen_syn or float(s["score"]) < self.synonym_min:
                continue
            seen_syn.add(k)
            if self.fact_nodes:
                self.add_edge(ent(s["entity_a"]), ent(s["entity_b"]), float(s["score"]))
            else:
                self.bump_edge(ent(s["entity_a"]), ent(s["entity_b"]), float(s["score"]))
        if not self.fact_nodes:
            for f in facts:
                fid = f["fact_id"]
                if fid in self._fact_ends:
                    continue
                a, b = f["subject_entity_id"], f["object_entity_id"]
                self._fact_ends[fid] = (a, b)
                self.add_node(ent(a))
                self.add_node(ent(b))
                self.bump_edge(ent(a), ent(b), self.fact_edge_weight)

    # ---- PPR -------------------------------------------------------------
    def _compile(self) -> None:
        if not self._dirty and self._M is not None:
            return
        self._nodes = list(self.adj.keys())
        self._index = {n: i for i, n in enumerate(self._nodes)}
        n = len(self._nodes)
        excluded = set()
        if self.hub_percentile > 0:
            degs = {u: len(nb) for u, nb in self.adj.items() if u.startswith("e:")}
            if degs:
                thr = float(np.percentile(list(degs.values()), self.hub_percentile))
                excluded = {u for u, d in degs.items() if d > thr}
        log_pen = self.degree_penalty == "log"
        rows, cols, vals = [], [], []
        for u, nbrs in self.adj.items():
            if u in excluded:
                continue
            i = self._index[u]
            ws = {}
            for v, w in nbrs.items():
                if v in excluded:
                    continue
                if log_pen and v.startswith("e:"):
                    w = w / np.log(np.e + len(self.adj[v]))
                ws[v] = w
            tot = sum(ws.values())
            if tot <= 0:
                continue
            for v, w in ws.items():
                rows.append(self._index[v])   # mass flows from column u to row v
                cols.append(i)
                vals.append(w / tot)
        self._M = sp.csr_matrix((vals, (rows, cols)), shape=(n, n), dtype=np.float64)
        self._dangling = np.asarray(self._M.sum(axis=0)).ravel() <= 0
        self._dirty = False

    def ppr(self, reset: Dict[str, float], damping: Optional[float] = None) -> Dict[str, float]:
        """Personalized PageRank from a reset distribution over node ids. Returns node -> score."""
        self._compile()
        n = len(self._nodes)
        if n == 0:
            return {}
        d = self.damping if damping is None else damping
        r = np.zeros(n)
        for node, mass in reset.items():
            i = self._index.get(node)
            if i is not None and mass > 0:
                r[i] += mass
        if r.sum() <= 0:
            return {}
        r /= r.sum()
        p = r.copy()
        M = self._M
        for _ in range(self.max_iter):
            spread = M @ p
            dangling_mass = float(p[self._dangling].sum())
            new = (1 - d) * r + d * (spread + dangling_mass * r)
            delta = float(np.abs(new - p).sum())
            p = new
            if delta < self.tol:
                break
        return {self._nodes[i]: float(p[i]) for i in np.nonzero(p > 0)[0]}

    def ppr_by_kind(self, reset: Dict[str, float], kind: str, top: Optional[int] = None) -> List[Tuple[str, float]]:
        scores = self.ppr(reset)
        prefix = kind + ":"
        out = [(n[len(prefix):], s) for n, s in scores.items() if n.startswith(prefix)]
        out.sort(key=lambda x: -x[1])
        return out[:top] if top else out
