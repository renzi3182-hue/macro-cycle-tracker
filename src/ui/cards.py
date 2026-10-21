"""Blocchi HTML dell'interfaccia (st.html). Colori solo da variabili CSS di theme.py, cosi' valgono in chiaro e scuro.
Niente <svg>: st.html li rimuove, quindi grafici solo con div/CSS."""
from collections import Counter
from html import escape
from math import cos, pi, sin

import pandas as pd

from src.classify.assess import label_regimes, run_start
from src.classify.cycle import PHASES
from src.classify.regime import REGIMES
from src.classify.risk import CANARY, LABELS as RISK_LABELS
from src.classify.score import STRONG, WEAK
from src.config.asset_allocation import PHASE_ASSETS
from src.ui.theme import DONUT_SLOTS, WAVE_AMPLITUDE, phase_color, regime_color

MONTHS = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
WEIGHT_VARS = ["accent", "r-gold", "r-defl", "r-refl", "r-stag", "muted"]
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



def level_var(v: float) -> str:
    """Colore di un valore 0-100 dove alto = bene: sotto 40 rosso, da 60 verde (come le fasce del Risk On/Off)."""
    return "r-gold" if v >= 60 else "r-stag" if v < 40 else "r-refl"



def stat_tile_html(href: str, eyebrow: str, value: int, total: int, state: str, color: str, bar: str, note: str) -> str:
    """Card in alto nella pagina Oggi: un numero su un totale, lo stato a parole e una barra; porta al dettaglio.
    `note` e' HTML gia' pronto."""
    return (
        f'<a class="card tile" href="{escape(href)}" target="_self"><span class="eyebrow">{escape(eyebrow)}</span>'
        f'<div class="total" style="border-top:0;padding-top:0;flex-wrap:wrap"><span class="big" style="font-size:44px;line-height:48px">{value}</span>'
        f'<span class="muted" style="font-size:16px">/{total}</span>'
        f'<span style="font-size:20px;font-weight:800;color:{color}">{escape(state)}</span></div>{bar}<p class="note">{note}</p></a>'
    )


def phase_bar_html(phases: dict[str, str | None]) -> str:
    """Un segmento per fase, largo quanto i paesi che ci stanno, nell'ordine di PHASES."""
    n = Counter(phases.values())
    return '<div class="seg">' + "".join(
        f'<i style="flex:{n[p]};background:{phase_color(p)}"></i>' for p in PHASES if n[p]) + "</div>"


def _assets(items: list[str]) -> str:
    return ", ".join(i.replace(" {paese}", "") for i in items)


def cycle_wave_html(phases: dict[str, str | None]) -> str:
    """Onda del ciclo (come wave_html) con un punto per paese, sparsi nel quarto della loro fase; etichette alternate
    sopra e sotto per non sovrapporsi. Sotto, per fase, quanti paesi e gli asset da pesare di piu' e di meno."""
    pts, cols = [], []
    for i, p in enumerate(PHASES):
        areas = [a for a, x in phases.items() if x == p]
        for j, area in enumerate(areas):
            x = 25 * i + 25 * (j + 1) / (len(areas) + 1)
            pos = f"left:{x:.1f}%;top:{50 - WAVE_AMPLITUDE * sin(2 * pi * x / 100):.1f}%"
            pts.append(f'<b style="{pos};background:{phase_color(p)}"></b><span class="wl{" dn" if j % 2 else ""}" style="{pos}">{escape(area)}</span>')
        good, bad = PHASE_ASSETS.get(p, ([], []))
        cols.append(
            f'<div style="{"" if areas else "opacity:.5"}"><b style="color:{phase_color(p)}">{escape(p)} · {len(areas)}</b>'
            f'<span style="color:var(--r-gold)">+ {escape(_assets(good))}</span><span style="color:var(--r-stag)">− {escape(_assets(bad))}</span></div>')
    label = ", ".join(f"{a}: {x}" for a, x in phases.items())
    return (f'<div class="wave many" role="img" aria-label="{escape(label)}"><div class="mid"><span>trend</span></div><i></i>{"".join(pts)}</div>'
            f'<div class="wave-l wave-a">{"".join(cols)}</div>')


