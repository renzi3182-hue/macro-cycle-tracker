import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from src.config.asset_allocation import ASSET_ALLOCATION, combined_portfolio_weights
from src.data import cache

AREAS = ["USA", "Eurozona", "Italia", "UK", "Giappone"]

st.set_page_config(page_title="Macro Cycle Tracker", layout="wide")
st.title("Macro Cycle Tracker")

st.header("Portafoglio diversificato multi-nazione")
risk_profile = st.select_slider("Profilo di rischio", options=["Basso", "Medio", "Alto"], value="Medio")

regimes_by_area = {}
for area in AREAS:
    history = cache.read_last_two_classifications(area)
    if history:
        regimes_by_area[area] = history[0]["regime"]

if regimes_by_area:
    weights = combined_portfolio_weights(regimes_by_area, risk_profile)
    fig, ax = plt.subplots()
    ax.pie(weights.values(), labels=weights.keys(), autopct="%1.0f%%")
    ax.axis("equal")
    st.pyplot(fig)
else:
    st.info("Nessun dato in cache per calcolare il portafoglio.")

st.divider()

for area in AREAS:
    st.header(area)
    history = cache.read_last_two_classifications(area)

    if not history:
        st.info("Nessun dato in cache. Esegui `python -m src.scheduler.update_data` per popolare.")
        continue

    current = history[0]
    changed = len(history) > 1 and (
        current["regime"] != history[1]["regime"] or current["phase"] != history[1]["phase"]
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Regime macro", current["regime"])
    col2.metric("Fase ciclo economico", current["phase"])
    if changed:
        col3.warning("Cambiato dall'ultimo aggiornamento")
    else:
        col3.caption("Nessun cambio dall'ultimo aggiornamento")

    growth = cache.read_indicator_series(area, "growth_yoy")
    inflation = cache.read_indicator_series(area, "inflation_yoy")
    if not growth.empty or not inflation.empty:
        chart_df = pd.DataFrame({"Crescita YoY %": growth, "Inflazione YoY %": inflation})
        st.line_chart(chart_df)

    allocation = ASSET_ALLOCATION.get(current["regime"], [])
    if allocation:
        st.caption("Asset allocation storicamente favorita per questo regime:")
        st.write(", ".join(allocation))

    st.divider()
