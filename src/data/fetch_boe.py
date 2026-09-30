# Nome file per aderenza allo spec ("Bank of England API"), ma implementato via ONS
# (Office for National Statistics): il vecchio database IADB della BoE rifiuta le
# richieste automatiche (403) e i codici serie non sono documentati in modo affidabile.
# ONS pubblica gli stessi dati (GDP, CPI) con API pubblica verificata.
import calendar

import pandas as pd
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; macro-cycle-tracker/1.0)"}
GDP_URL = "https://www.ons.gov.uk/economy/grossdomesticproductgdp/timeseries/ihyr/pn2/data"
CPI_URL = "https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23/data"
# CPI escluso energia, cibo, alcol e tabacco, variazione annua (ONS dko8, verificato 30/09/2026).
CORE_CPI_URL = "https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/dko8/mm23/data"
# Verificato con dati reali (29/09/2026): tasso di disoccupazione UK, 16+, destagionalizzato.
UNEMPLOYMENT_URL = "https://www.ons.gov.uk/employmentandlabourmarket/peoplenotinwork/unemployment/timeseries/mgsx/lms/data"


def _fetch_ons_series(url: str) -> pd.Series:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    # Mensile prima: CPI e disoccupazione hanno sia "months" sia "quarters" (medie), il PIL solo "quarters".
    entries = payload.get("months") or payload.get("quarters") or []
    dates, values = [], []
    for entry in entries:
        year = int(entry["year"])
        if entry.get("quarter"):
            month = (int(entry["quarter"][1]) - 1) * 3 + 1
        else:
            month = list(calendar.month_name).index(entry["month"])
        dates.append(pd.Timestamp(year=year, month=month, day=1))
        values.append(float(entry["value"]))
    return pd.Series(values, index=dates).sort_index()


def fetch_growth_yoy() -> pd.Series:
    return _fetch_ons_series(GDP_URL)


def fetch_inflation_yoy() -> pd.Series:
    return _fetch_ons_series(CPI_URL)


def fetch_core_inflation_yoy() -> pd.Series:
    return _fetch_ons_series(CORE_CPI_URL)


def fetch_unemployment_rate() -> pd.Series:
    return _fetch_ons_series(UNEMPLOYMENT_URL)
