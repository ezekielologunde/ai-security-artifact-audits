"""Generic SQL implementation shared by the SQLite and Postgres backends."""
from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple

from .base import Store, TABLES, TableSpec

_IN_CHUNK = 900  # keep IN-lists under SQLite's parameter limit


def table_name(spec: TableSpec) -> str:
    return spec.name


class SQLStoreMixin:
    """Row-level CRUD over a DB-API connection. Subclasses provide:
    - self._ph(i): placeholder string for the i-th parameter
    - self._execute(sql, params) -> cursor
    - self._prov_contains_sql(): predicate SQL with one placeholder for the chunk id
    - self._encode_json / self._decode_json
    """

    def _ph(self, i: int) -> str:  # pragma: no cover
        raise NotImplementedError

    def _execute(self, sql: str, params: Tuple = ()):  # pragma: no cover
        raise NotImplementedError

    def _prov_contains_sql(self) -> str:  # pragma: no cover
        raise NotImplementedError

    def _encode_json(self, v):
        return json.dumps(v, sort_keys=True, ensure_ascii=False)

    def _decode_json(self, v):
        if v is None or isinstance(v, (dict, list)):
            return v
        return json.loads(v)

    # ---- helpers --------------------------------------------------------
    def _spec(self, table: str) -> TableSpec:
        return TABLES[table]

    def _row_from(self, spec: TableSpec, cols: List[str], values) -> Dict:
        row = dict(zip(cols, values))
        for c in spec.json_columns:
            if c in row:
                row[c] = self._decode_json(row[c])
        return row

    def _plain_cols(self, spec: TableSpec) -> List[str]:
        return list(spec.key) + list(spec.columns)

    def _where_clause(self, where: Optional[Dict], start: int = 0) -> Tuple[str, list]:
        if not where:
            return "", []
        parts = []
        params = []
        i = start
        for col, val in where.items():
            if isinstance(val, (list, tuple, set)):
                vals = list(val)
                if not vals:
                    parts.append("1=0")
                    continue
                phs = ", ".join(self._ph(i + j) for j in range(len(vals)))
                parts.append(f"{col} IN ({phs})")
                params.extend(vals)
                i += len(vals)
            else:
                parts.append(f"{col} = {self._ph(i)}")
                params.append(val)
                i += 1
        return " WHERE " + " AND ".join(parts), params

    # ---- generic rows ----------------------------------------------------
    def get(self, table: str, key: Tuple) -> Optional[Dict]:
        spec = self._spec(table)
        cols = self._plain_cols(spec)
        where = " AND ".join(f"{k} = {self._ph(i)}" for i, k in enumerate(spec.key))
        cur = self._execute(f"SELECT {', '.join(cols)} FROM {table} WHERE {where}", tuple(key))
        r = cur.fetchone()
        return self._row_from(spec, cols, r) if r else None

    def put(self, table: str, row: Dict) -> None:
        spec = self._spec(table)
        sql, cols = self._put_sql(spec)
        self._execute(sql, self._row_values(spec, cols, row))

    def _put_sql(self, spec: TableSpec) -> Tuple[str, List[str]]:
        cols = self._plain_cols(spec)
        phs = ", ".join(self._ph(i) for i in range(len(cols)))
        updates = ", ".join(f"{c} = excluded.{c}" for c in spec.columns) or f"{spec.key[0]} = excluded.{spec.key[0]}"
        return (f"INSERT INTO {table_name(spec)} ({', '.join(cols)}) VALUES ({phs}) "
                f"ON CONFLICT ({', '.join(spec.key)}) DO UPDATE SET {updates}"), cols

    def _row_values(self, spec: TableSpec, cols: List[str], row: Dict) -> Tuple:
        vals = []
        for c in cols:
            v = row.get(c)
            if c in spec.json_columns and v is not None:
                v = self._encode_json(v)
            vals.append(v)
        return tuple(vals)

    def put_many(self, table: str, rows: Sequence[Dict]) -> None:
        if not rows:
            return
        spec = self._spec(table)
        sql, cols = self._put_sql(spec)
        self._executemany(sql, [self._row_values(spec, cols, r) for r in rows])

    def _executemany(self, sql: str, seq):  # pragma: no cover
        for params in seq:
            self._execute(sql, params)

    def delete_many(self, table: str, keys: Sequence[Tuple]) -> None:
        if not keys:
            return
        spec = self._spec(table)
        where = " AND ".join(f"{k} = {self._ph(i)}" for i, k in enumerate(spec.key))
        self._executemany(f"DELETE FROM {table} WHERE {where}", [tuple(k) for k in keys])
        if spec.vector:
            for k in keys:
                self._delete_vector(table, k)

    def delete(self, table: str, key: Tuple) -> None:
        spec = self._spec(table)
        where = " AND ".join(f"{k} = {self._ph(i)}" for i, k in enumerate(spec.key))
        self._execute(f"DELETE FROM {table} WHERE {where}", tuple(key))
        if spec.vector:
            self._delete_vector(table, key)

    def _delete_vector(self, table: str, key: Tuple) -> None:  # SQLite overrides
        pass

    def select(self, table: str, where: Optional[Dict] = None, limit: Optional[int] = None) -> List[Dict]:
        # split oversized IN-lists into several queries
        if where and limit is None:
            for col, val in where.items():
                if isinstance(val, (list, tuple, set)) and len(val) > _IN_CHUNK:
                    vals = list(val)
                    out: List[Dict] = []
                    for i in range(0, len(vals), _IN_CHUNK):
                        w = dict(where)
                        w[col] = vals[i:i + _IN_CHUNK]
                        out.extend(self.select(table, w))
                    return out
        spec = self._spec(table)
        cols = self._plain_cols(spec)
        wsql, params = self._where_clause(where)
        order = ", ".join(spec.key)
        lim = f" LIMIT {int(limit)}" if limit else ""
        cur = self._execute(f"SELECT {', '.join(cols)} FROM {table}{wsql} ORDER BY {order}{lim}", tuple(params))
        return [self._row_from(spec, cols, r) for r in cur.fetchall()]

    def rows_with_prov(self, table: str, chunk_id: str) -> List[Dict]:
        spec = self._spec(table)
        assert spec.has_prov, table
        cols = self._plain_cols(spec)
        cur = self._execute(
            f"SELECT {', '.join(cols)} FROM {table} WHERE {self._prov_contains_sql()} ORDER BY {', '.join(spec.key)}",
            (self._prov_param(chunk_id),),
        )
        return [self._row_from(spec, cols, r) for r in cur.fetchall()]

    def _prov_param(self, chunk_id: str):
        return chunk_id

    def count(self, table: str) -> int:
        cur = self._execute(f"SELECT COUNT(*) FROM {table}")
        return int(cur.fetchone()[0])
