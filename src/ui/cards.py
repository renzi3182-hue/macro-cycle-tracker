"""Blocchi HTML dell'interfaccia (st.html). Colori solo da variabili CSS di theme.py, cosi' valgono in chiaro e scuro.
Niente <svg>: st.html li rimuove, quindi grafici solo con div/CSS."""
from collections import Counter
from html import escape
from math import cos, pi, sin

import pandas as pd

from src.classify.cycle import PHASES
from src.classify.regime import REGIMES
from src.classify.score import STRONG, WEAK
from src.ui.theme import DONUT_SLOTS, phase_color, regime_color

MONTHS = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
WEIGHT_VARS = ["accent", "r-gold", "r-defl", "r-refl", "r-stag", "muted"]
CONFIDENCE_STEPS = {"Bassa": 1, "Media": 2, "Alta": 3}
RIBBON_MONTHS = 36


def month_it(ts: pd.Timestamp, short: bool = False) -> str:
    name = MONTHS[ts.month - 1]
    return f"{name[:3] if short else name} {ts.year}"


def duration_it(start: pd.Timestamp, end: pd.Timestamp) -> str:
    months = (end.year - start.year) * 12 + end.month - start.month + 1
    years, rest = divmod(months, 12)
    parts = ([f"{years} {'anno' if years == 1 else 'anni'}"] if years else []) + ([f"{rest} {'mese' if rest == 1 else 'mesi'}"] if rest else [])
    return " e ".join(parts)


def prevailing_regime(regimes: dict[str, str]) -> tuple[str, int]:
    """Regime piu' frequente fra le aree e quante aree lo condividono (a parita' vince il primo in ordine d'area)."""
    return Counter(regimes.values()).most_common(1)[0]


def weight_deltas(now: dict, prev: dict) -> dict:
    """Variazione in punti percentuali interi, per ogni asset del portafoglio attuale."""
    return {k: round(now[k]) - round(prev.get(k, 0)) for k in now}


def _dot(color: str) -> str:
    return f'<i class="dot" style="background:{color}"></i>'


def _signed(d: float) -> str:
    color = "var(--r-gold)" if d > 0 else "var(--r-stag)" if d < 0 else "var(--muted)"
    return f'<span class="mono" style="color:{color}">{f"{d:+.0f}".replace("-", "−")}</span>'


def hero_html(eyebrow: str, title: str, lead: str) -> str:
    """lead: html gia' sicuro."""
    return f'<div class="hero"><span class="eyebrow">{escape(eyebrow)}</span><h1>{title}</h1><p class="lead">{lead}</p></div>'


def solidity_html(confidence: str) -> str:
    n = CONFIDENCE_STEPS.get(confidence, 0)
    bars = "".join(f'<i class="{"on" if k < n else ""}"></i>' for k in range(3))
    return f'<span class="solid" title="Solidità della lettura: quanto i due assi sono lontani dalla soglia di cambio">' \
           f'<span role="img" aria-label="solidità {escape(confidence.lower())}">{bars}</span>Solidità {escape(confidence.lower())}</span>'


def ribbon_html(values: pd.Series, color, months: int = RIBBON_MONTHS, thin: bool = False, ticks: bool = True) -> str:
    """Nastro mensile (dal piu' vecchio a oggi). color: funzione valore -> colore CSS."""
    v = values.dropna().iloc[-months:]
    if v.empty:
        return ""
    cells = "".join(f'<i style="background:{color(x)}" title="{month_it(d, True)}: {escape(str(x))}"></i>' for d, x in v.items())
    out = f'<div class="ribbon{" thin" if thin else ""}" role="img" aria-label="storico mensile">{cells}</div>'
    if ticks:
        out += f'<div class="ticks"><span>{month_it(v.index[0], True)}</span><span>{month_it(v.index[-1], True)}</span></div>'
    return out


