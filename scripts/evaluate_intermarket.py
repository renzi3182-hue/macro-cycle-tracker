"""Verifica dell'intermarket (src/classify/intermarket.py): la fase di Murphy distingue qualcosa? L'allineamento
macro/mercati anticipa i crolli?

Dal 2000 gli ETF sono troppo giovani (TLT 2002, DBC 2006), quindi la fase si calcola con le serie lunghe di
scripts/backtest_assets.py: S&P 500 (^GSPC, senza dividendi), Treasury 10 anni sintetico dal DGS10 (durata da IEF,
non da TLT), S&P GSCI, oro GC=F, T-bill. Stessa regola dell'app: sopra/sotto la media a 10 mesi a mese chiuso.
Controllo: quota di mesi in cui la fase dalle serie lunghe coincide con quella dagli ETF (TLT, SPY, DBC).
Stampa:
1. per fase: rendimento medio dei 3 mesi successivi di azioni, Treasury, materie prime, oro e cash, casi e t contro
   le altre fasi (finestre sovrapposte: t su casi/3 osservazioni indipendenti); stessa tabella con gli ETF dal 2007;
2. allineamento (fase del ciclo USA point-in-time + fase di Murphy + rame/oro HG=F/GC=F a 3 mesi): quota di mesi
   seguiti da un drawdown dell'S&P 500 oltre il 10% entro 6 mesi (chiusure giornaliere), e i drawdown oltre il 10%
   dal 2000 con lo stato del mese prima del massimo. Soglia 10% dall'utente, orizzonte 6 mesi scelto prima, unico.
Uso: py -3.12 scripts/evaluate_intermarket.py   (serve FRED_API_KEY in .env; legge data/cache.db e scarica da Yahoo)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os

import pandas as pd

from scripts.backtest_assets import asset_returns
from src.classify.assess import USED_INPUTS, point_in_time_history
from src.classify.intermarket import ALIGNED, MISALIGNED, PARTIAL, alignment, change, murphy_history, phase_label
from src.classify.score import ASSET_AREA, HORIZON_MONTHS, UNIVERSE, complete_months, monthly_prices
from src.data import cache, fetch_market
from src.scheduler.update_data import _load_dotenv

START = "2000-01-01"
DD_THRESHOLD, DD_MONTHS = 0.10, 6
PROXIES = ("Treasury 10Y", "Azionario", "Materie prime")  # obbligazioni, azioni, materie prime come MURPHY_TICKERS
ASSETS = ["Azionario", "Treasury 10Y", "Materie prime", "Oro", "Cash"]
ETF_ASSETS = ["SPY", "TLT", "DBC", "GLD", "SHY"]


def by_phase(phase: pd.Series, wealth: pd.DataFrame, assets: list[str]) -> pd.DataFrame:
    """Rendimento medio % dei HORIZON_MONTHS mesi dopo, per fase; t della fase contro tutte le altre."""
    fwd = (wealth.shift(-HORIZON_MONTHS) / wealth - 1).loc[phase.index]
    rows = []
    for p in sorted(phase.unique()):
        for a in assets:
            x, rest = fwd.loc[phase == p, a].dropna(), fwd.loc[phase != p, a].dropna()
            se = (x.var() / (len(x) / HORIZON_MONTHS) + rest.var() / (len(rest) / HORIZON_MONTHS)) ** 0.5
            rows.append({"fase": phase_label(p), "asset": a, "casi": len(x), "media %": x.mean() * 100,
                         "t": (x.mean() - rest.mean()) / se if len(x) > 2 else float("nan")})
    t = pd.DataFrame(rows)
    out = t.pivot(index="fase", columns="asset", values="media %")[assets].round(1)
    out.insert(0, "casi", t.groupby("fase")["casi"].max())
    return out.join(t.pivot(index="fase", columns="asset", values="t")[assets].round(1), rsuffix=" t")


def drawdown_ahead(daily: pd.Series, months: pd.DatetimeIndex) -> pd.Series:
    """True se dalla chiusura di fine mese l'indice perde piu' di DD_THRESHOLD entro DD_MONTHS mesi."""
    out = {}
    for m in months:
        end = m + pd.offsets.MonthEnd(0)
        if end + pd.DateOffset(months=DD_MONTHS) > daily.index[-1]:
            continue
        start = daily.loc[:end]
        window = daily[(daily.index > end) & (daily.index <= end + pd.DateOffset(months=DD_MONTHS))]
        if not start.empty and not window.empty:
            out[m] = window.min() / start.iloc[-1] - 1 <= -DD_THRESHOLD
    return pd.Series(out)


def episodes(daily: pd.Series) -> list[tuple[pd.Timestamp, float]]:
    """Drawdown oltre DD_THRESHOLD dal massimo precedente: (data del massimo, perdita massima)."""
    out, peak, peak_date, worst, active = [], daily.iloc[0], daily.index[0], 0.0, False
    for d, v in daily.items():
        if v >= peak:
            if active:
                out.append((peak_date, worst))
            peak, peak_date, worst, active = v, d, 0.0, False
        else:
            worst = min(worst, v / peak - 1)
            active = active or worst <= -DD_THRESHOLD
    if active:
        out.append((peak_date, worst))
    return out


def main() -> None:
    _load_dotenv()
    rets = asset_returns(os.environ["FRED_API_KEY"])
    rets.index = rets.index.to_timestamp()
    wealth = (1 + rets).cumprod()
    proxy = murphy_history(wealth, PROXIES).loc[START:]

    px = complete_months(monthly_prices({t: cache.read_indicator_series(ASSET_AREA, t) for t in UNIVERSE}))
    etf = murphy_history(px)
    both = pd.concat([proxy, etf], axis=1, join="inner")
    print(f"Fase di Murphy dalle serie lunghe {proxy.index[0]:%Y-%m} -> {proxy.index[-1]:%Y-%m}, {len(proxy)} mesi; "
          f"uguale a quella degli ETF nel {(both.iloc[:, 0] == both.iloc[:, 1]).mean() * 100:.0f}% dei {len(both)} mesi "
          f"in comune (dal {both.index[0]:%Y-%m})")
    print("Mesi per fase:", proxy.map(phase_label).value_counts().sort_index().to_dict(), "\n")

    print(f"Rendimento medio dei {HORIZON_MONTHS} mesi dopo, per fase (serie lunghe, %); colonne 't' = fase contro le altre:")
    print(by_phase(proxy, wealth, ASSETS).to_string(), "\n")
    print(f"Stessa tabella con gli ETF, {etf.index[0]:%Y-%m} -> {etf.index[-1]:%Y-%m} (rettificati per dividendi):")
    print(by_phase(etf, px, ETF_ASSETS).to_string(), "\n")

    macro = point_in_time_history("USA", {n: cache.read_indicator_series("USA", n) for n in USED_INPUTS})["phase"]
    ratio = (fetch_market.fetch_yahoo("HG=F", "max", "1d") / fetch_market.fetch_yahoo("GC=F", "max", "1d")).dropna()
    copper_up = change(ratio.resample("MS").last().dropna()) > 0
    df = pd.DataFrame({"macro": macro, "murphy": proxy, "rame_oro_su": copper_up}).dropna().loc[START:]
    df["stato"] = [alignment(m, int(p), bool(c)) for m, p, c in zip(df["macro"], df["murphy"], df["rame_oro_su"])]
    spx = fetch_market.fetch_yahoo("^GSPC", "max", "1d")
    df["dd"] = drawdown_ahead(spx, df.index)
    d = df.dropna(subset=["dd"])
    print(f"Allineamento macro/mercati {df.index[0]:%Y-%m} -> {df.index[-1]:%Y-%m}: "
          + ", ".join(f"{k} {v}" for k, v in df["stato"].value_counts().items()))
    print(f"Mesi seguiti da un drawdown S&P 500 > {DD_THRESHOLD:.0%} entro {DD_MONTHS} mesi: "
          f"tutti {d['dd'].mean() * 100:.0f}% ({len(d)} mesi)")
    for s in (ALIGNED, PARTIAL, MISALIGNED):
        x = d.loc[d["stato"] == s, "dd"]
        print(f"- {s}: {x.mean() * 100:.0f}% ({x.sum():.0f} su {len(x)})" if len(x) else f"- {s}: nessun mese")

    eps = [(p, w) for p, w in episodes(spx.loc["1999-01-01":]) if p >= pd.Timestamp(START)]
    print(f"\nDrawdown S&P 500 > {DD_THRESHOLD:.0%} dal {START[:4]}: {len(eps)}; stato a fine mese prima del massimo:")
    counts = {}
    for peak, worst in eps:
        state = df["stato"].get((peak.to_period("M") - 1).to_timestamp(), "n/d")  # ultimo fine mese prima del massimo
        counts[state] = counts.get(state, 0) + 1
        print(f"  massimo {peak:%Y-%m-%d}, perdita {worst:.0%}: {state}")
    print("  totale per stato:", counts)


if __name__ == "__main__":
    main()
