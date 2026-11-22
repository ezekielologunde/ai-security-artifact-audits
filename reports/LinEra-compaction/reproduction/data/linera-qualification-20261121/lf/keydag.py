"""Lineage key DAG.

source o   : k_o = PPRF(t_o)
derived d  : k_d = HKDF(k_p1 || ... || k_pm || PPRF(t_d), info = b"lf/lineage" || t_d)   (parents sorted by tag)
Forgetting a source punctures the PPRF at t_o; every descendant needs k_o, so all become undecryptable.
Every object has its own PPRF point, so any object (source or derived) can be forgotten individually.
"""
from __future__ import annotations
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from .pprf import PPRF, Punctured

class Forgotten(Exception):
    pass

class KeyDAG:
    def __init__(self, pprf: PPRF):
        self.pprf = pprf
        self.parents: dict[int, tuple[int, ...]] = {}
        self.children: dict[int, set[int]] = {}
        self._cache: dict[int, bytes] = {}

    def register(self, tag: int, parents) -> None:
        ps = tuple(sorted(set(parents)))
        self.parents[tag] = ps
        for p in ps:
            self.children.setdefault(p, set()).add(tag)

    def _derive(self, tag: int) -> bytes:
        """Key of `tag`, assuming every parent key is already in the cache."""
        try:
            own = self.pprf.eval(tag)
        except Punctured:
            raise Forgotten(tag)
        ps = self.parents.get(tag, ())
        if not ps:
            return own
        material = b"".join(self._cache[p] for p in ps) + own
        return HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                    info=b"lf/lineage" + tag.to_bytes(4, "big")).derive(material)

    def key(self, tag: int) -> bytes:
        """Iterative (explicit-stack) derivation: lineage chains can be far deeper than Python's recursion limit."""
        if tag in self._cache:
            return self._cache[tag]
        stack = [tag]
        while stack:
            t = stack[-1]
            if t in self._cache:
                stack.pop(); continue
            missing = [p for p in self.parents.get(t, ()) if p not in self._cache]
            if missing:
                stack.extend(missing); continue
            self._cache[t] = self._derive(t)
            stack.pop()
        return self._cache[tag]

    def descendants(self, tag: int) -> set[int]:
        out, stack = set(), [tag]
        while stack:
            for c in self.children.get(stack.pop(), ()):
                if c not in out:
                    out.add(c); stack.append(c)
        return out

    def forget(self, tag: int) -> set[int]:
        """Puncture at tag; drop cached keys of tag and all descendants. Returns the lineage closure."""
        closure = {tag} | self.descendants(tag)
        self.pprf.puncture(tag)
        for t in closure:
            self._cache.pop(t, None)
        return closure

    def drop_cache(self) -> None:
        self._cache.clear()
