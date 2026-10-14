import pytest


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path, monkeypatch):
    """Every test uses mock mode and its own empty ledger, so tests never spend money or touch real spend."""
    monkeypatch.setenv("FACTDRIFT_MOCK", "1")
    monkeypatch.setenv("FACTDRIFT_LEDGER", str(tmp_path / "ledger.jsonl"))
    yield
