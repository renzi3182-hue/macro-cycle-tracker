"""Pagine del gruppo Mercati: Classifica, Mercati, COT report, Valute, Calendario."""
import math

import altair as alt
import pandas as pd
import streamlit as st

from src.classify import intermarket as im
from src.classify.currency import CURRENCIES, PAIRS, cot_component, momentum_returns, pair_view, strength_score, vix_component
from src.classify.positioning import percentile_rank, zscore
from src.classify.rrg import GROUPS, MOMENTUM_WEEKS, TREND_WEEKS, quadrant, rrg, weekly_prices
from src.classify.score import HORIZON_MONTHS, STRONG, UNIVERSE, WEAK, band_table, forward_excess, pillars
from src.config import cot_guide
from src.data import cache
from src.data.fetch_cot import CONTRACTS, DISAGG_GROUPS, DISAGG_MARKETS, TFF_GROUPS, WEEKS as COT_WEEKS
from src.ui.cards import (
    bands_html, calendar_html, cot_groups_html, events_html, hero_html, month_it, pairs_html, ranking_html, relations_html,
    rrg_html, strength_html, why_text,
)
from src.ui.data import load_indicator, load_scores, spark, ui
from src.ui.theme import hex_color

IMPACT_LABELS_IT = {"Alto": "High", "Medio": "Medium", "Basso": "Low", "Festivo": "Holiday"}
CCY_COT = {"USD": "Dollaro (DXY)", "EUR": "Euro", "GBP": "Sterlina", "JPY": "Yen"}
CCY_AREA = {"USD": "USA", "EUR": "Eurozona", "GBP": "UK", "JPY": "Giappone"}


@st.cache_data
def load_events() -> list[dict]:
    return cache.read_events()



def last_value(area: str, indicator: str) -> float | None:
    s = load_indicator(area, indicator)
    return None if s.empty else float(s.iloc[-1])



@st.cache_data
def load_weekly() -> tuple[pd.DataFrame, pd.Timestamp | None]:
    """Chiusure settimanali degli ETF (rotazione, src/classify/rrg.py) e data dell'ultima chiusura giornaliera."""
    daily = pd.DataFrame({t: load_indicator(im.AREA, t) for t in UNIVERSE})
    return (daily, None) if daily.empty else (weekly_prices(daily), daily.index[-1])



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
    ranks = {k: v[now.index].rank(ascending=False, method="min").astype(int) for k, v in p.items()}
    rows = [{"ticker": t, "nome": UNIVERSE[t][0], "gruppo": UNIVERSE[t][1], "punteggio": sc,
             "delta": sc - prev[t] if pd.notna(prev.get(t)) else None, **{k: v[t] for k, v in p.items()}, "storico": s[t],
             "perche": why_text({k: r[t] for k, r in ranks.items()}, len(now))}
            for t, sc in now.items() if group == "Tutti" or UNIVERSE[t][1] == group]
    col_r, col_e = st.columns([8, 4])
    with col_r:
        ui(ranking_html(rows, month))
    with col_e:
        ui(bands_html(band_table(s, forward_excess(px, s)), HORIZON_MONTHS, s.index[0]))
        wk, last_day = load_weekly()
        if not wk.empty:
            rot = st.segmented_control("Rotazione", list(GROUPS), default="Settori USA", required=True, key="rot",
                                       label_visibility="collapsed")
            ratio, mom = (x.iloc[-1].dropna() for x in rrg(wk, GROUPS[rot], TREND_WEEKS, MOMENTUM_WEEKS))
            items = [{"ticker": t, "nome": UNIVERSE[t][0], "ratio": ratio[t], "momentum": mom[t], "quadrante": quadrant(ratio[t], mom[t])}
                     for t in ratio.index.intersection(mom.index)]
            if items:
                ui(rrg_html(items, f"Rotazione · {rot}", f"settimanale, al {last_day:%d/%m/%Y}"))
    st.caption(f"Solo informativo, non è consulenza. Si aggiorna a fine mese. Verde sopra {STRONG}, rosso fino a {WEAK}. "
               "Backtest 2002-2026 senza costi (scripts/evaluate_score.py, 06/10/2026): i 5 migliori ribilanciati ogni mese "
               "14,6% l'anno con drawdown massimo −19%, S&P 500 11,2% e −51%. Il vantaggio è piccolo e sta più nel ridurre le perdite che nel rendimento. "
               "Entrare sopra 80 e uscire solo sotto 60 riduce i cambi di posizione del 40% ma rende 1,1 punti l'anno in meno.")



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
    lv = im.levels({k: load_indicator(im.AREA, k) for k in [*im.YAHOO, *im.FRED_SERIES]})
    if not lv.empty:
        rows = []
        for name, x, y, sign, book in im.RELATIONS:
            if x not in lv or y not in lv:
                continue
            c = im.rolling_corr(lv, x, y, im.NORM_WINDOW)
            cur, usual = (float(c.iloc[-1]) if not c.empty else math.nan), im.norm(c)
            rows.append((name, cur, usual, im.relation_state(cur, usual, sign), book))
        if rows:
            st.space("small")
            ui(relations_html(rows, f"{lv.index[-1]:%d/%m/%Y}"))
    st.caption("Posizionamento dei grandi operatori sui future: pagina **COT**.")


def cot_history_chart(s: pd.Series, lo: float, hi: float, mode: str) -> alt.LayerChart:
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



def page_cot(mode: str) -> None:
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
        st.altair_chart(cot_history_chart(s, window.quantile(0.1), window.quantile(0.9), mode),
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
            st.metric("Z-score 5 anni", f"{zscore(window):+.1f}", border=True,
                      help="Distanza dalla media degli ultimi 5 anni in deviazioni standard: oltre ±2 è raro.")
        comm = load_indicator("Mercati", f"cotc_{market}")
        if len(comm) > 1:
            cw = comm.tail(COT_WEEKS)
            corr = window.corr(cw)
            with st.container(horizontal=True):
                st.metric("Netto commercial", f"{comm.iloc[-1]:+.1f}%", f"{comm.iloc[-1] - comm.iloc[-2]:+.1f} pt", delta_color="off",
                          border=True, help="Long meno short di chi copre un'attività reale (produttori, utilizzatori, banche), "
                                            "in % dell'open interest.")
                st.metric("Commercial: percentile", f"{percentile_rank(cw):.0f}°", f"z {zscore(cw):+.1f}", delta_color="off",
                          delta_arrow="off", border=True, help="Percentile e z-score sugli ultimi 5 anni.")
            st.caption(f"Correlazione fra speculatori e commercial negli ultimi 5 anni: {corr:+.2f}. "
                       + ("I commercial sono quasi lo specchio degli speculatori: dicono la stessa cosa dall'altro lato."
                          if corr <= -0.9 else "Qui i commercial non sono solo lo specchio degli speculatori: guardali a parte."))

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
