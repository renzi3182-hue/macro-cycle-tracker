import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from src.config.asset_allocation import ASSET_ALLOCATION, combined_portfolio_weights
from src.data import cache

AREA_FLAGS = {
    "USA": "\U0001F1FA\U0001F1F8",
    "Eurozona": "\U0001F1EA\U0001F1FA",
    "Italia": "\U0001F1EE\U0001F1F9",
    "UK": "\U0001F1EC\U0001F1E7",
    "Giappone": "\U0001F1EF\U0001F1F5",
}

REGIME_COLORS = {
    "Espansione": "#2e7d32",
    "Reflazione": "#1565c0",
    "Stagflazione": "#c62828",
    "Deflazione": "#6a1b9a",
}

st.set_page_config(page_title="Macro Cycle Tracker", page_icon="\U0001F4CA", layout="wide")

st.markdown(
    """
    <style>
    .regime-badge {
        display: inline-block;
        padding: 4px 14px;
        border-radius: 999px;
        color: white;
        font-weight: 600;
        font-size: 0.95rem;
        margin-top: 4px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("\U0001F4CA Macro Cycle Tracker")
st.caption("Regime macro e fase del ciclo economico per USA, Eurozona, Italia, UK, Giappone")

with st.sidebar:
    st.header("Impostazioni")
    risk_profile = st.select_slider("Profilo di rischio", options=["Basso", "Medio", "Alto"], value="Medio")

regimes_by_area = {}
for area in AREA_FLAGS:
    history = cache.read_last_two_classifications(area)
    if history:
        regimes_by_area[area] = history[0]["regime"]

st.subheader("Portafoglio diversificato multi-nazione")
if regimes_by_area:
    weights = combined_portfolio_weights(regimes_by_area, risk_profile)
    fig, ax = plt.subplots(figsize=(5, 5), dpi=150)
    fig.patch.set_alpha(0)
    ax.pie(
        weights.values(),
        labels=weights.keys(),
        autopct="%1.0f%%",
        colors=plt.cm.Set2.colors,
        textprops={"fontsize": 9},
    )
    ax.axis("equal")
    col_left, col_mid, col_right = st.columns([1, 2, 1])
    with col_mid:
        st.pyplot(fig)
else:
    st.info("Nessun dato in cache per calcolare il portafoglio.")

st.divider()

tabs = st.tabs([f"{flag} {area}" for area, flag in AREA_FLAGS.items()])
for tab, area in zip(tabs, AREA_FLAGS):
    with tab:
        history = cache.read_last_two_classifications(area)

        if not history:
            st.info("Nessun dato in cache. Esegui `python -m src.scheduler.update_data` per popolare.")
            continue

        current = history[0]
        changed = len(history) > 1 and (
            current["regime"] != history[1]["regime"] or current["phase"] != history[1]["phase"]
        )
        color = REGIME_COLORS.get(current["regime"], "#555555")

        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            c1.markdown(
                f"**Regime macro**<br>"
                f"<span class='regime-badge' style='background:{color}'>{current['regime']}</span>",
                unsafe_allow_html=True,
            )
            c2.metric("Fase ciclo economico", current["phase"])
            if changed:
                c3.warning("Cambiato dall'ultimo aggiornamento")
            else:
                c3.caption("Nessun cambio dall'ultimo aggiornamento")

        growth = cache.read_indicator_series(area, "growth_yoy")
        inflation = cache.read_indicator_series(area, "inflation_yoy")
        if not growth.empty or not inflation.empty:
            chart_df = pd.DataFrame({"Crescita YoY %": growth, "Inflazione YoY %": inflation})
            st.line_chart(chart_df)

        allocation = ASSET_ALLOCATION.get(current["regime"], [])
        if allocation:
            st.caption("Asset allocation storicamente favorita per questo regime:")
            st.write(" · ".join(allocation))
