"""Verifica del punteggio asset (src/classify/score.py): un punteggio alto anticipa rendimenti migliori?

Il punteggio di fine mese t usa solo prezzi fino a t (i prezzi non vengono rivisti: e' gia' point-in-time).
Si misura il rendimento dei 3 mesi successivi contro la media equipesata degli asset disponibili.
Stampa:
1. per fascia di punteggio: casi, extra-rendimento mediano e medio a 3 mesi, % di volte sopra la media;
2. IC (correlazione di rango punteggio -> extra-rendimento) per pilastro e totale, in due sottoperiodi;
3. portafoglio dei migliori N, ribilanciato ogni mese, contro pesi uguali, SPY e 60/40 (niente costi).
Uso, da root del monorepo: .venv/Scripts/python code/macro-cycle-tracker/scripts/evaluate_score.py
(legge data/cache.db; se mancano i prezzi li scarica da Yahoo)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import math

import pandas as pd

from src.classify.score import ASSET_AREA, HORIZON_MONTHS as HORIZON, UNIVERSE, band_table, complete_months, forward_excess, monthly_prices, pillars, scores
from src.data import cache
from src.scheduler.update_data import update_asset_prices

SPLIT = "2014-01-01"  # due sottoperiodi di ~12 anni
TOP_N = 5


def load_prices() -> pd.DataFrame:
    if any(cache.read_indicator_series(ASSET_AREA, t).empty for t in UNIVERSE):
        update_asset_prices()
    return complete_months(monthly_prices({t: cache.read_indicator_series(ASSET_AREA, t) for t in UNIVERSE}))


def ic(signal: pd.DataFrame, excess: pd.DataFrame) -> tuple[float, float, int]:
    """IC medio mensile e t-stat. I rendimenti a 3 mesi si sovrappongono: t calcolato su n/HORIZON mesi indipendenti."""
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
    px = load_prices()
    s = scores(px)
    excess = forward_excess(px, s)
    start = s.dropna(how="all").index[0]
    print(f"Universo {px.shape[1]} ETF, punteggi da {start:%Y-%m} a {s.index[-1]:%Y-%m}, orizzonte {HORIZON} mesi\n")

    table = band_table(s, excess)
    print("Extra-rendimento a 3 mesi contro la media dell'universo, per fascia di punteggio (%):")
    print(table.round(2).to_string(), "\n")

    print("IC (Spearman mensile punteggio -> extra-rendimento a 3 mesi; t > 2 = probabilmente non casuale):")
    signals = {**{k: v.where(s.notna()) for k, v in pillars(px).items()}, "Punteggio": s}
    for name, sig in signals.items():
        parts = [f"{label} IC {m:+.3f} t {t:+.1f} ({n} mesi)"
                 for label, (m, t, n) in (("tutto", ic(sig, excess)), (f"<{SPLIT[:4]}", ic(sig.loc[:SPLIT], excess.loc[:SPLIT])),
                                          (f">={SPLIT[:4]}", ic(sig.loc[SPLIT:], excess.loc[SPLIT:])))]
        print(f"- {name:10s} " + " | ".join(parts))

    ret1 = px.pct_change(fill_method=None).shift(-1)  # punteggio a fine t -> rendimento del mese t+1
    top = s.rank(axis=1, ascending=False, method="first") <= TOP_N
    strategies = {
        f"Migliori {TOP_N}": ret1.where(top).mean(axis=1),
        "Pesi uguali": ret1.where(s.notna()).mean(axis=1),
        "SPY": ret1["SPY"],
        "60/40 SPY-IEF": 0.6 * ret1["SPY"] + 0.4 * ret1["IEF"],
    }
    d = pd.DataFrame(strategies).loc[start:].dropna()
    turnover = (top.astype(int).diff().abs().sum(axis=1) / 2 / TOP_N).loc[start:].mean() * 100
    print(f"\nPortafogli ribilanciati ogni mese, {d.index[0]:%Y-%m} -> {d.index[-1]:%Y-%m}, senza costi "
          f"(Migliori {TOP_N}: cambia in media il {turnover:.0f}% delle posizioni al mese):")
    print(pd.DataFrame({k: perf(v) for k, v in d.items()}).T.round(1).to_string())
    print(f"\nPunteggi attuali ({s.index[-1]:%Y-%m}):")
    print(s.iloc[-1].dropna().sort_values(ascending=False).astype(int).rename(lambda t: f"{t} {UNIVERSE[t][0]}").to_string())


if __name__ == "__main__":
    main()
