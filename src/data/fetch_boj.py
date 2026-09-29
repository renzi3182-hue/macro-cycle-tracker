import pandas as pd
import requests

# API Bank of Japan (Time-Series Data Search), pubblica, senza chiave.
# Tankan, DI condizioni di business, grandi imprese manifatturiere, dato effettivo.
# Trimestrale, % punti (>0 = piu' imprese dicono "buone" che "cattive"). Verificato 29/09/2026.
URL = "https://www.stat-search.boj.or.jp/api/v1/getDataCode"
TANKAN_LARGE_MANUFACTURERS = "TK99F1000601GCQ01000"


def fetch_tankan() -> pd.Series:
    resp = requests.get(
        URL,
        params={"format": "json", "lang": "en", "db": "CO", "code": TANKAN_LARGE_MANUFACTURERS, "startDate": "197401"},
        timeout=30,
    )
    resp.raise_for_status()
    values = resp.json()["RESULTSET"][0]["VALUES"]
    # SURVEY_DATES = AAAAQQ (es. 202602 = 2o trimestre 2026) -> primo giorno del trimestre, come gli altri dati trimestrali
    pairs = [(pd.Timestamp(year=d // 100, month=(d % 100 - 1) * 3 + 1, day=1), float(v))
             for d, v in zip(values["SURVEY_DATES"], values["VALUES"]) if v is not None]
    return pd.Series([v for _, v in pairs], index=[d for d, _ in pairs]).sort_index()
