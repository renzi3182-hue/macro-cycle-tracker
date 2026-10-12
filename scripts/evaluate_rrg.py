"""Verifica della rotazione relativa (src/classify/rrg.py): il quadrante dice qualcosa sui periodi dopo?

1. Mensile, settori: quadrante a mese chiuso, poi rendimento del settore meno SPY nei 1 e 3 mesi successivi
   (ETF rettificati per dividendi). Strategia di prova: pesi uguali ai settori in "Guida", ribilanciata ogni mese.
2. Settimanale, tutti i gruppi di UNIVERSE: quadrante a fine settimana, extra-rendimento su SPY nelle 4 e 13
   settimane dopo, per quadrante.
Uso: py -3.12 scripts/evaluate_rrg.py   (mensili da data/cache.db, giornalieri scaricati da Yahoo)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import math

import pandas as pd

from src.classify.rrg import BENCHMARK, GROUPS, MOMENTUM_WEEKS, QUADRANTS, SECTORS, TREND_WEEKS, quadrant, rrg, weekly_prices
from src.classify.score import ASSET_AREA, UNIVERSE, complete_months, monthly_prices
from src.data import cache
from src.data.fetch_market import fetch_yahoo

WEEKS_SHORT, WEEKS_LONG = 4, 13


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
    ok = ratio.notna() & mom.notna()  # i settori nascono in anni diversi (XLRE 2015, XLC 2018): pesi uguali fra i disponibili
    idx = ratio.index[ok.any(axis=1)][:-1]
    held = nxt[ratio.columns].where(lead).loc[idx].mean(axis=1).fillna(nxt[BENCHMARK].loc[idx])
    print(f"Strategie, {idx[0]:%Y-%m} -> {idx[-1]:%Y-%m}, mese dopo il segnale, niente costi:")
    print(f"  SPY:                   {perf(nxt[BENCHMARK].loc[idx])}")
    print(f"  settori pesi uguali:   {perf(nxt[ratio.columns].where(ok).loc[idx].mean(axis=1))}")
    print(f"  settori in Guida:      {perf(held)}  (in media {lead.loc[idx].sum(axis=1).mean():.1f} settori)")
    weekly()


def weekly() -> None:
    wk = weekly_prices(pd.DataFrame({t: fetch_yahoo(t, "max", "1d", adjusted=True) for t in UNIVERSE})).iloc[:-1]  # settimana in corso esclusa
    fwd = {h: wk.shift(-h) / wk - 1 for h in (WEEKS_SHORT, WEEKS_LONG)}
    order = list(QUADRANTS.values())
    for group, members in {"Tutti": [t for g in GROUPS.values() for t in g], **GROUPS}.items():
        ratio, mom = rrg(wk, members, TREND_WEEKS, MOMENTUM_WEEKS)
        q = pd.DataFrame({t: [quadrant(x, y) if pd.notna(x) and pd.notna(y) else None for x, y in zip(ratio[t], mom[t])]
                          for t in ratio}, index=ratio.index)
        long = pd.DataFrame({"q": q.stack(), **{f"ex{h}": (f[ratio.columns].sub(f[BENCHMARK], axis=0)).stack() * 100
                                                for h, f in fwd.items()}}).dropna()
        long["dopo2014"] = long.index.get_level_values(0) >= "2014"
        t = long.groupby("q").agg(casi=("q", "size"), **{f"ex{h}": (f"ex{h}", "mean") for h in fwd},
                                  sopra=(f"ex{WEEKS_LONG}", lambda x: (x > 0).mean() * 100))
        print(f"\nSettimanale, {group} ({', '.join(ratio.columns)}), {long.index[0][0]:%Y-%m} -> {long.index[-1][0]:%Y-%m}: "
              f"extra-rendimento medio su SPY a {WEEKS_SHORT} e {WEEKS_LONG} settimane (%)")
        print(t.reindex(order).round(2).to_string())
        for a, b in (("Guida", "Arretra"), ("Migliora", "Indebolisce")):
            for label, sub in (("tutto", long), ("<2014", long[~long.dopo2014]), (">=2014", long[long.dopo2014])):
                x, y = (sub.loc[sub.q == k, f"ex{WEEKS_LONG}"] for k in (a, b))
                # osservazioni sovrapposte (13 settimane): t diviso per la radice di 13
                tt = (x.mean() - y.mean()) / math.sqrt(x.var() / len(x) + y.var() / len(y)) / math.sqrt(WEEKS_LONG)
                print(f"  {a} - {b} a {WEEKS_LONG} sett., {label}: {(x.mean() - y.mean()):+.2f} pp, t ~ {tt:.1f}")


if __name__ == "__main__":
    main()
