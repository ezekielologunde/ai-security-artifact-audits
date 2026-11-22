"""Public entry point: `Lightfoot(store, config)`.

    lf = Lightfoot(SQLiteStore("lf.db"), LightfootConfig(mock=True))
    lf.index_documents([{"doc_id": "a", "text": "..."}])
    res = lf.query("Who founded Acme?")       # QueryResult(answer, ranked_chunk_ids, context, calls)
    lf.delete_documents(["a"])                # zero model calls
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Union

import numpy as np

from .answer import Answerer
from .chunking import Chunk, chunk_document, content_hash, estimate_tokens
from .config import LightfootConfig
from .costs import CallRecord, CostLedger
from .embed import Embedder
from .extract import Extractor, Extraction, ExtractedEntity
from .graph import GraphIndex, ent, fact, chunk as chunk_node
from .ledger import Ledger, Touched, ChunkItem
from .resolve import Candidate, Resolver, MockJudge, LLMJudge, EntityNameIndex, FormIndex
from .retrieve import Retriever, Reranker, RetrievalResult
from .store.base import Store
from .topics import TopicIndex, is_global_question
from .llm import LLMClient, make_client


@dataclass
class QueryResult:
    answer: str                      # short answer span (no explanation, no citations)
    ranked_chunk_ids: List[str]
    context: str
    calls: List[CallRecord]
    retrieval: Optional[RetrievalResult] = None
    latency_s: float = 0.0
    cited_chunk_ids: List[str] = field(default_factory=list)
    unanswerable: bool = False
    answer_raw: str = ""             # the model's raw answer output


@dataclass
class IndexReport:
    documents: int = 0
    skipped: int = 0
    chunks_indexed: int = 0
    chunks_reused: int = 0
    chunks_removed: int = 0
    calls: List[CallRecord] = field(default_factory=list)
    latency_s: float = 0.0


DocLike = Union[Dict, "Document"]


@dataclass
class Document:
    doc_id: str
    text: str
    metadata: Optional[Dict] = None


class Lightfoot:
    def __init__(self, store: Store, config: Optional[LightfootConfig] = None,
                 cost_callback: Optional[Callable[[CallRecord], None]] = None,
                 embedder: Optional[Embedder] = None, reranker: Optional[Reranker] = None,
                 judge=None, client=None, llm: Optional[LLMClient] = None, hybrid=None) -> None:
        """`client`: raw provider SDK client (optional); `llm`: an LLMClient (optional). Provider from
        LIGHTFOOT_LLM_PROVIDER (anthropic | openai) when neither is given. `hybrid`: a HybridES instance
        (optional; built from the config when hybrid_backend="es", tests pass one over a fake client)."""
        self.store = store
        self.config = config or LightfootConfig()
        cfg = self.config
        self.costs = CostLedger()
        self._user_callback = cost_callback
        self._scope: List[CallRecord] = []

        self.embedder = embedder or Embedder(cfg.embed_model)
        self.llm: Optional[LLMClient] = llm if llm is not None else (make_client(raw_client=client) if not cfg.mock else None)
        self.extractor = Extractor(cfg, self._on_call, llm=self.llm) if self.llm else Extractor(cfg, self._on_call, client=client)
        if judge is None:
            if cfg.mock:
                judge = MockJudge(self._on_call)
            else:
                # decisions are cached per pair so a re-index (and the erasure invariant) reuses them
                judge = LLMJudge(cfg.judge_model, cfg.judge_batch_size, self._on_call, llm=self.llm,
                                 concurrency=max(1, cfg.extract_concurrency), cache_dir=cfg.cache_dir,
                                 votes=cfg.judge_votes, output=cfg.judge_output)
        self.name_index = EntityNameIndex.load(store, cfg.tenant, store.dim)
        self.form_index = FormIndex.load(store, cfg.tenant, store.dim)
        self.resolver = Resolver(store, cfg, judge, self.name_index, self.form_index)
        self.ledger = Ledger(store, cfg, self.name_index, self.form_index)
        self.graph = GraphIndex.from_config(cfg)
        self.graph.rebuild_from_store(store, cfg.tenant)
        if reranker is None and cfg.reranker_model and cfg.reranker_model.lower() not in ("none", "off", ""):
            reranker = Reranker(cfg.reranker_model)
        self.hybrid = hybrid if hybrid is not None else self._make_hybrid()
        if self.hybrid is not None:
            # the index mirrors the chunks table exactly (reopened store, interrupted run): reuse stored vectors
            self.hybrid.sync_with_store(store, cfg.tenant)
        self.retriever = Retriever(store, self.embedder, self.graph, cfg, reranker, hybrid=self.hybrid)
        self.answerer = Answerer(cfg, self._on_call, llm=self.llm) if self.llm else Answerer(cfg, self._on_call, client=client)
        self.topics = TopicIndex(store, cfg, self._on_call, llm=self.llm) if self.llm else TopicIndex(store, cfg, self._on_call, client=client)

    def _make_hybrid(self):
        cfg = self.config
        backend = (cfg.hybrid_backend or "none").lower()
        if backend in ("none", "off", ""):
            return None
        if backend != "es":
            raise ValueError(f"unknown hybrid_backend {cfg.hybrid_backend!r} (expected 'es' or 'none')")
        from .hybrid_es import HybridES, index_name_for
        index = cfg.es_index or index_name_for(getattr(self.store, "path", None), cfg.tenant)
        return HybridES(index, dim=self.store.dim, url=cfg.es_url, rrf_k=cfg.hybrid_rrf_k,
                        window=max(cfg.hybrid_window, cfg.hybrid_k), num_candidates=cfg.hybrid_num_candidates,
                        native_rrf=cfg.es_native_rrf)

    # ---- cost plumbing -----------------------------------------------------
    def _on_call(self, rec: CallRecord) -> None:
        self.costs.record(rec)
        self._scope.append(rec)
        if self._user_callback:
            self._user_callback(rec)

    def _begin_scope(self) -> None:
        self._scope = []

    # ---- indexing ----------------------------------------------------------
    def index_documents(self, docs: Iterable[DocLike]) -> IndexReport:
        """Index documents in batches of `config.index_batch_size`: chunk all, extract the whole batch
        (concurrently for the real model), embed everything in a few large encode calls, resolve the batch
        with one matrix multiply, write one transaction, refresh the graph once."""
        t0 = time.time()
        self._begin_scope()
        rep = IndexReport()
        batch: List[Document] = []
        bs = max(1, self.config.index_batch_size)
        for d in docs:
            batch.append(d if isinstance(d, Document) else Document(str(d["doc_id"]), str(d["text"]), d.get("metadata")))
            if len(batch) >= bs:
                self._index_batch(batch, rep)
                batch = []
        if batch:
            self._index_batch(batch, rep)
        self.retriever.invalidate()
        self.topics.invalidate()
        rep.calls = list(self._scope)
        rep.latency_s = time.time() - t0
        return rep

    def _index_batch(self, docs: List[Document], rep: IndexReport) -> None:
        cfg = self.config
        st = self.store
        # dedupe by doc_id (last wins), hash-and-diff against the store
        by_id: Dict[str, Document] = {}
        for d in docs:
            by_id[d.doc_id] = d
        hashes = {k: content_hash(d.text) for k, d in by_id.items()}
        existing = {r["doc_id"]: r for r in st.select("documents", {"doc_id": sorted(by_id)})}
        changed: List[Document] = []
        for k, d in by_id.items():
            if k in existing and existing[k]["content_hash"] == hashes[k]:
                rep.skipped += 1
            else:
                changed.append(d)
        if not changed:
            return
        # chunk everything; chunk-level diff for re-uploads
        chunks_by_doc: Dict[str, List[Chunk]] = {d.doc_id: chunk_document(d.doc_id, d.text, cfg.chunk_target_tokens, cfg.chunk_max_tokens, cfg.chunk_overlap) for d in changed}
        re_ids = [d.doc_id for d in changed if d.doc_id in existing]
        old_chunks: Dict[str, set] = {}
        for r in (st.select("chunks", {"doc_id": re_ids}) if re_ids else []):
            old_chunks.setdefault(r["doc_id"], set()).add(r["chunk_id"])
        removed: List[str] = []
        todo: List[Chunk] = []
        seen_chunk: set = set()
        for d in changed:
            old = old_chunks.get(d.doc_id, set())
            new_ids = {c.chunk_id for c in chunks_by_doc[d.doc_id]}
            removed.extend(sorted(old - new_ids))
            for c in chunks_by_doc[d.doc_id]:
                if c.chunk_id in old:
                    rep.chunks_reused += 1
                elif c.chunk_id not in seen_chunk:
                    seen_chunk.add(c.chunk_id)
                    todo.append(c)
        touched = Touched()
        if removed:
            touched.merge(self.ledger.delete_chunks(removed))
            rep.chunks_removed += len(removed)
        rep.documents += len(changed)

        # 1. one extraction call per chunk (batch-concurrent for the real model)
        extractions = self.extractor.extract_many(todo)
        for ex in extractions:
            self._complete_fact_endpoints(ex)

        # 2. batch embed: all chunk texts, all entity names, all fact texts (triple + evidence) of the batch
        names = sorted({e.name for ex in extractions for e in ex.entities})
        # names are compared against thresholds, so their vectors must not depend on the batch
        encode_names = getattr(self.embedder, "encode_names", self.embedder.encode)
        name_vecs = dict(zip(names, encode_names(names))) if names else {}
        chunk_mat = self.embedder.encode([c.text for c in todo]) if todo else np.zeros((0, self.embedder.dim), np.float32)
        fact_sents = [f.embed_text() for ex in extractions for f in ex.facts]
        fact_mat = self.embedder.encode(fact_sents) if fact_sents else None

        # 3. canonicalize the whole batch (one matmul per type, judge batched)
        cands = [Candidate(c.chunk_id, e.name, e.type, e.description, name_vecs[e.name])
                 for c, ex in zip(todo, extractions) for e in ex.entities]
        resolution = self.resolver.resolve(cands)

        # 4. ledger upsert: one transaction per batch
        items: List[ChunkItem] = []
        fi = 0
        for i, (c, ex) in enumerate(zip(todo, extractions)):
            fe = fact_mat[fi: fi + len(ex.facts)] if fact_mat is not None else None
            fi += len(ex.facts)
            items.append(ChunkItem(c, ex, fe, chunk_mat[i]))
        now = time.time()
        with st.transaction():
            st.put_many("documents", [{"doc_id": d.doc_id, "content_hash": hashes[d.doc_id], "tenant": cfg.tenant,
                                       "metadata": d.metadata or {}, "created_at": now} for d in changed])
            touched.merge(self.ledger.upsert_batch(items, resolution, name_vecs))
        rep.chunks_indexed += len(todo)
        # 5. hybrid index: same chunks, same vectors (no second embedding pass), after the store commit
        if self.hybrid is not None:
            if removed:
                self.hybrid.delete_chunks(removed, refresh=False)
            self.hybrid.index_chunks([{"chunk_id": c.chunk_id, "doc_id": c.doc_id, "text": c.text} for c in todo],
                                     chunk_mat, refresh=True)
        # 6. graph refresh once per batch
        self._apply_touched(touched)

    @staticmethod
    def _complete_fact_endpoints(ex: Extraction) -> None:
        """Facts whose subject/object is not in the entity list get an OTHER entity so the triple is kept."""
        known = {e.name for e in ex.entities}
        for f in ex.facts:
            for n in (f.subject, f.object):
                if n not in known:
                    ex.entities.append(ExtractedEntity(name=n, type="OTHER", description=""))
                    known.add(n)

    def _apply_touched(self, t: Touched) -> None:
        removed = [ent(e) for e in t.removed_entity_ids] + [fact(f) for f in t.removed_fact_ids] + [chunk_node(c) for c in t.removed_chunk_ids]
        self.graph.refresh_from_store(self.store, t.entity_ids - t.removed_entity_ids, t.fact_ids - t.removed_fact_ids,
                                      t.chunk_ids - t.removed_chunk_ids, removed)

    # ---- deletion ----------------------------------------------------------
    def delete_documents(self, doc_ids: Sequence[str]) -> Touched:
        """Erase documents: one transaction, zero model calls (design section 5)."""
        self._begin_scope()
        total = Touched()
        for d in doc_ids:
            total.merge(self.ledger.delete_document(d))
        if self.hybrid is not None and len(doc_ids):
            self.hybrid.delete_docs(list(doc_ids), refresh=True)
        self._apply_touched(total)
        self.retriever.invalidate()
        self.topics.invalidate()
        return total

    # ---- query -------------------------------------------------------------
    def query(self, question: str, answer: bool = True) -> QueryResult:
        t0 = time.time()
        self._begin_scope()
        decompose = self.answerer.decompose if self.config.enable_decomposition else None
        res = self.retriever.retrieve(question, decompose)
        context = res.context
        if is_global_question(question):
            qv = self.embedder.encode_one(question)
            seeds = [e for e, _ in res.seed_entities]
            summaries = [self.topics.summary(t) for t in self.topics.topics_for_query(qv, seeds)]
            summaries = [s for s in summaries if s]
            if summaries:
                context = "Topic summaries:\n" + "\n".join(f"- {s}" for s in summaries) + "\n\n" + context
        if answer:
            ar = self.answerer.answer(question, context, res.ranked_chunk_ids)
            text, cites, unans, raw = ar.answer, ar.cited_chunk_ids, ar.unanswerable, ar.raw
        else:
            text, cites, unans, raw = "", [], False, ""
        qr = QueryResult(answer=text, ranked_chunk_ids=list(res.ranked_chunk_ids), context=context,
                         calls=list(self._scope), retrieval=res, latency_s=time.time() - t0,
                         cited_chunk_ids=cites, unanswerable=unans, answer_raw=raw)
        self._trace_query(question, qr)
        return qr

    # ---- observability -------------------------------------------------------
    def trace_path(self) -> Optional[str]:
        """`<store dir>/query_trace.jsonl` for file-backed stores, else None."""
        if not self.config.query_trace:
            return None
        path = getattr(self.store, "path", None)
        if not path or path == ":memory:":
            return None
        return os.path.join(os.path.dirname(os.path.abspath(path)), "query_trace.jsonl")

    def _trace_query(self, question: str, qr: QueryResult) -> None:
        p = self.trace_path()
        if p is None:
            return
        r = qr.retrieval
        rec = {
            "ts": time.time(), "question": question,
            "gate_fired": bool(r.escalated) if r else False,
            "best_rerank_score": round(float(r.best_rerank), 4) if r else None,
            "seed_coverage": round(float(r.coverage), 4) if r else None,
            "n_rounds": (1 + len(r.subquestions)) if (r and r.escalated) else 1,
            "n_llm_calls": sum(1 for c in qr.calls if c.real),
            "n_calls_by_kind": {k: sum(1 for c in qr.calls if c.kind == k) for k in dict.fromkeys(c.kind for c in qr.calls)},
            "latency_s": round(qr.latency_s, 3),
            "answer": qr.answer, "unanswerable": qr.unanswerable,
            "n_ranked": len(qr.ranked_chunk_ids), "cited": qr.cited_chunk_ids,
            "context_tokens": estimate_tokens(qr.context),
            "usd": round(sum(c.usd for c in qr.calls), 6),
        }
        if r is not None and r.hybrid_chunk_ids:
            # both rankings (and the fused one) so recall of each can be computed from a single run
            rec.update({"ranking_output": self.config.ranking_output, "ranked_graph": r.graph_chunk_ids[:20],
                        "ranked_hybrid": r.hybrid_chunk_ids[:20], "ranked_fused": r.fused_chunk_ids[:20],
                        "context_graph": r.context_graph_ids, "context_hybrid": r.context_hybrid_ids})
        try:
            with open(p, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def retrieve(self, question: str) -> RetrievalResult:
        return self.query(question, answer=False).retrieval  # type: ignore[return-value]

    # ---- introspection -----------------------------------------------------
    def graph_fingerprint(self) -> str:
        return self.ledger.graph_fingerprint()

    def counts(self) -> Dict[str, int]:
        return self.ledger.counts()
