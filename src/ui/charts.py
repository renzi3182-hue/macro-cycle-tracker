"""Grafici della pagina Mondo e delle schede paese (plan-dashboard-paesi.md, sezioni 4 e 6): SVG inline generato qui,
colori solo da variabili CSS di theme.py. Animazioni in CSS (spente con prefers-reduced-motion) e, per i paesi che
scorrono sull'onda, ANIMATE_JS (Web Animations, da includere nella pagina): senza script o con prefers-reduced-motion
ogni paese sta gia' nella posizione di oggi. Niente SMIL: la timeline dell'SVG puo' restare ferma all'inizio."""
from html import escape
from math import hypot, pi, sin

import pandas as pd

from src.classify.allocation import CCY
from src.classify.cycle import PHASES
from src.config.asset_allocation import PHASE_ASSETS
from src.ui.cards import cap, label_phrase, month_it
from src.ui.theme import phase_color, regime_color

FLAGS = {"USA": "🇺🇸", "Eurozona": "🇪🇺", "Italia": "🇮🇹", "UK": "🇬🇧", "Giappone": "🇯🇵", "Canada": "🇨🇦",
         "Cina": "🇨🇳", "Australia": "🇦🇺", "India": "🇮🇳"}
CCY_SYMBOL = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CAD": "C$", "AUD": "A$", "CNY": "元", "INR": "₹"}
PHASE_SHORT = {"Ripresa (sotto trend)": "Ripresa"}

# Onda del ciclo: un periodo di sinusoide, un quarto per fase nell'ordine di PHASES (come cards.wave_html)
WAVE_W, WAVE_H, WAVE_A = 720, 300, 92
WAVE_MID = 160
PHASE_FULL_MONTHS = 12  # oltre questi mesi nella fase il paese sta in fondo al suo quarto
FLAG_R = 20
# Quadrante dei regimi: assi in unita' di regime.axis_positions, tagliati a +-QUAD_MAX
QUAD_S, QUAD_PAD, QUAD_MAX, BUBBLE_R = 360, 30, 1.8, 16
QUAD_STEP = 3  # coda: un punto ogni 3 mesi, i mesi intermedi fanno solo rumore
HEAT_FULL = 10.0  # % di distanza dalla media con il colore pieno nella mappa di calore
# I paesi scorrono sull'onda dalla posizione di 6 mesi fa (data-trail, coordinate dell'SVG) a quella di oggi
ANIMATE_JS = ("if(!matchMedia('(prefers-reduced-motion: reduce)').matches)document.querySelectorAll('.wc-c[data-trail]')"
              ".forEach(g=>g.animate(g.dataset.trail.split(' ').map(p=>{const[x,y]=p.split(',');"
              "return{transform:`translate(${x}px,${y}px)`}}),{duration:1500,easing:'ease-in-out'}))")


def pct_it(x: float, digits: int = 1) -> str:
    """+5,3% con il segno meno tipografico."""
    return f"{x:+.{digits}f}%".replace(".", ",").replace("-", "−")


def trend_var(positive: bool | None) -> str:
    return "muted" if positive is None else "r-gold" if positive else "r-stag"


def _wave_y(x: float) -> float:
    return WAVE_MID - WAVE_A * sin(2 * pi * x / WAVE_W)


def wave_x(phase: str, months: int) -> float:
    """Punto sull'onda: quarto della fase, piu' avanti quanti piu' mesi ci e' (fino a PHASE_FULL_MONTHS)."""
    f = min(max(months, 1), PHASE_FULL_MONTHS) / PHASE_FULL_MONTHS
    return WAVE_W * (PHASES.index(phase) + 0.12 + 0.76 * f) / 4


