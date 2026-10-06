"""Backtest regime -> rendimenti degli asset (USA): l'asset allocation per regime regge sui dati?

Per ogni mese t si prende il regime USA calcolato con i soli dati pubblicati entro t (CLI e CPI con
1 mese di ritardo, vedi scripts/evaluate_model.py, dati in data/cache.db), poi si misura il rendimento del mese dopo.

Asset (serie gratuite, limiti dichiarati):
- Azionario: S&P 500 prezzo (Yahoo ^GSPC, mensile dal 1985), SENZA dividendi (~2%/anno in meno, uguale in ogni regime)
- Treasury 10Y: rendimento sintetico di un decennale alla pari dal DGS10 (FRED, dal 1962): cedola + variazione di prezzo
- Oro: future COMEX (Yahoo GC=F, giornaliero ridotto a fine mese), dal 2000
- Materie prime: S&P GSCI (Yahoo ^SPGSCI), dal 1985
- Cash: T-bill 3 mesi (FRED TB3MS)
Poche osservazioni per regime (Espansione/Stagflazione ~80-110 mesi dal 1962, meno per oro e azioni):
i t-stat contano piu' delle medie.

Filtro di tendenza (06/10/2026, 2000-08 -> 2026-08, niente costi): ogni asset sotto la media a 10 mesi va in cash.
Su tutti e 4 i portafogli il drawdown massimo scende di 55-75% (60/40 -31% -> -13%, All Weather -17% -> -6%,
regime -29% -> -11%) e la volatilita' di ~30%, il rendimento cala di 0,1-0,9 punti l'anno. Prima del 2014 il
filtro rende anche di piu' (60/40 3,5% -> 5,6%), dal 2014 costa 1-3 punti l'anno: protegge nei crolli lunghi
(2001-02, 2008), perde nei rimbalzi veloci. ~8 cambi entra/esci l'anno sommando i 4 asset.
Il portafoglio per regime (9,1% contro 5,5% dell'All Weather) usa la tabella riallineata il 03/10 su questi stessi
dati: risultato in-sample, non una prova di vantaggio.
Uso: py -3.12 scripts/backtest_assets.py   (serve FRED_API_KEY in .env)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import math
import os

import numpy as np
import pandas as pd

from scripts.evaluate_model import INPUTS, lagged
from src.classify.assess import assess
from src.classify.score import TREND_MONTHS
from src.config.asset_allocation import ALL_WEATHER_WEIGHTS, portfolio_weights
from src.data import cache, fetch_fred, fetch_market
from src.scheduler.update_data import _load_dotenv

START = "1960-01-01"
# Asset della tabella di allocazione -> asset testabile. Quelli senza serie lunga gratuita
# (indicizzate, immobiliare, credito) escono e i pesi si rinormalizzano.
TESTABLE = {
    "Azionario": "Azionario", "Azionario growth": "Azionario", "Azionario difensivo": "Azionario",
    "Azionario value/difensivo": "Azionario",
    "Obbligazioni governative lunga durata": "Treasury 10Y", "Obbligazioni lunga durata": "Treasury 10Y",
    "Obbligazioni medio termine": "Treasury 10Y", "Obbligazioni governative medio termine": "Treasury 10Y",
    "Oro": "Oro", "Materie prime": "Materie prime", "Cash": "Cash",
}


def _monthly_close(s: pd.Series) -> pd.Series:
    return s.groupby(s.index.to_period("M")).last()


def bond_returns(yield_pct: pd.Series) -> pd.Series:
    """Rendimento mensile di un decennale comprato alla pari a fine mese e rivalutato al rendimento del mese dopo."""
    y = _monthly_close(yield_pct) / 100
    y0, y1 = y.shift(1), y
    n = 20  # cedole semestrali in 10 anni
    price = np.where(y1 > 0, y0 / y1 * (1 - (1 + y1 / 2) ** -n) + (1 + y1 / 2) ** -n, 1 + y0 * 10)
    return (pd.Series(price, index=y.index) - 1 + y0 / 12).dropna()


def asset_returns(key: str) -> pd.DataFrame:
    prices = {
        "Azionario": fetch_market.fetch_yahoo("^GSPC", "max", "1mo"),
        "Oro": fetch_market.fetch_yahoo("GC=F", "max", "1d"),  # il mensile Yahoo del future salta ~15% dei mesi
        "Materie prime": fetch_market.fetch_yahoo("^SPGSCI", "max", "1mo"),
    }
    rets = {}
    for k, p in prices.items():
        p = _monthly_close(p)
        p = p.reindex(pd.period_range(p.index[0], p.index[-1], freq="M"))  # mesi mancanti = NaN, non rendimenti su 2 mesi
        rets[k] = p.pct_change(fill_method=None)
    rets["Treasury 10Y"] = bond_returns(fetch_fred._fetch_series("DGS10", key, "lin"))
    rets["Cash"] = _monthly_close(fetch_fred._fetch_series("TB3MS", key, "lin")) / 100 / 12
    return pd.DataFrame(rets)[["Azionario", "Treasury 10Y", "Oro", "Materie prime", "Cash"]]


def regimes_point_in_time() -> pd.Series:
    series = {n: lagged(x, n) for n in INPUTS if not (x := cache.read_indicator_series("USA", n)).empty}
    regime = assess("USA", series)["history"]["regime"]
    regime.index = regime.index.to_period("M")
    return regime


def perf(r: pd.Series) -> dict:
    r = r.dropna()
    wealth = (1 + r).cumprod()
    return {"mesi": len(r), "rend. annuo %": ((wealth.iloc[-1]) ** (12 / len(r)) - 1) * 100,
            "vol %": r.std() * math.sqrt(12) * 100, "max drawdown %": (wealth / wealth.cummax() - 1).min() * 100}


def main() -> None:
    _load_dotenv()
    key = os.environ["FRED_API_KEY"]
    rets = asset_returns(key).loc[START:]
    regime = regimes_point_in_time().reindex(rets.index).dropna()
    fwd = rets.shift(-1).loc[regime.index]  # regime noto a fine mese t -> rendimento del mese t+1
    df = fwd.assign(regime=regime.values).dropna(subset=["regime"])
    print(f"Regime USA point-in-time (CLI e CPI con ritardo di pubblicazione), "
          f"{df.index[0]} -> {df.index[-1]}\n")
    print("Mesi per regime:", df["regime"].value_counts().to_dict(), "\n")

    assets = [c for c in rets.columns]
    mean_all = df[assets].mean()
    rows = []
    for reg, g in df.groupby("regime"):
        for a in assets:
            x = g[a].dropna()
            rest = df.loc[df["regime"] != reg, a].dropna()
            se = math.sqrt(x.var() / len(x) + rest.var() / len(rest)) if len(x) > 2 else np.nan
            rows.append({"regime": reg, "asset": a, "mesi": len(x), "rend. annuo %": x.mean() * 1200,
                         "vs media %": (x.mean() - mean_all[a]) * 1200, "t vs altri regimi": (x.mean() - rest.mean()) / se,
                         "mesi positivi %": (x > 0).mean() * 100})
    table = pd.DataFrame(rows)
    print("Rendimento medio annualizzato del mese successivo, per regime (t > 2 = differenza probabilmente non casuale):")
    print(table.pivot(index="asset", columns="regime", values="rend. annuo %").round(1).to_string(), "\n")
    print("t-stat vs gli altri regimi:")
    print(table.pivot(index="asset", columns="regime", values="t vs altri regimi").round(2).to_string(), "\n")

    print("Asset favoriti dalla tabella (asset_allocation.py): rango del rendimento nel regime (1 = migliore su 5)")
    for reg, g in table.groupby("regime"):
        ranks = g.set_index("asset")["rend. annuo %"].rank(ascending=False)
        fav = sorted({TESTABLE[a] for a in portfolio_weights(reg, "Medio") if a in TESTABLE})
        print(f"- {reg}: " + ", ".join(f"{a} {int(ranks[a])}" for a in fav))

    def to_testable(weights: dict) -> dict:
        w = {}
        for a, v in weights.items():
            if a in TESTABLE:
                w[TESTABLE[a]] = w.get(TESTABLE[a], 0) + v
        tot = sum(w.values())
        return {a: v / tot for a, v in w.items()}

    common = df[assets].dropna().index  # tutti gli asset disponibili (oro dal 2000)
    d = df.loc[common]

    def strategies(r: pd.DataFrame) -> dict:
        return {
            "Regime (profilo Medio)": r.apply(lambda x: sum(x[a] * w for a, w in to_testable(portfolio_weights(d.at[x.name, "regime"], "Medio")).items()), axis=1),
            "All Weather statico": r[assets].mul(pd.Series(to_testable(ALL_WEATHER_WEIGHTS))).sum(axis=1, min_count=1),
            "60/40 statico": r["Azionario"] * 0.6 + r["Treasury 10Y"] * 0.4,
            "Pesi uguali 5 asset": r[assets].mean(axis=1),
        }

    # Filtro di tendenza (Faber 2007): un asset si tiene solo se a fine mese il suo indice di rendimento e' sopra la
    # media a TREND_MONTHS mesi, altrimenti la sua quota va in cash per il mese dopo. Stessa regola del punteggio asset.
    idx = (1 + rets).cumprod()
    on = (idx > idx.rolling(TREND_MONTHS).mean()).loc[common].assign(Cash=True)
    risky = [a for a in assets if a != "Cash"]
    held = d[assets].where(on[assets], d["Cash"], axis=0)
    switches = on[risky].astype(int).diff().abs().sum().sum() / len(on) * 12

    plain, trend = strategies(d), strategies(held)
    rows = {}
    for k in plain:
        rows[k] = perf(plain[k])
        rows[f"{k} + tendenza"] = perf(trend[k])
    print(f"\nPortafogli, ribilanciati ogni mese, {common[0]} -> {common[-1]} (azioni senza dividendi, niente costi):")
    print(pd.DataFrame(rows).T.round(1).to_string())
    print(f"Filtro di tendenza: {switches:.1f} cambi entra/esci all'anno sommando i {len(risky)} asset; mesi fuori: "
          + ", ".join(f"{a} {(~on[a]).mean() * 100:.0f}%" for a in risky))
    for label, (a, b) in {"<2014": (None, "2013-12"), ">=2014": ("2014-01", None)}.items():
        print(f"- {label}: " + " | ".join(
            f"{k} {perf(plain[k].loc[a:b])['rend. annuo %']:.1f}% -> {perf(trend[k].loc[a:b])['rend. annuo %']:.1f}% "
            f"(DD {perf(plain[k].loc[a:b])['max drawdown %']:.0f}% -> {perf(trend[k].loc[a:b])['max drawdown %']:.0f}%)" for k in plain))


if __name__ == "__main__":
    main()
