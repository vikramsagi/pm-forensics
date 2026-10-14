"""The only path to a model. Every call checks the budget, forces a structured answer through a tool
schema, validates it, and writes its cost to the spend ledger.

The model has no tools that act on anything: the single tool offered is the answer format.

Mock mode (FACTDRIFT_MOCK=1, or no API key) replaces the API with a registered deterministic fake, so
tests and dry runs cost nothing.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from factdrift import budget, config

ROOT = Path(__file__).resolve().parent.parent
_MOCKS: dict[str, Callable[[str], dict]] = {}
USAGE_KEYS = ("input_tokens", "output_tokens")


@dataclass
class LLMResult:
    output: dict
    model: str
    usage: dict
    cost_usd: float
    latency_ms: float
    mock: bool
    attempts: int = 1
    errors: list[str] = field(default_factory=list)


class InvalidOutput(RuntimeError):
    def __init__(self, errors: list[str], usage: dict, cost_usd: float):
        super().__init__("; ".join(errors))
        self.errors, self.usage, self.cost_usd = errors, usage, cost_usd


def _api_key() -> str | None:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "ANTHROPIC_API_KEY":
                return value.strip() or None
    return None


def mock_mode() -> bool:
    return os.environ.get("FACTDRIFT_MOCK") == "1" or _api_key() is None


def register_mock(tool_name: str, fn: Callable[[str], dict]) -> None:
    """Register a deterministic fake for one tool. `fn` receives the user message text."""
    _MOCKS[tool_name] = fn


def cost_of(tier: str, usage: dict, batch: bool = False) -> float:
    p = config.MODELS[tier]
    inp, out = usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    long_prompt = "long_prompt_tokens" in p and inp > p["long_prompt_tokens"]
    rate_in = p["long_input"] if long_prompt else p["input"]
    rate_out = p["long_output"] if long_prompt else p["output"]
    usd = (inp * rate_in + out * rate_out) / 1_000_000
    return usd * (config.BATCH_DISCOUNT if batch else 1.0)


def estimate_max_cost(tier: str, system: str, user: str, max_tokens: int) -> float:
    approx_input = int((len(system) + len(user)) / 3.0)  # conservative: about 3 characters per token
    return cost_of(tier, {"input_tokens": approx_input, "output_tokens": max_tokens})


def _client():
    import anthropic

    return anthropic.Anthropic(api_key=_api_key(), max_retries=3)


def tool_choice(tier: str, tool_name: str) -> dict:
    if config.MODELS[tier].get("forced_tool", True):
        return {"type": "tool", "name": tool_name}
    return {"type": "auto"}


def call(*, tier: str, system: str, user: str, tool: dict, purpose: str, run_id: str | None = None,
         max_tokens: int = config.MAX_TOKENS, validate: Callable[[dict], Any] | None = None,
         max_attempts: int = 2) -> LLMResult:
    """Call the model with one required answer tool. `validate` raises on a bad answer, which triggers
    one retry that quotes only the validation error, never the source text again."""
    model = config.MODELS[tier]["id"]
    errors: list[str] = []
    total_usage = {k: 0 for k in USAGE_KEYS}
    total_cost = 0.0
    started = time.perf_counter()
    for attempt in range(1, max_attempts + 1):
        budget.check(estimate_max_cost(tier, system, user, max_tokens))
        if mock_mode():
            output = _MOCKS[tool["name"]](user)
            usage = {"input_tokens": (len(system) + len(user)) // 4, "output_tokens": 150}
            cost, is_mock = 0.0, True
        else:
            resp = _client().messages.create(
                model=model, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": user}],
                tools=[tool], tool_choice=tool_choice(tier, tool["name"]),
            )
            usage = {k: getattr(resp.usage, k, 0) or 0 for k in USAGE_KEYS}
            blocks = [b for b in resp.content if getattr(b, "type", "") == "tool_use"]
            output = blocks[0].input if blocks else {}
            cost, is_mock = cost_of(tier, usage), False
        budget.record(model=model, purpose=purpose, usage=usage, cost_usd=cost, run_id=run_id, mock=is_mock)
        for k in USAGE_KEYS:
            total_usage[k] += usage[k]
        total_cost += cost
        try:
            if not output:
                raise ValueError("the answer tool was not used")
            if validate:
                validate(output)
            return LLMResult(output, model, total_usage, total_cost,
                             (time.perf_counter() - started) * 1000, is_mock, attempt, errors)
        except Exception as e:  # noqa: BLE001 - any validation failure triggers one retry
            errors.append(f"attempt {attempt}: {type(e).__name__}: {str(e)[:300]}")
            user = user + (f"\n\nYour previous answer was rejected: {str(e)[:300]}. "
                           "Answer again using the tool, following the schema exactly.")
    raise InvalidOutput(errors, total_usage, total_cost)
