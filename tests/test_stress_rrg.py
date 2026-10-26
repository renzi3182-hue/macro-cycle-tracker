import pandas as pd

from src.classify.rrg import GROUPS, quadrant, rrg, weekly_prices
from src.classify.stress import monte_carlo, portfolio_returns, recovery, scenario, summary, ticker_weights, trend_returns


def _px(**cols):
    idx = pd.date_range("2007-09-01", periods=len(next(iter(cols.values()))), freq="MS")
    return pd.DataFrame(cols, index=idx, dtype=float)


def test_ticker_weights_map_classes_and_skip_unmapped():
    tw, skipped = ticker_weights({"Azionario": 30, "Azionario growth": 30, "Cash": 20, "Credito corporate": 10, "Immobiliare": 10})
    assert tw == {"SPY": 1 / 3, "IWF": 1 / 3, "BIL": 2 / 9, "LQD": 1 / 9} and skipped == ["Immobiliare"]


def test_scenario_return_drawdown_and_missing_data():
    px = _px(SPY=[100, 100, 90, 81, 90], SHY=[100] * 5)
    r = portfolio_returns({"SPY": 0.5, "SHY": 0.5}, px)
    ret, dd = scenario(r, "2007-11", "2008-01")
    assert round(ret, 4) == round(0.95 * 0.95 * (1 + 0.5 * (90 / 81 - 1)) - 1, 4) and dd < ret
    assert scenario(r, "2007-08", "2007-12") is None  # mese prima dei dati


def test_trend_returns_move_to_cash_below_average():
    spy = [100.0 + i for i in range(12)] + [80.0, 70.0, 75.0]  # crolla dopo 12 mesi di salita
    px = _px(SPY=spy, BIL=[100 * 1.001 ** i for i in range(15)])
    rt, r = trend_returns({"SPY": 1.0}, px), portfolio_returns({"SPY": 1.0}, px)
    assert rt.iloc[:10].isna().all()  # media a 10 mesi non ancora disponibile il mese prima
    assert rt.iloc[12] == r.iloc[12]  # a fine mese 11 era sopra la media: il crollo si prende
    assert round(rt.iloc[13], 6) == round(rt.iloc[14], 6) == 0.001  # poi in cash (BIL)


def test_summary_and_recovery():
    r = pd.Series([0.1, -0.5, 0.5, 0.4] + [0.0] * 20, index=pd.date_range("2000-01-01", periods=24, freq="MS"))
    s = summary(r)
    assert round(s["dd"], 2) == -0.5 and s["under"] == 2 and s["start"] == r.index[0] and round(s["final"], 3) == 1.155
    assert recovery(r, "2000-02", "2000-02") == 3  # 0.5 * 1.5 * 1.4 = 1.05 al terzo mese
    assert recovery(r, "2000-03", "2000-04") == 0 and recovery(r.iloc[:3], "2000-02", "2000-02") is None
    assert recovery(pd.concat([r.iloc[:4], pd.Series([-0.9], index=[r.index[4]])]), "2000-03", "2000-04") == 0  # crollo dopo la crisi
    assert summary(r.head(12)) is None


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


def test_weekly_rrg_groups_exclude_benchmark():
    assert "SPY" not in GROUPS["Paesi"] and GROUPS["Materie prime"] == ["GLD", "DBC"]
    days = pd.bdate_range("2026-01-05", periods=10)
    wk = weekly_prices(pd.DataFrame({"SPY": range(10)}, index=days, dtype=float))
    assert list(wk["SPY"]) == [4.0, 9.0]  # ultima chiusura di ogni settimana


def test_eur_returns_add_the_exchange_rate_move():
    from src.classify.stress import eur_returns
    idx = pd.date_range("2020-01-01", periods=4, freq="MS")
    r = pd.Series([0.0, 0.0, 0.10, 0.10], index=idx)
    usd_per_eur = pd.Series([1.00, 1.25, 1.25, 1.00], index=idx)  # il dollaro si indebolisce, poi si rafforza
    out = eur_returns(r, usd_per_eur)
    assert pd.isna(out.iloc[0])  # nessun cambio del mese prima
    assert round(out.iloc[1], 6) == -0.2  # fermo in dollari, -20% in euro: un euro compra piu' dollari
    assert round(out.iloc[2], 6) == 0.10  # cambio fermo: stesso rendimento
    assert round(out.iloc[3], 6) == round(1.10 * 1.25 - 1, 6)  # dollaro piu' forte: guadagno in piu'
    assert eur_returns(r, usd_per_eur.iloc[:2]).iloc[2:].isna().all()  # senza cambio niente rendimento in euro


def test_common_window_keeps_only_the_last_unbroken_stretch():
    from src.classify.stress import common_window
    idx = pd.date_range("2020-01-01", periods=6, freq="MS")
    r = pd.Series([0.1, 0.1, 0.1, 0.1, 0.1, 0.1], index=idx)
    rt = pd.Series([0.1, None, 0.1, 0.1, 0.1, None], index=idx)  # buco a febbraio, ultimo mese mancante
    assert list(common_window(r, rt)) == list(idx[2:5])
    assert len(common_window(r, pd.Series(None, index=idx, dtype=float))) == 0
