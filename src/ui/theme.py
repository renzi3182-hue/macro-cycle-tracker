"""Token del design system Soft Glass (artifact NFSg6TDRqqdXEJp3C7hGTx, tokens.json) e CSS dei blocchi HTML.

I componenti in cards.py usano solo variabili CSS (var(--fg), var(--r-gold)...): il tema chiaro o scuro
si sceglie qui una volta, in base a st.context.theme.type, e i colori dei widget nativi vengono da
.streamlit/config.toml con gli stessi valori."""

TOKENS = {
    "dark": {
        "bg": "#0F1720", "surface": "#172330", "raised": "#1E2D3D", "fg": "#EAF2F5", "muted": "#8FA6B2",
        "line": "#25384A", "accent": "#5EEAD4", "on-accent": "#062B26",
        "r-gold": "#7BE0A4", "r-defl": "#8AB4FF", "r-refl": "#FFC878", "r-stag": "#FF9DA7",
        "shadow": "0 8px 24px rgba(0,0,0,.35)",
    },
    "light": {
        "bg": "#F3F8F8", "surface": "#FFFFFF", "raised": "#E6F0F1", "fg": "#0F1720", "muted": "#4F6472",
        "line": "#D3E2E6", "accent": "#0A7F70", "on-accent": "#FFFFFF",
        "r-gold": "#177A4D", "r-defl": "#2F6DB5", "r-refl": "#8F5A05", "r-stag": "#C0394B",
        "shadow": "0 4px 16px rgba(15,23,32,.08)",
    },
}

REGIME_VARS = {"Goldilocks": "r-gold", "Reflazione": "r-refl", "Stagflazione": "r-stag", "Deflazione": "r-defl"}
PHASE_VARS = {"Espansione": "r-gold", "Ripresa": "accent", "Rallentamento": "r-refl", "Recessione": "r-stag"}


def regime_color(regime: str) -> str:
    return f"var(--{REGIME_VARS.get(regime, 'muted')})"


def phase_color(phase: str | None) -> str:
    return f"var(--{PHASE_VARS.get(phase, 'muted')})"


def hex_color(mode: str, token: str) -> str:
    """Valore esadecimale di un token, per i componenti che non leggono variabili CSS (grafici)."""
    return TOKENS.get(mode, TOKENS["dark"])[token]


