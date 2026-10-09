import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

from src.classify.regime import (
    INFLATION_HIGH,
    activity_z,
    axis_states,
    classify_regime,
    growth_z,
    probabilities,
    regime_history,
)


def _m(values, start="2020-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="MS"))


def _q(values, start="2018-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="QS"))


WAVE = [2.0, 2.2, 1.9, 2.1] * 4  # PIL annuo che oscilla senza direzione per 4 anni
ACCEL = _q(WAVE + [2.3, 2.6, 2.9])
DECEL = _q(WAVE + [1.8, 1.5, 1.2])
N = 6 * 12
HIGH = _m([3.5] * N, "2018-01-01")  # inflazione stabile sopra la soglia del 2,5%
LOW = _m([1.0] * N, "2018-01-01")


@pytest.mark.parametrize(
    "gdp,inflation,expected",
    [
        (ACCEL, LOW, "Goldilocks"),
        (ACCEL, HIGH, "Reflazione"),
        (DECEL, HIGH, "Stagflazione"),
        (DECEL, LOW, "Deflazione"),
    ],
)
def test_classify_regime(gdp, inflation, expected):
    assert classify_regime(gdp, inflation) == expected


def test_needs_enough_data():
    with pytest.raises(ValueError):
        classify_regime(_m([100.0, 101.0]), _m([2.0, 2.0]))


def test_growing_but_slower_is_slowdown():
    # USA 10/2026: il PIL cresce ancora (2,7% -> 2,1%) ma rallenta; inflazione alta ma in calo -> Stagflazione (Quantaste).
    gdp = _q(WAVE + [2.0, 2.7, 2.1])
    inflation = _m([2.5] * (N - 6) + [3.8, 4.2, 3.5, 3.3, 3.3, 3.3], "2018-01-01")
    assert classify_regime(gdp, inflation, _m([2.5] * N, "2018-01-01")) == "Stagflazione"


def test_low_inflation_rising_counts_as_up():
    # Casario, Reflazione = "inflazione in accelerazione": sale anche se sotto la soglia.
    inflation = _m([1.0] * (N - 3) + [1.5, 1.8, 2.1], "2018-01-01")
    assert classify_regime(ACCEL, inflation) == "Reflazione"


def test_inflation_falling_fast_from_high_level_is_not_stagflation():
    # Europa fine 2008: livello ancora sopra il 2% ma in caduta veloce -> Deflazione, non Stagflazione.
    inflation = _m([4.0] * (N - 5) + [3.6, 3.0, 2.4, 2.1, 2.0], "2018-01-01")
    assert classify_regime(DECEL, inflation) == "Deflazione"


def test_confirm_months_delays_a_change():
    score = pd.Series([1.0] * 6 + [-1.0] + [1.0] * 3)
    assert set(axis_states(score, 0.5, -0.25, confirm=2)) == {"up"}
    assert axis_states(pd.Series([1.0] * 6 + [-1.0, -1.0]), 0.5, -0.25, confirm=2).iloc[-1] == "down"
    assert axis_states(pd.Series([1.0] * 6 + [-1.0]), INFLATION_HIGH, INFLATION_HIGH).iloc[-1] == "down"  # regime: subito


def test_hysteresis_keeps_state_inside_band():
    z = pd.Series([1.0, 1.0, 0.0, 0.0, 0.0])
    assert list(axis_states(z, 0.4, -0.4)) == ["up"] * 5


def test_quarterly_gdp_works_monthly():
    z = growth_z(ACCEL)
    assert z.index.freqstr == "MS" and z.iloc[-1] > 0


def test_history_has_both_axes_and_matches_classify():
    h = regime_history(ACCEL, HIGH)
    assert {"growth", "inflation", "regime", "inflation_level"} <= set(h.columns)
    assert h["regime"].iloc[-1] == classify_regime(ACCEL, HIGH)


def test_probabilities_sum_to_one_and_are_50_50_on_thresholds():
    p = probabilities(0.0, 0.0)
    assert sum(p.values()) == pytest.approx(1.0)
    assert all(v == pytest.approx(0.25) for v in p.values())


def test_probabilities_follow_activity_and_inflation():
    p = probabilities(2.0, 1.0)  # attivita' in accelerazione, inflazione 1 punto sopra la soglia
    assert max(p, key=p.get) == "Reflazione"
    assert probabilities(None, 1.0)["Reflazione"] == pytest.approx(probabilities(None, 1.0)["Stagflazione"])


def test_activity_prefers_industrial_production_over_cli():
    ip = _m([1.0] * 30 + [2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
    cli = _m([100.0] * 30 + [99.0, 98.0, 97.0, 96.0, 95.0, 94.0])
    assert activity_z(ip, cli).iloc[-1] > 0 > activity_z(None, cli).iloc[-1]
    assert activity_z(None, None).empty
