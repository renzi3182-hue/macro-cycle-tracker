import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.classify.cycle import classify_cycle
from src.classify.leading import leading_risk


def _s(v):
    return pd.Series([v], index=pd.to_datetime(["2024-01-01"]))


def test_leading_risk_levels():
    assert leading_risk(_s(1.0), _s(2.0), _s(-0.5))["level"] == "Basso"
    assert leading_risk(_s(-0.5), _s(2.0), _s(-0.5))["level"] == "Medio"
    assert leading_risk(_s(-0.5), _s(3.0), _s(-0.5))["level"] == "Alto"


def test_leading_risk_empty_series_are_off():
    empty = pd.Series(dtype=float)
    assert leading_risk(empty, empty, empty)["level"] == "Basso"


def test_high_risk_downgrades_expansion_only():
    up = pd.Series([1.0, 2.0], index=pd.date_range("2024-01-01", periods=2, freq="QE"))
    assert classify_cycle(up, "Alto") == "Rallentamento"
    assert classify_cycle(up, "Medio") == "Espansione"
    down = pd.Series([-1.0, -2.0], index=up.index)
    assert classify_cycle(down, "Alto") == "Recessione"
