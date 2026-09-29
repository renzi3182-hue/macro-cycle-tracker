from html import escape

import pandas as pd

REGIMES = ["Espansione", "Reflazione", "Stagflazione", "Deflazione"]
REGIME_COLORS = {"Espansione": "#34D399", "Reflazione": "#60A5FA", "Stagflazione": "#F87171", "Deflazione": "#A78BFA"}
SIGNAL_COLORS = {1: "#34D399", 0: "#FBBF24", -1: "#F87171"}
QUAD_EDGE = 0.5  # soglie di deadband che portano il punto sul bordo (le variazioni recenti sono quasi sempre < 0.5)
QUAD_FILL = 0.92  # frazione del semi-lato usata dal punto sul bordo
SIGNAL_EPS = 0.1  # variazione minima (punti %) sotto cui l'indicatore e' "neutro"

CSS = """
<style>
.ov { display: flex; flex-direction: column; gap: 16px; font-family: 'IBM Plex Sans', sans-serif; color: #E6EAF2; }
.ov * { box-sizing: border-box; }
.ov-cards { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }
.ov-card { background: #111827; border: 1px solid #1E2738; border-radius: 16px; padding: 18px; min-width: 0; }
.ov-card h4 { margin: 0; font-size: 12px; letter-spacing: .06em; text-transform: uppercase; color: #9AA6B8; }
.ov-rg { font-size: 18px; flex-wrap: wrap; font-weight: 800; margin: 8px 0 2px; display: flex; align-items: center; gap: 8px; }
.ov-ph { color: #9AA6B8; font-size: 13px; margin-bottom: 12px; }
.ov-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; flex: none; }
.ov-sb { display: flex; gap: 2px; height: 10px; }
.ov-sb i { display: block; height: 100%; border-radius: 2px; min-width: 2px; }
.ov-two { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr); gap: 12px; }
.ov h3 { margin: 0 0 12px; font: 600 18px 'Space Grotesk', sans-serif; }
.ov-heat { display: grid; grid-template-columns: 84px repeat(3, minmax(0, 1fr)); gap: 4px; font-size: 13px; }
.ov-heat .h { color: #9AA6B8; font-weight: 700; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; align-self: end; padding: 0 2px 2px; }
.ov-heat .c { border-radius: 6px; padding: 9px 6px; text-align: center; font-weight: 700; font-variant-numeric: tabular-nums; }
.ov-heat .n { align-self: center; font-weight: 700; }
.ov-legend { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: 12px; color: #9AA6B8; margin-top: 10px; }
.ov-legend span { display: inline-flex; gap: 6px; align-items: center; }
.ov-tl { display: grid; grid-template-columns: 52px 1fr; gap: 6px 10px; align-items: center; font-size: 12px; font-weight: 700; }
.ov-tl .bars { display: flex; height: 22px; gap: 2px; }
.ov-tl .bars i { display: block; height: 100%; flex: 1; border-radius: 3px; }
.ov-tl .axis { grid-column: 2; display: flex; justify-content: space-between; color: #9AA6B8; font-weight: 500; font-size: 11px; }
.ov-quad { position: relative; width: 100%; aspect-ratio: 1; max-width: 420px; margin: 0 auto; border-radius: 8px; overflow: hidden; }
.ov-quad .q { position: absolute; width: 50%; height: 50%; }
.ov-quad .ax-v { position: absolute; left: 50%; top: 0; bottom: 0; width: 1.5px; background: #1E2738; }
.ov-quad .ax-h { position: absolute; top: 50%; left: 0; right: 0; height: 1.5px; background: #1E2738; }
.ov-quad .ql { position: absolute; font-size: 11px; font-weight: 700; color: #9AA6B8; }
.ov-quad .pt { position: absolute; width: 16px; height: 16px; border-radius: 50%; border: 2.5px solid #111827; transform: translate(-50%, -50%); }
.ov-quad .pt b { position: absolute; left: 20px; top: 50%; transform: translateY(-50%); font-size: 12px; font-weight: 800; color: #E6EAF2; }
.ov-quad .pt b.l { left: auto; right: 20px; }
.ov-quad .pt b.u { left: 50%; top: -10px; transform: translateX(-50%); }
.ov-quad .pt b.d { left: 50%; top: 24px; transform: translateX(-50%); }
@media (max-width: 1100px) { .ov-cards { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 600px) { .ov-cards { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 900px) { .ov-two { grid-template-columns: 1fr; } }
</style>
"""


