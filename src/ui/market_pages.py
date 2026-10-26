"""Pagine del gruppo Mercati: Classifica, Allocazione, Mercati, COT report, Calendario; e la parte di Il mio paese
sulle classi di asset e la valuta (country_allocation)."""
import math

import altair as alt
import pandas as pd
import streamlit as st

from src.classify import allocation as al
from src.classify import intermarket as im
from src.classify.positioning import percentile_rank, zscore
from src.classify.rrg import GROUPS, MOMENTUM_WEEKS, TREND_WEEKS, quadrant, rrg, weekly_prices
from src.classify.score import HORIZON_MONTHS, PILLARS, UNIVERSE, hysteresis, pillars
from src.config import cot_guide
from src.config.sector_regime import sector_arrows
from src.data import cache
from src.data.fetch_cot import CONTRACTS, DISAGG_GROUPS, DISAGG_MARKETS, TFF_GROUPS, WEEKS as COT_WEEKS
from src.ui.cards import (
    calendar_html, cot_groups_html, currency_html, events_html, hero_html, label_phrase, month_it, ranking_html, relations_html,
    reliability_html,
    rrg_html, ucits_html, weights_html, why_text,
)
from src.ui.data import load_allocation, load_indicator, load_model, spark, ui
from src.ui.theme import hex_color

IMPACT_LABELS_IT = {"Alto": "High", "Medio": "Medium", "Basso": "Low", "Festivo": "Holiday"}


@st.cache_data
def load_events() -> list[dict]:
    return cache.read_events()



@st.cache_data
def load_weekly() -> tuple[pd.DataFrame, pd.Timestamp | None]:
    """Chiusure settimanali degli ETF (rotazione, src/classify/rrg.py) e data dell'ultima chiusura giornaliera."""
    daily = pd.DataFrame({t: load_indicator(im.AREA, t) for t in UNIVERSE})
    return (daily, None) if daily.empty else (weekly_prices(daily), daily.index[-1])



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
    m = load_model()
    px, s = m["px"], m["score"]
    if s.empty:
        st.info("Nessun prezzo degli asset in cache.", icon=":material/database:")
        st.stop()
    month, now = s.index[-1], s.iloc[-1].dropna().sort_values(ascending=False)
    prev = s.iloc[-2] if len(s) > 1 else pd.Series(dtype=float)
    trend = pillars(px)["Tendenza"].loc[month]
    active = hysteresis(s).iloc[-1]
    on = [UNIVERSE[t][0] for t in now.index if active[t]]
    ui(hero_html(f"Classifica asset · fine {month_it(month)}", "In testa: " + ", ".join(UNIVERSE[t][0] for t in now.index[:3]),
                 f"Punteggio 1-100 = posizione fra {len(now)} ETF per probabilità di battere la media degli asset nei "
                 f"{HORIZON_MONTHS} mesi dopo, stimata da cinque pilastri: {', '.join(PILLARS).lower()}. Segnale attivo "
                 f"(punteggio alto e stabile): <b>{', '.join(on) or 'nessuno'}</b>."))
    groups = ["Tutti", *dict.fromkeys(g for _, g in UNIVERSE.values())]
    group = st.segmented_control("Gruppo", groups, default="Tutti", required=True, key="group", label_visibility="collapsed")
    usa_regime = m["usa_regime"]
    arrows = sector_arrows(usa_regime)
    rows = [{"ticker": t, "nome": UNIVERSE[t][0], "gruppo": UNIVERSE[t][1], "punteggio": sc, "freccia": arrows.get(t),
             "delta": sc - prev[t] if pd.notna(prev.get(t)) else None, "Tendenza": trend[t], "prob": m["prob"].loc[month, t],
             "attivo": bool(active[t]), "storico": s[t], "perche": why_text({k: c.loc[month, t] for k, c in m["contrib"].items()})}
            for t, sc in now.items() if group == "Tutti" or UNIVERSE[t][1] == group]
    col_r, col_e = st.columns([8, 4])
    with col_r:
        sectors = group in ("Tutti", "Settori USA") and arrows
        ui(ranking_html(rows, month, note=reliability_html("ranking") + (reliability_html(
            "sector_regime", f"▲▼ accanto ai settori USA: regime USA di oggi, {label_phrase(usa_regime)} ({usa_regime}).")
            if sectors else "")))
    with col_e:
        ui(weights_html(m["weights"].iloc[-1][PILLARS].to_dict(), m["weights"].index[-1]))
        wk, last_day = load_weekly()
        if not wk.empty:
            rot = st.segmented_control("Rotazione", list(GROUPS), default="Settori USA", required=True, key="rot",
                                       label_visibility="collapsed")
            ratio, mom = (x.iloc[-1].dropna() for x in rrg(wk, GROUPS[rot], TREND_WEEKS, MOMENTUM_WEEKS))
            items = [{"ticker": t, "nome": UNIVERSE[t][0], "ratio": ratio[t], "momentum": mom[t], "quadrante": quadrant(ratio[t], mom[t])}
                     for t in ratio.index.intersection(mom.index)]
            if items:
                ui(rrg_html(items, f"Rotazione · {rot}", f"settimanale, al {last_day:%d/%m/%Y}"))
    with st.expander("Dall'Italia: equivalenti UCITS di questi ETF", icon=":material/euro:"):
        ui(ucits_html([r["ticker"] for r in rows], {t: n for t, (n, _) in UNIVERSE.items()}))
    st.caption("Solo informativo, non è consulenza. Si aggiorna a fine mese. Verde = parte alta della classifica, rosso = "
               "parte bassa. Verifica, soglie e cosa ha voluto dire ogni fascia di punteggio nella sezione Metodo.")



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
                 "sono tutti dalla stessa parte il mercato è <b>affollato</b>: basta poco per una ricopertura violenta.")
       + reliability_html("cot"))

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
                      selection_mode="single", required=True, label_visibility="collapsed") or next(iter(series))
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
            "- **Verificato qui.** Nella classifica delle valute (pagina Allocazione) il COT da solo non anticipa i 6 mesi dopo."
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


