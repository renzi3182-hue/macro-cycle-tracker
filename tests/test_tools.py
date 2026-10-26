import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import cot_guide
from src.data.fetch_cot import CONTRACTS, DISAGG_GROUPS, TFF_GROUPS


def test_cot_guide_covers_every_market_and_group():
    assert set(CONTRACTS) <= set(cot_guide.MARKET_INFO)
    assert set(TFF_GROUPS) | set(DISAGG_GROUPS) <= set(cot_guide.GROUP_INFO)
    assert cot_guide.crowding(95)[0] == "Affollato long" and cot_guide.crowding(5)[0] == "Affollato short"
    assert "short squeeze" in cot_guide.implication("Oro", 5, -1)
