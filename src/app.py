import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from streamlit_lightweight_charts import renderLightweightCharts

from src.classify.currency import CURRENCIES, PAIRS, cot_component, momentum_returns, pair_view, strength_score, vix_component
from src.classify.gip import gip_view
from src.classify.leading import leading_risk
from src.classify.regime import direction_position, regime_history, regime_probabilities
from src.classify.recession import recession_confirmed, sahm_gap
from src.classify.positioning import percentile_rank, positioning_label
from src.data.fetch_cot import CONTRACTS
from src.config.asset_allocation import ALL_WEATHER_WEIGHTS, ASSET_ALLOCATION, combined_portfolio_weights
from src.data import cache
from src.ui.overview import overview_html, signal

AREA_CODES = {"USA": "USA", "Eurozona": "EUR", "Italia": "ITA", "UK": "UK", "Giappone": "JP"}
AREA_FLAGS = {
    "USA": "\U0001F1FA\U0001F1F8",
    "Eurozona": "\U0001F1EA\U0001F1FA",
    "Italia": "\U0001F1EE\U0001F1F9",
    "UK": "\U0001F1EC\U0001F1E7",
    "Giappone": "\U0001F1EF\U0001F1F5",
}

REGIME_COLORS = {
    "Espansione": "#34D399",
    "Reflazione": "#60A5FA",
    "Stagflazione": "#F87171",
    "Deflazione": "#A78BFA",
}

REGIME_MEANING = {
    "Espansione": "crescita in accelerazione e inflazione in salita",
    "Reflazione": "crescita in accelerazione e inflazione in calo",
    "Stagflazione": "crescita in rallentamento e inflazione in salita",
    "Deflazione": "crescita in rallentamento e inflazione in calo",
}

PHASE_MEANING = {
    "Espansione": "PIL positivo e in accelerazione",
    "Rallentamento": "PIL ancora positivo ma in decelerazione",
    "Recessione": "PIL negativo (o vicino a zero) e in decelerazione",
    "Ripresa": "PIL in accelerazione dopo un periodo debole",
}


INDICATOR_COLORS = {
    "Crescita YoY %": "#34D399",
    "Inflazione YoY %": "#F87171",
    "Disoccupazione %": "#60A5FA",
}

RISK_PROFILE_LABELS = {"Basso": "Conservativo", "Medio": "Bilanciato", "Alto": "Aggressivo"}
ALL_WEATHER = "All Weather"

# Nomi accorciati solo per l'etichetta nel grafico a torta (spazio limitato in
# layout a 3 colonne): la lista completa resta invariata altrove (asset
# allocation testuale nelle tab).
ASSET_SHORT_LABELS = {
    "Obbligazioni indicizzate all'inflazione": "Obbl. indicizzate",
    "Obbligazioni governative lunga durata": "Obbl. governative",
    "Obbligazioni lunga durata": "Obbl. lunga durata",
    "Azionario value/difensivo": "Az. value/difensivo",
    "Azionario difensivo": "Az. difensivo",
    "Azionario growth": "Az. growth",
    "Credito corporate": "Credito corp.",
    "Obbligazioni medio termine": "Obbl. medio term.",
}

PIE_R = 150


@st.cache_data(ttl=300)
def load_classifications(area: str) -> list[dict]:
    return cache.read_last_two_classifications(area)


@st.cache_data(ttl=300)
def load_indicator(area: str, indicator: str) -> pd.Series:
    return cache.read_indicator_series(area, indicator)


