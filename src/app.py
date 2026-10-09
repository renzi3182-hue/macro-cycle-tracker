import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import altair as alt
import pandas as pd
import streamlit as st
from streamlit_lightweight_charts import renderLightweightCharts

from src.classify.assess import HIGH_FREQ_MAX_DAYS, USED_INPUTS, assess, stale_high_freq
from src.classify.currency import CURRENCIES, PAIRS, cot_component, momentum_returns, pair_view, strength_score, vix_component
from src.classify.leading import SIGNALS
from src.classify.positioning import percentile_rank
from src.classify.recession import sahm_gap
from src.classify.regime import INFLATION_HIGH_LEVEL, monthly
from src.classify.rrg import quadrant, rrg
from src.classify.stress import MC_YEARS, PROXY, SCENARIOS, monte_carlo, portfolio_returns, scenario, ticker_weights
from src.classify.risk import components as risk_components, label as risk_label, risk_score
from src.classify.score import (
    ASSET_AREA, HORIZON_MONTHS, STRONG, UNIVERSE, WEAK, band_table, complete_months, forward_excess, monthly_prices, pillars, scores,
)
from src.config import cot_guide
from src.config.asset_allocation import ALL_WEATHER_WEIGHTS, ASSET_ALLOCATION, apply_trend, combined_portfolio_weights
from src.data import cache
from src.data.fetch_cot import CONTRACTS, DISAGG_GROUPS, DISAGG_MARKETS, TFF_GROUPS, WEEKS as COT_WEEKS
from src.data.sync import sync_cache
from src.ui.cards import (
    area_hero_html, area_tile_html, axis_card_html, bands_html, calendar_html, changes_html, chips_html, cot_groups_html,
    events_html, freshness_html, gauge_html, hero_html, history_html, month_it, pairs_html, portfolio_html,
    prevailing_regime, prob_html, quadrant_html, ranking_html, risk_html, rrg_html, strength_html, stress_html, trend_html, weight_deltas,
)
from src.ui.theme import REGIME_VARS, hex_color, page_css, phase_color, regime_color
from src.ui.tool_pages import page_interest, page_sizing

AREAS = {"USA": "USA", "Eurozona": "EUR", "Italia": "ITA", "UK": "UK", "Giappone": "JP",
         "Canada": "CA", "Cina": "CN", "Australia": "AU", "India": "IN"}
LEADING_KEYS = sorted({key for signals in SIGNALS.values() for _, key, _ in signals})
INPUT_LABELS = {
    "cli": "CLI OCSE", "growth_yoy": "PIL annuo", "inflation_yoy": "Inflazione", "core_inflation_yoy": "Inflazione core",
    "unemployment_rate": "Disoccupazione", "recession_prob": "Prob. recessione (Chauvet-Piger)",
    "industrial_production": "Produzione industriale",
}
LEADING_LABELS = {
    "yield_curve": "Curva 10Y-breve (pp)", "credit_spread": "Spread Baa-10Y (pp)", "fin_conditions": "NFCI",
    "cli": "CLI OCSE", "esi": "Sentiment ESI", "btp_bund": "Spread BTP-Bund (pp)", "tankan": "Tankan grandi manif.",
}
PHASE_MEANING = {
    "Espansione": "crescita sopra il trend e in accelerazione",
    "Rallentamento": "lo slancio della crescita si sta esaurendo",
    "Recessione": "contrazione confermata da disoccupazione o PIL",
    "Ripresa": "crescita sotto il trend ma in miglioramento",
}
CHANGES_MONTHS = 4
TREND_NAMES = {"SPY": "Azionario", "TLT": "Treasury lunga durata", "IEF": "Treasury medio termine", "TIP": "Indicizzate inflazione",
               "GLD": "Oro", "DBC": "Materie prime"}
RISK_PROFILE_LABELS = {"Basso": "Conservativo", "Medio": "Bilanciato", "Alto": "Aggressivo"}
ALL_WEATHER = "All Weather"
IMPACT_LABELS_IT = {"Alto": "High", "Medio": "Medium", "Basso": "Low", "Festivo": "Holiday"}
CCY_COT = {"USD": "Dollaro (DXY)", "EUR": "Euro", "GBP": "Sterlina", "JPY": "Yen"}
CCY_AREA = {"USD": "USA", "EUR": "Eurozona", "GBP": "UK", "JPY": "Giappone"}


@st.cache_resource(ttl=600)
def _sync_cache() -> bool:
    return sync_cache()


@st.cache_data(ttl=300)
def load_indicator(area: str, indicator: str) -> pd.Series:
    return cache.read_indicator_series(area, indicator)


@st.cache_data(ttl=300)
def load_events() -> list[dict]:
    return cache.read_events()


@st.cache_data(ttl=300)
def load_assessment(area: str) -> dict | None:
    """Stesso calcolo dello scheduler (src/classify/assess.py): etichetta, grafici e storico non possono divergere."""
    series = {n: load_indicator(area, n) for n in {*USED_INPUTS, *LEADING_KEYS}}
    a = assess(area, series)
    if a:
        a["label"] = area
    return a


def ui(html: str) -> None:
    st.html(f'<div class="si">{html}</div>')


def last_value(area: str, indicator: str) -> float | None:
    s = load_indicator(area, indicator)
    return None if s.empty else float(s.iloc[-1])


def spark(ser: pd.Series, n: int = 24) -> list[float] | None:
    return None if len(ser) < 3 else ser.tail(n).round(2).tolist()


