"""LLM provider abstraction.

Two `LLMClient` implementations behind one interface:
  AnthropicClient   - the official `anthropic` SDK (`client.messages.create`), structured outputs via
                      `output_config.format`, effort via `output_config.effort`.
  OpenAICompatClient - the `openai` SDK against any OpenAI-compatible endpoint (default OpenRouter),
                      structured outputs via `response_format` json_schema (strict) with a per-model
                      fallback to `json_object`, then to prompt JSON.

Selected by env LIGHTFOOT_LLM_PROVIDER = "anthropic" (default) | "openai".
`LLMCaller` adds what every call site needs: retry with exponential backoff on rate limits and
5xx, usage reporting through the cost callback, refusal handling and lenient JSON parsing.
"""
from __future__ import annotations

import json
import logging
import os
import random
import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

from .costs import CallRecord

log = logging.getLogger("lightfoot.llm")

JSON_HINT = "\n\nRespond with a single JSON object and nothing else."
_sleep = time.sleep   # backoff sleep; tests patch this instead of time.sleep


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    finish_reason: Optional[str] = None   # normalised: "stop" | "length" | "refusal" | other
    latency_s: float = 0.0
    cost_usd: Optional[float] = None      # authoritative cost reported by the endpoint, when available

    @property
    def truncated(self) -> bool:
        return self.finish_reason == "length"


class LLMRefusal(RuntimeError):
    pass


class SchemaRejected(RuntimeError):
    """The endpoint rejected the structured-output request; the caller retries with prompt JSON."""


def provider_name() -> str:
    return os.environ.get("LIGHTFOOT_LLM_PROVIDER", "anthropic").strip().lower() or "anthropic"


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------
class LLMClient:
    """`complete(system, user, max_tokens, json_schema=None) -> (text, usage)`."""
    provider: str = "base"

    def complete(self, system: Optional[str], user: str, max_tokens: int, json_schema: Optional[Dict] = None,
                 model: Optional[str] = None, effort: Optional[str] = None, kind: Optional[str] = None) -> Tuple[str, Usage]:
        raise NotImplementedError

    def is_retryable(self, exc: Exception) -> bool:
        return False

    def retry_after(self, exc: Exception) -> Optional[float]:
        headers = getattr(getattr(exc, "response", None), "headers", None)
        if headers:
            try:
                return float(headers.get("retry-after"))
            except (TypeError, ValueError):
                return None
        return None


class AnthropicClient(LLMClient):
    provider = "anthropic"

    def __init__(self, client=None) -> None:
        self._client = client

    @property
    def client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic()
        return self._client

    def complete(self, system, user, max_tokens, json_schema=None, model=None, effort=None, kind=None):
        import anthropic
        kwargs: Dict[str, Any] = dict(model=model, max_tokens=max_tokens, messages=[{"role": "user", "content": user}])
        if system:
            kwargs["system"] = system
        oc: Dict[str, Any] = {}
        if effort:
            oc["effort"] = effort
        if json_schema is not None:
            oc["format"] = {"type": "json_schema", "schema": json_schema}
        if oc:
            kwargs["output_config"] = oc
        try:
            resp = self.client.messages.create(**kwargs)
        except anthropic.BadRequestError as e:
            if json_schema is not None and is_format_rejection(e):
                raise SchemaRejected(str(e)) from e
            raise
        u = getattr(resp, "usage", None)
        stop = getattr(resp, "stop_reason", None)
        usage = Usage(int(getattr(u, "input_tokens", 0) or 0), int(getattr(u, "output_tokens", 0) or 0),
                      int(getattr(u, "cache_read_input_tokens", 0) or 0), int(getattr(u, "cache_creation_input_tokens", 0) or 0),
                      finish_reason={"end_turn": "stop", "max_tokens": "length"}.get(stop, stop))
        if stop == "refusal":
            details = getattr(resp, "stop_details", None)
            raise LLMRefusal(f"model refused ({getattr(details, 'category', None)})")
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        return text, usage

    def is_retryable(self, exc: Exception) -> bool:
        import anthropic
        return isinstance(exc, (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError))