def _spread(xs: list[float], lo: float, hi: float, gap: float) -> list[float]:
    """Posizioni ordinate dentro [lo, hi] distanti almeno gap (o equidistanti se non ci stanno)."""
    if not xs:
        return []
    gap = min(gap, (hi - lo) / max(len(xs) - 1, 1))
    out = [max(lo, xs[0])]
    for x in xs[1:]:
        out.append(max(x, out[-1] + gap))
    out[-1] = min(out[-1], hi)
    for i in range(len(out) - 2, -1, -1):
        out[i] = min(out[i], out[i + 1] - gap)
    return out


def _wave_points(xa: float, xb: float) -> list[list[tuple[float, float]]]:
    """Tratto d'onda da xa a xb per la via piu' corta, spezzato dove passa il bordo (l'onda e' un ciclo)."""
    d = (xb - xa + WAVE_W / 2) % WAVE_W - WAVE_W / 2
    n = max(2, int(abs(d) / 6))
    parts, cur, prev = [], [], None
    for k in range(n + 1):
        x = (xa + d * k / n) % WAVE_W
        if prev is not None and abs(x - prev) > WAVE_W / 2:
            parts.append(cur)
            cur = []
        cur.append((x, _wave_y(x)))
        prev = x
    return [*parts, cur]


def _path(pts: list[tuple[float, float]], dx: float = 0, dy: float = 0) -> str:
    return "M" + " L".join(f"{x - dx:.1f} {y - dy:.1f}" for x, y in pts)


def world_cycle_html(countries: dict[str, dict]) -> str:
    """Onda del ciclo con i paesi sopra. countries: area -> {"trail": assess.phase_trail (dal piu' vecchio, l'ultimo
    e' oggi), "positive": stato della tendenza (exposure) o None, "regime": etichetta di regime}. Ogni paese e' una
    bandiera nel quarto della sua fase, con la scia tratteggiata da 6 mesi fa; il bordo ha il colore della tendenza.
    Sotto, per fase, i paesi e gli asset da pesare di piu' e di meno (PHASE_ASSETS)."""
    q = WAVE_W / 4
    now = {a: c for a, c in countries.items() if c.get("trail") and c["trail"][-1]["phase"] in PHASES}
    x_now = {}
    for i, p in enumerate(PHASES):
        here = sorted((a for a, c in now.items() if c["trail"][-1]["phase"] == p),
                      key=lambda a: wave_x(p, now[a]["trail"][-1]["months"]))
        xs = _spread([wave_x(p, now[a]["trail"][-1]["months"]) for a in here], q * i + 0.08 * q, q * (i + 1) - 0.08 * q, 2 * FLAG_R + 4)
        x_now.update(zip(here, xs))
    bands = "".join(
        f'<rect x="{q * i:.0f}" y="0" width="{q:.0f}" height="{WAVE_H}" style="fill:{phase_color(p)}" class="wc-band"/>'
        f'<text x="{q * i + q / 2:.0f}" y="22" text-anchor="middle" class="wc-ph" style="fill:{phase_color(p)}">'
        f'{escape(PHASE_SHORT.get(p, p))}</text>' for i, p in enumerate(PHASES))
    wave = _path([(x, _wave_y(x)) for x in range(0, WAVE_W + 1, 6)])
    trails, flags = [], []
    order = sorted(x_now, key=x_now.get)
    for j, a in enumerate(order):
        c, x = now[a], x_now[a]
        y = _wave_y(x)
        past = [wave_x(t["phase"], t["months"]) for t in c["trail"][:-1]]
        segs = []
        for xa, xb in zip(past, [*past[1:], x]):
            segs += _wave_points(xa, xb)
        if past:
            trails.append(f'<path d="{" ".join(_path(s) for s in segs if len(s) > 1)}" class="wc-trail"/>' + "".join(
                f'<circle cx="{px:.1f}" cy="{_wave_y(px):.1f}" r="3.5" class="wc-past" style="opacity:{0.35 + 0.3 * k}"/>'
                for k, px in enumerate(past)))
        motion = ""
        if past and len(segs) == len(past):  # nessun passaggio dal bordo: il paese scorre sulla scia
            pts = [pt for s in segs for pt in s][::2] + [(x, y)]
            motion = f' data-trail="{" ".join(f"{px:.1f},{py:.1f}" for px, py in pts)}"'
        t = c["trail"][-1]
        tip = (f'{a} · {t["phase"]} da {t["months"]} {"mese" if t["months"] == 1 else "mesi"} · '
               f'{c.get("regime") or "regime n/d"}' + ("" if c.get("positive") is None else
                                                      f' · tendenza {"positiva" if c["positive"] else "negativa"}'))
        ly = -FLAG_R - 9 if j % 2 == 0 else FLAG_R + 19
        flags.append(
            f'<g class="wc-c" transform="translate({x:.1f} {y:.1f})"{motion}><title>{escape(tip)}</title>'
            f'<circle r="{FLAG_R}" class="wc-ring" style="stroke:var(--{trend_var(c.get("positive"))})"/>'
            f'<text class="wc-flag" text-anchor="middle" dy="7">{FLAGS.get(a, "")}</text>'
            f'<text class="wc-lbl" text-anchor="middle" y="{ly}">{escape(a)}</text></g>')
    cols = []
    for p in PHASES:
        here = [a for a in order if now[a]["trail"][-1]["phase"] == p]
        good, bad = PHASE_ASSETS.get(p, ([], []))
        names = "".join(f'<span>{FLAGS.get(a, "")} {escape(a)}</span>' for a in here) or '<span class="muted">nessun paese</span>'
        cols.append(f'<div><b style="color:{phase_color(p)}">{escape(PHASE_SHORT.get(p, p))} · {len(here)}</b>{names}'
                    f'<span class="wc-as" style="color:var(--r-gold)">+ {escape(_assets(good))}</span>'
                    f'<span class="wc-as" style="color:var(--r-stag)">− {escape(_assets(bad))}</span></div>')
    label = "; ".join(f'{a}: {now[a]["trail"][-1]["phase"]}' for a in order)
    return (f'<div class="wc"><svg viewBox="0 0 {WAVE_W} {WAVE_H}" role="img" aria-label="Fase del ciclo per paese: '
            f'{escape(label)}">{bands}<line x1="0" x2="{WAVE_W}" y1="{WAVE_MID}" y2="{WAVE_MID}" class="wc-mid"/>'
            f'<path d="{wave}" class="wc-glow"/><path d="{wave}" class="wc-wave"/>{"".join(trails)}{"".join(flags)}</svg>'
            f'<div class="wc-l">{"".join(cols)}</div>'
            '<p class="note">Posizione nella fase: più a destra = da più mesi. Tratteggio = dove era il paese 6 e 3 '
            'mesi fa. Linea tratteggiata = crescita al suo trend. Bordo verde o rosso = tendenza della borsa positiva o negativa.</p></div>')


