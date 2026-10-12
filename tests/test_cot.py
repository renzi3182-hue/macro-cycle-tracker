import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

from src.classify.positioning import percentile_rank, positioning_label, zscore
from src.data import fetch_cot


def test_fetch_net_legacy_pct_of_open_interest(requests_mock):
    requests_mock.get(
        fetch_cot.URL,
        json=[
            {"report_date_as_yyyy_mm_dd": "2026-09-22T00:00:00.000", "noncomm_positions_long_all": "300",
             "noncomm_positions_short_all": "100", "comm_positions_long_all": "200", "comm_positions_short_all": "500",
             "open_interest_all": "1000"},
            {"report_date_as_yyyy_mm_dd": "2026-09-15T00:00:00.000", "noncomm_positions_long_all": "100",
             "noncomm_positions_short_all": "200", "comm_positions_long_all": "400", "comm_positions_short_all": "300",
             "open_interest_all": "1000"},
        ],
    )
    spec, comm = fetch_cot.fetch_net_legacy("13874A")
    assert list(spec.values) == [-10.0, 20.0]  # ordinata per data crescente
    assert list(comm.values) == [10.0, -30.0]


def test_percentile_and_label():
    s = pd.Series(range(100))
    assert percentile_rank(s) == 100.0
    assert positioning_label(95) == "Affollato long"
    assert positioning_label(5) == "Affollato short"
    assert positioning_label(50) == "Neutro"
    with pytest.raises(ValueError):
        percentile_rank(pd.Series(dtype=float))
    assert zscore(pd.Series([1.0, 2.0, 3.0])) == 1.0
