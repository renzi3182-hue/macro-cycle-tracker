import numpy as np
import pandas as pd

from src.classify.score import TREND_MONTHS, UNIVERSE
from src.config.asset_allocation import CASH, TREND_PROXY

# Stress test di un portafoglio per classi di asset (06/10/2026): rendimento nelle crisi passate e banda Monte Carlo.
# Ogni classe usa l'ETF del filtro di tendenza, il cash usa BIL (T-bill 1-3 mesi). Fino al 25/10/2026 il cash era SHY:
# con ~2 anni di duration guadagnava con i tassi in calo e perdeva con i tassi in salita, non come la liquidita' (60/40
# con filtro: crisi finanziaria +7,2% con SHY, +4,7% con BIL; 2022 -13,8% e -10,0%). Classi senza ETF escono e i pesi
# si rinormalizzano. Ribilanciamento mensile, niente costi.
# Gli ETF partono fra il 1993 (SPY) e il 2007 (UUP, BIL): una crisi senza dati per tutti gli asset resta n/d.
PROXY = {**TREND_PROXY, CASH: "BIL"}
EXTRA_ETF = sorted(set(PROXY.values()) - set(UNIVERSE))  # fuori dal punteggio: scaricati a parte, la classifica non cambia
# Crisi: dal mese dopo il massimo dell'S&P 500 al minimo, a fine mese. Niente bolla internet (2000-2002): gli ETF di
# obbligazioni, oro e materie prime partono dopo, quasi nessun portafoglio aveva dati.
SCENARIOS = {
    "Crisi finanziaria": ("2007-11", "2009-02"),
    "Crisi dell'euro": ("2011-05", "2011-09"),
    "Covid": ("2020-02", "2020-03"),
    "Inflazione e tassi": ("2022-01", "2022-10"),
}
MC_YEARS, MC_RUNS, MC_SEED = 10, 2000, 0
MC_PERCENTILES = (5, 50, 95)


def ticker_weights(weights: dict) -> tuple[dict, list[str]]:
    """Pesi per classe -> pesi per ETF che sommano a 1, piu' le classi escluse perche' senza ETF."""
    out, skipped = {}, []
    for asset, w in weights.items():
        if w <= 0:
            continue
        if asset in PROXY:
            out[PROXY[asset]] = out.get(PROXY[asset], 0.0) + w
        else:
            skipped.append(asset)
    tot = sum(out.values())
    return ({t: w / tot for t, w in out.items()} if tot else {}), skipped


def portfolio_returns(tw: dict, px: pd.DataFrame) -> pd.Series:
    """Rendimento mensile ribilanciato; NaN nei mesi in cui manca anche un solo ETF."""
    r = px[list(tw)].pct_change(fill_method=None)
    return r.mul(pd.Series(tw)).sum(axis=1, min_count=len(tw)).where(r.notna().all(axis=1))


def trend_returns(tw: dict, px: pd.DataFrame) -> pd.Series:
    """Come portfolio_returns, ma un ETF sotto la media a TREND_MONTHS mesi a fine mese passa in cash (BIL) il mese dopo
    (stessa regola di scripts/backtest_assets.py). NaN finche' la media non esiste per tutti gli ETF."""
    cols = list(tw)
    r = px.pct_change(fill_method=None)
    ma = px[cols].rolling(TREND_MONTHS).mean().shift(1)
    held = r[cols].where(px[cols].shift(1) > ma, r[PROXY[CASH]], axis=0).where(ma.notna())
    return held.mul(pd.Series(tw)).sum(axis=1, min_count=len(tw)).where(held.notna().all(axis=1))


def eur_returns(r: pd.Series, usd_per_eur: pd.Series) -> pd.Series:
    """Rendimenti mensili in dollari visti da chi investe in euro, senza copertura del cambio (26/10/2026, pagina
    Portafoglio): (1 + r) * cambio del mese prima / cambio del mese - 1. usd_per_eur: dollari per un euro a fine mese,
    stesso indice mensile di r (prima del 1999 il marco, allocation.fx_usd_per_local). NaN dove manca il cambio.
    Solo i rendimenti cambiano valuta: segnali, filtro di tendenza e punteggi restano calcolati in dollari."""
    fx = usd_per_eur.reindex(r.index)
    return (1 + r) * fx.shift(1) / fx - 1


def common_window(*series: pd.Series) -> pd.Index:
    """Mesi dell'ultimo tratto consecutivo in cui tutte le serie hanno un rendimento. Prima (fino al 26/10/2026) si
    prendevano tutti i mesi in comune anche con buchi in mezzo: con il filtro in cash prima della nascita di BIL (2007)
    quei mesi sparivano e il backtest cuciva periodi non consecutivi (60/40 dal 2003 con calo massimo -8%)."""
    ok = pd.concat(series, axis=1).notna().all(axis=1)
    ok = ok.loc[:ok[ok].index[-1]] if ok.any() else ok[ok]
    return ok.index[ok[::-1].cumprod()[::-1].astype(bool)]


def summary(r: pd.Series) -> dict | None:
    """Rendimento annuo, valore finale di 1, drawdown massimo e striscia piu' lunga di mesi sotto il massimo precedente.
    None sotto 2 anni."""
    r = r.dropna()
    if len(r) < 24:
        return None
    wealth = (1 + r).cumprod()
    under = wealth < wealth.cummax().clip(lower=1)
    return {"start": r.index[0], "final": wealth.iloc[-1], "cagr": wealth.iloc[-1] ** (12 / len(r)) - 1,
            "dd": min(0.0, (wealth / wealth.cummax().clip(lower=1) - 1).min()),
            "under": int(under.groupby((~under).cumsum()).sum().max())}


def recovery(r: pd.Series, start: str, end: str) -> int | None:
    """Mesi da inizio crisi a quando il portafoglio, dopo il minimo dentro la crisi, torna al valore di partenza; None se
    non ci e' ancora tornato."""
    wealth = (1 + r.loc[start:].dropna()).cumprod()
    crisis = wealth.loc[:end]
    if crisis.empty or crisis.min() >= 1:
        return 0
    after = wealth.loc[crisis.idxmin():]
    back = after[after >= 1]
    return None if back.empty else wealth.index.get_loc(back.index[0]) + 1


def scenario(r: pd.Series, start: str, end: str) -> tuple[float, float] | None:
    """(rendimento totale, drawdown massimo) nella finestra, None se mancano mesi."""
    w = r.loc[start:end]
    if w.empty or w.isna().any() or w.index[0] > pd.Timestamp(start):
        return None
    wealth = (1 + w).cumprod()
    return wealth.iloc[-1] - 1, min(0.0, (wealth / wealth.cummax().clip(lower=1) - 1).min())


def monte_carlo(r: pd.Series) -> dict[int, float] | None:
    """Valore finale di 100 dopo MC_YEARS anni, ricampionando i mesi storici (con reinserimento) MC_RUNS volte."""
    # ponytail: mesi indipendenti, ignora la persistenza delle crisi; bootstrap a blocchi se la banda serve stretta
    r = r.dropna().to_numpy()
    if len(r) < 60:
        return None
    draws = np.random.default_rng(MC_SEED).choice(r, size=(MC_RUNS, MC_YEARS * 12))
    final = 100 * np.prod(1 + draws, axis=1)
    return {p: float(np.percentile(final, p)) for p in MC_PERCENTILES}
