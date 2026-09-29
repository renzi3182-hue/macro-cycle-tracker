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


def test_regime_history_matches_classify_on_last_quarter():
    from src.classify.regime import regime_history

    g = _series([1.0, 1.0, 1.0, 2.0, 2.0, 2.0])
    i = _series([3.0, 3.0, 3.0, 1.0, 1.0, 1.0])
    hist = regime_history(g, i)
    assert hist.iloc[-1] == classify_regime(g, i)
    assert len(hist) == 3


def test_monthly_inflation_uses_quarterly_window():
    # CPI mensile: l'ultimo mese sale di 1.5pp sopra la media dei 3 mesi prima (sopra deadband 1.4),
    # ma rispetto alla media dei 3 trimestri prima la salita e' solo 1.17 (sotto deadband).
    # Deadband tarato su trimestri: l'inflazione resta "down", regime = Reflazione (non Espansione).
    from src.classify.regime import regime_history

    months = pd.date_range("2023-01-31", periods=24, freq="ME")
    inflation = pd.Series([2.0] * 15 + [1.0] * 8 + [2.5], index=months)
    growth = pd.Series([1.0, 1.0, 1.0] + [3.5] * 5, index=pd.date_range("2023-03-31", periods=8, freq="QE"))
    assert classify_regime(growth, inflation) == regime_history(growth, inflation).iloc[-1] == "Reflazione"
