import json
import sys
from collections import Counter
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st
from streamlit_lightweight_charts import renderLightweightCharts

from src.classify import intermarket as im
from src.classify.assess import HIGH_FREQ_MAX_DAYS, USED_INPUTS, assess, label_regimes, stale_high_freq
from src.classify.leading import SIGNALS
from src.classify.recession import sahm_gap
from src.classify.regime import INFLATION_HIGH_LEVEL, monthly
from src.classify.stress import (
    MC_YEARS, PROXY, SCENARIOS, monte_carlo, portfolio_returns, recovery, scenario, summary, ticker_weights, trend_returns,
)
from src.classify.risk import CANARY, FILL_DAYS, canary, components as risk_components, label as risk_label, risk_score
from src.classify.score import UNIVERSE, pillars
from src.config.asset_allocation import (
    ALL_WEATHER_WEIGHTS, AREA_EQUITY, ASSET_ALLOCATION, LAZY_PORTFOLIOS, apply_trend, combined_portfolio_weights,
    confirmation,
)
from src.data import cache
from src.data.sync import sync_cache
from src.ui.cards import (
    area_hero_html, asset_matrix_html, axis_card_html, cycle_wave_html, freshness_html, gauge_html, hero_html,
    history_html, lab_html, level_var, month_it, phase_bar_html, portfolio_html, prevailing_regime, prob_html,
    risk_explain_html, risk_html, stat_tile_html, stress_html, trend_chips_html, trend_html, weight_deltas,
)
from src.ui.data import load_indicator, load_scores, spark, ui
from src.ui.market_pages import page_allocation, page_calendar, page_cot, page_currencies, page_markets, page_ranking
from src.ui.theme import hex_color, page_css, phase_color, regime_color
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
    "Ripresa (sotto trend)": "crescita sotto il trend ma in miglioramento",
}
TREND_NAMES = {"SPY": "Azionario", "TLT": "Treasury lunga durata", "IEF": "Treasury medio termine", "TIP": "Indicizzate inflazione",
               "GLD": "Oro", "DBC": "Materie prime"}
RISK_PROFILE_LABELS = {"Basso": "Conservativo", "Medio": "Bilanciato", "Alto": "Aggressivo"}
ALL_WEATHER = "All Weather"
STATIC_PORTFOLIOS = {ALL_WEATHER: ALL_WEATHER_WEIGHTS, **LAZY_PORTFOLIOS}  # pesi fissi, indipendenti da regime e profilo


@st.cache_resource(ttl=600)
def _sync_cache() -> bool:
    """Si memorizza solo un controllo riuscito: se il download fallisce (dopo un redeploy l'app riparte con la cache
    del repo) l'eccezione non viene memorizzata e il caricamento dopo riprova, invece di aspettare 10 minuti."""
    done = sync_cache()
    if done is None:
        raise ConnectionError("cache non sincronizzata")
    return done  # se ha scaricato, updated_at cambia e _fresh_data svuota i load_*



@st.cache_resource
def _seen() -> dict:
    return {}


def _fresh_data(updated_at: str | None) -> None:
    """I load_* non scadono a tempo (ricalcolarli ogni 5 minuti costava ~2 s a chi capitava): si svuotano quando la
    cache su disco cambia, cioe' quando cambia updated_at (download da sync_cache o update_data in locale)."""
    seen = _seen()
    if seen.get("updated_at") != updated_at:
        st.cache_data.clear()
        seen["updated_at"] = updated_at


@st.cache_data
def load_assessment(area: str) -> dict | None:
    """Stesso calcolo dello scheduler (src/classify/assess.py): etichetta, grafici e storico non possono divergere."""
    series = {n: load_indicator(area, n) for n in {*USED_INPUTS, *LEADING_KEYS}}
    a = assess(area, series)
    if a:
        a["label"] = area
    return a


