import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from src.data import fetch_fred, http


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
    assert requests_mock.last_request.qs["series_id"] == ["cpiaucns"]  # non destagionalizzato
    fetch_fred.fetch_core_inflation_yoy("dummy_key")
    assert requests_mock.last_request.qs["series_id"] == ["cpilfens"]


def test_calls_counts_failures(requests_mock):
    fetch_fred.calls.update(tried=0, ok=0)
    requests_mock.get(fetch_fred.BASE_URL, status_code=500)
    with pytest.raises(Exception):
        fetch_fred.fetch_vix("k")
    assert fetch_fred.calls == {"tried": 1, "ok": 0}


def test_fetch_leading_series(requests_mock):
    requests_mock.get(
        fetch_fred.BASE_URL,
        json={"observations": [{"date": "2024-01-01", "value": "-0.4"}, {"date": "2024-01-02", "value": "."}]},
    )
    for fn in (fetch_fred.fetch_yield_curve, fetch_fred.fetch_credit_spread, fetch_fred.fetch_financial_conditions):
        assert list(fn("dummy_key").values) == [-0.4]


def test_fetch_market_expectations(requests_mock):
    requests_mock.get(fetch_fred.BASE_URL, json={"observations": [{"date": "2024-01-01", "value": "2.3"}]})
    for fn in (fetch_fred.fetch_vix, fetch_fred.fetch_recession_probability,
               fetch_fred.fetch_breakeven_5y, fetch_fred.fetch_breakeven_5y5y):
        assert list(fn("dummy_key").values) == [2.3]


def test_fetch_gip_series(requests_mock):
    requests_mock.get(fetch_fred.BASE_URL, json={"observations": [{"date": "2024-01-01", "value": "1.5"}]})
    assert list(fetch_fred.fetch_industrial_production_yoy("k").values) == [1.5]
    assert list(fetch_fred.fetch_fed_funds("k").values) == [1.5]


def test_retry_recovers_after_two_server_errors(requests_mock):
    requests_mock.get(fetch_fred.BASE_URL, [
        {"status_code": 502},
        {"status_code": 502},
        {"json": {"observations": [{"date": "2024-01-01", "value": "2.0"}]}, "status_code": 200},
    ])
    result = fetch_fred.fetch_vix("k")
    assert list(result.values) == [2.0]
    assert requests_mock.call_count == 3


def test_client_error_does_not_retry(requests_mock):
    requests_mock.get(fetch_fred.BASE_URL, status_code=400)
    with pytest.raises(Exception):
        fetch_fred.fetch_vix("k")
    assert requests_mock.call_count == 1


def test_circuit_opens_after_three_failed_series_then_single_attempt(requests_mock):
    requests_mock.get(fetch_fred.BASE_URL, status_code=502)
    for _ in range(3):
        with pytest.raises(Exception):
            fetch_fred.fetch_vix("k")
    assert requests_mock.call_count == 12  # 3 serie x 4 tentativi

    requests_mock.reset()
    requests_mock.get(fetch_fred.BASE_URL, status_code=502)
    with pytest.raises(Exception):
        fetch_fred.fetch_vix("k")
    assert requests_mock.call_count == 1  # circuito aperto: un solo tentativo

    requests_mock.reset()
    requests_mock.get(fetch_fred.BASE_URL, json={"observations": [{"date": "2024-01-01", "value": "2.0"}]})
    fetch_fred.fetch_vix("k")  # successo: azzera il contatore
    assert http._consecutive_failures.get("fred", 0) == 0


def test_usa_inflation_yoy_may_jun_jul_2026(requests_mock):
    """Dati salvati in fixture (osservazioni FRED units=pc1, gia' il valore YoY): nessuna chiamata di rete."""
    headline = {"CPIAUCNS": [("2026-05-01", "4.2"), ("2026-06-01", "3.5"), ("2026-07-01", "3.4")]}
    core = {"CPILFENS": [("2026-05-01", "2.9"), ("2026-06-01", "2.6"), ("2026-07-01", "2.5")]}

    def responder(request, context):
        series_id = request.qs["series_id"][0].upper()
        fixture = headline.get(series_id) or core[series_id]
        return {"observations": [{"date": d, "value": v} for d, v in fixture]}

    requests_mock.get(fetch_fred.BASE_URL, json=responder)
    h = fetch_fred.fetch_inflation_yoy("k")
    assert requests_mock.last_request.qs["series_id"] == ["cpiaucns"]
    c = fetch_fred.fetch_core_inflation_yoy("k")
    assert requests_mock.last_request.qs["series_id"] == ["cpilfens"]
    for month, expected in [("2026-05-01", 4.2), ("2026-06-01", 3.5), ("2026-07-01", 3.4)]:
        assert round(h.loc[month], 1) == expected
    for month, expected in [("2026-05-01", 2.9), ("2026-06-01", 2.6), ("2026-07-01", 2.5)]:
        assert round(c.loc[month], 1) == expected