_CSS = """
.si { font-family: 'Plus Jakarta Sans', system-ui, sans-serif; color: var(--fg); }
.si * { box-sizing: border-box; }
.si .mono, [data-testid="stMetricValue"] { font-family: 'DM Mono', ui-monospace, monospace; font-variant-numeric: tabular-nums; }
.si .muted { color: var(--muted); }
.si .eyebrow { font-size: 11px; line-height: 14px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
.si .dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; flex: none; }
.si h1, .si h2, .si h3, .si p { margin: 0; padding: 0; }
.si .card { background: var(--surface); border: 1px solid var(--line); border-radius: 18px; padding: 24px; display: flex; flex-direction: column; gap: 14px; min-width: 0; box-shadow: var(--shadow); }
.si .card h3 { font-size: 17px; line-height: 24px; font-weight: 600; letter-spacing: -0.01em; }
.si .head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.si .grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fill, minmax(232px, 1fr)); }
.si .two { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }
.si .chip { display: inline-flex; align-items: center; gap: 7px; padding: 4px 11px; border-radius: 999px; font-size: 13px; font-weight: 500; background: var(--raised); color: var(--fg); white-space: nowrap; }
.si .chip.tint { background: color-mix(in srgb, var(--c) 16%, transparent); color: var(--c); }
.si .note { font-size: 13px; line-height: 19px; color: var(--muted); }

/* hero */
.si .hero { display: flex; flex-direction: column; gap: 8px; padding: 12px 0 8px; }
.si .hero h1 { font-size: clamp(32px, 4.6vw, 52px); line-height: 1.05; font-weight: 800; letter-spacing: -0.035em; }
.si .hero .lead { font-size: 17px; line-height: 26px; color: var(--muted); max-width: 760px; }
.si .hero .lead b { color: var(--fg); font-weight: 600; }

/* tile di un'area */
.si a.tile { text-decoration: none; color: inherit; transition: transform .18s ease, border-color .18s ease; }
.si a.tile:hover { transform: translateY(-2px); border-color: color-mix(in srgb, var(--accent) 55%, var(--line)); }
.si a.tile:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.si .tile .regime { display: flex; align-items: center; gap: 10px; font-size: 26px; line-height: 30px; font-weight: 800; letter-spacing: -0.03em; }
.si .tile .regime .dot { width: 12px; height: 12px; }
.si .meta { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 13px; color: var(--muted); }
.si .meta b { color: var(--fg); font-weight: 500; }

/* solidita' a 3 tacche */
.si .solid { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--muted); }
.si .solid span { display: inline-flex; gap: 3px; }
.si .solid i { width: 14px; height: 6px; border-radius: 3px; background: var(--line); }
.si .solid i.on { background: var(--accent); }

/* nastro storico */
.si .ribbon { display: grid; grid-auto-flow: column; grid-auto-columns: 1fr; gap: 1px; height: 14px; border-radius: 5px; overflow: hidden; }
.si .ribbon.thin { height: 8px; }
.si .ribbon i { display: block; height: 100%; }
.si .ticks { display: flex; justify-content: space-between; font-size: 11px; color: var(--muted); margin-top: 6px; }
.si .rlabel { font-size: 12px; color: var(--muted); margin: 10px 0 6px; }

/* barre */
.si .track { height: 8px; border-radius: 4px; background: var(--raised); overflow: hidden; }
.si .track i { display: block; height: 100%; border-radius: 4px; }
.si .prow { display: grid; grid-template-columns: 112px minmax(0, 1fr) 44px; gap: 12px; align-items: center; font-size: 14px; min-height: 30px; }
.si .r { text-align: right; }

/* asse: indicatore di posizione rispetto alle soglie */
.si .gauge { position: relative; height: 34px; margin-top: 4px; }
.si .gauge .bar { position: absolute; top: 12px; left: 0; right: 0; height: 10px; border-radius: 5px;
  background: linear-gradient(90deg, color-mix(in srgb, var(--lo) 55%, transparent) 0 30%, var(--raised) 30% 70%, color-mix(in srgb, var(--hi) 55%, transparent) 70%); }
.si .gauge b { position: absolute; top: 4px; width: 4px; height: 26px; border-radius: 2px; background: var(--fg); transform: translateX(-2px); box-shadow: 0 0 0 3px var(--surface); }
.si .gauge-l { display: flex; justify-content: space-between; font-size: 12px; color: var(--muted); }
.si .big { font-family: 'DM Mono', monospace; font-size: 30px; line-height: 34px; font-weight: 500; letter-spacing: -0.02em; }

/* elenco righe (stile lista raggruppata) */
.si .list { display: flex; flex-direction: column; }
.si .list .row { display: flex; align-items: center; gap: 12px; padding: 11px 0; border-bottom: 1px solid var(--line); font-size: 14px; }
.si .list .row:last-child { border-bottom: 0; }
.si .list .row .grow { flex: 1 1 auto; min-width: 0; }

/* quadrante */
.si .quad { position: relative; aspect-ratio: 1.25; border-radius: 14px; overflow: hidden; border: 1px solid var(--line); }
.si .quad .q { position: absolute; width: 50%; height: 50%; }
.si .quad .ql { position: absolute; font-size: 12px; font-weight: 600; color: var(--muted); }
.si .quad .ax-v { position: absolute; left: 50%; top: 0; bottom: 0; width: 1px; background: var(--line); }
.si .quad .ax-h { position: absolute; top: 50%; left: 0; right: 0; height: 1px; background: var(--line); }
.si .quad .pt { position: absolute; width: 14px; height: 14px; margin: -7px 0 0 -7px; border-radius: 50%; border: 2px solid var(--surface); box-shadow: 0 1px 4px rgba(0,0,0,.25); }
.si .quad .pl { position: absolute; transform: translateY(-50%); font-size: 12px; font-weight: 700; color: var(--fg); white-space: nowrap; }

/* ciambella del portafoglio */
.si .donut { position: relative; width: 220px; aspect-ratio: 1; margin: 4px auto; border-radius: 50%; }
.si .donut .c { position: absolute; inset: 0; z-index: 2; pointer-events: none; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.si .donut .c b { font: 500 36px 'DM Mono', monospace; }
.si .donut .s { position: absolute; inset: 0; border-radius: 50%; transition: transform .15s; }
.si .donut .s:hover { transform: scale(1.03); }
.si .donut .hole { position: absolute; inset: 28px; border-radius: 50%; background: var(--surface); z-index: 1; }
.si .donut .c.tip { display: none; padding: 0 44px; text-align: center; line-height: 1.25; }
.si .donut:has(.s:hover) .c.def { display: none; }
__DONUT_TIPS__
.si .wrow { display: grid; grid-template-columns: 10px minmax(0, 1.4fr) minmax(40px, 1fr) 44px 36px; align-items: center; gap: 12px; min-height: 34px; font-size: 14px; }
.si .sw { width: 10px; height: 10px; border-radius: 3px; }

/* calendario, eventi, valute, COT */
.si .ev-next { display: flex; align-items: center; gap: 14px; padding: 12px; border-radius: 14px; background: color-mix(in srgb, var(--accent) 12%, transparent); }
.si .ev-next .d { width: 58px; height: 58px; border-radius: 14px; background: var(--accent); color: var(--on-accent); display: flex; flex-direction: column; align-items: center; justify-content: center; font: 500 24px/1 'DM Mono', monospace; flex: none; }
.si .ev-next .d small { font: 600 11px 'Plus Jakarta Sans', sans-serif; margin-top: 2px; }
.si .cal h4 { margin: 18px 0 2px; padding: 0; font-size: 11px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
.si .cal h4:first-child { margin-top: 0; }
.si .cal h4 b { color: var(--accent); margin-left: 8px; }
.si .cal .row { display: grid; grid-template-columns: 46px 46px 10px minmax(0, 1fr) auto; }
.si .cal .row.holiday { opacity: .55; }
.si .cal .v { font: 400 13px 'DM Mono', monospace; color: var(--muted); text-align: right; }
.si .cal .v b { color: var(--fg); font-weight: 500; }
.si .div { position: relative; height: 10px; border-radius: 5px; background: var(--raised); }
.si .div::before { content: ""; position: absolute; left: 50%; top: -3px; width: 1px; height: 16px; background: var(--muted); }
.si .div i { position: absolute; top: 0; height: 10px; background: var(--muted); }
.si .cot { display: grid; grid-template-columns: minmax(84px, 1fr) minmax(60px, 2fr) 56px 44px; gap: 12px; align-items: center; font-size: 14px; }
.si .srow { display: grid; grid-template-columns: 22px 52px minmax(0, 1fr) 40px; gap: 12px; align-items: center; min-height: 40px; }
.si .pairs { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
.si .pair { padding: 16px; border-radius: 14px; background: var(--raised); display: flex; flex-direction: column; gap: 8px; }
.si .scale { position: relative; height: 6px; border-radius: 3px; background: linear-gradient(90deg, var(--r-stag) 0 40%, var(--line) 40% 60%, var(--r-gold) 60%); }
.si .scale i { position: absolute; top: -4px; width: 3px; height: 14px; border-radius: 2px; background: var(--fg); }

@media (prefers-reduced-motion: no-preference) {
  .si .card { animation: si-in .35s ease-out both; }
}
@keyframes si-in { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
@media (max-width: 640px) {
  .si .card { padding: 18px; }
  .si .wrow { grid-template-columns: 10px minmax(0, 1fr) 44px 36px; }
  .si .wrow .track { display: none; }
  .si .cot { grid-template-columns: minmax(70px, 1fr) minmax(60px, 2fr) 56px; }
  .si .cot .lbl { display: none; }
  .si .prow { grid-template-columns: 96px minmax(0, 1fr) 40px; }
}
"""

DONUT_SLOTS = 12


def page_css(mode: str) -> str:
    t = TOKENS.get(mode, TOKENS["dark"])
    root = ":root { " + " ".join(f"--{k}: {v};" for k, v in t.items()) + " }"
    tips = "\n".join(f".si .donut:has(.s{i}:hover) .c.t{i} {{ display: flex; }}" for i in range(DONUT_SLOTS))
    return f"<style>{root}{_CSS.replace('__DONUT_TIPS__', tips)}</style>"
