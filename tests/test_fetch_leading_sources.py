import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data import fetch_boj, fetch_ecb, fetch_oecd

OECD_CSV = "REF_AREA,TIME_PERIOD,OBS_VALUE,OTHER\nUSA,2026-07,100.1,x\nG4E,2026-07,99.2,x\nUSA,2026-08,100.3,x\n"


def test_fetch_cli_filters_area_with_single_call(requests_mock):
    fetch_oecd._fetch_all.cache_clear()
    m = requests_mock.get(re.compile("sdmx.oecd.org"), text=OECD_CSV)
    assert list(fetch_oecd.fetch_cli("USA").values) == [100.1, 100.3]
    assert list(fetch_oecd.fetch_cli("Eurozona").values) == [99.2]
    assert m.call_count == 1
    fetch_oecd._fetch_all.cache_clear()


def test_fetch_tankan_quarter_dates(requests_mock):
    requests_mock.get(fetch_boj.URL, json={"RESULTSET": [{"VALUES": {
        "SURVEY_DATES": [202504, 202601, 202602], "VALUES": [15, None, 22]}}]})
    s = fetch_boj.fetch_tankan()
    assert [d.strftime("%Y-%m") for d in s.index] == ["2025-10", "2026-04"]
    assert list(s.values) == [15.0, 22.0]


def test_fetch_sentiment(requests_mock):
    requests_mock.get(f"{fetch_ecb.BASE_URL}/ei_bssi_m_r2", json={
        "dimension": {"time": {"category": {"index": {"2026-08": 0, "2026-09": 1}}}}, "value": {"0": 94.1, "1": 95.3}})
    assert list(fetch_ecb.fetch_sentiment("EA20").values) == [94.1, 95.3]
