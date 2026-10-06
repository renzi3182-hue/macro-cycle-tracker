import pandas as pd

from src.classify.rrg import quadrant, rrg
from src.classify.stress import monte_carlo, portfolio_returns, scenario, ticker_weights


def _px(**cols):
    idx = pd.date_range("2007-09-01", periods=len(next(iter(cols.values()))), freq="MS")
    return pd.DataFrame(cols, index=idx, dtype=float)


def test_ticker_weights_map_classes_and_skip_unmapped():
    tw, skipped = ticker_weights({"Azionario": 30, "Azionario growth": 30, "Cash": 20, "Credito corporate": 20})
    assert tw == {"SPY": 0.75, "SHY": 0.25} and skipped == ["Credito corporate"]


def test_scenario_return_drawdown_and_missing_data():
    px = _px(SPY=[100, 100, 90, 81, 90], SHY=[100] * 5)
    r = portfolio_returns({"SPY": 0.5, "SHY": 0.5}, px)
    ret, dd = scenario(r, "2007-11", "2008-01")
    assert round(ret, 4) == round(0.95 * 0.95 * (1 + 0.5 * (90 / 81 - 1)) - 1, 4) and dd < ret
    assert scenario(r, "2007-08", "2007-12") is None  # mese prima dei dati


def test_monte_carlo_is_ordered_and_needs_history():
    r = pd.Series([0.01, -0.02, 0.03] * 30)
    mc = monte_carlo(r)
    assert mc[5] < mc[50] < mc[95]
    assert monte_carlo(r.head(10)) is None


def test_rrg_quadrants():
    up, flat = [100 * 1.002 ** (i * i) for i in range(20)], [100.0] * 20  # crescita che accelera
    ratio, mom = rrg(_px(SPY=flat, XLK=up, XLU=[1e4 / x for x in up]))
    assert quadrant(ratio["XLK"].iloc[-1], mom["XLK"].iloc[-1]) == "Guida"
    assert quadrant(ratio["XLU"].iloc[-1], mom["XLU"].iloc[-1]) == "Arretra"
