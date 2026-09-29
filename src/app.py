import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st
from streamlit_lightweight_charts import renderLightweightCharts

from src.classify.currency import CURRENCIES, PAIRS, cot_component, momentum_returns, pair_view, strength_score, vix_component
from src.classify.gip import gip_view
from src.classify.leading import SIGNALS, leading_risk
from src.classify.regime import direction_position, regime_history, regime_probabilities, to_quarterly
from src.classify.recession import recession_confirmed, sahm_gap
from src.classify.positioning import percentile_rank, positioning_label
from src.data.fetch_cot import CONTRACTS, WEEKS as COT_WEEKS
from src.config.asset_allocation import ALL_WEATHER_WEIGHTS, ASSET_ALLOCATION, combined_portfolio_weights
from src.data import cache
from src.ui.cards import (
    CSS, area_hero_html, changes_strip, chips_html, cot_html, events_html, hero_html, pairs_html,
    portfolio_html, prob_html, regime_streak, risk_meter_html, strength_html, weight_deltas,
)
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

LEADING_LABELS = {
    "yield_curve": "Curva 10Y-breve (pp)",
    "credit_spread": "Spread Baa-10Y (pp)",
    "fin_conditions": "NFCI",
    "cli": "CLI OCSE",
    "esi": "Sentiment ESI",
    "btp_bund": "Spread BTP-Bund (pp)",
    "tankan": "Tankan grandi manif.",
}
# Oltre questa eta' un dato e' in ritardo anomalo (il PIL trimestrale normale arriva a ~230 giorni
# dall'inizio del trimestre prima del dato nuovo): di solito la fonte ha cambiato dataset.
STALE_DAYS = 250

RISK_PROFILE_LABELS ={"Basso": "Conservativo", "Medio": "Bilanciato", "Alto": "Aggressivo"}
ALL_WEATHER = "All Weather"

@st.cache_data(ttl=300)
def load_classifications(area: str) -> list[dict]:
    return cache.read_last_two_classifications(area)


@st.cache_data(ttl=300)
def load_indicator(area: str, indicator: str) -> pd.Series:
    return cache.read_indicator_series(area, indicator)


def area_probabilities(area: str, growth: pd.Series, inflation: pd.Series) -> tuple[dict | None, dict | None]:
    # deadband del modello PIL tarati su trimestri: CPI mensile portato a trimestri come in classify_regime
    g_q, i_q = to_quarterly(growth), to_quarterly(inflation)
    probs = regime_probabilities(g_q, i_q) if len(g_q) > 3 and len(i_q) > 3 else None
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
            "changed": len(history) > 1 and history[0]["regime"] != history[1]["regime"],
        })
        areas[-1]["streak"] = regime_streak(areas[-1]["history"])
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
        f"Regime <b>{regime}</b> ({regime_txt}); ciclo in <b>{phase}</b> ({phase_txt})."
        + (f" Ultimo dato: {data_txt}." if data_txt else "")
    )

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
                             cot_component(None if cot.empty else percentile_rank(cot.tail(COT_WEEKS))), vix_component(ccy, vix_pct))
        res["real_rate"], res["rate"], res["inflation"] = real, rate, infl
        out[ccy] = res
    return out




def upcoming_events() -> list[dict]:
    today = pd.Timestamp.today().normalize()
    events = []
    for name in ["FOMC", "CPI", "Occupazione (NFP)", "PIL"]:
        future = load_indicator("Calendario", name)
        future = future[future.index >= today]
        if not future.empty:
            events.append({"Evento": name, "Data": future.index[0], "giorni": (future.index[0] - today).days})
    return sorted(events, key=lambda e: e["Data"])


def spark(ser: pd.Series, n: int = 24) -> list[float] | None:
    return None if len(ser) < 3 else ser.tail(n).round(2).tolist()


st.set_page_config(page_title="Macro Cycle Tracker", page_icon=":material/monitoring:", layout="wide")