def pie_html(weights: dict, colors: list[str]) -> str:
    # Torta 2D piatta disegnata in SVG. Ogni spicchio entra volando da fuori
    # schermo nella propria direzione (--dx/--dy) e converge nella torta via
    # CSS keyframe. Le etichette non stanno sul raggio dello spicchio (si
    # accavallano quando piu' spicchi sottili sono vicini in angolo): vanno
    # invece in due colonne fisse (sinistra/destra), impilate verticalmente
    # con spaziatura minima forzata, collegate allo spicchio da una linea guida.
    svg_w, svg_h = 780, 400
    cx, cy = svg_w / 2, svg_h / 2
    label_col_x = {"left": cx - (PIE_R + 58), "right": cx + (PIE_R + 58)}
    min_gap = 15
    top_margin, bottom_margin = 16, svg_h - 16

    total = sum(weights.values()) or 1
    slices = []
    theta = 0.0
    for i, (label, value) in enumerate(weights.items()):
        pct = value / total
        sweep = pct * 360
        slices.append({"label": label, "pct": pct, "start": theta, "end": theta + sweep, "color": colors[i % len(colors)]})
        theta += sweep

    def point(angle_deg, r):
        t = math.radians(angle_deg - 90)
        return cx + r * math.cos(t), cy + r * math.sin(t)

    labels = []
    for i, s in enumerate(slices):
        mid = (s["start"] + s["end"]) / 2
        ex, ey = point(mid, PIE_R)
        ideal_x, ideal_y = point(mid, PIE_R + 18)
        side = "right" if ideal_x >= cx else "left"
        text = f'{ASSET_SHORT_LABELS.get(s["label"], s["label"])} {s["pct"] * 100:.0f}%'
        labels.append({"i": i, "side": side, "ex": ex, "ey": ey, "y": ideal_y, "text": text, "color": s["color"]})

    for side in ("left", "right"):
        items = sorted((l for l in labels if l["side"] == side), key=lambda l: l["y"])
        for k in range(1, len(items)):
            if items[k]["y"] < items[k - 1]["y"] + min_gap:
                items[k]["y"] = items[k - 1]["y"] + min_gap
        if items and items[-1]["y"] > bottom_margin:
            overflow = items[-1]["y"] - bottom_margin
            for l in items:
                l["y"] -= overflow
        if items and items[0]["y"] < top_margin:
            shift = top_margin - items[0]["y"]
            for l in items:
                l["y"] += shift

    groups = []
    for i, s in enumerate(slices):
        x1, y1 = point(s["start"], PIE_R)
        x2, y2 = point(s["end"], PIE_R)
        large_arc = 1 if s["end"] - s["start"] > 180 else 0
        path = f"M{cx},{cy} L{x1:.1f},{y1:.1f} A{PIE_R},{PIE_R} 0 {large_arc} 1 {x2:.1f},{y2:.1f} Z"

        li = labels[i]
        lx = label_col_x[li["side"]]
        sign = 1 if li["side"] == "right" else -1
        bend_x = cx + (PIE_R + 14) * sign
        anchor = "start" if li["side"] == "right" else "end"
        text_x = lx + 6 * sign

        mid_rad = math.radians((s["start"] + s["end"]) / 2 - 90)
        dx, dy = math.cos(mid_rad) * 420, math.sin(mid_rad) * 420

        groups.append(
            f'<g class="pie-slice" style="--dx:{dx:.0f}px; --dy:{dy:.0f}px; --delay:{i * 90}ms">'
            f'<path d="{path}" fill="{s["color"]}" stroke="#0F172A" stroke-width="1.5" />'
            f'<polyline points="{li["ex"]:.1f},{li["ey"]:.1f} {bend_x:.1f},{li["y"]:.1f} {lx:.1f},{li["y"]:.1f}" '
            f'fill="none" stroke="{s["color"]}" stroke-width="1.2" opacity="0.7" />'
            f'<text x="{text_x:.1f}" y="{li["y"]:.1f}" text-anchor="{anchor}" dominant-baseline="middle" class="pie-label">{li["text"]}</text>'
            f'</g>'
        )

    return f"""<!DOCTYPE html>
    <html><head><style>
    @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@700&display=swap');
    html, body {{ margin: 0; padding: 0; background: transparent; overflow: hidden; }}
    .pie-slice {{
        opacity: 0;
        transform: translate(var(--dx), var(--dy));
        animation: pie-in 0.9s cubic-bezier(.2,.8,.2,1) var(--delay) forwards;
        transform-box: fill-box;
        transform-origin: center;
    }}
    @keyframes pie-in {{ to {{ opacity: 1; transform: translate(0, 0); }} }}
    .pie-label {{
        fill: #F1F5F9;
        font: 700 14px 'Nunito', sans-serif;
        paint-order: stroke;
        stroke: #0F172A;
        stroke-width: 3px;
    }}
    </style></head><body>
    <svg viewBox="0 0 {svg_w} {svg_h}" width="100%" height="360" style="overflow: visible;">{''.join(groups)}</svg>
    </body></html>
    """


