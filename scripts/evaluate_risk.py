"""Verifica del Risk On/Off giornaliero (src/classify/risk.py): il punteggio dice qualcosa sulle sedute dopo dell'S&P 500?

Componenti point-in-time (percentili solo sul passato), confronto con volatilita' e rendimento dei 21 giorni dopo e con
un calo oltre il 10% entro 63 giorni. Riferimento: le sole tre componenti della prima versione (VIX, credito,
ampiezza) sulla stessa finestra. Strategie di prova: SPY se il segnale e' favorevole, altrimenti SHY, posizione dal
giorno dopo il segnale; termine di confronto il filtro di tendenza su SPY (media a 200 sedute).
Uso: py -3.12 scripts/evaluate_risk.py   (VIX, credito, XLY/XLP da data/cache.db; ETF giornalieri scaricati da Yahoo)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import math

import pandas as pd

from src.classify.risk import BANDS, CANARY, TREND_DAYS, canary, components, risk_score
from src.classify.score import UNIVERSE
from src.data import cache
from src.data.fetch_market import fetch_yahoo

FWD_DAYS, DD_DAYS, DD = 21, 63, -0.10
OLD = ["VIX", "Credito", "Ampiezza"]


def perf(r: pd.Series) -> str:
    r = r.dropna()
    w = (1 + r).cumprod()
    return (f"{(w.iloc[-1] ** (252 / len(r)) - 1) * 100:5.1f}%/anno, vol {r.std() * math.sqrt(252) * 100:4.1f}%, "
            f"DD {(w / w.cummax() - 1).min() * 100:4.0f}%")


def bands(d: pd.DataFrame, col: str) -> str:
    t = d.groupby(pd.cut(d[col], BANDS, include_lowest=True), observed=True).agg(
        sedute=("vol", "size"), vol_dopo=("vol", "mean"), r21_med=("r21", "median"), calo10=("calo", "mean"))
    return (t * [1, 1, 100, 100]).round(1).to_string()


def main() -> None:
    m = lambda k: cache.read_indicator_series("Mercati", k)
    px = pd.DataFrame({t: fetch_yahoo(t, "max", "1d", adjusted=True) for t in UNIVERSE})
    comp = components(m("vix"), m("vix3m"), cache.read_indicator_series("USA", "credit_spread"), m("xly"), m("xlp"), px)
    days = px["SPY"].dropna().index
    comp = comp.reindex(days)
    spy = px["SPY"].loc[days]
    r = spy.pct_change()
    d = pd.DataFrame({
        "new": risk_score(comp), "five": risk_score(comp.drop(columns="Canarino")), "old": risk_score(comp[OLD]),
        "vol": r.rolling(FWD_DAYS).std().shift(-FWD_DAYS) * math.sqrt(252) * 100,
        "r21": spy.shift(-FWD_DAYS) / spy - 1,
        "calo": (spy.rolling(DD_DAYS).min().shift(-DD_DAYS) / spy - 1 < DD).astype(float),
    }).dropna(subset=["new"])
    d = d.iloc[:-DD_DAYS]  # ultime sedute senza i 63 giorni dopo
    print(f"Sedute {d.index[0]:%Y-%m-%d} -> {d.index[-1]:%Y-%m-%d}, {len(d)}; ultimo punteggio "
          f"{risk_score(comp).dropna().iloc[-1]:.0f} ({', '.join(f'{k} {v:.0f}' for k, v in comp.dropna().iloc[-1].items())})")
    print("Correlazione fra componenti:\n", comp.loc[d.index].corr().round(2).to_string())
    print(f"\nOgni componente contro volatilita' e rendimento SPY dei {FWD_DAYS} giorni dopo:")
    for c in comp:
        print(f"  {c:10s} vol {comp.loc[d.index, c].corr(d['vol']):+.2f}  r21 {comp.loc[d.index, c].corr(d['r21']):+.3f}")
    for col, name in (("new", "Sei componenti"), ("five", "Cinque, senza canarino"), ("old", "Solo VIX, credito, ampiezza")):
        print(f"\n== {name}: corr vol {d[col].corr(d['vol']):+.3f}, corr r21 {d[col].corr(d['r21']):+.3f}")
        for per, sub in {"<2019": d.loc[:"2018-12"], ">=2019": d.loc["2019":]}.items():
            print(f"   {per}: corr vol {sub[col].corr(sub['vol']):+.3f}, corr r21 {sub[col].corr(sub['r21']):+.3f}, sedute {len(sub)}")
        print(f"Per fascia (vol_dopo = volatilita' annua dei {FWD_DAYS} giorni dopo, calo10 = % sedute con calo oltre il "
              f"10% entro {DD_DAYS}):\n{bands(d, col)}")

    alarm = (canary(px[CANARY]).loc[days] < 0).where(px[CANARY].shift(252).loc[days].notna())
    c = pd.DataFrame({"alarm": alarm, "vol": d["vol"].reindex(days), "calo": (spy.rolling(DD_DAYS).min().shift(-DD_DAYS) / spy - 1 < DD)})
    c = c.dropna(subset=["alarm"]).iloc[:-DD_DAYS]
    c["vol"] = r.rolling(FWD_DAYS).std().shift(-FWD_DAYS).loc[c.index] * math.sqrt(252) * 100
    g = c.groupby("alarm").agg(sedute=("vol", "size"), vol_dopo=("vol", "mean"), calo10=("calo", "mean"))
    print(f"\nCanarino {CANARY} {c.index[0]:%Y-%m} -> {c.index[-1]:%Y-%m}, in allarme nel {c['alarm'].mean() * 100:.0f}% delle sedute:")
    print((g * [1, 1, 100]).round(1).to_string())

    nxt_r, nxt_c = r.shift(-1), px["SHY"].loc[days].pct_change().shift(-1).fillna(0)
    trend = spy > spy.rolling(TREND_DAYS).mean()
    for start, label in ((d.index[0], "finestra del punteggio"), (c.index[0], "finestra del canarino")):
        idx = days[(days >= start) & (days <= d.index[-1])]
        print(f"\nStrategie, {label} {idx[0]:%Y-%m} -> {idx[-1]:%Y-%m} (niente costi, SHY come cash):")
        print(f"  SPY sempre:            {perf(nxt_r.loc[idx])}")
        print(f"  SPY se sopra media 200: {perf(nxt_r.loc[idx].where(trend.loc[idx], nxt_c.loc[idx]))}")
        print(f"  SPY se canarino calmo:  {perf(nxt_r.loc[idx].where(alarm.loc[idx] == 0, nxt_c.loc[idx]))}")
        if start == d.index[0]:
            for col in ("new", "five", "old"):
                print(f"  SPY se {col:4s} > 40:    {perf(nxt_r.loc[idx].where(d[col].reindex(idx) > 40, nxt_c.loc[idx]))}")


if __name__ == "__main__":
    main()
