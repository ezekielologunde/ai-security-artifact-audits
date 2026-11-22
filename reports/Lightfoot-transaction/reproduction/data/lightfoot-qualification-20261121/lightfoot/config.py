"""Configuration for Lightfoot. Everything tunable lives here; env vars give defaults."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


DEFAULT_ENTITY_TYPES: List[str] = [
    "PERSON", "ORGANIZATION", "LOCATION", "EVENT", "PRODUCT",
    "WORK", "CONCEPT", "DATE", "OTHER",
]


@dataclass
class LightfootConfig:
    tenant: str = "default"

    # Models
    extract_model: str = field(default_factory=lambda: os.environ.get("LIGHTFOOT_EXTRACT_LLM", "claude-haiku-5-5"))
    answer_model: str = field(default_factory=lambda: os.environ.get("LIGHTFOOT_ANSWER_LLM", "claude-sonnet-5-5"))
    # entity-resolution judge; empty -> extract_model (the judge is a cheap yes/no task, like extraction)
    judge_model: str = field(default_factory=lambda: os.environ.get("LIGHTFOOT_JUDGE_LLM", ""))
    embed_model: str = field(default_factory=lambda: os.environ.get("LIGHTFOOT_EMBED_MODEL", "BAAI/bge-base-en-v1.5"))
    reranker_model: Optional[str] = field(default_factory=lambda: os.environ.get("LIGHTFOOT_RERANKER", "BAAI/bge-reranker-base"))
    mock: bool = field(default_factory=lambda: _env_bool("LIGHTFOOT_MOCK", False))
    cache_dir: str = field(default_factory=lambda: os.environ.get("LIGHTFOOT_CACHE_DIR", os.path.expanduser("~/.cache/lightfoot")))

    # Extraction
    entity_types: List[str] = field(default_factory=lambda: list(DEFAULT_ENTITY_TYPES))
    extract_max_tokens: int = 1200
    extract_max_entities: int = 12
    extract_max_facts: int = 12
    extract_description_words: int = 8
    extract_evidence_words: int = 12
    extract_effort: str = "low"

    # Indexing throughput
    index_batch_size: int = 64        # documents per extraction/embedding/transaction batch
    extract_concurrency: int = 16     # concurrent real extraction calls per batch
    extract_max_retries: int = 6      # retries on rate limit / overload, exponential backoff

    # Chunking
    chunk_target_tokens: int = 512
    chunk_max_tokens: int = 800
    chunk_overlap: float = 0.10

    # Resolution bands. Two same-type names link iff cosine >= merge_threshold, or cosine is in
    # [judge_threshold, merge_threshold) and the LLM judge says yes. Default: no judge band (judge_threshold ==
    # merge_threshold). On the 2,000-passage MuSiQue slice (141 questions) the judge (0.80 band, double vote,
    # 526 calls) left recall@2/5/10 within noise of no judge (48.1/71.0/85.6 vs 47.9/71.6/85.2) while costing
    # ~$0.26 per 2k passages at provider prices. Re-enable with judge_threshold=0.80 (and judge_votes /
    # judge_output / judge_number_guard below).
    merge_threshold: float = 0.92
    judge_threshold: float = 0.92
    judge_batch_size: int = 20
    judge_votes: int = 2              # 2: forward + reversed call, link only if both agree; 1: one call
    judge_output: str = "decisions"   # "decisions": {"pair","same"} per pair; "compact": list of same pairs
    judge_number_guard: bool = False  # band pairs whose names carry different numbers are not linked, not judged
    synonym_threshold: float = 0.80
    # unused: synonym edges are all entity pairs >= synonym_threshold. A per-entity top-k cap made the edge
    # set depend on which entities existed when each list was computed, which breaks exact erasure.
    synonym_k: int = 0

    # PPR. 0.9 chosen on the MuSiQue tuning split with the hipporag seeding below (0.5 is HippoRAG 2's value;
    # with the original hybrid seeding use 0.5).
    damping: float = 0.9
    ppr_tolerance: float = 1e-6
    ppr_max_iter: int = 100

    # Graph layout. False = HippoRAG 2 layout: entity and chunk nodes only, each fact is an entity-entity
    # edge weighted by fact count. True = original layout with fact nodes linked to entities and chunks.
    graph_fact_nodes: bool = False
    fact_edge_weight: float = 1.0
    graph_synonym_min: float = 0.0    # skip synonym edges below this cosine (stored pairs are >= synonym_threshold)
    hub_percentile: float = 0.0       # >0: cut entities above this degree percentile out of the walk (e.g. 99)
    degree_penalty: str = "none"      # "log": divide edge weight into an entity by log(e + degree)

    # Retrieval
    # seed_mode "hipporag": reset on the subject/object entities of the top link_facts_k facts (fact cosine,
    # divided by the entity's passage count, averaged over facts) plus the top passage_seed_k dense passages
    # (min-max normalised over those, times passage_node_weight). "hybrid": original reset of facts 0.5,
    # entities 0.2, dense+BM25 RRF chunks 0.3 (needs graph_fact_nodes=True to seed fact nodes).
    seed_mode: str = "hipporag"
    link_facts_k: int = 2
    passage_seed_k: int = 100
    passage_node_weight: float = 0.05
    # final ranking over the top ppr_top_chunks PPR candidates:
    #   "rrf_ppr": reciprocal-rank fusion of the reranker rank (weight rerank_fusion_weight) and the PPR rank (weight 1)
    #   "replace": reranker order only (original behaviour)
    rerank_fusion: str = "rrf_ppr"
    rerank_fusion_weight: float = 1.0
    rerank_fusion_k: int = 60
    seed_facts_k: int = 20
    seed_entities_k: int = 10
    seed_chunks_k: int = 10
    bm25_k: int = 10
    ppr_top_chunks: int = 30
    min_ranked: int = 30              # always return at least this many ranked chunk ids
    seed_blend: float = 0.0           # weight of the hybrid seed score blended into the final ranking (measured: >0 hurts)
    final_chunks: int = 10            # graph passages sent to the answer model (was 8)
    top_facts: int = 10
    top_mentions: int = 10
    # Sized for facts + 20 passages (10 graph + up to 10 hybrid). MuSiQue passages: estimate_tokens mean 147,
    # p95 311, p99 438 (incl. the "[chunk id]" line); 20 x p99 = 8.8k, facts <= ~700 on the 2k slice. Was 6000.
    context_token_budget: int = 9000
    context_entity_notes: bool = False   # True: the old "Entity notes:" section (entity mention descriptions)
    context_order: str = "ranked"        # "ranked": passages in retrieval order; "doc": old (doc_id, ordinal) order

    # Hybrid search channel (Elasticsearch BM25 + kNN fused by RRF over the same chunks).
    #   "none": off (default). "es": index chunks into Elasticsearch at index time, delete with their documents,
    #   and send the hybrid top hybrid_k (de-duplicated against the graph passages) as a separate context section.
    hybrid_backend: str = "none"
    hybrid_k: int = 10                # hybrid passages considered for the context
    hybrid_window: int = 30           # length of the hybrid ranking kept for fusion/trace (>= hybrid_k)
    hybrid_rrf_k: int = 60            # RRF constant for BM25 + kNN inside the hybrid channel
    hybrid_num_candidates: int = 200  # kNN num_candidates
    es_url: str = field(default_factory=lambda: os.environ.get("LIGHTFOOT_ES_URL", "http://localhost:9200"))
    es_index: str = ""                # empty: derived from the store path + tenant (runs never share an index)
    es_native_rrf: str = "auto"       # "auto": try the rrf retriever once (needs a paid license), else client-side
    # ranked list returned to callers (and to the benchmark for recall):
    #   "graph": the graph pipeline's ranking (comparable with earlier runs); "fused": RRF of graph and hybrid
    ranking_output: str = "graph"
    fused_rrf_k: int = 60
    gate_rerank_threshold: float = 0.2   # on sigmoid(rerank logit)
    gate_coverage_threshold: float = 0.5
    enable_decomposition: bool = True
    max_subquestions: int = 3

    # Topics
    topics_k: int = 8
    topics_per_query: int = 3

    # Answer
    answer_max_tokens: int = 1500     # floor of 300 is enforced in Answerer
    query_trace: bool = True          # append one JSONL line per query to <store dir>/query_trace.jsonl

    def __post_init__(self) -> None:
        if not self.judge_model:
            self.judge_model = self.extract_model
