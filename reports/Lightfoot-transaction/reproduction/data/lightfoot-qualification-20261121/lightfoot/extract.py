"""One LLM call per chunk, JSON schema output, no gleaning (design section 4 step 4).

- Model from env LIGHTFOOT_EXTRACT_LLM (default claude-haiku-5-5), effort low,
  max_tokens ~1200, structured output via `output_config.format` (json_schema); a response cut off at
  max_tokens (finish_reason "length") is retried once with a stricter instruction.
- If the API rejects the format parameter we fall back to prompt JSON + lenient parse.
- Disk cache keyed by (chunk text, entity types, model, schema version, prompt hash); each schema version has its
  own directory, so old cached extractions stay readable under their version and are never reused by a new one.
- Facts carry no model-written sentence (output tokens are the main indexing cost): the stored fact text is
  composed from subject, predicate and object, and the embedded text adds the verbatim evidence span.
- Deterministic mock (LIGHTFOOT_MOCK=1): capitalised-span entities, no facts.
- Every real call reports usage via the cost callback.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Callable, Dict, List, Optional, Sequence

from .chunking import Chunk
from .config import LightfootConfig
from .costs import CallRecord
from .llm import LLMCaller, LLMClient, LLMRefusal, make_client

# v1: facts had a model-written `sentence`; v2: lean schema (no sentence, shorter spans and descriptions).
SCHEMA_VERSION = "v2"
LEGACY_SCHEMA_VERSIONS = ("v1",)   # cache key formula of these versions is kept so their files stay readable


@dataclass
class ExtractedEntity:
    name: str
    type: str
    description: str = ""


@dataclass
class ExtractedFact:
    subject: str
    predicate: str
    object: str
    sentence: str = ""         # composed "subject predicate object" unless given (legacy v1 extractions)
    evidence_span: str = ""

    def __post_init__(self) -> None:
        if not self.sentence:
            self.sentence = compose_fact_sentence(self.subject, self.predicate, self.object)

    def embed_text(self) -> str:
        """Text embedded for fact retrieval: the triple plus the verbatim evidence, which carries the context
        (dates, qualifiers) the old model-written sentence used to add."""
        ev = self.evidence_span.strip()
        if not ev or ev.lower() in self.sentence.lower():
            return self.sentence
        return f"{self.sentence}: {ev}"


def compose_fact_sentence(subject: str, predicate: str, obj: str) -> str:
    return " ".join(x.strip() for x in (subject, predicate, obj) if x and x.strip())


@dataclass
class Extraction:
    entities: List[ExtractedEntity] = field(default_factory=list)
    facts: List[ExtractedFact] = field(default_factory=list)
    raw: Optional[str] = None
    parse_error: bool = False
    truncated: bool = False   # finish_reason was "length" on the last attempt (lenient parse of partial JSON)

    def to_dict(self) -> Dict:
        return {"entities": [asdict(e) for e in self.entities], "facts": [asdict(f) for f in self.facts]}

    @staticmethod
    def from_dict(d: Dict, max_entities: int = 12, max_facts: int = 12, description_words: int = 8,
                  evidence_words: int = 12) -> "Extraction":
        ents = []
        for e in (d.get("entities", []) or [])[:max_entities]:
            if not isinstance(e, dict):
                continue
            name = str(e.get("name", "")).strip()
            if not name:
                continue
            ents.append(ExtractedEntity(name=name, type=str(e.get("type", "OTHER")).strip().upper() or "OTHER",
                                        description=_cap_words(str(e.get("description", "")), description_words)))
        facts = []
        seen_f = set()
        for f in (d.get("facts", []) or [])[:max_facts]:
            if isinstance(f, (list, tuple)):   # v2 positional form [subject, predicate, object, evidence_span]
                f = dict(zip(FACT_FIELDS, (x if isinstance(x, str) else str(x) for x in f)))
            if not isinstance(f, dict):
                continue
            s, p, o = (str(f.get(k, "")).strip() for k in ("subject", "predicate", "object"))
            if not (s and p and o) or (s, p.lower(), o) in seen_f:
                continue
            seen_f.add((s, p.lower(), o))
            facts.append(ExtractedFact(subject=s, predicate=p, object=o,
                                       sentence=_cap_words(str(f.get("sentence", "") or ""), 30),
                                       evidence_span=_cap_words(str(f.get("evidence_span", "")), evidence_words)))
        return Extraction(entities=ents, facts=facts)


FACT_FIELDS = ("subject", "predicate", "object", "evidence_span")


def _cap_words(text: str, n: int) -> str:
    words = text.strip().split()
    return " ".join(words[:n]) if len(words) > n else text.strip()


def extraction_schema(entity_types: Sequence[str]) -> Dict:
    return {
        "type": "object",
        "properties": {
            "entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "surface form as written, no pronouns"},
                        "type": {"type": "string", "enum": list(entity_types)},
                        "description": {"type": "string", "description": "at most 8 words; do not repeat the name"},
                    },
                    "required": ["name", "type", "description"],
                    "additionalProperties": False,
                },
            },
            "facts": {
                "type": "array",
                "description": "each fact is [subject, predicate, object, evidence_span]",
                "items": {
                    # Positional 4-string array instead of an object: per-fact key names and braces were about half
                    # of the output tokens. Strict mode allows plain string arrays; length is enforced client-side.
                    "type": "array",
                    "description": "[subject: an entity name, predicate: 1-3 word verb phrase, object: an entity name "
                                   "or short literal, evidence_span: shortest verbatim quote, at most 12 words]",
                    "items": {"type": "string"},
                },
            },
        },
        "required": ["entities", "facts"],
        "additionalProperties": False,
    }


SYSTEM_PROMPT = (
    "Extract a knowledge graph from one passage. Output minified JSON on one line (no newlines, no indentation), "
    "e.g. {\"entities\":[{\"name\":\"Ada Lovelace\",\"type\":\"PERSON\",\"description\":\"English mathematician\"}],"
    "\"facts\":[[\"Ada Lovelace\",\"born in\",\"1815\",\"Ada Lovelace (born 1815)\"]]}\n"
    "entities (at most 12): the named people, organizations, places, works, products and events the facts use. "
    "No dates, numbers, generic nouns or alternate names. name as written; type from the allowed list; "
    "description: 2-5 words, not repeating the name.\n"
    "facts: aim for 10-12 (fewer only when the passage states fewer relations), most important first. One fact "
    "per relation; split compound statements and lists; cover every date, place, role, nationality, occupation, "
    "membership, authorship, creation, size and count. Each fact is "
    "[subject, predicate, object, evidence_span]: subject an entity name; predicate a 1-3 word verb phrase; object "
    "an entity name or short literal; evidence_span the shortest verbatim quote holding the key detail, usually "
    "3-8 words, never more than 12.\n"
    "No prose, no duplicate facts."
)

STRICT_SUFFIX = (
    "\n\nYour previous answer was cut off for being too long. Be much more selective: at most 8 entities and 8 facts, "
    "descriptions of at most 5 words, evidence spans of at most 8 words."
)


def build_user_prompt(text: str, entity_types: Sequence[str], want_json_in_prompt: bool) -> str:
    p = f"Allowed entity types: {', '.join(entity_types)}\n\nPassage:\n<passage>\n{text}\n</passage>"
    if want_json_in_prompt:
        p += ("\n\nRespond with a single JSON object of the form "
              '{"entities":[{"name":"","type":"","description":""}],'
              '"facts":[["subject","predicate","object","evidence_span"]]} '
              "and nothing else.")
    return p


# Part of the cache key: any change to the prompt or schema wording invalidates cached extractions.
PROMPT_HASH = hashlib.sha256(json.dumps([SYSTEM_PROMPT, STRICT_SUFFIX, extraction_schema(["_"])],
                                        sort_keys=True).encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Mock extractor
# ---------------------------------------------------------------------------
_CAP_SPAN_RE = re.compile(r"\b([A-Z][a-zA-Z0-9'’\-]*(?:\s+(?:of|de|the|and|&)?\s*[A-Z][a-zA-Z0-9'’\-]*)*)\b")
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_MOCK_STOP = {
    "The", "A", "An", "In", "On", "At", "It", "He", "She", "They", "We", "I", "You", "This", "That", "These",
    "Those", "There", "Here", "When", "Where", "Why", "How", "What", "Who", "Which", "But", "And", "Or", "If",
    "Then", "So", "As", "By", "For", "From", "To", "With", "Of", "Its", "His", "Her", "Their", "Our", "After",
    "Before", "While", "Although", "However", "Because", "Since", "Also", "Not", "No", "Yes", "Both", "Each",
    "Every", "Some", "Many", "Most", "Several", "During", "Meanwhile", "Later", "Today", "Yesterday", "Tomorrow",
    "Finally", "Between",
}
MOCK_TYPE = "ENTITY"


def mock_extract(text: str) -> Extraction:
    """Deterministic: capitalised spans become entities, description is the first sentence containing them."""
    seen: Dict[str, ExtractedEntity] = {}
    sentences = _SENT_SPLIT_RE.split(text)
    for sent in sentences:
        for m in _CAP_SPAN_RE.finditer(sent):
            name = m.group(1).strip()
            words = name.split()
            # drop leading stopwords (sentence starters)
            while words and words[0] in _MOCK_STOP:
                words = words[1:]
            if not words:
                continue
            name = " ".join(words)
            if len(name) < 2 or name in seen:
                continue
            seen[name] = ExtractedEntity(name=name, type=MOCK_TYPE, description=sent.strip()[:300])
    return Extraction(entities=list(seen.values()), facts=[])


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------
class Extractor:
    def __init__(self, config: LightfootConfig, cost_callback: Optional[Callable[[CallRecord], None]] = None,
                 client=None, llm: Optional[LLMClient] = None, schema_version: str = SCHEMA_VERSION) -> None:
        """`client`: a raw provider SDK client (wrapped by the configured provider); `llm`: an LLMClient.
        `schema_version` selects the cache namespace (pass an old version only to read its cached extractions)."""
        self.config = config
        self.cost_callback = cost_callback
        self.model = config.extract_model
        self.llm = llm or make_client(raw_client=client)
        self.caller = LLMCaller(self.llm, self.model, cost_callback, config.extract_max_retries, config.extract_effort)
        self.entity_types = list(config.entity_types)
        self.schema_version = schema_version
        self.cache_dir = os.path.join(config.cache_dir, "extract", _safe(self.model), schema_version)
        os.makedirs(self.cache_dir, exist_ok=True)
        self._schema = extraction_schema(self.entity_types)
        self.trace: Optional[List[Dict]] = None   # set to a list to record per-call diagnostics
        self._types_hash = hashlib.sha256(",".join(self.entity_types).encode()).hexdigest()[:8]

    # cache ---------------------------------------------------------------
    def _cache_key(self, chunk: Chunk) -> str:
        base = chunk.text + "\x00" + self._types_hash
        if self.schema_version not in LEGACY_SCHEMA_VERSIONS:
            base += "\x00" + self.schema_version + "\x00" + PROMPT_HASH
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    def _cache_path(self, chunk: Chunk) -> str:
        return os.path.join(self.cache_dir, self._cache_key(chunk) + ".json")

    def _cache_get(self, chunk: Chunk) -> Optional[Extraction]:
        p = self._cache_path(chunk)
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return Extraction.from_dict(json.load(f))
            except Exception:
                return None
        return None

    def _cache_put(self, chunk: Chunk, ex: Extraction) -> None:
        tmp = self._cache_path(chunk) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(ex.to_dict(), f, ensure_ascii=False)
        os.replace(tmp, self._cache_path(chunk))

    # main ----------------------------------------------------------------
    def extract(self, chunk: Chunk) -> Extraction:
        if self.config.mock:
            ex = mock_extract(chunk.text)
            if self.cost_callback:
                self.cost_callback(CallRecord(kind="extract", model="mock", mock=True))
            return ex
        cached = self._cache_get(chunk)
        if cached is not None:
            if self.cost_callback:
                self.cost_callback(CallRecord(kind="extract", model=self.model, cached=True))
            return cached
        ex = self._call_with_retry(chunk.text)
        if not ex.parse_error:
            self._cache_put(chunk, ex)
        return ex

    def extract_many(self, chunks: Sequence[Chunk]) -> List[Extraction]:
        """Mock: in-process. Real: cache hits first, then concurrent API calls with backoff."""
        if self.config.mock or len(chunks) <= 1 or self.config.extract_concurrency <= 1:
            return [self.extract(c) for c in chunks]
        out: List[Optional[Extraction]] = [None] * len(chunks)
        todo: List[int] = []
        for i, c in enumerate(chunks):
            cached = self._cache_get(c)
            if cached is not None:
                out[i] = cached
                if self.cost_callback:
                    self.cost_callback(CallRecord(kind="extract", model=self.model, cached=True))
            else:
                todo.append(i)
        if todo:
            import contextvars
            from concurrent.futures import ThreadPoolExecutor
            # Each task runs in a copy of the caller's context so contextvars (e.g. the harness's cost
            # attribution phase) are visible to cost callbacks fired from worker threads.
            with ThreadPoolExecutor(max_workers=self.config.extract_concurrency) as pool:
                futures = [pool.submit(contextvars.copy_context().run, self._call_with_retry, chunks[i].text) for i in todo]
                results = [f.result() for f in futures]
            for i, ex in zip(todo, results):
                out[i] = ex
                if not ex.parse_error:
                    self._cache_put(chunks[i], ex)
        return out  # type: ignore[return-value]

    def _call_with_retry(self, text: str) -> Extraction:
        """Retry rate limits, overloads and connection errors with exponential backoff and jitter."""
        import random
        import time
        import anthropic
        attempt = 0
        while True:
            try:
                return self._call(text)
            except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError) as e:
                attempt += 1
                if attempt > self.config.extract_max_retries:
                    raise
                delay = min(60.0, (2 ** attempt) + random.uniform(0, 1))
                retry_after = getattr(getattr(e, "response", None), "headers", {}) or {}
                try:
                    delay = max(delay, float(retry_after.get("retry-after", 0)))
                except (TypeError, ValueError):
                    pass
                time.sleep(delay)

    def _call(self, text: str) -> Extraction:
        cfg = self.config
        user = build_user_prompt(text, self.entity_types, False)
        ex = Extraction(parse_error=True)
        for attempt, prompt in enumerate((user, user + STRICT_SUFFIX)):
            try:
                data, usage, raw = self.caller.json_full("extract", SYSTEM_PROMPT, prompt, cfg.extract_max_tokens, self._schema)
            except LLMRefusal:
                return Extraction()
            if isinstance(data, dict):
                ex = Extraction.from_dict(data, cfg.extract_max_entities, cfg.extract_max_facts,
                                          cfg.extract_description_words, cfg.extract_evidence_words)
            else:
                ex = Extraction(parse_error=True)
            ex.truncated = usage.truncated
            if self.trace is not None:
                self.trace.append({"attempt": attempt, "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens,
                                   "latency_s": usage.latency_s, "finish_reason": usage.finish_reason,
                                   "entities": len(ex.entities), "facts": len(ex.facts), "raw": raw})
            if not usage.truncated:
                break
            # truncated: retry once with a stricter instruction; a second truncation keeps the lenient parse
        return ex

    def _call_with_retry(self, text: str) -> Extraction:
        """Retries (rate limit, overload, connection) live in LLMCaller; kept for callers of the old name."""
        return self._call(text)


def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", s)
