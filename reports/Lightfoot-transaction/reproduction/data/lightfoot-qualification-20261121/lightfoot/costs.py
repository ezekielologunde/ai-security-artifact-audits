"""Cost ledger: every model call is reported through a callback as a CallRecord."""
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Callable, Dict, List, Optional

import json as _json
import logging as _logging
import os as _os

_log = _logging.getLogger("lightfoot.costs")

# USD per 1M tokens (in, out). Anthropic first-party rates cached 2026-10; OpenRouter entries as configured.
# Extend with register_price() or env LIGHTFOOT_PRICES='{"model": [in, out]}'. Unknown models cost 0 (warned once).
PRICES: Dict[str, tuple] = {
    "openai/gpt-6-luna": (0.10, 0.50),
    "openai/gpt-5.6-luna": (0.20, 1.20),
    "meta-llama/llama-3.3-70b-instruct": (0.10, 0.32),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-fable-5-1": (10.00, 50.00),
}


@dataclass
class CallRecord:
    kind: str                # "extract" | "judge" | "answer" | "decompose" | "topic"
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cached: bool = False     # served from the on-disk cache, no API call made
    mock: bool = False       # served by the deterministic mock, no API call made
    latency_s: float = 0.0
    provider_usd: Optional[float] = None   # cost reported by the endpoint (OpenRouter usage.cost), when present
    ts: float = field(default_factory=time.time)

    @property
    def real(self) -> bool:
        return not (self.cached or self.mock)

    @property
    def usd_source(self) -> str:
        """"provider" when the endpoint reported the cost, else "table" (price-table estimate)."""
        return "provider" if self.provider_usd is not None else "table"

    @property
    def usd(self) -> float:
        if self.mock:
            return 0.0
        if self.provider_usd is not None:
            return float(self.provider_usd)
        pi, po = price_for(self.model)
        return (self.input_tokens * pi + self.output_tokens * po) / 1e6


_warned: set = set()
_UNPRICED = {"mock", ""}


def register_price(model: str, input_per_m: float, output_per_m: float) -> None:
    PRICES[model] = (float(input_per_m), float(output_per_m))


def _load_env_prices() -> None:
    raw = _os.environ.get("LIGHTFOOT_PRICES")
    if not raw:
        return
    try:
        for m, (i, o) in _json.loads(raw).items():
            register_price(m, i, o)
    except Exception as e:  # pragma: no cover
        _log.warning("ignoring malformed LIGHTFOOT_PRICES: %s", e)


_load_env_prices()


def price_for(model: str) -> tuple:
    p = PRICES.get(model)
    if p is None:
        p = PRICES.get(model.split(":")[0])  # OpenRouter variants like "model:nitro"
    if p is None:
        if model not in _UNPRICED and model not in _warned:
            _warned.add(model)
            _log.warning("no price registered for model %r; recording $0 (use register_price or LIGHTFOOT_PRICES)", model)
        return (0.0, 0.0)
    return p


CostCallback = Callable[[CallRecord], None]


class CostLedger:
    """Accumulates CallRecords. Pass `ledger.record` as the cost_callback."""

    def __init__(self) -> None:
        self.records: List[CallRecord] = []

    def record(self, rec: CallRecord) -> None:
        self.records.append(rec)

    def real_calls(self, kind: Optional[str] = None) -> int:
        return sum(1 for r in self.records if r.real and (kind is None or r.kind == kind))

    def calls(self, kind: Optional[str] = None) -> int:
        return sum(1 for r in self.records if kind is None or r.kind == kind)

    def tokens(self) -> Dict[str, int]:
        return {
            "input": sum(r.input_tokens for r in self.records),
            "output": sum(r.output_tokens for r in self.records),
        }

    def usd(self) -> float:
        return sum(r.usd for r in self.records)

    def summary(self) -> Dict[str, object]:
        by_kind: Dict[str, Dict[str, float]] = {}
        for r in self.records:
            d = by_kind.setdefault(r.kind, {"calls": 0, "real": 0, "input": 0, "output": 0, "usd": 0.0})
            d["calls"] += 1
            d["real"] += int(r.real)
            d["input"] += r.input_tokens
            d["output"] += r.output_tokens
            d["usd"] += r.usd
        return {"by_kind": by_kind, "usd": self.usd(), "real_calls": self.real_calls()}

    def reset(self) -> None:
        self.records.clear()

    def to_dicts(self) -> List[dict]:
        return [asdict(r) for r in self.records]
