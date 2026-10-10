import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from src.data import http


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch):
    """Niente attese reali nei test di retry; contatore dell'interruttore per fonte azzerato a ogni test."""
    monkeypatch.setattr(http.time, "sleep", lambda seconds: None)
    http._consecutive_failures.clear()
