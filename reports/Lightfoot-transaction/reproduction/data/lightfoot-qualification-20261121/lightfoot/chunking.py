"""Structure-aware chunker.

- Cheap tokenizer estimate (no model): regex word/punct count scaled for BPE.
- Target 512 tokens, hard max 800, 10 percent overlap carried from the tail of the
  previous chunk (whole sentences).
- Headings, list items, table rows and blank-line paragraphs are block boundaries.
- Stable chunk ids: sha256 of (doc_id, chunk text). Re-uploading an unchanged
  paragraph yields the same id, so the hash-and-diff step can skip it.
- Short passages (<= max tokens) pass through as a single chunk.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import List

_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)
_SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S")
_LIST_RE = re.compile(r"^\s*([-*+]|\d+[.)])\s+")
_TABLE_RE = re.compile(r"^\s*\|.*\|\s*$")


def estimate_tokens(text: str) -> int:
    """Cheap BPE-ish estimate: words count ~1.3 tokens, punctuation ~1 token."""
    n_words = 0
    n_punct = 0
    for m in _TOKEN_RE.finditer(text):
        tok = m.group(0)
        if tok[0].isalnum() or tok[0] == "_":
            n_words += 1 + len(tok) // 8  # long tokens split into more pieces
        else:
            n_punct += 1
    return max(1, math.ceil(n_words * 1.3 + n_punct)) if text.strip() else 0


def chunk_id_for(doc_id: str, text: str) -> str:
    h = hashlib.sha256()
    h.update(doc_id.encode("utf-8"))
    h.update(b"\x00")
    h.update(text.encode("utf-8"))
    return h.hexdigest()[:32]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    ordinal: int
    text: str
    tokens: int


def _split_blocks(text: str) -> List[str]:
    """Split into structural blocks: headings, paragraphs, list items, table rows."""
    blocks: List[str] = []
    para: List[str] = []

    def flush():
        if para:
            blocks.append("\n".join(para).strip())
            para.clear()

    for line in text.splitlines():
        if not line.strip():
            flush()
            continue
        if _HEADING_RE.match(line):
            flush()
            blocks.append(line.strip())
            continue
        if _LIST_RE.match(line) or _TABLE_RE.match(line):
            # list items and table rows are their own blocks but stay adjacent
            flush()
            blocks.append(line.strip())
            continue
        para.append(line)
    flush()
    return [b for b in blocks if b]


def _split_sentences(text: str) -> List[str]:
    parts = _SENT_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


def _split_oversized(block: str, max_tokens: int) -> List[str]:
    """Split a single block that exceeds max_tokens by sentences, then by words."""
    out: List[str] = []
    cur: List[str] = []
    cur_tokens = 0
    for sent in _split_sentences(block):
        st = estimate_tokens(sent)
        if st > max_tokens:
            if cur:
                out.append(" ".join(cur))
                cur, cur_tokens = [], 0
            words = sent.split()
            step = max(1, int(max_tokens / 1.5))
            for i in range(0, len(words), step):
                out.append(" ".join(words[i:i + step]))
            continue
        if cur and cur_tokens + st > max_tokens:
            out.append(" ".join(cur))
            cur, cur_tokens = [], 0
        cur.append(sent)
        cur_tokens += st
    if cur:
        out.append(" ".join(cur))
    return out


def _tail_overlap(text: str, overlap_tokens: int) -> str:
    """Return the trailing whole sentences of `text` totalling about overlap_tokens."""
    if overlap_tokens <= 0:
        return ""
    sents = _split_sentences(text)
    acc: List[str] = []
    t = 0
    for s in reversed(sents):
        st = estimate_tokens(s)
        if acc and t + st > overlap_tokens:
            break
        acc.append(s)
        t += st
        if t >= overlap_tokens:
            break
    return " ".join(reversed(acc))


def chunk_document(doc_id: str, text: str, target_tokens: int = 512, max_tokens: int = 800,
                   overlap: float = 0.10) -> List[Chunk]:
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []
    total = estimate_tokens(text)
    if total <= max_tokens:
        return [Chunk(chunk_id_for(doc_id, text), doc_id, 0, text, total)]

    blocks: List[str] = []
    for b in _split_blocks(text):
        if estimate_tokens(b) > max_tokens:
            blocks.extend(_split_oversized(b, max_tokens))
        else:
            blocks.append(b)

    overlap_tokens = int(target_tokens * overlap)
    chunks_text: List[str] = []
    cur: List[str] = []
    cur_tokens = 0
    carry = ""  # overlap text prepended to the next chunk

    def emit():
        nonlocal cur, cur_tokens, carry
        body = "\n\n".join(cur)
        full = (carry + "\n\n" + body) if carry else body
        chunks_text.append(full)
        carry = _tail_overlap(body, overlap_tokens)
        cur, cur_tokens = [], 0

    for b in blocks:
        bt = estimate_tokens(b)
        carry_t = estimate_tokens(carry) if carry else 0
        if cur and (cur_tokens + bt + carry_t > max_tokens or cur_tokens >= target_tokens):
            emit()
        cur.append(b)
        cur_tokens += bt
    if cur:
        emit()

    out: List[Chunk] = []
    for i, t in enumerate(chunks_text):
        out.append(Chunk(chunk_id_for(doc_id, t), doc_id, i, t, estimate_tokens(t)))
    return out