def area_tile_html(a: dict, href: str) -> str:
    """a: risultato di assess() + chiave 'label'."""
    color = regime_color(a["regime"])
    phase = a["phase"] or "n/d"
    alert = f'<span class="chip tint" style="--c:var(--r-refl)">Dati in ritardo</span>' if a["stale"] else ""
    return (
        f'<a class="card tile" href="{escape(href)}" target="_self">'
        f'<div class="head"><span class="eyebrow">{escape(a["label"])}</span>'
        f'<span class="chip tint" style="--c:{phase_color(a["phase"])}">{escape(phase)}</span></div>'
        f'<div class="regime">{_dot(color)}<span style="color:{color}">{escape(a["regime"])}</span></div>'
        f'<div class="meta"><span>da <b>{month_it(a["regime_since"])}</b></span>{alert}</div>'
        f'{solidity_html(a["confidence"])}'
        f'{ribbon_html(a["history"]["regime"], regime_color)}</a>'
    )


def legend_html(phases: bool = False) -> str:
    items = [(phase_color(p), p) for p in PHASES] if phases else [(regime_color(r), r) for r in REGIMES]
    return '<div class="meta">' + "".join(f"<span>{_dot(c)} {n}</span>" for c, n in items) + "</div>"


LABEL_NEAR_X, LABEL_GAP_Y = 22, 8  # % del quadrante


def _place_labels(pts: list[dict]) -> None:
    """Etichette a sinistra del punto nella meta' destra; sullo stesso lato e vicine in x si scostano in verticale (chiave ly)."""
    placed = []
    for p in sorted(pts, key=lambda p: p["y"]):
        p["ly"] = p["y"]
        for q in sorted(placed, key=lambda q: q["ly"]):
            if q["left"] == p["left"] and abs(q["x"] - p["x"]) < LABEL_NEAR_X and abs(q["ly"] - p["ly"]) < LABEL_GAP_Y:
                p["ly"] = q["ly"] + LABEL_GAP_Y
        placed.append(p)


def quadrant_html(areas: list[dict], codes: dict[str, str]) -> str:
    """Posizione di ogni area: x = inflazione, y = crescita, in unita' di banda (+-1 = soglia). Div in %, niente svg."""
    edge, fill = 2.5, 0.9

    def pct(v):
        return 50 + max(-edge, min(edge, v)) / edge * 50 * fill

    quads = [("Goldilocks", "top:0;left:0"), ("Reflazione", "top:0;left:50%"),
             ("Stagflazione", "top:50%;left:50%"), ("Deflazione", "top:50%;left:0")]
    labels = [("Goldilocks", "top:10px;left:12px"), ("Reflazione", "top:10px;right:12px"),
              ("Stagflazione", "bottom:10px;right:12px"), ("Deflazione", "bottom:10px;left:12px")]
    out = ['<div class="quad" role="img" aria-label="Quadrante crescita e inflazione">']
    out += [f'<div class="q" style="{pos};background:color-mix(in srgb,{regime_color(r)} 13%,transparent)"></div>' for r, pos in quads]
    out.append('<div class="ax-v"></div><div class="ax-h"></div>')
    out += [f'<span class="ql" style="{pos};color:{regime_color(r)}">{r}</span>' for r, pos in labels]
    out.append('<span class="ql" style="bottom:32px;right:12px;font-weight:500">inflazione →</span>')
    out.append('<span class="ql" style="top:34px;left:calc(50% + 8px);font-weight:500">↑ crescita</span>')
    pts = []
    for a in areas:
        xg, xi = a["positions"]
        pts.append({"a": a, "x": pct(xi), "y": 100 - pct(xg), "left": pct(xi) > 60})
    _place_labels(pts)
    for p in pts:
        a = p["a"]
        xg, xi = a["positions"]
        tip = escape(f'{a["label"]}: {a["regime"]} (crescita {xg:+.1f}, inflazione {xi:+.1f}; 0 = soglia)')
        side = f'right:calc({100 - p["x"]:.1f}% + 12px)' if p["left"] else f'left:calc({p["x"]:.1f}% + 12px)'
        out.append(f'<div class="pt" title="{tip}" style="left:{p["x"]:.1f}%;top:{p["y"]:.1f}%;background:{regime_color(a["regime"])}"></div>'
                   f'<b class="pl" style="{side};top:{min(p["ly"], 96):.1f}%">{escape(codes.get(a["area"], a["area"]))}</b>')
    out.append("</div>")
    return "".join(out)


