"""SQLite backend: sqlite3 for rows, numpy arrays on disk for vectors.

Vectors live in one `NumpyIndex` per vector-bearing table, held in memory (a
growable float32 matrix with tombstones, so appends are O(1) amortised) and
written to `<db>.vec/<table>.npz` on commit when dirty. Each vector may carry
filter labels (tenant, type) so filtered searches never touch SQL.

Provenance lookups use a `chunk_refs(tbl, chunk_id, k1, k2)` side table that is
maintained on every put/delete, so `rows_with_prov` is an index lookup instead
of a JSON scan over the whole table.

Pragmas for the benchmark store: WAL journal, synchronous=NORMAL.
"""
from __future__ import annotations

import atexit
import os
import sqlite3
import time
import weakref
from contextlib import contextmanager
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

import numpy as np

from .base import Store, TABLES, TableSpec
from .sql_common import SQLStoreMixin

_KEY_SEP = "\x1f"


def _kstr(key: Tuple) -> str:
    return _KEY_SEP.join(str(k) for k in key)


def _kparse(s: str, n: int) -> Tuple:
    parts = s.split(_KEY_SEP)
    assert len(parts) == n
    return tuple(parts)


class NumpyIndex:
    """Brute-force cosine index over normalised float32 vectors with O(1) append."""

    def __init__(self, dim: int, attr_names: Sequence[str] = ()) -> None:
        self.dim = dim
        self.attr_names = tuple(attr_names)
        self._cap = 1024
        self._mat = np.zeros((self._cap, dim), dtype=np.float32)
        self._ids: List[Optional[str]] = []
        self._row: Dict[str, int] = {}
        self._attrs: Dict[str, List[Optional[str]]] = {a: [] for a in self.attr_names}
        self._alive = np.zeros(self._cap, dtype=bool)
        self._n = 0
        self._dead = 0
        self.dirty = False

    # ---- mutation ------------------------------------------------------
    def _grow(self, need: int) -> None:
        if self._n + need <= self._cap:
            return
        new_cap = max(self._cap * 2, self._n + need)
        mat = np.zeros((new_cap, self.dim), dtype=np.float32)
        mat[: self._n] = self._mat[: self._n]
        alive = np.zeros(new_cap, dtype=bool)
        alive[: self._n] = self._alive[: self._n]
        self._mat, self._alive, self._cap = mat, alive, new_cap

    @staticmethod
    def _norm(v: np.ndarray) -> np.ndarray:
        v = np.asarray(v, dtype=np.float32).reshape(-1)
        n = np.linalg.norm(v)
        return v / n if n > 0 else v

    def set(self, key: str, vec: np.ndarray, attrs: Optional[Dict] = None) -> None:
        v = self._norm(vec)
        r = self._row.get(key)
        if r is not None:
            self._mat[r] = v
        else:
            self._grow(1)
            r = self._n
            self._mat[r] = v
            self._alive[r] = True
            self._ids.append(key)
            self._row[key] = r
            for a in self.attr_names:
                self._attrs[a].append(None)
            self._n += 1
        if attrs:
            for a in self.attr_names:
                if a in attrs:
                    self._attrs[a][r] = attrs[a]
        self.dirty = True

    def set_many(self, keys: Sequence[str], mat: np.ndarray, attrs: Optional[Sequence[Dict]] = None) -> None:
        mat = np.asarray(mat, dtype=np.float32)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        mat = mat / norms
        new_idx = [i for i, k in enumerate(keys) if k not in self._row]
        self._grow(len(new_idx))
        for i, k in enumerate(keys):
            r = self._row.get(k)
            if r is None:
                r = self._n
                self._alive[r] = True
                self._ids.append(k)
                self._row[k] = r
                for a in self.attr_names:
                    self._attrs[a].append(None)
                self._n += 1
            self._mat[r] = mat[i]
            if attrs:
                for a in self.attr_names:
                    if a in attrs[i]:
                        self._attrs[a][r] = attrs[i][a]
        self.dirty = True

    def get(self, key: str) -> Optional[np.ndarray]:
        r = self._row.get(key)
        return None if r is None else self._mat[r]

    def delete(self, key: str) -> None:
        r = self._row.pop(key, None)
        if r is None:
            return
        self._alive[r] = False
        self._ids[r] = None
        self._mat[r] = 0
        self._dead += 1
        self.dirty = True
        if self._dead > 1024 and self._dead > self._n // 4:
            self._compact()

    def _compact(self) -> None:
        keep = np.nonzero(self._alive[: self._n])[0]
        mat = np.zeros((max(1024, len(keep) * 2), self.dim), dtype=np.float32)
        mat[: len(keep)] = self._mat[keep]
        ids = [self._ids[i] for i in keep]
        attrs = {a: [self._attrs[a][i] for i in keep] for a in self.attr_names}
        self._mat, self._cap = mat, mat.shape[0]
        self._alive = np.zeros(self._cap, dtype=bool)
        self._alive[: len(keep)] = True
        self._ids, self._attrs, self._n, self._dead = ids, attrs, len(keep), 0
        self._row = {k: i for i, k in enumerate(ids)}

    def __len__(self) -> int:
        return self._n - self._dead

    # ---- query ---------------------------------------------------------
    def _mask(self, where: Optional[Dict]) -> Optional[np.ndarray]:
        if not where:
            return None
        mask = np.ones(self._n, dtype=bool)
        for a, val in where.items():
            col = np.array(self._attrs[a][: self._n], dtype=object)
            if isinstance(val, (list, tuple, set)):
                mask &= np.isin(col, list(val))
            else:
                mask &= col == val
        return mask

    def can_filter(self, where: Optional[Dict]) -> bool:
        return not where or all(a in self.attr_names for a in where)

    def search(self, vec: np.ndarray, k: int, where: Optional[Dict] = None, allowed: Optional[set] = None) -> List[Tuple[str, float]]:
        n = self._n
        if n == 0 or k <= 0:
            return []
        scores = self._mat[:n] @ self._norm(vec)
        valid = self._alive[:n].copy()
        m = self._mask(where)
        if m is not None:
            valid &= m
        if allowed is not None:
            valid &= np.fromiter((i in allowed for i in self._ids[:n]), dtype=bool, count=n)
        scores = np.where(valid, scores, -np.inf)
        k = min(k, n)
        idx = np.argpartition(-scores, k - 1)[:k] if k < n else np.arange(n)
        idx = idx[np.argsort(-scores[idx])]
        return [(self._ids[i], float(scores[i])) for i in idx if np.isfinite(scores[i])]

    def all(self, where: Optional[Dict] = None) -> Tuple[List[str], np.ndarray]:
        n = self._n
        valid = self._alive[:n].copy()
        m = self._mask(where)
        if m is not None:
            valid &= m
        keep = np.nonzero(valid)[0]
        return [self._ids[i] for i in keep], self._mat[keep].copy()

    def matrix_view(self) -> Tuple[List[Optional[str]], np.ndarray, np.ndarray]:
        """(ids, matrix, alive) views over live rows, no copy. Rows with alive=False are tombstones."""
        return self._ids[: self._n], self._mat[: self._n], self._alive[: self._n]

    # ---- persistence -----------------------------------------------------
    def save(self, path: str) -> None:
        ids, mat = self.all()
        attrs = {f"attr_{a}": np.array([self._attrs[a][self._row[i]] for i in ids], dtype=object) for a in self.attr_names}
        tmp = path + ".tmp.npz"
        np.savez(tmp, ids=np.array(ids, dtype=object), matrix=mat, **attrs)
        os.replace(tmp, path)
        self.dirty = False

    def load(self, path: str) -> None:
        self.__init__(self.dim, self.attr_names)
        if os.path.exists(path):
            data = np.load(path, allow_pickle=True)
            ids = [str(i) for i in data["ids"]]
            attrs = None
            if self.attr_names and all(f"attr_{a}" in data for a in self.attr_names):
                cols = {a: data[f"attr_{a}"] for a in self.attr_names}
                attrs = [{a: (None if cols[a][i] is None else str(cols[a][i])) for a in self.attr_names} for i in range(len(ids))]
            if ids:
                self.set_many(ids, data["matrix"], attrs)
        self.dirty = False


