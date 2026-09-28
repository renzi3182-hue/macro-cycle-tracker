import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data import fetch_fred


def test_fetch_growth_yoy_skips_missing_values(requests_mock):
    requests_mock.get(
        fetch_fred.BASE_URL,
        json={
            "observations": [
                {"date": "2024-01-01", "value": "2.5"},
                {"date": "2024-04-01", "value": "."},
                {"date": "2024-07-01", "value": "3.0"},
            ]
        },
    )
    result = fetch_fred.fetch_growth_yoy("dummy_key")
    assert list(result.values) == [2.5, 3.0]


def test_fetch_inflation_yoy(requests_mock):
    requests_mock.get(
        fetch_fred.BASE_URL,
        json={"observations": [{"date": "2024-01-01", "value": "3.1"}]},
    )
    result = fetch_fred.fetch_inflation_yoy("dummy_key")
    assert list(result.values) == [3.1]
