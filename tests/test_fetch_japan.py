import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data import fetch_japan

INFLATION_PAYLOAD = {
    "GET_STATS_DATA": {
        "STATISTICAL_DATA": {
            "DATA_INF": {
                "VALUE": [
                    {"@time": "2026000707", "$": "2.0"},
                    {"@time": "2026000808", "$": "2.0"},
                ]
            }
        }
    }
}

# livelli PIL reale trimestrale: 4 trimestri 2024 + Q1 2025, per verificare
# il calcolo YoY (pct_change a 4 trimestri) sul primo punto disponibile.
GROWTH_PAYLOAD = {
    "GET_STATS_DATA": {
        "STATISTICAL_DATA": {
            "DATA_INF": {
                "VALUE": [
                    {"@time": "2024000103", "$": "100"},
                    {"@time": "2024000406", "$": "102"},
                    {"@time": "2024000709", "$": "104"},
                    {"@time": "2024001012", "$": "106"},
                    {"@time": "2025000103", "$": "110"},
                ]
            }
        }
    }
}


def test_fetch_growth_yoy_computes_from_levels(requests_mock):
    requests_mock.get(fetch_japan.BASE_URL, json=GROWTH_PAYLOAD)
    result = fetch_japan.fetch_growth_yoy("dummy_app_id")
    assert len(result) == 1
    assert result.index[0].strftime("%Y-%m") == "2025-01"
    assert round(result.iloc[0], 2) == 10.0


def test_fetch_growth_yoy_sends_verified_filters(requests_mock):
    requests_mock.get(fetch_japan.BASE_URL, json=GROWTH_PAYLOAD)
    fetch_japan.fetch_growth_yoy("dummy_app_id")
    qs = requests_mock.last_request.qs
    assert qs["cdtab"] == ["11"]
    assert qs["cdcat01"] == ["11"]


def test_fetch_inflation_yoy_parses_real_time_format(requests_mock):
    requests_mock.get(fetch_japan.BASE_URL, json=INFLATION_PAYLOAD)
    result = fetch_japan.fetch_inflation_yoy("dummy_app_id")
    assert list(result.values) == [2.0, 2.0]
    assert list(result.index.strftime("%Y-%m")) == ["2026-07", "2026-08"]


def test_fetch_inflation_yoy_sends_verified_filters(requests_mock):
    requests_mock.get(fetch_japan.BASE_URL, json=INFLATION_PAYLOAD)
    fetch_japan.fetch_inflation_yoy("dummy_app_id")
    qs = requests_mock.last_request.qs
    assert qs["cdtab"] == ["3"]
    assert qs["cdcat01"] == ["0001"]
    assert qs["cdarea"] == ["00000"]
