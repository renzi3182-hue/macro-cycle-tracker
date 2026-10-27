import json
import sys
from collections import Counter
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st
from streamlit_lightweight_charts import renderLightweightCharts

from src.classify import changes
from src.classify import opportunities as opp
from src.classify.assess import HIGH_FREQ_MAX_DAYS, label_regimes, stale_high_freq
from src.classify.leading import SIGNALS
from src.classify.recession import sahm_gap
from src.classify.regime import monthly
from src.classify.stress import (
    EXTRA_ETF, MC_YEARS, PROXY, SCENARIOS, common_window, eur_returns, monte_carlo, portfolio_returns, recovery, scenario, summary, ticker_weights,
    trend_returns,
)
from src.classify.risk import label as risk_label
from src.classify.score import UNIVERSE, pillars
from src.config.asset_allocation import (
    AREA_EQUITY, ASSET_ALLOCATION, TREND_PROXY, apply_trend, combined_portfolio_weights,
    confirmation,
)
from src.data import cache
from src.data.sync import sync_cache
from src.ui.cards import (
    area_hero_html, axis_card_html, bands_html, changes_html, cycle_wave_html, freshness_html, gauge_html, hero_html,
    history_html, lab_html, label_phrase, level_var, month_it, opportunity_map_html, phase_bar_html, portfolio_html,
    prevailing_regime, prob_html,
    regimes_html, reliability_html, reliability_table_html, risk_explain_html, risk_html, stat_tile_html, stress_html, ucits_html,
    trend_chips_html, trend_html, weight_deltas, cap,
)
from src.classify.score import HORIZON_MONTHS, band_table, forward_excess
from src.ui.data import load_allocation, load_indicator, load_model, load_scores, load_usd_per_eur, spark, ui
from src.ui.market_pages import country_allocation, page_allocation, page_calendar, page_cot, page_markets, page_ranking
from src.ui.shared import (
    AREAS, INPUT_LABELS, LEADING_LABELS, RISK_PARTS, RISK_PROFILE_LABELS, RISK_SAY, STATIC_PORTFOLIOS, STRESS_ASSETS,
    describe, load_assessment, load_risk, trend_rows,
)
from src.ui.theme import hex_color, page_css, phase_color, regime_color



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


