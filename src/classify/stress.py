import numpy as np
import pandas as pd

from src.config.asset_allocation import CASH, TREND_PROXY

# Stress test di un portafoglio per classi di asset (06/10/2026): rendimento nelle crisi passate e banda Monte Carlo.
# Ogni classe usa l'ETF del filtro di tendenza (tutto l'azionario = SPY), il cash usa SHY. Classi senza ETF
# (credito corporate) escono e i pesi si rinormalizzano. Ribilanciamento mensile, niente costi.
# Gli ETF partono fra il 1993 (SPY) e il 2006 (DBC): una crisi senza dati per tutti gli asset resta n/d.
PROXY = {**TREND_PROXY, CASH: "SHY"}
# Crisi: dal mese dopo il massimo dell'S&P 500 al minimo, a fine mese
SCENARIOS = {
    "Bolla internet": ("2000-09", "2002-09"),
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
