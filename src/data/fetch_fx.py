import pandas as pd

from src.data.fetch_fred import _fetch_series

# Cambi FRED (H.10, giornalieri) e tassi a breve OECD (mensili) per le 4 valute.
FX_SERIES = {"eurusd": "DEXUSEU", "gbpusd": "DEXUSUK", "usdjpy": "DEXJPUS"}
RATE_SERIES = {
    "USD": "IRSTCI01USM156N",
    "EUR": "ECBDFR",
    "GBP": "IRSTCI01GBM156N",
    "JPY": "IRSTCI01JPM156N",
}


def fetch_fx(name: str, api_key: str) -> pd.Series:
    return _fetch_series(FX_SERIES[name], api_key, units="lin")


def fetch_short_rate(ccy: str, api_key: str) -> pd.Series:
    return _fetch_series(RATE_SERIES[ccy], api_key, units="lin")
