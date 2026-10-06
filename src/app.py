import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st
from streamlit_lightweight_charts import renderLightweightCharts

from src.classify.assess import USED_INPUTS, assess
from src.classify.currency import CURRENCIES, PAIRS, cot_component, momentum_returns, pair_view, strength_score, vix_component
from src.classify.leading import SIGNALS
from src.classify.positioning import percentile_rank
from src.classify.recession import sahm_gap
from src.classify.regime import INFLATION_TARGET, monthly
from src.classify.rrg import quadrant, rrg
from src.classify.stress import MC_YEARS, PROXY, SCENARIOS, monte_carlo, portfolio_returns, scenario, ticker_weights
from src.classify.risk import components as risk_components, label as risk_label, risk_score
from src.classify.score import (
    ASSET_AREA, HORIZON_MONTHS, STRONG, UNIVERSE, WEAK, band_table, complete_months, forward_excess, monthly_prices, pillars, scores,
)
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

AREAS = {"USA": "USA", "Eurozona": "EUR", "Italia": "ITA", "UK": "UK", "Giappone": "JP"}
LEADING_KEYS = sorted({key for signals in SIGNALS.values() for _, key, _ in signals})
INPUT_LABELS = {
    "cli": "CLI OCSE", "growth_yoy": "PIL annuo", "inflation_yoy": "Inflazione", "core_inflation_yoy": "Inflazione core",
    "unemployment_rate": "Disoccupazione", "recession_prob": "Prob. recessione (Chauvet-Piger)",
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
    growth = "accelera (indicatore anticipatore OCSE in salita)" if a["growth_state"] == "up" else "rallenta (indicatore anticipatore OCSE in calo)"
    infl = "alta o in salita" if a["inflation_state"] == "up" else "sotto controllo"
    phase = a["phase"]
    return (
        f"La crescita <b>{growth}</b> e l'inflazione è <b>{infl}</b>: {a['inflation_level']:.1f}% contro un obiettivo del "
        f"{INFLATION_TARGET:.0f}%, {trend_txt} negli ultimi 3 mesi."
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
st.set_page_config(page_title="Soft Investing", page_icon=str(LOGO_DIR / "logo-mark.svg"), layout="wide")
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
       f'<div class="card"><div class="head"><h3>Crescita e inflazione</h3><span class="note">in bande: ±1 = soglia di cambio</span></div>'
       f'{quadrant_html(list(assessments.values()), AREAS)}'
       '<p class="note">Verso l\'alto la crescita accelera, verso destra l\'inflazione è più alta del 2% o sale. '
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
           f"{gser.iloc[-1]:.1f}" + ("" if growth_src == "cli" else "%"), f"{g_change:+.2f} in 3 mesi",
           gauge_html(xg, "rallenta", "accelera", "r-stag", "r-gold"),
           "Direzione del leading indicator OCSE: anticipa il ciclo e cambia poco con le revisioni.")
       + axis_card_html(
           "Inflazione · media totale e core",
           "Alta o in salita" if a["inflation_state"] == "up" else "Sotto controllo",
           "r-stag" if a["inflation_state"] == "up" else "r-gold",
           f"{a['inflation_level']:.1f}%", f"obiettivo {INFLATION_TARGET:.0f}%",
           gauge_html(xi, "sotto controllo", "alta", "r-gold", "r-stag"),
           "Livello rispetto all'obiettivo delle banche centrali, corretto per la direzione degli ultimi 3 mesi.")
       + f'<div class="card"><div class="head"><h3>Probabilità</h3><span class="note">stima dagli assi</span></div>{prob_html(a["probabilities"])}'
         '<p class="note">Il regime cambia solo dopo 2 mesi oltre la soglia: può restare diverso dalla probabilità più alta.</p></div>'
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
    st.caption("Solo informativo: non entra nella classificazione. COT = posizione netta degli speculatori (CFTC), percentile sugli ultimi 5 anni.")
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
    col_ev, col_cot = st.columns([5, 7])
    with col_ev:
        ui(events_html(upcoming_events()))
    with col_cot:
        market = st.selectbox("Mercato COT", list(CONTRACTS), label_visibility="collapsed")
        rows, last_date = [], None
        for group in (DISAGG_GROUPS if market in DISAGG_MARKETS else TFF_GROUPS):
            cot = load_indicator("Mercati", f"cotg_{market}_{group}")
            if cot.empty:
                continue
            rows.append({"Categoria": group, "Netto": cot.iloc[-1], "Variazione": cot.iloc[-1] - cot.iloc[-2] if len(cot) > 1 else 0.0,
                         "Percentile": round(percentile_rank(cot.tail(COT_WEEKS)))})
            last_date = cot.index[-1]
        if rows:
            ui(cot_groups_html(market, rows, f"{last_date:%d/%m}"))
        else:
            st.info("Nessun dato COT in cache.", icon=":material/database:")

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
            "Due assi, aggiornati ogni mese.\n\n"
            "- **Crescita**: direzione a 3 mesi del leading indicator OCSE (CLI). In salita = l'economia accelera rispetto al trend.\n"
            "- **Inflazione**: media di inflazione totale e core contro l'obiettivo del 2%, corretta per la direzione degli ultimi 3 mesi.\n\n"
            "Un asse cambia stato solo se supera la soglia per 2 mesi di fila.\n\n"
            "| | Inflazione sotto controllo | Inflazione alta |\n|---|---|---|\n"
            "| **Crescita in accelerazione** | Goldilocks | Reflazione |\n| **Crescita in rallentamento** | Deflazione | Stagflazione |"
        )
    with col_b, st.container(border=True):
        st.markdown(
            "#### Fase del ciclo\n"
            "- **Espansione**: crescita in accelerazione e PIL annuo sopra la sua media di 10 anni.\n"
            "- **Ripresa**: crescita in accelerazione con PIL ancora sotto il trend, o dopo una recessione.\n"
            "- **Rallentamento**: crescita in decelerazione, senza conferme di recessione.\n"
            "- **Recessione**: solo con conferma dai dati: regola di Sahm sulla disoccupazione "
            "(negli USA confermata dalla probabilità Chauvet-Piger) oppure PIL annuo negativo.\n\n"
            "Gli **indicatori anticipatori** (curva, spread, sentiment) sono mostrati a parte e non cambiano la fase."
        )
    with st.container(border=True):
        st.markdown("#### Affidabilità, dal 2000 (`scripts/evaluate_model.py`, 03/10/2026)")
        st.table(pd.DataFrame([
            {"Area": "USA", "Regime: tempo reale = storico": "90%", "Cambi di regime/anno": "1,2", "Ciclo vs riferimento": "NBER: 100% dei mesi di recessione in Rallentamento o Recessione, Recessione fuori 1%"},
            {"Area": "Eurozona", "Regime: tempo reale = storico": "92%", "Cambi di regime/anno": "0,9", "Ciclo vs riferimento": "OCSE: 90% dentro, 19% fuori"},
            {"Area": "Italia", "Regime: tempo reale = storico": "90%", "Cambi di regime/anno": "1,2", "Ciclo vs riferimento": "OCSE: 84% dentro, 26% fuori"},
            {"Area": "UK", "Regime: tempo reale = storico": "90%", "Cambi di regime/anno": "1,2", "Ciclo vs riferimento": "OCSE: 51% dentro, 45% fuori (debole)"},
            {"Area": "Giappone", "Regime: tempo reale = storico": "95%", "Cambi di regime/anno": "0,6", "Ciclo vs riferimento": "OCSE: 61% dentro, 17% fuori"},
        ]).set_index("Area"))
        st.caption(
            "Tempo reale = con i ritardi di pubblicazione veri (CLI e inflazione 1 mese, PIL 4). Il modello precedente "
            "(trimestrale, a momentum) coincideva col giudizio a posteriori solo nel 5-20% dei mesi. "
            "Limiti: il CLI viene rivisto (direzione stabile nel 79-93% delle revisioni 2018-2026); "
            "nel Regno Unito il ciclo è poco preciso; il regime non prevede i rendimenti futuri."
        )