def prob_html(probs: dict) -> str:
    return "".join(
        f'<div class="prow"><span>{_dot(regime_color(r))} {r}</span>'
        f'<div class="track"><i style="width:{p * 100:.0f}%;background:{regime_color(r)}"></i></div>'
        f'<span class="mono r">{p * 100:.0f}%</span></div>'
        for r, p in sorted(probs.items(), key=lambda x: -x[1])
    )


def gauge_html(x: float, lo_label: str, hi_label: str, lo_var: str, hi_var: str, mid_label: str = "stabile") -> str:
    """Posizione su una scala da -2.5 a +2.5 bande; la zona centrale (+-1) e' quella in cui lo stato non cambia."""
    left = 50 + max(-2.5, min(2.5, x)) / 2.5 * 50
    return (
        f'<div class="gauge" style="--lo:var(--{lo_var});--hi:var(--{hi_var})" role="img" aria-label="posizione {x:+.1f} bande">'
        f'<div class="bar"></div><b style="left:{left:.1f}%"></b></div>'
        f'<div class="gauge-l"><span>{escape(lo_label)}</span><span>{escape(mid_label)}</span><span>{escape(hi_label)}</span></div>'
    )


def axis_card_html(eyebrow: str, state: str, state_var: str, value: str, value_note: str, gauge: str, note: str) -> str:
    return (
        f'<div class="si card"><span class="eyebrow">{escape(eyebrow)}</span>'
        f'<h3 style="color:var(--{state_var})">{escape(state)}</h3>'
        f'<div><span class="big">{escape(value)}</span> <span class="muted" style="font-size:13px">{escape(value_note)}</span></div>'
        f'{gauge}<p class="note">{note}</p></div>'
    )


def area_hero_html(a: dict, sentence: str) -> str:
    color = regime_color(a["regime"])
    phase = a["phase"] or "n/d"
    end = a["month"]
    facts = [
        ("Fase del ciclo", f'<span style="color:{phase_color(a["phase"])}">{escape(phase)}</span>'),
        ("Regime da", f'{month_it(a["regime_since"])}<br><span class="muted" style="font-size:13px;font-weight:400">{duration_it(a["regime_since"], end)}</span>'),
        ("Solidità", escape(a["confidence"])),
        ("Dati fino a", month_it(end)),
    ]
    cells = "".join(f'<div style="display:flex;flex-direction:column;gap:4px"><span class="eyebrow">{k}</span>'
                    f'<span style="font-size:17px;font-weight:600">{v}</span></div>' for k, v in facts)
    return (
        f'<div class="si card" style="padding:32px;border-radius:28px;background:linear-gradient(160deg,color-mix(in srgb,{color} 14%,var(--surface)),var(--surface) 55%)">'
        f'<span class="eyebrow">Regime macro · {escape(a["label"])}</span>'
        f'<h1 style="font-size:clamp(40px,6vw,68px);line-height:1;font-weight:800;letter-spacing:-0.04em;color:{color}">{escape(a["regime"])}</h1>'
        f'<p style="font-size:17px;line-height:26px;max-width:720px">{sentence}</p>'
        f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:16px;margin-top:8px">{cells}</div></div>'
    )