@st.cache_data(ttl=300)
def load_scores() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Prezzi mensili a mese chiuso e punteggi (src/classify/score.py), solo mesi con una classifica."""
    px = monthly_prices({t: load_indicator(ASSET_AREA, t) for t in UNIVERSE})
    if px.empty:
        return px, px
    px = complete_months(px)
    return px, scores(px).dropna(how="all")


@st.cache_data(ttl=300)
def load_risk() -> pd.DataFrame:
    """Componenti del Risk On/Off (src/classify/risk.py) a mese chiuso, piu' la colonna Punteggio."""
    px, _ = load_scores()
    if px.empty:
        return px
    comp = risk_components(load_indicator("Mercati", "vix"), load_indicator("USA", "credit_spread"), px).loc[:px.index[-1]]
    return comp.assign(Punteggio=risk_score(comp)).dropna()


RISK_VARS = {"Risk Off estremo": "r-stag", "Risk Off": "r-stag", "Neutrale": "r-refl", "Risk On": "r-gold", "Risk On estremo": "r-gold"}


def key_numbers(regimes: dict) -> str:
    """Le 3 cifre in cima alla Panoramica: regime prevalente, Risk On/Off, quota di asset in tendenza positiva."""
    top, n = prevailing_regime(regimes)
    share = n / len(regimes) * 100
    cards = [axis_card_html(
        "Regime prevalente", top if n > 1 else "Quadro misto", REGIME_VARS.get(top, "muted") if n > 1 else "muted",
        f"{share:.0f}%", f"delle aree ({n} su {len(regimes)})", gauge_html((share - 50) / 20, "aree divise", "tutte concordi", "line", "accent", ""),
        "Quante aree condividono lo stesso regime macro.")]
    risk = load_risk()
    if not risk.empty:
        r = risk.iloc[-1]
        state = risk_label(r["Punteggio"])
        cards.append(axis_card_html(
            f"Risk On/Off · fine {month_it(risk.index[-1])}", state, RISK_VARS[state], f'{r["Punteggio"]:.0f}',
            f'/100 · VIX {r["VIX"]:.0f}, credito {r["Credito"]:.0f}, ampiezza {r["Ampiezza"]:.0f}',
            gauge_html((r["Punteggio"] - 50) / 20, "Risk Off", "Risk On", "r-stag", "r-gold", "neutrale"),
            "Anticipa la volatilità, non il rendimento: dal 1999, dopo un mese Risk Off estremo l'S&P 500 si è mosso "
            "in media del 5,8% il mese dopo, dopo Risk On estremo del 2,3%."))
        b = r["Ampiezza"]
        b_state, b_var = ("Tendenza ampia", "r-gold") if b >= 60 else ("Tendenza debole", "r-stag") if b <= 40 else ("Tendenza mista", "r-refl")
        cards.append(axis_card_html(
            "Asset in tendenza positiva", b_state, b_var, f"{b:.0f}%", f"dei {len(UNIVERSE)} ETF della Classifica",
            gauge_html((b - 50) / 20, "pochi", "quasi tutti", "r-stag", "r-gold", ""),
            "Quota sopra la media a 10 mesi, la regola del filtro di tendenza."))
    return '<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(260px,1fr))">' + "".join(cards) + "</div>"


def recent_changes(assessments: dict) -> list[tuple[str, str, str]]:
    """Cambi di regime o fase negli ultimi mesi di dati, dal piu' recente."""
    out = []
    for area, a in assessments.items():
        h = a["history"].iloc[-(CHANGES_MONTHS + 1):]
        for (d0, r0), (d1, r1) in zip(h.iterrows(), list(h.iterrows())[1:]):
            if r1["regime"] != r0["regime"]:
                out.append((d1, regime_color(r1["regime"]), f'{escape(area)}: da {r0["regime"]} a <b>{r1["regime"]}</b>'))
            if r1["phase"] != r0["phase"] and isinstance(r1["phase"], str):
                out.append((d1, phase_color(r1["phase"]), f'{escape(area)}: fase <b>{r1["phase"]}</b>'))
    return [(c, t, month_it(d, True)) for d, c, t in sorted(out, key=lambda x: x[0], reverse=True)]


