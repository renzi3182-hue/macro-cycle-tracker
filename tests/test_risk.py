import pandas as pd

from src.classify.risk import MIN_HISTORY_DAYS, TREND_DAYS, breadth, canary, components, expanding_percentile, label, risk_score


def test_expanding_percentile_ignores_future_values():
    s = pd.Series(range(MIN_HISTORY_DAYS + 5), dtype=float)
    pct = expanding_percentile(s)
    assert pct.iloc[: MIN_HISTORY_DAYS - 1].isna().all()
    assert pct.iloc[-1] == 100  # sempre il massimo finora
    later = pd.concat([s, pd.Series([1e9])], ignore_index=True)
    assert expanding_percentile(later).iloc[-2] == pct.iloc[-1]


def test_breadth_counts_assets_above_average():
    n = TREND_DAYS + 5
    up, down = pd.Series(range(1, n + 1), dtype=float), pd.Series(range(n, 0, -1), dtype=float)
    px = pd.DataFrame({f"u{i}": up for i in range(6)} | {f"d{i}": down for i in range(2)})
    assert breadth(px).iloc[-1] == 75
    assert pd.isna(breadth(px.iloc[:, :7]).iloc[-1])  # meno di 8 asset


def test_components_fill_calendar_gaps_and_need_history():
    days = pd.bdate_range("2000-01-03", periods=MIN_HISTORY_DAYS + TREND_DAYS + 10)  # consumi: media a 200 sedute, poi 5 anni di storia
    rising = pd.Series(range(len(days)), index=days, dtype=float) + 1
    px = pd.DataFrame({f"e{i}": rising for i in range(8)})
    vix = rising.drop(days[-1])  # FRED un giorno indietro rispetto a Yahoo
    flat = pd.Series(1.0, index=days)
    comp = components(vix, vix * 2, rising, flat.where(flat.index < days[-1], 2.0), flat, px)  # XLY balza l'ultimo giorno
    last = comp.iloc[-1]
    assert last["VIX"] == 0 and last["Credito"] == 0  # massimi storici = nessuna calma
    assert last["Ampiezza"] == 100 and last["Consumi"] == 100
    assert pd.isna(risk_score(comp).iloc[MIN_HISTORY_DAYS - 2])


def test_score_needs_all_components_and_labels():
    comp = pd.DataFrame({"VIX": [90, None], "Credito": [80, 50], "Ampiezza": [70, 50]})
    s = risk_score(comp)
    assert s.iloc[0] == 80 and pd.isna(s.iloc[1])
    assert label(0) == "Risk Off estremo" and label(50) == "Neutrale" and label(100) == "Risk On estremo"


def test_canary_weights_recent_months_more():
    tip = pd.Series([100.0] * 300)
    tip.iloc[-21:] = 98.0  # solo l'ultimo mese in calo del 2%
    assert canary(tip).iloc[-1] < 0
    assert pd.isna(canary(tip).iloc[250])  # serve un anno di storia
