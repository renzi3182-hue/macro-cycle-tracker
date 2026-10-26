"""Backtest settori per regime (src/config/sector_regime.py): i settori long del libro battono quelli short nel regime
USA del momento?

Regime USA point-in-time (assess.point_in_time_history: dati rivisti, con i ritardi di pubblicazione), letto a fine
mese t; rendimento del mese t+1 dei settori (e, a parte, dei 6 mesi dopo). Settori: ETF SPDR dove esistono, prima i
settori della Kenneth French Data Library (score.PROXY, 12 industrie: tecnologia = BusEq, comunicazioni = Telcm,
discrezionali = Shops, prima necessita' = NoDur, materiali = Chems, industriali = Manuf, finanziari = Money...).
Immobiliare senza serie lunga: entra solo con XLRE (dal 2015). Pesi uguali dentro long e short, niente costi.

Regola decisa prima di guardare i risultati: c'e' vantaggio se long meno short e' positivo con t >= 2 su tutto il
periodo e positivo in tutte e due le meta' del campione. I numeri si riportano anche senza vantaggio.
Uso, da root del monorepo: .venv/Scripts/python code/macro-cycle-tracker/scripts/backtest_sectors.py
(legge data/cache.db: prezzi degli ETF, storico French e dati macro USA)
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.classify.assess import USED_INPUTS, point_in_time_history
from src.classify.regime import REGIMES
from src.classify.score import (
    ASSET_AREA, HISTORY_AREA, HISTORY_SERIES, complete_months, extended_prices, monthly_prices, proxy_returns,
)
from src.config.sector_regime import SECTOR_NAMES, SECTOR_REGIME
from src.data import cache

HORIZON = 6  # seconda lettura, come l'orizzonte dell'app


def load() -> tuple[pd.DataFrame, pd.Series]:
    """Prezzi mensili dei settori (ETF, prima French) e regime USA point-in-time sullo stesso indice."""
    read = cache.read_indicator_series
    px = complete_months(monthly_prices({t: read(ASSET_AREA, t) for t in SECTOR_NAMES}))
    proxies = proxy_returns({s: read(HISTORY_AREA, s) for s in HISTORY_SERIES})
    ext = extended_prices(px, proxies)
    regime = point_in_time_history("USA", {n: read("USA", n) for n in USED_INPUTS})["regime"]
    regime = regime[~regime.index.duplicated(keep="last")].reindex(ext.index)
    return ext, regime


def legs(fwd: pd.DataFrame, regime: pd.Series) -> pd.DataFrame:
    """Per ogni mese con regime: rendimento futuro medio dei long, degli short e di tutti i settori disponibili."""
    rows = {}
    for t, reg in regime.dropna().items():
        if reg not in SECTOR_REGIME or t not in fwd.index:
            continue
        r = fwd.loc[t].dropna()
        long, short = (r.reindex(SECTOR_REGIME[reg][i]).dropna() for i in (0, 1))
        if len(long) and len(short):
            rows[t] = {"regime": reg, "long": long.mean(), "short": short.mean(), "tutti": r.mean()}
    return pd.DataFrame(rows).T.astype({"long": float, "short": float, "tutti": float})


def stat(x: pd.Series, overlap: int = 1) -> str:
    """Media annualizzata (in punti %), t (con esiti sovrapposti su n/overlap mesi indipendenti), mesi positivi."""
    x = x.dropna()
    if len(x) < 3:
        return "n/d"
    per_year = 12 / overlap
    t = x.mean() / x.std() * math.sqrt(len(x) / overlap)
    return f"{x.mean() * per_year * 100:+.1f} punti l'anno, t {t:+.1f}, positivo {(x > 0).mean() * 100:.0f}% ({len(x)} mesi)"


def perf(r: pd.Series) -> str:
    r = r.dropna()
    w = (1 + r).cumprod()
    return f"{(w.iloc[-1] ** (12 / len(r)) - 1) * 100:.1f}% l'anno, calo massimo {(w / w.cummax() - 1).min() * 100:.0f}%"


def main() -> None:
    ext, regime = load()
    r1 = ext.pct_change(fill_method=None).shift(-1)  # mese t+1 sulla riga t
    d = legs(r1, regime)
    spread = d["long"] - d["short"]
    mid = d.index[len(d) // 2]
    print(f"Settori USA, regime point-in-time, {d.index[0]:%Y-%m} -> {d.index[-1]:%Y-%m}, rendimento del mese dopo\n")
    print(f"Long meno short, tutto il periodo: {stat(spread)}")
    print(f"  prima meta' (fino a {mid:%Y-%m}): {stat(spread[spread.index < mid])}")
    print(f"  seconda meta':            {stat(spread[spread.index >= mid])}")
    print(f"  dal 2000:                 {stat(spread[spread.index >= '2000-01-01'])}")
    print(f"Long meno tutti i settori: {stat(d['long'] - d['tutti'])}")
    print(f"Short meno tutti i settori: {stat(d['short'] - d['tutti'])}  (negativo = gli short vanno peggio, come vuole il libro)")
    print("\nPer regime (long meno short):")
    for reg in REGIMES:
        print(f"  {reg:13s} {stat(spread[d['regime'] == reg])}")
    print(f"\nPortafogli ribilanciati ogni mese, niente costi: long {perf(d['long'])}; short {perf(d['short'])}; "
          f"tutti i settori {perf(d['tutti'])}")

    fwd = ext.shift(-HORIZON) / ext - 1
    d6 = legs(fwd, regime)
    s6 = d6["long"] - d6["short"]
    print(f"\nA {HORIZON} mesi (esiti sovrapposti): long meno short {stat(s6, HORIZON)}")
    print(f"  prima meta': {stat(s6[s6.index < mid], HORIZON)} · seconda meta': {stat(s6[s6.index >= mid], HORIZON)}")
    ok = spread.mean() / spread.std() * math.sqrt(len(spread)) >= 2 and spread[spread.index < mid].mean() > 0 \
        and spread[spread.index >= mid].mean() > 0
    print(f"\nEsito con la regola decisa prima: {'VANTAGGIO' if ok else 'nessun vantaggio dimostrato'}")


if __name__ == "__main__":
    main()