class OpenAICompatClient(LLMClient):
    """OpenAI-compatible chat completions (OpenRouter by default).

    Structured output modes are remembered per model: "json_schema" -> "json_object" -> "prompt".
    """
    provider = "openai"

    def __init__(self, client=None, base_url: Optional[str] = None, api_key: Optional[str] = None,
                 reasoning_effort: Optional[str] = None, provider_routing: Optional[Dict[str, Any]] = None) -> None:
        self._client = client
        self.base_url = base_url or os.environ.get("LIGHTFOOT_OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
        self.api_key = api_key or os.environ.get("LIGHTFOOT_OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
        self._mode: Dict[str, str] = {}      # model -> best structured mode known to work
        self._lock = threading.Lock()
        # Reasoning models count hidden reasoning tokens against max_tokens (measured on OpenRouter: 600-1150 of a
        # 1200 budget for a 100-word passage). Default "none" disables it; env LIGHTFOOT_OPENAI_REASONING overrides
        # ("none" | "minimal" | "low" | "medium" | "high" | "off" to send nothing).
        self.reasoning_effort = reasoning_effort if reasoning_effort is not None else os.environ.get("LIGHTFOOT_OPENAI_REASONING", "none")
        # Per call kind overrides: LIGHTFOOT_OPENAI_REASONING_<KIND> (e.g. _ANSWER). All kinds default to the
        # global setting ("none"): the benchmark baselines answer with reasoning none, so the answer call must too.
        self.reasoning_by_kind: Dict[str, str] = {}
        for k in ("extract", "judge", "decompose", "topic", "answer"):
            v = os.environ.get(f"LIGHTFOOT_OPENAI_REASONING_{k.upper()}")
            if v:
                self.reasoning_by_kind[k] = v
        self._reasoning_ok: Dict[str, bool] = {}   # model -> endpoint accepted the reasoning parameter
        # OpenRouter provider routing (env LIGHTFOOT_OPENAI_PROVIDER, a JSON object merged into extra_body.provider).
        # Default {"sort": "throughput"} on OpenRouter (measured: 136 s -> 9 s wall for 16 concurrent llama-3.3-70b calls),
        # nothing elsewhere. Rejections are remembered per model like the reasoning parameter.
        self.provider_routing: Optional[Dict[str, Any]] = provider_routing if provider_routing is not None else _env_provider_routing()
        self._provider_ok: Dict[str, bool] = {}

    @property
    def client(self):
        if self._client is None:
            import openai
            if not self.api_key:
                raise RuntimeError("set LIGHTFOOT_OPENAI_API_KEY or OPENROUTER_API_KEY for the openai provider")
            self._client = openai.OpenAI(base_url=self.base_url, api_key=self.api_key)
        return self._client

    def mode_for(self, model: str) -> str:
        return self._mode.get(model, "json_schema")

    @property
    def is_openrouter(self) -> bool:
        return "openrouter" in (self.base_url or "")

    def _reasoning_kwargs(self, model: str, kind: Optional[str] = None) -> Dict[str, Any]:
        eff = (self.reasoning_by_kind.get(kind or "", self.reasoning_effort) or "").strip().lower()
        if eff in ("", "off") or self._reasoning_ok.get(model) is False:
            return {}
        if self.is_openrouter:
            return {"extra_body": {"reasoning": {"effort": eff}}}
        return {"reasoning_effort": eff}

    def _provider_body(self, model: str) -> Dict[str, Any]:
        if not self.is_openrouter or not self.provider_routing or self._provider_ok.get(model) is False:
            return {}
        return {"provider": dict(self.provider_routing)}

    def _request_kwargs(self, model: str, kind: Optional[str] = None) -> Dict[str, Any]:
        """Reasoning + provider routing + usage accounting, merged into one extra_body where needed."""
        kw = self._reasoning_kwargs(model, kind)
        extra: Dict[str, Any] = dict(kw.pop("extra_body", {}))
        extra.update(self._provider_body(model))
        if self.is_openrouter:
            extra["usage"] = {"include": True}   # OpenRouter then reports usage.cost (USD) on the response
        if extra:
            kw["extra_body"] = extra
        return kw

    def complete(self, system, user, max_tokens, json_schema=None, model=None, effort=None, kind=None):
        import openai
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        mode = self.mode_for(model) if json_schema is not None else "text"
        while True:
            kwargs: Dict[str, Any] = dict(model=model, messages=messages, max_tokens=max_tokens)
            kwargs.update(self._request_kwargs(model, kind))
            if mode == "json_schema":
                kwargs["response_format"] = {"type": "json_schema", "json_schema": {
                    "name": "lightfoot_output", "schema": json_schema, "strict": True}}
            elif mode == "json_object":
                kwargs["response_format"] = {"type": "json_object"}
            try:
                resp = self.client.chat.completions.create(**kwargs)
                break
            except openai.BadRequestError as e:
                emsg = str(e).lower()
                if self._provider_body(model) and "provider" in emsg:
                    log.warning("%s rejected the provider routing body, sending without it", model)
                    with self._lock:
                        self._provider_ok[model] = False
                    continue
                if self._reasoning_kwargs(model, kind) and "reason" in emsg:
                    log.warning("%s rejected the reasoning parameter, sending without it", model)
                    with self._lock:
                        self._reasoning_ok[model] = False
                    continue
                if mode == "json_schema":
                    log.warning("%s rejected json_schema response_format, falling back to json_object", model)
                    with self._lock:
                        self._mode[model] = mode = "json_object"
                    continue
                if mode == "json_object":
                    log.warning("%s rejected json_object response_format, falling back to prompt JSON", model)
                    with self._lock:
                        self._mode[model] = "prompt"
                    raise SchemaRejected(str(e)) from e
                raise
        u = getattr(resp, "usage", None)
        details = getattr(u, "prompt_tokens_details", None)
        choice = resp.choices[0] if getattr(resp, "choices", None) else None
        usage = Usage(int(getattr(u, "prompt_tokens", 0) or 0), int(getattr(u, "completion_tokens", 0) or 0),
                      int(getattr(details, "cached_tokens", 0) or 0), 0,
                      finish_reason=getattr(choice, "finish_reason", None) if choice is not None else None,
                      cost_usd=_usage_cost(u))
        msg = getattr(choice, "message", None)
        if msg is not None and getattr(msg, "refusal", None):
            raise LLMRefusal(str(msg.refusal))
        if choice is not None and getattr(choice, "finish_reason", None) == "content_filter":
            raise LLMRefusal("content_filter")
        text = (getattr(msg, "content", None) or "") if msg is not None else ""
        if isinstance(text, list):  # some endpoints return content parts
            text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
        if mode == "prompt":
            # the caller asked for a schema but this model only does prompt JSON: tell the caller
            # (it adds the JSON hint) only when nothing parseable came back
            if parse_json_lenient(text) is None:
                raise SchemaRejected("prompt mode returned no JSON")
        return text, usage

    def is_retryable(self, exc: Exception) -> bool:
        import openai
        if isinstance(exc, (openai.RateLimitError, openai.APIConnectionError, openai.InternalServerError)):
            return True
        return isinstance(exc, openai.APIStatusError) and int(getattr(exc, "status_code", 0) or 0) >= 500


def _env_provider_routing() -> Optional[Dict[str, Any]]:
    raw = os.environ.get("LIGHTFOOT_OPENAI_PROVIDER")
    if raw is None or not raw.strip():
        return {"sort": "throughput"}
    if raw.strip().lower() in ("off", "none", "{}"):
        return None
    try:
        v = json.loads(raw)
        return v if isinstance(v, dict) and v else None
    except Exception:
        log.warning("ignoring malformed LIGHTFOOT_OPENAI_PROVIDER %r (expected a JSON object)", raw)
        return {"sort": "throughput"}


def _usage_cost(u) -> Optional[float]:
    """OpenRouter puts the USD cost in usage.cost (with usage.include); the SDK keeps it as an extra attribute."""
    if u is None:
        return None
    cost = getattr(u, "cost", None)
    if cost is None and hasattr(u, "model_extra") and isinstance(u.model_extra, dict):
        cost = u.model_extra.get("cost")
    try:
        return None if cost is None else float(cost)
    except (TypeError, ValueError):
        return None


def make_client(provider: Optional[str] = None, raw_client=None) -> LLMClient:
    p = (provider or provider_name())
    if p == "anthropic":
        return AnthropicClient(raw_client)
    if p in ("openai", "openai-compat", "openrouter"):
        return OpenAICompatClient(raw_client)
    raise ValueError(f"unknown LIGHTFOOT_LLM_PROVIDER {p!r} (use 'anthropic' or 'openai')")


# ---------------------------------------------------------------------------
# Caller: retries, usage reporting, JSON handling
# ---------------------------------------------------------------------------
class LLMCaller:
    def __init__(self, client: LLMClient, model: str, cost_callback: Optional[Callable[[CallRecord], None]] = None,
                 max_retries: int = 6, effort: Optional[str] = None) -> None:
        self.client = client
        self.model = model
        self.cost_callback = cost_callback
        self.max_retries = max_retries
        self.effort = effort
        self._schema_ok: Optional[bool] = None     # remembered per (client, model)

    def _complete(self, kind: str, system: Optional[str], user: str, max_tokens: int, schema: Optional[Dict]) -> str:
        return self._complete_full(kind, system, user, max_tokens, schema)[0]

    def _complete_full(self, kind: str, system: Optional[str], user: str, max_tokens: int, schema: Optional[Dict]) -> Tuple[str, Usage]:
        attempt = 0
        while True:
            t0 = time.time()
            try:
                text, usage = self.client.complete(system, user, max_tokens, schema, model=self.model, effort=self.effort, kind=kind)
            except Exception as e:
                if self.client.is_retryable(e) and attempt < self.max_retries:
                    attempt += 1
                    delay = min(60.0, (2 ** attempt) + random.uniform(0, 1))
                    ra = self.client.retry_after(e)
                    if ra is not None:
                        delay = max(delay, ra)
                    _sleep(delay)
                    continue
                raise
            usage.latency_s = time.time() - t0
            if self.cost_callback is not None:
                self.cost_callback(CallRecord(kind=kind, model=self.model, input_tokens=usage.input_tokens,
                                              output_tokens=usage.output_tokens, cache_read_tokens=usage.cache_read_tokens,
                                              cache_write_tokens=usage.cache_write_tokens, latency_s=usage.latency_s,
                                              provider_usd=usage.cost_usd))
            return text, usage

    def text(self, kind: str, system: Optional[str], user: str, max_tokens: int) -> str:
        return self._complete(kind, system, user, max_tokens, None)

    def json(self, kind: str, system: Optional[str], user: str, max_tokens: int, schema: Dict) -> Optional[Any]:
        return self.json_full(kind, system, user, max_tokens, schema)[0]

    def json_full(self, kind: str, system: Optional[str], user: str, max_tokens: int, schema: Dict) -> Tuple[Optional[Any], Usage, str]:
        """Structured call returning (parsed, usage, raw text). Falls back to prompt JSON + lenient parsing when
        the endpoint rejects the schema; the rejection is remembered so later calls go straight to prompt JSON."""
        text: Optional[str] = None
        usage = Usage()
        if self._schema_ok is not False:
            try:
                text, usage = self._complete_full(kind, system, user, max_tokens, schema)
                self._schema_ok = True
            except SchemaRejected:
                self._schema_ok = False
        if text is None:
            text, usage = self._complete_full(kind, system, user + JSON_HINT, max_tokens, None)
        return parse_json_lenient(text), usage, text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def is_format_rejection(exc: Exception) -> bool:
    """True when the Anthropic API rejected `output_config.format` (older SDK/model)."""
    msg = str(exc).lower()
    return ("output_config" in msg or "format" in msg) and ("invalid" in msg or "unexpected" in msg or "not supported" in msg or "unknown" in msg)


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def parse_json_lenient(text: str) -> Optional[Any]:
    """Parse JSON from model output: direct, fenced, outermost braces, or truncated repair."""
    if not text:
        return None
    candidates = [text.strip()]
    m = _FENCE_RE.search(text)
    if m:
        candidates.append(m.group(1).strip())
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start:end + 1])
    for c in candidates:
        try:
            return json.loads(c)
        except Exception:
            pass
    if start != -1:
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[start:])
            return obj
        except Exception:
            pass
        frag = text[start:]
        for cut in range(len(frag), max(0, len(frag) - 4000), -1):
            piece = frag[:cut]
            for suffix in ("", "\"", "\"}", "\"}]", "\"}]}", "}", "]}", "}]}", "]}}", "}]}}"):
                try:
                    return json.loads(piece + suffix)
                except Exception:
                    continue
    return None