@st.cache_data
def load_risk() -> pd.DataFrame:
    """Componenti del Risk On/Off (src/classify/risk.py) giornaliere, piu' Punteggio e Allarme (momentum del canarino, sotto zero = allarme)."""
    m = lambda k: load_indicator("Mercati", k)
    px = pd.DataFrame({t: load_indicator(im.AREA, t) for t in UNIVERSE})
    if px.empty:
        return px
    comp = risk_components(m("vix"), m("vix3m"), load_indicator("USA", "credit_spread"), m("xly"), m("xlp"), px)
    return comp.assign(Punteggio=risk_score(comp), Allarme=canary(px[CANARY]).reindex(comp.index).ffill(limit=FILL_DAYS)).dropna()



RISK_SAY = {
    "Risk Off estremo": "Mercati in forte tensione: gli investitori scappano dal rischio.",
    "Risk Off": "Mercati nervosi: gli investitori riducono il rischio.",
    "Neutrale": "Mercati né calmi né nervosi.",
    "Risk On": "Mercati tranquilli: gli investitori accettano rischio.",
    "Risk On estremo": "Mercati molto tranquilli: gli investitori cercano rischio.",
}
RISK_PARTS = [("VIX", "Calma in borsa", "volatilità (VIX) rispetto alla sua storia"),
              ("Credito", "Calma sul credito", "stress sulle obbligazioni societarie"),
              ("Ampiezza", "Asset in salita", "quota sopra la media a 200 sedute"),
              ("Struttura", "Paura sul breve assente", "VIX a 1 mese contro VIX a 3 mesi"),
              ("Consumi", "Voglia di spendere", "consumi discrezionali contro beni di base (XLY/XLP)"),
              ("Canarino", "Obbligazioni anti-inflazione", "momentum di TIP, spesso scende prima delle tensioni")]


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



CHART_YEARS = 20


def line_chart(series: dict[str, tuple[pd.Series, str]], key: str, height: int = 300, years: int = CHART_YEARS,
               left: str | None = None) -> None:
    """series: etichetta -> (serie, token colore). Legenda statica sopra il grafico. left: etichetta della serie da
    mettere sulla scala di sinistra (due unita' diverse nello stesso grafico)."""
    ui('<div style="display:flex;flex-wrap:wrap;gap:8px">' + "".join(
        f'<span class="chip"><i class="dot" style="background:var(--{tok})"></i>{escape(label)}</span>' for label, (_, tok) in series.items()
    ) + "</div>")
    renderLightweightCharts([{
        "chart": {
            "layout": {"background": {"type": "solid", "color": "transparent"}, "textColor": hex_color(mode, "muted"),
                       "fontFamily": "DM Mono, monospace"},
            "grid": {"vertLines": {"visible": False}, "horzLines": {"color": hex_color(mode, "line")}},
            "rightPriceScale": {"visible": True, "borderVisible": False},
            "leftPriceScale": {"visible": left is not None, "borderVisible": False},
            "timeScale": {"borderVisible": False, "rightOffset": 6},
            "crosshair": {"mode": 0},
            "height": height,
        },
        "series": [
            {"type": "Line", "data": [{"time": d.strftime("%Y-%m-%d"), "value": round(float(v), 2)} for d, v in s.dropna().loc[pd.Timestamp.today() - pd.DateOffset(years=years):].items()],
             "options": {"color": hex_color(mode, tok), "lineWidth": 2, "priceLineVisible": False, "lastValueVisible": True,
                         "priceScaleId": "left" if label == left else "right"}}
            for label, (s, tok) in series.items()
        ],
    }], key=key)


LOGO_DIR = Path(__file__).resolve().parent.parent / "assets"
st.set_page_config(page_title="Soft Investing", page_icon=str(LOGO_DIR / "logo-mark.svg"), layout="wide")
mode = st.context.theme.type or "dark"
st.logo(str(LOGO_DIR / ("logo-mark.svg" if mode == "dark" else "logo-mark-light.svg")), size="large")
st.html(page_css(mode))

