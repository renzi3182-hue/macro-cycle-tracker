import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from scripts.backtest_pac import irr, simulate, summary
from src.classify.risk import canary_level

IDX = pd.date_range("2020-01-01", periods=4, freq="MS")


def test_dynamic_pac_keeps_the_same_budget_and_spends_the_reserve_in_risk_off():
    price = pd.Series([10.0, 5.0, 10.0, 10.0], index=IDX)
    off = pd.Series([False, True, False, False], index=IDX)
    rate = pd.Series(0.0, index=IDX)
    const, dyn = simulate(price, rate, off, 150, 150, 150), simulate(price, rate, off, 150, 100, 250)
    assert const["versato"].iloc[-1] == dyn["versato"].iloc[-1] == 600  # stesso budget
    assert dyn["investito"].tolist() == [100, 200, 100, 100]  # in risk off solo la cassa che c'e' (50 + 150 in entrata)
    assert dyn["cassa"].iloc[-1] == 100 and const["cassa"].iloc[-1] == 0
    assert dyn["valore"].iloc[-1] == 70 * 10 + 100 and const["valore"].iloc[-1] == 75 * 10  # quote x prezzo + cassa
    s = summary(dyn, 150)
    assert round(s["prezzo_medio"], 4) == round(500 / 70, 4) and s["mesi_extra"] == 1  # comprato di piu' a 5


def test_cash_earns_the_short_rate_and_irr_is_annual():
    price = pd.Series(10.0, index=IDX[:2])
    out = simulate(price, pd.Series(12.0, index=IDX[:2]), pd.Series(False, index=IDX[:2]), 100, 0, 0)
    assert round(out["cassa"].iloc[-1], 6) == 201.0  # 100 dopo un mese all'1% + 100
    assert abs(irr([-100] * 12 + [0] * 0) - irr([-100] * 12)) < 1e-9 and round(irr([-100, 101]), 1) == 12.7


def test_canary_level_counts_positive_momentum():
    mom = pd.DataFrame({"a": [0.1, -0.1, 0.1], "b": [0.1, -0.1, None], "c": [0.1, 0.1, 0.1]})
    assert canary_level(mom).tolist()[:2] == [3.0, 1.0] and pd.isna(canary_level(mom).iloc[2])
