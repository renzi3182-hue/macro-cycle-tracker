"""Blocchi HTML dell'interfaccia (st.html). Colori solo da variabili CSS di theme.py, cosi' valgono in chiaro e scuro.
Niente <svg>: st.html li rimuove, quindi grafici solo con div/CSS."""
from collections import Counter
from html import escape
from math import cos, pi, sin

import pandas as pd

from src.classify.assess import label_regimes, run_start
from src.classify.cycle import PHASES
from src.classify.regime import REGIMES
from src.classify.score import STRONG, WEAK
from src.ui.theme import DONUT_SLOTS, WAVE_AMPLITUDE, phase_color, regime_color

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
    color = regime_color(a["regime_label"])
    phase = a["phase"] or "n/d"
    alert = f'<span class="chip tint" style="--c:var(--r-refl)">Dati in ritardo</span>' if a["stale"] else ""
    return (
        f'<a class="card tile" href="{escape(href)}" target="_self">'
        f'<div class="head"><span class="eyebrow">{escape(a["label"])}</span>'
        f'<span class="chip tint" style="--c:{phase_color(a["phase"])}">{escape(phase)}</span></div>'
        f'<div class="regime">{_dot(color)}<span style="color:{color}">{escape(a["regime_label"])}</span></div>'
        f'<div class="meta"><span>da <b>{month_it(a["regime_since"])}</b></span>{alert}</div>'
        f'{solidity_html(a["confidence"])}'
        f'{ribbon_html(a["history"]["regime"], regime_color)}</a>'
    )


def legend_html() -> str:
    items = [(regime_color(r), r) for r in REGIMES]
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
        tip = escape(f'{a["label"]}: {a["regime_label"]} (crescita {xg:+.1f}, inflazione {xi:+.1f}; 0 = soglia)')
        side = f'right:calc({100 - p["x"]:.1f}% + 12px)' if p["left"] else f'left:calc({p["x"]:.1f}% + 12px)'
        out.append(f'<div class="pt" title="{tip}" style="left:{p["x"]:.1f}%;top:{p["y"]:.1f}%;background:{regime_color(a["regime_label"])}"></div>'
                   f'<b class="pl" style="{side};top:{min(p["ly"], 96):.1f}%">{escape(codes.get(a["area"], a["area"]))}</b>')
    out.append("</div>")
    return "".join(out)


