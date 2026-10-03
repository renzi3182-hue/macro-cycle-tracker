import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.classify.recession import recession_confirmed, recession_flags, sahm_gap


def _unrate(values):
    return pd.Series(values, index=pd.date_range("2023-01-01", periods=len(values), freq="MS"))


def _prob(v):
    return pd.Series([v], index=pd.to_datetime(["2024-01-01"]))


RISING = _unrate([3.5] * 13 + [3.6, 4.0, 4.4])  # media 3m ~0.5 sopra il minimo
FLAT = _unrate([3.5] * 16)


def test_sahm_gap():
    assert sahm_gap(FLAT).dropna().iloc[-1] == 0
    assert sahm_gap(RISING).dropna().iloc[-1] >= 0.5


def test_confirmation_rules():
    assert recession_confirmed(RISING, _prob(15.0))  # Sahm + CP >= 10
    assert not recession_confirmed(RISING, _prob(1.0))  # Sahm da solo non basta (falso allarme 2003/2024)
    assert recession_confirmed(FLAT, _prob(60.0))  # CP >= 50 basta da solo
    assert not recession_confirmed(FLAT, _prob(15.0))
    assert not recession_confirmed(pd.Series(dtype=float), _prob(90.0))  # dati mancanti = spento


def test_flags_without_probability_need_two_months_of_sahm():
    assert recession_flags(_unrate([3.5] * 13 + [3.6, 4.0, 4.4, 4.6])).iloc[-1]
    assert not recession_flags(_unrate([3.5] * 14 + [4.0, 4.6])).iloc[-1]  # un solo mese sopra soglia
    assert not recession_flags(FLAT).iloc[-1]
    assert recession_flags(pd.Series(dtype=float)).empty
