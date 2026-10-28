"""Lettura della cache per l'export del sito (src/scheduler/export_site.py): niente chiamate API, solo data/cache.db.
Ogni funzione legge una volta per processo (functools.cache): chi la chiama non deve modificare il risultato."""
from functools import cache as memo

import pandas as pd

from src.classify import allocation
from src.classify.assess import USED_INPUTS, assess
from src.classify.score import ASSET_AREA, HISTORY_AREA, HISTORY_SERIES, UNIVERSE, complete_months, model, monthly_prices, proxy_returns
from src.classify.stress import EXTRA_ETF
from src.data import cache


@memo
def load_indicator(area: str, indicator: str) -> pd.Series:
    return cache.read_indicator_series(area, indicator)


@memo
def load_model() -> dict:
    """Prezzi mensili a mese chiuso (px) e punteggio a cinque pilastri (src/classify/score.py: score, prob, contrib,
    weights), solo mesi con una classifica. Senza serie lunghe o regime USA il modello usa solo gli ETF. px ha anche
    gli ETF fuori dal punteggio (EXTRA_ETF, colonne vuote se mancano in cache) per filtro di tendenza e stress test."""
    px = monthly_prices({t: load_indicator(ASSET_AREA, t) for t in UNIVERSE})
    if px.empty:
        return {"px": px, "score": px}
    px = complete_months(px)
    proxies = proxy_returns({s: v for s in HISTORY_SERIES if not (v := load_indicator(HISTORY_AREA, s)).empty})
    usa = assess("USA", {n: load_indicator("USA", n) for n in USED_INPUTS})
    m = model(px, proxies, usa["history"]["regime"] if usa else None)
    keep = m["score"].notna().any(axis=1)
    extra = monthly_prices({t: load_indicator(ASSET_AREA, t) for t in EXTRA_ETF}).reindex(index=px.index, columns=EXTRA_ETF)
    return {"px": px.join(extra), **{k: v[keep] for k, v in m.items() if k in ("score", "prob")},
            "contrib": {k: v[keep] for k, v in m["contrib"].items()}, "weights": m["weights"],
            "usa_regime": usa["regime"] if usa else None}  # regime USA di oggi, per le frecce dei settori nella Classifica


@memo
def load_usd_per_eur() -> pd.Series:
    """Dollari per euro a fine mese sui mesi dei prezzi di load_model (prima del 1999 il marco), per il Portafoglio in euro."""
    return allocation.fx_usd_per_local(load_indicator, load_model()["px"].index)["Eurozona"]


def load_scores() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Prezzi mensili a mese chiuso e punteggi, solo mesi con una classifica."""
    m = load_model()
    return m["px"], m["score"]


@memo
def load_allocation() -> dict:
    """Le tre classifiche di lungo periodo (src/classify/allocation.py): per ognuna score, prob, weights del modello
    ristimato ogni gennaio, feats (pilastri in posizione) e raw (valori dei pilastri)."""
    asset_px = monthly_prices({t: load_indicator(ASSET_AREA, t) for t in allocation.COUNTRY_ETF.values()})
    if asset_px.empty:
        return {}
    d = allocation.load(load_indicator, asset_px, load_indicator(HISTORY_AREA, "Mkt"))
    out = {}
    for name, build in (("Paesi", allocation.countries), ("Classi di asset", allocation.asset_classes),
                        ("Valute", allocation.currencies)):
        p = build(d)
        out[name] = {**allocation.model(p), "feats": p["feats"], "raw": p["raw"]}
    return out