def _prob_bar(probs: dict | None) -> str:
    if not probs:
        return '<div class="ov-ph">Probabilita\' n/d</div>'
    label = ", ".join(f"{r} {probs[r] * 100:.0f}%" for r in REGIMES)
    segs = "".join(
        f'<i style="width:{probs[r] * 100:.1f}%;background:{REGIME_COLORS[r]}" title="{r} {probs[r] * 100:.0f}%"></i>'
        for r in REGIMES
    )
    return f'<div class="ov-sb" role="img" aria-label="{label}">{segs}</div>'


def _legend() -> str:
    return '<div class="ov-legend">' + "".join(
        f'<span><i class="ov-dot" style="background:{REGIME_COLORS[r]}"></i>{r}</span>' for r in REGIMES
    ) + "</div>"


def _quadrant(areas: list[dict]) -> str:
    # Div posizionati in %, non SVG: st.html rimuove i tag <svg>.
    def pct(v):
        return 50 + max(-QUAD_EDGE, min(QUAD_EDGE, v)) / QUAD_EDGE * 50 * QUAD_FILL

    corners = [("Reflazione", "top:6px;left:8px"), ("Espansione", "top:6px;right:8px"),
               ("Stagflazione", "bottom:6px;right:8px"), ("Deflazione", "bottom:6px;left:8px")]
    quads = [("Reflazione", "top:0;left:0"), ("Espansione", "top:0;left:50%"),
             ("Stagflazione", "top:50%;left:50%"), ("Deflazione", "top:50%;left:0")]
    out = ['<div class="ov-quad" role="img" aria-label="Quadrante crescita e inflazione">']
    out += [f'<div class="q" style="{pos};background:color-mix(in srgb,{REGIME_COLORS[r]} 12%,transparent)"></div>' for r, pos in quads]
    out.append('<div class="ax-v"></div><div class="ax-h"></div>')
    out += [f'<span class="ql" style="{pos}">{r}</span>' for r, pos in corners]
    out.append('<span class="ql" style="top:24px;left:calc(50% + 6px);font-weight:500">↑ crescita</span>')
    out.append('<span class="ql" style="top:calc(50% + 6px);right:8px;font-weight:500">inflazione →</span>')
    pts = []
    for a in sorted((a for a in areas if a.get("pos")), key=lambda a: a["pos"][0]):
        pts.append({"a": a, "x": pct(a["pos"][0]), "y": 100 - pct(a["pos"][1]), "cls": ""})
    for i, p in enumerate(pts):
        p["cls"] = p["cls"] or ("l" if p["x"] > 78 else "")
        # punti vicini: quello piu' in alto ha l'etichetta sopra, l'altro sotto
        for q in pts[:i]:
            if abs(p["x"] - q["x"]) < 14 and abs(p["y"] - q["y"]) < 8 and q["cls"] not in ("u", "d"):
                q["cls"], p["cls"] = ("d", "u") if p["y"] < q["y"] else ("u", "d")
    for p in pts:
        a = p["a"]
        tip = escape(f'{a["area"]}: {a["regime"]}, crescita {a["pos"][1]:+.1f}, inflazione {a["pos"][0]:+.1f} (in soglie di deadband)')
        out.append(
            f'<div class="pt" title="{tip}" style="left:{p["x"]:.1f}%;top:{p["y"]:.1f}%;background:{REGIME_COLORS.get(a["regime"], "#9AA6B8")}">'
            f'<b class="{p["cls"]}">{escape(a["code"])}</b></div>'
        )
    out.append("</div>")
    return "".join(out)


