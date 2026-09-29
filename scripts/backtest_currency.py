"""Backtest punteggio valute: rebalance a fine mese, rendimento della coppia nel mese dopo.

Point-in-time solo sui tempi di pubblicazione (LAG_DAYS); i dati di crescita/inflazione in cache
sono l'ultima revisione, non le vintage originali. COT in cache = solo ~5 anni.
Uso: python scripts/backtest_currency.py
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src.classify.currency import (
    BUY_ABOVE, CURRENCIES, PAIRS, SELL_BELOW, cot_component, momentum_returns, pair_view, strength_score, vix_component,
)
from src.data import cache

CCY_AREA = {"USD": "USA", "EUR": "Eurozona", "GBP": "UK", "JPY": "Giappone"}
CCY_COT = {"USD": "Dollaro (DXY)", "EUR": "Euro", "GBP": "Sterlina", "JPY": "Yen"}
LAG_DAYS = {"growth": 120, "inflation": 45, "rate": 30}
MIN_COT_WEEKS = 52
MIN_VIX_OBS = 500
HORIZONS = [1, 3, 6, 12]  # mesi; rebalance ogni h mesi = periodi non sovrapposti


def load(area, name):
    return cache.read_indicator_series(area, name)


def asof(series, t, lag=0):
    s = series[series.index <= t - pd.Timedelta(days=lag)]
    return None if s.empty else float(s.iloc[-1])


def pct_expanding(series, t):
    s = series[series.index <= t]
    return float((s <= s.iloc[-1]).mean() * 100), len(s)


def main():
    fx = {n: load("Valute", n).dropna() for n in ("eurusd", "gbpusd", "usdjpy")}
    lvl = pd.DataFrame({"USD": 0.0, "EUR": np.log(fx["eurusd"]), "GBP": np.log(fx["gbpusd"]), "JPY": -np.log(fx["usdjpy"])}).dropna()
    data = {c: {"growth": load(CCY_AREA[c], "growth_yoy"), "infl": load(CCY_AREA[c], "inflation_yoy"),
                "rate": load("Valute", f"rate_{c}"), "cot": load("Mercati", f"cot_{CCY_COT[c]}")} for c in CURRENCIES}
    vix = load("Mercati", "vix")
    month_ends = lvl.groupby(lvl.index.to_period("M")).tail(1).index

    rows = []
    for i, t in enumerate(month_ends):
        if len(lvl[lvl.index <= t]) <= 64:
            continue
        mom = momentum_returns(*(fx[n][fx[n].index <= t] for n in ("eurusd", "gbpusd", "usdjpy")))
        vp = pct_expanding(vix, t) if len(vix[vix.index <= t]) else (None, 0)
        vix_pct = vp[0] if vp[1] >= MIN_VIX_OBS else None
        comp = {}
        for c in CURRENCIES:
            d = data[c]
            rate, infl = asof(d["rate"], t, LAG_DAYS["rate"]), asof(d["infl"], t, LAG_DAYS["inflation"])
            real = None if rate is None or infl is None else rate - infl
            real_d = {}
            for months in (6, 12):  # variazione del tasso reale vs mesi fa (point-in-time con gli stessi lag)
                tp = t - pd.DateOffset(months=months)
                r0, i0 = asof(d["rate"], tp, LAG_DAYS["rate"]), asof(d["infl"], tp, LAG_DAYS["inflation"])
                real_d[months] = None if real is None or r0 is None or i0 is None else real - (r0 - i0)
            cot_pct = None
            if len(d["cot"][d["cot"].index <= t]) >= MIN_COT_WEEKS:
                cot_pct = pct_expanding(d["cot"], t)[0]
            comp[c] = dict(real=real, d6=real_d[6], d12=real_d[12], growth=asof(d["growth"], t, LAG_DAYS["growth"]), mom=mom[c],
                           cot=cot_component(cot_pct), vix=vix_component(c, vix_pct))
        variants = {
            "completo": lambda x, c: strength_score(x["real"], x["growth"], x["mom"], x["cot"], x["vix"]),
            "senza COT/VIX": lambda x, c: strength_score(x["real"], x["growth"], x["mom"]),
            "solo tasso reale": lambda x, c: strength_score(x["real"], None, None),
            "solo var tasso reale 6m": lambda x, c: strength_score(x["d6"], None, None),
            "solo var tasso reale 12m": lambda x, c: strength_score(x["d12"], None, None),
            "solo crescita": lambda x, c: strength_score(None, x["growth"], None),
            "solo momentum": lambda x, c: strength_score(None, None, x["mom"]),
            "solo COT": lambda x, c: strength_score(None, None, None, cot=x["cot"]),
            "solo VIX": lambda x, c: strength_score(None, None, None, vix=x["vix"]),
        }
        for vname, fn in variants.items():
            sc = {c: fn(comp[c], c)["score"] for c in CURRENCIES}
            for base, quote in PAIRS:
                if sc[base] is None or sc[quote] is None:
                    continue
                for h in HORIZONS:
                    if i + h >= len(month_ends) or i % h:  # i % h: solo periodi non sovrapposti
                        continue
                    nxt = month_ends[i + h]
                    fwd = (lvl.loc[nxt, base] - lvl.loc[nxt, quote]) - (lvl.loc[t, base] - lvl.loc[t, quote])
                    rows.append(dict(t=t, h=h, variant=vname, pair=f"{base}/{quote}", score=pair_view(sc[base], sc[quote])["score"], fwd=fwd * 100))
    df = pd.DataFrame(rows)

    def stats(g):
        sig = g[(g.score >= BUY_ABOVE) | (g.score <= SELL_BELOW)]
        pnl = np.where(sig.score >= BUY_ABOVE, sig.fwd, -sig.fwd)
        return pd.Series({
            "mesi": g.t.nunique(), "obs": len(g), "IC": g.score.rank().corr(g.fwd.rank()),
            "n segnali": len(sig), "hit%": (pnl > 0).mean() * 100 if len(sig) else np.nan,
            "ret medio %/periodo": pnl.mean() if len(sig) else np.nan,
            "t-stat": pnl.mean() / (pnl.std(ddof=1) / math.sqrt(len(pnl))) if len(pnl) > 2 else np.nan,
        })

    def report(d, title):
        print(f"\n=== {title}: {d.t.min().date()} -> {d.t.max().date()} ===")
        print(d.groupby("variant").apply(stats, include_groups=False).round(3).to_string())

    for h in HORIZONS:
        report(df[df.h == h], f"orizzonte {h} mesi, periodi non sovrapposti")
    print()
    print("Per coppia, orizzonte 3 e 12 mesi:")
    for h in (3, 12):
        for v in ("solo tasso reale", "solo var tasso reale 6m", "solo var tasso reale 12m"):
            print()
            print(f"[{v}, {h}m]")
            print(df[(df.h == h) & (df.variant == v)].groupby("pair").apply(stats, include_groups=False).round(3).to_string())


if __name__ == "__main__":
    main()
