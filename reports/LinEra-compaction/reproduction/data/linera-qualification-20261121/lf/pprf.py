"""GGM puncturable PRF on a 32-bit domain (Goldreich-Goldwasser-Micali; Boneh-Waters / Kiayias et al. puncturing).

PRG G(seed) = (SHA-256(0x00||seed), SHA-256(0x01||seed)), seeds are 32 bytes.
State = set of frontier nodes {(depth, prefix) -> seed}; together they cover every non-punctured point.
Puncture(x) replaces the node covering x by the siblings along the path to x (at most DEPTH nodes).
"""
import hashlib, json, os, base64

DEPTH = 32

def _g(seed: bytes, bit: int) -> bytes:
    return hashlib.sha256(bytes([bit]) + seed).digest()

class Punctured(KeyError):
    pass

class PPRF:
    def __init__(self, seed: bytes | None = None, depth: int = DEPTH):
        self.depth = depth
        self.nodes: dict[tuple[int, int], bytes] = {(0, 0): seed or os.urandom(32)}
        self.punctured = 0

    def _cover(self, x: int):
        for d in range(self.depth + 1):
            key = (d, x >> (self.depth - d))
            if key in self.nodes:
                return key
        return None

    def eval(self, x: int) -> bytes:
        if not 0 <= x < (1 << self.depth):
            raise ValueError("tag out of domain")
        key = self._cover(x)
        if key is None:
            raise Punctured(x)
        d, _ = key
        s = self.nodes[key]
        for i in range(d, self.depth):
            s = _g(s, (x >> (self.depth - 1 - i)) & 1)
        return s

    def puncture(self, x: int) -> None:
        key = self._cover(x)
        if key is None:
            return  # already punctured
        d, _ = key
        s = self.nodes.pop(key)
        for i in range(d, self.depth):
            b = (x >> (self.depth - 1 - i)) & 1
            prefix = x >> (self.depth - 1 - i)          # prefix at depth i+1 on x's path
            self.nodes[(i + 1, prefix ^ 1)] = _g(s, b ^ 1)  # keep the sibling subtree
            s = _g(s, b)
        # s (the leaf value for x) is dropped here; callers must also drop cached copies
        del s
        self.punctured += 1

    def size_bytes(self) -> int:
        return len(self.nodes) * (32 + 8)

    # serialization (the state file is assumed sealed by the OS keystore / TPM)
    def dumps(self) -> str:
        return json.dumps({"depth": self.depth, "punctured": self.punctured,
                           "nodes": [[d, p, base64.b64encode(s).decode()] for (d, p), s in self.nodes.items()]})

    @classmethod
    def loads(cls, txt: str) -> "PPRF":
        o = json.loads(txt)
        f = cls(seed=b"\0" * 32, depth=o["depth"])
        f.nodes = {(d, p): base64.b64decode(s) for d, p, s in o["nodes"]}
        f.punctured = o["punctured"]
        return f
