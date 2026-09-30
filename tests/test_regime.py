import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

from src.classify.regime import (
    FLAT_BAND_ENTER,
    axis_states,
    axis_z,
    classify_regime,
    pick_inputs,
    regime_history,
)


def _series(values, freq="QE"):
    return pd.Series(values, index=pd.date_range("2024-01-01", periods=len(values), freq=freq))


@pytest.mark.parametrize(
    "growth_vals,inflation_vals,expected",
    [
        ([1.0, 1.0, 1.0, 2.0], [3.0, 3.0, 3.0, 1.0], "Goldilocks"),
        ([1.0, 1.0, 1.0, 2.0], [1.0, 1.0, 1.0, 3.0], "Reflazione"),
        ([2.0, 2.0, 2.0, 1.0], [1.0, 1.0, 1.0, 3.0], "Stagflazione"),
        ([2.0, 2.0, 2.0, 1.0], [3.0, 3.0, 3.0, 1.0], "Deflazione"),
        # un asse laterale: nessun quadrante netto
        ([1.0, 1.0, 1.0, 1.0], [1.0, 1.0, 1.0, 3.0], "Transizione"),
        ([1.0, 1.0, 1.0, 2.0], [3.0, 3.0, 3.0, 3.0], "Transizione"),
    ],
)
def test_classify_regime(growth_vals, inflation_vals, expected):
    assert classify_regime(_series(growth_vals), _series(inflation_vals)) == expected


def test_classify_regime_needs_enough_data():
    with pytest.raises(ValueError):
        classify_regime(_series([1.0, 2.0]), _series([1.0, 2.0, 3.0, 4.0]))


def test_small_steady_rise_is_detected_on_a_quiet_series():
    # Regressione Eurozona 2026: l'inflazione oscilla di +-0.1 per anni, poi sale da 2.0 a 3.2.
    # Una soglia fissa (1.4) non scattava mai e teneva "giu'" da otto trimestri; la banda e' relativa alla serie.
    inflation = _series([2.0, 2.1, 1.9, 2.0] * 5 + [2.4, 2.8, 3.2])
    assert axis_states(axis_z(inflation)).iloc[-1] == "up"


def test_hysteresis_holds_state_between_exit_and_enter():
    low = (FLAT_BAND_ENTER + 0.2) / 2  # sopra EXIT, sotto ENTER
    z = pd.Series([FLAT_BAND_ENTER + 0.1, low, low, -low])
    assert list(axis_states(z)) == ["up", "up", "up", "flat"]


def test_missing_inputs_are_skipped():
    s = _series([1.0, 1.5, 1.0, 2.0, 1.0, 3.0])
    assert axis_z([pd.Series(dtype=float), s]).equals(axis_z(s))
    assert pick_inputs({"a": s, "b": pd.Series(dtype=float)}, ("a", "b", "c")) == [s]


def test_leading_series_decides_the_quarter_gdp_has_not_reported():
    gdp = _series([1.0, 1.2, 1.0, 1.1] * 5, "QE")  # ultimo trimestre 2028Q4
    cli = pd.Series([100.0] * 80 + [101.0, 102.0, 103.0], index=pd.date_range("2024-01-31", periods=83, freq="ME"))
    z = axis_z([gdp, cli])
    assert z.index[-1] > to_end(gdp)


def to_end(s):
    return s.index[-1]


def test_monthly_input_is_moved_to_quarters():
    months = pd.date_range("2023-01-31", periods=24, freq="ME")
    z = axis_z(pd.Series([float(i % 5) for i in range(24)], index=months))
    assert len(z) == 5  # 8 trimestri meno la finestra di 3


def test_regime_history_matches_classify_on_last_quarter():
    g = _series([1.0, 1.0, 1.0, 2.0, 2.0, 2.0])
    i = _series([3.0, 3.0, 3.0, 1.0, 1.0, 1.0])
    hist = regime_history(g, i)
    assert hist.iloc[-1] == classify_regime(g, i)
    assert len(hist) == 3
