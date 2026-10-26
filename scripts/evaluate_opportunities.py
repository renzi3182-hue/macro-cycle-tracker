"""Verifica della mappa delle occasioni (src/classify/opportunities.py): la concordanza delle tre letture (punteggio
delle classi di asset nel paese, freccia della teoria per la fase del ciclo, tendenza a 10 mesi) migliora il
rendimento a 6 mesi rispetto al solo punteggio?

Stesse regole di scripts/evaluate_allocation.py: punteggio fuori campione nelle 4 finestre di verifica (fold_prob,
pesi fermi all'inizio di ogni finestra) e nel periodo finale 2019-2026 (holdout_prob, pesi di fine 2018), che si
riporta e non decide. Fase del ciclo di ogni paese come si leggeva allora (assess.point_in_time_history: dati rivisti,
con i ritardi di pubblicazione). Extra-rendimento a 6 mesi contro la media delle 4 classi del paese, in valuta locale.

Regola decisa prima di guardare i risultati: la concordanza migliora se nelle finestre
1. le classi in testa al paese (punteggio sopra allocation.ENTER) con freccia su e tendenza in salita hanno un
   extra-rendimento a 6 mesi piu' alto di quelle in testa senza concordanza, con t >= 2 (mesi indipendenti = mesi / 6);
2. il portafoglio della classe piu' concorde per paese (a parita' la piu' probabile) batte quello della classe in
   testa per punteggio (rendimento annuo, ribilanciamento mensile, senza costi).
Se no, la mappa e' descrittiva e la pagina lo dice.
Uso, da root del monorepo: .venv/Scripts/python code/macro-cycle-tracker/scripts/evaluate_opportunities.py
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src.classify import allocation as al
from src.classify import opportunities as opp
from src.classify.assess import USED_INPUTS, point_in_time_history
from src.classify.score import ASSET_AREA, HISTORY_AREA, monthly_prices
from src.data import cache


def load() -> tuple[dict, pd.DataFrame, pd.Series]:
    """Pannello delle classi di asset, probabilita' fuori campione (finestre + periodo finale) e fase point-in-time."""
    read = cache.read_indicator_series
    asset_px = monthly_prices({t: read(ASSET_AREA, t) for t in al.COUNTRY_ETF.values()})
    p = al.asset_classes(al.load(read, asset_px, read(HISTORY_AREA, "Mkt")))
    ex, feats, mi = p["excess"], p["feats"], p["min_items"]
    prob = al.fold_prob(feats, ex, min_items=mi).combine_first(al.holdout_prob(feats, ex, min_items=mi)[0]).reindex_like(ex)
    hist = {a: point_in_time_history(a, {n: read(a, n) for n in USED_INPUTS}) for a in al.AREAS}
    phase = pd.Series([hist[a]["phase"].get(m) if hist[a] is not None else None for a, m in ex.index], index=ex.index)
    return p, prob, phase


def t_by_month(diff: pd.Series) -> tuple[float, float, int]:
    """Media di una serie mensile e t su n/HORIZON mesi indipendenti (esiti a 6 mesi sovrapposti)."""
    d = diff.dropna()
    n = len(d)
    return (d.mean(), d.mean() / d.std() * math.sqrt(n / al.HORIZON), n) if n > 2 and d.std() > 0 else (np.nan, np.nan, n)


def pick_returns(choice: pd.DataFrame, p: dict) -> tuple[pd.Series, pd.Series]:
    """Rendimento del mese dopo e extra-rendimento a 6 mesi della classe scelta (True) per riga, media fra i paesi."""
    r1, ex = p["ret1"].reindex_like(choice), p["excess"].reindex_like(choice)
    keep = choice.any(axis=1)
    return (al.by_month(r1.where(choice).sum(axis=1, min_count=1)[keep]),
            al.by_month(ex.where(choice).sum(axis=1, min_count=1)[keep]))


