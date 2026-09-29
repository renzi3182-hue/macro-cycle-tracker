import pandas as pd
import requests

# Yahoo Finance chart endpoint: non ufficiale, senza chiave. MOVE non e' su FRED.
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/%5EMOVE"


def fetch_move() -> pd.Series:
    """ICE BofA MOVE Index (volatilita' implicita sui Treasury), chiusura giornaliera."""
    resp = requests.get(
        YAHOO_URL,
        params={"range": "5y", "interval": "1d"},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()["chart"]["result"][0]
    closes = result["indicators"]["quote"][0]["close"]
    pairs = [(pd.Timestamp(ts, unit="s").normalize(), c) for ts, c in zip(result["timestamp"], closes) if c is not None]
    return pd.Series([c for _, c in pairs], index=[d for d, _ in pairs]).sort_index()