def prob_html(p_inflation: float, estimate: str | None = None) -> str:
    """Solo l'asse inflazione: la crescita del trimestre non si prevede (resta ~50%).
    estimate: regime con probabilita' piu' alta, se le prime due sono abbastanza distanti (altrimenti None)."""
    chip = f'<span class="chip tint" style="--c:{regime_color(estimate)}">{escape(estimate)}</span>' if estimate else ""
    return (
        f'<div class="prow"><span>{_dot("var(--r-stag)")} Inflazione alta</span>'
        f'<div class="track"><i style="width:{p_inflation * 100:.0f}%;background:var(--r-stag)"></i></div>'
        f'<span class="mono r">{p_inflation * 100:.0f}%</span></div>'
        f'<div class="prow"><span>{_dot("var(--muted)")} Crescita</span><span class="muted">incerta</span><span></span></div>'
        f'{chip}'
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


REGIME_MEANING = {"Goldilocks": "crescita accelera, inflazione bassa", "Reflazione": "crescita accelera, inflazione alta",
                  "Stagflazione": "crescita rallenta, inflazione alta", "Deflazione": "crescita rallenta, inflazione bassa"}


def level_var(v: float) -> str:
    """Colore di un valore 0-100 dove alto = bene: sotto 40 rosso, da 60 verde (come le fasce del Risk On/Off)."""
    return "r-gold" if v >= 60 else "r-stag" if v < 40 else "r-refl"


def _regime_paint(label: str, alpha: int = 100, angle: int = 90) -> str:
    """Colore di un'etichetta di regime; un'area incerta e' meta' e meta' dei suoi due regimi."""
    cs = [f"color-mix(in srgb, {regime_color(r)} {alpha}%, transparent)" for r in label_regimes(label)]
    return cs[0] if len(cs) == 1 else f"linear-gradient({angle}deg, {cs[0]} 50%, {cs[1]} 50%)"


def story_card_html(eyebrow: str, title: str, title_var: str, say: str, body: str, note: str = "") -> str:
    """Card della Panoramica: lo stato, una frase semplice e il dettaglio che la spiega."""
    return (
        f'<div class="si card"><span class="eyebrow">{escape(eyebrow)}</span>{_big_state(title, f"var(--{title_var})")}'
        f'<p class="say">{escape(say)}</p>{body}' + (f'<p class="note">{escape(note)}</p>' if note else "") + "</div>"
    )


def answer_card_html(href: str, question: str, score: float, state: str, say: str, body: str, note: str) -> str:
    """Card della pagina Oggi: una domanda, un punteggio 1-100 (alto = favorevole) e il dettaglio; tutta la card
    porta alla pagina di approfondimento."""
    s = max(1, round(score))
    return (
        f'<a class="card tile" href="{escape(href)}" target="_self"><span class="eyebrow">{escape(question)}</span>'
        f'<div class="total" style="border-top:0;padding-top:0"><span class="big" style="font-size:56px;line-height:60px;'
        f'color:var(--{level_var(s)})">{s}</span><span class="muted" style="font-size:13px">/100</span></div>'
        f'<div class="track"><i style="width:{s}%;background:var(--{level_var(s)})"></i></div>'
        f'{_big_state(state, "var(--fg)")}<p class="say">{escape(say)}</p>{body}<p class="note">{escape(note)}</p></a>'
    )


def phase_actions_html(eyebrow: str, rows: list[tuple[str, str, str | None, list[str], list[str]]], note: str) -> str:
    """Card della pagina Oggi: per area (nome, valuta, fase) gli asset da pesare di piu' (verde) e di meno (rosso)."""
    def chips(label: str, items: list[str], var: str) -> str:
        return f'<div class="chips" style="align-items:center"><span class="muted" style="min-width:76px">{label}</span>' + "".join(
            f'<span class="chip tint" style="--c:var(--{var})">{escape(i)}</span>' for i in items) + "</div>" if items else ""
    out = "".join(
        f'<div class="grp"><div class="top"><b>{escape(area)}</b><small class="mono">{escape(ccy)}</small>'
        f'<span class="chip tint" style="--c:{phase_color(phase)}">{escape(phase or "n/d")}</span></div>'
        f'{chips("Più peso", good, "r-gold")}{chips("Meno peso", bad, "r-stag")}</div>'
        for area, ccy, phase, good, bad in rows)
    return (f'<div class="si card"><span class="eyebrow">{escape(eyebrow)}</span>'
            '<p class="say">Per ogni paese e la sua valuta: la fase del ciclo e gli asset che in quella fase hanno reso di più '
            'e di meno.</p>'
            f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(300px,100%),1fr));column-gap:28px">{out}</div>'
            f'<p class="note">{escape(note)}</p></div>')


def regime_groups_html(regimes: dict[str, str]) -> str:
    """Una riga per regime con le sue aree, dal piu' diffuso (a parita' l'ordine delle aree, come prevailing_regime);
    le incerte per coppia di regimi, i regimi senza aree in fondo."""
    groups: dict[str, list[str]] = {}
    for area, label in regimes.items():
        groups.setdefault(label, []).append(area)
    rows = sorted(groups.items(), key=lambda g: -len(g[1])) + [(r, []) for r in REGIMES if r not in groups]
    out = []
    for label, areas in rows:
        pair = label_regimes(label)
        name, meaning = ("Incerte", f"fra {pair[0]} e {pair[1]}") if len(pair) > 1 else (label, REGIME_MEANING[label])
        ink = "var(--fg)" if len(pair) > 1 else regime_color(label)
        chips = "".join(f'<span class="chip" style="background:{_regime_paint(label, 22, 135)};color:{ink}">{escape(a)}</span>' for a in areas)
        out.append(
            f'<div class="grp"><div class="top"><i class="dot" style="background:{_regime_paint(label)}"></i><b>{escape(name)}</b>'
            f'<small>{escape(meaning)}</small><span class="mono">{len(areas)}</span></div>'
            f'<div class="chips">{chips or "<span class=muted>nessuna area</span>"}</div></div>'
        )
    return "".join(out)


