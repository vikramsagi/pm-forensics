import pytest

from factdrift import budget, llm

TOOL = {"name": "answer", "description": "d", "input_schema": {"type": "object", "properties": {}}}


def test_haiku_cost_uses_the_short_prompt_rate():
    usage = {"input_tokens": 50_000, "output_tokens": 10_000}
    assert llm.cost_of("small", usage) == pytest.approx((50_000 * 0.10 + 10_000 * 0.50) / 1_000_000)


def test_haiku_cost_uses_the_long_prompt_rate_over_100k_tokens():
    usage = {"input_tokens": 200_000, "output_tokens": 1_000}
    assert llm.cost_of("small", usage) == pytest.approx((200_000 * 0.50 + 1_000 * 2.50) / 1_000_000)


def test_batch_halves_the_cost():
    usage = {"input_tokens": 10_000, "output_tokens": 1_000}
    assert llm.cost_of("large", usage, batch=True) == pytest.approx(llm.cost_of("large", usage) / 2)


def test_mock_call_records_zero_cost_in_the_ledger():
    llm.register_mock("answer", lambda user: {"ok": True})
    result = llm.call(tier="small", system="s", user="u", tool=TOOL, purpose="test")
    assert result.mock and result.cost_usd == 0
    assert budget.entries()[-1]["purpose"] == "test"


def test_a_rejected_answer_is_retried_once_then_raises():
    llm.register_mock("answer", lambda user: {"ok": False})

    def validate(out):
        if not out["ok"]:
            raise ValueError("bad")

    with pytest.raises(llm.InvalidOutput) as err:
        llm.call(tier="small", system="s", user="u", tool=TOOL, purpose="test", validate=validate)
    assert len(err.value.errors) == 2


def test_an_empty_answer_counts_as_rejected():
    llm.register_mock("answer", lambda user: {})
    with pytest.raises(llm.InvalidOutput):
        llm.call(tier="small", system="s", user="u", tool=TOOL, purpose="test")


def test_budget_cap_stops_the_call_before_it_is_made(monkeypatch):
    budget.record(model="m", purpose="t", usage={}, cost_usd=15.0, run_id=None, mock=False)
    llm.register_mock("answer", lambda user: {"ok": True})
    with pytest.raises(budget.BudgetExceeded):
        llm.call(tier="small", system="s", user="u", tool=TOOL, purpose="test")


def test_sonnet_is_offered_the_tool_with_auto_choice():
    assert llm.tool_choice("large", "answer") == {"type": "auto"}
    assert llm.tool_choice("small", "answer") == {"type": "tool", "name": "answer"}
