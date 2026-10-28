import pandas as pd

from src.classify import liquidity
from src.data import fetch_fred
from src.ui.cards import liquidity_html


def _obs(points: dict[str, float]) -> dict:
    return {"json": {"observations": [{"date": d, "value": str(v)} for d, v in points.items()]}}


def test_net_liquidity_is_assets_minus_treasury_minus_reverse_repo(requests_mock):
    weeks = {"2026-10-07": 0, "2026-10-14": 0}
    series = {
        "WALCL": {d: 6_700_000 for d in weeks},  # milioni
        "WTREGEN": {d: 900_000 for d in weeks},  # milioni
        "RRPONTSYD": {"2026-10-06": 50.0, "2026-10-13": 10.0, "2026-10-14": 5.0},  # miliardi, giornaliero
    }
    requests_mock.get(fetch_fred.BASE_URL, [_obs(series[s]) for s in ("WALCL", "WTREGEN", "RRPONTSYD")])
    net = fetch_fred.fetch_net_liquidity("k")
    assert net.to_dict() == {pd.Timestamp("2026-10-07"): 5750.0, pd.Timestamp("2026-10-14"): 5795.0}  # rrp del 6 e del 14


def test_factors_and_intensity():
    idx = pd.date_range("2025-01-01", periods=7, freq="MS")
    growth = pd.Series([3.0, 3.0, 3.0, 3.0, 2.5, 2.0, 1.8], idx)  # -1,2 punti in 3 mesi a luglio
    inflation = pd.Series(2.5, idx)
    liq = pd.Series([1.0, 1.0, 1.0, 1.0, 1.0, -0.5, -0.5], idx)
    real = pd.Series(0.5, idx)
    last = liquidity.factors(growth, inflation, liq, real).iloc[-1]
    assert last.to_dict() == {"PIL in calo forte": 1.0, "Inflazione sopra il 2%": 1.0, "Liquidità in calo": 1.0,
                              "Politica restrittiva": 0.0}
    assert liquidity.intensity("Stagflazione", 3) == "forte"
    assert liquidity.intensity("Deflazione", 2) == "media"
    assert liquidity.intensity("Deflazione", 1) == "debole"
    assert liquidity.intensity("Goldilocks", 4) is None  # il libro la da' solo per stagflazione e deflazione


def test_factors_carry_quarterly_gdp_forward():
    growth = pd.Series([3.0, 1.5], pd.to_datetime(["2026-01-01", "2026-04-01"]))
    monthly = pd.Series(2.5, pd.date_range("2026-01-01", periods=9, freq="MS"))
    f = liquidity.factors(growth, monthly, monthly, monthly)
    assert f.index[-1] == pd.Timestamp("2026-09-01") and f.iloc[-1].notna().all()


def test_policy_compares_dot_plot_and_december_futures():
    target = pd.Series([4.0], [pd.Timestamp("2026-10-27")])  # forchetta 3,75-4,00: meta' 3,875
    dots = pd.Series([3.875, 3.375], pd.to_datetime(["2026-01-01", "2027-01-01"]))
    curve = pd.Series([96.125, 96.875], pd.to_datetime(["2026-12-01", "2027-11-01"]))  # niente dicembre 2027
    p = liquidity.policy(target, dots, curve)
    assert [x["year"] for x in p] == [2026, 2027]
    assert p[0]["market"] == 3.875 and p[0]["fed_moves"] == 0
    assert p[1]["market"] is None and p[1]["fed_moves"] == -2


def test_rows_and_card():
    idx = pd.date_range("2024-01-01", periods=36, freq="MS")
    weekly = pd.date_range("2025-01-01", periods=40, freq="W-WED")
    d = {"net": pd.Series(range(6000, 5960, -1), weekly, dtype=float), "m2": pd.Series(4.0, idx),
         "target": pd.Series([4.0], [pd.Timestamp("2026-10-27")]),
         "dots": pd.Series([3.875, 3.375], pd.to_datetime(["2026-01-01", "2027-01-01"])),
         "curve": pd.Series([96.125, 96.375], pd.to_datetime(["2026-12-01", "2027-12-01"])),
         "fed_funds": pd.Series(3.0, idx), "growth": pd.Series(2.0, idx), "inflation": pd.Series(3.0, idx),
         "core": pd.Series(2.5, idx)}
    rows = liquidity.rows(d, "Stagflazione")
    names = [r["name"] for r in rows]
    assert names[0] == "Intensità del regime USA: Stagflazione" and rows[0]["state"] == "media"  # inflazione + liquidita'
    fed_2027 = next(r for r in rows if r["name"].startswith("Tassi Fed a fine 2027"))
    assert fed_2027["state"] == "mercato più rigido della Fed"  # 3,625% contro 3,375%
    html = liquidity_html(rows)
    assert "Liquidità e Fed" in html and "dot plot" in html
    assert liquidity.rows({k: pd.Series(dtype=float) for k in d}, None) == []
