"""Backtest COT per categoria (TFF, dal 2006) sulle valute: livello e CAMBIO di posizione di Asset manager / Hedge fund / Dealer.

Rebalance a fine mese, rendimento della coppia nei h mesi dopo, periodi non sovrapposti. Segnale 'follow':
coppia base/quote = feature(base) - feature(quote). IC > 0 = seguire la categoria funziona, IC < 0 = contrarian.
COT riferito al martedi', pubblicato il venerdi': lag 3 giorni. USD = contratto DXY.
Uso: python scripts/backtest_cot_groups.py
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src.classify.currency import CURRENCIES, PAIRS
from src.data import cache, fetch_cot

CCY_COT = {"USD": "Dollaro (DXY)", "EUR": "Euro", "GBP": "Sterlina", "JPY": "Yen"}
GROUPS = ["Asset manager", "Hedge fund", "Dealer"]
HORIZONS = [3, 6, 12]
LAG_DAYS = 3
MIN_WEEKS = 52
SPLIT = "2016-01-01"  # due meta' per controllare la stabilita' nel tempo


def main():
    fx = {n: cache.read_indicator_series("Valute", n).dropna() for n in ("eurusd", "gbpusd", "usdjpy")}
    lvl = pd.DataFrame({"USD": 0.0, "EUR": np.log(fx["eurusd"]), "GBP": np.log(fx["gbpusd"]), "JPY": -np.log(fx["usdjpy"])}).dropna()
    cot = {c: fetch_cot.fetch_net_by_group(CCY_COT[c], limit=5000) for c in CURRENCIES}
    month_ends = lvl.groupby(lvl.index.to_period("M")).tail(1).index

    def features(c, t):
        out = {}
        for g in GROUPS:
            s = cot[c][g]
            s = s[s.index <= t - pd.Timedelta(days=LAG_DAYS)]
            if len(s) < MIN_WEEKS + 1:
                continue
            out[f"{g}: livello (percentile)"] = float((s <= s.iloc[-1]).mean() * 100)
            for w in (13, 26, 52):
                out[f"{g}: cambio {w} sett."] = float(s.iloc[-1] - s.iloc[-1 - w])
        return out

    rows = []
    for i, t in enumerate(month_ends):
        feats = {c: features(c, t) for c in CURRENCIES}
        for base, quote in PAIRS:
            for name in feats[base].keys() & feats[quote].keys():
                for h in HORIZONS:
                    if i + h >= len(month_ends) or i % h:
                        continue
                    nxt = month_ends[i + h]
                    fwd = (lvl.loc[nxt, base] - lvl.loc[nxt, quote]) - (lvl.loc[t, base] - lvl.loc[t, quote])
                    rows.append(dict(t=t, h=h, feat=name, x=feats[base][name] - feats[quote][name], fwd=fwd * 100))
    df = pd.DataFrame(rows)

    def stats(g):
        pnl = np.sign(g.x) * g.fwd  # follow: long la coppia se la base ha piu' del quote
        return pd.Series({"obs": len(g), "IC": g.x.rank().corr(g.fwd.rank()), "hit%": (pnl > 0).mean() * 100,
                          "ret medio %": pnl.mean(), "t-stat": pnl.mean() / (pnl.std(ddof=1) / math.sqrt(len(pnl)))})

    for h in HORIZONS:
        d = df[df.h == h]
        print(f"\n=== orizzonte {h} mesi (follow), {d.t.min().date()} -> {d.t.max().date()} ===")
        print(d.groupby("feat", sort=False)[["x", "fwd"]].apply(stats).round(3).to_string())
        for title, part in ((f"prima del {SPLIT}", d[d.t < SPLIT]), (f"dal {SPLIT}", d[d.t >= SPLIT])):
            print(f"--- {title}")
            print(part.groupby("feat", sort=False)[["x", "fwd"]].apply(stats)[["obs", "IC", "t-stat"]].round(3).to_string())


if __name__ == "__main__":
    main()
