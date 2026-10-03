import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

from src.classify.cycle import LEVEL_MIN_MONTHS, phase_history, phase_name


def _m(values):
    return pd.Series(values, index=pd.date_range("2015-01-01", periods=len(values), freq="MS"))


N = LEVEL_MIN_MONTHS + 12


@pytest.mark.parametrize(
    "growth,above,recession,expected",
    [
        ("up", True, False, "Espansione"),
        ("down", True, False, "Rallentamento"),
        ("down", False, False, "Rallentamento"),  # sotto potenziale ma senza conferma dura: niente Recessione
        ("up", False, False, "Ripresa"),
        ("down", False, True, "Recessione"),
        ("up", False, True, "Ripresa"),  # CLI gia' in risalita durante la recessione: si esce dal fondo
    ],
)
def test_phase_name(growth, above, recession, expected):
    assert phase_name(growth, above, recession) == expected


def test_gdp_below_trend_is_recovery_even_with_low_unemployment():
    # Europa 2026: disoccupazione ai minimi storici ma PIL sotto il trend -> non e' Espansione
    states = _m(["up"] * N)
    low_u = _m([8.0] * (N - 6) + [6.0] * 6)
    assert phase_history(states, low_u, _m([1.5] * (N - 6) + [1.0] * 6)).iloc[-1] == "Ripresa"
    assert phase_history(states, low_u, _m([1.5] * (N - 6) + [2.0] * 6)).iloc[-1] == "Espansione"


def test_negative_gdp_or_sahm_confirms_recession():
    states = _m(["down"] * N)
    u = _m([5.0] * N)
    gdp_neg = pd.Series([1.0] * (N // 3 - 1) + [-0.5], index=pd.date_range("2015-01-01", periods=N // 3, freq="QS"))
    assert phase_history(states, u, gdp_neg).iloc[-1] == "Recessione"
    assert phase_history(states, u, recession=_m([False] * (N - 1) + [True])).iloc[-1] == "Recessione"
    assert phase_history(states, u).iloc[-1] == "Rallentamento"


def test_rising_unemployment_is_fallback_without_gdp():
    states = _m(["up"] * N)
    assert phase_history(states, _m([5.0] * (N - 6) + [4.0] * 6)).iloc[-1] == "Espansione"
    assert phase_history(states, _m([5.0] * (N - 6) + [6.0] * 6)).iloc[-1] == "Ripresa"


def test_needs_level_data():
    with pytest.raises(ValueError):
        phase_history(_m(["up"] * 5))
