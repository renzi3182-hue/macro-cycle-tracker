import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pytest

from src.classify import interest, sizing
from src.config import cot_guide
from src.data.fetch_cot import CONTRACTS, DISAGG_GROUPS, TFF_GROUPS


def test_equity_path_win_and_loss():
    wins = np.array([[True, False]])
    p = sizing.equity_paths(wins, 0.01, 2.0)
    assert p[0].tolist() == pytest.approx([1.0, 1.02, 1.02 * 0.99])
    assert sizing.max_drawdown(p)[0] == pytest.approx(0.01)


def test_streak_kelly_expectancy():
    wins = np.array([[False, False, True, False, False, False]])
    assert sizing.longest_losing_streak(wins).tolist() == [3]
    assert sizing.kelly(0.5, 2.0) == pytest.approx(0.25)
    assert sizing.expectancy(0.4, 2.0) == pytest.approx(0.2)


def test_more_risk_means_deeper_drawdown_on_same_draws():
    t = sizing.risk_table(sizing.outcomes(0.5, 100, 500), 1.5, 0.3)
    assert t["Drawdown mediano"].is_monotonic_increasing
    assert t["Prob. rovina"].iloc[0] <= t["Prob. rovina"].iloc[-1]


def test_simple_and_compound_interest():
    df = interest.schedule(1000, 0, 10, 2, per_year=1)
    assert df.loc[2, "Semplice"] == pytest.approx(1200)
    assert df.loc[2, "Composto"] == pytest.approx(1210)


def test_contributions_tax_and_inflation():
    df = interest.schedule(0, 100, 0, 1, inflation_pct=10, tax_pct=26)
    assert df.loc[1, "Versato"] == pytest.approx(1200) and df.loc[1, "Composto"] == pytest.approx(1200)
    assert df.loc[1, "Composto netto reale"] == pytest.approx(1200 / 1.1)
    taxed = interest.schedule(1000, 0, 10, 1, per_year=1, tax_pct=26)
    assert taxed.loc[1, "Composto netto"] == pytest.approx(1074)
    assert interest.years_to_double(7.0) == pytest.approx(10.24, abs=0.01)


def test_cot_guide_covers_every_market_and_group():
    assert set(CONTRACTS) <= set(cot_guide.MARKET_INFO)
    assert set(TFF_GROUPS) | set(DISAGG_GROUPS) <= set(cot_guide.GROUP_INFO)
    assert cot_guide.crowding(95)[0] == "Affollato long" and cot_guide.crowding(5)[0] == "Affollato short"
    assert "short squeeze" in cot_guide.implication("Oro", 5, -1)
