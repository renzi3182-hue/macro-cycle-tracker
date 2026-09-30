import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

from src.classify.cycle import classify_cycle

QUIET = [2.0, 2.2, 1.8, 2.0] * 10  # 10 anni di PIL annuo intorno a 2%


def _q(values):
    return pd.Series(values, index=pd.date_range("2010-03-31", periods=len(values), freq="QE"))


@pytest.mark.parametrize(
    "tail,expected",
    [
        ([2.6, 3.4], "Espansione"),  # sopra trend e in accelerazione
        ([1.6, 0.9], "Rallentamento"),  # ancora positivo ma in calo
        ([0.5, -0.5, -1.5], "Recessione"),  # negativo e in calo
        ([1.0, 0.5, 1.0, 1.8], "Ripresa"),  # sotto trend (3%) e in risalita
    ],
)
def test_classify_cycle(tail, expected):
    base = QUIET if expected != "Ripresa" else [3.0, 3.2, 2.8, 3.0] * 10
    assert classify_cycle(_q(base + tail)) == expected


def test_classify_cycle_needs_enough_data():
    with pytest.raises(ValueError):
        classify_cycle(_q([1.0, 2.0]))


def test_small_steady_rise_is_detected_on_a_quiet_series():
    # Regressione Eurozona: la soglia fissa (1.4) non scattava mai e lasciava il momentum "in calo" per anni.
    assert classify_cycle(_q(QUIET + [2.4, 2.8, 3.2])) == "Espansione"


def test_flat_growth_below_trend_is_slowdown_not_expansion():
    assert classify_cycle(_q([3.0, 3.2, 2.8, 3.0] * 10 + [1.0] * 4)) == "Rallentamento"


def test_leading_series_can_lift_the_phase():
    growth = _q([3.0, 3.2, 2.8, 3.0] * 10 + [1.0] * 4)  # PIL fermo sotto trend
    cli = pd.Series([100.0] * 126 + [100.5, 101.0, 101.5, 102.0, 102.5, 103.0],
                    index=pd.date_range("2010-01-31", periods=132, freq="ME"))
    assert classify_cycle(growth, momentum_inputs=[growth, cli]) == "Ripresa"
