"""BIS (Banca dei Regolamenti Internazionali, statistiche gratuite, riuso con citazione "Fonte: BIS"): cambio
effettivo reale (REER, paniere ampio, 1994 = inizio) per le 8 valute di src/classify/currency.py. Serve al pilastro
Valore della classifica valute (src/classify/allocation.py): una valuta sopra la sua media di lungo periodo e' cara."""
import io

import pandas as pd

from src.data.http import get_with_retry

URL = "https://stats.bis.org/api/v1/data/WS_EER/M.R.B.{areas}"
AREAS = {"USD": "US", "EUR": "XM", "GBP": "GB", "JPY": "JP", "CAD": "CA", "AUD": "AU", "CNY": "CN", "INR": "IN"}


def fetch_reer() -> dict[str, pd.Series]:
    """Una serie mensile per valuta (indice 2020 = 100), una sola chiamata."""
    resp = get_with_retry(URL.format(areas="+".join(AREAS.values())), source="bis", params={"format": "csv"}, timeout=60)
    df = pd.read_csv(io.StringIO(resp.text)).dropna(subset=["OBS_VALUE"])
    by_code = {v: k for k, v in AREAS.items()}
    return {by_code[a]: pd.Series(g["OBS_VALUE"].values, index=pd.to_datetime(g["TIME_PERIOD"])).sort_index()
            for a, g in df.groupby("REF_AREA") if a in by_code}
