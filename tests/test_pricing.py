import re

import numpy as np
import pandas as pd

from src.classify import pricing
from src.data import fetch_market
from src.ui.cards import pricing_html


def _yahoo(ts: pd.Timestamp, close: float) -> dict:
    return {"json": {"chart": {"result": [{"timestamp": [int(ts.timestamp())], "indicators": {"quote": [{"close": [close]}]}}]}}}


def test_curve_slope_and_fed_path():
    idx = pd.date_range("2026-11-01", periods=13, freq="MS")
    oil = pd.Series(np.linspace(100, 88, 13), index=idx)  # -12% in 12 mesi: backwardation
    assert round(fetch_market.curve_slope(oil), 1) == -12.0
    zq = pd.Series(np.linspace(96, 96.5, 13), index=idx)  # prezzo su = tasso giu' di 0,5 punti
    assert round(fetch_market.fed_path(zq), 2) == -0.5
    assert fetch_market.curve_slope(oil.iloc[:3]) is None  # contratto lontano a meno di 6 mesi


def test_fetch_futures_curve_skips_missing_and_stale(requests_mock):
    today = pd.Timestamp("2026-10-28")
    url = lambda sym: fetch_market.YAHOO_URL.format(symbol=sym)
    requests_mock.get(re.compile(r"https://query1\.finance\.yahoo\.com/.*"), status_code=404)
    requests_mock.get(url("CLV26.NYM"), **_yahoo(pd.Timestamp("2026-09-20"), 70.0))  # scaduto: prezzo vecchio
    requests_mock.get(url("CLX26.NYM"), **_yahoo(today, 101.0))
    requests_mock.get(url("CLX27.NYM"), **_yahoo(today, 82.0))
    curve = fetch_market.fetch_futures_curve("CL", "NYM", today)
    assert curve.to_dict() == {pd.Timestamp("2026-11-01"): 101.0, pd.Timestamp("2027-11-01"): 82.0}


def test_fetch_put_call_appends_missing_days_and_skips_403(requests_mock, monkeypatch):
    monkeypatch.setattr(fetch_market.pd.Timestamp, "today", classmethod(lambda cls: pd.Timestamp("2026-10-28")))
    cached = pd.Series([0.6], index=[pd.Timestamp("2026-10-23")])
    url = lambda d: fetch_market.PUT_CALL_DAILY_URL.format(date=d)
    body = lambda v: {"json": {"ratios": [{"name": "TOTAL PUT/CALL RATIO", "value": "1.0"},
                                          {"name": "EQUITY PUT/CALL RATIO", "value": v}]}}
    requests_mock.get(url("2026-10-26"), **body("0.55"))
    requests_mock.get(url("2026-10-27"), **body("0.65"))
    requests_mock.get(url("2026-10-28"), status_code=403)  # seduta non ancora pubblicata
    s = fetch_market.fetch_put_call(cached)
    assert s.to_dict() == {pd.Timestamp("2026-10-23"): 0.6, pd.Timestamp("2026-10-26"): 0.55, pd.Timestamp("2026-10-27"): 0.65}


def test_alarms_are_point_in_time_and_nan_without_history():
    days = pd.bdate_range("2000-01-03", periods=1400)
    up = pd.Series(np.arange(1400.0), index=days)  # sempre al massimo storico: in allarme appena c'e' il percentile
    d = {"credit": up, "skew": up, "put_call": up, "curve": pd.Series(-0.1, index=days),
         "vix": pd.Series(20.0, index=days), "vix3m": pd.Series(22.0, index=days)}
    al = pricing.alarms(d)
    assert al["Credito"].iloc[:1259].isna().all() and al["Credito"].iloc[-1] == 1
    assert al["Curva"].iloc[0] == 1 and al["Struttura VIX"].iloc[-1] == 0


def test_rows_and_card_skip_missing_series():
    days = pd.bdate_range("2026-01-01", periods=100)
    empty = pd.Series(dtype=float)
    d = {k: empty for k in ("credit", "vix", "vix3m", "move", "skew", "put_call", "breakeven", "dollar", "copper", "gold",
                            "fut_petrolio", "fut_rame", "fut_oro", "fut_fed_funds")}
    d.update(curve=pd.Series(-0.2, index=days), fut_fed_funds=pd.Series([-0.5], index=[days[-1]]),
             curves={"petrolio": empty, "rame": empty, "oro": empty, "fed_funds": empty})
    rows = pricing.rows(d)
    assert [r["key"] for r in rows] == ["curve", "fed"]
    assert rows[0]["state"] == "invertita" and rows[1]["state"] == "tagli" and "2,0 mosse" in rows[1]["note"]
    html = pricing_html(rows)
    assert "Cosa prezza il mercato" in html and "invertita" in html and "−0,20 pt" in html
