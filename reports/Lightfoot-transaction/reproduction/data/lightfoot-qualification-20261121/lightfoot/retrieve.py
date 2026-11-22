"""Query pipeline (design section 6): hybrid seeding, PPR, local rerank, gate, context assembly."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .chunking import estimate_tokens
from .config import LightfootConfig
from .embed import Embedder
from .graph import GraphIndex, ent, fact, chunk
from .store.base import Store

_TOK_RE = re.compile(r"\w+")


def _tok(s: str) -> List[str]:
    return _TOK_RE.findall(s.lower())


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


@dataclass
class RetrievalResult:
    ranked_chunk_ids: List[str]
    context: str
    chunk_scores: Dict[str, float]
    seed_facts: List[Tuple[str, float]] = field(default_factory=list)
    seed_entities: List[Tuple[str, float]] = field(default_factory=list)
    seed_chunks: List[Tuple[str, float]] = field(default_factory=list)
    best_rerank: float = 0.0
    coverage: float = 1.0
    escalated: bool = False
    subquestions: List[str] = field(default_factory=list)
    top_facts: List[dict] = field(default_factory=list)
    top_mentions: List[dict] = field(default_factory=list)
    # graph pipeline ranking (== ranked_chunk_ids unless ranking_output="fused")
    graph_chunk_ids: List[str] = field(default_factory=list)
    # hybrid channel (Elasticsearch BM25 + kNN, RRF); empty when hybrid_backend="none"
    hybrid_chunk_ids: List[str] = field(default_factory=list)
    hybrid_scores: Dict[str, float] = field(default_factory=dict)
    # RRF of graph_chunk_ids and hybrid_chunk_ids (== graph ranking when the hybrid channel is off)
    fused_chunk_ids: List[str] = field(default_factory=list)
    # passages actually placed in the context, per section, in context order
    context_graph_ids: List[str] = field(default_factory=list)
    context_hybrid_ids: List[str] = field(default_factory=list)


class Reranker:
    """Local cross-encoder (bge-reranker-base) on mps/cpu. Returns probabilities in [0,1]."""

    def __init__(self, model_name: str = "BAAI/bge-reranker-base", device: Optional[str] = None) -> None:
        from .embed import pick_device
        self.model_name = model_name
        self.device = device or pick_device()
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name, device=self.device, max_length=512)
        return self._model

    def score(self, question: str, texts: Sequence[str]) -> List[float]:
        if not texts:
            return []
        logits = self.model.predict([(question, t) for t in texts], batch_size=16, show_progress_bar=False)
        return [_sigmoid(float(x)) for x in np.asarray(logits).reshape(-1)]


class Retriever:
    def __init__(self, store: Store, embedder: Embedder, graph: GraphIndex, config: LightfootConfig,
                 reranker: Optional[Reranker] = None, hybrid=None) -> None:
        self.store = store
        self.hybrid = hybrid   # optional HybridES (or anything with .search(text, qvec, k) and .last)
        self.embedder = embedder
        self.graph = graph
        self.config = config
        self.reranker = reranker
        self._bm25 = None
        self._bm25_ids: List[str] = []
        self.last_trace: Dict[str, List[str]] = {}   # stage name -> ranked chunk ids (diagnostics)
        self._dense_pool: List[Tuple[str, float]] = []

    # ---- sparse index ------------------------------------------------------
    def invalidate(self) -> None:
        self._bm25 = None

    def _ensure_bm25(self) -> None:
        if self._bm25 is not None:
            return
        from rank_bm25 import BM25Okapi
        rows = self.store.select("chunks", {"tenant": self.config.tenant})
        self._bm25_ids = [r["chunk_id"] for r in rows]
        corpus = [_tok(r["text"]) for r in rows] or [["_"]]
        self._bm25 = BM25Okapi(corpus)

    def bm25_search(self, question: str, k: int) -> List[Tuple[str, float]]:
        self._ensure_bm25()
        if not self._bm25_ids:
            return []
        scores = self._bm25.get_scores(_tok(question))
        idx = np.argsort(-scores)[:k]
        return [(self._bm25_ids[i], float(scores[i])) for i in idx if scores[i] > 0]

    # ---- seeding -----------------------------------------------------------
    def seeds(self, question: str):
        cfg = self.config
        q = self.embedder.encode_one(question)
        qp = self.embedder.encode_query(question)
        w = {"tenant": cfg.tenant}
        hippo = cfg.seed_mode == "hipporag"
        facts = [(k[0], s) for k, s in self.store.search("facts", q, max(cfg.seed_facts_k, cfg.link_facts_k if hippo else 0), w)]
        ents = [(k[0], s) for k, s in self.store.search("entities", q, cfg.seed_entities_k, w)]
        n_dense = max(cfg.seed_chunks_k, cfg.passage_seed_k if hippo else 0)
        dense_all = [(k[0], s) for k, s in self.store.search("chunks", qp, n_dense, w)]
        self._dense_pool = dense_all
        dense = dense_all[: cfg.seed_chunks_k]
        sparse = self.bm25_search(question, cfg.bm25_k) if not hippo else []
        # reciprocal rank fusion for chunks
        hybrid: Dict[str, float] = {}
        for lst in (dense, sparse):
            for rank, (cid, _) in enumerate(lst):
                hybrid[cid] = hybrid.get(cid, 0.0) + 1.0 / (60 + rank)
        chunks = sorted(hybrid.items(), key=lambda x: -x[1])
        self.last_trace = {"dense": [c for c, _ in dense], "bm25": [c for c, _ in sparse], "rrf": [c for c, _ in chunks]}
        return facts, ents, chunks

    def hipporag_reset(self, facts, dense_pool) -> Dict[str, float]:
        """HippoRAG 2 reset without the LLM fact filter: the subject/object entities of the top link_facts_k
        facts get mean(fact cosine / entity passage count); the top passage_seed_k dense passages get
        passage_node_weight * min-max normalised dense score. With fact nodes in the graph, the facts
        themselves are not seeded (only their entities)."""
        cfg = self.config
        acc: Dict[str, List[float]] = {}
        for fid, s in facts[: cfg.link_facts_k]:
            ends = self._fact_ends(fid)
            for e in set(ends):
                n = ent(e)
                if self.graph.has_node(n):
                    acc.setdefault(n, []).append(max(s, 0.0) / max(1, self.graph.chunk_degree(n)))
        reset = {n: float(np.mean(xs)) for n, xs in acc.items() if np.mean(xs) > 0}
        pool = [(cid, s) for cid, s in dense_pool[: cfg.passage_seed_k] if self.graph.has_node(chunk(cid))]
        if pool and cfg.passage_node_weight > 0:
            lo, hi = min(s for _, s in pool), max(s for _, s in pool)
            for cid, s in pool:
                x = (s - lo) / (hi - lo) if hi > lo else 1.0
                if x > 0:
                    reset[chunk(cid)] = reset.get(chunk(cid), 0.0) + cfg.passage_node_weight * x
        return reset

    def _fact_ends(self, fid: str) -> Tuple[str, ...]:
        ends = self.graph._fact_ends.get(fid)
        if ends is None:
            f = self.store.get("facts", (fid,))
            ends = (f["subject_entity_id"], f["object_entity_id"]) if f else ()
        return tuple(ends)

    def reset_vector(self, facts, ents, chunks) -> Dict[str, float]:
        """Reset mass: facts 0.5, entities 0.2, chunks 0.3, renormalised over the seed sources that are
        actually present in the graph (no facts -> their share is redistributed to entities and chunks)."""
        groups = []
        for items, prefix_fn, total, transform in ((facts, fact, 0.5, lambda s: max(s, 0.0) ** 2),
                                                   (ents, ent, 0.2, lambda s: max(s, 0.0) ** 2),
                                                   (chunks, chunk, 0.3, lambda s: s)):
            vals = [(prefix_fn(i), transform(s)) for i, s in items if transform(s) > 0 and self.graph.has_node(prefix_fn(i))]
            z = sum(v for _, v in vals)
            if z > 0:
                groups.append((total, [(n, v / z) for n, v in vals]))
        present = sum(t for t, _ in groups)
        reset: Dict[str, float] = {}
        for total, vals in groups:
            for n, v in vals:
                reset[n] = reset.get(n, 0.0) + (total / present) * v
        return reset

    @staticmethod
    def _seed_scores(chunks) -> Dict[str, float]:
        """Hybrid (RRF) seed scores rescaled to [0, 1] by rank position."""
        if not chunks:
            return {}
        mx = chunks[0][1] or 1.0
        return {cid: s / mx for cid, s in chunks}

    # ---- one retrieval round ----------------------------------------------
    def retrieve_once(self, question: str) -> RetrievalResult:
        cfg = self.config
        facts, ents, chunks = self.seeds(question)
        hippo = cfg.seed_mode == "hipporag"
        reset = self.hipporag_reset(facts, self._dense_pool) if hippo else self.reset_vector(facts, ents, chunks)
        scores = self.graph.ppr(reset) if reset else {}
        chunk_scores = {n[2:]: s for n, s in scores.items() if n.startswith("c:")}
        ranked = sorted(chunk_scores.items(), key=lambda x: -x[1])[: cfg.ppr_top_chunks]
        cand = [cid for cid, _ in ranked]
        self.last_trace["ppr"] = list(cand)
        # hybrid mode: the dense/BM25 seeds are always candidates (PPR must never lose the seeds it started
        # from). In hipporag mode every dense seed already carries reset mass, so the pool is the PPR top-k.
        seed_score = self._seed_scores(chunks)
        if not hippo:
            for cid in seed_score:
                if cid not in chunk_scores:
                    cand.append(cid)
                    chunk_scores[cid] = 0.0
        rows = self.store.get_many("chunks", [(c,) for c in cand])
        cand = [c for c in cand if (c,) in rows]
        ppr_rank = {c: i for i, c in enumerate(sorted(cand, key=lambda c: -chunk_scores[c]))}
        best = 0.0
        tiebreak = ppr_rank
        if self.reranker is not None and cand:
            probs = self.reranker.score(question, [rows[(c,)]["text"] for c in cand])
            rer = dict(zip(cand, probs))
            best = max(probs)
            self.last_trace["rerank"] = sorted(cand, key=lambda c: -rer[c])
            if cfg.rerank_fusion == "rrf_ppr":
                # the reranker alone discards the graph evidence; fuse its rank with the PPR rank
                k, wr = cfg.rerank_fusion_k, cfg.rerank_fusion_weight
                rr_rank = {c: i for i, c in enumerate(self.last_trace["rerank"])}
                rer = {c: wr / (k + 1 + rr_rank[c]) + 1.0 / (k + 1 + ppr_rank[c]) for c in cand}
                tiebreak = rr_rank   # equal fused scores (rank swaps) go to the reranker's order
        else:
            mx = max((chunk_scores[c] for c in cand), default=1.0) or 1.0
            rer = {c: chunk_scores[c] / mx for c in cand}
            best = max(rer.values(), default=0.0)
            self.last_trace["rerank"] = sorted(cand, key=lambda c: -rer[c])
        # optionally blend with the seed score so a seed the reranker dislikes still ranks by its seed evidence
        b = cfg.seed_blend
        if b:
            rer = {c: (1 - b) * rer[c] + b * seed_score.get(c, 0.0) for c in cand}
        order = sorted(cand, key=lambda c: (-rer[c], tiebreak[c]))
        # always return at least min_ranked ids: continue with the remaining PPR chunks by score
        if len(order) < cfg.min_ranked:
            for cid, s in sorted(chunk_scores.items(), key=lambda x: -x[1]):
                if cid not in rer:
                    rer[cid] = 0.0
                    order.append(cid)
                if len(order) >= cfg.min_ranked:
                    break
        top = order[: cfg.final_chunks]
        if cfg.rerank_fusion != "rrf_ppr" or self.reranker is None:
            best = rer[order[0]] if order else 0.0
        coverage = self._coverage(ents, top)
        res = RetrievalResult(ranked_chunk_ids=order, context="", chunk_scores=rer,
                              seed_facts=facts, seed_entities=ents, seed_chunks=chunks,
                              best_rerank=best, coverage=coverage)
        res.top_facts = self._top_facts(scores) if self.graph.fact_nodes else self._top_facts_by_entities(scores, facts)
        res.top_mentions = self._top_mentions(scores, ents, top)
        return res

    def _coverage(self, ents, top_chunks: List[str]) -> float:
        strong = [e for e, s in ents if s >= 0.6]
        if not strong or not top_chunks:
            return 1.0
        covered = 0
        for eid in strong:
            ms = self.store.select("mentions", {"entity_id": eid, "chunk_id": top_chunks})
            if ms:
                covered += 1
        return covered / len(strong)

    def _top_facts(self, scores: Dict[str, float]) -> List[dict]:
        cfg = self.config
        fs = sorted(((n[2:], s) for n, s in scores.items() if n.startswith("f:")), key=lambda x: -x[1])[: cfg.top_facts]
        out = []
        for fid, s in fs:
            f = self.store.get("facts", (fid,))
            if not f:
                continue
            srcs = self.store.select("fact_sources", {"fact_id": fid})
            out.append({"fact_id": fid, "sentence": f["sentence"], "score": s,
                        "evidence": [(x["chunk_id"], x["evidence_span"]) for x in srcs]})
        return out

    def _top_facts_by_entities(self, scores: Dict[str, float], facts) -> List[dict]:
        """Without fact nodes: rank the query-similar facts by the PPR mass of their two entities."""
        cfg = self.config
        scored = []
        for fid, _ in facts:
            ends = self._fact_ends(fid)
            scored.append((fid, sum(scores.get(ent(e), 0.0) for e in set(ends))))
        scored.sort(key=lambda x: -x[1])
        out = []
        for fid, s in scored[: cfg.top_facts]:
            f = self.store.get("facts", (fid,))
            if not f:
                continue
            srcs = self.store.select("fact_sources", {"fact_id": fid})
            out.append({"fact_id": fid, "sentence": f["sentence"], "score": s,
                        "evidence": [(x["chunk_id"], x["evidence_span"]) for x in srcs]})
        return out

    def _top_mentions(self, scores: Dict[str, float], ents, top_chunks: List[str]) -> List[dict]:
        cfg = self.config
        seed_ids = [e for e, _ in ents[:5]]
        out = []
        for eid in seed_ids:
            e = self.store.get("entities", (eid,))
            if not e:
                continue
            ms = self.store.select("mentions", {"entity_id": eid})
            ms.sort(key=lambda m: -scores.get(chunk(m["chunk_id"]), 0.0))
            for m in ms[:2]:
                if m["description"]:
                    out.append({"entity": e["canonical_name"], "chunk_id": m["chunk_id"], "description": m["description"]})
            if len(out) >= cfg.top_mentions:
                break
        return out[: cfg.top_mentions]

    # ---- full pipeline with gate ------------------------------------------
    def retrieve(self, question: str, decompose: Optional[Callable[[str], List[str]]] = None) -> RetrievalResult:
        cfg = self.config
        res = self.retrieve_once(question)
        gate_ok = res.best_rerank >= cfg.gate_rerank_threshold and res.coverage >= cfg.gate_coverage_threshold
        if not gate_ok and cfg.enable_decomposition and decompose is not None:
            subs = [s for s in decompose(question) if s.strip() and s.strip() != question.strip()]
            if subs:
                merged: Dict[str, float] = dict(res.chunk_scores)
                facts_acc = {f["fact_id"]: f for f in res.top_facts}
                ments = list(res.top_mentions)
                for sq in subs[: cfg.max_subquestions]:
                    r2 = self.retrieve_once(sq)
                    for cid, s in r2.chunk_scores.items():
                        merged[cid] = max(merged.get(cid, 0.0), s)
                    for f in r2.top_facts:
                        facts_acc.setdefault(f["fact_id"], f)
                    ments.extend(r2.top_mentions)
                cand = sorted(merged, key=lambda c: -merged[c])[: cfg.ppr_top_chunks]
                rows = self.store.get_many("chunks", [(c,) for c in cand])
                cand = [c for c in cand if (c,) in rows]
                if self.reranker is not None and cand:
                    probs = self.reranker.score(question, [rows[(c,)]["text"] for c in cand])
                    rer = dict(zip(cand, probs))
                else:
                    rer = {c: merged[c] for c in cand}
                order = sorted(cand, key=lambda c: -rer[c])
                res = RetrievalResult(ranked_chunk_ids=order, context="", chunk_scores=rer,
                                      seed_facts=res.seed_facts, seed_entities=res.seed_entities, seed_chunks=res.seed_chunks,
                                      best_rerank=rer[order[0]] if order else 0.0, coverage=res.coverage,
                                      escalated=True, subquestions=subs,
                                      top_facts=sorted(facts_acc.values(), key=lambda f: -f["score"])[: cfg.top_facts],
                                      top_mentions=ments[: cfg.top_mentions])
        self._attach_hybrid(question, res)
        res.context = self.assemble_context(res)
        self.last_trace["graph"] = list(res.graph_chunk_ids)
        self.last_trace["fused"] = list(res.fused_chunk_ids)
        self.last_trace["final"] = list(res.ranked_chunk_ids)
        return res

    def _attach_hybrid(self, question: str, res: RetrievalResult) -> None:
        """Run the hybrid channel once for the original question and compute the fused ranking."""
        cfg = self.config
        res.graph_chunk_ids = list(res.ranked_chunk_ids)
        res.fused_chunk_ids = list(res.ranked_chunk_ids)
        if self.hybrid is None:
            return
        from .hybrid_es import rrf_fuse
        qp = self.embedder.encode_query(question)   # same bge query-instruction encoding as the dense seeds (cached)
        hits = self.hybrid.search(question, qp, max(cfg.hybrid_window, cfg.hybrid_k))
        rows = self.store.get_many("chunks", [(c,) for c, _ in hits])
        hits = [(c, s) for c, s in hits if (c,) in rows]   # never surface an id the store no longer has
        res.hybrid_chunk_ids = [c for c, _ in hits]
        res.hybrid_scores = dict(hits)
        last = getattr(self.hybrid, "last", {}) or {}
        self.last_trace["hybrid"] = list(res.hybrid_chunk_ids)
        for name in ("bm25", "knn"):
            if name in last:
                self.last_trace[f"hybrid_{name}"] = list(last[name])
        res.fused_chunk_ids = [c for c, _ in rrf_fuse([res.graph_chunk_ids, res.hybrid_chunk_ids], k=cfg.fused_rrf_k)]
        if cfg.ranking_output == "fused":
            res.ranked_chunk_ids = list(res.fused_chunk_ids)

    # ---- context ---------------------------------------------------------
    def assemble_context(self, res: RetrievalResult) -> str:
        """Facts, [Entity notes (context_entity_notes)], graph passages (top final_chunks), and, with the
        hybrid channel on, the hybrid top hybrid_k minus the graph passages in a separate section."""
        cfg = self.config
        budget = cfg.context_token_budget
        graph = res.graph_chunk_ids or res.ranked_chunk_ids
        top = list(dict.fromkeys(graph[: cfg.final_chunks]))
        in_top = set(top)
        extra = [c for c in dict.fromkeys(res.hybrid_chunk_ids[: cfg.hybrid_k]) if c not in in_top]
        rows = self.store.get_many("chunks", [(c,) for c in top + extra])

        def order(ids: List[str]) -> List[str]:
            ids = [c for c in ids if (c,) in rows]
            if cfg.context_order == "doc":
                return sorted(ids, key=lambda c: (rows[(c,)]["doc_id"], rows[(c,)]["ordinal"]))
            return ids

        parts: List[str] = []
        used = 0
        # facts first (short, high value)
        if res.top_facts:
            lines = ["Facts:"]
            for f in res.top_facts:
                ev = "; ".join(f'"{span}" [{cid}]' for cid, span in f["evidence"] if span)[:400]
                line = f"- {f['sentence']}" + (f" (evidence: {ev})" if ev else "")
                t = estimate_tokens(line)
                if used + t > budget * 0.25:
                    break
                lines.append(line)
                used += t
            if len(lines) > 1:
                parts.append("\n".join(lines))
        if cfg.context_entity_notes and res.top_mentions:
            lines = ["Entity notes:"]
            for m in res.top_mentions:
                line = f"- {m['entity']}: {m['description']} [{m['chunk_id']}]"
                t = estimate_tokens(line)
                if used + t > budget * 0.35:
                    break
                lines.append(line)
                used += t
            if len(lines) > 1:
                parts.append("\n".join(lines))
        hybrid_on = self.hybrid is not None or bool(res.hybrid_chunk_ids)
        sections = [("Graph passages:" if hybrid_on else "Passages:", order(top), res.context_graph_ids)]
        if hybrid_on:
            sections.append(("Keyword and semantic search results:", order(extra), res.context_hybrid_ids))
        del res.context_graph_ids[:], res.context_hybrid_ids[:]
        for header, ids, sent in sections:
            lines = [header]
            for cid in ids:
                r = rows[(cid,)]
                block = f"[{cid}]\n{r['text']}"
                t = estimate_tokens(block)
                if used + t > budget:
                    if used < budget * 0.5:  # always include at least part of the top passage
                        words = r["text"].split()
                        keep = max(50, int(len(words) * (budget - used) / max(t, 1)))
                        block = f"[{cid}]\n" + " ".join(words[:keep]) + " ..."
                        lines.append(block)
                        sent.append(cid)
                    used = budget
                    break
                lines.append(block)
                sent.append(cid)
                used += t
            if len(lines) > 1 or header == "Passages:":
                parts.append("\n\n".join(lines))
            if used >= budget:
                break
        return "\n\n".join(parts)
