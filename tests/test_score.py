import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src.classify.score import (
    MIN_ASSETS, MIN_TRAIN_MONTHS, complete_months, extended_prices, hysteresis, model, monthly_prices, scores,
)


def _prices(n_assets: int, months: int = 24) -> dict[str, pd.Series]:
    """Asset i cresce dell'i% al mese: piu' alto i, piu' forti tendenza e momentum."""
    idx = pd.date_range("2020-01-31", periods=months, freq="ME")
    return {f"A{i}": pd.Series([1.01 ** (i * k) for k in range(months)], index=idx) for i in range(n_assets)}


def _noisy(n_assets: int = MIN_ASSETS + 2, months: int = MIN_TRAIN_MONTHS + 60) -> pd.DataFrame:
    """Rendimenti con deriva diversa per asset e rumore: chi sale di piu' continua a salire di piu'."""
    rng = np.random.default_rng(0)
    idx = pd.date_range("2000-01-01", periods=months, freq="MS")
    r = rng.normal(0, 0.03, (months, n_assets)) + np.linspace(-0.01, 0.01, n_assets)
    return pd.DataFrame((1 + r).cumprod(axis=0), index=idx, columns=[f"A{i}" for i in range(n_assets)])


def test_model_learns_trend_and_ranks_strongest_asset_high():
    m = model(_noisy())
    last = m["score"].iloc[-1]
    assert last["A9"] > 80 and last["A0"] < 30 and last.max() == 100 and last.min() >= 1
    w = m["weights"].iloc[-1]
    assert w["Tendenza"] + w["Momentum"] > 0 and (w.drop("Costante") >= 0).all()  # pesi solo positivi
    assert ((m["prob"] > 0) & (m["prob"] < 1)).sum().sum() == m["prob"].notna().sum().sum()


def test_score_uses_only_the_past():
    px = _noisy()
    k = len(px) - 7
    full, cut = scores(px), scores(px.iloc[:k])
    pd.testing.assert_series_equal(full.iloc[k - 1], cut.iloc[-1])


def test_no_score_without_training_history_or_min_assets():
    s = scores(monthly_prices(_prices(MIN_ASSETS + 2)))
    assert s.isna().all().all()  # 24 mesi: meno di MIN_TRAIN_MONTHS di esiti noti
    assert scores(_noisy(MIN_ASSETS - 1)).isna().all().all()


def test_extended_prices_use_proxy_before_first_etf_price():
    px = _noisy(2, 6)
    px.iloc[:3, 0] = np.nan  # A0 nasce al quarto mese
    proxies = pd.DataFrame({"A0": [0.10, 0.10, 0.10, 0.10, 0.0, 0.0]}, index=px.index)
    ext = extended_prices(px, proxies)
    assert ext["A0"].notna().all()
    assert np.isclose(ext["A0"].iloc[2] / ext["A0"].iloc[1], 1.10)  # rendimento del proxy prima dell'ETF
    assert np.isclose(ext["A0"].iloc[5] / ext["A0"].iloc[4], px["A0"].iloc[5] / px["A0"].iloc[4])  # dopo, l'ETF
    assert ext["A1"].equals(ext["A1"]) and np.isclose(ext["A1"].iloc[5] / ext["A1"].iloc[0], px["A1"].iloc[5] / px["A1"].iloc[0])


def test_hysteresis_enters_above_80_exits_below_60():
    s = pd.DataFrame({"A": [70, 85, 65, 59, 75]})
    assert hysteresis(s)["A"].tolist() == [False, True, True, False, False]


def test_complete_months_drops_month_in_progress():
    px = monthly_prices(_prices(MIN_ASSETS, months=3))  # gen, feb, mar 2020
    assert complete_months(px, pd.Timestamp("2020-03-15")).index[-1] == pd.Timestamp("2020-02-01")
    assert len(complete_months(px, pd.Timestamp("2020-04-01"))) == 3
    periods = px.set_axis(px.index.to_period("M"))  # rendimenti di scripts/backtest_assets.py
    assert complete_months(periods, pd.Timestamp("2020-03-15")).index[-1] == pd.Period("2020-02", "M")
