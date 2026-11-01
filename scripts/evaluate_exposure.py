"""Verifica dello stato della tendenza per paese (plan-dashboard-paesi.md, sezione 1), prima di mostrarlo nell'app.

Regola: borsa del paese (rendimento totale in dollari, src/classify/allocation.equity_usd_returns) contro la sua media
a 10 mesi, letta a fine mese e applicata al mese dopo. Fuori dal mercato si tiene liquidita' in dollari (tasso a 3
mesi USA del mese, noto a fine mese). Varianti:
- Compra e tieni: sempre 100%.
- 2 stati: 100% sopra la media, 0% sotto.
- 3 stati: positiva 100% (sopra la media di oltre BAND); in bilico 50% (entro BAND dalla media, oppure sotto da un
  solo mese chiuso); negativa 0% (sotto da almeno 2 mesi chiusi e oltre BAND).
- 2 stati + regime: 100% sopra la media con regime favorevole alle azioni (Goldilocks o Reflazione, tutte le letture
  se "Incerto"), 50% sopra la media con regime sfavorevole, 0% sotto. Regime point-in-time
  (assess.point_in_time_history), quindi solo dove c'e' la storia macro. Serve a mostrare se il regime aggiunge.

Finestre: le 4 di verifica di allocation.FOLDS per scegliere, poi il periodo finale bloccato 2019-oggi una volta sola.
Niente costi di transazione (la regola cambia al massimo una volta al mese).

CRITERIO, fissato prima di guardare i numeri (30/10/2026): sulle finestre di verifica, in media sui 9 paesi, lo stato
"in bilico" resta se (a) il drawdown massimo medio non e' peggiore di oltre 1 punto rispetto ai 2 stati e (b) la
rotazione annua (somma dei cambi di esposizione in valore assoluto, per anno) e' piu' bassa. Altrimenti 2 stati.
Il regime entra nello stato solo se migliora il drawdown medio di almeno 2 punti senza togliere piu' di 0,5 punti di
rendimento annuo, sulle finestre di verifica e poi anche sul periodo finale.

Uso, da root del monorepo: .venv/bin/python code/macro-cycle-tracker/scripts/evaluate_exposure.py [--sviluppo]
(legge data/cache.db; serve un run completo di src/scheduler/update_data)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src.classify import allocation as al
from src.classify import exposure as ex
from src.classify.assess import USED_INPUTS, label_regimes, point_in_time_history
from src.classify.score import ASSET_AREA, HISTORY_AREA, monthly_prices
from src.data import cache

BAND = ex.BAND  # entro l'1% dalla media: in bilico
EQUITY_REGIMES = {"Goldilocks", "Reflazione"}


def load() -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """Rendimenti mensili in dollari per area, liquidita' mensile, regime point-in-time per area (NaN dove manca)."""
    read = cache.read_indicator_series
    asset_px = monthly_prices({t: read(ASSET_AREA, t) for t in al.COUNTRY_ETF.values()})
    d = al.load(read, asset_px, read(HISTORY_AREA, "Mkt"))
    cash = (d["rate"]["USA"] / 1200).ffill()
    regimes = {}
    for a in al.AREAS:
        h = point_in_time_history(a, {n: read(a, n) for n in USED_INPUTS})
        if h is not None:
            s = h["regime"]
            s.index = s.index.to_timestamp() if isinstance(s.index, pd.PeriodIndex) else s.index
            regimes[a] = s.reindex(d["grid"], method="ffill", limit=3)
    return d["equity_usd"], cash, pd.DataFrame(regimes, index=d["grid"]).reindex(columns=al.AREAS)


def exposures(r: pd.Series, regime: pd.Series) -> dict[str, pd.Series]:
    """Esposizione decisa a fine mese t (indice t), da applicare al rendimento del mese t+1."""
    dist = ex.distance(r)  # la stessa dell'app
    ok = dist.notna()
    below = dist < 0
    run = below.groupby((~below).cumsum()).cumsum()  # mesi chiusi consecutivi sotto la media
    two = (~below).astype(float)
    three = pd.Series(np.where(dist > BAND, 1.0, np.where((dist.abs() <= BAND) | (run == 1), 0.5, 0.0)), index=r.index)
    good = regime.map(lambda x: float(all(g in EQUITY_REGIMES for g in label_regimes(x))) if isinstance(x, str) else np.nan)
    with_regime = two * (0.5 + 0.5 * good)
    out = {"Compra e tieni": pd.Series(1.0, index=r.index), "2 stati": two, "3 stati": three, "2 stati + regime": with_regime}
    return {k: v.where(ok) for k, v in out.items()}


