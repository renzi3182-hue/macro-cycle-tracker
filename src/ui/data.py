"""Lettura della cache condivisa dalle pagine (src/app.py, src/ui/market_pages.py): niente chiamate API, solo data/cache.db."""
import pandas as pd
import streamlit as st

from src.classify import allocation
from src.classify.assess import USED_INPUTS, assess
from src.classify.score import ASSET_AREA, HISTORY_AREA, HISTORY_SERIES, UNIVERSE, complete_months, model, monthly_prices, proxy_returns
from src.data import cache


@st.cache_data
def load_indicator(area: str, indicator: str) -> pd.Series:
    return cache.read_indicator_series(area, indicator)


def ui(html: str) -> None:
    st.html(f'<div class="si">{html}</div>')



def spark(ser: pd.Series, n: int = 24) -> list[float] | None:
    return None if len(ser) < 3 else ser.tail(n).round(2).tolist()


@st.cache_data
def load_model() -> dict:
    """Prezzi mensili a mese chiuso (px) e punteggio a cinque pilastri (src/classify/score.py: score, prob, contrib,
    weights), solo mesi con una classifica. Senza serie lunghe o regime USA il modello usa solo gli ETF."""
    px = monthly_prices({t: load_indicator(ASSET_AREA, t) for t in UNIVERSE})
    if px.empty:
        return {"px": px, "score": px}
    px = complete_months(px)
    proxies = proxy_returns({s: v for s in HISTORY_SERIES if not (v := load_indicator(HISTORY_AREA, s)).empty})
    usa = assess("USA", {n: load_indicator("USA", n) for n in USED_INPUTS})
    m = model(px, proxies, usa["history"]["regime"] if usa else None)
    keep = m["score"].notna().any(axis=1)
    return {"px": px, **{k: v[keep] for k, v in m.items() if k in ("score", "prob")},
            "contrib": {k: v[keep] for k, v in m["contrib"].items()}, "weights": m["weights"]}


def load_scores() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Prezzi mensili a mese chiuso e punteggi, solo mesi con una classifica."""
    m = load_model()
    return m["px"], m["score"]


@st.cache_data
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
