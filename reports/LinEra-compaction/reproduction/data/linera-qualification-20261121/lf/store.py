"""Encrypted memory store (SQLite). Ciphertexts: ChaCha20-Poly1305, AD = tag || sorted parent tags.
The PPRF state lives in a separate file written atomically (tmp + fsync + rename).
"""
from __future__ import annotations
import os, json, sqlite3, secrets
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from .pprf import PPRF
from .keydag import KeyDAG, Forgotten

def _ad(tag, parents):
    return tag.to_bytes(4, "big") + b"".join(p.to_bytes(4, "big") for p in parents)

class LineageStore:
    def __init__(self, path: str, state_path: str):
        self.path, self.state_path = path, state_path
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS obj (tag INTEGER PRIMARY KEY, kind TEXT, parents TEXT, nonce BLOB, ct BLOB)")
        pprf = PPRF.loads(open(state_path).read()) if os.path.exists(state_path) else PPRF()
        self.dag = KeyDAG(pprf)
        for tag, parents in self.db.execute("SELECT tag, parents FROM obj"):
            self.dag.register(tag, json.loads(parents))
        self._used = {t for (t,) in self.db.execute("SELECT tag FROM obj")}
        self._save_state()

    def _new_tag(self) -> int:
        while True:
            t = secrets.randbits(32)
            if t not in self._used:
                self._used.add(t); return t

    def _save_state(self):
        tmp = self.state_path + ".tmp"
        with open(tmp, "w") as f:
            f.write(self.dag.pprf.dumps()); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, self.state_path)

    def put(self, content: str, kind: str = "source", parents=(), commit: bool = True) -> int:
        tag = self._new_tag()
        ps = tuple(sorted(set(parents)))
        self.dag.register(tag, ps)
        k = self.dag.key(tag)
        nonce = secrets.token_bytes(12)
        ct = ChaCha20Poly1305(k).encrypt(nonce, content.encode(), _ad(tag, ps))
        self.db.execute("INSERT INTO obj VALUES (?,?,?,?,?)", (tag, kind, json.dumps(ps), nonce, ct))
        if commit: self.db.commit()
        return tag

    def get(self, tag: int) -> str:
        row = self.db.execute("SELECT parents, nonce, ct FROM obj WHERE tag=?", (tag,)).fetchone()
        if row is None:
            raise KeyError(tag)
        ps = tuple(json.loads(row[0]))
        k = self.dag.key(tag)  # raises Forgotten
        return ChaCha20Poly1305(k).decrypt(row[1], row[2], _ad(tag, ps)).decode()

    def readable(self, tag: int) -> bool:
        try:
            self.get(tag); return True
        except (Forgotten, KeyError):
            return False

    def forget(self, tag: int, delete_rows: bool = True) -> set[int]:
        closure = self.dag.forget(tag)
        self._save_state()  # the puncture is durable before rows are touched
        if delete_rows:     # best effort only; security does not rely on it
            self.db.executemany("DELETE FROM obj WHERE tag=?", [(t,) for t in closure])
            self.db.commit()
        return closure

    def tags(self):
        return [t for (t,) in self.db.execute("SELECT tag FROM obj")]

    def rotate(self) -> int:
        """Compaction: re-encrypt every surviving object under a fresh PPRF (resets state size)."""
        rows = []
        for tag in self.tags():
            try:
                rows.append((tag, self.get(tag)))
            except Forgotten:
                continue
        old_parents = dict(self.dag.parents)
        new = KeyDAG(PPRF())
        for tag, _ in rows:
            new.register(tag, old_parents.get(tag, ()))
        self.dag = new
        for tag, content in rows:
            ps = self.dag.parents[tag]
            nonce = secrets.token_bytes(12)
            ct = ChaCha20Poly1305(self.dag.key(tag)).encrypt(nonce, content.encode(), _ad(tag, ps))
            self.db.execute("UPDATE obj SET nonce=?, ct=? WHERE tag=?", (nonce, ct, tag))
        self.db.commit()
        self._save_state()
        return len(rows)

    def close(self):
        self.db.close()
