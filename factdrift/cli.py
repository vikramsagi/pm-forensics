"""Command line for fact-drift.

    uv run factdrift budget     # spend so far against the cap
    uv run factdrift probe      # one tiny live call to confirm the model ID and structured output
"""

from __future__ import annotations

import argparse
import json
import sys

from factdrift import budget, config, llm

PROBE_TOOL = {
    "name": "record_claims",
    "description": "Record each factual claim found in the text.",
    "input_schema": {
        "type": "object",
        "properties": {
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "quote": {"type": "string", "description": "the exact words from the text"},
                        "subject": {"type": "string"},
                        "value": {"type": "string"},
                        "qualifier": {"type": "string"},
                    },
                    "required": ["quote", "subject", "value"],
                },
            }
        },
        "required": ["claims"],
    },
}
PROBE_TEXT = "Signed 40 paying B2B customers in 6 months."


def _probe_validate(out: dict) -> None:
    claims = out.get("claims")
    if not isinstance(claims, list) or not claims:
        raise ValueError("no claims returned")
    for c in claims:
        if c.get("quote", "") not in PROBE_TEXT:
            raise ValueError(f"quote not found verbatim: {c.get('quote')!r}")


def probe(tier: str) -> int:
    if llm.mock_mode():
        print("No API key found (or FACTDRIFT_MOCK=1). Add ANTHROPIC_API_KEY to .env, then run again.")
        return 1
    result = llm.call(tier=tier, system="Extract factual claims. Quote the source text exactly.",
                      user=PROBE_TEXT, tool=PROBE_TOOL, purpose="probe", max_tokens=400,
                      validate=_probe_validate)
    print(f"Model: {result.model}")
    print(f"Tool choice: {llm.tool_choice(tier, PROBE_TOOL['name'])['type']}")
    print(f"Tokens: {result.usage['input_tokens']} in, {result.usage['output_tokens']} out")
    print(f"Cost: {result.cost_usd:.6f} USD, attempts: {result.attempts}")
    print("Answer:", json.dumps(result.output, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="factdrift")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("budget", help="show spend so far against the cap")
    p = sub.add_parser("probe", help="one tiny live call to check the model setup")
    p.add_argument("--tier", default=config.DEFAULT_TIER, choices=sorted(config.MODELS))
    args = parser.parse_args(argv)
    if args.command == "budget":
        print(budget.summary())
        return 0
    if args.command == "probe":
        return probe(args.tier)
    return 2


if __name__ == "__main__":
    sys.exit(main())
