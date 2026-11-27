"""Macro Score 0-100 della Overview (27/11/2026, metodo scelto dall'utente: composito OCSE).

Per ogni area tre indagini mensili OCSE, confrontabili fra paesi:
- leading indicator composito (CLI, area in cache = paese, indicatore "cli");
- fiducia delle imprese (BCI, area "Allocazione", indicatore "<paese>_bci");
- fiducia dei consumatori (CCI, area "Allocazione", indicatore "<paese>_cci").
Ogni serie diventa il percentile del suo ultimo valore sugli ultimi WINDOW_MONTHS mesi della stessa serie (solo dati
fino a quel mese, niente look-ahead sul livello). Il punteggio e' la media dei percentili disponibili, con almeno
MIN_COMPONENTS componenti. 50 = situazione tipica del decennio per quel paese, non "crescita al 50%".
Emergenti = media di Cina e India; Globale = media delle aree con punteggio nel mese (pesi uguali, niente PIL).

Descrittivo: misura il clima congiunturale rispetto alla storia recente del paese. Non e' verificato come previsione
di rendimenti e non entra nella classificazione di regime e fase (src/classify/assess.py).
Limite: le serie OCSE sono riviste, quindi lo storico mostrato non e' esattamente quello letto all'epoca.
"""
import pandas as pd

WINDOW_MONTHS = 120  # percentile sul decennio precedente
MIN_MONTHS = 60  # niente percentile con meno di 5 anni di storia
MIN_COMPONENTS = 2  # su 3
FILL_MONTHS = 3  # un'indagine pubblicata in ritardo vale al massimo 3 mesi (India BCI esce tardi)
EMERGING = ("Cina", "India")
MIN_GLOBAL_SHARE = 0.5  # Globale solo se almeno meta' delle aree ha un punteggio nel mese

COMPONENT_NAMES = {"cli": "Leading indicator OCSE", "bci": "Fiducia imprese", "cci": "Fiducia consumatori"}


def components(area: str, read) -> dict[str, pd.Series]:
    """Le tre serie grezze dell'area; read(area, indicatore) -> pd.Series."""
    return {"cli": read(area, "cli"), "bci": read("Allocazione", f"{area}_bci"), "cci": read("Allocazione", f"{area}_cci")}


def monthly(s: pd.Series) -> pd.Series:
    s = s.dropna()
    if s.empty:
        return s
    s.index = pd.to_datetime(s.index)
    return s.resample("MS").last().dropna()


def rolling_percentile(s: pd.Series) -> pd.Series:
    """Percentile 0-100 di ogni valore sui WINDOW_MONTHS mesi fino a quel mese compreso."""
    s = monthly(s)
    if len(s) < MIN_MONTHS:
        return pd.Series(dtype=float)
    pct = s.rolling(WINDOW_MONTHS, min_periods=MIN_MONTHS).apply(lambda w: (w <= w[-1]).mean() * 100, raw=True)
    return pct.dropna()


def area_history(raw: dict[str, pd.Series]) -> pd.DataFrame:
    """Percentili delle componenti e punteggio mensile dell'area (colonna "score")."""
    pct = pd.DataFrame({k: rolling_percentile(v) for k, v in raw.items() if v is not None and not v.empty})
    if pct.empty:
        return pct
    pct = pct.sort_index()
    pct = pct.reindex(pd.date_range(pct.index.min(), pct.index.max(), freq="MS")).ffill(limit=FILL_MONTHS)
    score = pct.mean(axis=1).where(pct.notna().sum(axis=1) >= MIN_COMPONENTS)
    return pct.assign(score=score).dropna(subset=["score"])


def aggregate(scores: dict[str, pd.Series], min_share: float = 0.0) -> pd.Series:
    """Media a pesi uguali dei punteggi mensili; mesi con meno di min_share delle aree esclusi."""
    df = pd.DataFrame({a: s for a, s in scores.items() if not s.empty})
    if df.empty:
        return pd.Series(dtype=float)
    df = df.ffill(limit=FILL_MONTHS)
    need = max(1, int(round(min_share * len(scores))))
    return df.mean(axis=1).where(df.notna().sum(axis=1) >= need).dropna()


def economies(areas: list[str], read) -> dict[str, dict]:
    """Punteggi delle cinque card: USA, Eurozona, Italia, Emergenti, Globale, piu' ogni area singola.
    Valore: {"history": pd.Series mensile, "components": {nome: percentile ultimo}, "month": ultimo mese}."""
    hist = {a: area_history(components(a, read)) for a in areas}
    scores = {a: h["score"] for a, h in hist.items() if not h.empty}
    out = {}
    for a, h in hist.items():
        if h.empty:
            continue
        last = h.iloc[-1]
        out[a] = {"history": h["score"], "month": h.index[-1],
                  "components": {k: float(last[k]) for k in COMPONENT_NAMES if k in h and pd.notna(last[k])}}
    em = aggregate({a: scores[a] for a in EMERGING if a in scores})
    if not em.empty:
        out["Emergenti"] = {"history": em, "month": em.index[-1], "members": [a for a in EMERGING if a in scores]}
    world = aggregate(scores, MIN_GLOBAL_SHARE)
    if not world.empty:
        out["Globale"] = {"history": world, "month": world.index[-1], "members": list(scores)}
    return out


