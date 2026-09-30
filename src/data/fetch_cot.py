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


# Report per categoria di trader: TFF per i finanziari, Disaggregated per le materie prime.
# Gruppo -> (campo long, campo short). I nomi dei campi Socrata non sono uniformi (suffisso _all a volte assente).
TFF_URL = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
DISAGG_URL = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"
TFF_GROUPS = {
    "Dealer": ("dealer_positions_long_all", "dealer_positions_short_all"),
    "Asset manager": ("asset_mgr_positions_long", "asset_mgr_positions_short"),
    "Hedge fund": ("lev_money_positions_long", "lev_money_positions_short"),
    "Altri grandi": ("other_rept_positions_long", "other_rept_positions_short"),
    "Piccoli": ("nonrept_positions_long_all", "nonrept_positions_short_all"),
}
DISAGG_GROUPS = {
    "Produttori": ("prod_merc_positions_long", "prod_merc_positions_short"),
    "Swap dealer": ("swap_positions_long_all", "swap__positions_short_all"),
    "Hedge fund": ("m_money_positions_long_all", "m_money_positions_short_all"),
    "Altri grandi": ("other_rept_positions_long", "other_rept_positions_short"),
    "Piccoli": ("nonrept_positions_long_all", "nonrept_positions_short_all"),
}
DISAGG_MARKETS = {"Oro", "Petrolio WTI"}


def fetch_net_by_group(market: str, limit: int = WEEKS) -> dict[str, pd.Series]:
    """Posizione netta per categoria di trader, in % dell'open interest (ultime `limit` settimane)."""
    disagg = market in DISAGG_MARKETS
    groups = DISAGG_GROUPS if disagg else TFF_GROUPS
    resp = requests.get(
        DISAGG_URL if disagg else TFF_URL,
        params={"cftc_contract_market_code": CONTRACTS[market], "$order": "report_date_as_yyyy_mm_dd desc", "$limit": limit},
        timeout=30,
    )
    resp.raise_for_status()
    rows = resp.json()
    dates = [pd.Timestamp(r["report_date_as_yyyy_mm_dd"]) for r in rows]
    return {
        g: pd.Series([(float(r[lo]) - float(r[sh])) / float(r["open_interest_all"]) * 100 for r in rows], index=dates).sort_index()
        for g, (lo, sh) in groups.items()
    }