# Strumento d'esempio per classe di asset (solo nomi, non e' un consiglio): azioni = ETF del paese; per gli USA la
# pagina mostra anche i migliori della Classifica dentro la classe.
EXAMPLE = {"Obbligazioni": "Titoli di Stato decennali", "Liquidità": "Liquidità a 3 mesi", "Oro": "Oro (es. GLD)"}
CCY_NAMES = {"USD": "Dollaro USA", "EUR": "Euro", "GBP": "Sterlina", "JPY": "Yen", "CAD": "Dollaro canadese",
             "AUD": "Dollaro australiano", "CNY": "Renminbi", "INR": "Rupia indiana"}
CLASS_GROUPS = {"Azioni": ("Settori USA", "Indici USA"), "Obbligazioni": ("Obbligazioni",), "Oro": ("Materie prime",)}


def _alloc_rows(m: dict, key, names: dict, tickers: dict, gruppo: str, active: pd.Series | None) -> tuple[list[dict], pd.Timestamp]:
    """Righe per ranking_html dall'ultima riga con punteggio. key(month) -> etichetta di riga del mese."""
    s = m["score"].dropna(how="all")
    # ultimo mese con una riga per questa chiave: un paese con dati in ritardo non ha la riga del mese piu' recente
    month = max(mo for mo in al.months_of(s.index).unique() if key(mo) in s.index)
    before = key(month - pd.offsets.MonthBegin())
    now = s.loc[key(month)].dropna().sort_values(ascending=False)
    prev = s.loc[before] if before in s.index else pd.Series(dtype=float)
    w = m["weights"].iloc[-1]
    rows = []
    for item, sc in now.items():
        contrib = {k: m["feats"][k].loc[key(month), item] * w[k] for k in m["feats"]}
        hist = s.xs(key(month)[0], level=0)[item] if s.index.nlevels > 1 else s[item]
        rows.append({"item": item, "ticker": tickers.get(item, item), "nome": names.get(item, item), "gruppo": gruppo, "punteggio": sc,
                     "delta": sc - prev[item] if pd.notna(prev.get(item)) else None,
                     "Tendenza": m["raw"]["Tendenza"].loc[key(month), item], "prob": m["prob"].loc[key(month), item],
                     "attivo": bool(active is not None and active.get(item, False)), "storico": hist, "perche": why_text(contrib)})
    return rows, month