def summary(item: dict) -> dict:
    """Ultimo punteggio arrotondato, variazione sul mese prima e storico 36 mesi per grafico e trend."""
    s = item["history"].dropna()
    score = round(float(s.iloc[-1]))
    delta = None if len(s) < 2 else score - round(float(s.iloc[-2]))
    return {"score": score, "delta": delta, "month": f"{s.index[-1]:%Y-%m}",
            "history": [[f"{d:%Y-%m}", round(float(v), 1)] for d, v in s.tail(36).items()],
            **({"components": {COMPONENT_NAMES[k]: round(v) for k, v in item["components"].items()}} if "components" in item else {}),
            **({"members": item["members"]} if "members" in item else {})}


def band(score: float) -> str:
    """Lettura del punteggio: sopra 60 solido, sotto 40 debole."""
    return "solido" if score >= 60 else "debole" if score < 40 else "nella media"


# --- Macro Heatmap della Overview: segnali +1 / 0 / -1 per paese, descrittivi ---
GROWTH_BAND = 0.5  # PIL annuo oltre +-0,5 punti dalla mediana dei 10 anni del paese
INFLATION_TARGET = {"India": 4.0, "Cina": 3.0}  # obiettivi delle banche centrali; gli altri 2%
INFLATION_NEAR, INFLATION_FAR = 1.0, 2.5  # entro 1 punto dall'obiettivo positivo, oltre 2,5 negativo
CONFIDENCE_HIGH, CONFIDENCE_LOW = 60, 40  # percentile decennale della fiducia delle imprese
UNEMPLOYMENT_MONTHS = 6
UNEMPLOYMENT_DOWN, UNEMPLOYMENT_UP = -0.2, 0.3  # variazione del tasso di disoccupazione in 6 mesi, punti
HEAT_COLUMNS = ["PIL", "Inflazione", "Fiducia imprese", "Lavoro", "Borsa"]


def _num(x: float, sign: bool = False) -> str:
    return f"{x:{'+' if sign else ''}.1f}".replace(".", ",").replace("-", "−")


def heat_row(area: str, read, bci_pct: float | None, trend: dict | None) -> dict[str, dict | None]:
    """Segnale e testo per colonna; None se manca il dato."""
    row: dict[str, dict | None] = dict.fromkeys(HEAT_COLUMNS)
    g = read(area, "growth_yoy").dropna()
    if len(g) >= 8:
        med = float(g[g.index >= g.index[-1] - pd.DateOffset(years=10)].median())
        diff = float(g.iloc[-1]) - med
        row["PIL"] = {"signal": 1 if diff > GROWTH_BAND else -1 if diff < -GROWTH_BAND else 0,
                      "text": f"{_num(g.iloc[-1])}% annuo, mediana 10 anni {_num(med)}% ({g.index[-1]:%m/%Y})"}
    i = read(area, "inflation_yoy").dropna()
    if not i.empty:
        target = INFLATION_TARGET.get(area, 2.0)
        gap = abs(float(i.iloc[-1]) - target)
        row["Inflazione"] = {"signal": 1 if gap <= INFLATION_NEAR else -1 if gap > INFLATION_FAR else 0,
                             "text": f"{_num(i.iloc[-1])}% annuo, obiettivo {_num(target)}% ({i.index[-1]:%m/%Y})"}
    if bci_pct is not None:
        row["Fiducia imprese"] = {"signal": 1 if bci_pct >= CONFIDENCE_HIGH else -1 if bci_pct < CONFIDENCE_LOW else 0,
                                  "text": f"Percentile {bci_pct:.0f} sui 10 anni (OCSE)"}
    u = monthly(read(area, "unemployment_rate"))
    if len(u) > UNEMPLOYMENT_MONTHS:
        d = float(u.iloc[-1] - u.iloc[-1 - UNEMPLOYMENT_MONTHS])
        row["Lavoro"] = {"signal": 1 if d <= UNEMPLOYMENT_DOWN else -1 if d >= UNEMPLOYMENT_UP else 0,
                         "text": f"Disoccupazione {_num(u.iloc[-1])}%, {_num(d, True)} punti in 6 mesi ({u.index[-1]:%m/%Y})"}
    if trend:
        row["Borsa"] = {"signal": 1 if trend["positive"] else -1,
                        "text": f"{_num(trend['dist_pct'], True)}% dalla media a 10 mesi ({trend['month']})"}
    return row