def area_probabilities(area: str, growth: pd.Series, inflation: pd.Series) -> tuple[dict | None, dict | None]:
    probs = regime_probabilities(growth, inflation) if len(growth) > 3 and len(inflation) > 3 else None
    gip = None
    if area == "USA":
        ip, ff = load_indicator(area, "industrial_production"), load_indicator(area, "fed_funds")
        if len(ip) > 3 and len(inflation) > 3:
            gip = gip_view(ip, inflation, ff)
            if probs:  # media dei due modelli: PIL trimestrale + dati mensili
                probs = {r: (probs[r] + gip["probabilities"][r]) / 2 for r in probs}
    return probs, gip


def overview_areas() -> list[dict]:
    areas = []
    for area in AREA_FLAGS:
        history = load_classifications(area)
        if not history:
            continue
        growth = load_indicator(area, "growth_yoy")
        inflation = load_indicator(area, "inflation_yoy")
        unemployment = load_indicator(area, "unemployment_rate")
        enough = len(growth) > 3 and len(inflation) > 3
        areas.append({
            "area": area,
            "code": AREA_CODES[area],
            "regime": history[0]["regime"],
            "phase": history[0]["phase"],
            "probs": area_probabilities(area, growth, inflation)[0],
            "pos": direction_position(growth, inflation) if enough else None,
            "signals": [
                ("crescita", *signal(growth, True)),
                ("inflazione", *signal(inflation, False)),
                ("disoccupazione", *signal(unemployment, False)),
            ],
            "history": regime_history(growth, inflation) if enough else None,
        })
    return areas


def describe_regime(regime: str, phase: str, growth: pd.Series, inflation: pd.Series, unemployment: pd.Series) -> str:
    parts = []
    if not growth.empty:
        parts.append(f"crescita {growth.iloc[-1]:+.1f}%")
    if not inflation.empty:
        parts.append(f"inflazione {inflation.iloc[-1]:+.1f}%")
    if not unemployment.empty:
        parts.append(f"disoccupazione {unemployment.iloc[-1]:.1f}%")
    data_txt = ", ".join(parts)

    regime_txt = REGIME_MEANING.get(regime, regime.lower())
    phase_txt = PHASE_MEANING.get(phase, phase.lower())
    return (
        f"Regime **{regime}** ({regime_txt}); ciclo in **{phase}** ({phase_txt})."
        + (f" Ultimo dato: {data_txt}." if data_txt else "")
    )

st.set_page_config(page_title="Macro Cycle Tracker", page_icon=":material/monitoring:", layout="wide")

# Animazioni richieste esplicitamente dall'utente (ispirazione dashboard
# fintech scure con badge "glow" e card che reagiscono all'hover). Il resto
# del tema (colori/font) resta in .streamlit/config.toml per convenzione.
st.html(
    """
    <style>
    @media (prefers-reduced-motion: no-preference) {
        .regime-badge {
            animation: badge-in 0.5s ease-out both, badge-glow 2.8s ease-in-out 0.5s infinite;
        }
        [class*="st-key-regime-card-"] {
            animation: card-in 0.4s ease-out both;
        }
        [class*="st-key-indicators-section-"] {
            animation: card-in 0.5s ease-out 0.1s both;
        }
        body::before, body::after {
            animation-play-state: running;
        }
    }
    /* Sfondo "ambient": due aloni sfumati che derivano lentamente, come su
       disko.media/butter.video. Statici (nessun animation-play-state=running)
       se l'utente preferisce meno movimento. */
    body::before, body::after {
        content: "";
        position: fixed;
        border-radius: 50%;
        filter: blur(50px);
        z-index: -1;
        pointer-events: none;
        opacity: 0.28;
        animation-play-state: paused;
        will-change: transform;
    }
    body::before {
        width: 360px;
        height: 360px;
        top: -140px;
        left: -120px;
        background: #60A5FA;
        animation: ambient-drift-1 24s ease-in-out infinite alternate;
    }
    body::after {
        width: 320px;
        height: 320px;
        bottom: -140px;
        right: -100px;
        background: #A78BFA;
        animation: ambient-drift-2 28s ease-in-out infinite alternate;
    }
    @keyframes ambient-drift-1 {
        from { transform: translate(0, 0); }
        to { transform: translate(70px, 50px); }
    }
    @keyframes ambient-drift-2 {
        from { transform: translate(0, 0); }
        to { transform: translate(-60px, -40px); }
    }
    [class*="st-key-regime-card-"] {
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    [class*="st-key-regime-card-"]:hover {
        transform: translateY(-3px);
        box-shadow: 0 10px 28px rgba(0, 0, 0, 0.35);
    }
    .portfolio-badge {
        display: inline-block;
        padding: 6px 16px;
        border-radius: 10px;
        background: #1E293B;
        color: #F1F5F9;
        font-weight: 700;
        font-size: 1rem;
        margin-bottom: 8px;
    }
    .regime-badge {
        display: inline-block;
        padding: 4px 14px;
        border-radius: 999px;
        color: white;
        font-weight: 600;
        font-size: 0.95rem;
        margin-top: 4px;
        --glow: var(--badge-color, #60A5FA);
        box-shadow: 0 0 0 rgba(0, 0, 0, 0);
    }
    @keyframes badge-in {
        from { opacity: 0; transform: translateY(6px) scale(0.96); }
        to { opacity: 1; transform: translateY(0) scale(1); }
    }
    @keyframes badge-glow {
        0%, 100% { box-shadow: 0 0 4px 0 var(--glow); }
        50% { box-shadow: 0 0 16px 2px var(--glow); }
    }
    @keyframes card-in {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    </style>
    """
)

