"""Embeddings: sentence-transformers bge-base-en-v1.5 on mps when available, normalised."""
from __future__ import annotations

import threading
from typing import Dict, List, Optional, Sequence

import numpy as np

_BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
_NAME_BUCKETS = (32, 64, 128, 512)   # fixed padded lengths for encode_names
_NAME_BATCH = 64


def pick_device() -> str:
    try:
        import torch
        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


class Embedder:
    """Batch encoder with a small in-process cache. All outputs are L2-normalised float32."""

    def __init__(self, model_name: str = "BAAI/bge-base-en-v1.5", device: Optional[str] = None,
                 batch_size: int = 64, cache_size: int = 50000) -> None:
        self.model_name = model_name
        self.device = device or pick_device()
        self.batch_size = batch_size
        self._model = None
        self._lock = threading.Lock()
        self._cache: Dict[str, np.ndarray] = {}
        self._cache_size = cache_size
        self._dim: Optional[int] = None
        self._name_cache: Dict[str, np.ndarray] = {}

    @property
    def model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer
                    self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    @property
    def dim(self) -> int:
        if self._dim is None:
            m = self.model
            fn = getattr(m, "get_embedding_dimension", None) or m.get_sentence_embedding_dimension
            self._dim = int(fn())
        return self._dim

    def encode(self, texts: Sequence[str], show_progress: bool = False) -> np.ndarray:
        texts = list(texts)
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        out: List[Optional[np.ndarray]] = [None] * len(texts)
        todo: List[int] = []
        for i, t in enumerate(texts):
            c = self._cache.get(t)
            if c is not None:
                out[i] = c
            else:
                todo.append(i)
        if todo:
            uniq = list(dict.fromkeys(texts[i] for i in todo))
            vecs = self.model.encode(uniq, batch_size=self.batch_size, normalize_embeddings=True,
                                     convert_to_numpy=True, show_progress_bar=show_progress)
            vecs = np.asarray(vecs, dtype=np.float32)
            lookup = {t: vecs[j] for j, t in enumerate(uniq)}
            for i in todo:
                out[i] = lookup[texts[i]]
            if len(self._cache) + len(uniq) > self._cache_size:
                self._cache.clear()
            self._cache.update(lookup)
        return np.stack(out).astype(np.float32)  # type: ignore[arg-type]

    def encode_names(self, texts: Sequence[str]) -> np.ndarray:
        """Batch-independent encoding for entity names (resolution and synonym edges compare these against
        thresholds, so a name must get bit-identical vectors whatever else is in the batch). Every forward
        pass has the same shape: 64 rows padded to a fixed length bucket (32/64/128/512 tokens), filler
        rows empty. Measured: identical bits under shuffling and subsetting; plain `encode` differs by
        ~3e-7 depending on batch composition."""
        texts = list(texts)
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        todo = list(dict.fromkeys(t for t in texts if t not in self._name_cache))
        if todo:
            import torch
            m = self.model
            tok = m.tokenizer
            lengths = [len(ids) for ids in tok(todo, truncation=True, max_length=512)["input_ids"]]
            buckets: Dict[int, List[str]] = {}
            for t, n in zip(todo, lengths):
                L = next(b for b in _NAME_BUCKETS if n <= b)
                buckets.setdefault(L, []).append(t)
            B = _NAME_BATCH
            for L, group in sorted(buckets.items()):
                for i in range(0, len(group), B):
                    g = group[i:i + B]
                    feats = tok(g + [""] * (B - len(g)), padding="max_length", truncation=True, max_length=L,
                                return_tensors="pt")
                    feats = {k: v.to(m.device) for k, v in feats.items()}
                    with self._lock, torch.no_grad():
                        v = m(feats)["sentence_embedding"]
                    v = torch.nn.functional.normalize(v.float(), dim=-1).cpu().numpy().astype(np.float32)
                    for j, t in enumerate(g):
                        self._name_cache[t] = v[j]
            if len(self._name_cache) > self._cache_size * 4:
                keep = set(texts)
                self._name_cache = {k: v for k, v in self._name_cache.items() if k in keep}
        return np.stack([self._name_cache[t] for t in texts]).astype(np.float32)

    def encode_one(self, text: str) -> np.ndarray:
        return self.encode([text])[0]

    def encode_query(self, text: str) -> np.ndarray:
        """Query-side encoding for passage retrieval (bge instruction prefix)."""
        if "bge" in self.model_name.lower() and "v1.5" in self.model_name:
            return self.encode([_BGE_QUERY_PREFIX + text])[0]
        return self.encode([text])[0]