def page_today() -> None:
    """Tre numeri in alto (ciclo, nervosismo dei mercati, tendenza), cosa e' cambiato dal mese scorso, poi l'onda con i
    paesi, crescita e inflazione, la mappa delle occasioni (paesi x classi di asset) e il punteggio Risk On/Off."""
    phases = {area: a["phase"] for area, a in assessments.items()}
    top, n = Counter(phases.values()).most_common(1)[0]
    others = " · ".join(f"{k} {v}" for k, v in Counter(phases.values()).most_common()[1:])
    tiles = [stat_tile_html(
        "paese", f"Ciclo economico · dati fino a {month_it(max(a['month'] for a in assessments.values()))}", n, len(phases),
        f"in {top or 'n/d'}", phase_color(top), phase_bar_html(phases), escape(others), "Descrittivo")]
    risk = load_risk()
    if not risk.empty:
        r = risk.iloc[-1]
        s = max(1, round(r["Punteggio"]))
        state = risk_label(r["Punteggio"])
        alarm = r["Allarme"] < 0
        tiles.append(stat_tile_html(
            "#cosa-vuol-dire", f"Nervosismo dei mercati · al {risk.index[-1]:%d/%m}", s, 100, state, f"var(--{level_var(s)})",
            f'<div class="track"><i style="width:{s}%;background:var(--{level_var(s)})"></i></div>',
            escape(RISK_SAY[state]) + (' <b style="color:var(--r-refl)">Canarino in allarme.</b>' if alarm else ""), "Descrittivo"))
    px, sc = load_scores()
    trend = pillars(px.drop(columns=EXTRA_ETF))["Tendenza"].iloc[-1].dropna() if not px.empty else px  # solo la Classifica
    if not trend.empty and not sc.empty:
        up = int((trend > 0).sum())
        best = sc.iloc[-1].dropna().sort_values(ascending=False).head(3)
        tiles.append(stat_tile_html(
            "asset", f"Tendenza degli asset · fine {month_it(px.index[-1])}", up, len(trend), "in salita", "var(--fg)",
            f'<div class="track"><i style="width:{up / len(trend):.0%};background:var(--accent)"></i></div>',
            "Più forti: " + escape(", ".join(UNIVERSE[t][0] for t in best.index)), "Verificato"))
    ui(hero_html(f"Oggi · {pd.Timestamp.today():%d/%m/%Y}", "Il quadro di oggi",
                 "Tre numeri, cosa è cambiato dal mese scorso, il filtro di tendenza, poi dove si trova ogni paese nel ciclo, "
                 "come vanno crescita e inflazione e cosa pesare di più o di meno. Tocca una card per il dettaglio."))
    ui('<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(240px,1fr))">' + "".join(tiles) + "</div>")
    alloc = load_allocation()
    if not px.empty:
        st.space("small")
        names = {t: name for t, (name, _) in UNIVERSE.items()}
        rankings = {"Classifica asset": ("ranking", load_model()["prob"].rename(columns=lambda t: f"{names[t]} ({t})"))}
        if alloc:
            rankings = {"Paesi": ("countries", alloc["Paesi"]["prob"]),
                        "Classi di asset": ("asset_classes", changes.cells_by_month(alloc["Classi di asset"]["prob"], opp.CLASS_NAMES)),
                        **rankings}
        items = changes.summary({area: a["history"] for area, a in assessments.items()},
                                pillars(px.drop(columns=EXTRA_ETF))["Tendenza"], names, rankings)
        ui(changes_html(items, px.index[-1]))
        if items:
            with st.expander("Testo da copiare", icon=":material/content_copy:"):
                st.code("\n".join(text for _, text in items), language=None, wrap_lines=True)
    if not px.empty:
        # unica regola con effetto dimostrato (drawdown -55/75%): in evidenza prima delle letture descrittive
        st.space("small")
        ui(trend_html(trend_rows(px), px.index[-1]))
        st.caption("Per applicarlo alla tua allocazione: interruttore **Filtro di tendenza** nella pagina **Portafoglio**.")
    st.space("small")
    ui('<div class="card"><span class="eyebrow">In che fase è ogni paese</span>' + reliability_html("phase")
       + cycle_wave_html(phases) + "</div>")
    st.space("small")
    ui(regimes_html(assessments))
    st.space("small")
    if alloc:
        cl = alloc["Classi di asset"]
        month, grid = opp.grid(cl["score"], cl["prob"], cl["raw"]["Tendenza"], phases)
        if grid:
            ui(opportunity_map_html(grid, opp.best(grid), phases, month))
    if not risk.empty:
        st.space("small")
        ui('<span id="cosa-vuol-dire"></span>' + risk_explain_html(r["Punteggio"], state, f"{risk.index[-1]:%d/%m/%Y}",
                             [(name, desc, r[col]) for col, name, desc in RISK_PARTS], alarm))
    st.caption("Solo informativo, non è consulenza finanziaria. Metodo e affidabilità nella sezione **Metodo**.")


def section(title: str, lead: str) -> None:
    ui(f'<h2 class="sec">{escape(title)}</h2><p class="note" style="font-size:15px">{lead}</p>')


