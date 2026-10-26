"""Mappa delle occasioni (26/10/2026, pagina Oggi): paesi x classi di asset (azioni, titoli di Stato, oro, liquidita'),
con tre letture per cella:
- punteggio 1-100 della classifica delle classi di asset nel paese (allocation.asset_classes, Verificato): con 4
  classi vale 25, 50, 75 o 100, e "piu' peso" e' sopra allocation.ENTER, cioe' la classe in testa al paese;
- freccia della teoria per la fase del ciclo del paese (asset_allocation.PHASE_ASSETS, Teoria): +1 piu' peso, -1 meno
  peso, 0 neutra (liquidita' non e' mai citata; materie prime non e' una classe di questa classifica);
- tendenza: prezzo della classe in valuta locale contro la media a 10 mesi (pilastro Tendenza della stessa classifica).
Concordanza = quante delle tre letture dicono "piu' peso".
Verifica (scripts/evaluate_opportunities.py, 26/10/2026, regola decisa prima, decidono le 4 finestre di verifica di
allocation.FOLDS, fase point-in-time): la concordanza NON migliora il rendimento a 6 mesi rispetto al solo punteggio.
- Classe in testa al paese con freccia su e tendenza in salita contro classe in testa senza: finestre +1,00% contro
  +0,02% di extra-rendimento medio a 6 mesi (761 e 310 casi), differenza nei mesi con entrambe +0,85 punti, t 0,4;
  finale 2019-2026 +2,73% contro +2,96%, differenza -0,11 punti, t 0,0.
- Portafoglio di una classe per paese: la classe piu' concorde e' quasi sempre quella in testa per punteggio (stessa
  scelta nel 99,8% delle righe delle finestre e nel 100% del finale: la tendenza e' gia' un pilastro del punteggio),
  9,5% l'anno nelle finestre e 13,3% nel finale per entrambe (pesi uguali 7,5% e 9,1%).
- IC a 6 mesi, concordanza poi punteggio contro solo punteggio: finestre +0,207 (t 2,5) contro +0,225 (t 2,9); finale
  +0,275 (t 3,5) contro +0,256 (t 3,1), che non decide.
Per numero di letture a favore (finestre): 0 -0,78%, 1 -0,82%, 2 +1,26%, 3 +1,00%: l'ordine viene dal punteggio.
Esito: la mappa e' descrittiva (READINGS["map"] in src/config/reliability.py); il punteggio resta Verificato.
"""
import pandas as pd

from src.classify.allocation import ASSETS, ENTER, months_of
from src.config.asset_allocation import PHASE_ASSETS

CLASS_NAMES = {"Azioni": "Azioni", "Obbligazioni": "Titoli di Stato", "Liquidità": "Liquidità", "Oro": "Oro"}
PREFIX = {"Azionario": "Azioni", "Titoli di Stato": "Obbligazioni", "Oro": "Oro"}  # voce di PHASE_ASSETS -> classe
TOP = 3  # occasioni in parole sopra la mappa


def theory(phase: str | None) -> dict[str, tuple[int, str]]:
    """Classe -> (+1 piu' peso / -1 meno peso, aggettivo della voce: "ciclico", "difensivo" o ""), per la fase.
    Le classi non citate dalla tabella della fase non compaiono (neutre)."""
    good, bad = PHASE_ASSETS.get(phase, ([], []))
    out = {}
    for items, sign in ((good, 1), (bad, -1)):
        for item in items:
            for prefix, cls in PREFIX.items():
                if item.startswith(prefix):
                    out[cls] = (sign, item.replace("{paese}", "").removeprefix(prefix).strip())
    return out


def arrows(phases: pd.Series) -> pd.DataFrame:
    """Freccia della teoria per riga: phases ha la fase di ogni riga (indice qualsiasi, es. (area, mese)); colonne
    ASSETS, valori +1, -1, 0 (fase mancante = 0)."""
    signs = {p: {c: theory(p).get(c, (0, ""))[0] for c in ASSETS} for p in phases.dropna().unique()}
    return pd.DataFrame([signs.get(p, dict.fromkeys(ASSETS, 0)) for p in phases], index=phases.index, columns=ASSETS)


def agreement(score: pd.DataFrame, arrow: pd.DataFrame, trend: pd.DataFrame) -> pd.DataFrame:
    """Letture che dicono "piu' peso" (0-3): punteggio sopra ENTER, freccia su, tendenza positiva. NaN senza punteggio."""
    out = (score > ENTER).astype(int) + (arrow > 0).astype(int) + (trend > 0).astype(int)
    return out.where(score.notna())


def cells(score: pd.Series, prob: pd.Series, trend: pd.Series, phase: str | None) -> list[dict]:
    """Celle di un paese nel mese: una per classe con punteggio, nell'ordine di ASSETS."""
    th = theory(phase)
    out = []
    for c in ASSETS:
        if pd.isna(score.get(c)):
            continue
        sign, adj = th.get(c, (0, ""))
        up = None if pd.isna(trend.get(c)) else bool(trend[c] > 0)
        out.append({"classe": c, "nome": CLASS_NAMES[c], "punteggio": float(score[c]), "prob": float(prob[c]),
                    "freccia": sign, "aggettivo": adj, "in_salita": up,
                    "concordanza": int(score[c] > ENTER) + int(sign > 0) + int(bool(up))})
    return out


def grid(score: pd.DataFrame, prob: pd.DataFrame, trend: pd.DataFrame,
         phases: dict[str, str | None]) -> tuple[pd.Timestamp | None, dict[str, list[dict]]]:
    """Mappa dell'ultimo mese con punteggio: celle per paese, nell'ordine di phases (paese -> fase del ciclo di oggi).
    score, prob: classifica delle classi di asset (indice (area, mese)); trend: il suo pilastro Tendenza grezzo."""
    s = score.dropna(how="all")
    if s.empty:
        return None, {}
    month = months_of(s.index).max()
    out = {}
    for area, phase in phases.items():
        if (area, month) in s.index:
            out[area] = cells(s.loc[(area, month)], prob.loc[(area, month)], trend.loc[(area, month)], phase)
    return month, out


def best(grid: dict[str, list[dict]], k: int = TOP) -> list[tuple[str, dict]]:
    """Le k occasioni migliori fra tutti i paesi: piu' letture concordi, poi probabilita' piu' alta. Solo celle con
    punteggio in testa al paese o almeno due letture a favore."""
    flat = [(area, c) for area, cs in grid.items() for c in cs if c["punteggio"] > ENTER or c["concordanza"] >= 2]
    return sorted(flat, key=lambda x: (-x[1]["concordanza"], -x[1]["prob"]))[:k]


def sentence(area: str, c: dict) -> str:
    """Una occasione in parole: "Oro · USA: teoria ▲, in salita, punteggio 100"."""
    arrow = {1: "teoria ▲", -1: "teoria ▼", 0: "teoria neutra"}[c["freccia"]]
    if c["aggettivo"] and c["freccia"]:
        arrow += f" ({c['aggettivo']})"
    trend = "tendenza n/d" if c["in_salita"] is None else "in salita" if c["in_salita"] else "in calo"
    return f"{c['nome']} · {area}: {arrow}, {trend}, punteggio {c['punteggio']:.0f}"
