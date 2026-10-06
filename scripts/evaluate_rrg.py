"""Verifica della rotazione settori (src/classify/rrg.py): il quadrante di fine mese dice qualcosa sui mesi dopo?

Per ogni settore e mese: quadrante a mese chiuso, poi rendimento del settore meno SPY nei 1 e 3 mesi successivi
(ETF rettificati per dividendi). Strategia di prova: pesi uguali ai settori in "Guida", ribilanciata ogni mese.
Uso: py -3.12 scripts/evaluate_rrg.py   (dati da data/cache.db)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import math

import pandas as pd

from src.classify.rrg import BENCHMARK, QUADRANTS, SECTORS, quadrant, rrg
from src.classify.score import ASSET_AREA, UNIVERSE, complete_months, monthly_prices
from src.data import cache


def perf(r: pd.Series) -> str:
    r = r.dropna()
    w = (1 + r).cumprod()
    return f"{(w.iloc[-1] ** (12 / len(r)) - 1) * 100:5.1f}%/anno, DD {(w / w.cummax() - 1).min() * 100:4.0f}%"


def main() -> None:
    px = complete_months(monthly_prices({t: cache.read_indicator_series(ASSET_AREA, t) for t in UNIVERSE}))
    ratio, mom = rrg(px)
    r = px.pct_change(fill_method=None)
    rows = []
    for t in ratio:
        ex1 = r[t].shift(-1) - r[BENCHMARK].shift(-1)
        ex3 = (px[t].shift(-3) / px[t] - 1) - (px[BENCHMARK].shift(-3) / px[BENCHMARK] - 1)
        for d in ratio.index:
            if pd.notna(ratio.at[d, t]) and pd.notna(mom.at[d, t]):
                rows.append({"mese": d, "settore": t, "quadrante": quadrant(ratio.at[d, t], mom.at[d, t]),
                             "ex1": ex1[d], "ex3": ex3[d]})
    df = pd.DataFrame(rows).dropna()
    print(f"{df['mese'].min():%Y-%m} -> {df['mese'].max():%Y-%m}, {len(df)} casi, {len(SECTORS)} settori\n")
    order = list(QUADRANTS.values())
    for name, sub in {"tutto": df, "<2014": df[df["mese"] < "2014"], ">=2014": df[df["mese"] >= "2014"]}.items():
        t = sub.groupby("quadrante").agg(casi=("ex3", "count"), ex1_media=("ex1", "mean"), ex3_media=("ex3", "mean"),
                                         ex3_mediana=("ex3", "median"), sopra=("ex3", lambda x: (x > 0).mean()))
        t[["ex1_media", "ex3_media", "ex3_mediana", "sopra"]] *= 100
        print(f"Extra-rendimento vs SPY (%), {name}:\n{t.reindex(order).round(2).to_string()}\n")
        # t-stat grezzo Guida vs Arretra a 3 mesi (osservazioni sovrapposte: sovrastima)
        a, b = sub.loc[sub["quadrante"] == "Guida", "ex3"], sub.loc[sub["quadrante"] == "Arretra", "ex3"]
        print(f"  Guida - Arretra: {(a.mean() - b.mean()) * 100:+.2f} pp, t ~ "
              f"{(a.mean() - b.mean()) / math.sqrt(a.var() / len(a) + b.var() / len(b)):.1f}\n")

    nxt = r.shift(-1)
    lead = pd.DataFrame({t: [quadrant(x, y) == "Guida" if pd.notna(x) and pd.notna(y) else False
                             for x, y in zip(ratio[t], mom[t])] for t in ratio}, index=ratio.index)
    valid = ratio.notna().all(axis=1) & mom.notna().all(axis=1)
    idx = ratio.index[valid][:-1]
    held = nxt[ratio.columns].where(lead).loc[idx].mean(axis=1).fillna(nxt[BENCHMARK].loc[idx])
    print(f"Strategie, {idx[0]:%Y-%m} -> {idx[-1]:%Y-%m}, mese dopo il segnale, niente costi:")
    print(f"  SPY:                   {perf(nxt[BENCHMARK].loc[idx])}")
    print(f"  9 settori pesi uguali: {perf(nxt[ratio.columns].loc[idx].mean(axis=1))}")
    print(f"  settori in Guida:      {perf(held)}  (in media {lead.loc[idx].sum(axis=1).mean():.1f} settori)")


if __name__ == "__main__":
    main()