def report(label: str, sel, p: dict, prob: pd.DataFrame, phase: pd.Series) -> None:
    ex = sel(p["excess"])
    pr = sel(prob).where(ex.notna())
    score = al.to_score(pr)
    arrow = opp.arrows(sel(phase.to_frame("f"))["f"]).reindex_like(ex)
    trend = sel(p["raw"]["Tendenza"]).reindex_like(ex)
    agree = opp.agreement(score, arrow, trend)
    has_phase = sel(phase.to_frame("f"))["f"].notna().reindex(ex.index)
    hp = has_phase.to_numpy()[:, None]  # righe paese-mese con la fase del ciclo
    top = (score > al.ENTER) & hp
    conc = top & (arrow > 0) & (trend > 0)
    print(f"\n=== {label} ({al.months_of(ex.index).min():%Y-%m} -> {al.months_of(ex.index).max():%Y-%m}, "
          f"righe paese-mese con fase {int(has_phase.sum())}) ===")

    # 1. classi in testa: con concordanza contro senza
    by = lambda mask: al.by_month(ex.where(mask).mean(axis=1))
    c_mean, n_mean = by(conc), by(top & ~conc)
    mu, t, n = t_by_month(c_mean - n_mean)
    print(f"  Classe in testa al paese, extra-rendimento medio a 6 mesi: con concordanza {c_mean.mean() * 100:+.2f}% "
          f"({int(conc.sum().sum())} casi), senza {n_mean.mean() * 100:+.2f}% ({int((top & ~conc).sum().sum())} casi); "
          f"differenza {mu * 100:+.2f} punti, t {t:+.1f} ({n} mesi con entrambe)")
    for k in range(4):
        m = (agree == k) & hp
        print(f"    {k} letture a favore: extra-rendimento medio {by(m).mean() * 100:+.2f}% ({int(m.sum().sum())} casi)")

    # 2. portafogli: classe in testa per punteggio contro classe piu' concorde (a parita' la piu' probabile)
    key = agree * 10 + pr  # concordanza prima, poi probabilita'
    rows = key.notna().any(axis=1) & has_phase
    by_score = pr.eq(pr.max(axis=1), axis=0) & rows.to_numpy()[:, None]
    by_agree = key.eq(key.max(axis=1), axis=0) & rows.to_numpy()[:, None]
    same = (by_score & by_agree).any(axis=1)[rows].mean() * 100
    eq_r1 = al.by_month(p["ret1"].reindex_like(ex).where(pr.notna()).mean(axis=1)[rows])
    out = []
    for name, choice in (("solo punteggio", by_score), ("concordanza", by_agree)):
        r1, ex6 = pick_returns(choice, p)
        out.append(f"{name} {al.annual(r1):.1f}% l'anno (calo massimo {al.max_drawdown(r1):.1f}%, extra a 6 mesi "
                   f"{ex6.mean() * 100:+.2f}%)")
    print("  Portafoglio, una classe per paese: " + " · ".join(out) + f" · pesi uguali {al.annual(eq_r1):.1f}%"
          f" · stessa scelta nel {same:.1f}% delle righe")

    # 3. IC: solo punteggio contro punteggio con la concordanza davanti
    keep = has_phase.to_numpy()
    print(f"  IC a 6 mesi: solo punteggio {fmt(al.ic(pr[keep], ex[keep]))} · concordanza poi punteggio "
          f"{fmt(al.ic(key[keep], ex[keep]))}")


def fmt(res) -> str:
    mu, t, n = res
    return f"{mu:+.3f} (t {t:+.1f}, {n} mesi)"


def main() -> None:
    p, prob, phase = load()
    win = lambda df: pd.concat([df[(al.months_of(df.index) >= s) & (al.months_of(df.index) <= e)] for _, s, e in al.FOLDS])
    final = lambda df: df[al.months_of(df.index) >= al.HOLDOUT_START]
    report("FINESTRE DI VERIFICA 1995-97, 2002-04, 2009-11, 2016-18 (decidono)", win, p, prob, phase)
    report("PERIODO FINALE 2019-2026 (si riporta, non decide)", final, p, prob, phase)


if __name__ == "__main__":
    main()