try:
    _sync_cache()
except ConnectionError:
    pass  # si lavora con la cache locale, si riprova al prossimo caricamento
_fresh_data(cache.read_meta("updated_at"))
assessments = {area: a for area in AREAS if (a := load_assessment(area))}


def trend_rows(px: pd.DataFrame) -> list[tuple[str, str, float, float | None]]:
    """Righe di trend_html: classe di asset, ETF, distanza % dalla media a 10 mesi a fine mese e il mese prima."""
    t = pillars(px)["Tendenza"] * 100
    now, prev = t.iloc[-1].dropna(), t.iloc[-2] if len(t) > 1 else pd.Series(dtype=float)
    return [(name, k, now[k], prev.get(k)) for k, name in TREND_NAMES.items() if k in now]


def page_today() -> None:
    """Tre numeri in alto (ciclo, nervosismo dei mercati, tendenza), poi l'onda con i paesi, la matrice paesi x asset
    e la spiegazione del punteggio Risk On/Off."""
    phases = {area: a["phase"] for area, a in assessments.items()}
    top, n = Counter(phases.values()).most_common(1)[0]
    others = " · ".join(f"{k} {v}" for k, v in Counter(phases.values()).most_common()[1:])
    tiles = [stat_tile_html(
        "aree", f"Ciclo economico · dati fino a {month_it(max(a['month'] for a in assessments.values()))}", n, len(phases),
        f"in {top or 'n/d'}", phase_color(top), phase_bar_html(phases), escape(others))]
    risk = load_risk()
    if not risk.empty:
        r = risk.iloc[-1]
        s = max(1, round(r["Punteggio"]))
        state = risk_label(r["Punteggio"])
        alarm = r["Allarme"] < 0
        tiles.append(stat_tile_html(
            "#cosa-vuol-dire", f"Nervosismo dei mercati · al {risk.index[-1]:%d/%m}", s, 100, state, f"var(--{level_var(s)})",
            f'<div class="track"><i style="width:{s}%;background:var(--{level_var(s)})"></i></div>',
            escape(RISK_SAY[state]) + (' <b style="color:var(--r-refl)">Canarino in allarme.</b>' if alarm else "")))
    px, sc = load_scores()
    if not px.empty and not sc.empty:
        trend = pillars(px)["Tendenza"].iloc[-1].dropna()
        up = int((trend > 0).sum())
        best = sc.iloc[-1].dropna().sort_values(ascending=False).head(3)
        tiles.append(stat_tile_html(
            "classifica", f"Tendenza degli asset · fine {month_it(px.index[-1])}", up, len(trend), "in salita", "var(--fg)",
            f'<div class="track"><i style="width:{up / len(trend):.0%};background:var(--accent)"></i></div>',
            "Più forti: " + escape(", ".join(UNIVERSE[t][0] for t in best.index))))
    ui(hero_html(f"Oggi · {pd.Timestamp.today():%d/%m/%Y}", "Il quadro di oggi",
                 "Tre numeri, il filtro di tendenza, poi dove si trova ogni paese nel ciclo e cosa pesare di più o di meno. Tocca una card per il dettaglio."))
    ui('<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(240px,1fr))">' + "".join(tiles) + "</div>")
    if not px.empty:
        # unica regola con effetto dimostrato (drawdown -55/75%): in evidenza prima delle letture descrittive
        st.space("small")
        ui(trend_html(trend_rows(px), px.index[-1]))
        st.caption("Per applicarlo alla tua allocazione: interruttore **Filtro di tendenza** nella pagina **Portafoglio**.")
    st.space("small")
    ui('<div class="card"><span class="eyebrow">In che fase è ogni paese</span>' + cycle_wave_html(phases) + "</div>")
    st.space("small")
    ui('<div class="card"><span class="eyebrow">Cosa pesare, paese per paese</span>' + asset_matrix_html(phases)
       + '<p class="note"><span style="color:var(--r-gold)">▲</span> più peso · <span style="color:var(--r-stag)">▼</span> meno peso · '
       "vuoto = neutro. Sui dati USA dal 1985 le direzioni tornano, ma l'unica "
       "differenza netta è che i titoli di Stato rendono meno in Espansione: tendenze storiche, non previsioni.</p></div>")
    if not risk.empty:
        st.space("small")
        ui('<span id="cosa-vuol-dire"></span>' + risk_explain_html(r["Punteggio"], state, f"{risk.index[-1]:%d/%m/%Y}",
                             [(name, desc, r[col]) for col, name, desc in RISK_PARTS], alarm))
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
    px = load_scores()[0]
    above = {} if px.empty else (pillars(px)["Tendenza"].iloc[-1].dropna() > 0).to_dict()
    conf = confirmation(a["regime"], above, AREA_EQUITY.get(area))
    ui(area_hero_html(a, describe(a), (sum(up for *_, up in conf), len(conf))))

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
           "PIL annuo contro il trimestre prima: conta la velocità della crescita, non il livello."
           if growth_src != "cli" else "Direzione del leading indicator OCSE (PIL non disponibile).")
       + axis_card_html(
           "Inflazione · media totale e core",
           "Alta o in salita" if a["inflation_state"] == "up" else "Sotto controllo",
           "r-stag" if a["inflation_state"] == "up" else "r-gold",
           f"{a['inflation_level']:.1f}%", f"soglia {INFLATION_HIGH_LEVEL:.1f}%",
           gauge_html(xi, "sotto controllo", "alta", "r-gold", "r-stag"),
           "Alta se la media degli ultimi 3 mesi supera la soglia oppure se sale rispetto ai 3 mesi prima.")
       + f'<div class="card"><div class="head"><h3>Stima a fine trimestre</h3><span class="note">produzione industriale e CLI, calibrata dal 2000</span></div>'
         f'{prob_html(a["inflation_prob"], a["quarter_end_estimate"])}<p class="note">Stima, diversa dal regime attuale sopra: probabilità che '
         f'l\'inflazione del trimestre in corso risulti alta o in salita a dati completi. La crescita del trimestre non si prevede '
         f'(resta vicina al 50%): crescita incerta.</p></div>'
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
        trend = {asset: (t, up) for asset, t, up in conf}
        items = [(f"{asset} · {trend[asset][0]}" if asset in trend else asset, trend[asset][1] if asset in trend else None)
                 for asset in ASSET_ALLOCATION.get(a["regime"], [])]
        ui(f'<div class="card"><h3>Asset tipici in {escape(a["regime"])}</h3>{trend_chips_html(items)}'
           '<p class="note">Verde = ETF sopra la media a 10 mesi (fine mese), rosso = sotto, grigio = senza ETF. Dice se i mercati '
           'si muovono come il regime, non se il regime è giusto: dal 2004, con almeno 2 asset su 3 in salita la lettura del '
           'momento è stata confermata a dati completi nel 49% dei mesi, con al massimo 1 su 3 nel 51%. La tabella è di '
           'letteratura, non un vantaggio dimostrato: vedi la sezione Metodo.</p></div>')

