import pandas as pd
import pytest

from src.classify import macro_score as ms


def _series(values, start="2000-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="MS"), dtype=float)


def test_rolling_percentile_uses_only_the_past_window():
    s = _series(range(200))
    pct = ms.rolling_percentile(s)
    assert pct.index[0] == s.index[ms.MIN_MONTHS - 1]
    assert pct.iloc[-1] == 100  # massimo della finestra
    s2 = _series(list(range(150)) + [0])
    assert ms.rolling_percentile(s2).iloc[-1] == pytest.approx(100 / ms.WINDOW_MONTHS)  # minimo: solo se stesso


def test_short_history_gives_no_percentile():
    assert ms.rolling_percentile(_series(range(ms.MIN_MONTHS - 1))).empty


def test_area_score_needs_two_components_and_averages_them():
    up, down = _series(range(100)), _series(range(100, 0, -1))
    h = ms.area_history({"cli": up, "bci": down, "cci": pd.Series(dtype=float)})
    assert h["score"].iloc[-1] == pytest.approx((100 + h["bci"].iloc[-1]) / 2)
    assert ms.area_history({"cli": up}).empty


def test_economies_builds_emerging_and_global():
    data = {("Cina", "cli"): _series(range(100)), ("Allocazione", "Cina_bci"): _series(range(100)),
            ("India", "cli"): _series(range(100, 0, -1)), ("Allocazione", "India_bci"): _series(range(100, 0, -1))}
    read = lambda area, ind: data.get((area, ind), pd.Series(dtype=float))
    eco = ms.economies(["Cina", "India"], read)
    assert eco["Cina"]["history"].iloc[-1] == 100
    em, world = ms.summary(eco["Emergenti"]), ms.summary(eco["Globale"])
    assert em["score"] == round((100 + eco["India"]["history"].iloc[-1]) / 2) == world["score"]
    assert em["members"] == ["Cina", "India"] and len(em["history"]) <= 36


def test_heat_row_signals():
    idx = pd.date_range("2016-01-01", periods=40, freq="QS")
    data = {("X", "growth_yoy"): pd.Series([2.0] * 39 + [3.0], index=idx),
            ("X", "inflation_yoy"): _series([2.5]), ("X", "unemployment_rate"): _series([5.0] * 6 + [4.5])}
    read = lambda area, ind: data.get((area, ind), pd.Series(dtype=float))
    row = ms.heat_row("X", read, 30, {"positive": False, "dist_pct": -2.0, "month": "2026-10"})
    assert [row[k]["signal"] for k in ms.HEAT_COLUMNS] == [1, 1, -1, 1, -1]
    assert ms.heat_row("X", lambda a, i: pd.Series(dtype=float), None, None) == dict.fromkeys(ms.HEAT_COLUMNS)


def test_band():
    assert (ms.band(60), ms.band(59), ms.band(39)) == ("solido", "nella media", "debole")