st.title("Macro cycle tracker", icon=":material/monitoring:")
st.caption("Regime macro e fase del ciclo economico per USA, Eurozona, Italia, UK, Giappone")

with st.sidebar:
    st.header("Impostazioni")
    # All Weather non e' un profilo di rischio: pesi statici, indipendenti da regime e profilo.
    risk_profile = st.select_slider("Profilo di rischio", options=["Basso", "Medio", "Alto", ALL_WEATHER], value="Medio")

regimes_by_area = {}
for area in AREA_FLAGS:
    history = load_classifications(area)
    if history:
        regimes_by_area[area] = history[0]["regime"]

st.subheader("Portafoglio diversificato multi-nazione")
if regimes_by_area:
    weights = ALL_WEATHER_WEIGHTS if risk_profile == ALL_WEATHER else combined_portfolio_weights(regimes_by_area, risk_profile)
    col_left, col_mid, col_right = st.columns([1, 2, 1])
    with col_mid, st.container(key="pie-chart"):
        st.markdown(
            f'<div class="portfolio-badge">{RISK_PROFILE_LABELS.get(risk_profile, ALL_WEATHER)}</div>',
            unsafe_allow_html=True,
        )
        components.html(
            pie_html(weights, ["#60A5FA", "#34D399", "#A78BFA", "#F87171", "#FBBF24", "#38BDF8", "#94A3B8"]),
            height=380,
        )
else:
    st.info("Nessun dato in cache per calcolare il portafoglio.")

st.divider()

tabs = st.tabs(["🌍 Panoramica"] + [f"{flag} {area}" for area, flag in AREA_FLAGS.items()] + ["📊 Contesto mercato", "💱 Valute"])
with tabs[0]:
    overview = overview_areas()
    if overview:
        st.html(overview_html(overview))
    else:
        st.info("Nessun dato in cache. Esegui `python -m src.scheduler.update_data` per popolare.")

