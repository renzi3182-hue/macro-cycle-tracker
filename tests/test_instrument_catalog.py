import pandas as pd

from src.classify import instrument_catalog


def test_fx_series_exports_recent_positive_rates(monkeypatch):
    dates = pd.date_range("2026-01-01", periods=300, freq="D")
    values = [1.1] * 299 + [float("nan")]
    series = pd.Series(values, index=dates)
    calls = []

    def fake(area, indicator):
        calls.append((area, indicator))
        return series

    monkeypatch.setattr(instrument_catalog.cache, "read_indicator_series", fake)
    out = instrument_catalog.fx_series()
    assert calls == [("Valute", "eurusd")]
    rows = out["EURUSD"]
    assert len(rows) == instrument_catalog.FX_SESSIONS
    assert rows[-1] == [dates[-2].date().isoformat(), 1.1]


def test_fx_series_empty_cache_gives_empty_list(monkeypatch):
    monkeypatch.setattr(instrument_catalog.cache, "read_indicator_series", lambda a, i: pd.Series(dtype=float))
    assert instrument_catalog.fx_series() == {"EURUSD": []}
