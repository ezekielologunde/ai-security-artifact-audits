"""Postgres 16 + pgvector backend (design section 8).

Schema follows design section 3 with pgvector columns, HNSW indexes on the three
embedding columns (plus alias embeddings, needed to revert canonical names on
delete with zero model calls), a GIN index on every `prov` JSONB column and a
tsvector column on chunks for sparse retrieval inside the database.

Connection string: `dsn` argument or env LIGHTFOOT_PG_DSN
(e.g. "postgresql://localhost/lightfoot").
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

import numpy as np

from .base import Store, TABLES
from .sql_common import SQLStoreMixin

try:
    import psycopg
    from psycopg.types.json import Jsonb
    from pgvector.psycopg import register_vector
except ImportError as e:  # pragma: no cover
    raise ImportError("PostgresStore requires psycopg[binary] and pgvector") from e


def _to_np(v) -> np.ndarray:
    """pgvector returns numpy arrays or `Vector` objects depending on version."""
    if hasattr(v, "to_numpy"):
        return np.asarray(v.to_numpy(), dtype=np.float32)
    if hasattr(v, "to_list"):
        return np.asarray(v.to_list(), dtype=np.float32)
    return np.asarray(v, dtype=np.float32)


def _ddl(dim: int) -> str:
    return f"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE TABLE IF NOT EXISTS documents (
  doc_id TEXT PRIMARY KEY, content_hash TEXT, tenant TEXT, metadata JSONB, created_at DOUBLE PRECISION);
CREATE TABLE IF NOT EXISTS chunks (
  chunk_id TEXT PRIMARY KEY, doc_id TEXT, tenant TEXT, ordinal INTEGER, text TEXT, tokens INTEGER,
  embedding vector({dim}),
  bm25_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(text, ''))) STORED);
CREATE INDEX IF NOT EXISTS chunks_doc ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS chunks_tsv ON chunks USING GIN(bm25_tsv);
CREATE INDEX IF NOT EXISTS chunks_emb ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE TABLE IF NOT EXISTS entities (
  entity_id TEXT PRIMARY KEY, tenant TEXT, canonical_name TEXT, type TEXT, prov JSONB, name_embedding vector({dim}));
CREATE INDEX IF NOT EXISTS entities_type ON entities(tenant, type);
CREATE INDEX IF NOT EXISTS entities_prov ON entities USING GIN(prov);
CREATE INDEX IF NOT EXISTS entities_emb ON entities USING hnsw (name_embedding vector_cosine_ops);
CREATE TABLE IF NOT EXISTS aliases (
  alias_text TEXT, entity_id TEXT, tenant TEXT, prov JSONB, embedding vector({dim}), PRIMARY KEY (alias_text, entity_id));
CREATE INDEX IF NOT EXISTS aliases_entity ON aliases(entity_id);
CREATE INDEX IF NOT EXISTS aliases_prov ON aliases USING GIN(prov);
CREATE TABLE IF NOT EXISTS mentions (
  chunk_id TEXT, entity_id TEXT, description TEXT, prov JSONB, PRIMARY KEY (chunk_id, entity_id));
CREATE INDEX IF NOT EXISTS mentions_entity ON mentions(entity_id);
CREATE INDEX IF NOT EXISTS mentions_prov ON mentions USING GIN(prov);
CREATE TABLE IF NOT EXISTS facts (
  fact_id TEXT PRIMARY KEY, tenant TEXT, subject_entity_id TEXT, predicate TEXT, object_entity_id TEXT,
  sentence TEXT, prov JSONB, embedding vector({dim}));
CREATE INDEX IF NOT EXISTS facts_subject ON facts(subject_entity_id);
CREATE INDEX IF NOT EXISTS facts_object ON facts(object_entity_id);
CREATE INDEX IF NOT EXISTS facts_prov ON facts USING GIN(prov);
CREATE INDEX IF NOT EXISTS facts_emb ON facts USING hnsw (embedding vector_cosine_ops);
CREATE TABLE IF NOT EXISTS fact_sources (
  fact_id TEXT, chunk_id TEXT, evidence_span TEXT, prov JSONB, PRIMARY KEY (fact_id, chunk_id));
CREATE INDEX IF NOT EXISTS fact_sources_chunk ON fact_sources(chunk_id);
CREATE INDEX IF NOT EXISTS fact_sources_prov ON fact_sources USING GIN(prov);
CREATE TABLE IF NOT EXISTS synonyms (
  entity_a TEXT, entity_b TEXT, tenant TEXT, score DOUBLE PRECISION, prov JSONB, PRIMARY KEY (entity_a, entity_b));
CREATE INDEX IF NOT EXISTS synonyms_b ON synonyms(entity_b);
CREATE INDEX IF NOT EXISTS synonyms_prov ON synonyms USING GIN(prov);
ALTER TABLE facts ADD COLUMN IF NOT EXISTS subject_form TEXT;
ALTER TABLE facts ADD COLUMN IF NOT EXISTS object_form TEXT;
CREATE TABLE IF NOT EXISTS forms (
  chunk_id TEXT, form TEXT, tenant TEXT, type TEXT, name TEXT, description TEXT, ord INTEGER, prov JSONB,
  PRIMARY KEY (chunk_id, form));
CREATE INDEX IF NOT EXISTS forms_form ON forms(form);
CREATE INDEX IF NOT EXISTS forms_prov ON forms USING GIN(prov);
CREATE TABLE IF NOT EXISTS form_links (
  form_a TEXT, form_b TEXT, tenant TEXT, type TEXT, score DOUBLE PRECISION, kind TEXT, PRIMARY KEY (form_a, form_b));
CREATE INDEX IF NOT EXISTS form_links_b ON form_links(form_b);
CREATE TABLE IF NOT EXISTS topic_cache (
  topic_key TEXT PRIMARY KEY, tenant TEXT, chunk_set_hash TEXT, chunk_ids JSONB, summary TEXT, created_at DOUBLE PRECISION);
"""