_ATTRS = {"chunks": ("tenant",), "entities": ("tenant", "type"), "aliases": ("tenant",), "facts": ("tenant",)}

_DDL = """
CREATE TABLE IF NOT EXISTS documents (doc_id TEXT PRIMARY KEY, content_hash TEXT, tenant TEXT, metadata TEXT, created_at REAL);
CREATE TABLE IF NOT EXISTS chunks (chunk_id TEXT PRIMARY KEY, doc_id TEXT, tenant TEXT, ordinal INTEGER, text TEXT, tokens INTEGER);
CREATE INDEX IF NOT EXISTS chunks_doc ON chunks(doc_id);
CREATE TABLE IF NOT EXISTS entities (entity_id TEXT PRIMARY KEY, tenant TEXT, canonical_name TEXT, type TEXT, prov TEXT);
CREATE INDEX IF NOT EXISTS entities_type ON entities(tenant, type);
CREATE TABLE IF NOT EXISTS aliases (alias_text TEXT, entity_id TEXT, tenant TEXT, prov TEXT, PRIMARY KEY (alias_text, entity_id));
CREATE INDEX IF NOT EXISTS aliases_entity ON aliases(entity_id);
CREATE TABLE IF NOT EXISTS mentions (chunk_id TEXT, entity_id TEXT, description TEXT, prov TEXT, PRIMARY KEY (chunk_id, entity_id));
CREATE INDEX IF NOT EXISTS mentions_entity ON mentions(entity_id);
CREATE TABLE IF NOT EXISTS facts (fact_id TEXT PRIMARY KEY, tenant TEXT, subject_entity_id TEXT, predicate TEXT, object_entity_id TEXT, sentence TEXT, prov TEXT);
CREATE INDEX IF NOT EXISTS facts_subject ON facts(subject_entity_id);
CREATE INDEX IF NOT EXISTS facts_object ON facts(object_entity_id);
CREATE TABLE IF NOT EXISTS fact_sources (fact_id TEXT, chunk_id TEXT, evidence_span TEXT, prov TEXT, PRIMARY KEY (fact_id, chunk_id));
CREATE INDEX IF NOT EXISTS fact_sources_chunk ON fact_sources(chunk_id);
CREATE TABLE IF NOT EXISTS synonyms (entity_a TEXT, entity_b TEXT, tenant TEXT, score REAL, prov TEXT, PRIMARY KEY (entity_a, entity_b));
CREATE INDEX IF NOT EXISTS synonyms_b ON synonyms(entity_b);
CREATE TABLE IF NOT EXISTS forms (chunk_id TEXT, form TEXT, tenant TEXT, type TEXT, name TEXT, description TEXT, ord INTEGER, prov TEXT, PRIMARY KEY (chunk_id, form));
CREATE INDEX IF NOT EXISTS forms_form ON forms(form);
CREATE TABLE IF NOT EXISTS form_links (form_a TEXT, form_b TEXT, tenant TEXT, type TEXT, score REAL, kind TEXT, PRIMARY KEY (form_a, form_b));
CREATE INDEX IF NOT EXISTS form_links_b ON form_links(form_b);
CREATE TABLE IF NOT EXISTS topic_cache (topic_key TEXT PRIMARY KEY, tenant TEXT, chunk_set_hash TEXT, chunk_ids TEXT, summary TEXT, created_at REAL);
CREATE TABLE IF NOT EXISTS chunk_refs (tbl TEXT, chunk_id TEXT, k1 TEXT, k2 TEXT, PRIMARY KEY (tbl, chunk_id, k1, k2)) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS chunk_refs_row ON chunk_refs(tbl, k1, k2);
"""


