import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from src.config.asset_allocation import combined_portfolio_weights, portfolio_weights


@pytest.mark.parametrize("risk_profile", ["Basso", "Medio", "Alto"])
def test_portfolio_weights_sum_to_100(risk_profile):
    weights = portfolio_weights("Espansione", risk_profile)
    assert sum(weights.values()) == pytest.approx(100.0)


def test_higher_risk_profile_increases_equity_share():
    low = portfolio_weights("Espansione", "Basso")
    high = portfolio_weights("Espansione", "Alto")
    assert low["Azionario"] < high["Azionario"]


def test_combined_portfolio_weights_averages_areas():
    combined = combined_portfolio_weights(
        {"USA": "Espansione", "Italia": "Deflazione"}, "Medio"
    )
    assert sum(combined.values()) == pytest.approx(100.0)