# Stile del redesign (richiesto dall'utente): componenti HTML in src/ui/cards.py, colori e
# font in .streamlit/config.toml. Qui solo entrata delle card e segnali anticipatori attivi.
st.html(
    CSS
    + """
    <style>
    @media (prefers-reduced-motion: no-preference) {
        .mc-card, .ov-card { animation: card-in 0.4s ease-out both; }
    }
    @keyframes card-in {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }
    [class*="st-key-sig-on-"] [data-testid="stMetric"] { border-color: #FBBF24; }
    </style>
    """
)

# Etichette semplici: con bind="query-params" diventano l'URL (?view=Aree), niente icone nel valore.
VIEWS = ["Portafoglio", "Panoramica", "Aree", "Mercato", "Valute"]

histories = {area: h for area in AREA_FLAGS if (h := load_classifications(area))}

with st.container(horizontal=True, vertical_alignment="center", gap="medium"):
    st.markdown("#### :material/monitoring: Macro Cycle", width="content")
    view = st.segmented_control(
        "Sezione", VIEWS, default="Portafoglio", required=True, key="view", bind="query-params",
        label_visibility="collapsed",
    )
    if histories:
        updated = pd.Timestamp(max(h[0]["computed_at"] for h in histories.values()))
        fresh = (pd.Timestamp.now() - updated).days < 2
        st.caption(f"{':green' if fresh else ':orange'}[●] Dati aggiornati {updated:%d/%m %H:%M}", width="content")

if not histories:
    st.info("Nessun dato in cache. Esegui `python -m src.scheduler.update_data` per popolare.")
    st.stop()

if view == "Portafoglio":
    changes = []
    for area, h in histories.items():
        if len(h) > 1 and h[0]["regime"] != h[1]["regime"]:
            changes.append((REGIME_COLORS.get(h[0]["regime"], "#9AA6B8"), f"{area} passa a <b>{h[0]['regime']}</b>"))
        elif len(h) > 1 and h[0]["phase"] != h[1]["phase"]:
            changes.append(("#FBBF24", f"{area}: fase <b>{h[0]['phase']}</b>"))
    if not changes:
        changes.append(("#9AA6B8", "Nessun cambio di regime o fase"))
    events = upcoming_events()
    if events:
        e = events[0]
        changes.append(("#7CB8FF", f"{e['Evento']} fra <b>{e['giorni']}</b> {'giorno' if e['giorni'] == 1 else 'giorni'}"))
    st.html(changes_strip(changes))

    regimes = {area: h[0]["regime"] for area, h in histories.items()}
    with st.container(horizontal=True, vertical_alignment="bottom", gap="large"):
        st.html(hero_html(regimes))
        # All Weather non e' un profilo di rischio: pesi statici, indipendenti da regime e profilo.
        risk_profile = st.segmented_control(
            "Profilo di rischio", ["Basso", "Medio", "Alto", ALL_WEATHER], default="Medio", required=True,
            key="risk", bind="query-params",
        )

    if risk_profile == ALL_WEATHER:
        weights, deltas = ALL_WEATHER_WEIGHTS, None
    else:
        weights = combined_portfolio_weights(regimes, risk_profile)
        prev = {area: (h[1] if len(h) > 1 else h[0])["regime"] for area, h in histories.items()}
        deltas = weight_deltas(weights, combined_portfolio_weights(prev, risk_profile))
    st.html(portfolio_html(weights, deltas, "Portafoglio multi-area", RISK_PROFILE_LABELS.get(risk_profile, "pesi statici")))
    with st.expander("Come sono calcolati questi pesi?", icon=":material/help:"):
        st.markdown(
            "Media equipesata dei portafogli per regime di ogni area. Dentro ogni regime, la quota azionaria "
            "segue il profilo (Basso 30%, Medio 50%, Alto 70%) e il resto va agli asset difensivi. "
            "All Weather usa pesi statici indipendenti dal regime."
        )
    st.caption(
        "Solo informativo, non è consulenza. Backtest USA 2000-2026: vantaggio sui portafogli statici non significativo "
        "(vedi `scripts/backtest_assets.py`)."
    )

elif view == "Panoramica":
    st.html(overview_html(overview_areas()))

