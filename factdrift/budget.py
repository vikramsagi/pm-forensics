"""Append-only spend ledger and a hard budget cap. Every model call is checked here first.

    uv run factdrift budget      # show spend so far
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from factdrift import config

ROOT = Path(__file__).resolve().parent.parent


class BudgetExceeded(RuntimeError):
    pass


def ledger_path() -> Path:
    return Path(os.environ.get("FACTDRIFT_LEDGER", ROOT / ".spend" / "ledger.jsonl"))


def entries() -> list[dict]:
    p = ledger_path()
    return [json.loads(line) for line in p.read_text().splitlines() if line] if p.exists() else []


def total_usd() -> float:
    return round(sum(e["cost_usd"] for e in entries()), 6)


def check(estimate_usd: float, cap: float | None = None) -> None:
    """Refuse a call if it could take total spend past the cap."""
    cap = config.BUDGET_CAP_USD if cap is None else cap
    spent = total_usd()
    if spent + estimate_usd > cap:
        raise BudgetExceeded(
            f"spent {spent:.4f} USD; a call estimated at up to {estimate_usd:.4f} USD would pass the {cap:.2f} USD cap")


def record(*, model: str, purpose: str, usage: dict, cost_usd: float, run_id: str | None, mock: bool) -> None:
    p = ledger_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "model": model, "purpose": purpose, "run_id": run_id,
             "mock": mock, "usage": usage, "cost_usd": round(cost_usd, 6)}
    with p.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def summary() -> str:
    by: dict[tuple, list] = defaultdict(lambda: [0, 0.0])
    for e in entries():
        k = (e["purpose"], e["model"], "mock" if e["mock"] else "live")
        by[k][0] += 1
        by[k][1] += e["cost_usd"]
    lines = [f"Total spend: {total_usd():.4f} USD of {config.BUDGET_CAP_USD:.2f} USD cap"]
    for (purpose, model, mode), (n, c) in sorted(by.items()):
        lines.append(f"  {purpose:14s} {model:22s} {mode:5s} {n:5d} calls  {c:.4f} USD")
    return "\n".join(lines)
