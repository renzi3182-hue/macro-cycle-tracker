import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

from src.classify.assess import HIGH_FREQ_MAX_DAYS, assess, stale_high_freq
from src.data import cache


def _m(values, start="2015-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="MS"))


N = 90
CLI = _m([100.0, 100.3, 100.1, 99.8, 100.0, 100.2] * 14 + [100.5, 101.0, 101.5, 102.0, 102.5, 103.0])
SERIES = {"cli": CLI, "inflation_yoy": _m([1.0] * N), "unemployment_rate": _m([5.0] * (N - 6) + [4.0] * 6)}
TODAY = CLI.index[-1] + pd.Timedelta(days=45)


def test_assess_gives_regime_phase_and_metadata():
    a = assess("UK", SERIES, today=TODAY)
    assert (a["regime"], a["phase"]) == ("Goldilocks", "Espansione")
    assert a["month"] == CLI.index[-1]
    assert a["stale"] == [] and a["confidence"] in ("Alta", "Media", "Bassa")
    assert sum(a["probabilities"].values()) == pytest.approx(1.0)
    assert a["inflation_prob"] == pytest.approx(0.5)  # inflazione piatta: punteggio 0, sulla soglia
    assert a["history"]["regime"].iloc[-1] == a["regime"]


def test_missing_inflation_returns_none_and_gdp_is_the_growth_input():
    assert assess("UK", {"cli": CLI}) is None
    gdp = pd.Series([2.0] * 28 + [2.5, 3.0], index=pd.date_range("2015-01-01", periods=30, freq="QS"))
    a = assess("UK", {"growth_yoy": gdp, "inflation_yoy": _m([1.0] * N)}, today=TODAY)
    assert a["growth_source"] == "growth_yoy" and a["regime"] == "Goldilocks"


def test_stale_core_input_lowers_confidence():
    a = assess("UK", SERIES, today=TODAY + pd.Timedelta(days=200))
    assert "cli" in a["stale"] and a["confidence"] == "Bassa"


def test_stale_high_freq_daily_5_weekly_14():
    today = pd.Timestamp("2026-10-09")
    dates = {k: today - pd.Timedelta(days=d) for k, d in HIGH_FREQ_MAX_DAYS.items()}
    assert stale_high_freq(dates, today) == []
    dates[("Mercati", "vix")] = today - pd.Timedelta(days=6)
    dates[("USA", "claims")] = today - pd.Timedelta(days=13)
    del dates[("USA", "yield_curve")]
    assert stale_high_freq(dates, today) == [("USA", "yield_curve"), ("Mercati", "vix")]


def test_cache_refuses_to_wipe_history(tmp_path):
    db = tmp_path / "t.db"
    full = _m([1.0] * 100)
    cache.write_indicator_series("USA", "cli", full, db_path=db)
    for bad in (pd.Series(dtype=float), full.tail(10), _m([1.0] * 60, start="2000-01-01")):
        with pytest.raises(ValueError):
            cache.write_indicator_series("USA", "cli", bad, db_path=db)
    assert len(cache.read_indicator_series("USA", "cli", db_path=db)) == 100
    cache.write_indicator_series("USA", "cli", _m([2.0] * 101), db_path=db)  # serie normale: sostituita
    assert cache.read_indicator_series("USA", "cli", db_path=db).iloc[-1] == 2.0