def describe(a: dict) -> str:
    headline = load_indicator(a["area"], "inflation_yoy")
    h = monthly(headline)
    trend = h.iloc[-1] - h.iloc[-4] if len(h) > 3 else 0.0
    trend_txt = "in salita" if trend > 0.2 else "in calo" if trend < -0.2 else "stabile"
    growth = "accelera (PIL annuo in aumento sul trimestre prima)" if a["growth_state"] == "up" else "rallenta (PIL annuo in calo sul trimestre prima)"
    infl = "alta o in salita" if a["inflation_state"] == "up" else "sotto controllo"
    phase = a["phase"]
    return (
        f"La crescita <b>{growth}</b> e l'inflazione è <b>{infl}</b>: {a['inflation_level']:.1f}% (soglia "
        f"{INFLATION_HIGH_LEVEL:.1f}%), {trend_txt} negli ultimi 3 mesi."
        + (f" Ciclo in <b>{phase}</b>: {PHASE_MEANING[phase]}." if phase else "")
    )


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
        rate, infl = last_value("Valute", f"rate_{ccy}"), last_value(CCY_AREA[ccy], "inflation_yoy")
        real = None if rate is None or infl is None else rate - infl
        res = strength_score(real, last_value(CCY_AREA[ccy], "growth_yoy"), mom.get(ccy),
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


CHART_YEARS = 20


def line_chart(series: dict[str, tuple[pd.Series, str]], key: str, height: int = 300) -> None:
    """series: etichetta -> (serie, token colore). Legenda statica sopra il grafico."""
    ui('<div style="display:flex;flex-wrap:wrap;gap:8px">' + "".join(
        f'<span class="chip"><i class="dot" style="background:var(--{tok})"></i>{escape(label)}</span>' for label, (_, tok) in series.items()
    ) + "</div>")
    renderLightweightCharts([{
        "chart": {
            "layout": {"background": {"type": "solid", "color": "transparent"}, "textColor": hex_color(mode, "muted"),
                       "fontFamily": "DM Mono, monospace"},
            "grid": {"vertLines": {"visible": False}, "horzLines": {"color": hex_color(mode, "line")}},
            "rightPriceScale": {"visible": True, "borderVisible": False},
            "timeScale": {"borderVisible": False, "rightOffset": 6},
            "crosshair": {"mode": 0},
            "height": height,
        },
        "series": [
            {"type": "Line", "data": [{"time": d.strftime("%Y-%m-%d"), "value": round(float(v), 2)} for d, v in s.dropna().loc[pd.Timestamp.today() - pd.DateOffset(years=CHART_YEARS):].items()],
             "options": {"color": hex_color(mode, tok), "lineWidth": 2, "priceLineVisible": False, "lastValueVisible": True}}
            for s, tok in series.values()
        ],
    }], key=key)


LOGO_DIR = Path(__file__).resolve().parent.parent / "assets"
st.set_page_config(page_title="Soft Works", page_icon=str(LOGO_DIR / "logo-mark.svg"), layout="wide")
mode = st.context.theme.type or "dark"
st.logo(str(LOGO_DIR / ("logo-mark.svg" if mode == "dark" else "logo-mark-light.svg")), size="large")
st.html(page_css(mode))

_sync_cache()
assessments = {area: a for area in AREAS if (a := load_assessment(area))}


def page_overview() -> None:
    regimes = {area: a["regime"] for area, a in assessments.items()}
    top, n = prevailing_regime(regimes)
    last_month = max(a["month"] for a in assessments.values())
    title = (f'{n} aree su {len(regimes)} in <span style="color:{regime_color(top)}">{top}</span>' if n > 1
             else "Quadro macro misto")
    in_recession = [a for a, x in assessments.items() if x["phase"] == "Recessione"]
    high_risk = [a for a, x in assessments.items() if x["leading"] and x["leading"]["level"] == "Alto"]
    weak = [a for a, x in assessments.items() if x["confidence"] == "Bassa"]
    lead = [
        f"In recessione: <b>{', '.join(in_recession)}</b>." if in_recession else "Nessuna area in recessione.",
        f"Anticipatori in allarme: <b>{', '.join(high_risk)}</b>." if high_risk else "Indicatori anticipatori senza allarmi.",
        f"Lettura meno solida, vicina a un cambio: {', '.join(weak)}." if weak else "",
    ]
    ui(hero_html(f"Panoramica · dati fino a {month_it(last_month)}", title, " ".join(x for x in lead if x)))
    ui(key_numbers(regimes))
    st.space("small")
    ui('<div class="grid">' + "".join(area_tile_html(a, f"aree?area={area}") for area, a in assessments.items()) + "</div>")
    st.space("small")
    ui('<div class="two">'
       f'<div class="card"><div class="head"><h3>Crescita e inflazione</h3><span class="note">0 = soglia di cambio</span></div>'
       f'{quadrant_html(list(assessments.values()), AREAS)}'
       '<p class="note">Verso l\'alto la crescita accelera, verso destra l\'inflazione è sopra il 2,5% o sale. '
       'Un\'area vicina a un asse può cambiare regime.</p></div>'
       f'{changes_html(recent_changes(assessments))}</div>')
    st.caption("Solo informativo, non è consulenza finanziaria. Metodo e affidabilità nella sezione **Metodo**.")

def page_area() -> None:
    area = st.segmented_control("Area", list(AREAS), default="USA", required=True, key="area",
                                bind="query-params", label_visibility="collapsed")
    a = assessments.get(area)
    if not a:
        st.info("Nessun dato in cache per quest'area.", icon=":material/database:")
        st.stop()
    if a["stale"]:
        st.warning("Dati in ritardo anomalo: " + ", ".join(INPUT_LABELS.get(n, n) for n in a["stale"])
                   + ". La fonte potrebbe aver cambiato dataset: la lettura è meno affidabile.", icon=":material/schedule:")
    ui(area_hero_html(a, describe(a)))

    xg, xi = a["positions"]
    growth_src = a["growth_source"]
    gser = load_indicator(area, growth_src)
    gm = monthly(gser)
    g_change = gm.iloc[-1] - gm.iloc[-4] if len(gm) > 3 else 0.0
    ui('<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(280px,1fr))">'
       + axis_card_html(
           f"Crescita · {'CLI OCSE' if growth_src == 'cli' else 'PIL annuo'}",
           "In accelerazione" if a["growth_state"] == "up" else "In rallentamento",
           "r-gold" if a["growth_state"] == "up" else "r-stag",
           f"{gser.iloc[-1]:.1f}" + ("" if growth_src == "cli" else "%"),
           f"{g_change:+.2f} " + ("in 3 mesi" if growth_src == "cli" else "sul trimestre prima"),
           gauge_html(xg, "rallenta", "accelera", "r-stag", "r-gold"),
           "PIL annuo contro il trimestre prima, come Quantaste: conta la velocità della crescita, non il livello."
           if growth_src != "cli" else "Direzione del leading indicator OCSE (PIL non disponibile).")
       + axis_card_html(
           "Inflazione · media totale e core",
           "Alta o in salita" if a["inflation_state"] == "up" else "Sotto controllo",
           "r-stag" if a["inflation_state"] == "up" else "r-gold",
           f"{a['inflation_level']:.1f}%", f"soglia {INFLATION_HIGH_LEVEL:.1f}%",
           gauge_html(xi, "sotto controllo", "alta", "r-gold", "r-stag"),
           "Alta se la media degli ultimi 3 mesi supera la soglia oppure se sale rispetto ai 3 mesi prima.")
       + f'<div class="card"><div class="head"><h3>Probabilità · trimestre in corso</h3><span class="note">calibrata dal 2000</span></div>'
         f'{prob_html(a["inflation_prob"])}<p class="note">Probabilità che l\'inflazione del trimestre in corso risulti alta '
         f'o in salita a dati completi. La crescita del trimestre non si prevede (resta vicina al 50%): crescita incerta.</p></div>'
       + "</div>")
    st.space("small")
    ui(history_html(a["history"]))

    risk = a["leading"]
    if risk:
        with st.container(border=True, key=f"leading-{area}"):
            ui(risk_html(risk["level"], risk["score"], risk["total"]))
            with st.container(horizontal=True):
                for label, key, _ in SIGNALS[area]:
                    ser = load_indicator(area, key)
                    st.metric(LEADING_LABELS[key], "n/d" if ser.empty else f"{ser.iloc[-1]:.2f}", border=True,
                              chart_data=spark(ser), delta="attivo" if risk["signals"][label] else None,
                              delta_color="inverse" if risk["signals"][label] else "off", delta_arrow="off",
                              help=f"Segnale: {label}." + ("" if ser.empty else f" Ultimo dato {ser.index[-1]:%m/%Y}."))
            st.caption("Segnali di stress su curva, credito e sentiment. Mostrati a parte: non cambiano regime né fase.")
            if area == "USA":
                unemployment, prob = load_indicator(area, "unemployment_rate"), load_indicator(area, "recession_prob")
                gap = sahm_gap(unemployment).dropna()
                if not gap.empty and not prob.empty:
                    st.caption(f"Recessione in corso: regola di Sahm {gap.iloc[-1]:+.2f} pp (soglia 0,5), Chauvet-Piger "
                               f"{prob.iloc[-1]:.1f}%: " + ("**confermata**." if a["recession"] else "non confermata."))
                with st.expander("Altri indicatori USA (informativi)", icon=":material/monitoring:"):
                    claims = load_indicator(area, "claims").rolling(4).mean().dropna()
                    extra = [
                        ("Sussidi (media 4 sett.)", claims / 1000, "{:.0f}k", 4, "Richieste iniziali di sussidi. In salita = lavoro più debole."),
                        ("Permessi di costruzione", load_indicator(area, "permits"), "{:.0f}k", 1, "Migliaia, annualizzati. Anticipano l'edilizia."),
                        ("Philly Fed manif.", load_indicator(area, "philly_fed"), "{:.1f}", 1, "Proxy dell'ISM: sotto 0 = contrazione."),
                        ("GDPNow", load_indicator(area, "gdpnow"), "{:.1f}%", 1, "Stima Atlanta Fed del PIL del trimestre, % t/t annualizzata."),
                    ]
                    with st.container(horizontal=True):
                        for label, ser, fmt, lag, tip in extra:
                            delta = f"{ser.iloc[-1] - ser.iloc[-1 - lag]:+.1f}" if len(ser) > lag else None
                            st.metric(label, "n/d" if ser.empty else fmt.format(ser.iloc[-1]), delta, delta_color="off",
                                      help=tip, border=True, chart_data=spark(ser))

    growth, inflation, unemployment = (load_indicator(area, n) for n in ("growth_yoy", "inflation_yoy", "unemployment_rate"))
    with st.container(border=True, key=f"chart-{area}"):
        st.markdown("**Crescita, inflazione, disoccupazione**")
        line_chart({k: v for k, v in {
            "PIL annuo %": (growth, "r-gold"), "Inflazione annua %": (inflation, "r-stag"), "Disoccupazione %": (unemployment, "r-defl"),
        }.items() if not v[0].empty}, key=f"lwc-{area}")

    col_data, col_assets = st.columns([1, 1])
    with col_data:
        ui(freshness_html([(INPUT_LABELS[n], d, n in a["stale"]) for n, d in a["as_of"].items()]))
    with col_assets:
        allocation = ASSET_ALLOCATION.get(a["regime"], [])
        ui(f'<div class="card"><h3>Asset tipici in {escape(a["regime"])}</h3>{chips_html(allocation)}'
           '<p class="note">Tabella statica di letteratura, non un vantaggio dimostrato: vedi la sezione Metodo.</p></div>')

def page_portfolio() -> None:
    regimes = {area: a["regime"] for area, a in assessments.items()}
    with st.container(horizontal=True, vertical_alignment="bottom", gap="large"):
        top, n = prevailing_regime(regimes)
        ui(hero_html("Portafoglio multi-area", f'Regime prevalente: <span style="color:{regime_color(top)}">{top}</span>',
                     f"{n} aree su {len(regimes)}. Media equipesata dei portafogli per regime di ogni area."))
        risk_profile = st.segmented_control("Profilo di rischio", ["Basso", "Medio", "Alto", ALL_WEATHER], default="Medio",
                                            required=True, key="risk", bind="query-params")
    if risk_profile == ALL_WEATHER:  # pesi statici, indipendenti da regime e profilo
        weights, deltas = ALL_WEATHER_WEIGHTS, None
    else:
        weights = combined_portfolio_weights(regimes, risk_profile)
        prev = {}
        for area, a in assessments.items():
            changed = a["history"]["regime"][a["history"]["regime"] != a["regime"]]
            prev[area] = changed.iloc[-1] if not changed.empty else a["regime"]
        deltas = weight_deltas(weights, combined_portfolio_weights(prev, risk_profile))
    delta_note = "vs regimi precedenti"
    px, _ = load_scores()
    trend = pillars(px)["Tendenza"].iloc[-1].dropna() if len(px) else pd.Series(dtype=float)
    use_trend = st.toggle("Filtro di tendenza: in cash gli asset sotto la media a 10 mesi", key="trend", disabled=trend.empty)
    if use_trend:
        filtered = apply_trend(weights, (trend > 0).to_dict())
        weights, deltas, delta_note = filtered, weight_deltas(filtered, weights), "vs senza filtro"
    col_p, col_t = st.columns([8, 4])
    with col_p:
        ui(portfolio_html(weights, deltas, "Allocazione", RISK_PROFILE_LABELS.get(risk_profile, "pesi statici"), delta_note))
    with col_t:
        if trend.empty:
            st.info("Nessun prezzo degli ETF in cache per il filtro di tendenza.", icon=":material/database:")
        else:
            ui(trend_html([(name, t, trend[t] * 100) for t, name in TREND_NAMES.items() if t in trend], px.index[-1]))
    if not px.empty:
        stress_section(weights, px)
    st.caption("Dentro ogni regime la quota azionaria segue il profilo (Basso 30%, Medio 50%, Alto 70%). "
               "Solo informativo, non è consulenza: il backtest non mostra un vantaggio sui portafogli statici (sezione Metodo).")

STRESS_ASSETS = sorted({*PROXY, *ALL_WEATHER_WEIGHTS, *(a for v in ASSET_ALLOCATION.values() for a in v)})


def stress_section(weights: dict, px: pd.DataFrame) -> None:
    """Posizioni modificabili (partono dall'allocazione mostrata) e loro stress test (src/classify/stress.py)."""
    col_in, col_out = st.columns([5, 7])
    with col_in:
        st.markdown("**Le tue posizioni**")
        edited = st.data_editor(
            pd.DataFrame({"Asset": list(weights), "Peso %": [round(w, 1) for w in weights.values()]}),
            num_rows="dynamic", hide_index=True, width="stretch",
            column_config={"Asset": st.column_config.SelectboxColumn(options=STRESS_ASSETS, required=True),
                           "Peso %": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, step=1.0, format="%.1f")})
        st.caption("Parte dall'allocazione qui sopra: cambia pesi o aggiungi righe. I pesi si riportano a 100.")
    edited = edited.dropna()
    tw, skipped = ticker_weights(edited.groupby("Asset")["Peso %"].sum().to_dict())
    with col_out:
        if not tw:
            st.info("Inserisci almeno una posizione con un ETF di riferimento.", icon=":material/edit:")
            return
        r, spy = portfolio_returns(tw, px), px["SPY"].pct_change(fill_method=None)
        rows = [(name, f"{month_it(pd.Timestamp(a), True)} – {month_it(pd.Timestamp(b), True)}", scenario(r, a, b), scenario(spy, a, b))
                for name, (a, b) in SCENARIOS.items()]
        ui(stress_html(rows, monte_carlo(r), MC_YEARS, skipped))


