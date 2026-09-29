import re
from datetime import date

import pandas as pd
import requests

FRED_RELEASE_DATES_URL = "https://api.stlouisfed.org/fred/release/dates"
FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
FRED_RELEASES = {"CPI": 10, "Occupazione (NFP)": 50, "PIL": 53}  # nome -> release_id FRED
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def fetch_release_dates(release_id: int, api_key: str, today: date | None = None) -> pd.Series:
    """Prossime date di pubblicazione di una release FRED, come Series (indice = data, valore 1.0)."""
    today = today or date.today()
    resp = requests.get(
        FRED_RELEASE_DATES_URL,
        params={
            "release_id": release_id,
            "api_key": api_key,
            "file_type": "json",
            "realtime_start": today.isoformat(),
            "include_release_dates_with_no_data": "true",
            "sort_order": "asc",
            "limit": 6,
        },
        timeout=30,
    )
    resp.raise_for_status()
    dates = [pd.Timestamp(d["date"]) for d in resp.json()["release_dates"]]
    return pd.Series(1.0, index=dates)


def fetch_fomc_dates(years: tuple[int, ...] | None = None) -> pd.Series:
    """Giorno di decisione (ultimo giorno) di ogni riunione FOMC dal calendario Fed."""
    years = years or (date.today().year, date.today().year + 1)
    resp = requests.get(FOMC_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    resp.raise_for_status()
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", resp.text))
    found = []
    for year in years:
        start = text.find(f"{year} FOMC Meetings")
        if start == -1:
            continue
        end = text.find("FOMC Meetings", start + 20)
        section = text[start:end if end != -1 else None]
        # Le riunioni future non hanno ancora il link "Statement": si riconoscono dal
        # range di due giorni ("October 27-28"). Esclude le release dei verbali ("April 08, 2026").
        for month, last in re.findall(rf"({'|'.join(MONTHS)}) \d{{1,2}}-(\d{{1,2}})", section):
            found.append(pd.Timestamp(year=year, month=MONTHS.index(month) + 1, day=int(last)))
    return pd.Series(1.0, index=sorted(found))
