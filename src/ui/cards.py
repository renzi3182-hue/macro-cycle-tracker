"""Blocchi HTML del redesign (st.html). Niente <svg>: st.html li rimuove, quindi grafici solo con div/CSS."""
from collections import Counter
from html import escape

import pandas as pd

from src.ui.overview import REGIME_COLORS, REGIMES

PHASES = ["Ripresa", "Espansione", "Rallentamento", "Recessione"]
WEIGHT_COLORS = ["#60A5FA", "#34D399", "#A78BFA", "#38BDF8", "#FBBF24", "#FB923C", "#F472B6", "#94A3B8", "#2DD4BF", "#E8B04B"]
MUTED = "#9AA6B8"
UP, DOWN = "#34D399", "#F87171"

CSS = """
<style>
[data-testid="stMetricValue"], .mc-mono { font-family: 'IBM Plex Mono', monospace; font-variant-numeric: tabular-nums; }
.mc-disp { font-family: 'Space Grotesk', sans-serif; }
.mc-muted { color: #9AA6B8; }
.mc-strip { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 10px; padding: 10px 14px; border-radius: 12px; background: #111827; border: 1px solid #1E2738; }
.mc-strip .t { font-size: 12px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: #9AA6B8; margin-right: 6px; }
.mc-chip { display: inline-flex; align-items: center; gap: 8px; padding: 5px 12px; border-radius: 999px; background: #1A2233; font-size: 13px; color: #E6EAF2; }
.mc-chip.o { background: transparent; border: 1px solid #243044; }
.mc-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; flex: none; }
.mc-hero { display: flex; flex-direction: column; gap: 10px; padding: 8px 0 4px; }
.mc-hero h1 { margin: 0; padding: 0; font: 600 clamp(34px, 5vw, 56px)/1.04 'Space Grotesk', sans-serif; letter-spacing: -0.03em; color: #E6EAF2; }
.mc-row { display: flex; flex-wrap: wrap; gap: 8px; }
.mc-card { padding: 22px; border-radius: 16px; background: #111827; border: 1px solid #1E2738; display: flex; flex-direction: column; gap: 12px; color: #E6EAF2; }
.mc-card h3 { margin: 0; padding: 0; font: 600 18px 'Space Grotesk', sans-serif; }
.mc-head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
.mc-head span { font-size: 12px; color: #9AA6B8; }
.mc-donut { position: relative; width: 240px; aspect-ratio: 1; margin: 6px auto; border-radius: 50%; }
.mc-donut::after { content: ""; position: absolute; inset: 30px; border-radius: 50%; background: #111827; }
.mc-donut .c { position: absolute; inset: 0; z-index: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.mc-donut .c b { font: 500 38px 'IBM Plex Mono', monospace; }
.mc-wrow { display: grid; grid-template-columns: 12px minmax(0, 1.4fr) minmax(40px, 1fr) 44px 36px; align-items: center; gap: 12px; min-height: 34px; font-size: 14px; }
.mc-sw { width: 10px; height: 10px; border-radius: 3px; }
.mc-track { height: 8px; border-radius: 4px; background: #1A2233; overflow: hidden; }
.mc-track i { display: block; height: 100%; border-radius: 4px; }
.mc-r { text-align: right; }
.mc-regime { margin: 0; padding: 0; font: 600 clamp(38px, 5vw, 52px)/1 'Space Grotesk', sans-serif; letter-spacing: -0.03em; }
.mc-steps { display: flex; flex-wrap: wrap; gap: 4px; }
.mc-steps span { padding: 4px 10px; border-radius: 6px; background: #1A2233; color: #9AA6B8; font-size: 13px; }
.mc-steps span.on { background: #FBBF24; color: #0B0F17; font-weight: 600; }
.mc-prow { display: grid; grid-template-columns: 104px minmax(0, 1fr) 44px; gap: 12px; align-items: center; font-size: 14px; }
.mc-meter { display: inline-flex; gap: 4px; vertical-align: middle; }
.mc-meter i { width: 26px; height: 10px; border-radius: 3px; background: #243044; }
.mc-ev { display: flex; align-items: center; gap: 14px; padding: 10px 12px; border-bottom: 1px solid #1E2738; font-size: 15px; }
.mc-ev:last-child { border-bottom: 0; }
.mc-ev .d { min-width: 64px; flex: none; white-space: nowrap; text-align: center; font: 500 17px 'IBM Plex Mono', monospace; }
.mc-ev.next { border: 1px solid rgba(124,184,255,.35); background: rgba(124,184,255,.08); border-radius: 12px; }
.mc-ev.next .d { height: 60px; border-radius: 12px; background: #7CB8FF; color: #0B0F17; display: flex; flex-direction: column; align-items: center; justify-content: center; font-size: 24px; line-height: 1; }
.mc-ev.next .d small { font: 600 11px 'IBM Plex Sans', sans-serif; }
.mc-cot { display: grid; grid-template-columns: minmax(70px, 1fr) minmax(60px, 2fr) 32px minmax(0, 1fr); gap: 12px; align-items: center; font-size: 14px; }
.mc-div { position: relative; height: 12px; border-radius: 6px; background: #1A2233; }
.mc-div::before { content: ""; position: absolute; left: 50%; top: -3px; width: 1px; height: 18px; background: #3A475C; }
.mc-div i { position: absolute; top: 0; height: 12px; }
.mc-srow { display: grid; grid-template-columns: 24px 56px minmax(0, 1fr) 44px; gap: 12px; align-items: center; }
.mc-pairs { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 12px; }
.mc-pair { padding: 14px; border-radius: 12px; background: #0E131D; border: 1px solid #243044; display: flex; flex-direction: column; gap: 8px; }
.mc-pair .tag { padding: 2px 8px; border-radius: 6px; font-size: 12px; font-weight: 700; }
.mc-scale { position: relative; height: 6px; border-radius: 3px; background: linear-gradient(90deg, #F87171 0 40%, #243044 40% 60%, #34D399 60%); }
.mc-scale i { position: absolute; top: -4px; width: 3px; height: 14px; border-radius: 2px; background: #E6EAF2; }
@media (max-width: 640px) {
  .mc-wrow { grid-template-columns: 12px minmax(0, 1fr) 44px 36px; }
  .mc-wrow .mc-track { display: none; }
  .mc-cot { grid-template-columns: minmax(70px, 1fr) minmax(60px, 2fr) 32px; }
  .mc-cot .lbl { display: none; }
}
</style>
"""