def bar_rows_html(rows: list[tuple[str, str, float]]) -> str:
    """(etichetta, spiegazione, valore 0-100): una barra per riga, colorata con level_var."""
    return "".join(
        f'<div class="brow"><span>{escape(label)}</span><span class="mono">{v:.0f}</span><small>{escape(note)}</small>'
        f'<div class="track"><i style="width:{v:.0f}%;background:var(--{level_var(v)})"></i></div></div>'
        for label, note, v in rows
    )


def group_rows_html(groups: dict[str, list[tuple[str, bool]]]) -> str:
    """Per gruppo, (nome, in salita?) di ogni elemento: quanti in salita su quanti e un segmento per elemento."""
    out = []
    for group, items in groups.items():
        segs = "".join(f'<i title="{escape(n)}" style="background:{"var(--r-gold)" if up else "color-mix(in srgb, var(--r-stag) 30%, transparent)"}"></i>'
                       for n, up in items)
        out.append(f'<div class="brow"><span>{escape(group)}</span><span class="mono">{sum(up for _, up in items)} su {len(items)}</span>'
                   f'<div class="seg">{segs}</div></div>')
    return "".join(out)


def group_summary(groups: dict[str, list[tuple[str, bool]]]) -> str:
    """Frase sui gruppi tutti in salita o tutti in calo."""
    full = [g for g, items in groups.items() if all(up for _, up in items)]
    none = [g for g, items in groups.items() if not any(up for _, up in items)]
    parts = ([f"Tutti in salita: {', '.join(full)}."] if full else []) + ([f"Tutti in calo: {', '.join(none)}."] if none else [])
    return " ".join(parts) or "Nessun gruppo tutto in salita o tutto in calo."


def area_hero_html(a: dict, sentence: str, markets: tuple[int, int] | None = None) -> str:
    """markets: (asset tipici del regime in salita, asset con un ETF), da asset_allocation.confirmation."""
    color = regime_color(a["regime_label"])
    phase = a["phase"] or "n/d"
    end = a["month"]
    facts = [
        ("Fase del ciclo", f'<span style="color:{phase_color(a["phase"])}">{escape(phase)}</span>'),
        ("Regime da", f'{month_it(a["regime_since"])}<br><span class="muted" style="font-size:13px;font-weight:400">{duration_it(a["regime_since"], end)}</span>'),
        ("Solidità macro", escape(a["confidence"])),
        *([("Conferma mercati", f'{markets[0]} su {markets[1]}<br><span class="muted" style="font-size:13px;font-weight:400">asset tipici in salita</span>')]
          if markets and markets[1] else []),
        ("Dati fino a", month_it(end)),
    ]
    cells = "".join(f'<div style="display:flex;flex-direction:column;gap:4px"><span class="eyebrow">{k}</span>'
                    f'<span style="font-size:17px;font-weight:600">{v}</span></div>' for k, v in facts)
    return (
        f'<div class="si card" style="padding:32px;border-radius:28px;background:linear-gradient(160deg,color-mix(in srgb,{color} 14%,var(--surface)),var(--surface) 55%)">'
        f'<span class="eyebrow">Regime attuale · dati PIL a {month_it(a["month"])}</span>'
        f'<h1 style="font-size:clamp(40px,6vw,68px);line-height:1;font-weight:800;letter-spacing:-0.04em;color:{color}">{escape(a["regime_label"])}</h1>'
        f'<p style="font-size:17px;line-height:26px;max-width:720px">{sentence}</p>'
        f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:16px;margin-top:8px">{cells}</div></div>'
    )


