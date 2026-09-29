import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data import fetch_calendar, fetch_market


def test_fetch_move_skips_null_closes(requests_mock):
    requests_mock.get(
        fetch_market.YAHOO_URL,
        json={"chart": {"result": [{"timestamp": [1700000000, 1700086400],
                                    "indicators": {"quote": [{"close": [100.5, None]}]}}]}},
    )
    assert list(fetch_market.fetch_move().values) == [100.5]


def test_fetch_release_dates(requests_mock):
    requests_mock.get(fetch_calendar.FRED_RELEASE_DATES_URL,
                      json={"release_dates": [{"release_id": 10, "date": "2026-10-14"}]})
    result = fetch_calendar.fetch_release_dates(10, "k", today=date(2026, 9, 29))
    assert [d.strftime("%Y-%m-%d") for d in result.index] == ["2026-10-14"]


def test_fetch_fomc_dates_takes_last_day(requests_mock):
    html = ("<h4>2026 FOMC Meetings</h4><div>January 27-28</div> "
            "<div>March 17-18*</div> <h4>2025 FOMC Meetings</h4> December 9-10 Statement")
    requests_mock.get(fetch_calendar.FOMC_URL, text=html)
    result = fetch_calendar.fetch_fomc_dates(years=(2026,))
    assert [d.strftime("%Y-%m-%d") for d in result.index] == ["2026-01-28", "2026-03-18"]