PAGES = [
    st.Page(page_overview, title="Panoramica", icon=":material/public:", url_path="panoramica", default=True),
    st.Page(page_area, title="Aree", icon=":material/location_on:", url_path="aree"),
    st.Page(page_ranking, title="Classifica", icon=":material/leaderboard:", url_path="classifica"),
    st.Page(page_portfolio, title="Portafoglio", icon=":material/donut_large:", url_path="portafoglio"),
    st.Page(page_markets, title="Mercati", icon=":material/candlestick_chart:", url_path="mercati"),
    st.Page(page_calendar, title="Calendario", icon=":material/calendar_month:", url_path="calendario"),
    st.Page(page_currencies, title="Valute", icon=":material/currency_exchange:", url_path="valute"),
    st.Page(page_method, title="Metodo", icon=":material/menu_book:", url_path="metodo"),
]
nav = st.navigation(PAGES, position="top")
meta = cache.read_meta("updated_at")
if meta:
    utc = pd.Timestamp(meta)
    fresh = pd.Timestamp.now(tz="UTC") - utc < pd.Timedelta(hours=6)
    st.caption(f"{':green' if fresh else ':orange'}[●] Dati aggiornati il {utc.tz_convert('Europe/Rome'):%d/%m alle %H:%M}")
if not assessments:
    st.info("Nessun dato in cache. Esegui `python -m src.scheduler.update_data` per popolare.", icon=":material/database:")
    st.stop()
nav.run()
