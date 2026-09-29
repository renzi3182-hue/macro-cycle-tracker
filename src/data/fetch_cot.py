import pandas as pd
import requests

# CFTC Legacy Futures Only (Socrata, pubblico, senza chiave). Dato riferito al
# martedi', pubblicato il venerdi'.
URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
WEEKS = 260  # ~5 anni: finestra del percentile (app e backtest)
HISTORY_LIMIT = 5000  # tutto lo storico disponibile (dal 1986 circa), serve al backtest valute

CONTRACTS = {  # nome -> cftc_contract_market_code
    "S&P 500": "13874A",
    "Nasdaq 100": "209742",
    "Treasury 10Y": "043602",
    "Oro": "088691",
    "Petrolio WTI": "067651",
    "Euro": "099741",
    "Yen": "097741",
    "Sterlina": "096742",
    "Dollaro (DXY)": "098662",
}


def fetch_net_speculative(code: str) -> pd.Series:
    """Posizione netta dei non-commercial (speculatori) in % dell'open interest."""
    resp = requests.get(
        URL,
        params={
            "cftc_contract_market_code": code,
            "$order": "report_date_as_yyyy_mm_dd desc",
            "$limit": HISTORY_LIMIT,
        },
        timeout=30,
    )
    resp.raise_for_status()
    rows = resp.json()
    dates = [pd.Timestamp(r["report_date_as_yyyy_mm_dd"]) for r in rows]
    values = [
        (float(r["noncomm_positions_long_all"]) - float(r["noncomm_positions_short_all"]))
        / float(r["open_interest_all"]) * 100
        for r in rows
    ]
    return pd.Series(values, index=dates).sort_index()
