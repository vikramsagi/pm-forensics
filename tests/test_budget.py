import pytest

from factdrift import budget


def test_empty_ledger_has_zero_spend():
    assert budget.total_usd() == 0


def test_record_adds_to_total():
    budget.record(model="m", purpose="t", usage={}, cost_usd=0.25, run_id=None, mock=False)
    budget.record(model="m", purpose="t", usage={}, cost_usd=0.5, run_id=None, mock=False)
    assert budget.total_usd() == 0.75


def test_check_refuses_a_call_that_would_pass_the_cap():
    budget.record(model="m", purpose="t", usage={}, cost_usd=14.9, run_id=None, mock=False)
    with pytest.raises(budget.BudgetExceeded):
        budget.check(0.2, cap=15.0)


def test_check_allows_a_call_under_the_cap():
    budget.record(model="m", purpose="t", usage={}, cost_usd=1.0, run_id=None, mock=False)
    budget.check(0.2, cap=15.0)
