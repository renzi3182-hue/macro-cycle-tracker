import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

from src.classify.regime import (
    GROWTH_BAND,
    INFLATION_HIGH,
    axis_states,
    classify_regime,
    growth_z,
    probabilities,
    regime_history,
)


def _m(values, start="2020-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="MS"))


WAVE = [100.0, 100.3, 100.1, 99.8, 100.0, 100.2] * 5  # CLI che oscilla senza direzione per 30 mesi
RISING = WAVE + [100.5, 101.0, 101.5, 102.0, 102.5]
FALLING = WAVE + [99.5, 99.0, 98.5, 98.0, 97.5]
HIGH = [3.5] * 35  # inflazione stabile ben sopra il 2%
LOW = [1.0] * 35


@pytest.mark.parametrize(
    "cli,inflation,expected",
    [
        (RISING, LOW, "Goldilocks"),
        (RISING, HIGH, "Reflazione"),
        (FALLING, HIGH, "Stagflazione"),
        (FALLING, LOW, "Deflazione"),
    ],
)
def test_classify_regime(cli, inflation, expected):
    assert classify_regime(_m(cli), _m(inflation)) == expected


def test_needs_enough_data():
    with pytest.raises(ValueError):
        classify_regime(_m([100.0, 101.0]), _m([2.0, 2.0]))


def test_inflation_falling_fast_from_high_level_is_not_stagflation():
    # Europa fine 2008: livello ancora sopra il 2% ma in caduta veloce -> Deflazione, non Stagflazione.
    inflation = _m([4.0] * 30 + [3.6, 3.0, 2.4, 2.1, 2.0])
    assert classify_regime(_m(FALLING), inflation) == "Deflazione"


def test_one_month_spike_does_not_flip_the_axis():
    score = pd.Series([1.0] * 6 + [-1.0] + [1.0] * 3)
    assert set(axis_states(score, INFLATION_HIGH, -0.25)) == {"up"}  # serve la conferma di 2 mesi
    assert axis_states(pd.Series([1.0] * 6 + [-1.0, -1.0]), INFLATION_HIGH, -0.25).iloc[-1] == "down"


def test_hysteresis_keeps_state_inside_band():
    z = pd.Series([1.0, 1.0, 0.0, 0.0, 0.0])
    assert list(axis_states(z, GROWTH_BAND, -GROWTH_BAND)) == ["up"] * 5


def test_quarterly_gdp_fallback_works_monthly():
    gdp = pd.Series([2.0, 2.2, 1.8, 2.0] * 4 + [2.5, 3.0], index=pd.date_range("2020-01-01", periods=18, freq="QS"))
    z = growth_z(gdp)
    assert z.index.freqstr == "MS" and z.iloc[-1] > 0


def test_history_has_both_axes_and_matches_classify():
    h = regime_history(_m(RISING), _m(HIGH))
    assert {"growth", "inflation", "regime", "inflation_level"} <= set(h.columns)
    assert h["regime"].iloc[-1] == classify_regime(_m(RISING), _m(HIGH))


def test_probabilities_sum_to_one_and_are_75_percent_on_the_band():
    p = probabilities(GROWTH_BAND, (INFLATION_HIGH + -0.25) / 2)
    assert sum(p.values()) == pytest.approx(1.0)
    assert p["Goldilocks"] + p["Reflazione"] == pytest.approx(0.75)
    assert p["Reflazione"] == pytest.approx(p["Goldilocks"])  # inflazione al centro della banda: 50/50
