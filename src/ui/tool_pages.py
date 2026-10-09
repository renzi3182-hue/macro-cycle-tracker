"""Pagine strumenti senza dati di mercato: position sizing Monte Carlo e calcolatore di interesse."""
import altair as alt
import pandas as pd
import streamlit as st

from src.classify import interest, sizing
from src.ui.cards import hero_html
from src.ui.theme import hex_color


def _ui(html: str) -> None:
    st.html(f'<div class="si">{html}</div>')


def _eur(x: float) -> str:
    return f"€ {x:,.0f}".replace(",", ".")


def _pct(x: float, digits: int = 0) -> str:
    return f"{x * 100:.{digits}f}%".replace(".", ",")


def _chart(c: alt.Chart, mode: str, height: int = 320) -> alt.Chart:
    muted, line = hex_color(mode, "muted"), hex_color(mode, "line")
    return (c.properties(height=height, background="transparent")
            .configure_view(strokeWidth=0)
            .configure_axis(labelColor=muted, titleColor=muted, gridColor=line, domainColor=line, tickColor=line,
                            labelFont="DM Mono", titleFont="Plus Jakarta Sans", titleFontWeight=500)
            .configure_legend(labelColor=muted, titleColor=muted, orient="top", labelFont="Plus Jakarta Sans"))


@st.cache_data(ttl=3600, max_entries=32)
def _simulate(win_rate: float, reward_risk: float, risk: float, trades: int, runs: int, ruin: float):
    wins = sizing.outcomes(win_rate, trades, runs)
    paths = sizing.equity_paths(wins, risk, reward_risk)
    return (sizing.fan(paths), sizing.summary(paths, ruin), sizing.max_drawdown(paths),
            float(pd.Series(sizing.longest_losing_streak(wins)).quantile(0.95)), sizing.risk_table(wins, reward_risk, ruin))