def page_portfolio() -> None:
    regimes = {area: a["regime_label"] for area, a in assessments.items()}
    uncertain = [area for area, label in regimes.items() if len(label_regimes(label)) > 1]
    with st.container(horizontal=True, vertical_alignment="bottom", gap="large"):
        top, n = prevailing_regime(regimes)
        ui(hero_html("Portafoglio multi-area", f'Regime prevalente: <span style="color:{regime_color(top)}">{top}</span>',
                     f"{n} aree su {len(regimes)}. Media equipesata dei portafogli per regime di ogni area."))
        risk_profile = st.segmented_control("Profilo o portafoglio pigro", ["Basso", "Medio", "Alto", *STATIC_PORTFOLIOS],
                                            default="Medio", required=True, key="risk", bind="query-params")
    if risk_profile in STATIC_PORTFOLIOS:
        weights, deltas = STATIC_PORTFOLIOS[risk_profile], None
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
    base = weights
    if use_trend:
        filtered = apply_trend(weights, (trend > 0).to_dict())
        weights, deltas, delta_note = filtered, weight_deltas(filtered, weights), "vs senza filtro"
    col_p, col_t = st.columns([8, 4])
    with col_p:
        ui(portfolio_html(weights, deltas, "Allocazione", RISK_PROFILE_LABELS.get(risk_profile, "pesi statici"), delta_note))
        if uncertain and risk_profile not in STATIC_PORTFOLIOS:
            st.caption(f"Aree incerte ({', '.join(uncertain)}): metà pesi di ciascuno dei due regimi.")
    with col_t:
        if trend.empty:
            st.info("Nessun prezzo degli ETF in cache per il filtro di tendenza.", icon=":material/database:")
        else:
            ui(trend_html(trend_rows(px), px.index[-1]))
    if not px.empty:
        stress_section(base, px)
    st.caption("Dentro ogni regime la quota azionaria segue il profilo (Basso 30%, Medio 50%, Alto 70%). "
               "Solo informativo, non è consulenza: il backtest non mostra un vantaggio sui portafogli statici (sezione Metodo).")