# Classifica dell'Allocazione -> lettura di src/config/reliability.py (etichetta coerente con al.EDGE: test in test_reliability)
ALLOC_READING = {"Paesi": "countries", "Classi di asset": "asset_classes", "Valute": "currencies"}


def _badge(name: str) -> str:
    return reliability_html(ALLOC_READING[name])


def country_allocation(area: str) -> str | None:
    """Pagina Il mio paese: classi di asset del paese (classifica verificata) e la sua valuta nella classifica delle
    valute (descrittiva, il punteggio scelto il 25/10/2026). Ritorna la classe in testa, None senza dati."""
    data = load_allocation()
    if not data:
        st.info("Nessun prezzo in cache per le classi di asset.", icon=":material/database:")
        return None
    cl, fx = data["Classi di asset"], data["Valute"]
    hold = hysteresis(cl["score"].xs(area, level=0).dropna(how="all"), al.ENTER, al.EXIT).iloc[-1]
    tickers = {"Azioni": al.COUNTRY_ETF[area], "Obbligazioni": "10Y", "Liquidità": "3M", "Oro": "XAU"}
    rows, month = _alloc_rows(cl, lambda mo: (area, mo), EXAMPLE | {"Azioni": f"Azioni {area}"}, tickers, area, hold)
    ui(ranking_html(rows, month, f"Classi di asset · {area}", al.HORIZON, _badge("Classi di asset")))
    cls = rows[0]["item"]
    if area == "USA" and cls in CLASS_GROUPS:
        s = load_model()["score"].iloc[-1].dropna().sort_values(ascending=False)
        pick = [t for t in s.index if UNIVERSE[t][1] in CLASS_GROUPS[cls]][:3]
        if pick:
            st.caption("Dentro la classe, i più alti della Classifica: "
                       + ", ".join(f"{UNIVERSE[t][0]} ({t}, {s[t]:.0f})" for t in pick) + ".")
    currencies, _ = _alloc_rows(fx, lambda mo: mo, CCY_NAMES, {}, "valuta", None)
    pos = next((i for i, r in enumerate(currencies, 1) if r["item"] == al.CCY[area]), None)
    if pos:
        ui(currency_html(currencies[pos - 1], pos, len(currencies), month, _badge("Valute")))
    return rows[0]["nome"]


def page_allocation() -> None:
    data = load_allocation()
    if not data:
        st.info("Nessun prezzo in cache.", icon=":material/database:")
        st.stop()
    pa, fx = data["Paesi"], data["Valute"]
    countries, month = _alloc_rows(pa, lambda mo: mo, {}, al.COUNTRY_ETF, "azioni", None)
    best = countries[0]["nome"]
    ui(hero_html(f"Allocazione di lungo periodo · fine {month_it(month)}", f"In testa: {best}",
                 "Per PAC e investimenti fissi, orizzonte 6-12 mesi. Punteggio 1-100 relativo: 50 = metà classifica, 90 = "
                 "meglio del 90% degli altri nello stesso mese, per probabilità di battere la media nei 6 mesi dopo. "
                 "Più peso a chi sta in alto, meno peso a chi sta in basso: sono vantaggi statistici storici, non certezze. "
                 "Le classi di asset di ogni paese sono nella pagina <b>Il mio paese</b>."))
    ui(ranking_html(countries, month, "Paesi", al.HORIZON, _badge("Paesi")))
    ui(ranking_html(_alloc_rows(fx, lambda mo: mo, CCY_NAMES, {}, "valuta", None)[0], month, "Valute", al.HORIZON, _badge("Valute")))
    st.caption("Solo informativo, non è consulenza. Si aggiorna a fine mese. Come è stata verificata nella sezione Metodo. "
               "Fonti: OCSE (fiducia, tassi), BIS (cambio reale), CFTC (COT), Kenneth French e ETF (borse), FRED (cambi), "
               "datahub (oro).")