def page_sizing(mode: str) -> None:
    _ui(hero_html("Gestione del rischio · Monte Carlo", "Quanto rischiare per trade",
                  "Simula migliaia di sequenze di trade con le tue statistiche e guarda cosa succede al conto: "
                  "crescita tipica, drawdown e probabilità di rovina per ogni livello di rischio."))
    with st.container(border=True):
        with st.container(horizontal=True, gap="medium"):
            capital = st.number_input("Capitale", 1000, 10_000_000, 10_000, step=1000, format="%d", icon=":material/euro:")
            win_rate = st.number_input("Trade vincenti %", 5.0, 95.0, 45.0, step=1.0, help="Quota storica di trade chiusi in guadagno.")
            reward_risk = st.number_input("Rendimento / rischio", 0.2, 10.0, 2.0, step=0.1,
                                          help="Guadagno medio di un trade vinto diviso la perdita media di un trade perso (R multiplo).")
            risk_pct = st.number_input("Rischio per trade %", 0.1, 25.0, 1.0, step=0.25,
                                       help="Quota del capitale persa se scatta lo stop.")
        with st.container(horizontal=True, gap="medium", vertical_alignment="bottom"):
            trades = st.slider("Numero di trade", 20, 1000, 200, step=10)
            ruin_pct = st.slider("Soglia di rovina (drawdown)", 10, 90, 50, step=5, format="%d%%",
                                 help="Perdita dal massimo oltre la quale consideri il conto compromesso.")
            runs = st.segmented_control("Simulazioni", [1000, 5000, 10000], default=5000, required=True,
                                        format_func=lambda n: f"{n:,}".replace(",", "."))

    w, rr, risk, ruin = win_rate / 100, reward_risk, risk_pct / 100, ruin_pct / 100
    fan, s, dd, streak95, table = _simulate(w, rr, risk, trades, runs, ruin)
    exp_r, k = sizing.expectancy(w, rr), sizing.kelly(w, rr)

    with st.container(horizontal=True):
        st.metric("Expectancy", f"{exp_r:+.2f} R".replace(".", ","), help="Guadagno medio per trade in multipli del rischio. Sotto zero il sistema perde.",
                  border=True)
        st.metric("Kelly", _pct(max(k, 0), 1), f"metà: {_pct(max(k, 0) / 2, 1)}", delta_color="off", delta_arrow="off",
                  help="Rischio per trade che massimizza la crescita attesa. In pratica si usa al massimo metà Kelly: "
                       "le statistiche reali sono incerte.", border=True)
        st.metric("Capitale mediano", _eur(capital * s["final"][50]), _pct(s["final"][50] - 1), border=True,
                  help=f"Metà delle simulazioni finisce sopra questo valore dopo {trades} trade.")
        st.metric("Caso cattivo (5%)", _eur(capital * s["final"][5]), _pct(s["final"][5] - 1), border=True,
                  help="1 simulazione su 20 finisce sotto questo valore.")
        st.metric("Prob. di rovina", _pct(s["p_ruin"], 1), border=True,
                  help=f"Simulazioni con un drawdown di almeno il {ruin_pct}%.")
        st.metric("Perdite di fila", f"{streak95:.0f}", border=True,
                  help="Striscia di perdite consecutive che il 5% delle simulazioni supera: preparati psicologicamente a vederla.")

    if exp_r <= 0:
        st.error("Expectancy negativa: con queste statistiche il sistema perde soldi e nessun size lo rende vincente. "
                 "Ridurre il rischio rallenta solo la perdita.", icon=":material/block:")
    elif risk > k:
        st.warning(f"Stai rischiando più del Kelly pieno ({_pct(k, 1)}): oltre quel livello rischiare di più fa crescere "
                   "meno il conto e aumenta molto i drawdown.", icon=":material/warning:")
    elif risk > k / 2:
        st.info(f"Rischio tra metà Kelly e Kelly pieno: crescita alta, drawdown profondi. Molti trader professionisti "
                f"restano sotto {_pct(k / 2, 1)}.", icon=":material/info:")
    else:
        st.success("Rischio sotto metà Kelly: zona prudente, il conto sopravvive anche a statistiche un po' peggiori del previsto.",
                   icon=":material/verified_user:")

    col_fan, col_dd = st.columns([3, 2])
    with col_fan, st.container(border=True):
        st.markdown("**Capitale dopo ogni trade**")
        f = fan.mul(capital).reset_index(names="trade")
        accent = hex_color(mode, "accent")
        base = alt.Chart(f).encode(x=alt.X("trade:Q", title="Trade"))
        chart = (base.mark_area(opacity=0.15, color=accent).encode(y=alt.Y("p5:Q", title="Capitale (€)", axis=alt.Axis(format="~s")), y2="p95:Q")
                 + base.mark_area(opacity=0.3, color=accent).encode(y="p25:Q", y2="p75:Q")
                 + base.mark_line(color=accent, strokeWidth=2.5).encode(
                     y="p50:Q", tooltip=[alt.Tooltip("trade:Q", title="Trade"), alt.Tooltip("p50:Q", title="Mediana", format=",.0f"),
                                         alt.Tooltip("p5:Q", title="5%", format=",.0f"), alt.Tooltip("p95:Q", title="95%", format=",.0f")]))
        st.altair_chart(_chart(chart, mode), alt="Ventaglio del capitale simulato: mediana, 50% e 90% centrali")
        st.caption("Linea: mediana. Banda scura: metà centrale delle simulazioni. Banda chiara: 90% centrale.")
    with col_dd, st.container(border=True):
        st.markdown("**Drawdown massimo**")
        d = pd.DataFrame({"dd": dd * 100})
        hist = alt.Chart(d).mark_bar(color=hex_color(mode, "r-stag"), cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
            x=alt.X("dd:Q", bin=alt.Bin(extent=[0, max(float(d["dd"].max()), ruin_pct) + 1], maxbins=40), title="Drawdown massimo (%)"),
            y=alt.Y("count():Q", title="Simulazioni"))
        rule = alt.Chart(pd.DataFrame({"x": [ruin_pct]})).mark_rule(color=hex_color(mode, "fg"), strokeDash=[4, 4]).encode(x="x:Q")
        st.altair_chart(_chart(hist + rule, mode), alt="Distribuzione del drawdown massimo delle simulazioni")
        st.caption(f"Mediana {_pct(s['dd_median'])}, 1 su 20 oltre {_pct(s['dd_p95'])}. Tratteggio: soglia di rovina.")

    with st.container(border=True):
        st.markdown("**Stesse statistiche, rischio diverso**")
        t = table.assign(**{c: table[c] * capital for c in ("Mediana", "Caso cattivo (5%)")})
        st.dataframe(t, hide_index=True, width="stretch", alt="Confronto fra livelli di rischio per trade", column_config={
            "Rischio %": st.column_config.NumberColumn(format="%.2f%%"),
            "Mediana": st.column_config.NumberColumn("Capitale mediano", format="€ %,.0f"),
            "Caso cattivo (5%)": st.column_config.NumberColumn(format="€ %,.0f"),
            "Drawdown mediano": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
            "Drawdown 95%": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
            "Prob. rovina": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
        })
    st.caption("Ipotesi: trade indipendenti, stesso esito medio, rischio ricalcolato sul capitale di ogni momento, niente costi. "
               "Nella realtà le perdite arrivano a grappoli: considera drawdown e strisce come un minimo. Solo didattico, non è consulenza.")


@st.cache_data(ttl=3600, max_entries=64)
def _schedule(*args) -> pd.DataFrame:
    return interest.schedule(*args)


PER_YEAR = {"Annuale": 1, "Trimestrale": 4, "Mensile": 12}


