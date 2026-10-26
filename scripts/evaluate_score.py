"""Verifica del punteggio asset (src/classify/score.py): un punteggio alto anticipa rendimenti migliori?

Il punteggio di fine mese t usa solo prezzi fino a t e pesi stimati solo su esiti gia' noti (walk-forward).
Si misura il rendimento dei mesi successivi (orizzonte di score.py, o --orizzonte N: taratura e verifica sullo stesso
orizzonte) contro la media equipesata degli asset disponibili.
Stampa:
1. per fascia di punteggio: casi, extra-rendimento mediano e medio sull'orizzonte, % di volte sopra la media, per il
   punteggio e per la prima versione (tendenza e momentum a pesi uguali), sugli stessi mesi e asset;
2. IC (correlazione di rango punteggio -> extra-rendimento) per pilastro e totale, in due sottoperiodi;
3. taratura: probabilita' prevista contro frequenza realizzata, e i pesi stimati per decennio;
4. portafoglio dei migliori N, ribilanciato ogni mese, contro pesi uguali, SPY e 60/40 (niente costi).
Uso, da root del monorepo: .venv/Scripts/python code/macro-cycle-tracker/scripts/evaluate_score.py [--orizzonte 6]
(legge data/cache.db; se mancano prezzi o serie lunghe li scarica, le serie FRED con FRED_API_KEY)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import math
import os

import pandas as pd

from src.classify.assess import USED_INPUTS, assess
from src.classify.score import (
    ASSET_AREA, ENTER, EXIT, HISTORY_AREA, HISTORY_SERIES, HORIZON_MONTHS, MIN_ASSETS, UNIVERSE, band_table,
    complete_months, extended_prices, forward_excess, hysteresis, macro, model, monthly_prices, pillars, proxy_returns,
    seasonality,
)
from src.data import cache
from src.scheduler.update_data import _load_dotenv, update_asset_prices, update_history

SPLIT = "2014-01-01"  # due sottoperiodi di ~12 anni
TOP_N = 5
HORIZON = HORIZON_MONTHS  # sostituito da --orizzonte


def load_prices() -> pd.DataFrame:
    if any(cache.read_indicator_series(ASSET_AREA, t).empty for t in UNIVERSE):
        update_asset_prices()
    return complete_months(monthly_prices({t: cache.read_indicator_series(ASSET_AREA, t) for t in UNIVERSE}))


def load_inputs() -> tuple[pd.DataFrame, pd.Series]:
    """Rendimenti delle serie lunghe (scaricate se mancano) e regime USA mensile."""
    if any(cache.read_indicator_series(HISTORY_AREA, s).empty for s in HISTORY_SERIES):
        _load_dotenv()
        update_history(os.environ.get("FRED_API_KEY", ""))
    proxies = proxy_returns({s: cache.read_indicator_series(HISTORY_AREA, s) for s in HISTORY_SERIES})
    usa = assess("USA", {n: cache.read_indicator_series("USA", n) for n in USED_INPUTS})
    return proxies, usa["history"]["regime"]


def first_version(px: pd.DataFrame) -> pd.DataFrame:
    """Punteggio fino al 19/10/2026: percentile della media dei percentili di tendenza e momentum."""
    p = pillars(px)
    avg = (p["Tendenza"].rank(axis=1, pct=True) + p["Momentum"].rank(axis=1, pct=True)) / 2
    s = (avg.rank(axis=1, pct=True) * 100).round().clip(lower=1)
    return s.where(avg.notna().sum(axis=1) >= MIN_ASSETS, axis=0)


def ic(signal: pd.DataFrame, excess: pd.DataFrame) -> tuple[float, float, int]:
    """IC medio mensile e t-stat. I rendimenti a HORIZON mesi si sovrappongono: t calcolato su n/HORIZON mesi indipendenti."""
    both = signal.notna() & excess.notna()
    # Spearman = Pearson sui ranghi (senza scipy)
    by_month = signal.where(both).rank(axis=1).corrwith(excess.where(both).rank(axis=1), axis=1).dropna()
    n = len(by_month)
    return by_month.mean(), by_month.mean() / by_month.std() * math.sqrt(n / HORIZON), n


def perf(r: pd.Series) -> dict:
    r = r.dropna()
    wealth = (1 + r).cumprod()
    return {"rend. annuo %": (wealth.iloc[-1] ** (12 / len(r)) - 1) * 100, "vol %": r.std() * math.sqrt(12) * 100,
            "max drawdown %": (wealth / wealth.cummax() - 1).min() * 100}


def main() -> None:
    global HORIZON
    parser = argparse.ArgumentParser()
    parser.add_argument("--orizzonte", type=int, default=HORIZON_MONTHS, help="mesi dell'extra-rendimento da prevedere")
    HORIZON = parser.parse_args().orizzonte
    px = load_prices()
    proxies, regime = load_inputs()
    m = model(px, proxies, regime, HORIZON)
    old = first_version(px)
    both = m["score"].notna() & old.notna()
    s, old = m["score"].where(both), old.where(both)
    excess = forward_excess(px, s, HORIZON)
    start = s.dropna(how="all").index[0]
    ext = extended_prices(px, proxies)
    print(f"Universo {px.shape[1]} ETF, storico esteso da {ext.index[0]:%Y-%m}, punteggi da {start:%Y-%m} "
          f"a {s.index[-1]:%Y-%m}, orizzonte {HORIZON} mesi\n")

    for name, sc in (("Punteggio", s), ("Prima versione", old)):
        print(f"{name}: extra-rendimento a {HORIZON} mesi contro la media dell'universo, per fascia (%):")
        print(band_table(sc, excess).round(2).to_string(), "\n")

    print(f"IC (Spearman mensile -> extra-rendimento a {HORIZON} mesi; t > 2 = probabilmente non casuale):")
    raw = {**pillars(px), "Stagionalità": seasonality(ext, HORIZON).reindex(px.index),
           "Macro": macro(ext, regime, HORIZON).reindex(px.index)}
    for name, sig in {**{k: v.where(both) for k, v in raw.items()}, "Punteggio": s, "Prima vers.": old}.items():
        parts = [f"{label} IC {mu:+.3f} t {t:+.1f} ({n} mesi)"
                 for label, (mu, t, n) in (("tutto", ic(sig, excess)), (f"<{SPLIT[:4]}", ic(sig.loc[:SPLIT], excess.loc[:SPLIT])),
                                           (f">={SPLIT[:4]}", ic(sig.loc[SPLIT:], excess.loc[SPLIT:])))]
        print(f"- {name:13s} " + " | ".join(parts))

    long = pd.DataFrame({"p": m["prob"].where(both).stack(), "y": (excess > 0).where(excess.notna()).stack()}).dropna()
    long["prevista"] = pd.cut(long["p"], [0, .4, .45, .5, .55, .6, 1])
    print("\nTaratura fuori campione (probabilita' prevista -> % di volte sopra la media):")
    print(long.groupby("prevista", observed=True)["y"].agg(casi="size", realizzata=lambda x: x.mean() * 100).round(1).to_string())
    w = m["weights"]
    print("\nPesi medi per decennio (logistica sui pilastri in posizione -0,5..+0,5):")
    print(w.groupby(w.index.year // 10 * 10).mean().round(2).to_string())

    ret1 = px.pct_change(fill_method=None).shift(-1)  # punteggio a fine t -> rendimento del mese t+1
    tops = {name: sc.rank(axis=1, ascending=False, method="first") <= TOP_N for name, sc in (("", s), (" prima vers.", old))}
    strategies = {
        **{f"Migliori {TOP_N}{name}": ret1.where(top).mean(axis=1) for name, top in tops.items()},
        "Pesi uguali": ret1.where(s.notna()).mean(axis=1),
        "SPY": ret1["SPY"],
        "60/40 SPY-IEF": 0.6 * ret1["SPY"] + 0.4 * ret1["IEF"],
    }
    d = pd.DataFrame(strategies).loc[start:].dropna()
    turnover = (tops[""].astype(int).diff().abs().sum(axis=1) / 2 / TOP_N).loc[start:].mean() * 100
    print(f"\nPortafogli ribilanciati ogni mese, {d.index[0]:%Y-%m} -> {d.index[-1]:%Y-%m}, senza costi "
          f"(Migliori {TOP_N}: cambia in media il {turnover:.0f}% delle posizioni al mese):")
    print(pd.DataFrame({k: perf(v) for k, v in d.items()}).T.round(1).to_string())

    # Segnale attivo: entra sopra ENTER, esce sotto EXIT (isteresi) contro entra/esce sopra/sotto ENTER.
    # Pesi uguali fra gli asset tenuti, SHY quando non ce n'e' nessuno.
    print(f"\nTutti gli asset sopra {ENTER} (pesi uguali, SHY se nessuno), con e senza uscita sotto {EXIT}:")
    held = {f"sopra {ENTER}": s > ENTER, f"entra {ENTER} esce {EXIT}": hysteresis(s, ENTER, EXIT)}
    rows = {}
    for name, h in held.items():
        wt = h.astype(float).div(h.sum(axis=1), axis=0).fillna(0)
        r = (wt * ret1.fillna(0)).sum(axis=1).where(h.any(axis=1), ret1["SHY"]).reindex(d.index)  # stesso periodo dei portafogli sopra
        rows[name] = {**perf(r), "asset medi": h.reindex(d.index).sum(axis=1).mean(),
                      "turnover %/mese": (wt.diff().abs().sum(axis=1) / 2).reindex(d.index).mean() * 100}
    print(pd.DataFrame(rows).T.round(1).to_string())
    last = m["score"].iloc[-1].dropna().sort_values(ascending=False)
    print(f"\nPunteggi attuali ({last.name:%Y-%m}), con probabilita' di battere la media a {HORIZON} mesi:")
    for t, v in last.items():
        print(f"  {t:5s} {UNIVERSE[t][0]:24s} {v:3.0f}  {m['prob'].loc[last.name, t] * 100:4.1f}%")


if __name__ == "__main__":
    main()
