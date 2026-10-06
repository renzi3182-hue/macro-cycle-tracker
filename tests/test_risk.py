import pandas as pd

from src.classify.risk import MIN_HISTORY_MONTHS, breadth, expanding_percentile, label, risk_score


def test_expanding_percentile_ignores_future_values():
    s = pd.Series(range(MIN_HISTORY_MONTHS + 5), dtype=float)
    pct = expanding_percentile(s)
    assert pct.iloc[: MIN_HISTORY_MONTHS - 1].isna().all()
    assert pct.iloc[-1] == 100  # sempre il massimo finora
    later = pd.concat([s, pd.Series([1e9])], ignore_index=True)
    assert expanding_percentile(later).iloc[-2] == pct.iloc[-1]


def test_breadth_counts_assets_above_average():
    idx = pd.date_range("2020-01-01", periods=12, freq="MS")
    up, down = pd.Series(range(1, 13), index=idx, dtype=float), pd.Series(range(12, 0, -1), index=idx, dtype=float)
    px = pd.DataFrame({f"u{i}": up for i in range(6)} | {f"d{i}": down for i in range(2)})
    assert breadth(px).iloc[-1] == 75
    assert pd.isna(breadth(px.iloc[:, :7]).iloc[-1])  # meno di 8 asset


def test_score_needs_all_components_and_labels():
    comp = pd.DataFrame({"VIX": [90, None], "Credito": [80, 50], "Ampiezza": [70, 50]})
    s = risk_score(comp)
    assert s.iloc[0] == 80 and pd.isna(s.iloc[1])
    assert label(0) == "Risk Off estremo" and label(50) == "Neutrale" and label(100) == "Risk On estremo"