def prevailing_regime(regimes: dict[str, str]) -> tuple[str, int]:
    """Regime piu' frequente fra le aree e quante aree lo condividono (a parita' vince il primo in ordine d'area)."""
    return Counter(regimes.values()).most_common(1)[0]


def regime_streak(history: pd.Series | None) -> int:
    """Trimestri consecutivi, contando l'ultimo, nello stesso regime dell'ultimo trimestre."""
    if history is None or history.empty:
        return 0
    last, n = history.iloc[-1], 0
    for r in reversed(history.tolist()):
        if r != last:
            break
        n += 1
    return n


def weight_deltas(now: dict, prev: dict) -> dict:
    """Variazione in punti percentuali interi, per ogni asset del portafoglio attuale."""
    return {k: round(now[k]) - round(prev.get(k, 0)) for k in now}


def _dot(color: str) -> str:
    return f'<i class="mc-dot" style="background:{color}"></i>'


def _signed(d: float, fmt: str = "{:+.0f}") -> str:
    color = UP if d > 0 else DOWN if d < 0 else MUTED
    return f'<span class="mc-mono" style="color:{color}">{fmt.format(d).replace("-", "−")}</span>'


def changes_strip(items: list[tuple[str, str]]) -> str:
    """items: (colore pallino, testo html gia' sicuro)."""
    chips = "".join(f'<span class="mc-chip">{_dot(c)}{t}</span>' for c, t in items)
    return f'<div class="mc-strip"><span class="t">Dall\'ultimo aggiornamento</span>{chips}</div>'


def hero_html(regimes: dict[str, str]) -> str:
    regime, n = prevailing_regime(regimes)
    color = REGIME_COLORS.get(regime, MUTED)
    pills = "".join(f'<span class="mc-chip o">{_dot(REGIME_COLORS.get(r, MUTED))}{escape(a)}</span>' for a, r in regimes.items())
    return (
        f'<div class="mc-hero"><span class="mc-muted" style="font-size:13px">Regime prevalente, {n} aree su {len(regimes)}</span>'
        f'<h1>Il mondo è in <span style="color:{color}">{escape(regime)}</span></h1><div class="mc-row">{pills}</div></div>'
    )


