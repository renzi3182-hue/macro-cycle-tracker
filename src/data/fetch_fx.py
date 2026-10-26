import pandas as pd

from src.data.fetch_fred import _fetch_series

# Cambi FRED (H.10, giornalieri) e tassi a breve OECD (mensili) per la classifica valute di src/classify/allocation.py.
FX_SERIES = {"eurusd": "DEXUSEU", "gbpusd": "DEXUSUK", "usdjpy": "DEXJPUS", "usdcad": "DEXCAUS", "audusd": "DEXUSAL",
             "usdcny": "DEXCHUS", "usdinr": "DEXINUS",
             "usddem": "EXGEUS", "usditl": "EXITUS"}  # marco e lira, mensili 1971-2001: prima dell'euro
RATE_SERIES = {
    "USD": "IRSTCI01USM156N",
    "EUR": "ECBDFR",
    "GBP": "IRSTCI01GBM156N",
    "JPY": "IRSTCI01JPM156N",
    "CAD": "IRSTCI01CAM156N",
    "AUD": "IRSTCI01AUM156N",
    "CNY": "IR3TIB01CNM156N",  # interbancario 3 mesi: il tasso overnight OCSE e' fermo al 2025
    "INR": "IRSTCI01INM156N",
    "DEM": "IR3TIB01DEM156N",  # Germania 3 mesi: tasso dell'euro prima del 1999 (allocation.py)
}


def fetch_fx(name: str, api_key: str) -> pd.Series:
    return _fetch_series(FX_SERIES[name], api_key, units="lin")


def fetch_short_rate(ccy: str, api_key: str) -> pd.Series:
    return _fetch_series(RATE_SERIES[ccy], api_key, units="lin")