def wave_html(phase: str | None) -> str:
    """Onda del ciclo come nel logo: un periodo, un quarto per fase nell'ordine di PHASES (Espansione sale al picco,
    Rallentamento scende, Recessione tocca il fondo, Ripresa risale verso il trend). Punto al centro del quarto."""
    dot = ""
    if phase in PHASES:
        x = 12.5 + 25 * PHASES.index(phase)
        dot = f'<b style="left:{x}%;top:{50 - WAVE_AMPLITUDE * sin(2 * pi * x / 100):.1f}%"></b>'
    labels = "".join(f'<span class="{"on" if p == phase else ""}">{escape(p)}</span>' for p in PHASES)
    return (f'<div class="wave" role="img" aria-label="Fase del ciclo: {escape(phase or "n/d")}">'
            f'<div class="mid"><span>trend</span></div><i></i>{dot}</div><div class="wave-l">{labels}</div>')


def history_html(hist: pd.DataFrame, months: int = 120) -> str:
    """Regime: un quadratino per mese. Fase: solo dove siamo sull'onda del ciclo (i colori della fase si confondevano
    con quelli del regime)."""
    h = hist.iloc[-months:]
    years = sorted({d.year for d in h.index})
    step = max(1, len(years) // 5)
    ticks = "".join(f"<span>{y}</span>" for y in years[::step])
    p = hist["phase"].dropna()
    phase = p.iloc[-1] if not p.empty else None
    since = f" da {month_it(run_start(p))}" if phase else ""
    return (
        f'<div class="si card"><div class="head"><h3>Storico</h3><span class="note">ultimi {len(h) // 12} anni, un tratto per mese</span></div>'
        f'<div><div class="rlabel">Regime</div>{ribbon_html(h["regime"], regime_color, months, ticks=False)}'
        f'<div class="ticks">{ticks}</div></div>{legend_html()}'
        f'<div><div class="rlabel">Fase del ciclo: <b>{escape(phase or "n/d")}</b>{since}</div>{wave_html(phase)}</div></div>'
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


def why_text(ranks: dict[str, int], n: int) -> str:
    """Perche' del punteggio: posizione fra gli n asset nel pilastro migliore e in quello peggiore."""
    (best, rb), (worst, rw) = sorted(ranks.items(), key=lambda kv: kv[1])[::len(ranks) - 1]
    if rb == rw:
        return f"{' e '.join(ranks).lower()} entrambi {rb}° su {n}"
    return f"meglio in {best.lower()} ({rb}° su {n}) che in {worst.lower()} ({rw}°)"


def ranking_html(rows: list[dict], month: pd.Timestamp) -> str:
    """rows: ticker, nome, gruppo, punteggio, delta (vs mese prima o None), Tendenza e Momentum (frazioni), storico (serie
    mensile), perche' (testo di why_text)."""
    head = ('<div class="arow th"><span>#</span><span>Asset</span><span class="opt">Ultimi 12 mesi</span>'
            '<span class="r opt">Tendenza</span><span class="r opt">Mom. 12-1</span><span class="r">Punt.</span><span class="r">Var.</span></div>')
    body = "".join(
        f'<div class="arow"><span class="mono muted">{i}</span>'
        f'<span style="min-width:0"><b style="font-weight:600">{escape(r["nome"])}</b> '
        f'<span class="mono muted" style="font-size:12px">{escape(r["ticker"])}<span class="opt"> · {escape(r["gruppo"])}</span></span>'
        f'<small class="muted" style="display:block;font-size:12px;line-height:16px">{escape(r["perche"])}</small></span>'
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


def trend_chips_html(items: list[tuple[str, bool | None]]) -> str:
    """(nome, in salita): verde sopra la media, rosso sotto, neutro senza dato."""
    return '<div class="si" style="display:flex;flex-wrap:wrap;gap:8px">' + "".join(
        f'<span class="chip tint" style="--c:var(--{"muted" if up is None else "r-gold" if up else "r-stag"})">{escape(n)}</span>'
        for n, up in items) + "</div>"


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
RRG_TEXT = {  # in ordine di rotazione (senso orario)
    "Migliora": ("In ingresso", "ancora peggio dell'S&P 500, ma recupera"),
    "Guida": ("In testa", "meglio dell'S&P 500 e il vantaggio cresce"),
    "Indebolisce": ("In raffreddamento", "ancora meglio dell'S&P 500, ma il vantaggio cala"),
    "Arretra": ("In coda", "peggio dell'S&P 500 e lo svantaggio cresce"),
}


def rrg_html(rows: list[dict], title: str, when: str) -> str:
    """rows: ticker, nome, ratio, momentum, quadrante. x = RS-Ratio, y = RS-Momentum, centro 100. Div in %, niente svg."""
    span = max(2.0, *(abs(r[k] - 100) for r in rows for k in ("ratio", "momentum"))) * 1.1

    def pct(v):
        return 50 + (v - 100) / span * 50 * 0.9

    quads = [("Migliora", "top:0;left:0"), ("Guida", "top:0;left:50%"), ("Indebolisce", "top:50%;left:50%"), ("Arretra", "top:50%;left:0")]
    labels = [("Migliora", "top:10px;left:12px"), ("Guida", "top:10px;right:12px"),
              ("Indebolisce", "bottom:10px;right:12px"), ("Arretra", "bottom:10px;left:12px")]
    out = [f'<div class="card"><div class="head"><h3>{escape(title)}</h3><span class="note">{escape(when)}</span></div>'
           f'<div class="quad" role="img" aria-label="{escape(title)}: forza relativa contro lo S&amp;P 500">']
    out += [f'<div class="q" style="{pos};background:color-mix(in srgb,var(--{RRG_VARS[q]}) 13%,transparent)"></div>' for q, pos in quads]
    out.append('<div class="ax-v"></div><div class="ax-h"></div>')
    out += [f'<span class="ql" style="{pos};color:var(--{RRG_VARS[q]})">{RRG_TEXT[q][0]}</span>' for q, pos in labels]
    out.append('<span class="ql" style="bottom:32px;right:12px;font-weight:500">forza relativa →</span>')
    out.append('<span class="ql" style="top:34px;left:calc(50% + 8px);font-weight:500">↑ slancio</span>')
    pts = [{"r": r, "x": pct(r["ratio"]), "y": 100 - pct(r["momentum"]), "left": pct(r["ratio"]) > 60} for r in rows]
    _place_labels(pts)
    for p in pts:
        r = p["r"]
        tip = escape(f'{r["nome"]}: {RRG_TEXT[r["quadrante"]][0].lower()} (RS-Ratio {r["ratio"]:.1f}, RS-Momentum {r["momentum"]:.1f})')
        side = f'right:calc({100 - p["x"]:.1f}% + 12px)' if p["left"] else f'left:calc({p["x"]:.1f}% + 12px)'
        out.append(f'<div class="pt" title="{tip}" style="left:{p["x"]:.1f}%;top:{p["y"]:.1f}%;background:var(--{RRG_VARS[r["quadrante"]]})"></div>'
                   f'<b class="pl" style="{side};top:{min(p["ly"], 96):.1f}%">{escape(r["ticker"])}</b>')
    out.append('</div><div class="list">')
    for q, (name, meaning) in RRG_TEXT.items():
        names = ", ".join(f'{r["nome"]} ({r["ticker"]})' for r in sorted(rows, key=lambda r: -r["ratio"]) if r["quadrante"] == q)
        if names:
            out.append(f'<div class="row">{_dot(f"var(--{RRG_VARS[q]})")}<span class="grow"><b>{name}</b>: {escape(names)}'
                       f'<small class="muted" style="display:block;font-size:12px">{meaning}</small></span></div>')
    out.append('</div><p class="note">Forza relativa = asset contro lo S&amp;P 500 rispetto alla sua media a 10 settimane; '
               'slancio = variazione della forza relativa in 3 settimane. Gira in senso orario: in ingresso, in testa, in '
               'raffreddamento, in coda. Mappa descrittiva: dal 1996, su 27 ETF, chi era in testa o in ingresso non ha fatto '
               'meglio degli altri nelle 4 e 13 settimane dopo.</p></div>')
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


MURPHY_VARS = {"Fase 1": "r-defl", "Fase 2": "accent", "Fase 3": "r-gold", "Fase 4": "r-refl", "Fase 5": "r-stag", "Fase 6": "muted"}
ALIGN_VARS = {"Allineati": "r-gold", "Parzialmente allineati": "r-refl", "Disallineati": "r-stag"}
CHECK_VARS = {"allineata": "r-gold", "parziale": "r-refl", "disallineata": "r-stag", "coerente": "r-gold", "contrario": "r-stag"}
RELATION_VARS = {"regolare": "r-gold", "più debole del solito": "r-refl", "rotta": "r-stag"}


def _num_it(x: float, digits: int = 2) -> str:
    return "n/d" if pd.isna(x) else f"{x:+.{digits}f}".replace(".", ",").replace("-", "−")


def murphy_color(label: str) -> str:
    return f"var(--{MURPHY_VARS.get(label, 'line')})"


def _big_state(text: str, color: str) -> str:
    return f'<h3 style="font-size:28px;line-height:32px;font-weight:800;letter-spacing:-0.02em;color:{color}">{escape(text)}</h3>'


def murphy_html(label: str, text: str, trends: list[tuple[str, float]], hist: pd.Series, month: pd.Timestamp) -> str:
    """label: 'Fase 1'..'Fase 6' o fase non definita. trends: (nome, distanza dalla media a 10 mesi). hist: etichette per mese."""
    chips = "".join(f'<span class="chip tint" style="--c:var(--{"r-gold" if d > 0 else "r-stag"})">{escape(n)} '
                    f'{"sopra" if d > 0 else "sotto"} la media <span class="mono">{_pct_it(d, 1)}</span></span>' for n, d in trends)
    legend = ('<div class="meta">' + "".join(f"<span>{_dot(murphy_color(k))} {k}</span>" for k in MURPHY_VARS)
              + f'<span>{_dot(murphy_color(""))} non definita</span></div>')
    color = murphy_color(label) if label in MURPHY_VARS else "var(--muted)"
    return (f'<div class="si card"><span class="eyebrow">Fase di Murphy · fine {month_it(month)}</span>'
            f'{_big_state(label, color)}<p>{escape(text)}</p><div style="display:flex;flex-wrap:wrap;gap:8px">{chips}</div>'
            f'<div><div class="rlabel">Ultimi 24 mesi</div>{ribbon_html(hist, murphy_color, 24)}</div>{legend}'
            '<p class="note">Obbligazioni (TLT), azioni (SPY) e materie prime (DBC) sopra o sotto la media a 10 mesi, a mese chiuso. '
            'Obbligazioni e materie prime nella stessa direzione, con le azioni contro, non sono una fase del ciclo.</p></div>')


def alignment_html(state: str | None, macro_phase: str | None, checks: list[tuple[str, str, str]], mapping: list[str],
                   message: str | None) -> str:
    """checks: (voce, valore, esito in CHECK_VARS). state None = fase del ciclo USA non disponibile."""
    rows = (f'<div class="row"><span class="grow">Fase del ciclo USA</span>'
            f'<b style="color:{phase_color(macro_phase)}">{escape(macro_phase or "n/d")}</b></div>'
            + "".join(f'<div class="row"><span class="grow">{escape(k)}</span><span>{escape(v)}</span>'
                      f'<span class="chip tint" style="--c:var(--{CHECK_VARS[c]})">{escape(c)}</span></div>' for k, v, c in checks))
    msg = f'<p style="color:var(--r-stag);font-weight:500">{escape(message)}</p>' if message else ""
    color = f"var(--{ALIGN_VARS.get(state, 'muted')})"
    return (f'<div class="si card"><span class="eyebrow">Allineamento macro / mercati</span>'
            f'{_big_state(state or "n/d", color)}<div class="list">{rows}</div>{msg}'
            f'<p class="note">Fasi di Murphy attese: {escape(" · ".join(mapping))}. Allineati = fase di Murphy e rame/oro '
            'confermano la fase del ciclo; disallineati = nessuno dei due; parzialmente = uno solo.</p></div>')


def relation_html(name: str, current: float, usual: float, state: str, book: str, divergence: str | None = None) -> str:
    chips = f'<span class="chip tint" style="--c:var(--{RELATION_VARS.get(state, "muted")})">{escape(state)}</span>'
    if divergence:
        chips += f'<span class="chip tint" style="--c:var(--r-stag)">{escape(divergence)}</span>'
    return (f'<div class="head"><h3 style="font-size:17px;font-weight:600">{escape(name)}</h3>'
            f'<span style="display:flex;gap:6px;flex-wrap:wrap">{chips}</span></div>'
            f'<div style="margin-top:8px"><span class="big">{_num_it(current)}</span> <span class="muted" style="font-size:13px">'
            f'correlazione a 120 giorni · norma {_num_it(usual)}</span></div><p class="note" style="margin-top:6px">{escape(book)}</p>')


def matrix_html(m: pd.DataFrame, breaks: pd.DataFrame, names: dict[str, str], refs: dict[str, str]) -> str:
    """m: intermarket.matrix(), colonne (riferimento, finestra o 'norma'); breaks: intermarket.matrix_breaks()."""
    groups = {ref: [c for c in m.columns if c[0] == ref] for ref in refs}
    head = ("<tr><th></th>" + "".join(f'<th class="sep" colspan="{len(cols)}">contro {escape(refs[ref])}</th>' for ref, cols in groups.items())
            + "</tr><tr><th></th>" + "".join(f'<th class="{"sep" if i == 0 else ""}">{"norma" if w == "norma" else f"{w} g"}</th>'
                                            for cols in groups.values() for i, (_, w) in enumerate(cols)) + "</tr>")

    def cell(t, c, first):
        v = m[c][t]
        cls = ["sep"] if first else []
        if c[1] == "norma":
            cls.append("n")
        elif bool(breaks[c][t]):
            cls.append("brk")
        return f'<td class="{" ".join(cls)}">{"·" if pd.isna(v) else _num_it(v)}</td>'

    rows = "".join(f'<tr><td>{escape(names.get(t, t))}</td>'
                   + "".join(cell(t, c, i == 0) for cols in groups.values() for i, c in enumerate(cols)) + "</tr>" for t in m.index)
    return (f'<div class="si card"><div class="head"><h3>Correlazioni</h3><span class="note">rendimenti giornalieri, finestre in giorni di borsa</span></div>'
            f'<div class="tbl"><table class="mtx">{head}{rows}</table></div>'
            '<p class="note">Norma = mediana della correlazione a 120 giorni negli ultimi 5 anni. In rosso = fuori dalla norma: '
            'segno opposto (se la norma è almeno ±0,2) o distanza oltre 0,5. Per i tassi conta la variazione giornaliera in punti.</p></div>')


def edge_html(title: str, table: pd.DataFrame, names: dict[str, str], top: list[str]) -> str:
    """table: intermarket.edge_table() di un gruppo di ticker; top: quelli in evidenza (intermarket.highlighted)."""
    head = "<tr><th></th><th>casi</th><th>media</th><th>mediana</th><th>sopra</th><th>t</th></tr>"
    rows = "".join(
        f'<tr class="{"top" if t in top else ""}"><td><b>{escape(t)}</b> <span class="muted">{escape(names.get(t, ""))}</span></td>'
        f'<td>{r.casi:.0f}</td><td>{_num_it(r.media)}%</td><td>{_num_it(r.mediana)}%</td><td>{r.sopra:.0f}%</td><td>{_num_it(r.t, 1)}</td></tr>'
        for t, r in table.iterrows())
    return f'<div class="si card"><h3>{escape(title)}</h3><div class="tbl"><table class="mtx">{head}{rows}</table></div></div>'