def page_ranking() -> None:
    px, s = load_scores()
    if s.empty:
        st.info("Nessun prezzo degli asset in cache.", icon=":material/database:")
        st.stop()
    month, now = s.index[-1], s.iloc[-1].dropna().sort_values(ascending=False)
    prev = s.iloc[-2] if len(s) > 1 else pd.Series(dtype=float)
    p = {k: v.loc[month] for k, v in pillars(px).items()}
    strong = [UNIVERSE[t][0] for t in now.index if now[t] > STRONG]
    ui(hero_html(f"Classifica asset · fine {month_it(month)}", "In testa: " + ", ".join(UNIVERSE[t][0] for t in now.index[:3]),
                 f"Punteggio 1-100 = posizione fra {len(now)} ETF per tendenza (prezzo contro la media a 10 mesi) e momentum "
                 f"(rendimento 12 mesi escluso l'ultimo). Sopra {STRONG}: <b>{', '.join(strong) or 'nessuno'}</b>."))
    groups = ["Tutti", *dict.fromkeys(g for _, g in UNIVERSE.values())]
    group = st.segmented_control("Gruppo", groups, default="Tutti", required=True, key="group", label_visibility="collapsed")
    rows = [{"ticker": t, "nome": UNIVERSE[t][0], "gruppo": UNIVERSE[t][1], "punteggio": sc,
             "delta": sc - prev[t] if pd.notna(prev.get(t)) else None, **{k: v[t] for k, v in p.items()}, "storico": s[t]}
            for t, sc in now.items() if group == "Tutti" or UNIVERSE[t][1] == group]
    col_r, col_e = st.columns([8, 4])
    with col_r:
        ui(ranking_html(rows, month))
    with col_e:
        ui(bands_html(band_table(s, forward_excess(px, s)), HORIZON_MONTHS, s.index[0]))
        ratio, mom = (x.iloc[-1].dropna() for x in rrg(px))
        sectors = [{"ticker": t, "nome": UNIVERSE[t][0], "ratio": ratio[t], "momentum": mom[t], "quadrante": quadrant(ratio[t], mom[t])}
                   for t in ratio.index.intersection(mom.index)]
        if sectors:
            ui(rrg_html(sectors, px.index[-1]))
    st.caption(f"Solo informativo, non è consulenza. Si aggiorna a fine mese. Verde sopra {STRONG}, rosso fino a {WEAK}. "
               "Backtest 2002-2026 senza costi (scripts/evaluate_score.py, 06/10/2026): i 5 migliori ribilanciati ogni mese "
               "12,0% l'anno con drawdown massimo −18%, S&P 500 11,2% e −51%. Il vantaggio è piccolo e sta più nel ridurre le perdite che nel rendimento.")


