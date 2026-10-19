import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.classify.currency import cot_component, growth_gap, momentum_returns, pair_view, strength_score, vix_component


def test_strength_bounds_and_missing_components():
    assert strength_score(20, 20, 20)["score"] == 100
    assert strength_score(-20, -20, -20)["score"] == 1
    assert strength_score(0, 0, None)["score"] == 50  # crescita in media -> 50; tasso reale ha peso 0
    assert strength_score(10, None, None)["score"] is None  # solo tasso reale: nessuna componente pesata
    assert strength_score(None, None, None)["score"] is None


def test_pair_view():
    assert pair_view(80, 20) == {"score": 80, "label": "Buy"}
    assert pair_view(20, 80) == {"score": 20, "label": "Sell"}
    assert pair_view(50, 50)["label"] == "Neutra"


def test_momentum_centered():
    flat = pd.Series([1.0] * 70)
    rising = pd.Series([1.0] * 7 + [1.1] * 63)
    m = momentum_returns({"eurusd": rising, "gbpusd": flat, "usdjpy": rising, "usdinr": flat.head(10)}, days=63)
    assert abs(sum(m.values())) < 1e-9
    assert m["EUR"] > m["GBP"] == m["USD"] > m["JPY"]  # usdjpy in salita = yen piu' debole
    assert "INR" not in m  # serie troppo corta


def test_cot_and_vix_components():
    assert cot_component(95) == 5 and cot_component(None) is None
    assert vix_component("JPY", 100) == 100 and vix_component("GBP", 100) == 25
    assert vix_component("USD", None) is None
    assert strength_score(None, 0, None, cot=100, vix=0)["score"] == 23  # COT peso 0: (.25*50+.30*0)/.55 = 22.7
    assert strength_score(None, 0, None, cot=100, vix=0, cot_weight=0.25)["score"] == 47  # (.25*50+.25*100)/.80


def test_growth_gap_uses_last_10_years():
    idx = pd.date_range("2000-01-01", periods=80, freq="QS")  # 20 anni
    g = pd.Series([10.0] * 40 + [2.0] * 39 + [3.0], idx)
    assert growth_gap(g) == 3.0 - (2.0 * 39 + 3.0) / 40  # i primi 10 anni (10%) fuori dalla media
    assert growth_gap(g.head(5)) is None
