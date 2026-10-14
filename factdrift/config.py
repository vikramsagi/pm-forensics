"""Model IDs, prices, budget and run limits. The only place these values live.

Prices are USD per million tokens, from https://platform.claude.com/docs/en/about-claude/pricing
(checked 2026-10-14). Haiku 5.5 is priced by prompt length: prompts over 100,000 tokens pay the higher
rate. Prompt caching is not used, so cache prices are not needed.
"""

PROVIDER = "claude"  # the model provider is a setting; other providers plug in behind factdrift.llm

MODELS = {
    "small": {
        "id": "claude-haiku-5-5",
        "input": 0.10, "output": 0.50,
        "long_prompt_tokens": 100_000, "long_input": 0.50, "long_output": 2.50,
    },
    "large": {
        "id": "claude-sonnet-5-5",
        "input": 2.00, "output": 10.00,
        "forced_tool": False,  # this model rejects tool_choice "tool" (seen in denial-triage); offer the tool with "auto"
    },
}

DEFAULT_TIER = "small"     # production default until the eval's model rule says otherwise
BATCH_DISCOUNT = 0.50
MAX_TOKENS = 4000

BUDGET_CAP_USD = 15.0      # whole build, eval included; the ledger refuses calls past it