def page_markets() -> None:
    st.caption("Solo informativo: non entra nella classificazione.")
    with st.container(horizontal=True):
        for label, (ser_area, key), fmt in [
            ("VIX", ("Mercati", "vix"), "{:.1f}"), ("MOVE (vol. Treasury)", ("Mercati", "move"), "{:.1f}"),
            ("Prob. recessione USA", ("USA", "recession_prob"), "{:.2f}%"),
            ("Inflazione attesa 5Y", ("Mercati", "breakeven_5y"), "{:.2f}%"), ("Inflazione attesa 5Y5Y", ("Mercati", "breakeven_5y5y"), "{:.2f}%"),
        ]:
            ser = load_indicator(ser_area, key)
            if ser.empty:
                st.metric(label, "n/d", border=True)
            else:
                delta = f"{ser.iloc[-1] - ser.iloc[-2]:+.2f}" if len(ser) > 1 else None
                st.metric(label, fmt.format(ser.iloc[-1]), delta, delta_color="off", border=True, chart_data=spark(ser, 60),
                          delta_description="vs rilev. prec.")
    ui(events_html(upcoming_events()))
    st.caption("Posizionamento dei grandi operatori sui future: pagina **COT**.")

def cot_history_chart(s: pd.Series, lo: float, hi: float) -> alt.LayerChart:
    """Netto degli speculatori negli ultimi 5 anni con le soglie del 10o e 90o percentile."""
    d = s.tail(COT_WEEKS).rename("netto").rename_axis("data").reset_index()
    line = alt.Chart(d).mark_area(
        line={"color": hex_color(mode, "accent"), "strokeWidth": 2}, opacity=0.18, color=hex_color(mode, "accent")).encode(
        x=alt.X("data:T", title=None, axis=alt.Axis(format="%Y", tickCount="year")), y=alt.Y("netto:Q", title="Netto speculatori (% open interest)"),
        tooltip=[alt.Tooltip("data:T", title="Settimana", format="%d/%m/%Y"), alt.Tooltip("netto:Q", title="Netto %", format="+.1f")])
    bands = alt.Chart(pd.DataFrame({"y": [lo, hi], "q": ["10° percentile", "90° percentile"]})).mark_rule(strokeDash=[5, 4]).encode(
        y="y:Q", color=alt.Color("q:N", title=None, scale=alt.Scale(range=[hex_color(mode, "r-defl"), hex_color(mode, "r-stag")])))
    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=hex_color(mode, "muted"), opacity=0.5).encode(y="y:Q")
    return (line + bands + zero).properties(height=300, background="transparent").configure_view(strokeWidth=0).configure_axis(
        labelColor=hex_color(mode, "muted"), titleColor=hex_color(mode, "muted"), gridColor=hex_color(mode, "line"),
        domainColor=hex_color(mode, "line"), labelFont="DM Mono").configure_legend(labelColor=hex_color(mode, "muted"), orient="top")