MATRIX_ASSETS = ["Azionario", "Materie prime", "Oro", "Titoli di Stato"]


def asset_matrix_html(phases: dict[str, str | None]) -> str:
    """Paesi per riga (in ordine di fase), asset per colonna: freccia su = piu' peso, giu' = meno peso (PHASE_ASSETS),
    con l'aggettivo che distingue l'azionario (ciclico, difensivo)."""
    def cell(phase: str | None, asset: str) -> str:
        good, bad = PHASE_ASSETS.get(phase, ([], []))
        for items, mark, var in ((good, "▲", "r-gold"), (bad, "▼", "r-stag")):
            hit = next((i for i in items if i.startswith(asset)), None)
            if hit:
                extra = hit.replace("{paese}", "").removeprefix(asset).strip()
                return f'<span class="mx" style="--c:var(--{var})">{mark} {escape(extra)}</span>'
        return '<span class="mx"></span>'
    order = sorted(phases.items(), key=lambda kv: PHASES.index(kv[1]) if kv[1] in PHASES else len(PHASES))
    head = '<span></span><span class="ph"></span>' + "".join(f'<span class="eyebrow" style="text-align:center">{escape(a)}</span>' for a in MATRIX_ASSETS)
    rows = "".join(
        f'<b style="--c:{phase_color(p)}" title="{escape(p or "n/d")}">{escape(area)}</b><span class="mono ph" style="font-size:12px;color:{phase_color(p)}">{escape(p or "n/d")}</span>'
        + "".join(cell(p, a) for a in MATRIX_ASSETS) for area, p in order)
    return f'<div style="overflow-x:auto"><div class="mxg">{head}{rows}</div></div>'


def risk_explain_html(score: float, state: str, when: str, parts: list[tuple[str, str, float]], alarm: bool) -> str:
    """Spiega il punteggio Risk On/Off: la scala a cinque fasce con il segno sul valore, cosa misura e cosa non
    misura, le sei componenti e lo stato del canarino."""
    s = round(score)
    low = min(parts, key=lambda x: x[2])
    bands = "".join(f'<span class="{"on" if lab == state else ""}">{lo}<br>{escape(lab)}</span>'
                    for lo, lab in zip(range(0, 100, 20), RISK_LABELS))
    canary = ("<b style=\"color:var(--r-refl)\">in allarme</b>: le obbligazioni legate all'inflazione scendono, spesso prima "
              "delle tensioni sul resto del mercato" if alarm else "<b>tranquillo</b>: le obbligazioni legate all'inflazione tengono")
    return (
        f'<div class="si card"><span class="eyebrow">Cosa vuol dire {s}/100 · al {escape(when)}</span>'
        f'<div class="rscale"><div class="seg"><i style="background:var(--r-stag)"></i><i style="background:color-mix(in srgb,var(--r-stag) 45%,var(--raised))"></i>'
        f'<i style="background:var(--raised)"></i><i style="background:color-mix(in srgb,var(--r-gold) 45%,var(--raised))"></i><i style="background:var(--r-gold)"></i></div>'
        f'<b style="left:{s}%"></b></div><div class="rbands">{bands}</div>'
        f'<p class="say"><b>{s}</b> è la media di sei misure di calma dei mercati. Ognuna va da 0 (il momento più teso della '
        f'sua storia) a 100 (il più calmo): 50 è una giornata normale. Oggi: <b>{escape(state)}</b>. La misura più bassa '
        f'è <b>{escape(low[0].lower())}</b> ({low[2]:.0f}).</p>'
        '<p class="say">Dice <b>quanto può oscillare la borsa</b> nel mese dopo, non se salirà: dal 2012, sotto 20 l\'S&amp;P 500 '
        'ha oscillato al 29% annuo, sopra 60 all\'11-13%.</p>'
        f'<div>{bar_rows_html(parts)}</div>'
        f'<p class="note">Canarino {CANARY} {canary}. È anche la sesta misura del punteggio.</p></div>'
    )