STRESS_ASSETS = sorted({*PROXY, *ALL_WEATHER_WEIGHTS, *(a for v in ASSET_ALLOCATION.values() for a in v)})


def stress_section(weights: dict, px: pd.DataFrame) -> None:
    """Posizioni modificabili (partono dall'allocazione mostrata, senza filtro) e loro backtest e stress test con e senza
    filtro di tendenza (src/classify/stress.py)."""
    col_in, col_out = st.columns([5, 7])
    with col_in:
        st.markdown("**Le tue posizioni**")
        edited = st.data_editor(
            pd.DataFrame({"Asset": list(weights), "Peso %": [round(w, 1) for w in weights.values()]}),
            num_rows="dynamic", hide_index=True, width="stretch",
            column_config={"Asset": st.column_config.SelectboxColumn(options=STRESS_ASSETS, required=True),
                           "Peso %": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, step=1.0, format="%.1f")})
        st.caption("Parte dall'allocazione qui sopra senza filtro: cambia pesi o aggiungi righe. I pesi si riportano a 100. "
                   "Il filtro si confronta nel backtest.")
    edited = edited.dropna()
    tw, skipped = ticker_weights(edited.groupby("Asset")["Peso %"].sum().to_dict())
    with col_out:
        if not tw:
            st.info("Inserisci almeno una posizione con un ETF di riferimento.", icon=":material/edit:")
            return
        r, rt, spy = portfolio_returns(tw, px), trend_returns(tw, px), px["SPY"].pct_change(fill_method=None)
        common = r.dropna().index.intersection(rt.dropna().index)
        plain = summary(r.loc[common])
        if plain:
            ui(lab_html(plain, summary(rt.loc[common])))
            line_chart({"Senza filtro": (100 * (1 + r.loc[common]).cumprod(), "r-defl"),
                        "Con filtro": (100 * (1 + rt.loc[common]).cumprod(), "r-refl")}, key="lab", height=240, years=40)

    def crisis(x: pd.Series, a: str, b: str) -> tuple | None:
        sc = scenario(x, a, b)
        return (*sc, recovery(x, a, b)) if sc else None
    rows = [(name, f"{month_it(pd.Timestamp(a), True)} – {month_it(pd.Timestamp(b), True)}", crisis(r, a, b), crisis(rt, a, b),
             crisis(spy, a, b)) for name, (a, b) in SCENARIOS.items()]
    ui(stress_html(rows, monte_carlo(r), MC_YEARS, skipped))



