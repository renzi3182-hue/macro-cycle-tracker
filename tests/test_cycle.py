import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

from src.classify.cycle import classify_cycle


@pytest.mark.parametrize(
    "values,expected",
    [
        ([1.0, 2.0], "Espansione"),
        ([2.0, 1.0], "Rallentamento"),
        ([-1.0, -2.0], "Recessione"),
        ([-2.0, -1.0], "Ripresa"),
    ],
)
def test_classify_cycle(values, expected):
    series = pd.Series(values, index=pd.date_range("2024-01-01", periods=len(values), freq="QE"))
    assert classify_cycle(series) == expected


def test_classify_cycle_needs_enough_data():
    with pytest.raises(ValueError):
        classify_cycle(pd.Series([1.0], index=pd.date_range("2024-01-01", periods=1, freq="QE")))


def test_classify_cycle_deadband_suppresses_small_dip():
    # momentum sale nettamente (+4, sopra soglia 1.4) poi scende di poco
    # (-0.5, sotto soglia) - senza deadband darebbe "decel" e Rallentamento;
    # con deadband resta "accel" (Espansione), il calo e' rumore.
    values = [1.0, 5.0, 4.5]
    series = pd.Series(values, index=pd.date_range("2024-01-01", periods=len(values), freq="QE"))
    assert classify_cycle(series) == "Espansione"