def bar_rows_html(rows: list[tuple[str, str, float]]) -> str:
    """(etichetta, spiegazione, valore 0-100): una barra per riga, colorata con level_var."""
    return "".join(
        f'<div class="brow"><span>{escape(label)}</span><span class="mono">{v:.0f}</span><small>{escape(note)}</small>'
        f'<div class="track"><i style="width:{v:.0f}%;background:var(--{level_var(v)})"></i></div></div>'
        for label, note, v in rows
    )



def area_hero_html(a: dict, sentence: str, markets: tuple[int, int] | None = None) -> str:
    """markets: (asset tipici del regime in salita, asset con un ETF), da asset_allocation.confirmation."""
    color = regime_color(a["regime_label"])
    phase = a["phase"] or "n/d"
    end = a["month"]
    facts = [
        ("Fase del ciclo", f'<span style="color:{phase_color(a["phase"])}">{escape(phase)}</span>'),
        ("Regime da", f'{month_it(a["regime_since"])}<br><span class="muted" style="font-size:13px;font-weight:400">{duration_it(a["regime_since"], end)}</span>'),
        ("Solidità macro", escape(a["confidence"])),
        *([("Conferma mercati", f'{markets[0] / markets[1]:.0%}<br><span class="muted" style="font-size:13px;font-weight:400">'
                                f'asset tipici in salita ({markets[0]} su {markets[1]}): coerenza, non probabilità</span>')]
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


def trend_html(rows: list[tuple[str, str, float, float | None]], month: pd.Timestamp) -> str:
    """rows: (asset class, ticker, distanza % dalla media a 10 mesi, distanza il mese prima o None)."""
    def change(d: float, prev: float | None) -> str:
        if prev is None or pd.isna(prev) or (d > 0) == (prev > 0):
            return ""
        var = "r-gold" if d > 0 else "r-stag"
        return f'<span class="chip tint" style="--c:var(--{var})">{"rientra" if d > 0 else "esce"}</span>'
    items = "".join(
        f'<div class="row">{_dot("var(--r-gold)" if d > 0 else "var(--r-stag)")}<span class="grow">{escape(a)} '
        f'<span class="mono muted" style="font-size:12px">{escape(t)}</span></span>{change(d, prev)}'
        f'<span class="mono" style="color:var(--{"r-gold" if d > 0 else "r-stag"})">{f"{d:+.1f}".replace(".", ",").replace("-", "−")}%</span></div>'
        for a, t, d, prev in rows
    )
    changed = sum(1 for _, _, d, prev in rows if prev is not None and not pd.isna(prev) and (d > 0) != (prev > 0))
    return (f'<div class="si card"><div class="head"><h3>Tendenza</h3><span class="note">fine {month_it(month)}, prezzo vs media 10 mesi</span></div>'
            f'<p>{"Nessun cambio" if not changed else "1 cambio" if changed == 1 else f"{changed} cambi"} rispetto al mese prima.</p>'
            f'<div class="list">{items}</div>'
            '<p class="note">Rosso = sotto la media: con il filtro attivo quella quota va in cash. "Esce" e "rientra" = il segnale '
            'è cambiato a fine mese, l\'unico momento in cui il filtro chiede di fare qualcosa. Nel backtest 2000-2026 il filtro ha '
            'ridotto il drawdown massimo del 55-75% (60/40 da −31% a −13%) e il rendimento di 0,1-0,9 punti l\'anno: '
            'protegge nei crolli lunghi, perde nei rimbalzi veloci.</p></div>')


RELATION_VARS = {"regolare": "r-gold", "più debole del solito": "r-refl", "rotta": "r-stag"}


def _corr_it(x: float) -> str:
    return "n/d" if pd.isna(x) else f"{x:+.2f}".replace(".", ",").replace("-", "−")


def relations_html(rows: list[tuple[str, float, float, str, str]], when: str) -> str:
    """Le 4 relazioni chiave fra mercati (intermarket.RELATIONS), una riga ciascuna: (nome, correlazione a 120 giorni,
    norma degli ultimi 5 anni, stato, cosa dice la relazione). Descrizione del momento, non un segnale."""
    body = "".join(
        f'<div class="row" style="align-items:flex-start"><div class="grow"><b style="font-weight:600">{escape(name)}</b>'
        f'<small class="muted" style="display:block;font-size:12px;line-height:17px">{escape(book)}</small></div>'
        f'<span class="mono" style="white-space:nowrap;font-size:13px">{_corr_it(cur)} <span class="muted">· norma {_corr_it(usual)}</span></span>'
        f'<span class="chip tint" style="--c:var(--{RELATION_VARS.get(state, "muted")})">{escape(state)}</span></div>'
        for name, cur, usual, state, book in rows)
    return (f'<div class="si card"><div class="head"><h3>Come si muovono i mercati fra loro</h3><span class="note">al {escape(when)}</span></div>'
            f'<div class="list">{body}</div>'
            '<p class="note">Correlazione degli ultimi 120 giorni contro la sua norma (mediana di 5 anni): da −1 (opposti) a +1 '
            "(insieme). Regolare = come di solito. Più debole = stessa direzione, legame allentato. Rotta = al contrario del "
            "solito: quel mercato oggi è guidato da altro. Descrive il momento, non anticipa i rendimenti.</p></div>")


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


WHY_MIN = 0.01  # spinta minima (in log-odds) per nominare un pilastro


def why_text(contrib: dict[str, float]) -> str:
    """Perche' del punteggio: il pilastro che alza di piu' la probabilita' e quello che la abbassa di piu'
    (contrib: peso * posizione, da score.model)."""
    up, down = max(contrib, key=contrib.get), min(contrib, key=contrib.get)
    parts = ([f"spinge {up.lower()}"] if contrib[up] > WHY_MIN else []) + ([f"frena {down.lower()}"] if contrib[down] < -WHY_MIN else [])
    return " · ".join(parts) or "nessun pilastro si distingue"


def weights_html(weights: dict[str, float], month: pd.Timestamp) -> str:
    """Peso di ogni pilastro nella stima di oggi, in % del totale. Peso 0 = i dati non lo premiano."""
    total = sum(weights.values()) or 1.0
    rows = "".join(  # stesso markup di bar_rows_html, ma un solo colore: un peso basso non e' un segnale negativo
        f'<div class="brow"><span>{escape(k)}</span><span class="mono">{w / total:.0%}</span>'
        f'<small>{"escluso: nella storia non ha aiutato" if w <= 0 else ""}</small>'
        f'<div class="track"><i style="width:{max(w, 0) / total:.0%};background:var(--accent)"></i></div></div>'
        for k, w in weights.items())
    return (f'<div class="si card"><div class="head"><h3>Quanto conta ogni pilastro</h3><span class="note">stima di '
            f'{month_it(month)}</span></div><div>{rows}</div>'
            '<p class="note">I pesi li decidono i dati: ogni anno si ristimano solo sul passato, su quanto ogni pilastro '
            'ha anticipato chi batte la media a 3 mesi.</p></div>')


ACTIVE = '<b style="color:var(--r-gold)">Segnale attivo</b> · '


def ranking_html(rows: list[dict], month: pd.Timestamp, title: str = "Classifica", horizon: int = 3, note: str = "") -> str:
    """rows: ticker, nome, gruppo, punteggio, delta (vs mese prima o None), Tendenza (frazione), prob (0-1), attivo
    (segnale acceso), storico (serie mensile), perche' (testo di why_text). note: riga sotto il titolo."""
    head = (f'<div class="arow th"><span>#</span><span>Asset</span><span class="opt">Ultimi 12 mesi</span>'
            f'<span class="r opt">Tendenza</span><span class="r opt">Prob. {horizon}m</span><span class="r">Punt.</span><span class="r">Var.</span></div>')
    body = "".join(
        f'<div class="arow"><span class="mono muted">{i}</span>'
        f'<span style="min-width:0"><b style="font-weight:600">{escape(r["nome"])}</b> '
        f'<span class="mono muted" style="font-size:12px">{escape(r["ticker"])}<span class="opt"> · {escape(r["gruppo"])}</span></span>'
        f'<small class="muted" style="display:block;font-size:12px;line-height:16px">'
        f'{ACTIVE if r["attivo"] else ""}{escape(r["perche"])}</small></span>'
        f'<span class="opt">{ribbon_html(r["storico"], score_color, 12, thin=True, ticks=False)}</span>'
        f'<span class="mono r opt">{r["Tendenza"] * 100:+.1f}%</span><span class="mono r opt">{r["prob"] * 100:.0f}%</span>'
        f'<span class="r"><span class="chip tint mono" style="--c:{score_color(r["punteggio"])};font-weight:700">{r["punteggio"]:.0f}</span></span>'
        f'<span class="r" style="font-size:13px">{_signed(r["delta"]) if r["delta"] is not None else ""}</span></div>'
        for i, r in enumerate(rows, 1)
    )
    sub = f'<p class="note">{note}</p>' if note else ""
    return (f'<div class="si card"><div class="head"><h3>{escape(title)}</h3><span class="note">punteggio di fine {month_it(month)}, 1-100</span></div>'
            f'{sub}<div class="list">{head}{body}</div></div>')


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


def _months_it(n: int | None) -> str:
    return "non ancora" if n is None else "subito" if n == 0 else f"{n} {'mese' if n == 1 else 'mesi'}"


def lab_html(plain: dict, trend: dict | None) -> str:
    """plain/trend: summary() di src/classify/stress.py del portafoglio senza e con filtro di tendenza."""
    cols = [("Senza filtro", plain), *([("Con filtro di tendenza", trend)] if trend else [])]
    head = "".join(f"<th>{name}</th>" for name, _ in cols)
    rows = [("Oggi avresti", lambda x: f"{10000 * x['final']:,.0f} €".replace(",", ".")),
            ("Guadagno medio all'anno", lambda x: _pct_it(x["cagr"], 1)),
            ("Calo peggiore", lambda x: _pct_it(x["dd"])),
            ("Attesa più lunga per tornare in pari", lambda x: "mai sotto" if x["under"] == 0 else _months_it(x["under"]))]
    body = "".join(f"<tr><td>{label}</td>" + "".join(f"<td>{fmt(x)}</td>" for _, x in cols) + "</tr>" for label, fmt in rows)
    verdict = ""
    if trend:
        diff = (trend["cagr"] - plain["cagr"]) * 100
        verdict = (f'<p>Il filtro ha reso <b>{abs(diff):.1f} punti l\'anno {"in più" if diff >= 0 else "in meno"}</b>'.replace(".", ",", 1)
                   + f' e ha portato il calo peggiore da <b class="mono">{_pct_it(plain["dd"])}</b> a <b class="mono">{_pct_it(trend["dd"])}</b>.</p>')
    return (f'<div class="si card"><div class="head"><h3>Come sarebbe andata</h3><span class="note">da {month_it(plain["start"], True)} a oggi</span></div>'
            f'<p>Se a {month_it(plain["start"])} avessi messo <b>10.000 €</b> nel portafoglio qui a fianco:</p>'
            f'<div class="tbl"><table class="mtx"><tr><th></th>{head}</tr>{body}</table></div>{verdict}'
            '<p class="note">Calo peggiore = quanto sei sceso, al massimo, da un picco. Attesa più lunga = il periodo più lungo passato '
            'sotto un picco prima di superarlo. Il grafico sotto segue 100 € nel tempo. Ribilanciamento ogni mese, ETF in dollari, '
            'senza costi né tasse; il filtro sposta in cash (SHY) ogni ETF sotto la sua media a 10 mesi.</p></div>')


def stress_html(rows: list[tuple[str, str, tuple | None, tuple | None, tuple | None]], mc: dict | None, years: int, skipped: list[str]) -> str:
    """rows: (crisi, periodo, (rendimento, drawdown, mesi per recuperare) del portafoglio o None, idem con filtro, idem S&P 500).
    mc: percentile -> valore di 100."""
    def back(n: int | None) -> str:
        return "non ancora in pari" if n is None else "mai sotto la partenza" if n == 0 else f"in pari dopo {_months_it(n)}"

    def cell(x: tuple | None, bold: bool = False) -> str:
        if not x:
            return '<td class="n">nessun dato</td>'
        color = f' style="color:var(--{"r-gold" if x[0] >= 0 else "r-stag"})"' if bold else ""
        return f'<td{color}>{_pct_it(x[0])}<br><span class="muted" style="font-size:11px">{back(x[2])}</span></td>'
    body = "".join(f'<tr><td>{escape(name)}<br><span class="muted" style="font-size:12px">{escape(period)}</span></td>'
                   f"{cell(p, True)}{cell(t, True)}{cell(s)}</tr>" for name, period, p, t, s in rows)
    worst = min(((name, p, t) for name, _, p, t, _ in rows if p and t), key=lambda x: x[1][0], default=None)
    example = ""
    if worst:
        name, p, t = worst
        euro = lambda x: f"{10000 * (1 + x[0]):,.0f} €".replace(",", ".")
        example = (f'<p>Esempio, {escape(name.lower())}: con 10.000 € saresti arrivato a <b class="mono">{euro(p)}</b> '
                   f'senza filtro e a <b class="mono">{euro(t)}</b> con il filtro.</p>')
    band = (f'<p>Guardando avanti, fra {years} anni 100 € potrebbero diventare circa <b class="mono">{mc[50]:.0f}</b>: '
            f'<b class="mono">{mc[5]:.0f}</b> se va molto male, <b class="mono">{mc[95]:.0f}</b> se va molto bene.</p>' if mc else "")
    note = f" Esclusi perché senza ETF: {escape(', '.join(skipped))}." if skipped else ""
    return (f'<div class="si card"><div class="head"><h3>Grandi crolli</h3><span class="note">cosa sarebbe successo ai tuoi soldi</span></div>'
            f'<p>Le {len(rows)} grandi discese della borsa dal 2007. Per ognuna: <b>quanto avresti perso o guadagnato</b> (sopra) e <b>dopo quanto '
            'tempo saresti tornato alla cifra di partenza</b> (sotto).</p>'
            '<div class="tbl"><table class="mtx"><tr><th></th><th>Il tuo portafoglio</th><th>Con filtro di tendenza</th>'
            f'<th>Solo borsa USA</th></tr>{body}</table></div>{example}{band}'
            '<p class="note">Con filtro di tendenza = vendi ciò che scende sotto la sua media a 10 mesi e lo ricompri quando torna sopra: '
            'aiuta nei crolli lunghi, nei rimbalzi veloci ti fa ricomprare tardi. Solo borsa USA = tutto nell\'S&amp;P 500. '
            'Nessun dato = qualche fondo non esisteva ancora.Ogni classe usa il suo ETF (azionario = SPY, '
            'cash = SHY), ribilanciamento mensile, niente costi. La stima a 10 anni rimescola i mesi passati del portafoglio: '
            f'il passato non garantisce il futuro.{note}</p></div>')



