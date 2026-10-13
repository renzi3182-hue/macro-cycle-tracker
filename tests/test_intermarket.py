import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import pytest

from src.classify import intermarket as im


@pytest.mark.parametrize("bonds, stocks, commodities, phase", [
    (True, False, False, 1), (True, True, False, 2), (True, True, True, 3), (False, True, True, 4),
    (False, False, True, 5), (False, False, False, 6), (True, False, True, None), (False, True, False, None),
])
def test_murphy_phase_all_8_combinations(bonds, stocks, commodities, phase):
    assert im.murphy_phase(bonds, stocks, commodities) == phase


def test_murphy_history_uses_10_month_trend_and_marks_undefined():
    idx = pd.date_range("2020-01-01", periods=14, freq="MS")
    up, down = pd.Series(np.arange(100, 114.0), idx), pd.Series(np.arange(114, 100.0, -1), idx)
    px = pd.DataFrame({"TLT": up, "SPY": down, "DBC": down})
    h = im.murphy_history(px)
    assert h.index[0] == idx[9] and (h == 1).all()  # media a 10 mesi: primo valore al 10o mese
    assert (im.murphy_history(px.assign(DBC=up)) == 0).all()  # obbligazioni e materie prime su, azioni giu'
    assert im.phase_label(0) == im.UNDEFINED and im.phase_label(4) == "Fase 4"


def _daily(values, start="2024-01-01"):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)), dtype=float)


def test_rolling_corr_on_common_dates_and_rate_changes():
    rng = np.random.default_rng(0)
    r = rng.normal(0, 0.01, 200)
    price = _daily(100 * np.cumprod(1 + r))
    rate = _daily(4 + np.cumsum(r * 10))  # rendimento che sale quando il prezzo sale: variazioni in punti, non in %
    lv = im.levels({"SPY": price, "DGS10": rate.drop(rate.index[::7])})  # FRED senza alcuni giorni
    c = im.rolling_corr(lv, "SPY", "DGS10", 30)
    assert c.iloc[-1] > 0.95
    assert im.rolling_corr(lv.assign(DGS10=-lv["DGS10"]), "SPY", "DGS10", 30).iloc[-1] < -0.95


def test_levels_drop_non_positive_prices_and_add_copper_gold():
    lv = im.levels({"DCOILWTICO": _daily([20, -37, 15]), "HG=F": _daily([4, 4, 5]), "GLD": _daily([2, 2, 2]),
                    "DFII10": _daily([-0.5, -1, 0.2])})
    assert lv["DCOILWTICO"].isna().tolist() == [False, True, False]
    assert lv["DFII10"].notna().all()  # i tassi possono essere negativi
    assert lv[im.COPPER_GOLD].tolist() == [2, 2, 2.5]


@pytest.mark.parametrize("current, usual, broken", [
    (-0.3, 0.4, True),   # segno opposto a una norma con segno
    (-0.05, 0.1, False),  # norma ~0: il segno non conta, distanza 0,15
    (0.9, 0.3, True),    # stesso segno ma distanza oltre 0,5
    (0.5, 0.3, False),
    (float("nan"), 0.3, False),
])
def test_is_break(current, usual, broken):
    assert im.is_break(current, usual) is broken


def test_norm_is_median_of_last_5_years():
    c = pd.Series([0.9] * 10 + [0.1, 0.2, 0.3], index=pd.to_datetime(
        [f"{y}-01-01" for y in range(2010, 2020)] + ["2024-01-01", "2025-01-01", "2026-01-01"]))
    assert im.norm(c) == pytest.approx(0.2)


@pytest.mark.parametrize("current, usual, sign, state", [
    (-0.5, -0.4, -1, "regolare"), (0.2, -0.4, -1, "rotta"), (-0.1, -0.7, -1, "più debole del solito"),
    (-0.95, -0.3, -1, "regolare"),  # piu' forte del solito: non e' un indebolimento
])
def test_relation_state(current, usual, sign, state):
    assert im.relation_state(current, usual, sign) == state


def test_copper_gold_divergence_on_3_month_direction():
    idx = pd.date_range("2025-01-01", periods=8, freq="MS")
    ratio = pd.Series([1, 1, 1, 1, 0.9, 0.8, 0.7, 0.6], idx)
    rising, falling = pd.Series(np.arange(8.0), idx), pd.Series(-np.arange(8.0), idx)
    assert im.diverging(ratio, rising).iloc[-1]  # rame/oro giu', rendimento su: uno dei due "mente"
    assert not im.diverging(ratio, falling).iloc[-1]
    assert im.change(ratio).iloc[-1] == pytest.approx(-0.3)


@pytest.mark.parametrize("macro, phase, copper_up, state", [
    ("Espansione", 4, True, im.ALIGNED),
    ("Espansione", 4, False, im.PARTIAL),
    ("Espansione", 2, True, im.PARTIAL),      # Murphy parziale
    ("Espansione", 6, True, im.PARTIAL),      # Murphy contraria ma rame/oro d'accordo
    ("Espansione", 2, False, im.MISALIGNED),
    ("Recessione", 3, True, im.MISALIGNED),
    ("Recessione", 1, False, im.ALIGNED),
    ("Ripresa (sotto trend)", 0, True, im.PARTIAL),  # fase non definita
])
def test_alignment(macro, phase, copper_up, state):
    assert im.alignment(macro, phase, copper_up) == state


def test_every_macro_phase_maps_all_murphy_phases():
    for aligned, partial in im.MACRO_TO_MURPHY.values():
        assert len(aligned) == len(partial) == 2 and not aligned & partial


def _excess(n_months: int, values: dict[str, float]) -> pd.DataFrame:
    idx = pd.date_range("2000-01-01", periods=n_months, freq="MS")
    rng = np.random.default_rng(1)
    return pd.DataFrame({t: v + rng.normal(0, 0.02, n_months) for t, v in values.items()}, index=idx)


def test_edge_highlights_only_significant_positive_with_30_cases():
    ex = _excess(60, {"GLD": 0.03, "TLT": 0.001, "XLE": -0.03})
    table = im.edge_table(ex, ex.index)
    assert list(table.index) == ["GLD", "TLT", "XLE"]  # ordinato per extra-rendimento
    assert im.highlighted(table, ["GLD", "TLT", "XLE"]) == ["GLD"]  # TLT t ~0, XLE t molto negativo: no
    few = im.edge_table(ex, ex.index[:29])
    assert im.highlighted(few, ["GLD"]) == []  # 29 casi: nessun vantaggio
    assert im.highlighted(table, ["TLT", "XLE"]) == []


def test_double_risk_flags_correlated_pairs():
    rng = np.random.default_rng(2)
    r = rng.normal(0, 0.01, 200)
    lv = im.levels({"QQQ": _daily(100 * np.cumprod(1 + r)), "SMH": _daily(100 * np.cumprod(1 + r * 1.5)),
                    "TLT": _daily(100 * np.cumprod(1 + rng.normal(0, 0.01, 200)))})
    pairs = im.double_risk(lv, ["QQQ", "SMH", "TLT"])
    assert [(a, b) for a, b, _ in pairs] == [("QQQ", "SMH")]


def test_same_situation_needs_both_regime_and_phase():
    idx = pd.date_range("2020-01-01", periods=4, freq="MS")
    regime = pd.Series(["Stagflazione", "Stagflazione", "Goldilocks", "Stagflazione"], idx)
    murphy = pd.Series([3, 4, 4], idx[1:])  # Murphy parte un mese dopo
    assert list(im.same_situation(regime, murphy, "Stagflazione", 4)) == [idx[3]]