def page_area() -> None:
    """Il mio paese (26/10/2026): un paese scelto (?area= nell'URL), poi le sue classi di asset, la sua valuta e il quadro
    macro (regime, fase, anticipatori, dati)."""
    # con ?area= vuoto o sconosciuto nell'URL il widget legato ai parametri restituisce None: si torna al predefinito
    area = st.segmented_control("Area", list(AREAS), default="USA", required=True, key="area",
                                bind="query-params", label_visibility="collapsed") or "USA"
    ui(hero_html("Il mio paese", escape(area), "Cosa pesare di più dentro il paese, come sta la sua valuta e il quadro "
                 "macro: crescita, inflazione e fase del ciclo. Cambia paese qui sopra: il link resta sul paese scelto."))
    section("Classi di asset e valuta", "Azioni, titoli di Stato, liquidità e oro del paese, in valuta locale, per "
            "probabilità di rendere più delle altre nei 6 mesi dopo; poi la valuta fra le 8 dell'app.")
    country_allocation(area)
    a = assessments.get(area)
    if not a:
        st.info("Nessun dato macro in cache per quest'area.", icon=":material/database:")
        st.stop()
    section("Il quadro macro", "Crescita e inflazione, fase del ciclo, indicatori anticipatori e dati usati.")
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
           "In accelerazione" if a["inflation_state"] == "up" else "In rallentamento",
           "r-stag" if a["inflation_state"] == "up" else "r-gold",
           f"{a['inflation_level']:.1f}%", f"{a['inflation_change']:+.2f} sui 3 mesi prima",
           gauge_html(xi, "rallenta", "accelera", "r-gold", "r-stag"),
           "Inflazione totale (media 3 mesi) contro i 3 mesi prima: conta la direzione, non il livello.")
       + f'<div class="card"><div class="head"><h3>Stima a fine trimestre</h3><span class="note">produzione industriale e CLI</span></div>'
         f'{reliability_html("quarter")}{prob_html(a["inflation_prob"], a["quarter_end_estimate"])}<p class="note">Stima, diversa dal regime attuale sopra: probabilità che '
         f'l\'inflazione del trimestre in corso risulti in salita a dati completi. La crescita del trimestre non si prevede '
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
                    st.caption("Recessione in corso: " + ("**confermata** da disoccupazione e probabilità di recessione."
                               if a["recession"] else "non confermata da disoccupazione e probabilità di recessione.")
                               + " Regole e soglie nella sezione Metodo.")
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
        ui(f'<div class="card"><div class="head"><h3>Asset tipici quando {escape(label_phrase(a["regime"]))}</h3>'
           f'<span class="note">regime {escape(a["regime"])}</span></div>{reliability_html("regime_assets")}{trend_chips_html(items)}'
           f'{reliability_html("confirmation")}'
           '<p class="note">Verde = ETF sopra la media a 10 mesi (fine mese), rosso = sotto, grigio = senza ETF.</p></div>')

def page_portfolio() -> None:
    regimes = {area: a["regime_label"] for area, a in assessments.items()}
    uncertain = [area for area, label in regimes.items() if len(label_regimes(label)) > 1]
    with st.container(horizontal=True, vertical_alignment="bottom", gap="large"):
        top, n = prevailing_regime(regimes)
        ui(hero_html("Portafoglio multi-area", f'<span style="color:{regime_color(top)}">{escape(cap(label_phrase(top)))}</span>',
                     f"La situazione più comune, in {n} aree su {len(regimes)}: regime prevalente <b>{escape(top)}</b>. "
                     + ("Incerto = un asse è vicino alla soglia, quindi conta per metà in ciascuno dei due regimi. "
                        if len(label_regimes(top)) > 1 else "")
                     + "Media equipesata dei portafogli per regime di ogni area."))
        risk_profile = st.segmented_control("Profilo o portafoglio pigro", ["Basso", "Medio", "Alto", *STATIC_PORTFOLIOS],
                                            default="Medio", required=True, key="risk", bind="query-params") or "Medio"
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
        ui(portfolio_html(weights, deltas, "Allocazione", RISK_PROFILE_LABELS.get(risk_profile, "pesi statici"), delta_note,
                          "" if risk_profile in STATIC_PORTFOLIOS else reliability_html("regime_assets")))
        if uncertain and risk_profile not in STATIC_PORTFOLIOS:
            st.caption(f"Aree incerte ({', '.join(uncertain)}): un asse è vicino alla soglia, quindi metà pesi a "
                       "ciascuno dei due regimi possibili.")
    with col_t:
        if trend.empty:
            st.info("Nessun prezzo degli ETF in cache per il filtro di tendenza.", icon=":material/database:")
        else:  # una riga per ogni ETF del portafoglio: si vede quale quota il filtro manda in cash
            ui(trend_html(trend_rows(px, {TREND_PROXY[a]: a for a in sorted(base, key=base.get, reverse=True) if a in TREND_PROXY}),
                          px.index[-1]))
    if not px.empty:
        stress_section(base, px)
    st.caption("Dentro ogni regime la quota azionaria segue il profilo (Basso 30%, Medio 50%, Alto 70%). "
               "Solo informativo, non è consulenza: il backtest non mostra un vantaggio sui portafogli statici (sezione Metodo).")

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
        ccy = st.segmented_control("Valuta dei risultati", ["Dollari", "Euro"], default="Dollari", required=True,
                                   key="valuta", bind="query-params") or "Dollari"
        st.caption("Euro = per chi investe dall'Italia in ETF in dollari senza copertura del cambio (cambio EUR/USD, prima "
                   "del 1999 il marco). Segnali e filtro restano calcolati in dollari.")
    edited = edited.dropna()
    tw, skipped = ticker_weights(edited.groupby("Asset")["Peso %"].sum().to_dict())
    with col_out:
        if not tw:
            st.info("Inserisci almeno una posizione con un ETF di riferimento.", icon=":material/edit:")
            return
        r, rt, spy = portfolio_returns(tw, px), trend_returns(tw, px), px["SPY"].pct_change(fill_method=None)
        unit = "$"
        if ccy == "Euro":
            usd_per_eur = load_usd_per_eur()
            r, rt, spy, unit = eur_returns(r, usd_per_eur), eur_returns(rt, usd_per_eur), eur_returns(spy, usd_per_eur), "€"
        common = common_window(r, rt)
        plain, filtered = summary(r.loc[common]), summary(rt.loc[common])
        if not plain:  # il filtro non ha un tratto abbastanza lungo (manca la liquidita' BIL): solo il portafoglio
            common = common_window(r)
            plain, filtered = summary(r.loc[common]), None
        if plain:
            ui(lab_html(plain, filtered, unit))
            line_chart({"Senza filtro": (100 * (1 + r.loc[common]).cumprod(), "r-defl"),
                        **({"Con filtro": (100 * (1 + rt.loc[common]).cumprod(), "r-refl")} if filtered else {})},
                       key="lab", height=240, years=40)

    def crisis(x: pd.Series, a: str, b: str) -> tuple | None:
        sc = scenario(x, a, b)
        return (*sc, recovery(x, a, b)) if sc else None
    rows = [(name, f"{month_it(pd.Timestamp(a), True)} – {month_it(pd.Timestamp(b), True)}", crisis(r, a, b), crisis(rt, a, b),
             crisis(spy, a, b)) for name, (a, b) in SCENARIOS.items()]
    ui(stress_html(rows, monte_carlo(r), MC_YEARS, skipped, unit))
    ui(ucits_html(list(tw), {t: a for a, t in PROXY.items()}))



