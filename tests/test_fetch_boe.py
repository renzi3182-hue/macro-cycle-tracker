import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data import fetch_boe

QUARTERLY_PAYLOAD = {
    "years": [],
    "quarters": [
        {"year": "2025", "quarter": "Q4", "value": "0.9"},
        {"year": "2026", "quarter": "Q1", "value": "0.9"},
    ],
    "months": [],
}

MONTHLY_PAYLOAD = {
    "years": [],
    "quarters": [],
    "months": [
        {"year": "2026", "month": "July", "value": "2.9"},
        {"year": "2026", "month": "August", "value": "3.1"},
    ],
}


def test_fetch_growth_yoy(requests_mock):
    requests_mock.get(fetch_boe.GDP_URL, json=QUARTERLY_PAYLOAD)
    result = fetch_boe.fetch_growth_yoy()
    assert list(result.values) == [0.9, 0.9]


def test_fetch_inflation_yoy(requests_mock):
    requests_mock.get(fetch_boe.CPI_URL, json=MONTHLY_PAYLOAD)
    result = fetch_boe.fetch_inflation_yoy()
    assert list(result.values) == [2.9, 3.1]


def test_monthly_preferred_over_quarterly(requests_mock):
    # ONS pubblica il CPI sia mensile sia come media trimestrale: serve il mensile (piu' tempestivo)
    both = {"years": [], "quarters": QUARTERLY_PAYLOAD["quarters"], "months": MONTHLY_PAYLOAD["months"]}
    requests_mock.get(fetch_boe.CPI_URL, json=both)
    assert list(fetch_boe.fetch_inflation_yoy().values) == [2.9, 3.1]
