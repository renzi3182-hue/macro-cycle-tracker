"""Blocchi HTML del redesign (st.html). Niente <svg>: st.html li rimuove, quindi grafici solo con div/CSS."""
from collections import Counter
from html import escape
from math import cos, pi, sin

import pandas as pd

from src.ui.overview import REGIME_COLORS, REGIMES

PHASES = ["Ripresa", "Espansione", "Rallentamento", "Recessione"]
WEIGHT_COLORS = ["#5EEAD4", "#7BE0A4", "#8AB4FF", "#FFC878", "#FF9DA7", "#B8C4FF", "#FFA86B", "#8FA6B2", "#2DD4BF", "#C4A8FF"]
MUTED = "#8FA6B2"
UP, DOWN = "#7BE0A4", "#FF9DA7"

CSS = """
<style>
[data-testid="stMetricValue"], .mc-mono { font-family: 'DM Mono', monospace; font-variant-numeric: tabular-nums; }
.mc-disp { font-family: 'Plus Jakarta Sans', sans-serif; }
.mc-muted { color: #8FA6B2; }
.mc-strip { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 10px; padding: 10px 14px; border-radius: 12px; background: #172330; border: 1px solid #25384A; }
.mc-strip .t { font-size: 12px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: #8FA6B2; margin-right: 6px; }
.mc-chip { display: inline-flex; align-items: center; gap: 8px; padding: 5px 12px; border-radius: 999px; background: #1E2D3D; font-size: 13px; color: #EAF2F5; }
.mc-chip.o { background: transparent; border: 1px solid #25384A; }
.mc-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; flex: none; }
.mc-hero { display: flex; flex-direction: column; gap: 10px; padding: 8px 0 4px; }
.mc-hero h1 { margin: 0; padding: 0; font: 800 clamp(34px, 5vw, 56px)/1.04 'Plus Jakarta Sans', sans-serif; letter-spacing: -0.03em; color: #EAF2F5; }
.mc-row { display: flex; flex-wrap: wrap; gap: 8px; }
.mc-card { padding: 22px; border-radius: 18px; background: #172330; border: 1px solid #25384A; display: flex; flex-direction: column; gap: 12px; color: #EAF2F5; }
.mc-card h3 { margin: 0; padding: 0; font: 600 18px 'Plus Jakarta Sans', sans-serif; }
.mc-head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
.mc-head span { font-size: 12px; color: #8FA6B2; }
.mc-donut { position: relative; width: 240px; aspect-ratio: 1; margin: 6px auto; border-radius: 50%; }
.mc-donut .c { position: absolute; inset: 0; z-index: 2; pointer-events: none; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.mc-donut .c b { font: 500 38px 'DM Mono', monospace; }
.mc-donut .s { position: absolute; inset: 0; border-radius: 50%; transition: transform .15s; }
.mc-donut .s:hover { transform: scale(1.04); }
.mc-donut .hole { position: absolute; inset: 30px; border-radius: 50%; background: #172330; z-index: 1; }
.mc-donut .c.tip { display: none; padding: 0 48px; text-align: center; line-height: 1.25; }
.mc-donut:has(.s:hover) .c.def { display: none; }
.mc-donut:has(.s0:hover) .c.t0 { display: flex; }
.mc-donut:has(.s1:hover) .c.t1 { display: flex; }
.mc-donut:has(.s2:hover) .c.t2 { display: flex; }
.mc-donut:has(.s3:hover) .c.t3 { display: flex; }
.mc-donut:has(.s4:hover) .c.t4 { display: flex; }
.mc-donut:has(.s5:hover) .c.t5 { display: flex; }
.mc-donut:has(.s6:hover) .c.t6 { display: flex; }
.mc-donut:has(.s7:hover) .c.t7 { display: flex; }
.mc-donut:has(.s8:hover) .c.t8 { display: flex; }
.mc-donut:has(.s9:hover) .c.t9 { display: flex; }
.mc-donut:has(.s10:hover) .c.t10 { display: flex; }
.mc-donut:has(.s11:hover) .c.t11 { display: flex; }
.mc-wrow { display: grid; grid-template-columns: 12px minmax(0, 1.4fr) minmax(40px, 1fr) 44px 36px; align-items: center; gap: 12px; min-height: 34px; font-size: 14px; }
.mc-sw { width: 10px; height: 10px; border-radius: 3px; }
.mc-track { height: 8px; border-radius: 4px; background: #1E2D3D; overflow: hidden; }
.mc-track i { display: block; height: 100%; border-radius: 4px; }
.mc-r { text-align: right; }
.mc-regime { margin: 0; padding: 0; font: 800 clamp(38px, 5vw, 52px)/1 'Plus Jakarta Sans', sans-serif; letter-spacing: -0.03em; }
.mc-steps { display: flex; flex-wrap: wrap; gap: 4px; }
.mc-steps span { padding: 4px 10px; border-radius: 6px; background: #1E2D3D; color: #8FA6B2; font-size: 13px; }
.mc-steps span.on { background: #FFC878; color: #0F1720; font-weight: 600; }
.mc-prow { display: grid; grid-template-columns: 104px minmax(0, 1fr) 44px; gap: 12px; align-items: center; font-size: 14px; }
.mc-meter { display: inline-flex; gap: 4px; vertical-align: middle; }
.mc-meter i { width: 26px; height: 10px; border-radius: 3px; background: #25384A; }
.mc-ev { display: flex; align-items: center; gap: 14px; padding: 10px 12px; border-bottom: 1px solid #25384A; font-size: 15px; }
.mc-ev:last-child { border-bottom: 0; }
.mc-ev .d { min-width: 64px; flex: none; white-space: nowrap; text-align: center; font: 500 17px 'DM Mono', monospace; }
.mc-ev.next { border: 1px solid rgba(94,234,212,.35); background: rgba(94,234,212,.08); border-radius: 12px; }
.mc-ev.next .d { height: 60px; border-radius: 12px; background: #5EEAD4; color: #062B26; display: flex; flex-direction: column; align-items: center; justify-content: center; font-size: 24px; line-height: 1; }
.mc-ev.next .d small { font: 600 11px 'Plus Jakarta Sans', sans-serif; }
.mc-cot { display: grid; grid-template-columns: minmax(70px, 1fr) minmax(60px, 2fr) 32px minmax(0, 1fr); gap: 12px; align-items: center; font-size: 14px; }
.mc-cotg { grid-template-columns: minmax(84px, 1fr) minmax(60px, 2fr) 56px 44px; }
.mc-div { position: relative; height: 12px; border-radius: 6px; background: #1E2D3D; }
.mc-div::before { content: ""; position: absolute; left: 50%; top: -3px; width: 1px; height: 18px; background: #8FA6B2; }
.mc-div i { position: absolute; top: 0; height: 12px; }
.mc-srow { display: grid; grid-template-columns: 24px 56px minmax(0, 1fr) 44px; gap: 12px; align-items: center; }
.mc-pairs { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 12px; }
.mc-pair { padding: 14px; border-radius: 12px; background: #0F1720; border: 1px solid #25384A; display: flex; flex-direction: column; gap: 8px; }
.mc-pair .tag { padding: 2px 8px; border-radius: 6px; font-size: 12px; font-weight: 700; }
.mc-scale { position: relative; height: 6px; border-radius: 3px; background: linear-gradient(90deg, #FF9DA7 0 40%, #25384A 40% 60%, #7BE0A4 60%); }
.mc-scale i { position: absolute; top: -4px; width: 3px; height: 14px; border-radius: 2px; background: #EAF2F5; }
@media (max-width: 640px) {
  .mc-wrow { grid-template-columns: 12px minmax(0, 1fr) 44px 36px; }
  .mc-wrow .mc-track { display: none; }
  .mc-cot { grid-template-columns: minmax(70px, 1fr) minmax(60px, 2fr) 32px; }
  .mc-cot .lbl { display: none; }
}
.mc-cal h4 { margin: 14px 0 4px; padding: 0; font: 600 13px 'Plus Jakarta Sans', sans-serif; letter-spacing: .06em; text-transform: uppercase; color: #8FA6B2; }
.mc-cal h4:first-child { margin-top: 0; }
.mc-cal h4 b { color: #5EEAD4; margin-left: 8px; }
.mc-cal .r { display: grid; grid-template-columns: 48px 44px 10px minmax(0, 1fr) auto; align-items: center; gap: 12px; padding: 9px 4px; border-bottom: 1px solid #25384A; font-size: 14px; }
.mc-cal .r:last-child { border-bottom: 0; }
.mc-cal .r.holiday { opacity: .55; }
.mc-cal .v { font: 400 13px 'DM Mono', monospace; color: #8FA6B2; text-align: right; }
.mc-cal .v b { color: #EAF2F5; font-weight: 500; }
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
    equity = sum(v for k, v in weights.items() if "Azionario" in k)
    top = items[0][1] or 1
    rows = "".join(
        f'<div class="mc-wrow"><span class="mc-sw" style="background:{colors[k]}"></span><span>{escape(k)}</span>'
        f'<div class="mc-track"><i style="width:{v / top * 100:.0f}%;background:{colors[k]}"></i></div>'
        f'<span class="mc-mono mc-r">{v:.0f}%</span>'
        f'<span class="mc-r" style="font-size:13px">{_signed(deltas[k]) if deltas else ""}</span></div>'
        for k, v in items
    )
    segs, tips, acc = "", "", 0.0
    for i, (k, v) in enumerate(items):
        a0, a1 = acc / 100 * 2 * pi, max(acc + v - 0.4, acc) / 100 * 2 * pi
        n = max(int((a1 - a0) / 0.05), 1)
        pts = ["50% 50%"] + [f"{50 + 75 * sin(a0 + (a1 - a0) * j / n):.2f}% {50 - 75 * cos(a0 + (a1 - a0) * j / n):.2f}%" for j in range(n + 1)]
        segs += f'<div class="s s{i}" style="background:{colors[k]};clip-path:polygon({", ".join(pts)})"></div>'
        tips += (
            f'<div class="c tip t{i}"><b>{v:.0f}<span class="mc-muted" style="font-size:20px">%</span></b>'
            f'<span style="font-size:12px;color:{colors[k]}">{escape(k)}</span></div>'
        )
        acc += v
    donut = (
        f'<div class="mc-donut" role="img" aria-label="Quota azionaria {equity:.0f}%">{segs}<div class="hole"></div>'
        f'<div class="c def"><b>{equity:.0f}<span class="mc-muted" style="font-size:20px">%</span></b><span class="mc-muted" style="font-size:13px">azionario</span></div>{tips}</div>'
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
    streak = f'<span class="mc-muted" style="font-size:16px">da <span class="mc-mono" style="color:#EAF2F5">{streak_q}</span> {"trimestre" if streak_q == 1 else "trimestri"}</span>' if streak_q else ""
    return (
        f'<div class="mc-card" style="background:linear-gradient(180deg,color-mix(in srgb,{color} 9%,transparent),transparent 60%),#172330;height:100%;box-sizing:border-box">'
        f'<span class="mc-muted" style="font-size:13px">Regime macro · {escape(area)}</span>'
        f'<div style="display:flex;flex-wrap:wrap;align-items:baseline;gap:16px"><p class="mc-regime" style="color:{color}">{escape(regime)}</p>{streak}</div>'
        f'<div style="display:flex;flex-wrap:wrap;align-items:center;gap:10px"><span class="mc-muted" style="font-size:14px">Fase del ciclo</span><div class="mc-steps">{steps}</div></div>'
        f'<p style="margin:0;font-size:15px;line-height:1.55;color:#EAF2F5">{description}</p></div>'
    )


def prob_html(probs: dict, note: str) -> str:
    rows = "".join(
        f'<div class="mc-prow"><span>{r}</span><div class="mc-track" style="height:10px"><i style="width:{p * 100:.0f}%;background:{REGIME_COLORS.get(r, MUTED)}"></i></div>'
        f'<span class="mc-mono mc-r">{p * 100:.0f}%</span></div>'
        for r, p in sorted(probs.items(), key=lambda x: -x[1])
    )
    return f'<div class="mc-card" style="height:100%;box-sizing:border-box"><div class="mc-head"><h3>Probabilità per regime</h3><span>{escape(note)}</span></div>{rows}</div>'


def risk_meter_html(level: str, score: int, total: int) -> str:
    color = {"Alto": DOWN, "Medio": "#FFC878"}.get(level, UP)
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


def cot_groups_html(market: str, rows: list[dict], date: str) -> str:
    """rows: Categoria, Netto (% open interest), Variazione (punti, vs settimana prima), Percentile (5 anni). Solo informativo, nessun giudizio."""
    out = []
    for r in rows:
        pct = r["Percentile"]
        left, width = (50, pct - 50) if pct >= 50 else (pct, 50 - pct)
        out.append(
            f'<span>{escape(r["Categoria"])}</span>'
            f'<div class="mc-div" role="img" aria-label="percentile {pct}"><i style="left:{left}%;width:{width}%;background:#8FA6B2;border-radius:{"0 6px 6px 0" if pct >= 50 else "6px 0 0 6px"}"></i></div>'
            f'<span class="mc-mono mc-r">{r["Netto"]:+.1f}%</span><span class="mc-mono mc-r mc-muted">{r["Variazione"]:+.1f}</span>'
        )
    return (
        f'<div class="mc-card"><div class="mc-head"><h3>Posizioni per categoria: {escape(market)}</h3><span>dato del {escape(date)}</span></div>'
        f'<div class="mc-cot mc-cotg">{"".join(out)}</div>'
        '<span class="mc-muted" style="font-size:12px">Netto = long meno short in % dell open interest. Variazione in punti rispetto alla settimana prima. '
        'Barra dal centro: percentile sugli ultimi 5 anni (destra = più long del solito, sinistra = più short). '
        'Dealer/Produttori/Swap dealer sono in gran parte coperture, non scommesse direzionali. Dati CFTC (TFF e Disaggregated); private equity e sentiment non fanno parte del report.</span></div>'
    )


def strength_html(scores: dict[str, int | None]) -> str:
    ranked = sorted(((c, s) for c, s in scores.items() if s is not None), key=lambda x: -x[1])
    rows = "".join(
        f'<div class="mc-srow"><span class="mc-mono mc-muted">{i}</span><b class="mc-disp" style="font-size:20px">{c}</b>'
        f'<div class="mc-track" style="height:14px"><i style="width:{s}%;background:{UP if s >= 60 else DOWN if s <= 40 else "#5EEAD4"}"></i></div>'
        f'<span class="mc-mono mc-r" style="font-size:20px">{s}</span></div>'
        for i, (c, s) in enumerate(ranked, 1)
    )
    return f'<div class="mc-card"><div class="mc-head"><h3>Classifica di forza</h3><span>1-100</span></div>{rows}</div>'


def pairs_html(rows: list[dict]) -> str:
    """rows: Coppia, Punteggio, Segnale (Buy/Sell/Neutra)."""
    tag = {"Buy": ("#7BE0A4", "#0F1720"), "Sell": ("#FF9DA7", "#0F1720")}
    cards = "".join(
        f'<div class="mc-pair" style="border-color:{tag[r["Segnale"]][0] if r["Segnale"] in tag else "#25384A"}">'
        f'<div class="mc-head"><span class="mc-mono" style="font-size:16px;color:#EAF2F5">{escape(r["Coppia"])}</span>'
        f'<span class="tag" style="background:{tag.get(r["Segnale"], ("#1E2D3D",))[0]};color:{tag.get(r["Segnale"], ("", MUTED))[1]}">{escape(r["Segnale"]).upper()}</span></div>'
        f'<span class="mc-mono" style="font-size:28px">{r["Punteggio"]}</span>'
        f'<div class="mc-scale"><i style="left:{r["Punteggio"]}%"></i></div></div>'
        for r in rows
    )
    return f'<div class="mc-card"><div class="mc-head"><h3>Coppie</h3><span>Buy ≥ 60 · Sell ≤ 40</span></div><div class="mc-pairs">{cards}</div></div>'


def chips_html(items: list[str]) -> str:
    return '<div class="mc-row">' + "".join(f'<span class="mc-chip">{escape(i)}</span>' for i in items) + "</div>"



IMPACT_COLORS = {"High": "#FF9DA7", "Medium": "#FFC878", "Low": "#8FA6B2", "Holiday": "#25384A"}
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
        return '<div class="mc-card mc-cal"><span class="mc-muted">Nessun evento con questi filtri.</span></div>'
    out = []
    for day, rows in days.items():
        mark = "<b>oggi</b>" if day == today else ""
        out.append(f"<h4>{WEEKDAYS[day.weekday()]} {day:%d/%m}{mark}</h4>")
        for local, e in rows:
            color = IMPACT_COLORS.get(e["impact"], MUTED)
            values = " · ".join(
                f"{label} <b>{escape(v)}</b>" for label, v in (("atteso", e["forecast"]), ("prec.", e["previous"])) if v
            )
            out.append(
                f'<div class="r{" holiday" if e["impact"] == "Holiday" else ""}"><span class="mc-mono">{local:%H:%M}</span>'
                f'<span class="mc-chip o" style="padding:2px 8px;font-size:12px">{escape(e["country"])}</span>'
                f'<i class="mc-dot" style="background:{color}" title="Impatto {IMPACT_LABELS.get(e["impact"], e["impact"])}"></i>'
                f'<span>{escape(e["title"])}</span><span class="v">{values}</span></div>'
            )
    return f'<div class="mc-card mc-cal">{"".join(out)}</div>'
