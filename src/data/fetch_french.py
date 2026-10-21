"""Rendimenti mensili dalla Kenneth French Data Library (Dartmouth, gratuita, dati CRSP): mercato USA e 12 settori
dal 1926. Allungano lo storico del punteggio asset (src/classify/score.py) prima della nascita degli ETF."""
import io
import zipfile

import pandas as pd

from src.data.http import get_with_retry

URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{}_CSV.zip"
INDUSTRIES = "12_Industry_Portfolios"
FACTORS = "F-F_Research_Data_Factors"


def parse_monthly(text: str) -> pd.DataFrame:
    """Prima tabella del CSV (mensile; per i settori: pesata per capitalizzazione), in frazioni, indice = inizio mese.
    Le tabelle iniziano con una riga di intestazione che comincia con una virgola e finiscono alla prima riga senza AAAAMM."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(","))
    cols = [c.strip() for c in lines[start].split(",")[1:]]
    rows = []
    for line in lines[start + 1:]:
        parts = [p.strip() for p in line.split(",")]
        if len(parts[0]) != 6 or not parts[0].isdigit():
            break
        rows.append(parts)
    df = pd.DataFrame([r[1:] for r in rows], columns=cols, index=pd.to_datetime([r[0] for r in rows], format="%Y%m"))
    return df.astype(float).where(lambda d: d > -99) / 100  # -99.99 = dato mancante


def _download(name: str) -> pd.DataFrame:
    resp = get_with_retry(URL.format(name), source="french", timeout=60)
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        return parse_monthly(z.read(z.namelist()[0]).decode("latin-1"))


def fetch_french() -> dict[str, pd.Series]:
    """Una serie di rendimenti mensili per settore (NoDur, BusEq, ...) piu' Mkt = mercato USA totale (Mkt-RF + RF)."""
    ind, fac = _download(INDUSTRIES), _download(FACTORS)
    return {**{c: ind[c].dropna() for c in ind}, "Mkt": (fac["Mkt-RF"] + fac["RF"]).dropna()}


# Mercati azionari per paese (F-F_International_Countries, dati MSCI/Bloomberg rielaborati da French): rendimento totale
# mensile in dollari e in valuta locale dal 1975, e rapporti annuali E/P e D/P (in %) del mercato. Aggiornato una volta
# l'anno (febbraio, fino a dicembre dell'anno prima): dopo, i rendimenti vengono dagli ETF (src/classify/allocation.py).
# Eurozona = media di Francia, Germania, Italia, Spagna, Olanda (calcolata in allocation.py).
COUNTRIES_FILE = "F-F_International_Countries"
COUNTRIES = {"UK": "UK", "Japan": "Giappone", "Canada": "Canada", "Austrlia": "Australia", "Italy": "Italia",
             "France": "Francia", "Germany": "Germania", "Spain": "Spagna", "Nethrlnd": "Olanda"}


def parse_country(text: str) -> dict[str, pd.Series]:
    """Mkt dei blocchi 'All 4 Data Items Not Reqd': usd e local (mensili, frazioni), ep e dp (annuali, %, indice = dicembre)."""
    rows: dict[str, dict] = {"usd": {}, "local": {}, "ep": {}, "dp": {}}
    block, required = None, False
    for line in text.splitlines():
        if "Dollar Returns" in line:
            block = "usd"
        elif "Local" in line and "Returns" in line:
            block = "local"
        elif line.startswith("Average of Annual"):
            block = "ratio"
        if "Data Items" in line:
            required = "Required" in line
        parts = line.split()
        if required or not parts or not parts[0].isdigit():
            continue
        if block in ("usd", "local") and len(parts[0]) == 6:
            rows[block].setdefault(pd.Timestamp(f"{parts[0][:4]}-{parts[0][4:]}-01"), float(parts[1]) / 100)
        elif block == "ratio" and len(parts[0]) == 4 and len(parts) == 6:
            when = pd.Timestamp(f"{parts[0]}-12-01")
            rows["ep"].setdefault(when, float(parts[3]))
            rows["dp"].setdefault(when, float(parts[5]))
    return {k: pd.Series(v, dtype=float).sort_index().where(lambda s: s > -0.99) for k, v in rows.items()}


def fetch_countries() -> dict[str, pd.Series]:
    """'{paese}_{usd|ep|dp}' per i paesi di COUNTRIES."""
    resp = get_with_retry(URL.format(COUNTRIES_FILE).replace("_CSV", ""), source="french", timeout=90)
    out = {}
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        for code, name in COUNTRIES.items():
            for k, s in parse_country(z.read(f"{code}.Dat").decode("latin-1")).items():
                if k != "local":  # in valuta locale si converte dal dollaro con i cambi FRED (allocation.py)
                    out[f"{name}_{k}"] = s.dropna()
    return out
