"""Export del sito statico (public/index.html, 27/10/2026): legge data/cache.db, compone le pagine con i blocchi HTML
di src/ui/cards.py e scrive un solo JSON che la pagina legge. Dal 28/10/2026 e' l'unica interfaccia: l'app Streamlit
e' stata tolta.

Quello che dipende da una scelta dell'utente diventa una variante: blocchi con data-when="nome=valore", la pagina
mostra quelli che corrispondono alla scelta. Grafici: segnaposto <div data-chart="chiave"> e serie in "charts". Lo
stress test del Portafoglio si ricalcola nel browser a ogni modifica: qui solo prezzi mensili, cambio e testi fissi.

Uso (da code/macro-cycle-tracker): python -m src.scheduler.export_site [percorso.json], predefinito public/data/site.json."""
import json
import math
import re
import sys
from collections import Counter
from html import escape
from pathlib import Path

import pandas as pd

from src.classify import changes
from src.classify.allocation import CCY, COUNTRY_ETF, ENTER, EXIT, HORIZON as AL_HORIZON
from src.classify import intermarket as im
from src.classify import opportunities as opp
from src.classify.assess import HIGH_FREQ_MAX_DAYS, label_regimes, stale_high_freq
from src.classify.leading import SIGNALS
from src.classify.positioning import percentile_rank, zscore
from src.classify.recession import sahm_gap
from src.classify.regime import monthly
from src.classify.risk import label as risk_label
from src.classify.rrg import GROUPS, MOMENTUM_WEEKS, TREND_WEEKS, quadrant, rrg
from src.classify.score import HORIZON_MONTHS, PILLARS, TREND_MONTHS, UNIVERSE, band_table, forward_excess, hysteresis, pillars
from src.classify.stress import EXTRA_ETF, MC_RUNS, MC_YEARS, PROXY, SCENARIOS, VAR_LEVEL
from src.config import cot_guide
from src.config.asset_allocation import (
    AREA_EQUITY, ASSET_ALLOCATION, CASH, TREND_PROXY, apply_trend, combined_portfolio_weights, confirmation,
)
from src.config.sector_regime import sector_arrows
from src.data import cache
from src.data.fetch_cot import CONTRACTS, DISAGG_GROUPS, DISAGG_MARKETS, TFF_GROUPS, WEEKS as COT_WEEKS
from src.ui.cards import (
    area_hero_html, axis_card_html, bands_html, calendar_html, cap, changes_html, cot_groups_html, currency_html, cycle_wave_html,
    events_html, freshness_html, gauge_html, hero_html, history_html, label_phrase, level_var, liquidity_html, monitor_html, month_it,
    opportunity_map_html, phase_bar_html, portfolio_html, prevailing_regime, pricing_html, prob_html, ranking_html, regimes_html,
    relations_html, reliability_html, reliability_table_html, risk_explain_html, risk_html, stat_tile_html,
    rrg_html, sector_regime_html, trend_chips_html, trend_html, ucits_html, weight_deltas, weights_html, why_text,
)
from src.ui.data import load_allocation, load_indicator, load_model, load_scores, load_usd_per_eur
from src.ui.shared import (
    CCY_NAMES, CLASS_GROUPS, EXAMPLE, IMPACT_LABELS_IT, _alloc_rows, _badge, load_weekly, upcoming_events, AREAS, INPUT_LABELS, LEADING_LABELS, RISK_PARTS, RISK_PROFILE_LABELS, RISK_SAY, STATIC_PORTFOLIOS, STRESS_ASSETS,
    describe, load_assessment, load_book_canary, load_liquidity, load_monitor, load_pricing, load_risk, trend_rows, trend_vs_hold,
)
from src.ui.theme import _CSS, DONUT_SLOTS, TOKENS, _WAVE_MASK, phase_color, regime_color

OUT = Path(__file__).resolve().parents[2] / "public" / "data" / "site.json"
CHART_YEARS = 20


# --- piccoli blocchi: metriche, scelte a pulsanti, sezioni apribili ---

def ui(html: str) -> str:
    return f'<div class="si">{html}</div>'


def md(text: str) -> str:
    """Markdown minimo dei testi dell'app: **grassetto**, `codice`, elenchi "- ", paragrafi separati da riga vuota."""
    def inline(s: str) -> str:
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escape(s, quote=False))
        return re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    out = []
    for block in text.strip().split("\n\n"):
        lines = block.split("\n")
        if all(line.startswith("- ") for line in lines):
            out.append("<ul>" + "".join(f"<li>{inline(line[2:])}</li>" for line in lines) + "</ul>")
        elif lines[0].startswith("#### "):
            out.append(f"<h3>{inline(lines[0][5:])}</h3>" + (f"<p>{inline(' '.join(lines[1:]))}</p>" if lines[1:] else ""))
        else:
            out.append(f"<p>{inline(' '.join(lines))}</p>")
    return "".join(out)


def caption(text: str) -> str:
    return f'<p class="cap">{md(text)[3:-4] if text else ""}</p>'


def notice(text: str, kind: str = "info") -> str:
    return f'<p class="notice {kind}">{escape(text)}</p>'


def details(summary: str, body: str, open_: bool = False) -> str:
    return f'<details class="box"{" open" if open_ else ""}><summary>{escape(summary)}</summary>{body}</details>'


def spark_svg(values: list[float] | None, area: bool = False) -> str:
    """Mini grafico SVG di una metrica."""
    if not values or len(values) < 3:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    pts = " ".join(f"{i / (len(values) - 1) * 100:.1f},{28 - (v - lo) / span * 26:.1f}" for i, v in enumerate(values))
    fill = f'<polygon points="0,30 {pts} 100,30" fill="var(--accent)" opacity=".15"/>' if area else ""
    return (f'<svg class="spark" viewBox="0 0 100 30" preserveAspectRatio="none" aria-hidden="true">{fill}'
            f'<polyline points="{pts}" fill="none" stroke="var(--accent)" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>')


