import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

from src.classify.gip import gip_view, policy_stance
from src.classify.regime import GROWTH_DEADBAND, regime_probabilities


def _s(values):
    return pd.Series(values, index=pd.date_range("2020-01-01", periods=len(values), freq="MS"))


def test_probabilities_sum_to_one_and_follow_direction():
    flat = _s([1.0] * 6)
    p = regime_probabilities(flat, flat)
    assert sum(p.values()) == pytest.approx(1.0)
    assert all(v == pytest.approx(0.25) for v in p.values())  # nessuna direzione: tutto incerto
    up_down = regime_probabilities(_s([1, 1, 1, 1 + 3 * GROWTH_DEADBAND]), _s([5, 5, 5, 0]))
    assert max(up_down, key=up_down.get) == "Reflazione"


def test_probability_at_deadband_is_75_percent():
    p = regime_probabilities(_s([0, 0, 0, GROWTH_DEADBAND]), _s([0, 0, 0, 0]))
    assert p["Reflazione"] + p["Espansione"] == pytest.approx(0.75)


def test_policy_stance():
    assert policy_stance(_s([1.0] * 7)) == "Neutrale"
    assert policy_stance(_s([1.0] * 6 + [1.5])) == "Restrittiva"
    assert policy_stance(_s([1.5] * 6 + [1.0])) == "Espansiva"
    assert policy_stance(_s([1.0, 1.0])) == "n/d"


def test_gip_view_picks_stagflation_when_growth_down_inflation_up():
    view = gip_view(_s([5, 5, 5, 0]), _s([2, 2, 2, 4]), _s([1.0] * 7))
    assert view["regime"] == "Stagflazione"
    assert view["policy"] == "Neutrale"