for tab, area in zip(tabs[1:], AREA_FLAGS):
    with tab:
        history = load_classifications(area)

        if not history:
            st.info("Nessun dato in cache. Esegui `python -m src.scheduler.update_data` per popolare.")
            continue

        current = history[0]
        changed = len(history) > 1 and (
            current["regime"] != history[1]["regime"] or current["phase"] != history[1]["phase"]
        )
        color = REGIME_COLORS.get(current["regime"], "#555555")

        growth = load_indicator(area, "growth_yoy")
        inflation = load_indicator(area, "inflation_yoy")
        unemployment = load_indicator(area, "unemployment_rate")

        with st.container(border=True, key=f"regime-card-{area}"):
            c1, c2, c3 = st.columns(3)
            c1.markdown(
                f"**Regime macro**<br>"
                f"<span class='regime-badge' style='background:{color}; --badge-color:{color}'>{current['regime']}</span>",
                unsafe_allow_html=True,
            )
            c2.metric("Fase ciclo economico", current["phase"])
            if changed:
                c3.warning("Cambiato dall'ultimo aggiornamento")
            else:
                c3.caption("Nessun cambio dall'ultimo aggiornamento")
            st.markdown(describe_regime(current["regime"], current["phase"], growth, inflation, unemployment))

            probs, gip = area_probabilities(area, growth, inflation)
            if probs:
                st.markdown("**Probabilita' per regime**" + (" (media modello PIL e modello mensile)" if gip else ""))
                for col, (regime_name, p) in zip(st.columns(4), sorted(probs.items(), key=lambda x: -x[1])):
                    col.metric(regime_name, f"{p * 100:.0f}%")
                st.caption(
                    "Stima non calibrata su frequenze storiche. L'etichetta del regime ha memoria (deadband): "
                    "puo' non coincidere con la probabilita' piu' alta."
                )
            if gip:
                agree = "concorda con il" if gip["regime"] == current["regime"] else "diverge dal"
                st.caption(
                    f"Regime mensile alternativo (stile Hedgeye GIP, produzione industriale + CPI): "
                    f"**{gip['regime']}**, {agree} regime principale. Politica Fed: {gip['policy']}."
                )

        if area == "USA":
            curve = load_indicator(area, "yield_curve")
            spread = load_indicator(area, "credit_spread")
            fin = load_indicator(area, "fin_conditions")
            if not (curve.empty and spread.empty and fin.empty):
                risk = leading_risk(curve, spread, fin)
                with st.container(border=True, key="leading-card"):
                    st.markdown(f"**Indicatori anticipatori**: rischio {risk['level']} ({risk['score']}/3 segnali)")
                    for col, (label, ser, unit) in zip(
                        st.columns(3),
                        [("Curva 10Y-3M", curve, " pp"), ("Spread Baa-10Y", spread, " pp"), ("NFCI", fin, "")],
                    ):
                        col.metric(label, f"{ser.iloc[-1]:.2f}{unit}" if not ser.empty else "n/d")
                    active = [k for k, on in risk["signals"].items() if on]
                    st.caption("Segnali attivi: " + (", ".join(active) if active else "nessuno"))
                    gap = sahm_gap(unemployment).dropna()
                    prob = load_indicator(area, "recession_prob")
                    if not gap.empty and not prob.empty:
                        st.caption(
                            f"Recessione in corso: Regola di Sahm {gap.iloc[-1]:+.2f} pp (soglia 0.5), "
                            f"Chauvet-Piger {prob.iloc[-1]:.1f}%. "
                            + ("CONFERMATA" if recession_confirmed(unemployment, prob) else "Non confermata")
                        )

        if not growth.empty or not inflation.empty or not unemployment.empty:
            # Le serie hanno frequenze diverse (crescita/disoccupazione spesso
            # trimestrali o mensili, inflazione mensile): senza ffill l'unione
            # degli indici lascia buchi (NaN) tra una rilevazione e l'altra, e
            # st.line_chart non collega i punti oltre un NaN, quindi le linee
            # piu' rade spariscono su schermi stretti (mobile).
            chart_df = pd.DataFrame({
                "Crescita YoY %": growth,
                "Inflazione YoY %": inflation,
                "Disoccupazione %": unemployment,
            }).sort_index().ffill()

            with st.container(key=f"indicators-section-{area}"):
                visible = st.pills(
                    "Indicatori nel grafico",
                    list(chart_df.columns),
                    selection_mode="multi",
                    default=list(chart_df.columns),
                    key=f"visible_indicators_{area}",
                )
                if visible:
                    series_config = [
                        {
                            "type": "Line",
                            "data": [
                                {"time": idx.strftime("%Y-%m-%d"), "value": round(float(v), 2)}
                                for idx, v in chart_df[col].dropna().items()
                            ],
                            "options": {"color": INDICATOR_COLORS.get(col, "#94A3B8"), "lineWidth": 2},
                        }
                        for col in visible
                    ]
                    # Nome indicatore come legenda statica sopra il grafico, non come
                    # label nativa lightweight-charts: quella (title + value uniti in
                    # un'unica pillola ancorata a destra) si allarga verso sinistra
                    # sopra le linee quando il testo e' lungo, senza modo di
                    # riordinare value/title o contenerla nel gutter dell'asse.
                    legend_html = "".join(
                        f'<span style="display:inline-flex; align-items:center; gap:6px; margin-right:16px;">'
                        f'<span style="width:10px; height:10px; border-radius:50%; background:{INDICATOR_COLORS.get(col, "#94A3B8")}; display:inline-block;"></span>'
                        f'<span style="color:#CBD5E1; font-size:0.85rem;">{col}</span>'
                        f'</span>'
                        for col in visible
                    )
                    st.markdown(f'<div style="margin-bottom:6px;">{legend_html}</div>', unsafe_allow_html=True)
                    renderLightweightCharts(
                        [{
                            "chart": {
                                "layout": {"background": {"type": "solid", "color": "transparent"}, "textColor": "#CBD5E1"},
                                "grid": {
                                    "vertLines": {"color": "rgba(148,163,184,0.1)"},
                                    "horzLines": {"color": "rgba(148,163,184,0.1)"},
                                },
                                "rightPriceScale": {"visible": True, "borderColor": "rgba(148,163,184,0.3)"},
                                "timeScale": {"borderColor": "rgba(148,163,184,0.3)", "rightOffset": 6},
                                "height": 320,
                            },
                            "series": series_config,
                        }],
                        key=f"lwc_{area}",
                    )
                else:
                    st.info("Seleziona almeno un indicatore per vederlo nel grafico.")

                indicators = [
                    ("Crescita YoY %", growth),
                    ("Inflazione YoY %", inflation),
                    ("Disoccupazione %", unemployment),
                ]
                non_empty = [(label, series) for label, series in indicators if not series.empty]
                if non_empty:
                    cols = st.columns(len(non_empty))
                    for col, (label, series) in zip(cols, non_empty):
                        with col:
                            st.caption(label)
                            recent = series.tail(5).sort_index(ascending=False)
                            st.dataframe(
                                pd.DataFrame({
                                    "Data": recent.index.strftime("%d/%m/%Y"),
                                    "Valore": recent.values.round(1),
                                }),
                                hide_index=True,
                                width="stretch",
                            )

        allocation = ASSET_ALLOCATION.get(current["regime"], [])
        if allocation:
            st.caption("Asset allocation storicamente favorita per questo regime:")
            st.write(" · ".join(allocation))


