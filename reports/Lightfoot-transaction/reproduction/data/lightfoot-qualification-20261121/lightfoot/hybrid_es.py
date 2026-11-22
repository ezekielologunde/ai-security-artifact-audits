"""Elasticsearch hybrid-search channel: BM25 on chunk text + kNN on the chunk embedding, fused by RRF.

One index per (store, tenant). The index mirrors the `chunks` table exactly: chunks are added in the same
index batch that writes them to the store (reusing the embeddings Lightfoot already computed) and removed
with their documents, so after any delete the index holds exactly the surviving chunks (zero model calls).

Native RRF (the `rrf` retriever) needs a Platinum/Enterprise license in 8.x; on the free Basic license the
server answers 403 "current license is non-compliant for [Reciprocal Rank Fusion (RRF)]". `native_rrf="auto"`
tries it once and falls back to client-side RRF: one BM25 `match` query and one `knn` query, each returning
`window` hits, fused with score(d) = sum 1 / (k + rank), rank starting at 1 (the same formula ES uses).
"""
from __future__ import annotations

import hashlib
import os
import re
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import numpy as np


def index_name_for(store_path: Optional[str], tenant: str, prefix: str = "lightfoot") -> str:
    """Deterministic per-store, per-tenant index name. An in-memory store gets a random name (never shared)."""
    if not store_path or store_path == ":memory:":
        key = "mem:" + os.urandom(8).hex()
    else:
        key = os.path.abspath(store_path)
    h = hashlib.sha1(f"{key}\x00{tenant}".encode("utf-8")).hexdigest()[:16]
    t = re.sub(r"[^a-z0-9_-]+", "-", tenant.lower()).strip("-_")[:40] or "t"
    return f"{prefix}-{t}-{h}"


def rrf_fuse(lists: Sequence[Sequence[str]], k: int = 60, weights: Optional[Sequence[float]] = None) -> List[Tuple[str, float]]:
    """Reciprocal rank fusion. Ties break by the best (lowest) rank in any list, then by first list order."""
    weights = list(weights) if weights is not None else [1.0] * len(lists)
    score: Dict[str, float] = {}
    best: Dict[str, Tuple[int, int]] = {}
    for li, (lst, w) in enumerate(zip(lists, weights)):
        for r, cid in enumerate(lst, start=1):
            score[cid] = score.get(cid, 0.0) + w / (k + r)
            b = (r, li)
            if cid not in best or b < best[cid]:
                best[cid] = b
    return sorted(score.items(), key=lambda x: (-x[1], best[x[0]]))