def _assets(items: list[str]) -> str:
    return ", ".join(i.replace(" {paese}", "") for i in items) or "nessuno"


def _quad_xy(x: float, y: float) -> tuple[float, float]:
    k = (QUAD_S / 2 - QUAD_PAD - BUBBLE_R) / QUAD_MAX
    clip = lambda v: max(-QUAD_MAX, min(QUAD_MAX, v))
    return QUAD_S / 2 + clip(x) * k, QUAD_S / 2 - clip(y) * k


def _separate(pts: dict[str, list[float]], dist: float, rounds: int = 40) -> None:
    """Allontana le bolle sovrapposte (solo per il disegno; la coda resta sui valori veri)."""
    keys = list(pts)
    for _ in range(rounds):
        moved = False
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                (xa, ya), (xb, yb) = pts[a], pts[b]
                d = hypot(xb - xa, yb - ya)
                if d < dist:
                    ux, uy = ((xb - xa) / d, (yb - ya) / d) if d > 1e-6 else (1.0, 0.0)
                    push = (dist - d) / 2
                    pts[a] = [xa - ux * push, ya - uy * push]
                    pts[b] = [xb + ux * push, yb + uy * push]
                    moved = True
        if not moved:
            return


def regime_quadrant_html(countries: dict[str, dict]) -> str:
    """Quadrante dei regimi: crescita in orizzontale, inflazione in verticale (regime.axis_positions, 0 = soglia).
    countries: area -> {"trail": assess.axis_trail (dal piu' vecchio), "label": etichetta di regime}. Bolla con la
    bandiera e coda degli ultimi mesi; bordo tratteggiato se l'etichetta e' "Incerto"."""
    c0, lo, hi = QUAD_S / 2, QUAD_PAD, QUAD_S - QUAD_PAD
    corners = {"Stagflazione": (lo, lo, "start", 1), "Reflazione": (hi, lo, "end", 1),
               "Deflazione": (lo, hi, "start", -1), "Goldilocks": (hi, hi, "end", -1)}
    quads = "".join(
        f'<rect x="{min(x, c0):.0f}" y="{min(y, c0):.0f}" width="{c0 - lo:.0f}" height="{c0 - lo:.0f}" class="rq-band" '
        f'style="fill:{regime_color(r)}"/><text x="{x + (8 if anchor == "start" else -8):.0f}" '
        f'y="{y + (18 if s > 0 else -10):.0f}" text-anchor="{anchor}" class="rq-name" style="fill:{regime_color(r)}">'
        f'{escape(r)}</text>' for r, (x, y, anchor, s) in corners.items())
    axes = (f'<line x1="{lo}" x2="{hi}" y1="{c0}" y2="{c0}" class="rq-axis"/><line x1="{c0}" x2="{c0}" y1="{lo}" '
            f'y2="{hi}" class="rq-axis"/><text x="{hi}" y="{hi + 20}" text-anchor="end" class="rq-ax">crescita →</text>'
            f'<text x="{lo}" y="{lo - 10}" class="rq-ax">inflazione ↑</text>')
    have = {a: c for a, c in countries.items() if c.get("trail")}
    pos = {a: list(_quad_xy(c["trail"][-1]["x"], c["trail"][-1]["y"])) for a, c in have.items()}
    _separate(pos, 2 * BUBBLE_R + 2)
    tails, bubbles = [], []
    for a, c in have.items():
        color = regime_color(c["trail"][-1]["regime"])
        past = c["trail"][-1 - QUAD_STEP::-QUAD_STEP][::-1]
        pts = [_quad_xy(t["x"], t["y"]) for t in past] + [tuple(pos[a])]
        if len(pts) > 1:
            tails.append(f'<path d="{_path(pts)}" pathLength="1" class="rq-tail" style="stroke:{color}"/>' + "".join(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" class="rq-past" style="fill:{color}"/>' for x, y in pts[:-1]))
        label = c.get("label") or c["trail"][-1]["regime"]
        unc = " unc" if label.startswith("Incerto") else ""
        bubbles.append(
            f'<g class="rq-b{unc}" transform="translate({pos[a][0]:.1f} {pos[a][1]:.1f})"><title>{escape(a)} · '
            f'{escape(label)} · {escape(label_phrase(label))}</title><circle r="{BUBBLE_R}" style="stroke:{color}"/>'
            f'<text text-anchor="middle" dy="6">{FLAGS.get(a, "")}</text></g>')
    label = "; ".join(f'{a}: {c.get("label") or c["trail"][-1]["regime"]}' for a, c in have.items())
    return (f'<div class="rq"><svg viewBox="0 0 {QUAD_S} {QUAD_S}" role="img" aria-label="Regime per paese: '
            f'{escape(label)}">{quads}{axes}{"".join(tails)}{"".join(bubbles)}</svg>'
            '<p class="note">Coda = ultimi 6 mesi. Bordo tratteggiato = vicino alla soglia, la lettura può cambiare.</p></div>')


def mini_wave_svg(phase: str | None) -> str:
    """Onda piccola con il punto della fase, per le schede paese."""
    w, h, a, mid = 120, 36, 13, 18
    d = "M" + " L".join(f"{x} {mid - a * sin(2 * pi * x / w):.1f}" for x in range(0, w + 1, 4))
    dot = ""
    if phase in PHASES:
        x = w * (PHASES.index(phase) + 0.5) / 4
        dot = f'<circle cx="{x}" cy="{mid - a * sin(2 * pi * x / w):.1f}" r="4.5" style="fill:{phase_color(phase)}"/>'
    return f'<svg class="mw" viewBox="0 0 {w} {h}" aria-hidden="true"><path d="{d}"/>{dot}</svg>'


def country_card_html(c: dict, i: int = 0) -> str:
    """Scheda in vetro di un paese per la griglia della pagina Mondo. c: area, href, trend (exposure.summary o None),
    regime (etichetta), phase, ccy_up (valuta in rafforzamento: True/False/None), assets [(nome, sopra la media)],
    change (frase o None). i: posizione, per l'ingresso in sequenza."""
    a, t = c["area"], c.get("trend")
    ccy = CCY.get(a, "")
    arrow = {True: ("▲", "r-gold"), False: ("▼", "r-stag")}.get(c.get("ccy_up"), ("", "muted"))
    if t:
        state = (f'<div class="cc-state" style="--c:var(--{trend_var(t["positive"])})"><i></i>{escape(t["label"])}</div>'
                 f'<div class="cc-sub"><span class="mono">{pct_it(t["dist_pct"])}</span> dalla media a 10 mesi · da '
                 f'{escape(month_it(_month(t["since"]), short=True))}'
                 + (' <span class="chip tint" style="--c:var(--r-refl)">vicina alla media</span>' if t["near"] else "")
                 + "</div>" + strip_html(t["history"][-12:]))
    else:
        state = '<div class="cc-state" style="--c:var(--muted)"><i></i>Tendenza n/d</div>'
    regime = c.get("regime")
    chips = "".join(f'<span class="chip tint" style="--c:var(--{trend_var(up) if up else "muted"})">{escape(n)}</span>'
                    for n, up in c.get("assets", []))
    change = f'<p class="cc-ch">{escape(c["change"])}</p>' if c.get("change") else ""
    return (
        f'<a class="si card tile cc" href="{escape(c["href"])}" target="_self" style="--i:{i}">'
        f'<div class="cc-top"><span class="cc-flag">{FLAGS.get(a, "")}</span><h3>{escape(a)}</h3>'
        f'<span class="chip cc-ccy">{escape(CCY_SYMBOL.get(ccy, ""))} {escape(ccy)}'
        f'{f" <b style=\"color:var(--{arrow[1]})\">{arrow[0]}</b>" if arrow[0] else ""}</span></div>{state}'
        f'<div class="cc-mid"><div><span class="eyebrow">Regime</span><b style="color:{regime_color(_first(regime))}">'
        f'{escape(cap(label_phrase(regime)) if regime else "n/d")}</b></div>'
        f'<div><span class="eyebrow">Fase · {escape(PHASE_SHORT.get(c.get("phase"), c.get("phase") or "n/d"))}</span>'
        f'{mini_wave_svg(c.get("phase"))}</div></div>'
        + (f'<div class="cc-chips">{chips}</div>' if chips else "") + f"{change}</a>")


def _first(label: str | None) -> str:
    return label.removeprefix("Incerto: ").split(" / ")[0] if label else ""


def _month(ym: str) -> pd.Timestamp:
    return pd.Timestamp(f"{ym}-01")


def strip_html(history: list[dict]) -> str:
    """Striscia degli ultimi mesi: una tacca per mese, verde sopra la media e rossa sotto."""
    cells = "".join(f'<i title="{escape(h["month"])}: {pct_it(h["dist_pct"])}" style="background:var(--'
                    f'{trend_var(h["positive"])})"></i>' for h in history)
    return f'<div class="cc-strip" aria-hidden="true">{cells}</div>'


def heatmap_html(rows: dict[str, dict[str, float | None]], cols: list[str], month) -> str:
    """Mappa di calore paesi x classi di asset: distanza in % dalla media a 10 mesi, verde sopra e rosso sotto,
    piu' intenso fino a HEAT_FULL. rows: area -> {colonna: distanza o None}."""
    def cell(v: float | None) -> str:
        if v is None:
            return '<span class="hm-c hm-na">–</span>'
        k = 12 + 58 * min(abs(v) / HEAT_FULL, 1)
        return (f'<span class="hm-c mono" style="background:color-mix(in srgb,var(--{trend_var(v >= 0)}) {k:.0f}%,'
                f'var(--surface))">{pct_it(v)}</span>')
    head = '<span></span>' + "".join(f'<span class="eyebrow hm-h">{escape(c)}</span>' for c in cols)
    body = "".join(f'<b class="hm-a"><span>{FLAGS.get(a, "")}</span> {escape(a)}</b>' + "".join(cell(r.get(c)) for c in cols)
                   for a, r in rows.items())
    return (f'<div class="hm" style="--n:{len(cols)}">{head}{body}</div>'
            f'<p class="note">Distanza dalla media a 10 mesi a fine {escape(month_it(month))}. Verde sopra, '
            'rosso sotto; più intenso più è lontano.</p>')



def world_hero_html(eyebrow: str, title: str, lead: str) -> str:
    """Testata della pagina Mondo: onde di vetro (public/media/onde-*, fal.ai) come sfondo fermo; il video lo aggiunge
    public/index.html solo senza prefers-reduced-motion e senza risparmio dati. lead: html gia' sicuro."""
    return (f'<div class="wh"><video class="wh-v" muted loop playsinline preload="none" aria-hidden="true"></video>'
            f'<div class="hero wh-t"><span class="eyebrow">{escape(eyebrow)}</span><h1>{escape(title)}</h1>'
            f'<p class="lead">{lead}</p></div></div>')


TREND_SAY = {True: "Storicamente, chi seguiva la regola restava investito.",
             False: "Storicamente, chi seguiva la regola spostava questa parte in liquidità. Sullo storico ha dimezzato "
                    "le perdite grandi; dal 2019 è costato circa 4 punti l'anno."}


def country_hero_html(area: str, trend: dict | None, month) -> str:
    """Testata della pagina Paese: simbolo della valuta in vetro (public/media/valuta-*, fal.ai), bandiera, nome e
    stato della tendenza grande con la sua frase. trend: exposure.summary o None; month: mese della lettura o None."""
    ccy = CCY.get(area, "")
    img = (f'<img class="ph-i" src="/media/valuta-{ccy.lower()}.webp" alt="" width="480" height="480" decoding="async">'
           if ccy else "")
    eyebrow = f"Paese · lettura di {month_it(month)}" if month is not None else "Paese"
    if trend:
        side = "sopra" if trend["positive"] else "sotto"
        state = (f'<div class="ph-s" style="--c:var(--{trend_var(trend["positive"])})"><i></i>{escape(trend["label"])}'
                 + (' <span class="chip tint" style="--c:var(--r-refl)">vicina alla media</span>' if trend["near"] else "")
                 + "</div>"
                 f'<p class="lead">La borsa {escape(area)} è {side} la media a 10 mesi da '
                 f'{escape(month_it(_month(trend["since"])))} (<span class="mono">{pct_it(trend["dist_pct"])}</span>). '
                 f'{escape(TREND_SAY[trend["positive"]])}</p>' + strip_html(trend["history"][-12:]))
    else:
        state = '<div class="ph-s" style="--c:var(--muted)"><i></i>Tendenza n/d</div>'
    return (f'<div class="ph">{img}<div class="hero ph-t"><span class="eyebrow">{escape(eyebrow)}</span>'
            f'<h1><span class="ph-f">{FLAGS.get(area, "")}</span> {escape(area)} '
            f'<span class="chip">{escape(CCY_SYMBOL.get(ccy, ""))} {escape(ccy)}</span></h1>{state}</div></div>')
