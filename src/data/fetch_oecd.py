import io
from functools import lru_cache

import pandas as pd

from src.data.http import get_with_retry

# OECD Composite Leading Indicator, amplitude adjusted (media di lungo periodo = 100).
# Anticipa i punti di svolta del ciclo di 6-9 mesi. L'OCSE non pubblica il CLI per
# l'Eurozona: G4E = 4 grandi economie europee (DE, FR, IT, ES), ~75% del PIL dell'area.
# Verificato con dati reali (29/09/2026): serie mensili dal 1960, ultimo dato ago 2026.
BASE = "https://sdmx.oecd.org/public/rest/data/"
CLI_URL = BASE + "OECD.SDD.STES,DSD_STES@DF_CLI,/{areas}.M.LI...AA...H"
# Aree senza una fonte nazionale gia' usata (aggiunte il 09/10/2026, le stesse della dashboard Quantaste piu'
# l'India): PIL e inflazione dall'OCSE, che li pubblica anche per Cina e India. Verificato: PIL annuo reale fino
# al 2o trimestre 2026 (Cina dal 1993, India dal 1997), CPI annuo fino ad agosto 2026.
# Inflazione core: solo Australia. Quella del Canada si ferma ad aprile 2025, Cina e India non la pubblicano.
# Australia: CPI mensile solo da aprile 2025, prima trimestrale; il mensile vale dove c'e'.
GDP_URL = BASE + "OECD.SDD.NAD,DSD_NAMAIN1@DF_QNA_EXPENDITURE_GROWTH_OECD,/Q.Y.{areas}.S1.S1.B1GQ._Z._Z._Z.PC.L.GY."
CPI_URL = BASE + "OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,/{areas}.M+Q.N.CPI.PA._T+_TXCP01_NRG.N.GY"
AREAS = {"USA": "USA", "Eurozona": "G4E", "Italia": "ITA", "UK": "GBR", "Giappone": "JPN",
         "Canada": "CAN", "Cina": "CHN", "Australia": "AUS", "India": "IND"}
OECD_ONLY = ["Canada", "Cina", "Australia", "India"]
CORE_AREAS = {"Australia"}
CORE, HEADLINE = "_TXCP01_NRG", "_T"


@lru_cache(maxsize=4)  # una sola chiamata per dataset e tutte le aree: l'API OCSE ha limiti di frequenza stretti
def _fetch(url: str, start: str) -> pd.DataFrame:
    resp = get_with_retry(
        url, source="oecd",
        params={"startPeriod": start, "format": "csv"},
        headers={"User-Agent": "Mozilla/5.0 (compatible; macro-cycle-tracker/1.0)"},
        timeout=60,
    )
    return pd.read_csv(io.StringIO(resp.text))


def _to_series(df: pd.DataFrame) -> pd.Series:
    """TIME_PERIOD "2026-08" o "2026-Q2" -> inizio del periodo."""
    df = df.dropna(subset=["OBS_VALUE"])
    dates = df["TIME_PERIOD"].str.replace(r"-Q(\d)", lambda m: f"-{3 * int(m[1]) - 2:02d}", regex=True)
    return pd.Series(df["OBS_VALUE"].values, index=pd.to_datetime(dates))


def fetch_cli(area: str) -> pd.Series:
    df = _fetch(CLI_URL.format(areas="+".join(AREAS.values())), "1960-01")
    return _to_series(df[df["REF_AREA"] == AREAS[area]]).sort_index()


def fetch_growth_yoy(area: str) -> pd.Series:
    """PIL reale, variazione % sullo stesso trimestre dell'anno prima."""
    df = _fetch(GDP_URL.format(areas="+".join(AREAS[a] for a in OECD_ONLY)), "1960-Q1")
    return _to_series(df[df["REF_AREA"] == AREAS[area]]).sort_index()


def fetch_inflation_yoy(area: str, core: bool = False) -> pd.Series:
    """CPI annuo %. Dove ci sono sia mensile sia trimestrale vale il mensile."""
    df = _fetch(CPI_URL.format(areas="+".join(AREAS[a] for a in OECD_ONLY)), "1960-01")
    df = df[(df["REF_AREA"] == AREAS[area]) & (df["EXPENDITURE"] == (CORE if core else HEADLINE))]
    monthly, quarterly = (_to_series(df[df["FREQ"] == f]) for f in ("M", "Q"))
    if not monthly.empty:
        quarterly = quarterly[quarterly.index < monthly.index.min()]
    return pd.concat([quarterly, monthly]).sort_index()


# Produzione industriale (indice, non destagionalizzato): dato mensile di attivita' che esce ~6 settimane dopo il
# mese, contro i ~4 mesi del PIL del trimestre. Cina e Australia non la pubblicano all'OCSE.
IP_URL = BASE + "OECD.SDD.STES,DSD_STES@DF_INDSERV,/{areas}.M.PRVM.IX.BTE.N.._Z."
IP_AREAS = {"Eurozona": "EA20", "Italia": "ITA", "UK": "GBR", "Giappone": "JPN", "Canada": "CAN", "India": "IND"}


def fetch_industrial_production_yoy(area: str) -> pd.Series:
    df = _fetch(IP_URL.format(areas="+".join(IP_AREAS.values())), "1960-01")
    level = _to_series(df[df["REF_AREA"] == IP_AREAS[area]]).sort_index()
    return (level.pct_change(12, fill_method=None) * 100).dropna()