def page_cot() -> None:
    series = {m: load_indicator("Mercati", f"cot_{m}") for m in CONTRACTS}
    series = {m: s for m, s in series.items() if len(s) > 1}
    if not series:
        st.info("Nessun dato COT in cache.", icon=":material/database:")
        st.stop()
    last = max(s.index[-1] for s in series.values())
    ui(hero_html(f"COT report · CFTC, dato del {last:%d/%m/%Y}", "Chi è posizionato dove",
                 "Ogni venerdì la CFTC pubblica le posizioni sui future al martedì precedente. Quando gli speculatori "
                 "sono tutti dalla stessa parte il mercato è <b>affollato</b>: basta poco per una ricopertura violenta."))

    stats = {}
    for m, s in series.items():
        pct = percentile_rank(s.tail(COT_WEEKS))
        stats[m] = (s.iloc[-1], s.iloc[-1] - s.iloc[-2], pct, *cot_guide.crowding(pct))
    with st.container(horizontal=True):
        for m, (net, chg, pct, label, color) in stats.items():
            st.metric(m, f"{net:+.1f}%", label, delta_color=color, delta_arrow="off", border=True, width=232,
                      delta_description=f"{pct:.0f}° percentile", chart_data=spark(series[m], 52), chart_type="area",
                      help=f"Speculatori long meno short in % dell'open interest. Variazione settimana: {chg:+.1f} punti.")

    market = st.pills("Mercato", list(series), default=next(iter(series)), key="cot_market", bind="query-params",
                      selection_mode="single", required=True, label_visibility="collapsed")
    net, chg, pct, label, color = stats[market]
    what, reading = cot_guide.MARKET_INFO[market]
    s = series[market]
    col_l, col_r = st.columns([7, 5])
    with col_l, st.container(border=True):
        with st.container(horizontal=True, vertical_alignment="center"):
            st.markdown(f"### {market}")
            st.badge(label, color=color, icon=":material/groups:")
        st.caption(what)
        window = s.tail(COT_WEEKS)
        st.altair_chart(cot_history_chart(s, window.quantile(0.1), window.quantile(0.9)),
                        alt=f"Posizione netta degli speculatori su {market} negli ultimi 5 anni")
        st.caption("Sopra la linea rossa: più long del 90% delle settimane degli ultimi 5 anni. Sotto la blu: più short del 90%.")
    with col_r:
        with st.container(border=True):
            st.markdown("**Cosa implica oggi**")
            st.markdown(cot_guide.implication(market, pct, chg))
            st.markdown(f"**Come si legge su questo mercato.** {reading}")
        with st.container(horizontal=True):
            st.metric("Netto speculatori", f"{net:+.1f}%", f"{chg:+.1f} pt", delta_color="off", border=True,
                      help="Long meno short dei non-commercial, in % dell'open interest.")
            st.metric("Percentile 5 anni", f"{pct:.0f}°", border=True,
                      help="Quota di settimane degli ultimi 5 anni con un netto più basso di oggi.")

    groups = DISAGG_GROUPS if market in DISAGG_MARKETS else TFF_GROUPS
    rows, gdate = [], None
    for group in groups:
        g = load_indicator("Mercati", f"cotg_{market}_{group}")
        if len(g) < 2:
            continue
        rows.append({"Categoria": group, "Netto": g.iloc[-1], "Variazione": g.iloc[-1] - g.iloc[-2],
                     "Percentile": round(percentile_rank(g.tail(COT_WEEKS)))})
        gdate = g.index[-1]
    col_g, col_e = st.columns([7, 5])
    with col_g:
        if rows:
            ui(cot_groups_html(market, rows, f"{gdate:%d/%m}"))
    with col_e, st.container(border=True):
        st.markdown(f"**Le categorie nel report {'Disaggregated' if market in DISAGG_MARKETS else 'Traders in Financial Futures'}**")
        for group in groups:
            who, how = cot_guide.GROUP_INFO[group]
            st.markdown(f"**{group}** · {who} {how}")

    with st.expander("Come usare il COT", icon=":material/school:"):
        st.markdown(
            "- **È contesto, non timing.** Un mercato può restare affollato per mesi mentre il trend continua: "
            "l'estremo dice dove sta il rischio, non quando arriva.\n"
            "- **Guarda chi muove.** Hedge fund e managed money seguono il trend e sono i primi a chiudere; asset manager e "
            "produttori si muovono piano e per motivi strutturali (coperture, mandati).\n"
            "- **Cerca le divergenze.** Prezzo ai massimi con speculatori che riducono il long = rally meno sostenuto.\n"
            "- **Ritardo di 3 giorni.** Il dato è del martedì e esce il venerdì: nelle settimane volatili è già vecchio.\n"
            "- **Verificato qui.** Nel backtest delle valute (1999-2026) il COT non ha migliorato la previsione a 6-12 mesi."
        )
    st.caption("Fonte: CFTC (Legacy per gli speculatori, TFF e Disaggregated per le categorie). Solo informativo, non è consulenza.")