def history_html(hist: pd.DataFrame, months: int = 120) -> str:
    h = hist.iloc[-months:]
    years = sorted({d.year for d in h.index})
    step = max(1, len(years) // 5)
    ticks = "".join(f"<span>{y}</span>" for y in years[::step])
    return (
        f'<div class="si card"><div class="head"><h3>Storico</h3><span class="note">ultimi {len(h) // 12} anni, un tratto per mese</span></div>'
        f'<div><div class="rlabel">Regime (riga alta) e fase del ciclo (riga bassa)</div>{ribbon_html(h["regime"], regime_color, months, ticks=False)}'
        f'<div style="height:4px"></div>{ribbon_html(h["phase"], phase_color, months, thin=True, ticks=False)}'
        f'<div class="ticks">{ticks}</div></div><div>{legend_html()}<div style="height:6px"></div>{legend_html(phases=True)}</div></div>'
    )


def freshness_html(rows: list[tuple[str, pd.Timestamp, bool]]) -> str:
    """rows: (etichetta, data dell'ultimo dato, in ritardo)."""
    items = "".join(
        f'<div class="row">{_dot("var(--r-refl)" if stale else "var(--r-gold)")}<span class="grow">{escape(label)}</span>'
        f'<span class="mono muted">{month_it(d, True)}</span></div>'
        for label, d, stale in rows
    )
    return f'<div class="si card"><h3>Dati usati</h3><div class="list">{items}</div>' \
           '<p class="note">Giallo = più vecchio del normale ritardo di pubblicazione: la fonte potrebbe aver cambiato dataset.</p></div>'


def changes_html(items: list[tuple[str, str, str]]) -> str:
    """items: (colore CSS, testo html sicuro, data)."""
    if not items:
        rows = '<div class="row"><span class="grow muted">Nessun cambio di regime o fase negli ultimi 90 giorni.</span></div>'
    else:
        rows = "".join(f'<div class="row">{_dot(c)}<span class="grow">{t}</span><span class="mono muted">{escape(d)}</span></div>' for c, t, d in items)
    return f'<div class="si card"><h3>Cosa è cambiato</h3><div class="list">{rows}</div></div>'


def risk_html(level: str, score: int, total: int) -> str:
    var = {"Alto": "r-stag", "Medio": "r-refl"}.get(level, "r-gold")
    blocks = "".join(f'<i class="{"on" if k < score else ""}" style="{"background:var(--" + var + ")" if k < score else ""}"></i>' for k in range(total))
    return (
        f'<div class="si head"><h3 style="font-size:17px;font-weight:600">Indicatori anticipatori</h3>'
        f'<span class="solid"><span role="img" aria-label="{score} segnali attivi su {total}">{blocks}</span>'
        f'<b style="color:var(--{var})">Rischio {escape(level.lower())} · {score}/{total}</b></span></div>'
    )


def portfolio_html(weights: dict, deltas: dict | None, title: str, subtitle: str, delta_note: str = "vs regimi precedenti") -> str:
    items = sorted(weights.items(), key=lambda kv: -kv[1])[:DONUT_SLOTS]
    colors = {k: f"var(--{WEIGHT_VARS[i % len(WEIGHT_VARS)]})" for i, (k, _) in enumerate(items)}
    equity = sum(v for k, v in weights.items() if "Azionario" in k)
    top = items[0][1] or 1
    rows = "".join(
        f'<div class="wrow"><span class="sw" style="background:{colors[k]};opacity:{1 - i // len(WEIGHT_VARS) * .45}"></span><span>{escape(k)}</span>'
        f'<div class="track"><i style="width:{v / top * 100:.0f}%;background:{colors[k]}"></i></div>'
        f'<span class="mono r">{v:.0f}%</span><span class="r" style="font-size:13px">{_signed(deltas[k]) if deltas else ""}</span></div>'
        for i, (k, v) in enumerate(items)
    )
    segs, tips, acc = "", "", 0.0
    for i, (k, v) in enumerate(items):
        a0, a1 = acc / 100 * 2 * pi, max(acc + v - 0.4, acc) / 100 * 2 * pi
        n = max(int((a1 - a0) / 0.05), 1)
        pts = ["50% 50%"] + [f"{50 + 75 * sin(a0 + (a1 - a0) * j / n):.2f}% {50 - 75 * cos(a0 + (a1 - a0) * j / n):.2f}%" for j in range(n + 1)]
        segs += f'<div class="s s{i}" style="background:{colors[k]};opacity:{1 - i // len(WEIGHT_VARS) * .45};clip-path:polygon({", ".join(pts)})"></div>'
        tips += (f'<div class="c tip t{i}"><b>{v:.0f}<span class="muted" style="font-size:20px">%</span></b>'
                 f'<span style="font-size:12px;color:{colors[k]}">{escape(k)}</span></div>')
        acc += v
    donut = (
        f'<div class="donut" role="img" aria-label="Quota azionaria {equity:.0f}%">{segs}<div class="hole"></div>'
        f'<div class="c def"><b>{equity:.0f}<span class="muted" style="font-size:20px">%</span></b><span class="muted" style="font-size:13px">azionario</span></div>{tips}</div>'
    )
    return (
        f'<div class="si two"><div class="card"><div class="head"><h3>{escape(title)}</h3><span class="note">{escape(subtitle)}</span></div>{donut}</div>'
        f'<div class="card"><div class="head"><h3>Pesi per asset class</h3><span class="note">{escape(delta_note) if deltas else ""}</span></div>{rows}</div></div>'
    )


def trend_html(rows: list[tuple[str, str, float]], month: pd.Timestamp) -> str:
    """rows: (asset class, ticker, distanza % dalla media a 10 mesi)."""
    items = "".join(
        f'<div class="row">{_dot("var(--r-gold)" if d > 0 else "var(--r-stag)")}<span class="grow">{escape(a)} '
        f'<span class="mono muted" style="font-size:12px">{escape(t)}</span></span>'
        f'<span class="mono" style="color:var(--{"r-gold" if d > 0 else "r-stag"})">{f"{d:+.1f}".replace(".", ",").replace("-", "−")}%</span></div>'
        for a, t, d in rows
    )
    return (f'<div class="si card"><div class="head"><h3>Tendenza</h3><span class="note">fine {month_it(month)}, prezzo vs media 10 mesi</span></div>'
            f'<div class="list">{items}</div>'
            '<p class="note">Rosso = sotto la media: con il filtro attivo quella quota va in cash. Nel backtest 2000-2026 il filtro ha '
            'ridotto il drawdown massimo del 55-75% (60/40 da −31% a −13%) e il rendimento di 0,1-0,9 punti l\'anno: '
            'protegge nei crolli lunghi, perde nei rimbalzi veloci.</p></div>')


def events_html(events: list[dict]) -> str:
    """events: dict Evento, Data (Timestamp), giorni; gia' ordinati per data."""
    if not events:
        return '<div class="si card"><h3>Prossimi eventi</h3><p class="note">Nessuna data in cache.</p></div>'
    first, rest = events[0], events[1:]
    head = (f'<div class="ev-next"><div class="d"><span>{first["giorni"]}</span><small>{"giorno" if first["giorni"] == 1 else "giorni"}</small></div>'
            f'<div style="display:flex;flex-direction:column"><b style="font-weight:600">{escape(first["Evento"])}</b>'
            f'<span class="mono muted" style="font-size:13px">{first["Data"]:%d/%m/%Y}</span></div></div>')
    rows = "".join(f'<div class="row"><span class="mono" style="min-width:56px">{e["giorni"]} gg</span><span class="grow">{escape(e["Evento"])}</span>'
                   f'<span class="mono muted">{e["Data"]:%d/%m/%Y}</span></div>' for e in rest)
    return f'<div class="si card"><h3>Prossimi eventi</h3>{head}<div class="list">{rows}</div></div>'


def cot_groups_html(market: str, rows: list[dict], date: str) -> str:
    """rows: Categoria, Netto (% open interest), Variazione (punti, vs settimana prima), Percentile (5 anni). Solo informativo."""
    out = []
    for r in rows:
        pct = r["Percentile"]
        left, width = (50, pct - 50) if pct >= 50 else (pct, 50 - pct)
        out.append(
            f'<span>{escape(r["Categoria"])}</span>'
            f'<div class="div" role="img" aria-label="percentile {pct}"><i style="left:{left}%;width:{width}%;border-radius:{"0 5px 5px 0" if pct >= 50 else "5px 0 0 5px"}"></i></div>'
            f'<span class="mono r">{r["Netto"]:+.1f}%</span><span class="mono r muted lbl">{r["Variazione"]:+.1f}</span>'
        )
    return (
        f'<div class="si card"><div class="head"><h3>Posizioni per categoria: {escape(market)}</h3><span class="note">dato del {escape(date)}</span></div>'
        f'<div class="cot">{"".join(out)}</div>'
        '<p class="note">Netto = long meno short in % dell\'open interest; variazione in punti sulla settimana prima. '
        'Barra dal centro: percentile sugli ultimi 5 anni (destra = più long del solito). '
        'Dealer, produttori e swap dealer sono in gran parte coperture, non scommesse direzionali. Dati CFTC.</p></div>'
    )


def strength_html(scores: dict[str, int | None]) -> str:
    ranked = sorted(((c, s) for c, s in scores.items() if s is not None), key=lambda x: -x[1])
    rows = "".join(
        f'<div class="srow"><span class="mono muted">{i}</span><b style="font-size:19px;font-weight:700">{c}</b>'
        f'<div class="track" style="height:12px"><i style="width:{s}%;background:var(--{"r-gold" if s >= 60 else "r-stag" if s <= 40 else "accent"})"></i></div>'
        f'<span class="mono r" style="font-size:19px">{s}</span></div>'
        for i, (c, s) in enumerate(ranked, 1)
    )
    return f'<div class="si card"><div class="head"><h3>Classifica di forza</h3><span class="note">1-100</span></div>{rows}</div>'


def pairs_html(rows: list[dict]) -> str:
    """rows: Coppia, Punteggio, Segnale (Buy/Sell/Neutra)."""
    tag = {"Buy": "r-gold", "Sell": "r-stag"}
    cards = "".join(
        f'<div class="pair"><div class="head"><span class="mono" style="font-size:15px">{escape(r["Coppia"])}</span>'
        f'<span class="chip tint" style="--c:var(--{tag.get(r["Segnale"], "muted")});font-size:12px;font-weight:700">{escape(r["Segnale"])}</span></div>'
        f'<span class="mono" style="font-size:28px">{r["Punteggio"]}</span><div class="scale"><i style="left:{r["Punteggio"]}%"></i></div></div>'
        for r in rows
    )
    return f'<div class="si card"><div class="head"><h3>Coppie</h3><span class="note">Buy ≥ 60 · Sell ≤ 40</span></div><div class="pairs">{cards}</div></div>'


def score_color(s: float) -> str:
    return f"var(--{'r-gold' if s > STRONG else 'r-stag' if s <= WEAK else 'muted'})"


def ranking_html(rows: list[dict], month: pd.Timestamp) -> str:
    """rows: ticker, nome, gruppo, punteggio, delta (vs mese prima o None), Tendenza e Momentum (frazioni), storico (serie mensile)."""
    head = ('<div class="arow th"><span>#</span><span>Asset</span><span class="opt">Ultimi 12 mesi</span>'
            '<span class="r opt">Tendenza</span><span class="r opt">Mom. 12-1</span><span class="r">Punt.</span><span class="r">Var.</span></div>')
    body = "".join(
        f'<div class="arow"><span class="mono muted">{i}</span>'
        f'<span style="min-width:0"><b style="font-weight:600">{escape(r["nome"])}</b> '
        f'<span class="mono muted" style="font-size:12px">{escape(r["ticker"])}<span class="opt"> · {escape(r["gruppo"])}</span></span></span>'
        f'<span class="opt">{ribbon_html(r["storico"], score_color, 12, thin=True, ticks=False)}</span>'
        f'<span class="mono r opt">{r["Tendenza"] * 100:+.1f}%</span><span class="mono r opt">{r["Momentum"] * 100:+.1f}%</span>'
        f'<span class="r"><span class="chip tint mono" style="--c:{score_color(r["punteggio"])};font-weight:700">{r["punteggio"]:.0f}</span></span>'
        f'<span class="r" style="font-size:13px">{_signed(r["delta"]) if r["delta"] is not None else ""}</span></div>'
        for i, r in enumerate(rows, 1)
    )
    return (f'<div class="si card"><div class="head"><h3>Classifica</h3><span class="note">punteggio di fine {month_it(month)}, 1-100</span></div>'
            f'<div class="list">{head}{body}</div></div>')


def bands_html(table: pd.DataFrame, horizon: int, since: pd.Timestamp) -> str:
    """table: band_table() di score.py, indice = fascia ('81-100'), colonne mediana e sopra in %."""
    top = max(table["mediana"].abs().max(), 0.01)
    rows = []
    for band, r in table.iloc[::-1].iterrows():
        m, lo = r["mediana"], int(str(band).split("-")[0])
        left, width = (50, m / top * 50) if m >= 0 else (50 + m / top * 50, -m / top * 50)
        rows.append(
            f'<span class="mono">{escape(str(band))}</span>'
            f'<div class="div" role="img" aria-label="extra-rendimento mediano {m:+.2f}%"><i style="left:{left:.1f}%;width:{width:.1f}%;'
            f'background:{score_color(lo)};border-radius:{"0 5px 5px 0" if m >= 0 else "5px 0 0 5px"}"></i></div>'
            f'<span class="mono r">{f"{m:+.2f}".replace(".", ",").replace("-", "−")}%</span><span class="mono r muted lbl">{r["sopra"]:.0f}%</span>'
        )
    return (
        f'<div class="si card"><div class="head"><h3>Cosa ha voluto dire</h3><span class="note">{int(table["casi"].sum())} casi da {month_it(since, True)}</span></div>'
        f'<div class="cot">{"".join(rows)}</div>'
        f'<p class="note">Per fascia di punteggio: extra-rendimento mediano nei {horizon} mesi successivi contro la media degli asset, '
        'e quante volte l\'asset ha fatto meglio della media. Ogni mese usa solo i prezzi noti in quel momento.</p></div>'
    )


def chips_html(items: list[str]) -> str:
    return '<div class="si" style="display:flex;flex-wrap:wrap;gap:8px">' + "".join(f'<span class="chip">{escape(i)}</span>' for i in items) + "</div>"


IMPACT_VARS = {"High": "r-stag", "Medium": "r-refl", "Low": "muted", "Holiday": "line"}
IMPACT_LABELS = {"High": "Alto", "Medium": "Medio", "Low": "Basso", "Holiday": "Festivo"}
WEEKDAYS = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]


