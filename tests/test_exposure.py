import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src.classify import exposure as ex


def _returns(values: list[float], start: str = "2020-01-01") -> pd.Series:
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="MS"))


def test_distance_against_ten_month_average():
    r = _returns([0.01] * 12)
    d = ex.distance(r)
    assert d.iloc[:9].isna().all() and d.iloc[9:].notna().all()
    px = 1.01 ** np.arange(1, 13)
    assert abs(d.iloc[-1] - (px[-1] / px[-10:].mean() - 1)) < 1e-12


def test_distance_starts_at_first_return():
    r = _returns([np.nan] * 5 + [0.01] * 12)
    d = ex.distance(r)
    assert d.iloc[:14].isna().all() and d.iloc[14:].notna().all()


def test_rising_market_is_positive_falling_is_negative():
    up = ex.summary(_returns([0.02] * 24))
    assert up["positive"] and up["label"] == ex.POSITIVE and up["dist_pct"] > 0 and not up["near"]
    down = ex.summary(_returns([0.02] * 24 + [-0.05] * 6))
    assert not down["positive"] and down["label"] == ex.NEGATIVE and down["dist_pct"] < 0


def test_since_counts_months_in_current_state():
    s = ex.summary(_returns([0.02] * 24 + [-0.05] * 6))
    hist = ex.states(_returns([0.02] * 24 + [-0.05] * 6))
    flip = hist.index[~hist["positive"]][0]
    assert s["since"] == f"{flip:%Y-%m}" and s["months"] == (hist.index >= flip).sum()
    assert s["month"] == "2022-06" and not s["first_reading"]
    assert ex.summary(_returns([0.02] * 24))["first_reading"]


def test_near_average_warns_without_changing_state():
    s = ex.states(_returns([0.0] * 15))
    assert (s["dist"] == 0).all() and s["positive"].all() and s["near"].all()
    slightly_below = ex.summary(_returns([0.0] * 14 + [-0.005]))
    assert not slightly_below["positive"] and slightly_below["near"]


def test_history_is_capped():
    s = ex.summary(_returns([0.01] * 100))
    assert len(s["history"]) == ex.HISTORY_MONTHS and s["history"][-1]["month"] == s["month"]


def test_no_data_gives_no_summary():
    assert ex.summary(_returns([0.01] * 5)) is None
    assert ex.summary(_returns([np.nan] * 20)) is None


def test_countries_skips_missing_areas():
    eq = pd.DataFrame({"USA": _returns([0.01] * 20), "Cina": _returns([np.nan] * 20)})
    out = ex.countries(eq)
    assert list(out) == ["USA"]
