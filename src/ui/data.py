"""Lettura della cache condivisa dalle pagine (src/app.py, src/ui/market_pages.py): niente chiamate API, solo data/cache.db."""
import pandas as pd
import streamlit as st

from src.classify.score import ASSET_AREA, UNIVERSE, complete_months, monthly_prices, scores
from src.data import cache


@st.cache_data
def load_indicator(area: str, indicator: str) -> pd.Series:
    return cache.read_indicator_series(area, indicator)


def ui(html: str) -> None:
    st.html(f'<div class="si">{html}</div>')



def spark(ser: pd.Series, n: int = 24) -> list[float] | None:
    return None if len(ser) < 3 else ser.tail(n).round(2).tolist()


@st.cache_data
def load_scores() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Prezzi mensili a mese chiuso e punteggi (src/classify/score.py), solo mesi con una classifica."""
    px = monthly_prices({t: load_indicator(ASSET_AREA, t) for t in UNIVERSE})
    if px.empty:
        return px, px
    px = complete_months(px)
    return px, scores(px).dropna(how="all")