def page_method() -> None:
    ui(hero_html("Metodo", "Come leggere i regimi", "Regole semplici e pubbliche, verificate sui dati come erano disponibili al momento."))
    col_a, col_b = st.columns(2)
    with col_a, st.container(border=True):
        st.markdown(
            "#### Regime macro\n"
            "Due assi: crescita e inflazione.\n\n"
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
            "- **Ripresa (sotto trend)**: CLI in salita con PIL ancora sotto il trend, o dopo una recessione.\n"
            "- **Rallentamento**: CLI in calo, senza conferme di recessione.\n"
            "- **Recessione**: solo con conferma dai dati: regola di Sahm sulla disoccupazione "
            "(negli USA confermata dalla probabilità Chauvet-Piger) oppure PIL annuo negativo.\n\n"
            "Gli **indicatori anticipatori** (curva, spread, sentiment) sono mostrati a parte e non cambiano la fase."
        )
    with st.container(border=True):
        st.markdown("#### Affidabilità, dal 2000 (`scripts/evaluate_model.py`, 19/10/2026)")
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
            "Tempo reale = con i ritardi di pubblicazione veri (inflazione 1 mese, PIL 4): il PIL del trimestre si "
            "conosce tardi e viene rivisto, per questo la lettura del momento coincide con quella a posteriori circa "
            "1 mese su 2. Nel Regno Unito il ciclo è poco preciso; il regime non prevede i rendimenti futuri."
        )
        # numeri da scripts/evaluate_model.py, riga "Letture di riferimento" (19/10/2026)
        st.markdown(
            "**Letture note**: su 17 trimestri con un regime già documentato (2015-2026, soprattutto USA) il modello ne "
            "riproduce **14**. La regola è stata scelta guardando le prime 14, quindi è un controllo di coerenza, non una "
            "prova: delle 3 letture aggiunte dopo (Canada, Cina, Australia, 3° trimestre 2026) ne riproduce 1."
        )


SIZE_PAGE = st.Page(lambda: page_sizing(mode), title="Size Monte Carlo", icon=":material/casino:", url_path="size")
PAGES = {
    "": [st.Page(page_today, title="Oggi", icon=":material/today:", url_path="oggi", default=True)],
    "Macro": [
        st.Page(page_area, title="Aree", icon=":material/location_on:", url_path="aree"),
        st.Page(page_method, title="Metodo", icon=":material/menu_book:", url_path="metodo"),
    ],
    "Mercati": [
        st.Page(page_ranking, title="Classifica", icon=":material/leaderboard:", url_path="classifica"),
        st.Page(page_allocation, title="Allocazione", icon=":material/public:", url_path="allocazione"),
        st.Page(page_markets, title="Mercati", icon=":material/candlestick_chart:", url_path="mercati"),
        st.Page(lambda: page_cot(mode), title="COT report", icon=":material/groups:", url_path="cot"),
        st.Page(page_currencies, title="Valute", icon=":material/currency_exchange:", url_path="valute"),
        st.Page(page_calendar, title="Calendario", icon=":material/calendar_month:", url_path="calendario"),
    ],
    "Strumenti": [
        st.Page(page_portfolio, title="Portafoglio", icon=":material/donut_large:", url_path="portafoglio"),
        SIZE_PAGE,
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
failures = json.loads(cache.read_meta("fetch_failures") or "[]")
if failures:
    st.warning("Fetch falliti nell'ultimo aggiornamento: " + ", ".join(
        f'{f["indicator"]} ({f["area"]}, {pd.Timestamp(f["time"]):%H:%M}) — {f["message"]}' for f in failures
    ) + ". Tengo i dati in cache.", icon=":material/schedule:")
if not assessments:
    st.info("Nessun dato in cache. Esegui `python -m src.scheduler.update_data` per popolare.", icon=":material/database:")
    st.stop()
nav.run()
