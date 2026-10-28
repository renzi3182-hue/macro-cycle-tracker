import pandas as pd

from src.classify import monitor
from src.ui.cards import monitor_html


def _data(trend: float) -> dict[str, pd.Series]:
    """Tutte le serie del cruscotto: mensili salvo le trimestrali, in salita (trend > 0) o in calo."""
    out = {}
    for key, _, _, _, _, quarterly in monitor.ALL:
        idx = pd.date_range("2020-01-01", "2026-07-01", freq="QS" if quarterly else "MS")
        out[key] = pd.Series([100 + trend * i for i in range(len(idx))], idx, dtype=float)
    return out


def test_diffusion_counts_signed_series_with_publication_lag():
    up = monitor.diffusion(_data(1), pd.Timestamp("2026-10-28"))
    # salgono tutte: buone quelle col verso 1, cattive le due col verso -1 (richieste di sussidio, settimane, servizio del debito)
    signed = [s for s in monitor.ALL if s[3]]
    assert round(up.iloc[-1]) == round(100 * sum(s[3] > 0 for s in signed) / len(signed))
    assert up.index[-1] <= pd.Timestamp("2026-10-28") and pd.isna(up.get(pd.Timestamp("2020-01-01")))
    assert round(monitor.diffusion(_data(-1), pd.Timestamp("2026-10-28")).iloc[-1]) == round(
        100 * sum(s[3] < 0 for s in signed) / len(signed))


def test_change_and_rows_and_card():
    s = pd.Series([100.0, 102.0, 101.0, 104.0], pd.date_range("2026-01-01", periods=4, freq="MS"))
    assert monitor.change(s, "%", 1) == (104 / 101 - 1) * 100 and monitor.change(s, "pt", 3) == 4.0
    assert monitor.change(s, "pt", 12) is None
    groups = monitor.rows(_data(1))
    assert [g for g, _ in groups] == [g for g, _ in monitor.SERIES]
    claims = next(r for _, rows in groups for r in rows if r["name"].startswith("Richieste"))
    html = monitor_html(groups, pd.Series([40.0, 45.0, 50.0, 60.0], pd.date_range("2026-07-01", periods=4, freq="MS")))
    assert claims["sign"] == -1 and "Cruscotto USA" in html and "<b>60%</b>" in html and "Tre mesi prima era il 40%" in html
    assert monitor.rows({}) == []