def page_calendar() -> None:
    events = load_events()
    if not events:
        st.info("Nessun evento in cache.", icon=":material/event_busy:")
        st.stop()
    with st.container(horizontal=True, vertical_alignment="center"):
        currencies = sorted({e["country"] for e in events})
        picked_ccy = st.pills("Valuta", currencies, selection_mode="multi", key="cal_ccy", label_visibility="collapsed",
                              default=[c for c in ("USD", "EUR", "GBP", "JPY") if c in currencies])
        picked_impact = st.pills("Impatto", list(IMPACT_LABELS_IT), selection_mode="multi", default=["Alto", "Medio"],
                                 key="cal_impact", label_visibility="collapsed")
    wanted = {IMPACT_LABELS_IT[i] for i in picked_impact}
    ui(calendar_html([e for e in events if e["country"] in (picked_ccy or []) and e["impact"] in wanted]))
    st.caption("Solo informativo. Fonte: feed pubblico non ufficiale del calendario Forex Factory, settimana in corso, orari di Roma. "
               "Atteso = consenso, prec. = dato precedente.")

def page_currencies() -> None:
    scores = currency_scores()
    if all(v["score"] is None for v in scores.values()):
        st.info("Nessun dato valute in cache.", icon=":material/database:")
        st.stop()
    pairs = []
    for base, quote in PAIRS:
        if scores[base]["score"] is not None and scores[quote]["score"] is not None:
            pv = pair_view(scores[base]["score"], scores[quote]["score"])
            pairs.append({"Coppia": f"{base}/{quote}", "Punteggio": pv["score"], "Segnale": pv["label"]})
    col_s, col_p = st.columns(2)
    with col_s:
        ui(strength_html({ccy: v["score"] for ccy, v in scores.items()}))
    with col_p:
        ui(pairs_html(pairs))
    st.caption("Solo informativo, orizzonte 6-12 mesi. Forza 1-100 = crescita PIL, momentum 12 mesi del cambio e VIX "
               "(risk-off favorisce JPY/USD). Tasso reale e COT mostrati ma con peso 0% (backtest 1999-2026).")
    with st.expander("Composizione del punteggio", icon=":material/table:"):
        st.dataframe(pd.DataFrame([
            {"Valuta": ccy, "Forza": v["score"],
             "Tasso breve %": None if v["rate"] is None else round(v["rate"], 2),
             "Inflazione %": None if v["inflation"] is None else round(v["inflation"], 2),
             "Tasso reale %": None if v["real_rate"] is None else round(v["real_rate"], 2),
             **{k: None if p is None else round(p) for k, p in zip(("Tasso reale", "Crescita", "Momentum", "COT", "VIX"), v["parts"].values())}}
            for ccy, v in scores.items()
        ]), hide_index=True)

