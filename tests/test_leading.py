import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.classify.leading import leading_risk


def _s(v):
    return pd.Series([v], index=pd.to_datetime(["2024-01-01"]))


def _usa(curve, spread, fin):
    return leading_risk("USA", {"yield_curve": _s(curve), "credit_spread": _s(spread), "fin_conditions": _s(fin)})


def test_leading_risk_levels():
    assert _usa(1.0, 2.0, -0.5)["level"] == "Basso"
    assert _usa(-0.5, 2.0, -0.5)["level"] == "Medio"
    assert _usa(-0.5, 3.0, -0.5)["level"] == "Alto"


def test_leading_risk_missing_series_are_off():
    assert leading_risk("USA", {"yield_curve": pd.Series(dtype=float)})["level"] == "Basso"
    assert leading_risk("Marte", {}) is None


def test_non_usa_signals():
    months = pd.date_range("2024-01-01", periods=5, freq="MS")
    cli_falling = pd.Series([100.5, 100.2, 99.9, 99.6, 99.3], index=months)  # sotto 100 e sotto 3 mesi prima
    tankan_falling = pd.Series([12.0, 10.0, 8.0], index=pd.date_range("2024-01-01", periods=3, freq="QS"))
    risk = leading_risk("Giappone", {"cli": cli_falling, "tankan": tankan_falling, "yield_curve": _s(0.8)})
    assert risk["level"] == "Alto" and risk["score"] == 2 and risk["total"] == 3
    # CLI sotto 100 ma in risalita: nessun segnale
    assert leading_risk("UK", {"cli": pd.Series([98.0, 98.5, 99.0, 99.5], index=months[:4])})["level"] == "Basso"