def metric(label: str, value: str, delta: str | None = None, help: str = "", chart: list | None = None,
           delta_var: str | None = None, delta_note: str = "", area: bool = False) -> str:
    """Metrica con bordo, valore, variazione e mini grafico. delta_var: token colore del delta (None = grigio)."""
    color = f"var(--{delta_var})" if delta_var else "var(--muted)"
    d = (f'<span class="d" style="color:{color}">{escape(delta)}</span>' if delta else "") + (
        f'<span class="d">{escape(delta_note)}</span>' if delta_note else "")
    tip = f' title="{escape(help)}"' if help else ""
    return (f'<div class="metric"{tip}><span class="k">{escape(label)}{" ⓘ" if help else ""}</span>'
            f'<span class="v">{escape(value)}</span>{d}{spark_svg(chart, area)}</div>')


def metrics(items: list[str]) -> str:
    return f'<div class="metrics">{"".join(items)}</div>'


def spark(ser: pd.Series, n: int = 24) -> list[float] | None:
    return None if len(ser) < 3 else ser.tail(n).round(2).tolist()


def switch(name: str, options: list[str], default: str, labels: dict | None = None) -> str:
    """Scelta a pulsanti: la pagina mostra i blocchi data-when="name=valore"."""
    buttons = "".join(f'<button type="button" data-value="{escape(o)}">{escape((labels or {}).get(o, o))}</button>' for o in options)
    return f'<div class="seg" data-switch="{escape(name)}" data-default="{escape(default)}">{buttons}</div>'


def when(cond: str, html: str) -> str:
    return f'<div data-when="{escape(cond)}">{html}</div>'


def columns(*cols: tuple[int, str]) -> str:
    return f'<div class="cols" style="grid-template-columns:{" ".join(f"minmax(0,{w}fr)" for w, _ in cols)}">' + "".join(
        f"<div>{c}</div>" for _, c in cols) + "</div>"


def card(html: str) -> str:
    return f'<div class="si"><div class="card">{html}</div></div>'


def series_points(s: pd.Series, years: int = CHART_YEARS) -> list:
    s = s.dropna().loc[pd.Timestamp.today() - pd.DateOffset(years=years):]
    return [[d.strftime("%Y-%m-%d"), round(float(v), 2)] for d, v in s.items()]


def chart_div(key: str, series: dict[str, str]) -> str:
    """Legenda statica e segnaposto del grafico; series: etichetta -> token colore."""
    legend = "".join(f'<span class="chip"><i class="dot" style="background:var(--{tok})"></i>{escape(lb)}</span>'
                     for lb, tok in series.items())
    return f'<div class="si" style="display:flex;flex-wrap:wrap;gap:8px">{legend}</div><div class="lwc" data-chart="{escape(key)}"></div>'


# --- pagine ---