def page_method() -> None:
    ui(hero_html("Metodo", "Come leggere i regimi", "Regole semplici e pubbliche, verificate sui dati come erano disponibili al momento."))
    col_a, col_b = st.columns(2)
    with col_a, st.container(border=True):
        st.markdown(
            "#### Regime macro\n"
            "Due assi, con la regola di Marco Casario usata da Quantaste.\n\n"
            "- **Crescita**: PIL annuo contro il trimestre prima. In aumento = l'economia accelera, in calo = rallenta, "
            "anche se cresce ancora.\n"
            "- **Inflazione**: alta se la media di totale e core degli ultimi 3 mesi supera il 2,5% "
            "oppure se l'inflazione sale rispetto ai 3 mesi prima.\n\n"
            "Il PIL cambia una volta a trimestre: il regime può cambiare 3-4 volte l'anno.\n\n"
            "**Probabilità**: quanto è probabile che l'inflazione del trimestre in corso risulti alta, a dati completi (la crescita è mostrata come incerta). Calibrate sul "
            "passato (9 aree dal 2000): una probabilità del 70% si è avverata circa 7 volte su 10. L'inflazione si prevede "
            "bene (88% dei mesi dal 2015), l'accelerazione del PIL del trimestre no (56%, quasi una moneta): neanche "
            "la produzione industriale mensile la anticipa davvero.\n\n"
            "| | Inflazione sotto controllo | Inflazione alta |\n|---|---|---|\n"
            "| **Crescita in accelerazione** | Goldilocks | Reflazione |\n| **Crescita in rallentamento** | Deflazione | Stagflazione |"
        )
    with col_b, st.container(border=True):
        st.markdown(
            "#### Fase del ciclo\n"
            "Momentum = direzione a 3 mesi del leading indicator OCSE (CLI), con conferma di 2 mesi.\n\n"
            "- **Espansione**: CLI in salita e PIL annuo sopra la sua media di 10 anni.\n"
            "- **Ripresa**: CLI in salita con PIL ancora sotto il trend, o dopo una recessione.\n"
            "- **Rallentamento**: CLI in calo, senza conferme di recessione.\n"
            "- **Recessione**: solo con conferma dai dati: regola di Sahm sulla disoccupazione "
            "(negli USA confermata dalla probabilità Chauvet-Piger) oppure PIL annuo negativo.\n\n"
            "Gli **indicatori anticipatori** (curva, spread, sentiment) sono mostrati a parte e non cambiano la fase."
        )
    with st.container(border=True):
        st.markdown("#### Affidabilità, dal 2000 (`scripts/evaluate_model.py`, 09/10/2026)")
        st.table(pd.DataFrame([
            {"Area": "USA", "Regime: tempo reale = storico": "48%", "Cambi di regime/anno": "3,0", "Ciclo vs riferimento": "NBER: 100% dei mesi di recessione in Rallentamento o Recessione, Recessione fuori 1%"},
            {"Area": "Eurozona", "Regime: tempo reale = storico": "57%", "Cambi di regime/anno": "3,0", "Ciclo vs riferimento": "OCSE: 86% dentro, 19% fuori"},
            {"Area": "Italia", "Regime: tempo reale = storico": "52%", "Cambi di regime/anno": "2,9", "Ciclo vs riferimento": "OCSE: 80% dentro, 28% fuori"},
            {"Area": "UK", "Regime: tempo reale = storico": "58%", "Cambi di regime/anno": "2,3", "Ciclo vs riferimento": "OCSE: 51% dentro, 45% fuori (debole)"},
            {"Area": "Giappone", "Regime: tempo reale = storico": "46%", "Cambi di regime/anno": "3,4", "Ciclo vs riferimento": "OCSE: 66% dentro, 16% fuori"},
            {"Area": "Canada", "Regime: tempo reale = storico": "45%", "Cambi di regime/anno": "3,5", "Ciclo vs riferimento": "OCSE: 74% dentro, 38% fuori"},
            {"Area": "Cina", "Regime: tempo reale = storico": "44%", "Cambi di regime/anno": "3,6", "Ciclo vs riferimento": "OCSE: 72% dentro, 30% fuori (dati meno affidabili)"},
            {"Area": "Australia", "Regime: tempo reale = storico": "49%", "Cambi di regime/anno": "2,9", "Ciclo vs riferimento": "OCSE: 48% dentro, 66% fuori (debole)"},
            {"Area": "India", "Regime: tempo reale = storico": "52%", "Cambi di regime/anno": "2,1", "Ciclo vs riferimento": "OCSE: 92% dentro, 25% fuori"},
        ]).set_index("Area"))
        st.caption(
            "Confronto con Quantaste: 14 letture note su 17 riprodotte (dashboard 10/2026, libro di Casario Q1 2024, "
            "trimestri 2015-2022 dal blog). Le 3 di Canada, Cina e Australia non sono servite a scegliere la regola: "
            "ne coincide 1 (Australia). Il modello precedente (direzione del CLI) ne riproduceva 5 su 14. "
            "Tempo reale = con i ritardi di pubblicazione veri (inflazione 1 mese, PIL 4): il PIL del trimestre si "
            "conosce tardi e viene rivisto, per questo la lettura del momento coincide con quella a posteriori circa "
            "1 mese su 2. Nel Regno Unito il ciclo è poco preciso; il regime non prevede i rendimenti futuri."
        )


PAGES = {
    "Macro": [
        st.Page(page_overview, title="Panoramica", icon=":material/public:", url_path="panoramica", default=True),
        st.Page(page_area, title="Aree", icon=":material/location_on:", url_path="aree"),
        st.Page(page_method, title="Metodo", icon=":material/menu_book:", url_path="metodo"),
    ],
    "Mercati": [
        st.Page(page_ranking, title="Classifica", icon=":material/leaderboard:", url_path="classifica"),
        st.Page(page_markets, title="Mercati", icon=":material/candlestick_chart:", url_path="mercati"),
        st.Page(page_cot, title="COT report", icon=":material/groups:", url_path="cot"),
        st.Page(page_currencies, title="Valute", icon=":material/currency_exchange:", url_path="valute"),
        st.Page(page_calendar, title="Calendario", icon=":material/calendar_month:", url_path="calendario"),
    ],
    "Strumenti": [
        st.Page(page_portfolio, title="Portafoglio", icon=":material/donut_large:", url_path="portafoglio"),
        st.Page(lambda: page_sizing(mode), title="Size Monte Carlo", icon=":material/casino:", url_path="size"),
        st.Page(lambda: page_interest(mode), title="Interesse composto", icon=":material/savings:", url_path="interesse"),
    ],
}
nav = st.navigation(PAGES, position="top")
meta = cache.read_meta("updated_at")
if meta:
    utc = pd.Timestamp(meta)
    fresh = pd.Timestamp.now(tz="UTC") - utc < pd.Timedelta(hours=6)
    st.caption(f"{':green' if fresh else ':orange'}[●] Dati aggiornati il {utc.tz_convert('Europe/Rome'):%d/%m alle %H:%M}")
late = stale_high_freq({k: (s.index[-1] if not (s := load_indicator(*k)).empty else None) for k in HIGH_FREQ_MAX_DAYS})
if late:
    st.warning("Serie giornaliere/settimanali FRED ferme: " + ", ".join(f"{k[1]} ({k[0]})" for k in late)
               + ". Possibile problema di aggiornamento.", icon=":material/schedule:")
if not assessments:
    st.info("Nessun dato in cache. Esegui `python -m src.scheduler.update_data` per popolare.", icon=":material/database:")
    st.stop()
nav.run()