def portfolio_html(weights: dict, deltas: dict | None, title: str, subtitle: str) -> str:
    items = sorted(weights.items(), key=lambda kv: -kv[1])
    colors = {k: WEIGHT_COLORS[i % len(WEIGHT_COLORS)] for i, (k, _) in enumerate(items)}
    stops, acc = [], 0.0
    for k, v in items:
        stops.append(f"{colors[k]} {acc:.2f}% {acc + v - 0.4:.2f}%, #111827 {acc + v - 0.4:.2f}% {acc + v:.2f}%")
        acc += v
    equity = sum(v for k, v in weights.items() if "Azionario" in k)
    top = items[0][1] or 1
    rows = "".join(
        f'<div class="mc-wrow"><span class="mc-sw" style="background:{colors[k]}"></span><span>{escape(k)}</span>'
        f'<div class="mc-track"><i style="width:{v / top * 100:.0f}%;background:{colors[k]}"></i></div>'
        f'<span class="mc-mono mc-r">{v:.0f}%</span>'
        f'<span class="mc-r" style="font-size:13px">{_signed(deltas[k]) if deltas else ""}</span></div>'
        for k, v in items
    )
    donut = (
        f'<div class="mc-donut" role="img" aria-label="Quota azionaria {equity:.0f}%" style="background:conic-gradient({", ".join(stops)})">'
        f'<div class="c"><b>{equity:.0f}<span class="mc-muted" style="font-size:20px">%</span></b><span class="mc-muted" style="font-size:13px">azionario</span></div></div>'
    )
    delta_note = "vs aggiornamento precedente" if deltas else ""
    return (
        f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px">'
        f'<div class="mc-card"><div class="mc-head"><h3>{escape(title)}</h3><span>{escape(subtitle)}</span></div>{donut}</div>'
        f'<div class="mc-card"><div class="mc-head"><h3>Pesi per asset class</h3><span>{delta_note}</span></div>{rows}</div></div>'
    )


def area_hero_html(area: str, regime: str, phase: str, streak_q: int, description: str) -> str:
    color = REGIME_COLORS.get(regime, MUTED)
    steps = "".join(f'<span class="{"on" if p == phase else ""}">{p}</span>' for p in PHASES)
    streak = f'<span class="mc-muted" style="font-size:16px">da <span class="mc-mono" style="color:#E6EAF2">{streak_q}</span> {"trimestre" if streak_q == 1 else "trimestri"}</span>' if streak_q else ""
    return (
        f'<div class="mc-card" style="background:linear-gradient(180deg,color-mix(in srgb,{color} 9%,transparent),transparent 60%),#111827;height:100%;box-sizing:border-box">'
        f'<span class="mc-muted" style="font-size:13px">Regime macro · {escape(area)}</span>'
        f'<div style="display:flex;flex-wrap:wrap;align-items:baseline;gap:16px"><p class="mc-regime" style="color:{color}">{escape(regime)}</p>{streak}</div>'
        f'<div style="display:flex;flex-wrap:wrap;align-items:center;gap:10px"><span class="mc-muted" style="font-size:14px">Fase del ciclo</span><div class="mc-steps">{steps}</div></div>'
        f'<p style="margin:0;font-size:15px;line-height:1.55;color:#C9D1DD">{description}</p></div>'
    )


def prob_html(probs: dict, note: str) -> str:
    rows = "".join(
        f'<div class="mc-prow"><span>{r}</span><div class="mc-track" style="height:10px"><i style="width:{p * 100:.0f}%;background:{REGIME_COLORS.get(r, MUTED)}"></i></div>'
        f'<span class="mc-mono mc-r">{p * 100:.0f}%</span></div>'
        for r, p in sorted(probs.items(), key=lambda x: -x[1])
    )
    return f'<div class="mc-card" style="height:100%;box-sizing:border-box"><div class="mc-head"><h3>Probabilità per regime</h3><span>{escape(note)}</span></div>{rows}</div>'


def risk_meter_html(level: str, score: int, total: int) -> str:
    color = {"Alto": DOWN, "Medio": "#FBBF24"}.get(level, UP)
    blocks = "".join(f'<i style="background:{color}"></i>' if k < score else "<i></i>" for k in range(total))
    return (
        f'<div class="mc-head"><h3 class="mc-disp" style="margin:0;font-size:18px">Indicatori anticipatori</h3>'
        f'<div style="display:flex;align-items:center;gap:10px;font-size:14px"><span class="mc-muted">Rischio</span>'
        f'<span class="mc-meter" role="img" aria-label="{score} segnali attivi su {total}">{blocks}</span>'
        f'<b style="color:{color}">{escape(level)} · {score}/{total}</b></div></div>'
    )