def calendar_html(events: list[dict], tz: str = "Europe/Rome", today: pd.Timestamp | None = None) -> str:
    """events: dict date (UTC ISO), country, title, impact, forecast, previous. Raggruppa per giorno nel fuso `tz`."""
    today = (today or pd.Timestamp.now(tz)).date()
    days: dict = {}
    for e in sorted(events, key=lambda e: e["date"]):
        local = pd.Timestamp(e["date"]).tz_convert(tz)
        days.setdefault(local.date(), []).append((local, e))
    if not days:
        return '<div class="si card"><p class="note">Nessun evento con questi filtri.</p></div>'
    out = []
    for day, rows in days.items():
        out.append(f"<h4>{WEEKDAYS[day.weekday()]} {day:%d/%m}{'<b>oggi</b>' if day == today else ''}</h4>")
        for local, e in rows:
            values = " · ".join(f"{label} <b>{escape(v)}</b>" for label, v in (("atteso", e["forecast"]), ("prec.", e["previous"])) if v)
            out.append(
                f'<div class="row{" holiday" if e["impact"] == "Holiday" else ""}"><span class="mono">{local:%H:%M}</span>'
                f'<span class="chip" style="padding:2px 8px;font-size:12px">{escape(e["country"])}</span>'
                f'<i class="dot" style="background:var(--{IMPACT_VARS.get(e["impact"], "muted")})" title="Impatto {IMPACT_LABELS.get(e["impact"], e["impact"])}"></i>'
                f'<span>{escape(e["title"])}</span><span class="v">{values}</span></div>'
            )
    return f'<div class="si card cal"><div class="list">{"".join(out)}</div></div>'


