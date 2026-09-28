import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

from src.classify.regime import classify_regime


def _series(values):
    dates = pd.date_range("2024-01-01", periods=len(values), freq="QE")
    return pd.Series(values, index=dates)


@pytest.mark.parametrize(
    "growth_vals,inflation_vals,expected",
    [
        ([1.0, 1.0, 1.0, 2.0], [3.0, 3.0, 3.0, 1.0], "Reflazione"),
        ([1.0, 1.0, 1.0, 2.0], [1.0, 1.0, 1.0, 3.0], "Espansione"),
        ([2.0, 2.0, 2.0, 1.0], [1.0, 1.0, 1.0, 3.0], "Stagflazione"),
        ([2.0, 2.0, 2.0, 1.0], [3.0, 3.0, 3.0, 1.0], "Deflazione"),
    ],
)
def test_classify_regime(growth_vals, inflation_vals, expected):
    assert classify_regime(_series(growth_vals), _series(inflation_vals)) == expected


def test_classify_regime_needs_enough_data():
    with pytest.raises(ValueError):
        classify_regime(_series([1.0, 2.0]), _series([1.0, 2.0, 3.0, 4.0]))


def test_classify_regime_deadband_suppresses_small_dip():
    # crescita: sale nettamente (delta=4, sopra soglia) poi scende di poco
    # (delta=-0.83, sotto soglia 2.0) - senza deadband darebbe "down" e quindi
    # Deflazione; con deadband resta "up" (Reflazione), il piccolo calo e'
    # rumore non un'inversione di trend.
    growth = _series([1.0, 1.0, 1.0, 5.0, 1.5])
    inflation = _series([1.0, 1.0, 1.0, 1.0, 1.0])
    assert classify_regime(growth, inflation) == "Reflazione"