elif view == "Aree":
    area = st.segmented_control(
        "Area", list(AREA_FLAGS), default="USA", required=True, key="area", bind="query-params",
        label_visibility="collapsed",
    )
    history = histories.get(area)
    if not history:
        st.info("Nessun dato in cache per quest'area. Esegui `python -m src.scheduler.update_data`.")
        st.stop()

    current = history[0]
    changed = len(history) > 1 and (current["regime"] != history[1]["regime"] or current["phase"] != history[1]["phase"])
    growth = load_indicator(area, "growth_yoy")
    inflation = load_indicator(area, "inflation_yoy")
    unemployment = load_indicator(area, "unemployment_rate")
    enough = len(growth) > 3 and len(inflation) > 3

    if changed:
        st.warning("Regime o fase cambiati dall'ultimo aggiornamento.", icon=":material/change_circle:")
    stale = [
        f"{label} (ultimo {s.index[-1]:%m/%Y})"
        for label, s in (("crescita", growth), ("inflazione", inflation), ("disoccupazione", unemployment))
        if not s.empty and (pd.Timestamp.today() - s.index[-1]).days > STALE_DAYS
    ]
    if stale:
        st.warning("Dati in ritardo anomalo, la fonte potrebbe aver cambiato dataset: " + ", ".join(stale))

    probs, gip = area_probabilities(area, growth, inflation)
    streak = regime_streak(regime_history(growth, inflation, quarters=400)) if enough else 0
    col_hero, col_probs = st.columns([7, 5])
    with col_hero:
        st.html(area_hero_html(area, current["regime"], current["phase"], streak,
                               describe_regime(current["regime"], current["phase"], growth, inflation, unemployment)))
    with col_probs:
        if probs:
            st.html(prob_html(probs, "media PIL + mensile" if gip else "modello PIL"))
            st.caption(
                "Stima non calibrata su frequenze storiche. L'etichetta del regime ha memoria (deadband): "
                "può non coincidere con la probabilità più alta."
            )
        if gip:
            agree = "concorda con il" if gip["regime"] == current["regime"] else "diverge dal"
            st.caption(
                f"Regime mensile alternativo (stile Hedgeye GIP, produzione industriale + CPI): "
                f"**{gip['regime']}**, {agree} regime principale. Politica Fed: {gip['policy']}."
            )

    signal_series = {key: load_indicator(area, key) for _, key, _ in SIGNALS.get(area, [])}
    if any(not s.empty for s in signal_series.values()):
        risk = leading_risk(area, signal_series)
        with st.container(border=True, key=f"leading-card-{area}"):
            st.html(risk_meter_html(risk["level"], risk["score"], risk["total"]))
            with st.container(horizontal=True):
                for label, key, _ in SIGNALS[area]:
                    ser = signal_series[key]
                    with st.container(key=f"sig-{'on' if risk['signals'][label] else 'off'}-{key}"):
                        st.metric(
                            LEADING_LABELS[key], "n/d" if ser.empty else f"{ser.iloc[-1]:.2f}", border=True,
                            chart_data=spark(ser), delta="attivo" if risk["signals"][label] else None,
                            delta_color="off", delta_arrow="off",
                            help=f"Segnale: {label}." + ("" if ser.empty else f" Ultimo dato {ser.index[-1]:%m/%Y}."),
                        )
            st.caption("Bordo giallo = segnale attivo. Con rischio Alto un'Espansione viene declassata a Rallentamento.")
            cli = load_indicator(area, "cli")
            if area == "USA":
                with st.expander("Informativi, non entrano nel punteggio"):
                    claims, permits = load_indicator(area, "claims"), load_indicator(area, "permits")
                    philly, gdpnow = load_indicator(area, "philly_fed"), load_indicator(area, "gdpnow")
                    claims_4w = claims.rolling(4).mean().dropna()
                    extra = [
                        ("CLI OCSE", cli, "{:.1f}", 3, "Anticipa il ciclo di 6-9 mesi. Sotto 100 e in calo = rallentamento."),
                        ("Sussidi (media 4 sett.)", claims_4w / 1000, "{:.0f}k", 4, "Richieste iniziali di sussidi di disoccupazione. In salita = mercato del lavoro che si indebolisce."),
                        ("Permessi di costruzione", permits, "{:.0f}k", 1, "Migliaia, annualizzati. Anticipano l'edilizia di alcuni mesi."),
                        ("Philly Fed manif.", philly, "{:.1f}", 1, "Proxy dell'ISM PMI (non disponibile gratis): sotto 0 = contrazione."),
                        ("GDPNow", gdpnow, "{:.1f}%", 1, "Stima Atlanta Fed del PIL del trimestre in corso, % t/t annualizzata."),
                    ]
                    with st.container(horizontal=True):
                        for label, ser, fmt, lag, tip in extra:
                            delta = f"{ser.iloc[-1] - ser.iloc[-1 - lag]:+.1f}" if len(ser) > lag else None
                            st.metric(label, "n/d" if ser.empty else fmt.format(ser.iloc[-1]), delta, delta_color="off",
                                      help=tip, border=True, chart_data=spark(ser))
                    st.caption("Tarato su NBER con curva, spread e NFCI: questi restano fuori dal punteggio di rischio.")
                gap = sahm_gap(unemployment).dropna()
                prob = load_indicator(area, "recession_prob")
                if not gap.empty and not prob.empty:
                    st.caption(
                        f"Recessione in corso: Regola di Sahm {gap.iloc[-1]:+.2f} pp (soglia 0.5), "
                        f"Chauvet-Piger {prob.iloc[-1]:.1f}%. "
                        + ("CONFERMATA" if recession_confirmed(unemployment, prob) else "Non confermata")
                    )
            elif len(cli) > 3:
                st.caption(f"CLI OCSE {cli.iloc[-1]:.1f} ({cli.index[-1]:%m/%Y}), 3 mesi prima {cli.iloc[-4]:.1f}.")

    if not growth.empty or not inflation.empty or not unemployment.empty:
        # Le serie hanno frequenze diverse (crescita/disoccupazione spesso
        # trimestrali o mensili, inflazione mensile): senza ffill l'unione
        # degli indici lascia buchi (NaN) tra una rilevazione e l'altra, e
        # il grafico non collega i punti oltre un NaN, quindi le linee
        # piu' rade spariscono su schermi stretti (mobile).
        chart_df = pd.DataFrame({
            "Crescita YoY %": growth,
            "Inflazione YoY %": inflation,
            "Disoccupazione %": unemployment,
        }).sort_index().ffill()

        with st.container(border=True, key=f"indicators-section-{area}"):
            with st.container(horizontal=True, vertical_alignment="center"):
                st.markdown("**Crescita, inflazione, disoccupazione**")
                visible = st.pills(
                    "Indicatori nel grafico",
                    list(chart_df.columns),
                    selection_mode="multi",
                    default=list(chart_df.columns),
                    key=f"visible_indicators_{area}",
                    label_visibility="collapsed",
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
                # sopra le linee quando il testo e' lungo.
                st.html(
                    '<div class="mc-row">'
                    + "".join(
                        f'<span class="mc-chip o"><i class="mc-dot" style="background:{INDICATOR_COLORS.get(col, "#94A3B8")}"></i>{col}</span>'
                        for col in visible
                    )
                    + "</div>"
                )
                renderLightweightCharts(
                    [{
                        "chart": {
                            "layout": {
                                "background": {"type": "solid", "color": "transparent"},
                                "textColor": "#9AA6B8",
                                "fontFamily": "IBM Plex Mono, monospace",
                            },
                            "grid": {
                                "vertLines": {"color": "rgba(154,166,184,0.08)"},
                                "horzLines": {"color": "rgba(154,166,184,0.08)"},
                            },
                            "rightPriceScale": {"visible": True, "borderColor": "#1E2738"},
                            "timeScale": {"borderColor": "#1E2738", "rightOffset": 6},
                            "height": 320,
                        },
                        "series": series_config,
                    }],
                    key=f"lwc_{area}",
                )
            else:
                st.info("Seleziona almeno un indicatore per vederlo nel grafico.")

        indicators = [("Crescita YoY %", growth), ("Inflazione YoY %", inflation), ("Disoccupazione %", unemployment)]
        non_empty = [(label, series) for label, series in indicators if not series.empty]
        allocation = ASSET_ALLOCATION.get(current["regime"], [])
        cols = st.columns(len(non_empty) + (1 if allocation else 0))
        for col, (label, series) in zip(cols, non_empty):
            with col, st.container(border=True):
                st.caption(label)
                recent = series.tail(5).sort_index(ascending=False)
                st.dataframe(
                    pd.DataFrame({"Data": recent.index.strftime("%d/%m/%Y"), "Valore": recent.values.round(1)}),
                    hide_index=True,
                    width="stretch",
                )
        if allocation:
            with cols[-1], st.container(border=True):
                st.caption(f"Asset favoriti in {current['regime']}")
                st.html(chips_html(allocation))
                st.caption("Letteratura, non vantaggio dimostrato (backtest USA 1985-2026, vedi scripts/backtest_assets.py).")

elif view == "Mercato":
    st.caption(
        "Solo informativo: non entra nella classificazione di regime e ciclo. "
        "COT = posizione netta degli speculatori (CFTC, aggiornata il venerdì, dato del martedì), "
        "percentile sugli ultimi 5 anni."
    )
    with st.container(horizontal=True):
        for label, key, unit in [
            ("VIX", "vix", ""),
            ("MOVE (vol. Treasury)", "move", ""),
            ("Prob. recessione in corso", "USA:recession_prob", "%"),
            ("Inflazione attesa 5Y", "breakeven_5y", "%"),
            ("Inflazione attesa 5Y5Y", "breakeven_5y5y", "%"),
        ]:
            ser_area, _, ser_key = key.rpartition(":")
            ser = load_indicator(ser_area or "Mercati", ser_key)
            if ser.empty:
                st.metric(label, "n/d", border=True)
            else:
                delta = f"{ser.iloc[-1] - ser.iloc[-2]:+.2f}" if len(ser) > 1 else None
                value = f"{ser.iloc[-1]:.1f}{unit}" if key in ("vix", "move") else f"{ser.iloc[-1]:.2f}{unit}"
                st.metric(label, value, delta, delta_color="off", border=True, chart_data=spark(ser, 60),
                          delta_description="vs rilev. prec.")

    col_ev, col_cot = st.columns([5, 7])
    with col_ev:
        events = upcoming_events()
        if events:
            st.html(events_html(events))
        else:
            st.caption("Nessuna data in cache: esegui l'aggiornamento dati.")
    with col_cot:
        rows, last_date = [], None
        for name in CONTRACTS:
            cot = load_indicator("Mercati", f"cot_{name}")
            if cot.empty:
                continue
            pct = percentile_rank(cot.tail(COT_WEEKS))
            rows.append({"Mercato": name, "Percentile 5 anni": round(pct), "Posizionamento": positioning_label(pct)})
            last_date = max(last_date or cot.index[-1], cot.index[-1])
        if rows:
            st.html(cot_html(rows, f"{last_date:%d/%m}"))
        else:
            st.info("Nessun dato COT in cache. Esegui `python -m src.scheduler.update_data`.")

elif view == "Valute":
    st.caption(
        "Solo informativo, non è consulenza. Pensato per orizzonte 6-12 mesi. Forza 1-100 = 33% crescita PIL, "
        "27% momentum 12 mesi del cambio, 40% VIX (risk-off favorisce JPY/USD, penalizza GBP/EUR). "
        "Tasso reale e COT sono mostrati ma pesano 0% (backtest 1999-2026). Coppia: 50 + (forza base - forza quota)/2."
    )
    scores = currency_scores()
    if all(v["score"] is None for v in scores.values()):
        st.info("Nessun dato valute in cache. Esegui `python -m src.scheduler.update_data`.")
        st.stop()
    pairs = []
    for base, quote in PAIRS:
        if scores[base]["score"] is None or scores[quote]["score"] is None:
            continue
        pv = pair_view(scores[base]["score"], scores[quote]["score"])
        pairs.append({"Coppia": f"{base}/{quote}", "Punteggio": pv["score"], "Segnale": pv["label"]})
    col_s, col_p = st.columns(2)
    with col_s:
        st.html(strength_html({ccy: v["score"] for ccy, v in scores.items()}))
    with col_p:
        st.html(pairs_html(pairs))
    with st.expander("Contesto e composizione del punteggio", icon=":material/table:"):
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
