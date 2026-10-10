import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

from src.classify.assess import HIGH_FREQ_MAX_DAYS, assess, stale_high_freq, uncertain_pair
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


def test_uncertain_pair_none_when_both_axes_solid():
    assert uncertain_pair("up", "up", xg=0.5, xi=2.0) is None


def test_uncertain_pair_flips_weaker_growth_axis():
    assert uncertain_pair("up", "up", xg=0.1, xi=2.0) == ("Reflazione", "Stagflazione")


def test_uncertain_pair_flips_weaker_inflation_axis():
    assert uncertain_pair("up", "down", xg=2.0, xi=0.05) == ("Goldilocks", "Reflazione")


def test_regime_label_matches_regime_when_axes_solid():
    inflation = _m([1.0] * (N - 6) + [1.5, 2.0, 2.8, 3.5, 4.2, 5.0])
    a = assess("UK", {**SERIES, "inflation_yoy": inflation}, today=TODAY)
    assert a["regime_label"] == a["regime"]


def test_regime_label_is_uncertain_on_borderline_axis():
    """SERIES ha inflazione piatta: punteggio esattamente sulla soglia, asse debole."""
    a = assess("UK", SERIES, today=TODAY)
    assert a["regime_label"] == f'Incerto: {a["regime"]} / {a["regime_label"].split(" / ")[1]}'


def test_quarter_end_estimate_none_when_top_two_probabilities_are_close():
    a = assess("UK", SERIES, today=TODAY)  # inflazione piatta: probabilita' vicine al 50%
    assert a["quarter_end_estimate"] is None


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
