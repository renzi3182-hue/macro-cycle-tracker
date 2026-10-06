"""Verifica del Risk On/Off (src/classify/risk.py): il punteggio di fine mese dice qualcosa sul mese dopo dell'S&P 500?

Punteggio point-in-time (percentili solo sul passato, ampiezza a mese chiuso), confronto con il mese/i 3 mesi successivi
di SPY (rettificato per dividendi). Strategia di prova: SPY se il punteggio e' sopra una soglia, altrimenti SHY;
termine di confronto il solo filtro di tendenza su SPY (stessa regola dell'ampiezza, un asset solo).
Uso: py -3.12 scripts/evaluate_risk.py   (dati da data/cache.db)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import math

import pandas as pd

from src.classify.risk import BANDS, components, risk_score
from src.classify.score import ASSET_AREA, TREND_MONTHS, UNIVERSE, complete_months, monthly_prices
from src.data import cache


def perf(r: pd.Series) -> str:
    r = r.dropna()
    w = (1 + r).cumprod()
    return (f"{(w.iloc[-1] ** (12 / len(r)) - 1) * 100:5.1f}%/anno, vol {r.std() * math.sqrt(12) * 100:4.1f}%, "
            f"DD {(w / w.cummax() - 1).min() * 100:4.0f}%")


def main() -> None:
    px = complete_months(monthly_prices({t: cache.read_indicator_series(ASSET_AREA, t) for t in UNIVERSE}))
    comp = components(cache.read_indicator_series("Mercati", "vix"), cache.read_indicator_series("USA", "credit_spread"), px)
    comp = comp.loc[:px.index[-1]]
    score = risk_score(comp).dropna()
    r = px["SPY"].pct_change(fill_method=None)
    cash = px["SHY"].pct_change(fill_method=None).fillna(0)
    d = pd.DataFrame({"score": score, "r1": r.shift(-1), "r3": px["SPY"].shift(-3) / px["SPY"] - 1,
                      "abs1": r.shift(-1).abs()}).dropna(subset=["score"])
    print(f"Punteggio {d.index[0]:%Y-%m} -> {d.index[-1]:%Y-%m}, {len(d)} mesi; ultimo {score.iloc[-1]:.0f} "
          f"({', '.join(f'{k} {v:.0f}' for k, v in comp.iloc[-1].items())})")
    print("Correlazione fra componenti:\n", comp.dropna().corr().round(2).to_string())

    d["fascia"] = pd.cut(d["score"], BANDS, include_lowest=True)
    t = d.groupby("fascia", observed=True).agg(mesi=("r1", "count"), r1_med=("r1", "median"), r1_pos=("r1", lambda x: (x > 0).mean()),
                                                r3_med=("r3", "median"), mossa_media=("abs1", "mean"))
    print("\nSPY nel mese/3 mesi dopo, per fascia (mossa_media = |rendimento| del mese dopo, proxy della volatilita'):")
    print((t * [1, 100, 100, 100, 100]).round(1).to_string())
    print(f"\nCorrelazione punteggio vs r1 {d['score'].corr(d['r1']):+.3f}, vs r3 {d['score'].corr(d['r3']):+.3f}, "
          f"vs |r1| {d['score'].corr(d['abs1']):+.3f}")
    for name, sub in {"<2014": d.loc[:"2013-12"], ">=2014": d.loc["2014-01":]}.items():
        print(f"- {name}: corr r3 {sub['score'].corr(sub['r3']):+.3f}, corr |r1| {sub['score'].corr(sub['abs1']):+.3f}, mesi {len(sub)}")

    idx = d.index
    nxt_r, nxt_c = r.shift(-1).loc[idx], cash.shift(-1).loc[idx]
    trend_on = (px["SPY"] > px["SPY"].rolling(TREND_MONTHS).mean()).loc[idx]
    print(f"\nStrategie, mese dopo il segnale, {idx[0]:%Y-%m} -> {idx[-1]:%Y-%m} (niente costi, SHY come cash):")
    print(f"  SPY sempre:               {perf(nxt_r)}")
    print(f"  SPY se sopra media 10m:   {perf(nxt_r.where(trend_on, nxt_c))}  mesi fuori {(~trend_on).mean() * 100:.0f}%")
    for th in (20, 40, 50):
        on = d["score"] > th
        print(f"  SPY se Risk On/Off > {th}:  {perf(nxt_r.where(on, nxt_c))}  mesi fuori {(~on).mean() * 100:.0f}%")


if __name__ == "__main__":
    main()