def events_html(events: list[dict]) -> str:
    """events: dict Evento, Data (Timestamp), giorni; gia' ordinati per data."""
    rows = []
    for i, e in enumerate(events):
        date = e["Data"].strftime("%d/%m/%Y")
        if i == 0:
            rows.append(
                f'<div class="mc-ev next"><div class="d"><span>{e["giorni"]}</span><small>{"giorno" if e["giorni"] == 1 else "giorni"}</small></div>'
                f'<div style="display:flex;flex-direction:column"><b style="font-weight:600">{escape(e["Evento"])}</b><span class="mc-mono mc-muted" style="font-size:13px">{date}</span></div></div>'
            )
        else:
            rows.append(
                f'<div class="mc-ev"><span class="d">{e["giorni"]} gg</span><span style="flex-grow:1">{escape(e["Evento"])}</span>'
                f'<span class="mc-mono mc-muted" style="font-size:13px">{date}</span></div>'
            )
    return f'<div class="mc-card"><h3>Prossimi eventi</h3>{"".join(rows)}</div>'


def cot_html(rows: list[dict], date: str) -> str:
    """rows: Mercato, Percentile 5 anni, Posizionamento."""
    out = []
    for r in rows:
        pct = r["Percentile 5 anni"]
        extreme = pct < 15 or pct > 85
        color = (DOWN if pct > 50 else UP) if extreme else MUTED
        left, width = (50, pct - 50) if pct >= 50 else (pct, 50 - pct)
        out.append(
            f'<span>{escape(r["Mercato"])}</span>'
            f'<div class="mc-div" role="img" aria-label="percentile {pct}"><i style="left:{left}%;width:{width}%;background:{color};border-radius:{"0 6px 6px 0" if pct >= 50 else "6px 0 0 6px"}"></i></div>'
            f'<span class="mc-mono mc-r">{pct}</span><span class="lbl" style="color:{color};font-weight:{600 if extreme else 400}">{escape(r["Posizionamento"])}</span>'
        )
    return (
        f'<div class="mc-card"><div class="mc-head"><h3>Posizionamento speculatori (COT)</h3><span>percentile 5 anni · dato del {escape(date)}</span></div>'
        f'<div class="mc-cot">{"".join(out)}</div>'
        '<span class="mc-muted" style="font-size:12px">Barra dal centro: a destra più long della media, a sinistra più short. Estremi (&lt;15 o &gt;85) evidenziati.</span></div>'
    )


def strength_html(scores: dict[str, int | None]) -> str:
    ranked = sorted(((c, s) for c, s in scores.items() if s is not None), key=lambda x: -x[1])
    rows = "".join(
        f'<div class="mc-srow"><span class="mc-mono mc-muted">{i}</span><b class="mc-disp" style="font-size:20px">{c}</b>'
        f'<div class="mc-track" style="height:14px"><i style="width:{s}%;background:{UP if s >= 60 else DOWN if s <= 40 else "#7CB8FF"}"></i></div>'
        f'<span class="mc-mono mc-r" style="font-size:20px">{s}</span></div>'
        for i, (c, s) in enumerate(ranked, 1)
    )
    return f'<div class="mc-card"><div class="mc-head"><h3>Classifica di forza</h3><span>1-100</span></div>{rows}</div>'


def pairs_html(rows: list[dict]) -> str:
    """rows: Coppia, Punteggio, Segnale (Buy/Sell/Neutra)."""
    tag = {"Buy": ("#34D399", "#0B0F17"), "Sell": ("#F87171", "#0B0F17")}
    cards = "".join(
        f'<div class="mc-pair" style="border-color:{tag[r["Segnale"]][0] if r["Segnale"] in tag else "#243044"}">'
        f'<div class="mc-head"><span class="mc-mono" style="font-size:16px;color:#E6EAF2">{escape(r["Coppia"])}</span>'
        f'<span class="tag" style="background:{tag.get(r["Segnale"], ("#1A2233",))[0]};color:{tag.get(r["Segnale"], ("", MUTED))[1]}">{escape(r["Segnale"]).upper()}</span></div>'
        f'<span class="mc-mono" style="font-size:28px">{r["Punteggio"]}</span>'
        f'<div class="mc-scale"><i style="left:{r["Punteggio"]}%"></i></div></div>'
        for r in rows
    )
    return f'<div class="mc-card"><div class="mc-head"><h3>Coppie</h3><span>Buy ≥ 60 · Sell ≤ 40</span></div><div class="mc-pairs">{cards}</div></div>'


def chips_html(items: list[str]) -> str:
    return '<div class="mc-row">' + "".join(f'<span class="mc-chip">{escape(i)}</span>' for i in items) + "</div>"

