import pytest


@pytest.fixture(autouse=True)
def _outside_herdr(monkeypatch):
    """Tests run in a Herdr terminal; its real wa label must not reach them."""
    monkeypatch.delenv("HC_TERMINAL_ID", raising=False)
