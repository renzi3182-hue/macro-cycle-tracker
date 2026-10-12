import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from src.config.asset_allocation import combined_portfolio_weights, portfolio_weights


@pytest.mark.parametrize("risk_profile", ["Basso", "Medio", "Alto"])
def test_portfolio_weights_sum_to_100(risk_profile):
    weights = portfolio_weights("Reflazione", risk_profile)
    assert sum(weights.values()) == pytest.approx(100.0)


def test_higher_risk_profile_increases_equity_share():
    low = portfolio_weights("Reflazione", "Basso")
    high = portfolio_weights("Reflazione", "Alto")
    assert low["Azionario"] < high["Azionario"]


def test_combined_portfolio_weights_averages_areas():
    combined = combined_portfolio_weights(
        {"USA": "Reflazione", "Italia": "Deflazione"}, "Medio"
    )
    assert sum(combined.values()) == pytest.approx(100.0)


def test_apply_trend_moves_assets_below_average_to_cash():
    from src.config.asset_allocation import apply_trend
    out = apply_trend({"Azionario": 50.0, "Oro": 30.0, "Cash": 10.0, "Credito corporate": 10.0}, {"SPY": False, "GLD": True})
    assert out == {"Cash": 60.0, "Oro": 30.0, "Credito corporate": 10.0}


def test_uncertain_area_takes_half_of_each_regime():
    half = combined_portfolio_weights({"India": "Incerto: Reflazione / Stagflazione"}, "Medio")
    both = combined_portfolio_weights({"A": "Reflazione", "B": "Stagflazione"}, "Medio")
    assert half == pytest.approx(both)
    assert sum(half.values()) == pytest.approx(100.0)


def test_confirmation_uses_country_equity_and_skips_assets_without_etf():
    from src.config.asset_allocation import confirmation
    above = {"EZU": True, "GLD": False, "DBC": True, "TIP": True, "SPY": False}
    assert confirmation("Reflazione", above, "EZU") == [
        ("Azionario", "EZU", True), ("Oro", "GLD", False), ("Materie prime", "DBC", True),
        ("Obbligazioni indicizzate all'inflazione", "TIP", True)]
    assert [t for _, t, _ in confirmation("Reflazione", above, None)] == ["GLD", "DBC", "TIP"]  # paese senza ETF azionario
    assert confirmation("Goldilocks", {}, "SPY") == []