def page_today(ctx: dict) -> str:
    assessments = ctx["assessments"]
    phases = {area: a["phase"] for area, a in assessments.items()}
    top, n = Counter(phases.values()).most_common(1)[0]
    others = " · ".join(f"{k} {v}" for k, v in Counter(phases.values()).most_common()[1:])
    tiles = [stat_tile_html(
        "#paese", f"Ciclo economico · dati fino a {month_it(max(a['month'] for a in assessments.values()))}", n, len(phases),
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
    trend = pillars(px.drop(columns=EXTRA_ETF))["Tendenza"].iloc[-1].dropna() if not px.empty else px
    if not trend.empty and not sc.empty:
        up = int((trend > 0).sum())
        best = sc.iloc[-1].dropna().sort_values(ascending=False).head(3)
        tiles.append(stat_tile_html(
            "#asset", f"Tendenza degli asset · fine {month_it(px.index[-1])}", up, len(trend), "in salita", "var(--fg)",
            f'<div class="track"><i style="width:{up / len(trend):.0%};background:var(--accent)"></i></div>',
            "Più forti: " + escape(", ".join(UNIVERSE[t][0] for t in best.index)), "Verificato"))
    out = [ui(hero_html(f"Oggi · {pd.Timestamp.today():%d/%m/%Y}", "Il quadro di oggi",
                        "Tre numeri e cosa è cambiato dal mese scorso, poi tre livelli: cosa prezza il mercato, che guarda avanti, "
                        "il ciclo macro, che spiega il contesto, e la tendenza, l'unica regola che decide. Tocca una card per il dettaglio.")),
           ui('<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(240px,1fr))">' + "".join(tiles) + "</div>")]
    alloc = load_allocation()
    if not px.empty:
        names = {t: name for t, (name, _) in UNIVERSE.items()}
        rankings = {"Classifica asset": ("ranking", load_model()["prob"].rename(columns=lambda t: f"{names[t]} ({t})"))}
        if alloc:
            rankings = {"Paesi": ("countries", alloc["Paesi"]["prob"]),
                        "Classi di asset": ("asset_classes", changes.cells_by_month(alloc["Classi di asset"]["prob"], opp.CLASS_NAMES)),
                        **rankings}
        items = changes.summary({area: a["history"] for area, a in assessments.items()},
                                pillars(px.drop(columns=EXTRA_ETF))["Tendenza"], names, rankings)
        out.append(ui(changes_html(items, px.index[-1])))
        if items:
            out.append(details("Testo da copiare", f'<pre class="copy">{escape(chr(10).join(t for _, t in items))}</pre>'))
    out.append(section('1 · Cosa prezza il mercato', 'Tassi, credito, opzioni e futures guardano avanti e cambiano ogni giorno: dicono cosa si aspetta il mercato, non cosa fare.'))
    if rows := load_pricing():
        out.append(ui(pricing_html(rows)))
    if not risk.empty:
        out.append(ui('<span id="cosa-vuol-dire"></span>' + risk_explain_html(
            r["Punteggio"], state, f"{risk.index[-1]:%d/%m/%Y}", [(name, desc, r[col]) for col, name, desc in RISK_PARTS], alarm,
            load_book_canary())))
    out.append(section('2 · Ciclo macro', 'Crescita, inflazione e fase del ciclo per paese. Dati lenti e rivisti: spiegano il contesto, non decidono.'))
    out.append(ui('<div class="card"><span class="eyebrow">In che fase è ogni paese</span>' + reliability_html("phase")
                  + cycle_wave_html(phases) + "</div>"))
    out.append(ui(regimes_html(assessments)))
    if rows := load_liquidity(assessments.get("USA")):
        out.append(ui(liquidity_html(rows)))
    if (mon := load_monitor())[0]:
        out.append(ui(monitor_html(*mon)))
    out.append(section('3 · Tendenza: la regola che decide', "Prezzo contro la media a 10 mesi: l'unica regola dell'app che nel passato ha ridotto le perdite. Sotto, dove pesare di più dentro ogni paese."))
    if not px.empty:
        out.append(ui(trend_html(trend_rows(px), px.index[-1])))
        out.append(caption(trend_vs_hold(px) + " Per applicarlo alla tua allocazione: interruttore **Filtro di tendenza** nella pagina **Portafoglio**."))
    if alloc:
        cl = alloc["Classi di asset"]
        month, grid = opp.grid(cl["score"], cl["prob"], cl["raw"]["Tendenza"], phases)
        if grid:
            out.append(ui(opportunity_map_html(grid, opp.best(grid), phases, month)))
    out.append(caption("Solo informativo, non è consulenza finanziaria. Metodo e affidabilità nella sezione **Metodo**."))
    return "".join(out)


def section(title: str, lead: str) -> str:
    return ui(f'<h2 class="sec">{escape(title)}</h2><p class="note" style="font-size:15px">{lead}</p>')


def country_allocation(area: str) -> str:
    """Pagina Il mio paese: classi di asset del paese (classifica verificata) e la sua valuta nella classifica delle valute."""
    data = load_allocation()
    if not data:
        return notice("Nessun prezzo in cache per le classi di asset.")
    cl, fx = data["Classi di asset"], data["Valute"]
    hold = hysteresis(cl["score"].xs(area, level=0).dropna(how="all"), ENTER, EXIT).iloc[-1]
    tickers = {"Azioni": COUNTRY_ETF[area], "Obbligazioni": "10Y", "Liquidità": "3M", "Oro": "XAU"}
    rows, month = _alloc_rows(cl, lambda mo: (area, mo), EXAMPLE | {"Azioni": f"Azioni {area}"}, tickers, area, hold)
    out = [ui(ranking_html(rows, month, f"Classi di asset · {area}", AL_HORIZON, _badge("Classi di asset")))]
    cls = rows[0]["item"]
    if area == "USA" and cls in CLASS_GROUPS:
        s = load_model()["score"].iloc[-1].dropna().sort_values(ascending=False)
        pick = [t for t in s.index if UNIVERSE[t][1] in CLASS_GROUPS[cls]][:3]
        if pick:
            out.append(caption("Dentro la classe, i più alti della Classifica: "
                               + ", ".join(f"{UNIVERSE[t][0]} ({t}, {s[t]:.0f})" for t in pick) + "."))
    currencies, _ = _alloc_rows(fx, lambda mo: mo, CCY_NAMES, {}, "valuta", None)
    pos = next((i for i, r in enumerate(currencies, 1) if r["item"] == CCY[area]), None)
    if pos:
        out.append(ui(currency_html(currencies[pos - 1], pos, len(currencies), month, _badge("Valute"))))
    return "".join(out)


def page_area(area: str, ctx: dict) -> str:
    out = [ui(hero_html("Il mio paese", escape(area), "Cosa pesare di più dentro il paese, come sta la sua valuta e il quadro "
                        "macro: crescita, inflazione e fase del ciclo. Cambia paese qui sopra: il link resta sul paese scelto.")),
           section("Classi di asset e valuta", "Azioni, titoli di Stato, liquidità e oro del paese, in valuta locale, per "
                   "probabilità di rendere più delle altre nei 6 mesi dopo; poi la valuta fra le 8 dell'app."),
           country_allocation(area)]
    a = ctx["assessments"].get(area)
    if not a:
        return "".join(out) + notice("Nessun dato macro in cache per quest'area.")
    out.append(section("Il quadro macro", "Crescita e inflazione, fase del ciclo, indicatori anticipatori e dati usati."))
    if a["stale"]:
        out.append(notice("Dati in ritardo anomalo: " + ", ".join(INPUT_LABELS.get(n, n) for n in a["stale"])
                          + ". La fonte potrebbe aver cambiato dataset: la lettura è meno affidabile.", "warn"))
    px = load_scores()[0]
    above = {} if px.empty else (pillars(px)["Tendenza"].iloc[-1].dropna() > 0).to_dict()
    conf = confirmation(a["regime"], above, AREA_EQUITY.get(area))
    out.append(ui(area_hero_html(a, describe(a), (sum(up for *_, up in conf), len(conf)))))

    xg, xi = a["positions"]
    growth_src = a["growth_source"]
    gser = load_indicator(area, growth_src)
    gm = monthly(gser)
    g_change = gm.iloc[-1] - gm.iloc[-4] if len(gm) > 3 else 0.0
    out.append(ui(
        '<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(280px,1fr))">'
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
        + "</div>"))
    out.append(ui(history_html(a["history"])))

    risk = a["leading"]
    if risk:
        box = [ui(risk_html(risk["level"], risk["score"], risk["total"]))]
        items = []
        for label, key, _ in SIGNALS[area]:
            ser = load_indicator(area, key)
            on = risk["signals"][label]
            items.append(metric(LEADING_LABELS[key], "n/d" if ser.empty else f"{ser.iloc[-1]:.2f}", "attivo" if on else None,
                                f"Segnale: {label}." + ("" if ser.empty else f" Ultimo dato {ser.index[-1]:%m/%Y}."),
                                spark(ser), "r-stag" if on else None))
        box.append(metrics(items))
        box.append(caption("Segnali di stress su curva, credito e sentiment. Mostrati a parte: non cambiano regime né fase."))
        if area == "USA":
            unemployment, prob = load_indicator(area, "unemployment_rate"), load_indicator(area, "recession_prob")
            gap = sahm_gap(unemployment).dropna()
            if not gap.empty and not prob.empty:
                box.append(caption("Recessione in corso: " + ("**confermata** da disoccupazione e probabilità di recessione."
                                   if a["recession"] else "non confermata da disoccupazione e probabilità di recessione.")
                                   + " Regole e soglie nella sezione Metodo."))
            claims = load_indicator(area, "claims").rolling(4).mean().dropna()
            extra = [
                ("Sussidi (media 4 sett.)", claims / 1000, "{:.0f}k", 4, "Richieste iniziali di sussidi. In salita = lavoro più debole."),
                ("Permessi di costruzione", load_indicator(area, "permits"), "{:.0f}k", 1, "Migliaia, annualizzati. Anticipano l'edilizia."),
                ("Philly Fed manif.", load_indicator(area, "philly_fed"), "{:.1f}", 1, "Proxy dell'ISM: sotto 0 = contrazione."),
                ("GDPNow", load_indicator(area, "gdpnow"), "{:.1f}%", 1, "Stima Atlanta Fed del PIL del trimestre, % t/t annualizzata."),
            ]
            box.append(details("Altri indicatori USA (informativi)", metrics([
                metric(label, "n/d" if ser.empty else fmt.format(ser.iloc[-1]),
                       f"{ser.iloc[-1] - ser.iloc[-1 - lag]:+.1f}" if len(ser) > lag else None, tip, spark(ser))
                for label, ser, fmt, lag, tip in extra])))
        out.append(f'<div class="box">{"".join(box)}</div>')

    growth, inflation, unemployment = (load_indicator(area, n) for n in ("growth_yoy", "inflation_yoy", "unemployment_rate"))
    lines = {k: v for k, v in {"PIL annuo %": (growth, "r-gold"), "Inflazione annua %": (inflation, "r-stag"),
                               "Disoccupazione %": (unemployment, "r-defl")}.items() if not v[0].empty}
    key = f"area-{area}"
    ctx["charts"][key] = {"height": 300, "series": [{"label": lb, "tok": tok, "data": series_points(s)} for lb, (s, tok) in lines.items()]}
    out.append(f'<div class="box"><b>Crescita, inflazione, disoccupazione</b>{chart_div(key, {lb: tok for lb, (_, tok) in lines.items()})}</div>')

    trend = {asset: (t, up) for asset, t, up in conf}
    items = [(f"{asset} · {trend[asset][0]}" if asset in trend else asset, trend[asset][1] if asset in trend else None)
             for asset in ASSET_ALLOCATION.get(a["regime"], [])]
    out.append(columns(
        (1, ui(freshness_html([(INPUT_LABELS[n], d, n in a["stale"]) for n, d in a["as_of"].items()]))),
        (1, ui(f'<div class="card"><div class="head"><h3>Asset tipici quando {escape(label_phrase(a["regime"]))}</h3>'
               f'<span class="note">regime {escape(a["regime"])}</span></div>{reliability_html("regime_assets")}{trend_chips_html(items)}'
               f'{reliability_html("confirmation")}'
               '<p class="note">Verde = ETF sopra la media a 10 mesi (fine mese), rosso = sotto, grigio = senza ETF.</p></div>'))))
    return "".join(out)


def page_ranking() -> str:
    m = load_model()
    px, s = m["px"], m["score"]
    if s.empty:
        return notice("Nessun prezzo degli asset in cache.")
    month, now = s.index[-1], s.iloc[-1].dropna().sort_values(ascending=False)
    prev = s.iloc[-2] if len(s) > 1 else pd.Series(dtype=float)
    trend = pillars(px)["Tendenza"].loc[month]
    active = hysteresis(s).iloc[-1]
    on = [UNIVERSE[t][0] for t in now.index if active[t]]
    out = [ui(hero_html(f"Classifica asset · fine {month_it(month)}", "In testa: " + ", ".join(UNIVERSE[t][0] for t in now.index[:3]),
                        f"Punteggio 1-100 = posizione fra {len(now)} ETF per probabilità di battere la media degli asset nei "
                        f"{HORIZON_MONTHS} mesi dopo, stimata da cinque pilastri: {', '.join(PILLARS).lower()}. Segnale attivo "
                        f"(punteggio alto e stabile): <b>{', '.join(on) or 'nessuno'}</b>."))]
    groups = ["Tutti", *dict.fromkeys(g for _, g in UNIVERSE.values())]
    out.append(switch("group", groups, "Tutti"))
    usa_regime = m["usa_regime"]
    arrows = sector_arrows(usa_regime)
    left, ucits = [], []
    for group in groups:
        rows = [{"ticker": t, "nome": UNIVERSE[t][0], "gruppo": UNIVERSE[t][1], "punteggio": sc, "freccia": arrows.get(t),
                 "delta": sc - prev[t] if pd.notna(prev.get(t)) else None, "Tendenza": trend[t], "prob": m["prob"].loc[month, t],
                 "attivo": bool(active[t]), "storico": s[t],
                 "perche": why_text({k: c.loc[month, t] for k, c in m["contrib"].items()})}
                for t, sc in now.items() if group == "Tutti" or UNIVERSE[t][1] == group]
        sectors = group in ("Tutti", "Settori USA") and arrows
        left.append(when(f"group={group}", ui(ranking_html(rows, month, note=reliability_html("ranking") + (reliability_html(
            "sector_regime", f"▲▼ accanto ai settori USA: regime USA di oggi, {label_phrase(usa_regime)} ({usa_regime}).")
            if sectors else "")))))
        ucits.append(when(f"group={group}", ucits_html([r["ticker"] for r in rows], {t: n for t, (n, _) in UNIVERSE.items()})))
    right = [ui(weights_html(m["weights"].iloc[-1][PILLARS].to_dict(), m["weights"].index[-1]))]
    wk, last_day = load_weekly()
    if not wk.empty:
        right.append(switch("rot", list(GROUPS), "Settori USA"))
        for rot in GROUPS:
            ratio, mom = (x.iloc[-1].dropna() for x in rrg(wk, GROUPS[rot], TREND_WEEKS, MOMENTUM_WEEKS))
            items = [{"ticker": t, "nome": UNIVERSE[t][0], "ratio": ratio[t], "momentum": mom[t], "quadrante": quadrant(ratio[t], mom[t])}
                     for t in ratio.index.intersection(mom.index)]
            if items:
                right.append(when(f"rot={rot}", ui(rrg_html(items, f"Rotazione · {rot}", f"settimanale, al {last_day:%d/%m/%Y}"))))
    out.append(columns((8, "".join(left)), (4, "".join(right))))
    out.append(when("group=Tutti", ui(sector_regime_html(usa_regime))) + when("group=Settori USA", ui(sector_regime_html(usa_regime))))
    out.append(details("Dall'Italia: equivalenti UCITS di questi ETF", ui("".join(ucits))))
    out.append(caption("Solo informativo, non è consulenza. Si aggiorna a fine mese. Verde = parte alta della classifica, rosso = "
                       "parte bassa. Verifica, soglie e cosa ha voluto dire ogni fascia di punteggio nella sezione Metodo."))
    return "".join(out)


def page_portfolio(ctx: dict) -> tuple[str, dict]:
    """HTML delle varianti (profilo x filtro) e dati per lo stress test calcolato nel browser."""
    assessments = ctx["assessments"]
    regimes = {area: a["regime_label"] for area, a in assessments.items()}
    uncertain = [area for area, label in regimes.items() if len(label_regimes(label)) > 1]
    top, n = prevailing_regime(regimes)
    profiles = ["Basso", "Medio", "Alto", *STATIC_PORTFOLIOS]
    out = [ui(hero_html("Portafoglio multi-area", f'<span style="color:{regime_color(top)}">{escape(cap(label_phrase(top)))}</span>',
                        f"La situazione più comune, in {n} aree su {len(regimes)}: regime prevalente <b>{escape(top)}</b>. "
                        + ("Incerto = un asse è vicino alla soglia, quindi conta per metà in ciascuno dei due regimi. "
                           if len(label_regimes(top)) > 1 else "")
                        + "Media equipesata dei portafogli per regime di ogni area.")),
           '<p class="lbl">Profilo o portafoglio pigro</p>' + switch("risk", profiles, "Medio")]
    px, _ = load_scores()
    trend = pillars(px)["Tendenza"].iloc[-1].dropna() if len(px) else pd.Series(dtype=float)
    out.append('<label class="toggle"><input type="checkbox" data-switch="trend"' + (" disabled" if trend.empty else "")
               + '> Filtro di tendenza: in cash gli asset sotto la media a 10 mesi</label>')
    prev = {}
    for area, a in assessments.items():
        changed = a["history"]["regime"][a["history"]["regime"] != a["regime"]]
        prev[area] = changed.iloc[-1] if not changed.empty else a["regime"]
    bases = {}
    for profile in profiles:
        if profile in STATIC_PORTFOLIOS:
            weights, deltas = STATIC_PORTFOLIOS[profile], None
        else:
            weights = combined_portfolio_weights(regimes, profile)
            deltas = weight_deltas(weights, combined_portfolio_weights(prev, profile))
        bases[profile] = {k: round(w, 1) for k, w in weights.items()}
        side = notice("Nessun prezzo degli ETF in cache per il filtro di tendenza.") if trend.empty else ui(trend_html(
            trend_rows(px, {TREND_PROXY[a]: a for a in sorted(weights, key=weights.get, reverse=True) if a in TREND_PROXY}), px.index[-1]))
        for use_trend in (0, 1):
            w, d, note = weights, deltas, "vs regimi precedenti"
            if use_trend:
                w = apply_trend(weights, (trend > 0).to_dict())
                d, note = weight_deltas(w, weights), "vs senza filtro"
            main = ui(portfolio_html(w, d, "Allocazione", RISK_PROFILE_LABELS.get(profile, "pesi statici"), note,
                                     "" if profile in STATIC_PORTFOLIOS else reliability_html("regime_assets")))
            if uncertain and profile not in STATIC_PORTFOLIOS:
                main += caption(f"Aree incerte ({', '.join(uncertain)}): un asse è vicino alla soglia, quindi metà pesi a "
                                "ciascuno dei due regimi possibili.")
            out.append(when(f"risk={profile};trend={use_trend}", columns((8, main), (4, side))))
    if not px.empty:
        out.append('<div id="lab"></div>')
    out.append(caption("Dentro ogni regime la quota azionaria segue il profilo (Basso 30%, Medio 50%, Alto 70%). "
                       "Solo informativo, non è consulenza: il backtest non mostra un vantaggio sui portafogli statici (sezione Metodo)."))
    return "".join(out), stress_data(px, bases)


def stress_data(px: pd.DataFrame, bases: dict) -> dict:
    """Tutto quello che serve a public/index.html per rifare stress.py nel browser."""
    tickers = sorted({*PROXY.values(), "SPY"})
    p = px[tickers]
    names = {t: a for a, t in PROXY.items()}
    empty = ucits_html([], names)
    head_end = empty.index("</tr>") + len("</tr>")
    rows = {}
    for t in tickers:
        h = ucits_html([t], names)
        rows[t] = h[head_end:h.index("</table>")]
    usd = load_usd_per_eur().reindex(p.index)
    nums = lambda s: [None if pd.isna(v) else round(float(v), 6) for v in s]
    return {
        "months": [d.strftime("%Y-%m") for d in p.index], "px": {t: nums(p[t]) for t in tickers}, "usd_per_eur": nums(usd),
        "proxy": PROXY, "cash": PROXY[CASH], "trend_months": TREND_MONTHS, "mc": {"years": MC_YEARS, "runs": MC_RUNS}, "var_level": VAR_LEVEL,
        "scenarios": [[name, f"{month_it(pd.Timestamp(a), True)} – {month_it(pd.Timestamp(b), True)}", a, b]
                      for name, (a, b) in SCENARIOS.items()],
        "assets": STRESS_ASSETS, "bases": bases,
        "ucits": {"head": empty[:head_end], "tail": empty[empty.index("</table>"):], "rows": rows},
    }


def page_method() -> str:
    out = [ui(hero_html("Metodo", "Come leggere i regimi", "Regole semplici e pubbliche, verificate sui dati come erano disponibili al momento. "
                        "Ogni lettura dell'app ha un'etichetta: <b>Verificato</b>, <b>Teoria</b> o <b>Descrittivo</b>. Qui i numeri.")),
           ui(reliability_table_html())]
    m = load_model()
    if not m["score"].empty:
        s = m["score"]
        out.append(ui(bands_html(band_table(s, forward_excess(m["px"], s)), HORIZON_MONTHS, s.index[0])))
    regime = (
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
        "la produzione industriale mensile la anticipa davvero."
    )
    grid = ('<div class="tbl"><table class="mtx ucits"><tr><th></th><th>Inflazione in rallentamento</th><th>Inflazione in accelerazione</th></tr>'
            "<tr><td><b>Crescita in accelerazione</b></td><td>Goldilocks</td><td>Reflazione</td></tr>"
            "<tr><td><b>Crescita in rallentamento</b></td><td>Deflazione</td><td>Stagflazione</td></tr></table></div>")
    cycle = (
        "#### Fase del ciclo\n"
        "Momentum = direzione a 3 mesi del leading indicator OCSE (CLI), con conferma di 2 mesi.\n\n"
        "- **Espansione**: CLI in salita e PIL annuo sopra la sua media di 10 anni.\n"
        "- **Ripresa (sotto trend)**: CLI in salita con PIL ancora sotto il trend, o dopo una recessione.\n"
        "- **Rallentamento**: CLI in calo, senza conferme di recessione.\n"
        "- **Recessione**: solo con conferma dai dati: regola di Sahm sulla disoccupazione "
        "(negli USA confermata dalla probabilità Chauvet-Piger) oppure PIL annuo negativo.\n\n"
        "Gli **indicatori anticipatori** (curva, spread, sentiment) sono mostrati a parte e non cambiano la fase."
    )
    out.append(columns((1, f'<div class="box prose">{md(regime)}{ui(grid)}</div>'), (1, f'<div class="box prose">{md(cycle)}</div>')))
    rel = [
        ("USA", "44%", "3,6", "NBER: 100% dei mesi di recessione in Rallentamento o Recessione, Recessione fuori 1%"),
        ("Eurozona", "56%", "3,1", "OCSE: 86% dentro, 19% fuori"),
        ("Italia", "49%", "3,2", "OCSE: 80% dentro, 28% fuori"),
        ("UK", "57%", "2,5", "OCSE: 51% dentro, 45% fuori (debole)"),
        ("Giappone", "45%", "3,5", "OCSE: 66% dentro, 16% fuori"),
        ("Canada", "44%", "3,8", "OCSE: 74% dentro, 38% fuori"),
        ("Cina", "43%", "3,6", "OCSE: 72% dentro, 30% fuori (dati meno affidabili)"),
        ("Australia", "46%", "3,4", "OCSE: 48% dentro, 66% fuori (debole)"),
        ("India", "41%", "4,4", "OCSE: 92% dentro, 25% fuori"),
    ]
    table = ('<div class="tbl"><table class="mtx ucits"><tr><th>Area</th><th>Regime: tempo reale = storico</th>'
             '<th>Cambi di regime/anno</th><th>Ciclo vs riferimento</th></tr>'
             + "".join(f"<tr><td><b>{a}</b></td><td>{r}</td><td>{c}</td><td>{v}</td></tr>" for a, r, c, v in rel) + "</table></div>")
    # numeri da scripts/evaluate_model.py, riga "Letture di riferimento" (25/10/2026)
    out.append(f'<div class="box prose">{md("#### Affidabilità, dal 2000 (`scripts/evaluate_model.py`, 25/10/2026)")}{ui(table)}'
               + caption(
                   "Tempo reale = con i ritardi di pubblicazione veri (inflazione 1 mese, PIL 4): il PIL del trimestre si "
                   "conosce tardi e viene rivisto, per questo la lettura del momento coincide con quella a posteriori circa "
                   "1 mese su 2. Nel Regno Unito il ciclo è poco preciso; il regime non prevede i rendimenti futuri.")
               + md("**Letture note**: su 29 trimestri con un regime già documentato (2015-2026: USA, Eurozona, Cina e altre aree) "
                    "il modello ne riproduce **18**. La regola segue una definizione fissa (solo la direzione di crescita e "
                    "inflazione), non tarata su queste letture: è un controllo di coerenza, non una prova. Riproduce 9 delle 13 "
                    "letture 2023-2024 e 1 delle 5 del 3° trimestre 2026.") + "</div>")
    return "".join(out)


def page_cot(ctx: dict) -> str:
    series = {m: load_indicator("Mercati", f"cot_{m}") for m in CONTRACTS}
    series = {m: s for m, s in series.items() if len(s) > 1}
    if not series:
        return notice("Nessun dato COT in cache.")
    last = max(s.index[-1] for s in series.values())
    out = [ui(hero_html(f"COT report · CFTC, dato del {last:%d/%m/%Y}", "Chi è posizionato dove",
                        "Ogni venerdì la CFTC pubblica le posizioni sui future al martedì precedente. Quando gli speculatori "
                        "sono tutti dalla stessa parte il mercato è <b>affollato</b>: basta poco per una ricopertura violenta.")
              + reliability_html("cot"))]
    stats = {}
    for m, s in series.items():
        pct = percentile_rank(s.tail(COT_WEEKS))
        stats[m] = (s.iloc[-1], s.iloc[-1] - s.iloc[-2], pct, *cot_guide.crowding(pct))
    colors = {"red": "r-stag", "blue": "r-defl", "green": "r-gold", "orange": "r-refl", "violet": "r-defl", "gray": None}
    out.append(metrics([metric(m, f"{net:+.1f}%", label, f"Speculatori long meno short in % dell'open interest. "
                               f"Variazione settimana: {chg:+.1f} punti.", spark(series[m], 52), colors.get(color), f"{pct:.0f}° percentile", True)
                        for m, (net, chg, pct, label, color) in stats.items()]))
    out.append(switch("cot_market", list(series), next(iter(series))))
    for market, s in series.items():
        net, chg, pct, label, color = stats[market]
        what, reading = cot_guide.MARKET_INFO[market]
        window = s.tail(COT_WEEKS)
        key = f"cot-{market}"
        ctx["charts"][key] = {"height": 300, "series": [{"label": "Netto speculatori (% open interest)", "tok": "accent", "type": "area",
                                                          "data": series_points(window, 100)}],
                              "lines": [{"value": round(float(window.quantile(0.1)), 2), "tok": "r-defl", "title": "10° percentile"},
                                        {"value": round(float(window.quantile(0.9)), 2), "tok": "r-stag", "title": "90° percentile"},
                                        {"value": 0, "tok": "muted", "title": ""}]}
        tok = colors.get(color) or "muted"
        left = (f'<div class="box"><div class="si" style="display:flex;align-items:center;gap:12px;flex-wrap:wrap"><h3 class="h">{escape(market)}</h3>'
                f'<span class="chip tint" style="--c:var(--{tok})">{escape(label)}</span></div>{caption(what)}'
                f'<div class="lwc" data-chart="{escape(key)}"></div>'
                + caption("Sopra la linea rossa: più long del 90% delle settimane degli ultimi 5 anni. Sotto la blu: più short del 90%.") + "</div>")
        right = [f'<div class="box prose"><p><b>Cosa implica oggi</b></p>{md(cot_guide.implication(market, pct, chg))}'
                 f'{md(f"**Come si legge su questo mercato.** {reading}")}</div>',
                 metrics([metric("Netto speculatori", f"{net:+.1f}%", f"{chg:+.1f} pt", "Long meno short dei non-commercial, in % dell'open interest."),
                          metric("Percentile 5 anni", f"{pct:.0f}°", help="Quota di settimane degli ultimi 5 anni con un netto più basso di oggi."),
                          metric("Z-score 5 anni", f"{zscore(window):+.1f}", help="Distanza dalla media degli ultimi 5 anni in deviazioni standard: oltre ±2 è raro.")])]
        comm = load_indicator("Mercati", f"cotc_{market}")
        if len(comm) > 1:
            cw = comm.tail(COT_WEEKS)
            corr = window.corr(cw)
            right.append(metrics([
                metric("Netto commercial", f"{comm.iloc[-1]:+.1f}%", f"{comm.iloc[-1] - comm.iloc[-2]:+.1f} pt",
                       "Long meno short di chi copre un'attività reale (produttori, utilizzatori, banche), in % dell'open interest."),
                metric("Commercial: percentile", f"{percentile_rank(cw):.0f}°", f"z {zscore(cw):+.1f}", "Percentile e z-score sugli ultimi 5 anni.")]))
            right.append(caption(f"Correlazione fra speculatori e commercial negli ultimi 5 anni: {corr:+.2f}. "
                                 + ("I commercial sono quasi lo specchio degli speculatori: dicono la stessa cosa dall'altro lato."
                                    if corr <= -0.9 else "Qui i commercial non sono solo lo specchio degli speculatori: guardali a parte.")))
        groups = DISAGG_GROUPS if market in DISAGG_MARKETS else TFF_GROUPS
        rows, gdate = [], None
        for group in groups:
            g = load_indicator("Mercati", f"cotg_{market}_{group}")
            if len(g) < 2:
                continue
            rows.append({"Categoria": group, "Netto": g.iloc[-1], "Variazione": g.iloc[-1] - g.iloc[-2],
                         "Percentile": round(percentile_rank(g.tail(COT_WEEKS)))})
            gdate = g.index[-1]
        info = (f'<div class="box prose"><p><b>Le categorie nel report {"Disaggregated" if market in DISAGG_MARKETS else "Traders in Financial Futures"}</b></p>'
                + "".join(md(f"**{group}** · {cot_guide.GROUP_INFO[group][0]} {cot_guide.GROUP_INFO[group][1]}") for group in groups) + "</div>")
        out.append(when(f"cot_market={market}", columns((7, left), (5, "".join(right)))
                        + columns((7, ui(cot_groups_html(market, rows, f"{gdate:%d/%m}")) if rows else ""), (5, info))))
    out.append(details("Come usare il COT", f'<div class="prose">{md(
        "- **È contesto, non timing.** Un mercato può restare affollato per mesi mentre il trend continua: "
        "l'estremo dice dove sta il rischio, non quando arriva.\n"
        "- **Guarda chi muove.** Hedge fund e managed money seguono il trend e sono i primi a chiudere; asset manager e "
        "produttori si muovono piano e per motivi strutturali (coperture, mandati).\n"
        "- **Cerca le divergenze.** Prezzo ai massimi con speculatori che riducono il long = rally meno sostenuto.\n"
        "- **Ritardo di 3 giorni.** Il dato è del martedì e esce il venerdì: nelle settimane volatili è già vecchio.\n"
        "- **Verificato qui.** Nella classifica delle valute (pagina Allocazione) il COT da solo non anticipa i 6 mesi dopo.")}</div>'))
    out.append(caption("Fonte: CFTC (Legacy per gli speculatori, TFF e Disaggregated per le categorie). Solo informativo, non è consulenza."))
    return "".join(out)


def page_calendar() -> str:
    events = cache.read_events()
    if not events:
        return notice("Nessun evento in cache.")
    currencies = sorted({e["country"] for e in events})
    picked = [c for c in ("USD", "EUR", "GBP", "JPY") if c in currencies]
    # filtri a scelta multipla: li applica la pagina sulle righe (data-ccy, data-impact di calendar_html)
    out = [f'<div class="seg multi" data-filter="ccy" data-default="{",".join(picked)}">'
           + "".join(f'<button type="button" data-value="{escape(c)}">{escape(c)}</button>' for c in currencies) + "</div> "
           + '<div class="seg multi" data-filter="impact" data-default="Alto,Medio">'
           + "".join(f'<button type="button" data-value="{i}">{i}</button>' for i in IMPACT_LABELS_IT) + "</div>",
           f'<div id="calendar">{ui(calendar_html(events))}</div>',
           caption("Solo informativo. Fonte: feed pubblico non ufficiale del calendario Forex Factory, settimana in corso, orari di Roma. "
                   "Atteso = consenso, prec. = dato precedente.")]
    return "".join(out)


def page_markets() -> str:
    out = [caption("Solo informativo: non entra nella classificazione.")]
    items = []
    for label, (ser_area, key), fmt in [
        ("VIX", ("Mercati", "vix"), "{:.1f}"), ("MOVE (vol. Treasury)", ("Mercati", "move"), "{:.1f}"),
        ("Prob. recessione USA", ("USA", "recession_prob"), "{:.2f}%"),
        ("Inflazione attesa 5Y", ("Mercati", "breakeven_5y"), "{:.2f}%"), ("Inflazione attesa 5Y5Y", ("Mercati", "breakeven_5y5y"), "{:.2f}%"),
    ]:
        ser = load_indicator(ser_area, key)
        items.append(metric(label, "n/d") if ser.empty else metric(
            label, fmt.format(ser.iloc[-1]), f"{ser.iloc[-1] - ser.iloc[-2]:+.2f}" if len(ser) > 1 else None,
            chart=spark(ser, 60), delta_note="vs rilev. prec."))
    out.append(metrics(items))
    out.append(ui(events_html(upcoming_events())))
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
            out.append(ui(relations_html(rows, f"{lv.index[-1]:%d/%m/%Y}")))
    out.append(caption("Posizionamento dei grandi operatori sui future: pagina **COT**."))
    return "".join(out)


def page_allocation() -> str:
    data = load_allocation()
    if not data:
        return notice("Nessun prezzo in cache.")
    pa, fx = data["Paesi"], data["Valute"]
    countries, month = _alloc_rows(pa, lambda mo: mo, {}, COUNTRY_ETF, "azioni", None)
    best = countries[0]["nome"]
    return "".join([
        ui(hero_html(f"Allocazione di lungo periodo · fine {month_it(month)}", f"In testa: {best}",
                     "Per PAC e investimenti fissi, orizzonte 6-12 mesi. Punteggio 1-100 relativo: 50 = metà classifica, 90 = "
                     "meglio del 90% degli altri nello stesso mese, per probabilità di battere la media nei 6 mesi dopo. "
                     "Più peso a chi sta in alto, meno peso a chi sta in basso: sono vantaggi statistici storici, non certezze. "
                     "Le classi di asset di ogni paese sono nella pagina <b>Il mio paese</b>.")),
        ui(ranking_html(countries, month, "Paesi", AL_HORIZON, _badge("Paesi"))),
        ui(ranking_html(_alloc_rows(fx, lambda mo: mo, CCY_NAMES, {}, "valuta", None)[0], month, "Valute", AL_HORIZON, _badge("Valute"))),
        caption("Solo informativo, non è consulenza. Si aggiorna a fine mese. Come è stata verificata nella sezione Metodo. "
                "Fonti: OCSE (fiducia, tassi), BIS (cambio reale), CFTC (COT), Kenneth French e ETF (borse), FRED (cambi), "
                "datahub (oro)."),
    ])


def warnings_html() -> str:
    """Avvisi in testa a ogni pagina: serie FRED ferme e fetch falliti."""
    out = []
    late = stale_high_freq({k: (s.index[-1] if not (s := load_indicator(*k)).empty else None) for k in HIGH_FREQ_MAX_DAYS})
    if late:
        out.append(notice("Serie giornaliere/settimanali ferme: " + ", ".join(f"{k[1]} ({k[0]})" for k in late)
                          + ". Possibile problema di aggiornamento.", "warn"))
    failures = json.loads(cache.read_meta("fetch_failures") or "[]")
    if failures:
        out.append(notice("Fetch falliti nell'ultimo aggiornamento: " + ", ".join(
            f'{f["indicator"]} ({f["area"]}, {pd.Timestamp(f["time"]):%H:%M}) — {f["message"]}' for f in failures
        ) + ". Tengo i dati in cache.", "warn"))
    return "".join(out)


def css() -> str:
    """CSS dei blocchi di cards.py con i token chiari e scuri."""
    var = lambda mode: " ".join(f"--{k}: {v};" for k, v in TOKENS[mode].items())
    tips = "\n".join(f".si .donut:has(.s{i}:hover) .c.t{i} {{ display: flex; }}" for i in range(DONUT_SLOTS))
    return (f":root {{ {var('dark')} color-scheme: dark; }}\n@media (prefers-color-scheme: light) {{ :root {{ {var('light')} color-scheme: light; }} }}\n"
            + _CSS.replace("__DONUT_TIPS__", tips).replace("__WAVE__", _WAVE_MASK))


def build() -> dict:
    ctx = {"assessments": {area: a for area in AREAS if (a := load_assessment(area))}, "charts": {}}
    if not ctx["assessments"]:
        raise SystemExit("Nessun dato in cache: esegui prima python -m src.scheduler.update_data")
    areas = list(AREAS)
    paese = switch("area", areas, "USA") + "".join(when(f"area={a}", page_area(a, ctx)) for a in areas)
    portfolio, stress = page_portfolio(ctx)
    return {
        "updated_at": cache.read_meta("updated_at"), "exported_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "css": css(), "warnings": warnings_html(),
        "pages": {"oggi": page_today(ctx), "paese": paese, "asset": page_ranking(), "portafoglio": portfolio,
                  "metodo": page_method(), "cot": page_cot(ctx), "calendario": page_calendar(), "mercati": page_markets(),
                  "allocazione": page_allocation()},
        "charts": ctx["charts"], "stress": stress,
    }


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build(), ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    print(f"{out}: {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