class HybridES:
    """Small wrapper around one Elasticsearch index of chunks. `client` may be any object with the
    elasticsearch-py 8.x surface used here (tests pass a fake)."""

    def __init__(self, index: str, dim: int = 768, url: str = "http://localhost:9200", client=None,
                 rrf_k: int = 60, window: int = 50, num_candidates: int = 200, native_rrf: str = "auto") -> None:
        self.index = index
        self.dim = int(dim)
        self.url = url
        self.rrf_k = int(rrf_k)
        self.window = int(window)
        self.num_candidates = int(num_candidates)
        self._native: Optional[bool] = {"auto": None, "on": True, "off": False}.get(str(native_rrf).lower(), None)
        if client is None:
            from elasticsearch import Elasticsearch
            client = Elasticsearch(url, request_timeout=60)
        self.es = client
        self.last: Dict[str, List[str]] = {}   # "bm25" / "knn" / "hybrid" -> ranked chunk ids of the last search
        self.ensure_index()

    # ---- index lifecycle -----------------------------------------------------
    def mapping(self) -> Dict:
        return {
            "settings": {"number_of_shards": 1, "number_of_replicas": 0},
            "mappings": {
                "dynamic": "strict",
                "properties": {
                    "chunk_id": {"type": "keyword"},
                    "doc_id": {"type": "keyword"},
                    "text": {"type": "text", "analyzer": "standard"},
                    "embedding": {"type": "dense_vector", "dims": self.dim, "index": True, "similarity": "cosine"},
                },
            },
        }

    def ensure_index(self) -> None:
        if not self.es.indices.exists(index=self.index):
            m = self.mapping()
            self.es.indices.create(index=self.index, settings=m["settings"], mappings=m["mappings"])

    def drop(self) -> None:
        self.es.indices.delete(index=self.index, ignore_unavailable=True)

    def refresh(self) -> None:
        self.es.indices.refresh(index=self.index)

    # ---- writes ----------------------------------------------------------------
    def index_chunks(self, rows: Sequence[Dict], vectors: np.ndarray, refresh: bool = True) -> int:
        """rows: dicts with chunk_id, doc_id, text; vectors: (n, dim) chunk embeddings (already normalised)."""
        if not len(rows):
            return 0
        vectors = np.asarray(vectors, dtype=np.float32)
        assert vectors.shape == (len(rows), self.dim), (vectors.shape, len(rows), self.dim)
        ops: List[Dict] = []
        for r, v in zip(rows, vectors):
            ops.append({"index": {"_index": self.index, "_id": r["chunk_id"]}})
            ops.append({"chunk_id": r["chunk_id"], "doc_id": r["doc_id"], "text": r["text"],
                        "embedding": [float(x) for x in v]})
        n = 0
        step = 1000   # 500 docs per bulk request
        for i in range(0, len(ops), step):
            resp = self.es.bulk(operations=ops[i:i + step], refresh=False)
            if resp.get("errors"):
                bad = [it for it in resp.get("items", []) if any(x.get("error") for x in it.values())]
                raise RuntimeError(f"elasticsearch bulk index failed for {len(bad)} chunks: {bad[:2]}")
            n += len(resp.get("items", [])) or len(ops[i:i + step]) // 2
        if refresh:
            self.refresh()
        return n

    def delete_docs(self, doc_ids: Sequence[str], refresh: bool = True) -> int:
        return self._delete_by_terms("doc_id", doc_ids, refresh)

    def delete_chunks(self, chunk_ids: Sequence[str], refresh: bool = True) -> int:
        return self._delete_by_terms("chunk_id", chunk_ids, refresh)

    def _delete_by_terms(self, field: str, values: Sequence[str], refresh: bool) -> int:
        values = sorted(set(values))
        n = 0
        for i in range(0, len(values), 1000):
            resp = self.es.delete_by_query(index=self.index, query={"terms": {field: values[i:i + 1000]}},
                                           refresh=refresh, conflicts="proceed", slices="auto")
            n += int(resp.get("deleted", 0))
        return n

    # ---- reads -----------------------------------------------------------------
    def count(self) -> int:
        return int(self.es.count(index=self.index)["count"])

    def chunk_ids(self) -> Set[str]:
        """Every chunk id in the index (search_after paging; fine for verification and reconciliation)."""
        out: Set[str] = set()
        after = None
        while True:
            kw = dict(index=self.index, size=5000, sort=[{"chunk_id": "asc"}], source=False,
                      fields=["chunk_id"], query={"match_all": {}})
            if after is not None:
                kw["search_after"] = after
            hits = self.es.search(**kw)["hits"]["hits"]
            if not hits:
                break
            for h in hits:
                out.add(h["_id"])
            after = hits[-1]["sort"]
            if len(hits) < 5000:
                break
        return out

    def bm25(self, text: str, k: int) -> List[Tuple[str, float]]:
        resp = self.es.search(index=self.index, size=k, source=False,
                              query={"match": {"text": {"query": text}}})
        return [(h["_id"], float(h["_score"])) for h in resp["hits"]["hits"]]

    def knn(self, qvec: np.ndarray, k: int) -> List[Tuple[str, float]]:
        resp = self.es.search(index=self.index, size=k, source=False,
                              knn={"field": "embedding", "query_vector": [float(x) for x in qvec], "k": k,
                                   "num_candidates": max(self.num_candidates, k)})
        return [(h["_id"], float(h["_score"])) for h in resp["hits"]["hits"]]

    def _native_search(self, text: str, qvec: np.ndarray, k: int) -> List[Tuple[str, float]]:
        w = max(self.window, k)
        resp = self.es.search(index=self.index, size=k, source=False, retriever={"rrf": {
            "retrievers": [
                {"standard": {"query": {"match": {"text": {"query": text}}}}},
                {"knn": {"field": "embedding", "query_vector": [float(x) for x in qvec], "k": w,
                         "num_candidates": max(self.num_candidates, w)}},
            ],
            "rank_window_size": w, "rank_constant": self.rrf_k}})
        return [(h["_id"], float(h["_score"])) for h in resp["hits"]["hits"]]

    def search(self, text: str, qvec: np.ndarray, k: int) -> List[Tuple[str, float]]:
        """Hybrid ranking: [(chunk_id, fused score)] best first, at most k."""
        if self._native is not False:
            try:
                out = self._native_search(text, qvec, k)
                self._native = True
                self.last = {"hybrid": [c for c, _ in out]}
                return out
            except Exception as e:   # license (403) or older server: fall back for good
                if self._native is True and not _is_license_error(e):
                    raise
                self._native = False
        w = max(self.window, k)
        b = self.bm25(text, w)
        d = self.knn(qvec, w)
        fused = rrf_fuse([[c for c, _ in b], [c for c, _ in d]], k=self.rrf_k)[:k]
        self.last = {"bm25": [c for c, _ in b], "knn": [c for c, _ in d], "hybrid": [c for c, _ in fused]}
        return fused

    @property
    def native_rrf(self) -> Optional[bool]:
        return self._native

    # ---- reconciliation --------------------------------------------------------
    def sync_with_store(self, store, tenant: str) -> Tuple[int, int]:
        """Make the index hold exactly the store's chunks for this tenant, reusing stored chunk vectors
        (zero model calls). Returns (added, removed)."""
        rows = store.select("chunks", {"tenant": tenant})
        want = {r["chunk_id"]: r for r in rows}
        have = self.chunk_ids()
        extra = sorted(have - set(want))
        missing = sorted(set(want) - have)
        if extra:
            self.delete_chunks(extra, refresh=False)
        if missing:
            vecs = store.get_vectors("chunks", [(c,) for c in missing])
            keep = [(want[c], v) for c, v in zip(missing, vecs) if v is not None]
            if keep:
                self.index_chunks([r for r, _ in keep], np.stack([v for _, v in keep]), refresh=False)
        if extra or missing:
            self.refresh()
        return len(missing), len(extra)


def _is_license_error(e: Exception) -> bool:
    s = str(e).lower()
    return "license" in s or "non-compliant" in s or getattr(e, "status_code", None) in (400, 403)