def page_method() -> None:
    ui(hero_html("Metodo", "Come leggere i regimi", "Regole semplici e pubbliche, verificate sui dati come erano disponibili al momento. "
                 "Ogni lettura dell'app ha un'etichetta: <b>Verificato</b>, <b>Teoria</b> o <b>Descrittivo</b>. Qui i numeri."))
    ui(reliability_table_html())
    m = load_model()
    if not m["score"].empty:
        s = m["score"]
        ui(bands_html(band_table(s, forward_excess(m["px"], s)), HORIZON_MONTHS, s.index[0]))
    st.space("small")
    col_a, col_b = st.columns(2)
    with col_a, st.container(border=True):
        st.markdown(
            "#### Regime macro\n"
            "Due assi: crescita e inflazione.\n\n"
            "- **Crescita**: PIL annuo contro il trimestre prima. In aumento = l'economia accelera, in calo = rallenta, "
            "anche se cresce ancora.\n"
            "- **Inflazione**: inflazione totale degli ultimi 3 mesi contro i 3 mesi prima. In aumento = accelera, "
            "in calo = rallenta, anche se resta alta.\n\n"
            "Il PIL cambia una volta a trimestre: il regime può cambiare 3-4 volte l'anno.\n\n"
            "**Probabilità**: quanto è probabile che l'inflazione del trimestre in corso risulti in salita, a dati completi (la crescita è mostrata come incerta). Calibrate sul "
            "passato (9 aree dal 2000): una probabilità del 70% si è avverata circa 7 volte su 10. L'inflazione si prevede "
            "bene (84% dei mesi dal 2015), l'accelerazione del PIL del trimestre no (56%, quasi una moneta): neanche "
            "la produzione industriale mensile la anticipa davvero.\n\n"
            "| | Inflazione in rallentamento | Inflazione in accelerazione |\n|---|---|---|\n"
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
        st.markdown("#### Affidabilità, dal 2000 (`scripts/evaluate_model.py`, 25/10/2026)")
        st.table(pd.DataFrame([
            {"Area": "USA", "Regime: tempo reale = storico": "44%", "Cambi di regime/anno": "3,6", "Ciclo vs riferimento": "NBER: 100% dei mesi di recessione in Rallentamento o Recessione, Recessione fuori 1%"},
            {"Area": "Eurozona", "Regime: tempo reale = storico": "56%", "Cambi di regime/anno": "3,1", "Ciclo vs riferimento": "OCSE: 86% dentro, 19% fuori"},
            {"Area": "Italia", "Regime: tempo reale = storico": "49%", "Cambi di regime/anno": "3,2", "Ciclo vs riferimento": "OCSE: 80% dentro, 28% fuori"},
            {"Area": "UK", "Regime: tempo reale = storico": "57%", "Cambi di regime/anno": "2,5", "Ciclo vs riferimento": "OCSE: 51% dentro, 45% fuori (debole)"},
            {"Area": "Giappone", "Regime: tempo reale = storico": "45%", "Cambi di regime/anno": "3,5", "Ciclo vs riferimento": "OCSE: 66% dentro, 16% fuori"},
            {"Area": "Canada", "Regime: tempo reale = storico": "44%", "Cambi di regime/anno": "3,8", "Ciclo vs riferimento": "OCSE: 74% dentro, 38% fuori"},
            {"Area": "Cina", "Regime: tempo reale = storico": "43%", "Cambi di regime/anno": "3,6", "Ciclo vs riferimento": "OCSE: 72% dentro, 30% fuori (dati meno affidabili)"},
            {"Area": "Australia", "Regime: tempo reale = storico": "46%", "Cambi di regime/anno": "3,4", "Ciclo vs riferimento": "OCSE: 48% dentro, 66% fuori (debole)"},
            {"Area": "India", "Regime: tempo reale = storico": "41%", "Cambi di regime/anno": "4,4", "Ciclo vs riferimento": "OCSE: 92% dentro, 25% fuori"},
        ]).set_index("Area"))
        st.caption(
            "Tempo reale = con i ritardi di pubblicazione veri (inflazione 1 mese, PIL 4): il PIL del trimestre si "
            "conosce tardi e viene rivisto, per questo la lettura del momento coincide con quella a posteriori circa "
            "1 mese su 2. Nel Regno Unito il ciclo è poco preciso; il regime non prevede i rendimenti futuri."
        )
        # numeri da scripts/evaluate_model.py, riga "Letture di riferimento" (25/10/2026)
        st.markdown(
            "**Letture note**: su 29 trimestri con un regime già documentato (2015-2026: USA, Eurozona, Cina e altre aree) "
            "il modello ne riproduce **18**. La regola segue una definizione fissa (solo la direzione di crescita e "
            "inflazione), non tarata su queste letture: è un controllo di coerenza, non una prova. Riproduce 9 delle 13 "
            "letture 2023-2024 e 1 delle 5 del 3° trimestre 2026."
        )


# Cinque voci principali in alto; il resto nel menu Avanzato (url_path "aree" e "classifica" diventati "paese" e "asset").
PAGE_AREA = st.Page(page_area, title="Il mio paese", icon=":material/location_on:", url_path="paese")
PAGE_ASSET = st.Page(page_ranking, title="Asset", icon=":material/leaderboard:", url_path="asset")
PAGE_ALLOCATION = st.Page(page_allocation, title="Allocazione", icon=":material/public:", url_path="allocazione")
# indirizzi di prima del 26/10/2026 (link salvati o condivisi): portano alla pagina che li ha sostituiti
OLD_PATHS = {"aree": PAGE_AREA, "classifica": PAGE_ASSET, "valute": PAGE_ALLOCATION}
PAGES = {
    "": [
        st.Page(page_today, title="Oggi", icon=":material/today:", url_path="oggi", default=True),
        PAGE_AREA,
        PAGE_ASSET,
        st.Page(page_portfolio, title="Portafoglio", icon=":material/donut_large:", url_path="portafoglio"),
        st.Page(page_method, title="Metodo", icon=":material/menu_book:", url_path="metodo"),
    ],
    "Avanzato": [
        st.Page(lambda: page_cot(mode), title="COT report", icon=":material/groups:", url_path="cot"),
        st.Page(page_calendar, title="Calendario", icon=":material/calendar_month:", url_path="calendario"),
        st.Page(page_markets, title="Mercati", icon=":material/candlestick_chart:", url_path="mercati"),
        PAGE_ALLOCATION,
        *(st.Page(lambda p=p: st.switch_page(p, query_params=st.query_params.to_dict()), title=p.title, url_path=old,
                  visibility="hidden")
          for old, p in OLD_PATHS.items()),
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
