import pandas as pd
import pytest

from src.classify.advice_refs import EQUITY_WORLD, LABELS, equity_world, rate_returns, references

IDX = pd.date_range("2020-01-01", periods=4, freq="MS")


def test_rate_returns_coupon_minus_duration_times_change():
    r = rate_returns(pd.Series([2.0, 3.0, 3.0], index=IDX[:3]), 6.0)
    assert pd.isna(r.iloc[0])
    assert r.iloc[1] == pytest.approx(0.02 / 12 - 6 * 0.01)
    assert r.iloc[2] == pytest.approx(0.03 / 12)


def test_equity_world_weights_in_euro_and_needs_every_etf():
    px = pd.DataFrame({"SPY": [100, 110, 110, 110], "VEA": [100, 100, 100, 100], "EEM": [100, 100, None, 100]}, index=IDX)
    fx = pd.Series([1.0, 1.1, 1.1, 1.1], index=IDX)  # euro piu' forte: il guadagno in dollari vale meno in euro
    r = equity_world(px, fx)
    spy, vea = 1.1 / 1.1 - 1, 1 / 1.1 - 1
    assert r.iloc[1] == pytest.approx(EQUITY_WORLD["SPY"] * spy + (EQUITY_WORLD["VEA"] + EQUITY_WORLD["EEM"]) * vea)
    assert r.iloc[2:].isna().all()  # EEM manca a marzo: niente rendimento a marzo e ad aprile


def test_references_align_to_index_and_take_month_end_rates():
    px = pd.DataFrame({t: [100.0] * 4 for t in EQUITY_WORLD}, index=IDX)
    fx = pd.Series(1.0, index=IDX)
    daily = pd.Series([1.0, 9.0, 2.0], index=pd.to_datetime(["2020-01-01", "2020-02-03", "2020-02-28"]))
    out = references(IDX, px, fx, daily, daily)
    assert list(out) == list(LABELS)
    assert all(s.index.equals(IDX) for s in out.values())
    assert out["Liquidità area euro"].iloc[1] == pytest.approx(0.01 / 12 - 0.5 * 0.01)
    assert out["Azioni mondo"].iloc[1] == 0