def returns(r: pd.Series, cash: pd.Series, w: pd.Series) -> pd.Series:
    """Rendimento del mese t+1 con l'esposizione decisa a fine t, indicizzato al mese del rendimento."""
    w1 = w.shift(1)
    return (w1 * r + (1 - w1) * cash.shift(1)).where(w1.notna() & r.notna())


def stats(rets: pd.Series, w: pd.Series, start: str, end: str) -> dict:
    m = (rets.index >= start) & (rets.index <= end)
    x = rets[m].dropna()
    if len(x) < 24:
        return {}
    wx = w.shift(1)[m].reindex(x.index)
    years = len(x) / 12
    return {"rend": al.annual(x), "vol": float(x.std() * np.sqrt(12) * 100), "dd": al.max_drawdown(x),
            "rot": float(wx.diff().abs().sum() / years), "fuori": float((wx < 1).mean() * 100)}


def table(eq, cash, reg, windows: list[tuple[str, str]], title: str) -> pd.DataFrame:
    rows = []
    for a in al.AREAS:
        r = eq[a]
        for name, w in exposures(r, reg[a]).items():
            rr = returns(r, cash, w)
            for s, e in windows:
                st = stats(rr, w, s, e)
                if st:
                    rows.append({"area": a, "regola": name, "finestra": f"{s[:4]}-{e[:4]}", **st})
    df = pd.DataFrame(rows)
    print(f"\n=== {title} ===")
    print("Media su paesi e finestre (rend. e vol. % annui, drawdown %, rotazione = cambi di esposizione per anno, "
          "fuori = % mesi non al 100%):")
    # stesso campione per ogni regola: solo le coppie area-finestra dove esistono tutte (il regime manca in alcune)
    keys = df.groupby(["area", "finestra"])["regola"].nunique()
    full = keys[keys == df["regola"].nunique()].index
    both = df.set_index(["area", "finestra"]).loc[full].reset_index()
    print(df.groupby("regola")[["rend", "vol", "dd", "rot", "fuori"]].mean().round(2).to_string())
    print(f"Solo dove c'e' anche il regime ({len(full)} coppie area-finestra):")
    print(both.groupby("regola")[["rend", "vol", "dd", "rot", "fuori"]].mean().round(2).to_string())
    print("Drawdown massimo per paese (media sulle finestre):")
    print(df.pivot_table(index="area", columns="regola", values="dd").reindex(al.AREAS).round(1).to_string())
    return df


def verdict(df: pd.DataFrame) -> None:
    m = df[df["regola"] != "2 stati + regime"].groupby("regola")[["rend", "dd", "rot"]].mean()
    two, three = m.loc["2 stati"], m.loc["3 stati"]
    keep = three["dd"] >= two["dd"] - 1 and three["rot"] < two["rot"]
    print(f"\nCriterio 3 stati: drawdown {three['dd']:.1f} contro {two['dd']:.1f} (tolleranza 1 punto), rotazione "
          f"{three['rot']:.2f} contro {two['rot']:.2f} -> {'3 STATI' if keep else '2 STATI'}")
    keys = df.groupby(["area", "finestra"])["regola"].nunique()
    full = keys[keys == df["regola"].nunique()].index
    g = df.set_index(["area", "finestra"]).loc[full].groupby("regola")[["rend", "dd"]].mean()
    gain, cost = g.loc["2 stati + regime", "dd"] - g.loc["2 stati", "dd"], g.loc["2 stati", "rend"] - g.loc["2 stati + regime", "rend"]
    print(f"Criterio regime: drawdown {gain:+.1f} punti, rendimento {-cost:+.2f} punti l'anno -> "
          f"{'IL REGIME AGGIUNGE' if gain >= 2 and cost <= 0.5 else 'IL REGIME NON AGGIUNGE'}")


def main() -> None:
    eq, cash, reg = load()
    dev = table(eq, cash, reg, [(s, e) for _, s, e in al.FOLDS], "Finestre di verifica (per scegliere)")
    verdict(dev)
    if "--sviluppo" in sys.argv:
        return
    end = f"{eq.index[-1]:%Y-%m-%d}"
    final = table(eq, cash, reg, [(al.HOLDOUT_START, end)], f"Periodo finale bloccato {al.HOLDOUT_START[:4]}-oggi (una volta)")
    verdict(final)
    table(eq, cash, reg, [("1976-01-01", end)], "Tutto lo storico, solo descrittivo")
    print("\nStato oggi (ultimo mese chiuso):")
    for a in al.AREAS:
        w = exposures(eq[a], reg[a])
        print(f"  {a:10s} 2 stati {w['2 stati'].iloc[-1]:.0%}  3 stati {w['3 stati'].iloc[-1]:.0%}")


if __name__ == "__main__":
    main()