with tabs[-2]:
    st.caption(
        "Solo informativo: non entra nella classificazione di regime e ciclo. "
        "COT = posizione netta degli speculatori (CFTC, aggiornata il venerdi', dato del martedi'), "
        "percentile sugli ultimi 5 anni."
    )
    st.markdown("**Aspettative del mercato (USA)**")
    for col, (label, key, unit) in zip(
        st.columns(5),
        [
            ("VIX", "vix", ""),
            ("MOVE (vol. Treasury)", "move", ""),
            ("Prob. recessione in corso", "USA:recession_prob", "%"),
            ("Inflazione attesa 5Y", "breakeven_5y", "%"),
            ("Inflazione attesa 5Y5Y", "breakeven_5y5y", "%"),
        ],
    ):
        ser_area, _, ser_key = key.rpartition(":")
        ser = load_indicator(ser_area or "Mercati", ser_key)
        if ser.empty:
            col.metric(label, "n/d")
        else:
            delta = f"{ser.iloc[-1] - ser.iloc[-2]:+.2f} vs rilev. prec." if len(ser) > 1 else None
            col.metric(label, f"{ser.iloc[-1]:.1f}{unit}" if key in ("vix", "move") else f"{ser.iloc[-1]:.2f}{unit}", delta)
    st.markdown("**Prossimi eventi macro**")
    today = pd.Timestamp.today().normalize()
    upcoming = []
    for name in ["FOMC", "CPI", "Occupazione (NFP)", "PIL"]:
        future = load_indicator("Calendario", name)
        future = future[future.index >= today]
        if not future.empty:
            upcoming.append({"Evento": name, "Data": future.index[0], "Fra (giorni)": (future.index[0] - today).days})
    if upcoming:
        df = pd.DataFrame(upcoming).sort_values("Data")
        df["Data"] = df["Data"].dt.strftime("%d/%m/%Y")
        st.dataframe(df, hide_index=True, width="stretch")
    else:
        st.caption("Nessuna data in cache: esegui l'aggiornamento dati.")
    st.markdown("**Posizionamento speculatori (COT)**")
    rows = []
    for name in CONTRACTS:
        cot = load_indicator("Mercati", f"cot_{name}")
        if cot.empty:
            continue
        pct = percentile_rank(cot)
        rows.append({
            "Mercato": name,
            "Netto speculatori (% OI)": round(float(cot.iloc[-1]), 1),
            "Percentile 5 anni": round(pct),
            "Posizionamento": positioning_label(pct),
            "Data": cot.index[-1].strftime("%d/%m/%Y"),
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        st.info("Nessun dato COT in cache. Esegui `python -m src.scheduler.update_data`.")


CCY_COT = {"USD": "Dollaro (DXY)", "EUR": "Euro", "GBP": "Sterlina", "JPY": "Yen"}
CCY_AREA = {"USD": "USA", "EUR": "Eurozona", "GBP": "UK", "JPY": "Giappone"}
LABEL_COLORS = {"Buy": "#34D399", "Sell": "#F87171", "Neutra": "#9CA3AF"}


def _last(area: str, indicator: str) -> float | None:
    ser = load_indicator(area, indicator)
    return None if ser.empty else float(ser.iloc[-1])


def currency_scores() -> dict[str, dict]:
    try:
        mom = momentum_returns(*(load_indicator("Valute", n) for n in ("eurusd", "gbpusd", "usdjpy")))
    except Exception:  # serie assente o troppo corta
        mom = {}
    vix = load_indicator("Mercati", "vix")
    vix_pct = None if vix.empty else percentile_rank(vix)
    out = {}
    for ccy in CURRENCIES:
        cot = load_indicator("Mercati", f"cot_{CCY_COT[ccy]}")
        rate, infl = _last("Valute", f"rate_{ccy}"), _last(CCY_AREA[ccy], "inflation_yoy")
        real = None if rate is None or infl is None else rate - infl
        res = strength_score(real, _last(CCY_AREA[ccy], "growth_yoy"), mom.get(ccy),
                             cot_component(None if cot.empty else percentile_rank(cot)), vix_component(ccy, vix_pct))
        res["real_rate"], res["rate"], res["inflation"] = real, rate, infl
        out[ccy] = res
    return out


with tabs[-1]:
    st.caption(
        "Solo informativo, non e' consulenza. Forza 1-100 assoluta = 25% crescita PIL, 20% momentum 3 mesi del cambio, "
        "25% COT (contrarian: speculatori affollati long = meno punti), 30% VIX (risk-off favorisce JPY/USD, penalizza GBP/EUR). "
        "Il tasso reale e' mostrato ma pesa 0% (backtest: nessun potere predittivo). "
        "Coppia: 50 + (forza base - forza quota)/2; "
        "Buy >= 60, Sell <= 40, altrimenti Neutra."
    )
    scores = currency_scores()
    if all(v["score"] is None for v in scores.values()):
        st.info("Nessun dato valute in cache. Esegui `python -m src.scheduler.update_data`.")
    else:
        st.markdown("**Forza assoluta (1-100)**")
        for col, (ccy, v) in zip(st.columns(len(scores)), scores.items()):
            col.metric(ccy, "n/d" if v["score"] is None else v["score"])
        st.dataframe(
            pd.DataFrame([
                {
                    "Valuta": ccy,
                    "Forza": v["score"],
                    "Tasso breve %": None if v["rate"] is None else round(v["rate"], 2),
                    "Inflazione %": None if v["inflation"] is None else round(v["inflation"], 2),
                    "Tasso reale %": None if v["real_rate"] is None else round(v["real_rate"], 2),
                    **{k: None if p is None else round(p) for k, p in zip(("Sub: tasso reale", "Sub: crescita", "Sub: momentum", "Sub: COT", "Sub: VIX"), v["parts"].values())},
                }
                for ccy, v in scores.items()
            ]),
            hide_index=True,
            width="stretch",
        )
        st.markdown("**Coppie: punteggio direzionale (1-100)**")
        rows = []
        for base, quote in PAIRS:
            if scores[base]["score"] is None or scores[quote]["score"] is None:
                continue
            view = pair_view(scores[base]["score"], scores[quote]["score"])
            rows.append({"Coppia": f"{base}/{quote}", "Punteggio": view["score"], "Segnale": view["label"]})
        pair_df = pd.DataFrame(rows)
        st.dataframe(
            pair_df.style.map(lambda x: f"color: {LABEL_COLORS.get(x, 'inherit')}; font-weight: 700", subset=["Segnale"]),
            hide_index=True,
            width="stretch",
        )
