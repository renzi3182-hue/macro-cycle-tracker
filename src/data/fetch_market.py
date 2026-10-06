import time
from urllib.parse import quote

import pandas as pd
import requests

# Yahoo Finance chart endpoint: non ufficiale, senza chiave. MOVE non e' su FRED.
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
FIRST_TIMESTAMP = -1_500_000_000  # 1922: prima di qualsiasi serie Yahoo (i mensili partono comunque dal 1985)


def fetch_yahoo(symbol: str, range_: str = "5y", interval: str = "1d", adjusted: bool = False) -> pd.Series:
    """Chiusure di un simbolo Yahoo. Con interval='1mo' la data e' il primo del mese, la chiusura l'ultima del mese.
    adjusted=True: chiusure rettificate per dividendi e split (rendimento totale degli ETF)."""
    # range=max con interval=1mo restituisce un punto ogni 3 mesi: per tutto lo storico serve period1/period2
    span = {"period1": FIRST_TIMESTAMP, "period2": int(time.time())} if range_ == "max" else {"range": range_}
    resp = requests.get(
        YAHOO_URL.format(symbol=quote(symbol)),
        params={**span, "interval": interval},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()["chart"]["result"][0]
    closes = result["indicators"]["adjclose"][0]["adjclose"] if adjusted else result["indicators"]["quote"][0]["close"]
    pairs = [(pd.Timestamp(ts, unit="s").normalize(), c) for ts, c in zip(result["timestamp"], closes) if c is not None]
    return pd.Series([c for _, c in pairs], index=[d for d, _ in pairs]).sort_index()


def fetch_move() -> pd.Series:
    """ICE BofA MOVE Index (volatilita' implicita sui Treasury), chiusura giornaliera."""
    return fetch_yahoo("^MOVE")
