import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.classify.score import MIN_ASSETS, complete_months, monthly_prices, scores


def _prices(n_assets: int, months: int = 24) -> dict[str, pd.Series]:
    """Asset i cresce dell'i% al mese: piu' alto i, piu' forti tendenza e momentum."""
    idx = pd.date_range("2020-01-31", periods=months, freq="ME")
    return {f"A{i}": pd.Series([1.01 ** (i * k) for k in range(months)], index=idx) for i in range(n_assets)}


def test_score_ranks_strongest_asset_first():
    s = scores(monthly_prices(_prices(MIN_ASSETS + 2))).iloc[-1]
    assert s.idxmax() == f"A{MIN_ASSETS + 1}" and s.max() == 100 and s.min() >= 1


def test_score_needs_full_history_and_min_assets():
    s = scores(monthly_prices(_prices(MIN_ASSETS + 2)))
    assert s.iloc[:11].isna().all().all()  # momentum 12-1 serve 12 mesi
    assert scores(monthly_prices(_prices(MIN_ASSETS - 1))).isna().all().all()


def test_short_history_asset_enters_after_12_months_without_blocking_others():
    prices = _prices(MIN_ASSETS, months=30)
    prices["NEW"] = prices["A1"].iloc[10:] * 1.0  # nasce al mese 11, come XLC nel 2018
    s = scores(monthly_prices(prices))
    assert s["NEW"].iloc[:22].isna().all() and s["NEW"].iloc[22:].notna().all()  # 12 mesi dopo la nascita
    assert s["A0"].iloc[12:].notna().all()  # gli altri hanno la classifica anche prima


def test_complete_months_drops_month_in_progress():
    px = monthly_prices(_prices(MIN_ASSETS, months=3))  # gen, feb, mar 2020
    assert complete_months(px, pd.Timestamp("2020-03-15")).index[-1] == pd.Timestamp("2020-02-01")
    assert len(complete_months(px, pd.Timestamp("2020-04-01"))) == 3
    periods = px.set_axis(px.index.to_period("M"))  # rendimenti di scripts/backtest_assets.py
    assert complete_months(periods, pd.Timestamp("2020-03-15")).index[-1] == pd.Period("2020-02", "M")