def page_interest(mode: str) -> None:
    _ui(hero_html("Calcolatore", "Interesse semplice e composto",
                  "Quanto diventano i tuoi risparmi nel tempo, con versamenti mensili, tasse e inflazione. "
                  "Il composto fa maturare interessi anche sugli interessi: la differenza esplode negli anni."))
    with st.container(border=True):
        with st.container(horizontal=True, gap="medium"):
            principal = st.number_input("Capitale iniziale", 0, 100_000_000, 10_000, step=1000, format="%d", icon=":material/euro:")
            monthly = st.number_input("Versamento mensile", 0, 1_000_000, 200, step=50, format="%d", icon=":material/euro:")
            rate = st.number_input("Rendimento annuo %", 0.0, 30.0, 5.0, step=0.25)
            years = st.slider("Anni", 1, 60, 20)
        with st.container(horizontal=True, gap="medium", vertical_alignment="bottom"):
            freq = st.segmented_control("Capitalizzazione", list(PER_YEAR), default="Annuale", required=True)
            tax = st.segmented_control("Tassa sugli interessi", [0.0, 12.5, 26.0], default=26.0, required=True,
                                       format_func=lambda x: "Nessuna" if x == 0 else f"{x:g}%".replace(".", ","),
                                       help="Italia: 26% su ETF e conti, 12,5% sui titoli di Stato.")
            inflation = st.number_input("Inflazione annua %", 0.0, 20.0, 2.0, step=0.25,
                                        help="Per il valore reale: quanto potere d'acquisto di oggi avrai.")

    df = _schedule(principal, monthly, rate, years, PER_YEAR[freq], inflation, tax)
    last = df.iloc[-1]
    doubling = interest.years_to_double(rate)
    with st.container(horizontal=True):
        st.metric("Valore finale (composto)", _eur(last["Composto"]), f"+{_eur(last['Composto'] - last['Semplice'])} vs semplice",
                  delta_arrow="off", border=True)
        st.metric("Totale versato", _eur(last["Versato"]), border=True)
        st.metric("Interessi composti", _eur(last["Interessi composto"]),
                  f"{last['Interessi composto'] / max(last['Composto'], 1) * 100:.0f}% del valore finale", delta_color="off",
                  delta_arrow="off", border=True)
        st.metric("Netto tasse, in euro di oggi", _eur(last["Composto netto reale"]), border=True,
                  help=f"Dopo la tassa del {tax:g}% sugli interessi e {inflation:g}% di inflazione l'anno.")
        st.metric("Anni per raddoppiare", "n/d" if doubling is None else f"{doubling:.1f}".replace(".", ","), border=True,
                  help="Solo capitale, interesse composto annuo, senza versamenti.")

    with st.container(border=True):
        st.markdown(f"**Crescita in {years} anni**")
        long = pd.concat([
            df[["Versato"]].rename(columns={"Versato": "v"}).assign(voce="Versato"),
            df[["Interessi composto"]].rename(columns={"Interessi composto": "v"}).assign(voce="Interessi composti"),
        ]).reset_index()
        colors = alt.Scale(domain=["Versato", "Interessi composti"], range=[hex_color(mode, "r-defl"), hex_color(mode, "accent")])
        area = alt.Chart(long).mark_area(opacity=0.85, interpolate="monotone").encode(
            x=alt.X("Anno:Q", title="Anni"), y=alt.Y("v:Q", stack=True, title="Valore (€)", axis=alt.Axis(format="~s")),
            color=alt.Color("voce:N", scale=colors, title=None), order=alt.Order("voce:N", sort="descending"),
            tooltip=[alt.Tooltip("Anno:Q"), alt.Tooltip("voce:N", title="Voce"), alt.Tooltip("v:Q", title="€", format=",.0f")])
        simple = alt.Chart(df.reset_index()).mark_line(color=hex_color(mode, "r-refl"), strokeDash=[6, 4], strokeWidth=2).encode(
            x="Anno:Q", y="Semplice:Q", tooltip=[alt.Tooltip("Anno:Q"), alt.Tooltip("Semplice:Q", title="Interesse semplice", format=",.0f")])
        st.altair_chart(_chart(area + simple, mode, 360), alt="Crescita del capitale: versato e interessi composti, linea dell'interesse semplice")
        st.caption("Area: versato + interessi composti. Tratteggio: stesso piano con interesse semplice.")

    with st.expander("Tabella anno per anno", icon=":material/table:"):
        st.dataframe(df[["Versato", "Semplice", "Composto", "Interessi composto", "Composto netto", "Composto netto reale"]],
                     width="stretch", alt="Valori anno per anno",
                     column_config={c: st.column_config.NumberColumn(format="€ %,.0f") for c in df.columns})
    st.caption("Rendimento costante ogni anno: nella realtà varia, e con le azioni l'ordine dei rendimenti conta. "
               "Tassa applicata sugli interessi alla fine, come per un ETF ad accumulazione venduto quel giorno. Solo didattico.")