RRG_VARS = {"Guida": "r-gold", "Indebolisce": "r-refl", "Arretra": "r-stag", "Migliora": "r-defl"}


def rrg_html(rows: list[dict], month: pd.Timestamp) -> str:
    """rows: ticker, nome, ratio, momentum, quadrante. x = RS-Ratio, y = RS-Momentum, centro 100. Div in %, niente svg."""
    span = max(2.0, *(abs(r[k] - 100) for r in rows for k in ("ratio", "momentum"))) * 1.1

    def pct(v):
        return 50 + (v - 100) / span * 50 * 0.9

    quads = [("Migliora", "top:0;left:0"), ("Guida", "top:0;left:50%"), ("Indebolisce", "top:50%;left:50%"), ("Arretra", "top:50%;left:0")]
    labels = [("Migliora", "top:10px;left:12px"), ("Guida", "top:10px;right:12px"),
              ("Indebolisce", "bottom:10px;right:12px"), ("Arretra", "bottom:10px;left:12px")]
    out = [f'<div class="card"><div class="head"><h3>Rotazione settori USA</h3><span class="note">fine {month_it(month)}</span></div>'
           '<div class="quad" role="img" aria-label="Forza relativa dei settori USA contro lo S&amp;P 500">']
    out += [f'<div class="q" style="{pos};background:color-mix(in srgb,var(--{RRG_VARS[q]}) 13%,transparent)"></div>' for q, pos in quads]
    out.append('<div class="ax-v"></div><div class="ax-h"></div>')
    out += [f'<span class="ql" style="{pos};color:var(--{RRG_VARS[q]})">{q}</span>' for q, pos in labels]
    out.append('<span class="ql" style="bottom:32px;right:12px;font-weight:500">forza relativa →</span>')
    out.append('<span class="ql" style="top:34px;left:calc(50% + 8px);font-weight:500">↑ slancio</span>')
    pts = [{"r": r, "x": pct(r["ratio"]), "y": 100 - pct(r["momentum"]), "left": pct(r["ratio"]) > 60} for r in rows]
    _place_labels(pts)
    for p in pts:
        r = p["r"]
        tip = escape(f'{r["nome"]}: {r["quadrante"]} (RS-Ratio {r["ratio"]:.1f}, RS-Momentum {r["momentum"]:.1f})')
        side = f'right:calc({100 - p["x"]:.1f}% + 12px)' if p["left"] else f'left:calc({p["x"]:.1f}% + 12px)'
        out.append(f'<div class="pt" title="{tip}" style="left:{p["x"]:.1f}%;top:{p["y"]:.1f}%;background:var(--{RRG_VARS[r["quadrante"]]})"></div>'
                   f'<b class="pl" style="{side};top:{min(p["ly"], 96):.1f}%">{escape(r["ticker"])}</b>')
    out.append("</div>")
    out.append(chips_html([f'{r["ticker"]} {r["nome"]}: {r["quadrante"]}' for r in sorted(rows, key=lambda r: -r["ratio"])]))
    out.append('<p class="note">Forza relativa = settore contro lo S&amp;P 500 rispetto alla sua media a 10 mesi; slancio = '
               'variazione della forza relativa in 3 mesi. Mappa descrittiva: dal 1999 i settori in Guida non hanno '
               'fatto meglio di quelli che Arretrano nei 3 mesi dopo.</p></div>')
    return "".join(out)


