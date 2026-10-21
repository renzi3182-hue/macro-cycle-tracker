"""Verifica delle classifiche di lungo periodo (src/classify/allocation.py): paesi, classi di asset nel paese, valute.

Metodo (come le slide dell'app di riferimento):
- sviluppo e verifica a rotazione: in 4 finestre (1995-97, 2002-04, 2009-11, 2016-18) i pesi si stimano su tutto
  quello che c'e' prima e si provano sulla finestra senza ristimare; le scelte si fanno solo qui (--sviluppo);
- periodo finale 2019-2026 bloccato: pesi stimati con gli esiti noti a fine 2018, fissi, un solo giro;
- IC (Spearman del mese, punteggio -> extra-rendimento a 6 mesi) con t su n/6 mesi indipendenti;
- portafogli: i migliori k ribilanciati ogni mese contro 500 portafogli presi a caso fra gli stessi elementi e
  contro benchmark statici (pesi uguali, USA, 60/40, All Weather). Niente costi.
Niente survivorship bias: l'universo (9 aree, 4 classi, 8 valute) e' fisso e deciso prima; le serie partono quando
esistono (Cina 2004, India 1997), nessun elemento sparisce. Limite: India prima del 2012 senza dividendi; dati macro
nell'ultima revisione (la fiducia OCSE e' destagionalizzata e un po' rivista), con un mese di ritardo di pubblicazione.

Uso, da root del monorepo: .venv/Scripts/python code/macro-cycle-tracker/scripts/evaluate_allocation.py [--sviluppo]
(legge data/cache.db; serve un run completo di src/scheduler/update_data)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src.classify import allocation as al
from src.classify.score import ASSET_AREA, HISTORY_AREA, monthly_prices
from src.data import cache

TOP = {"Paesi": 3, "Classi di asset": 1, "Valute": 2}


def load() -> dict:
    read = cache.read_indicator_series
    asset_px = monthly_prices({t: read(ASSET_AREA, t) for t in al.COUNTRY_ETF.values()})
    d = al.load(read, asset_px, read(HISTORY_AREA, "Mkt"))
    return {"Paesi": al.countries(d), "Classi di asset": al.asset_classes(d), "Valute": al.currencies(d)}


def fmt_ic(res) -> str:
    mu, t, n = res
    return f"IC {mu:+.3f} t {t:+.1f} ({n} mesi)" if n >= 3 else "n/d"


def in_window(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    m = al.months_of(df.index)
    return df[(m >= start) & (m <= end)]


def development(name: str, p: dict) -> None:
    ex, feats, mi = p["excess"], p["feats"], p["min_items"]
    print(f"\n=== {name}: sviluppo e verifica a rotazione (finestre di verifica, pesi fermi all'inizio) ===")
    prob = al.fold_prob(feats, ex, min_items=mi)
    for _, start, end in al.FOLDS:
        print(f"  {start[:4]}-{end[:4]}  modello {fmt_ic(al.ic(in_window(prob, start, end), in_window(ex, start, end)))}")
    print(f"  tutte    modello {fmt_ic(al.ic(prob, ex))}")
    windows = lambda df: pd.concat([in_window(df, s, e) for _, s, e in al.FOLDS])
    print("  Pilastri da soli (valore orientato, finestre di verifica):")
    for k, v in p["raw"].items():
        print(f"    {k:12s} {fmt_ic(al.ic(windows(v.reindex_like(ex).where(ex.notna())), windows(ex)))}")
    print("  Senza un pilastro (solo diagnostica, non usata per scegliere):")
    for k in feats:
        prob_k = al.fold_prob({j: v for j, v in feats.items() if j != k}, ex, min_items=mi)
        print(f"    senza {k:12s} {fmt_ic(al.ic(prob_k, ex))}")


def benchmarks(name: str, p: dict) -> dict:
    r1 = p["ret1"]
    eq = al.by_month(r1.mean(axis=1))
    if name == "Paesi":
        return {"Pesi uguali 9 aree": eq, "Solo USA": r1["USA"]}
    if name == "Valute":
        return {"Pesi uguali 8 valute": eq, "Solo dollaro": r1["USD"]}
    mix = lambda w: al.by_month(sum(r1[k] * v for k, v in w.items()))
    return {"Pesi uguali 4 classi": eq, "60/40": mix({"Azioni": .6, "Obbligazioni": .4}),
            "All Weather (30/55/15 oro)": mix({"Azioni": .3, "Obbligazioni": .55, "Oro": .15})}


def skip_excess(p: dict) -> pd.DataFrame:
    """Extra-rendimento dal mese t+1 al t+7: controllo contro l'effetto delle medie mensili (decennale e oro sono
    medie del mese, il loro primo mese e' in parte gia' noto a fine t)."""
    def one(px):
        fwd = px.shift(-al.HORIZON - 1) / px.shift(-1) - 1
        return fwd.sub(fwd.mean(axis=1), axis=0)
    px = p["px"]
    out = pd.concat({a: one(px.loc[a]) for a in px.index.get_level_values(0).unique()}) if px.index.nlevels > 1 else one(px)
    return out.where(p["excess"].notna())


def final(name: str, p: dict) -> pd.DataFrame:
    ex, feats, mi, k = p["excess"], p["feats"], p["min_items"], TOP[name]
    prob, w = al.holdout_prob(feats, ex, min_items=mi)
    score = al.to_score(prob)
    live = al.model(p)["score"]
    live = live[al.months_of(live.index) >= al.HOLDOUT_START]
    print(f"\n=== {name}: TEST FINALE {al.HOLDOUT_START[:4]}-oggi (pesi di fine 2018, mai ristimati) ===")
    print("  Pesi:", ", ".join(f"{i} {v:.2f}" for i, v in w.items()))
    print(f"  Modello      {fmt_ic(al.ic(score, ex))}")
    print(f"  Ristimato ogni gennaio (come nell'app) {fmt_ic(al.ic(live, ex))}")
    print(f"  Controllo, esito dal mese dopo {fmt_ic(al.ic(score, skip_excess(p).reindex_like(score)))}")
    for j, v in p["raw"].items():
        print(f"    {j:12s} {fmt_ic(al.ic(v.reindex_like(score).where(score.notna()), ex.reindex_like(score)))}")
    strat = al.top_returns(score, p["ret1"], k)
    months = strat.dropna().index
    rows = {f"Migliori {k}": strat, **benchmarks(name, p)}
    out = pd.DataFrame({n: {"rend. annuo %": al.annual(r.reindex(months)), "drawdown %": al.max_drawdown(r.reindex(months))}
                        for n, r in rows.items()}).T
    rnd = al.random_portfolios(score, p["ret1"], k)
    pct = (rnd < out.iloc[0, 0]).mean() * 100
    print(f"  Portafogli {months[0]:%Y-%m} -> {months[-1]:%Y-%m}, ribilanciati ogni mese, senza costi:")
    print(out.round(1).to_string())
    print(f"  500 portafogli a caso ({k} elementi): mediana {np.median(rnd):.1f}%, 5-95% {np.percentile(rnd, 5):.1f}/"
          f"{np.percentile(rnd, 95):.1f}%; i migliori {k} battono il {pct:.0f}% (p = {1 - pct / 100:.2f})")
    return out


def main() -> None:
    panels = load()
    for name, p in panels.items():
        development(name, p)
    if "--sviluppo" in sys.argv:
        return
    for name, p in panels.items():
        final(name, p)


if __name__ == "__main__":
    main()
