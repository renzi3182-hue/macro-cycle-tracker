# Nome file per aderenza allo spec ("ECB Statistical Data Warehouse + Eurostat"),
# ma implementato via Eurostat REST (dataset ufficiali Eurostat, no API key, stesso dato).
import pandas as pd
import requests

BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"


def _parse_eurostat_period(label: str) -> pd.Timestamp:
    if "-Q" in label:
        year, q = label.split("-Q")
        month = (int(q) - 1) * 3 + 1
        return pd.Timestamp(year=int(year), month=month, day=1)
    if "M" in label:
        year, month = label.split("M")
        return pd.Timestamp(year=int(year), month=int(month), day=1)
    if "-" in label:
        year, month = label.split("-")
        return pd.Timestamp(year=int(year), month=int(month), day=1)
    return pd.Timestamp(year=int(label), month=1, day=1)


def _parse_jsonstat(payload: dict) -> pd.Series:
    time_index = payload["dimension"]["time"]["category"]["index"]
    label_by_index = {v: k for k, v in time_index.items()}
    values = payload["value"]
    series_dict = {
        label_by_index[int(flat_idx)]: val
        for flat_idx, val in values.items()
        if int(flat_idx) in label_by_index
    }
    dates = [_parse_eurostat_period(label) for label in series_dict]
    return pd.Series(list(series_dict.values()), index=dates).sort_index()


def fetch_growth_yoy(geo: str) -> pd.Series:
    """geo: 'EA21' per Eurozona (con la Bulgaria dal 2026; EA20 non e' piu' aggiornato per l'ESI), 'IT' per Italia."""
    resp = requests.get(
        f"{BASE_URL}/namq_10_gdp",
        params={"format": "JSON", "lang": "EN", "unit": "CLV_PCH_SM", "na_item": "B1GQ", "s_adj": "SCA", "geo": geo},
        timeout=30,
    )
    resp.raise_for_status()
    return _parse_jsonstat(resp.json())


def fetch_inflation_yoy(geo: str, coicop18: str = "TOTAL") -> pd.Series:
    """geo: 'EA' per Eurozona, 'IT' per Italia. coicop18: 'TOTAL' o 'TOT_X_NRG_FOOD' (core, senza energia e cibo).

    prc_hicp_manr e' congelato a dic 2025 (ultimo update feb 2026): Eurostat e' passata
    a ECOICOP v2 (prc_hicp_minr). Verificato con dati reali (29/09/2026)."""
    resp = requests.get(
        f"{BASE_URL}/prc_hicp_minr",
        params={"format": "JSON", "lang": "EN", "coicop18": coicop18, "unit": "RCH_A", "geo": geo},
        timeout=30,
    )
    resp.raise_for_status()
    return _parse_jsonstat(resp.json())


def fetch_core_inflation_yoy(geo: str) -> pd.Series:
    return fetch_inflation_yoy(geo, "TOT_X_NRG_FOOD")


def fetch_sentiment(geo: str) -> pd.Series:
    """Economic Sentiment Indicator (Commissione UE), media di lungo periodo = 100. geo: 'EA21', 'IT' (EA20 fermo a dic 2025)."""
    resp = requests.get(
        f"{BASE_URL}/ei_bssi_m_r2",
        params={"format": "JSON", "lang": "EN", "indic": "BS-ESI-I", "s_adj": "SA", "geo": geo},
        timeout=30,
    )
    resp.raise_for_status()
    return _parse_jsonstat(resp.json())


def fetch_unemployment_rate(geo: str) -> pd.Series:
    """geo: 'EA21' per Eurozona, 'IT' per Italia. Verificato con dati reali (29/09/2026)."""
    resp = requests.get(
        f"{BASE_URL}/une_rt_m",
        params={
            "format": "JSON", "lang": "EN",
            "s_adj": "SA", "age": "TOTAL", "sex": "T", "unit": "PC_ACT", "geo": geo,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return _parse_jsonstat(resp.json())
