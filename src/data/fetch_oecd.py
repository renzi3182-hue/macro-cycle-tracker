import io
from functools import lru_cache

import pandas as pd
import requests

# OECD Composite Leading Indicator, amplitude adjusted (media di lungo periodo = 100).
# Anticipa i punti di svolta del ciclo di 6-9 mesi. L'OCSE non pubblica il CLI per
# l'Eurozona: G4E = 4 grandi economie europee (DE, FR, IT, ES), ~75% del PIL dell'area.
# Verificato con dati reali (29/09/2026): serie mensili dal 1960, ultimo dato ago 2026.
URL = "https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_CLI,/{areas}.M.LI...AA...H"
AREAS = {"USA": "USA", "Eurozona": "G4E", "Italia": "ITA", "UK": "GBR", "Giappone": "JPN"}


@lru_cache(maxsize=1)  # una sola chiamata per tutte le aree: l'API OCSE ha limiti di frequenza stretti
def _fetch_all() -> pd.DataFrame:
    resp = requests.get(
        URL.format(areas="+".join(AREAS.values())),
        params={"startPeriod": "1960-01", "format": "csv"},
        headers={"User-Agent": "Mozilla/5.0 (compatible; macro-cycle-tracker/1.0)"},
        timeout=60,
    )
    resp.raise_for_status()
    return pd.read_csv(io.StringIO(resp.text), usecols=["REF_AREA", "TIME_PERIOD", "OBS_VALUE"])


def fetch_cli(area: str) -> pd.Series:
    df = _fetch_all()
    df = df[df["REF_AREA"] == AREAS[area]].dropna()
    return pd.Series(df["OBS_VALUE"].values, index=pd.to_datetime(df["TIME_PERIOD"])).sort_index()
