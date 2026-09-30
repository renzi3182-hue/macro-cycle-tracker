import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data import fetch_calendar, fetch_market


def test_fetch_move_skips_null_closes(requests_mock):
    requests_mock.get(
        fetch_market.YAHOO_URL.format(symbol="%5EMOVE"),
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


FF_EVENT = {"title": "CPI m/m", "country": "USD", "date": "2026-10-14T08:30:00-04:00", "impact": "High",
            "forecast": "0.3%", "previous": "0.4%"}


def test_fetch_economic_events_converts_to_utc_and_skips_missing_next_week(requests_mock):
    requests_mock.get(fetch_calendar.FF_URLS[0], json=[FF_EVENT])
    requests_mock.get(fetch_calendar.FF_URLS[1], status_code=404)
    events = fetch_calendar.fetch_economic_events()
    assert len(events) == 1 and events[0]["date"] == "2026-10-14T12:30:00+00:00" and events[0]["impact"] == "High"


def test_events_cache_roundtrip_prunes_old(tmp_path):
    import pandas as pd

    from src.data import cache

    db = tmp_path / "t.db"
    old = {**FF_EVENT, "date": "2026-09-01T12:30:00+00:00"}
    new = {**FF_EVENT, "date": "2026-10-14T12:30:00+00:00"}
    cache.write_events([old, new], now=pd.Timestamp("2026-10-10", tz="UTC"), db_path=db)
    cache.write_events([new], now=pd.Timestamp("2026-10-10", tz="UTC"), db_path=db)  # upsert: nessun duplicato
    rows = cache.read_events(db_path=db)
    assert [r["date"] for r in rows] == [new["date"]]


def test_calendar_html_groups_by_local_day_and_escapes():
    import pandas as pd

    from src.ui.cards import calendar_html

    ev = [{**FF_EVENT, "date": "2026-10-14T12:30:00+00:00", "title": "CPI <m/m>"}]
    html = calendar_html(ev, today=pd.Timestamp("2026-10-14", tz="Europe/Rome"))
    assert "Mer 14/10" in html and "14:30" in html and "oggi" in html and "CPI &lt;m/m&gt;" in html
    assert "Nessun evento" in calendar_html([])
