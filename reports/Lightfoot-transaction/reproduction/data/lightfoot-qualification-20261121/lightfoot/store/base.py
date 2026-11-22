"""Storage interface for the Lightfoot ledger (design section 3).

Every ledger table has a key, plain columns, an optional JSON `prov` column and an
optional vector column. The interface is generic over tables so both backends share
one implementation of the ledger logic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class TableSpec:
    name: str
    key: Tuple[str, ...]
    columns: Tuple[str, ...]          # non-key columns (prov included when present)
    json_columns: Tuple[str, ...] = ()
    vector: Optional[str] = None      # name of the vector column, if any
    has_prov: bool = False


TABLES: Dict[str, TableSpec] = {
    "documents": TableSpec("documents", ("doc_id",), ("content_hash", "tenant", "metadata", "created_at"), ("metadata",)),
    "chunks": TableSpec("chunks", ("chunk_id",), ("doc_id", "tenant", "ordinal", "text", "tokens"), (), "embedding"),
    "entities": TableSpec("entities", ("entity_id",), ("tenant", "canonical_name", "type", "prov"), ("prov",), "name_embedding", True),
    "aliases": TableSpec("aliases", ("alias_text", "entity_id"), ("tenant", "prov"), ("prov",), "embedding", True),
    "mentions": TableSpec("mentions", ("chunk_id", "entity_id"), ("description", "prov"), ("prov",), None, True),
    "facts": TableSpec("facts", ("fact_id",), ("tenant", "subject_entity_id", "predicate", "object_entity_id", "sentence", "prov",
                                               "subject_form", "object_form"), ("prov",), "embedding", True),
    "fact_sources": TableSpec("fact_sources", ("fact_id", "chunk_id"), ("evidence_span", "prov"), ("prov",), None, True),
    "synonyms": TableSpec("synonyms", ("entity_a", "entity_b"), ("tenant", "score", "prov"), ("prov",), None, True),
    # surface ledger: one row per (chunk, surface form "TYPE\x1ename"); entities, aliases and mentions are derived
    # from these rows and the form links, so they can be rebuilt exactly after any delete
    "forms": TableSpec("forms", ("chunk_id", "form"), ("tenant", "type", "name", "description", "ord", "prov"), ("prov",), None, True),
    # same-entity edges between surface forms (auto band or judge-approved); a link lives while both forms live
    "form_links": TableSpec("form_links", ("form_a", "form_b"), ("tenant", "type", "score", "kind")),
    "topic_cache": TableSpec("topic_cache", ("topic_key",), ("tenant", "chunk_set_hash", "chunk_ids", "summary", "created_at"), ("chunk_ids",)),
}

# Order in which zero-provenance rows are removed on delete (design section 5).
DELETE_ORDER = ("forms", "mentions", "fact_sources", "aliases", "facts", "entities", "synonyms")


def key_of(table: str, row: Dict) -> Tuple:
    return tuple(row[k] for k in TABLES[table].key)


class Store(ABC):
    """Abstract ledger store. Rows are plain dicts; keys are tuples in TableSpec.key order."""

    dim: int

    # ---- lifecycle -------------------------------------------------------
    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    @contextmanager
    def transaction(self) -> Iterator[None]:
        """All writes inside are atomic; vectors are rolled back with rows."""
        ...

    @abstractmethod
    def clear(self) -> None:
        """Drop every row and vector (used by tests)."""
        ...

    # ---- generic rows ----------------------------------------------------
    @abstractmethod
    def get(self, table: str, key: Tuple) -> Optional[Dict]: ...

    @abstractmethod
    def put(self, table: str, row: Dict) -> None:
        """Upsert a full row (all key + non-key columns present)."""
        ...

    @abstractmethod
    def delete(self, table: str, key: Tuple) -> None: ...

    def put_many(self, table: str, rows: Sequence[Dict]) -> None:
        for r in rows:
            self.put(table, r)

    def delete_many(self, table: str, keys: Sequence[Tuple]) -> None:
        for k in keys:
            self.delete(table, k)

    @abstractmethod
    def select(self, table: str, where: Optional[Dict] = None, limit: Optional[int] = None) -> List[Dict]: ...

    @abstractmethod
    def rows_with_prov(self, table: str, chunk_id: str) -> List[Dict]:
        """Rows whose prov map contains chunk_id."""
        ...

    @abstractmethod
    def count(self, table: str) -> int: ...

    # ---- vectors ---------------------------------------------------------
    @abstractmethod
    def set_vector(self, table: str, key: Tuple, vec: np.ndarray, attrs: Optional[Dict] = None) -> None:
        """attrs: optional filterable labels (tenant, type) kept beside the vector by in-memory backends."""
        ...

    def set_vectors(self, table: str, keys: Sequence[Tuple], mat: np.ndarray, attrs: Optional[Sequence[Dict]] = None) -> None:
        for i, k in enumerate(keys):
            self.set_vector(table, k, mat[i], attrs[i] if attrs else None)

    @abstractmethod
    def get_vector(self, table: str, key: Tuple) -> Optional[np.ndarray]: ...

    @abstractmethod
    def get_vectors(self, table: str, keys: Sequence[Tuple]) -> List[Optional[np.ndarray]]: ...

    @abstractmethod
    def search(self, table: str, vec: np.ndarray, k: int, where: Optional[Dict] = None) -> List[Tuple[Tuple, float]]:
        """Cosine top-k over the table's vector column. Returns (key, score)."""
        ...

    @abstractmethod
    def all_vectors(self, table: str, where: Optional[Dict] = None) -> Tuple[List[Tuple], np.ndarray]:
        """(keys, matrix) for the whole table; used by topics and synonym recompute."""
        ...

    # ---- convenience -----------------------------------------------------
    def get_many(self, table: str, keys: Sequence[Tuple]) -> Dict[Tuple, Dict]:
        out: Dict[Tuple, Dict] = {}
        for k in keys:
            r = self.get(table, k)
            if r is not None:
                out[k] = r
        return out