class PostgresStore(SQLStoreMixin, Store):
    def __init__(self, dsn: Optional[str] = None, dim: int = 768) -> None:
        self.dsn = dsn or os.environ.get("LIGHTFOOT_PG_DSN", "postgresql://localhost/lightfoot")
        self.dim = dim
        self.conn = psycopg.connect(self.dsn, autocommit=True)
        with self.conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(self.conn)
        with self.conn.cursor() as cur:
            cur.execute(_ddl(dim))
        self._tx_depth = 0

    # ---- SQL plumbing ----------------------------------------------------
    def _ph(self, i: int) -> str:
        return "%s"

    def _execute(self, sql: str, params: Tuple = ()):
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur

    def _executemany(self, sql: str, seq):
        cur = self.conn.cursor()
        cur.executemany(sql, list(seq))
        return cur

    def _prov_contains_sql(self) -> str:
        return "prov ? %s"

    def _encode_json(self, v):
        return Jsonb(v)

    def _decode_json(self, v):
        return v

    # ---- lifecycle -------------------------------------------------------
    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        if self._tx_depth > 0:
            yield
            return
        self._tx_depth += 1
        try:
            with self.conn.transaction():
                yield
        finally:
            self._tx_depth -= 1

    def clear(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute("TRUNCATE " + ", ".join(TABLES))

    # ---- vectors ---------------------------------------------------------
    def _vec_where(self, spec) -> str:
        return " AND ".join(f"{k} = %s" for k in spec.key)

    def set_vector(self, table: str, key: Tuple, vec: np.ndarray, attrs: Optional[Dict] = None) -> None:
        spec = TABLES[table]
        v = np.asarray(vec, dtype=np.float32).reshape(-1)
        n = np.linalg.norm(v)
        if n > 0:
            v = v / n
        self._execute(f"UPDATE {table} SET {spec.vector} = %s WHERE {self._vec_where(spec)}", (v, *key))

    def set_vectors(self, table: str, keys: Sequence[Tuple], mat: np.ndarray, attrs: Optional[Sequence[Dict]] = None) -> None:
        if not len(keys):
            return
        spec = TABLES[table]
        mat = np.asarray(mat, dtype=np.float32)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        mat = mat / norms
        self._executemany(f"UPDATE {table} SET {spec.vector} = %s WHERE {self._vec_where(spec)}",
                          [(mat[i], *k) for i, k in enumerate(keys)])

    def get_vector(self, table: str, key: Tuple) -> Optional[np.ndarray]:
        spec = TABLES[table]
        cur = self._execute(f"SELECT {spec.vector} FROM {table} WHERE {self._vec_where(spec)}", tuple(key))
        r = cur.fetchone()
        if not r or r[0] is None:
            return None
        return _to_np(r[0])

    def get_vectors(self, table: str, keys: Sequence[Tuple]) -> List[Optional[np.ndarray]]:
        return [self.get_vector(table, k) for k in keys]

    def search(self, table: str, vec: np.ndarray, k: int, where: Optional[Dict] = None) -> List[Tuple[Tuple, float]]:
        spec = TABLES[table]
        v = np.asarray(vec, dtype=np.float32).reshape(-1)
        n = np.linalg.norm(v)
        if n > 0:
            v = v / n
        wsql, params = self._where_clause(where)
        cond = f"{wsql} AND {spec.vector} IS NOT NULL" if wsql else f" WHERE {spec.vector} IS NOT NULL"
        cur = self._execute(
            f"SELECT {', '.join(spec.key)}, 1 - ({spec.vector} <=> %s) AS score FROM {table}{cond} "
            f"ORDER BY {spec.vector} <=> %s LIMIT %s",
            (v, *params, v, int(k)),
        )
        rows = cur.fetchall()
        return [(tuple(r[:-1]), float(r[-1])) for r in rows]

    def all_vectors(self, table: str, where: Optional[Dict] = None) -> Tuple[List[Tuple], np.ndarray]:
        spec = TABLES[table]
        wsql, params = self._where_clause(where)
        cond = f"{wsql} AND {spec.vector} IS NOT NULL" if wsql else f" WHERE {spec.vector} IS NOT NULL"
        cur = self._execute(f"SELECT {', '.join(spec.key)}, {spec.vector} FROM {table}{cond} ORDER BY {', '.join(spec.key)}", tuple(params))
        rows = cur.fetchall()
        keys = [tuple(r[:-1]) for r in rows]
        mat = np.stack([_to_np(r[-1]) for r in rows]) if rows else np.zeros((0, self.dim), np.float32)
        return keys, mat

    # ---- extras ----------------------------------------------------------
    def bm25_search(self, query: str, k: int, tenant: Optional[str] = None) -> List[Tuple[str, float]]:
        """Database-side sparse retrieval via tsvector (optional alternative to rank_bm25)."""
        params: list = [query]
        tsql = ""
        if tenant:
            tsql = " AND tenant = %s"
            params.append(tenant)
        cur = self._execute(
            "SELECT chunk_id, ts_rank_cd(bm25_tsv, q) FROM chunks, plainto_tsquery('english', %s) q "
            f"WHERE bm25_tsv @@ q{tsql} ORDER BY 2 DESC LIMIT %s", (*params, int(k)))
        return [(r[0], float(r[1])) for r in cur.fetchall()]
