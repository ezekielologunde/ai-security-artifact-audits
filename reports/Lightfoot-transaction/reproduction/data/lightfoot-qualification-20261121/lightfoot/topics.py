"""Lazy topic summaries (design section 7).

Entities are clustered by k-means over their name embeddings (no LLM). A topic is a
cluster plus the set of chunk ids reachable through its entities' mentions. The
summary is produced on demand by one LLM call and cached under the hash of the
chunk set; any insert or delete that touches a chunk in the set changes the hash,
so the cached summary is simply not found and is regenerated on demand. Deletes
also remove cache rows covering a deleted chunk (ledger.delete_chunks).
"""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .config import LightfootConfig
from .costs import CallRecord
from .llm import LLMCaller, LLMClient, LLMRefusal, make_client
from .store.base import Store

_GLOBAL_RE = re.compile(r"\b(overall|themes?|summar(y|ise|ize)|compare across|across (the|all)|main (topics|ideas)|"
                        r"what (are|were) the (key|main|major)|big picture|in general|trends?)\b", re.I)

TOPIC_SYSTEM = ("Summarise the main points of the passages in at most 150 words. Mention the key entities by name. "
                "Cite chunk ids in square brackets.")


def is_global_question(q: str) -> bool:
    return bool(_GLOBAL_RE.search(q))


@dataclass
class Topic:
    topic_key: str
    entity_ids: List[str]
    chunk_ids: List[str]
    chunk_set_hash: str
    centroid: np.ndarray
    entity_names: List[str] = field(default_factory=list)


class TopicIndex:
    def __init__(self, store: Store, config: LightfootConfig,
                 cost_callback: Optional[Callable[[CallRecord], None]] = None, client=None,
                 llm: Optional[LLMClient] = None) -> None:
        self.store = store
        self.config = config
        self.cost_callback = cost_callback
        self._llm = llm
        self._raw_client = client
        self._caller: Optional[LLMCaller] = None
        self._topics: Optional[List[Topic]] = None

    @property
    def caller(self) -> LLMCaller:
        if self._caller is None:
            llm = self._llm or make_client(raw_client=self._raw_client)
            self._caller = LLMCaller(llm, self.config.answer_model, self.cost_callback, self.config.extract_max_retries)
        return self._caller

    def invalidate(self) -> None:
        self._topics = None

    # ---- clustering ------------------------------------------------------
    def topics(self) -> List[Topic]:
        if self._topics is not None:
            return self._topics
        cfg = self.config
        keys, mat = self.store.all_vectors("entities", {"tenant": cfg.tenant})
        if len(keys) == 0:
            self._topics = []
            return self._topics
        k = max(1, min(cfg.topics_k, len(keys)))
        if k == 1 or len(keys) < 3:
            labels = np.zeros(len(keys), dtype=int)
            centroids = mat.mean(axis=0, keepdims=True)
        else:
            from scipy.cluster.vq import kmeans2
            centroids, labels = kmeans2(mat.astype(np.float64), k, minit="++", seed=0)
        topics: List[Topic] = []
        for c in range(int(labels.max()) + 1):
            idx = np.nonzero(labels == c)[0]
            if len(idx) == 0:
                continue
            eids = sorted(keys[i][0] for i in idx)
            chunk_ids = set()
            names = []
            for eid in eids:
                for m in self.store.select("mentions", {"entity_id": eid}):
                    chunk_ids.add(m["chunk_id"])
                e = self.store.get("entities", (eid,))
                if e:
                    names.append(e["canonical_name"])
            cids = sorted(chunk_ids)
            h = hashlib.sha256("\n".join(cids).encode()).hexdigest()
            topics.append(Topic(f"{cfg.tenant}:k{k}:c{c}", eids, cids, h, np.asarray(centroids[c], dtype=np.float32), names))
        self._topics = topics
        return topics

    def topics_for_query(self, query_vec: np.ndarray, seed_entity_ids: Sequence[str]) -> List[Topic]:
        ts = self.topics()
        if not ts:
            return []
        seeds = set(seed_entity_ids)

        def score(t: Topic) -> float:
            overlap = len(seeds & set(t.entity_ids)) / max(1, len(seeds)) if seeds else 0.0
            c = t.centroid / (np.linalg.norm(t.centroid) or 1.0)
            return overlap + 0.5 * float(c @ query_vec)
        return sorted(ts, key=score, reverse=True)[: self.config.topics_per_query]

    # ---- lazy summaries ----------------------------------------------------
    def summary(self, topic: Topic) -> str:
        row = self.store.get("topic_cache", (topic.topic_key,))
        if row and row["chunk_set_hash"] == topic.chunk_set_hash and row.get("summary"):
            return row["summary"]
        text = self._summarise(topic)
        with self.store.transaction():
            self.store.put("topic_cache", {"topic_key": topic.topic_key, "tenant": self.config.tenant,
                                           "chunk_set_hash": topic.chunk_set_hash, "chunk_ids": topic.chunk_ids,
                                           "summary": text, "created_at": time.time()})
        return text

    def _summarise(self, topic: Topic) -> str:
        rows = self.store.get_many("chunks", [(c,) for c in topic.chunk_ids[:20]])
        passages = "\n\n".join(f"[{cid}]\n{r['text']}" for (cid,), r in rows.items())
        if self.config.mock:
            if self.cost_callback:
                self.cost_callback(CallRecord(kind="topic", model="mock", mock=True))
            return f"MOCK TOPIC SUMMARY ({len(topic.chunk_ids)} chunks; entities: {', '.join(topic.entity_names[:8])}): " + passages[:200].replace("\n", " ")
        try:
            return self.caller.text("topic", TOPIC_SYSTEM, passages, 400)
        except LLMRefusal:
            return ""