def _pct_it(x: float, digits: int = 0) -> str:
    return f"{x * 100:+.{digits}f}".replace(".", ",").replace("-", "−") + "%"


def stress_html(rows: list[tuple[str, str, tuple | None, tuple | None]], mc: dict | None, years: int, skipped: list[str]) -> str:
    """rows: (crisi, periodo, (rendimento, drawdown) del portafoglio o None, idem S&P 500). mc: percentile -> valore di 100."""
    items = "".join(
        f'<div class="row"><span class="grow">{escape(name)} <span class="muted" style="font-size:12px">{escape(period)}</span></span>'
        + (f'<span class="mono" style="color:var(--{"r-gold" if p[0] >= 0 else "r-stag"})" title="drawdown massimo {_pct_it(p[1])}">{_pct_it(p[0])}</span>'
           if p else '<span class="muted" style="font-size:13px">n/d</span>')
        + f'<span class="mono muted opt" style="font-size:12px;min-width:92px;text-align:right">S&amp;P {_pct_it(s[0]) if s else "n/d"}</span></div>'
        for name, period, p, s in rows
    )
    band = (f'<p>Dopo {years} anni, 100 diventano <b class="mono">{mc[5]:.0f}</b> nel 5% dei casi peggiori, '
            f'<b class="mono">{mc[50]:.0f}</b> a metà, <b class="mono">{mc[95]:.0f}</b> nel 5% migliore.</p>' if mc else "")
    note = f" Esclusi perché senza ETF: {escape(', '.join(skipped))}." if skipped else ""
    return (f'<div class="si card"><div class="head"><h3>Stress test</h3><span class="note">rendimento nella crisi</span></div>'
            f'<div class="list">{items}</div>{band}'
            '<p class="note">Ogni classe usa il suo ETF (azionario = SPY, cash = SHY), ribilanciamento mensile, niente costi. '
            'n/d = qualche ETF non esisteva ancora. La banda ricampiona i mesi storici del portafoglio: '
            f'il passato non garantisce il futuro.{note}</p></div>')
