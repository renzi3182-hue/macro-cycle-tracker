import pandas as pd
import requests

BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
SERIES_GROWTH = "GDPC1"  # Real GDP
SERIES_INFLATION = "CPIAUCSL"  # CPI All Urban Consumers
SERIES_UNEMPLOYMENT = "UNRATE"  # Civilian Unemployment Rate


def _fetch_series(series_id: str, api_key: str, units: str = "pc1") -> pd.Series:
    resp = requests.get(
        BASE_URL,
        params={
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "units": units,  # pc1 = percent change from a year ago (YoY diretto da FRED)
        },
        timeout=30,
    )
    resp.raise_for_status()
    observations = resp.json()["observations"]
    dates = [pd.Timestamp(o["date"]) for o in observations if o["value"] != "."]
    values = [float(o["value"]) for o in observations if o["value"] != "."]
    return pd.Series(values, index=dates).sort_index()


def fetch_growth_yoy(api_key: str) -> pd.Series:
    return _fetch_series(SERIES_GROWTH, api_key)


def fetch_inflation_yoy(api_key: str) -> pd.Series:
    return _fetch_series(SERIES_INFLATION, api_key)


def fetch_unemployment_rate(api_key: str) -> pd.Series:
    return _fetch_series(SERIES_UNEMPLOYMENT, api_key, units="lin")  # gia' un tasso %, no trasformazione