def _heatmap(areas: list[dict]) -> str:
    cells = ['<div class="h"></div>'] + [f'<div class="h">{h}</div>' for h in ("Crescita", "Inflazione", "Disoccup.")]
    for a in areas:
        cells.append(f'<div class="n">{escape(a["code"])}</div>')
        for label, value, sig in a["signals"]:
            if value is None:
                cells.append('<div class="c" style="background:#0B0F17;color:#9AA6B8">n/d</div>')
            else:
                color = SIGNAL_COLORS[sig]
                cells.append(
                    f'<div class="c" title="{escape(a["area"])} {label}" '
                    f'style="background:color-mix(in srgb,{color} 24%,#111827)">{value:.1f}%</div>'
                )
    legend = (
        '<div class="ov-legend">'
        f'<span><i class="ov-dot" style="background:{SIGNAL_COLORS[1]}"></i>favorevole</span>'
        f'<span><i class="ov-dot" style="background:{SIGNAL_COLORS[0]}"></i>neutro</span>'
        f'<span><i class="ov-dot" style="background:{SIGNAL_COLORS[-1]}"></i>sfavorevole</span>'
        "<span>colore = variazione vs media dei 3 rilevamenti precedenti</span></div>"
    )
    return f'<div class="ov-heat">{"".join(cells)}</div>{legend}'


def _timeline(areas: list[dict]) -> str:
    rows = []
    for a in areas:
        hist = a.get("history")
        if hist is None or hist.empty:
            continue
        bars = "".join(
            f'<i style="background:{REGIME_COLORS.get(r, "#9AA6B8")}" title="{d.strftime("%Y")} T{d.quarter}: {r}"></i>'
            for d, r in hist.items()
        )
        rows.append(f'<div>{escape(a["code"])}</div><div class="bars">{bars}</div>')
    if not rows:
        return '<div class="ov-ph">Storico n/d</div>'
    first = next(a["history"] for a in areas if a.get("history") is not None and not a["history"].empty)
    axis = f'<div class="axis"><span>{first.index[0].year} T{first.index[0].quarter}</span><span>ultimo trimestre</span></div>'
    return f'<div class="ov-tl">{"".join(rows)}{axis}</div>'


def signal(series: pd.Series, higher_is_good: bool) -> tuple[float | None, int]:
    """(ultimo valore, segnale +1/0/-1) dalla variazione rispetto alla media dei 3 rilevamenti precedenti."""
    if len(series) < 4:
        return (float(series.iloc[-1]) if len(series) else None), 0
    delta = series.iloc[-1] - series.iloc[-4:-1].mean()
    if abs(delta) < SIGNAL_EPS:
        return float(series.iloc[-1]), 0
    return float(series.iloc[-1]), 1 if (delta > 0) == higher_is_good else -1


def overview_html(areas: list[dict]) -> str:
    """areas: dict con area, code, regime, phase, probs|None, pos|None, signals [(label, value|None, sig)]*3, history|None."""
    def streak(a):
        n = a.get("streak") or 0
        return f' · da {n} trim.' if n else ""

    cards = "".join(
        f'<div class="ov-card"{" style=\"border-color:" + REGIME_COLORS.get(a["regime"], "#9AA6B8") + "\"" if a.get("changed") else ""}>'
        f'<h4>{escape(a["area"])}{" · cambiato" if a.get("changed") else ""}</h4>'
        f'<div class="ov-rg"><i class="ov-dot" style="background:{REGIME_COLORS.get(a["regime"], "#9AA6B8")}"></i>{escape(a["regime"])}</div>'
        f'<div class="ov-ph">Fase: {escape(a["phase"])}{streak(a)}</div>{_prob_bar(a.get("probs"))}</div>'
        for a in areas
    )
    return (
        CSS
        + f'<div class="ov"><div class="ov-cards">{cards}</div>'
        f'<div class="ov-two"><div class="ov-card"><h3>Segnali degli indicatori</h3>{_heatmap(areas)}</div>'
        f'<div class="ov-card"><h3>Quadrante crescita e inflazione</h3>{_quadrant(areas)}'
        '<div class="ov-legend"><span>bordo = mezza soglia di cambio direzione. Posizione = variazione recente; il regime ha memoria (deadband) e può stare in un altro quadrante</span></div></div></div>'
        f'<div class="ov-card"><h3>Storico regime, ultimi 5 anni</h3>{_timeline(areas)}{_legend()}</div></div>'
    )
