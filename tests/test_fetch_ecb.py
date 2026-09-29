import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data import fetch_ecb

JSONSTAT_PAYLOAD = {
    "dimension": {"time": {"category": {"index": {"2023-Q1": 0, "2023-Q2": 1, "2023-Q3": 2}}}},
    "value": {"0": 1.1, "1": 1.5, "2": 1.8},
}

JSONSTAT_MONTHLY_PAYLOAD = {
    "dimension": {"time": {"category": {"index": {"2023M01": 0, "2023M02": 1}}}},
    "value": {"0": 2.4, "1": 2.6},
}

JSONSTAT_MONTHLY_HYPHEN_PAYLOAD = {
    "dimension": {"time": {"category": {"index": {"2023-01": 0, "2023-02": 1}}}},
    "value": {"0": 3.1, "1": 3.3},
}


def test_fetch_growth_yoy(requests_mock):
    requests_mock.get(f"{fetch_ecb.BASE_URL}/namq_10_gdp", json=JSONSTAT_PAYLOAD)
    result = fetch_ecb.fetch_growth_yoy("EA20")
    assert len(result) == 3
    assert list(result.values) == [1.1, 1.5, 1.8]


def test_fetch_inflation_yoy(requests_mock):
    requests_mock.get(f"{fetch_ecb.BASE_URL}/prc_hicp_minr", json=JSONSTAT_MONTHLY_PAYLOAD)
    result = fetch_ecb.fetch_inflation_yoy("IT")
    assert len(result) == 2
    assert list(result.values) == [2.4, 2.6]


def test_fetch_inflation_yoy_hyphenated_month(requests_mock):
    # formato reale osservato da Eurostat per prc_hicp_minr: "2023-01", non "2023M01"
    requests_mock.get(f"{fetch_ecb.BASE_URL}/prc_hicp_minr", json=JSONSTAT_MONTHLY_HYPHEN_PAYLOAD)
    result = fetch_ecb.fetch_inflation_yoy("IT")
    assert len(result) == 2
    assert list(result.values) == [3.1, 3.3]
