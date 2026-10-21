import time
from urllib.parse import quote

import pandas as pd

from src.data.http import get_with_retry

# Yahoo Finance chart endpoint: non ufficiale, senza chiave. MOVE non e' su FRED.
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
FIRST_TIMESTAMP = -1_500_000_000  # 1922: prima di qualsiasi serie Yahoo (i mensili partono comunque dal 1985)


def fetch_yahoo(symbol: str, range_: str = "5y", interval: str = "1d", adjusted: bool = False) -> pd.Series:
    """Chiusure di un simbolo Yahoo. Con interval='1mo' la data e' il primo del mese, la chiusura l'ultima del mese.
    adjusted=True: chiusure rettificate per dividendi e split (rendimento totale degli ETF)."""
    # range=max con interval=1mo restituisce un punto ogni 3 mesi: per tutto lo storico serve period1/period2
    span = {"period1": FIRST_TIMESTAMP, "period2": int(time.time())} if range_ == "max" else {"range": range_}
    resp = get_with_retry(
        YAHOO_URL.format(symbol=quote(symbol)),
        source="yahoo",
        params={**span, "interval": interval},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    result = resp.json()["chart"]["result"][0]
    closes = result["indicators"]["adjclose"][0]["adjclose"] if adjusted else result["indicators"]["quote"][0]["close"]
    pairs = [(pd.Timestamp(ts, unit="s").normalize(), c) for ts, c in zip(result["timestamp"], closes) if c is not None]
    return pd.Series([c for _, c in pairs], index=[d for d, _ in pairs]).sort_index()


def fetch_move() -> pd.Series:
    """ICE BofA MOVE Index (volatilita' implicita sui Treasury), chiusura giornaliera."""
    return fetch_yahoo("^MOVE")


# Oro, prezzo medio mensile in dollari dal 1833 (dataset pubblico datahub "gold-prices", licenza ODC-PDDL, fonte World
# Bank/Bundesbank): allunga lo storico prima di GLD (2004) per la classifica delle classi di asset.
GOLD_URL = "https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv"


def fetch_gold_monthly() -> pd.Series:
    resp = get_with_retry(GOLD_URL, source="datahub", timeout=60)
    rows = [line.split(",") for line in resp.text.splitlines()[1:] if line.count(",") == 1]
    return pd.Series([float(v) for _, v in rows], index=pd.to_datetime([d for d, _ in rows], format="%Y-%m")).sort_index()
