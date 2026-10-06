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
