"""Answer generation and question decomposition: one SDK call each, mockable."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .config import LightfootConfig
from .costs import CallRecord
from .llm import LLMCaller, LLMClient, LLMRefusal, make_client

# Measured on 30 MuSiQue questions with reasoning disabled (fairness constraint: baselines answer with
# reasoning none): this prompt EM 0.200 / F1 0.290 / 3% empty vs 0.167 / 0.254 / 20% empty for a prompt with an
# `unanswerable` field, which the model used to dodge multi-hop questions.
ANSWER_SYSTEM = (
    "You answer questions from the provided context. The context contains passages, each introduced by its chunk id "
    "in square brackets, plus extracted facts with evidence quotes. Combine the passages (questions usually need two "
    "or three hops) and output JSON with two keys: `answer`: your single best guess for the answer, as the shortest "
    "span that answers the question (a name, date, number or short phrase copied from the context; no sentence, no "
    "explanation, no citations, never 'unknown' or 'not stated'); `supporting_chunk_ids`: the chunk ids of the "
    "passages you used. Always output a best guess even when the evidence is incomplete.\n"
    "Examples:\n"
    "Question: Who is the spouse of the director of the film that won Best Picture in 1998? -> "
    '{"answer":"Kathleen Kennedy","supporting_chunk_ids":["<id1>","<id2>"]}\n'
    "Question: In what year was the company that acquired the maker of the Walkman founded? -> "
    '{"answer":"1946","supporting_chunk_ids":["<id1>"]}'
)

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string", "description": "single best guess, shortest answer span"},
        "supporting_chunk_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["answer", "supporting_chunk_ids"],
    "additionalProperties": False,
}

_ANSWER_LINE_RE = re.compile(r"Answer\s*:\s*(.*)", re.I | re.S)
_CITE_RE = re.compile(r"\[([0-9a-f]{8,64})\]")
_TRAIL_PUNCT = ".,;:!?\"'`)]} \t\n"


_PLACEHOLDER_RE = re.compile(r"^(not (stated|given|mentioned|provided|specified|found|available|in (the )?context)|"
                             r"unknown|unanswerable|n/?a|none|no answer|cannot (be )?determine[d]?|insufficient (context|information))$", re.I)


def clean_span(text: str) -> str:
    """Strip citations, quotes, whitespace and trailing punctuation from an answer span; placeholders such as
    'not stated' or 'unknown' become the empty string."""
    t = _CITE_RE.sub("", text or "").strip()
    t = t.splitlines()[0].strip() if t else t
    t = t.strip(_TRAIL_PUNCT).strip()
    if len(t) >= 2 and t[0] in "\"'`" and t[-1] in "\"'`":
        t = t[1:-1].strip()
    return "" if _PLACEHOLDER_RE.match(t) else t


def parse_answer_text(text: str, known_chunk_ids=None) -> "AnswerResult":
    """Fallback parse when JSON fails: the text after the last 'Answer:' line, else the whole text; citations
    are every bracketed chunk id in the text."""
    text = text or ""
    cites = [c for c in dict.fromkeys(_CITE_RE.findall(text)) if not known_chunk_ids or c in known_chunk_ids]
    matches = list(_ANSWER_LINE_RE.finditer(text))
    span = clean_span(matches[-1].group(1) if matches else text)
    return AnswerResult(answer=span, cited_chunk_ids=cites, unanswerable=not span, raw=text)


@dataclass
class AnswerResult:
    answer: str                      # short span, trailing punctuation stripped, no citations
    cited_chunk_ids: List[str] = field(default_factory=list)
    unanswerable: bool = False       # the span is empty (the model found nothing usable in the context)
    raw: str = ""


DECOMPOSE_SYSTEM = (
    "Break a complex question into the minimal ordered list of simpler sub-questions whose answers together "
    "answer it. Each sub-question must be self-contained. Return JSON {\"subquestions\": [\"...\", ...]}."
)

_DECOMPOSE_SCHEMA = {
    "type": "object",
    "properties": {"subquestions": {"type": "array", "items": {"type": "string"}}},
    "required": ["subquestions"],
    "additionalProperties": False,
}


class Answerer:
    def __init__(self, config: LightfootConfig, cost_callback: Optional[Callable[[CallRecord], None]] = None,
                 client=None, llm: Optional[LLMClient] = None) -> None:
        self.config = config
        self.cost_callback = cost_callback
        self.model = config.answer_model
        self.llm = llm or make_client(raw_client=client)
        self.caller = LLMCaller(self.llm, self.model, cost_callback, config.extract_max_retries)
        self._decompose_caller = LLMCaller(self.llm, self.model, cost_callback, config.extract_max_retries, "low")

    def answer(self, question: str, context: str, chunk_ids: Optional[List[str]] = None) -> AnswerResult:
        """Short-span answer via the JSON path (schema -> json_object -> prompt JSON), with a text fallback that
        takes whatever follows the last 'Answer:' line. max_tokens is at least 300 so the span never truncates."""
        if self.config.mock:
            if self.cost_callback:
                self.cost_callback(CallRecord(kind="answer", model="mock", mock=True))
            return AnswerResult(answer="(mock)", cited_chunk_ids=list(chunk_ids[:1]) if chunk_ids else [],
                                raw=f"MOCK ANSWER for: {question}\nAnswer: (mock)")
        prompt = f"<context>\n{context}\n</context>\n\nQuestion: {question}"
        max_tokens = max(300, int(self.config.answer_max_tokens))
        try:
            data, usage, raw = self.caller.json_full("answer", ANSWER_SYSTEM, prompt, max_tokens, ANSWER_SCHEMA)
        except LLMRefusal as e:
            return AnswerResult(answer="", unanswerable=True, raw=f"The model declined to answer ({e}).")
        known = set(chunk_ids or [])
        if isinstance(data, dict) and "answer" in data:
            cites = [str(c) for c in (data.get("supporting_chunk_ids") or []) if isinstance(c, (str, int))]
            cites = [c for c in dict.fromkeys(cites) if not known or c in known]
            if not cites:
                cites = [c for c in dict.fromkeys(_CITE_RE.findall(raw)) if not known or c in known]
            span = clean_span(str(data.get("answer", "")))
            return AnswerResult(answer=span, cited_chunk_ids=cites,
                                unanswerable=bool(data.get("unanswerable", False)) or not span, raw=raw)
        return parse_answer_text(raw, known)

    def decompose(self, question: str) -> List[str]:
        if self.config.mock:
            if self.cost_callback:
                self.cost_callback(CallRecord(kind="decompose", model="mock", mock=True))
            parts = [p.strip(" ?") for p in re.split(r"\band\b|;|,", question) if len(p.strip()) > 8]
            return [p + "?" for p in parts[: self.config.max_subquestions]] or [question]
        try:
            data = self._decompose_caller.json("decompose", DECOMPOSE_SYSTEM, f"Question: {question}", 600, _DECOMPOSE_SCHEMA) or {}
        except LLMRefusal:
            return [question]
        subs = [str(s).strip() for s in data.get("subquestions", []) if str(s).strip()] if isinstance(data, dict) else []
        return subs[: self.config.max_subquestions] or [question]