def _flush_weak(ref) -> None:
    st = ref()
    if st is not None:
        try:
            st.flush()
        except Exception:
            pass


class SQLiteStore(SQLStoreMixin, Store):
    def __init__(self, path: str = ":memory:", dim: int = 768, autosave_interval_s: float = 30.0) -> None:
        self.path = path
        self.dim = dim
        self.autosave_interval_s = autosave_interval_s
        self._last_save = time.time()
        self._closed = False
        self.conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        if path != ":memory:":
            self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA temp_store=MEMORY")
        self.conn.execute("PRAGMA cache_size=-65536")
        self.conn.execute("PRAGMA foreign_keys=OFF")
        self.conn.executescript(_DDL)
        fact_cols = {r[1] for r in self.conn.execute("PRAGMA table_info(facts)")}
        for col in ("subject_form", "object_form"):   # stores created before the surface ledger
            if col not in fact_cols:
                self.conn.execute(f"ALTER TABLE facts ADD COLUMN {col} TEXT")
        self._vec_dir = None if path == ":memory:" else path + ".vec"
        if self._vec_dir:
            os.makedirs(self._vec_dir, exist_ok=True)
        self._indexes: Dict[str, NumpyIndex] = {}
        for name, spec in TABLES.items():
            if spec.vector:
                idx = NumpyIndex(dim, _ATTRS.get(name, ()))
                if self._vec_dir:
                    idx.load(self._vec_path(name))
                self._indexes[name] = idx
        self._in_tx = False
        if self._vec_dir:
            # flush vectors at interpreter exit even if close() is never called
            atexit.register(_flush_weak, weakref.ref(self))

    # ---- SQL plumbing ----------------------------------------------------
    def _ph(self, i: int) -> str:
        return "?"

    def _execute(self, sql: str, params: Tuple = ()):
        return self.conn.execute(sql, params)

    def _executemany(self, sql: str, seq):
        return self.conn.executemany(sql, list(seq))

    def _vec_path(self, table: str) -> str:
        return os.path.join(self._vec_dir, f"{table}.npz")

    # ---- provenance side table -------------------------------------------
    @staticmethod
    def _refs_for(spec: TableSpec, row: Dict) -> List[Tuple[str, str, str, str]]:
        k1 = str(row[spec.key[0]])
        k2 = str(row[spec.key[1]]) if len(spec.key) > 1 else ""
        return [(spec.name, c, k1, k2) for c in (row.get("prov") or {})]

    def put(self, table: str, row: Dict) -> None:
        super().put(table, row)
        spec = TABLES[table]
        if spec.has_prov:
            k1 = str(row[spec.key[0]])
            k2 = str(row[spec.key[1]]) if len(spec.key) > 1 else ""
            self.conn.execute("DELETE FROM chunk_refs WHERE tbl=? AND k1=? AND k2=?", (table, k1, k2))
            self.conn.executemany("INSERT OR IGNORE INTO chunk_refs VALUES (?,?,?,?)", self._refs_for(spec, row))

    def put_many(self, table: str, rows: Sequence[Dict]) -> None:
        if not rows:
            return
        super().put_many(table, rows)
        spec = TABLES[table]
        if spec.has_prov:
            keys = []
            refs = []
            for r in rows:
                k1 = str(r[spec.key[0]])
                k2 = str(r[spec.key[1]]) if len(spec.key) > 1 else ""
                keys.append((table, k1, k2))
                refs.extend(self._refs_for(spec, r))
            self.conn.executemany("DELETE FROM chunk_refs WHERE tbl=? AND k1=? AND k2=?", keys)
            self.conn.executemany("INSERT OR IGNORE INTO chunk_refs VALUES (?,?,?,?)", refs)

    def delete(self, table: str, key: Tuple) -> None:
        super().delete(table, key)
        if TABLES[table].has_prov:
            k2 = str(key[1]) if len(key) > 1 else ""
            self.conn.execute("DELETE FROM chunk_refs WHERE tbl=? AND k1=? AND k2=?", (table, str(key[0]), k2))

    def delete_many(self, table: str, keys: Sequence[Tuple]) -> None:
        if not keys:
            return
        super().delete_many(table, keys)
        if TABLES[table].has_prov:
            self.conn.executemany("DELETE FROM chunk_refs WHERE tbl=? AND k1=? AND k2=?",
                                  [(table, str(k[0]), str(k[1]) if len(k) > 1 else "") for k in keys])

    def rows_with_prov(self, table: str, chunk_id: str) -> List[Dict]:
        spec = TABLES[table]
        assert spec.has_prov, table
        cols = self._plain_cols(spec)
        join = f"t.{spec.key[0]} = r.k1" + (f" AND t.{spec.key[1]} = r.k2" if len(spec.key) > 1 else "")
        cur = self._execute(
            f"SELECT {', '.join('t.' + c for c in cols)} FROM chunk_refs r JOIN {table} t ON {join} "
            f"WHERE r.tbl = ? AND r.chunk_id = ? ORDER BY {', '.join('t.' + k for k in spec.key)}",
            (table, chunk_id),
        )
        return [self._row_from(spec, cols, r) for r in cur.fetchall()]

    def clear(self) -> None:
        for name in list(TABLES) + ["chunk_refs"]:
            self.conn.execute(f"DELETE FROM {name}")
        for name, idx in self._indexes.items():
            idx.__init__(self.dim, _ATTRS.get(name, ()))
            idx.dirty = True
        self._save_vectors(force=True)

    # ---- lifecycle -------------------------------------------------------
    def close(self) -> None:
        if self._closed:
            return
        try:
            self.flush()   # before marking closed: flush() is a no-op on a closed store
        finally:
            self._closed = True
            self.conn.close()

    def flush(self) -> None:
        """Write dirty vector indexes to disk now."""
        if self._vec_dir and not self._closed:
            for name, idx in self._indexes.items():
                if idx.dirty:
                    idx.save(self._vec_path(name))
        self._last_save = time.time()

    def _save_vectors(self, force: bool = False) -> None:
        """Vectors are flushed periodically (autosave_interval_s), on flush()/close() and at exit,
        not on every commit: a commit-time rewrite of a few hundred MB per batch dominated indexing."""
        if not self._vec_dir:
            return
        if force or (time.time() - self._last_save) >= self.autosave_interval_s:
            self.flush()

    def _reload_vectors(self) -> None:
        if self._vec_dir:
            for name, idx in self._indexes.items():
                idx.load(self._vec_path(name))

    @contextmanager
    def transaction(self) -> Iterator[None]:
        if self._in_tx:  # nested: join the outer transaction
            yield
            return
        self._in_tx = True
        snapshot = None
        if not self._vec_dir:
            snapshot = {}
            for n, i in self._indexes.items():
                ids, mat = i.all()
                attrs = [{a: i._attrs[a][i._row[k]] for a in i.attr_names} for k in ids]
                snapshot[n] = (ids, mat, attrs)
        self.conn.execute("BEGIN")
        try:
            yield
        except BaseException:
            self.conn.execute("ROLLBACK")
            if snapshot is not None:
                for n, (ids, mat, attrs) in snapshot.items():
                    idx = self._indexes[n]
                    idx.__init__(self.dim, idx.attr_names)
                    if ids:
                        idx.set_many(ids, mat, attrs)
            else:
                self._reload_vectors()
            self._in_tx = False
            raise
        else:
            self.conn.execute("COMMIT")
            self._save_vectors()
            self._in_tx = False

    # ---- vectors ---------------------------------------------------------
    def _delete_vector(self, table: str, key: Tuple) -> None:
        self._indexes[table].delete(_kstr(key))

    def set_vector(self, table: str, key: Tuple, vec: np.ndarray, attrs: Optional[Dict] = None) -> None:
        self._indexes[table].set(_kstr(key), vec, attrs)

    def set_vectors(self, table: str, keys: Sequence[Tuple], mat: np.ndarray, attrs: Optional[Sequence[Dict]] = None) -> None:
        if len(keys):
            self._indexes[table].set_many([_kstr(k) for k in keys], mat, attrs)

    def get_vector(self, table: str, key: Tuple) -> Optional[np.ndarray]:
        return self._indexes[table].get(_kstr(key))

    def get_vectors(self, table: str, keys: Sequence[Tuple]) -> List[Optional[np.ndarray]]:
        idx = self._indexes[table]
        return [idx.get(_kstr(k)) for k in keys]

    def _allowed(self, table: str, where: Dict) -> Optional[set]:
        spec = TABLES[table]
        return {_kstr(tuple(r[c] for c in spec.key)) for r in self.select(table, where)}

    def search(self, table: str, vec: np.ndarray, k: int, where: Optional[Dict] = None) -> List[Tuple[Tuple, float]]:
        spec = TABLES[table]
        idx = self._indexes[table]
        if idx.can_filter(where):
            hits = idx.search(vec, k, where)
        else:
            allowed = self._allowed(table, where)
            if not allowed:
                return []
            hits = idx.search(vec, k, None, allowed)
        return [(_kparse(h, len(spec.key)), s) for h, s in hits]

    def all_vectors(self, table: str, where: Optional[Dict] = None) -> Tuple[List[Tuple], np.ndarray]:
        spec = TABLES[table]
        idx = self._indexes[table]
        if idx.can_filter(where):
            ids, mat = idx.all(where)
            return [_kparse(i, len(spec.key)) for i in ids], mat
        ids, mat = idx.all()
        keys = [_kparse(i, len(spec.key)) for i in ids]
        allowed = {tuple(r[c] for c in spec.key) for r in self.select(table, where)}
        keep = [i for i, k in enumerate(keys) if k in allowed]
        return [keys[i] for i in keep], (mat[keep] if keep else np.zeros((0, self.dim), np.float32))
