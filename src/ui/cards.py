"""Blocchi HTML del sito (src/scheduler/export_site.py). Colori solo da variabili CSS di theme.py, cosi' valgono in
chiaro e scuro. Grafici con div/CSS, senza <svg> inline (scelta nata con Streamlit, che li toglieva)."""
from collections import Counter
from html import escape
from math import cos, pi, sin
from urllib.parse import quote

import pandas as pd

from src.classify.assess import label_regimes, run_start
from src.classify.cycle import PHASES
from src.classify.opportunities import CLASS_NAMES, sentence as opp_sentence
from src.classify.regime import REGIME_AXES, REGIMES
from src.classify.risk import BOOK_CANARIES, CANARY, CANARY_LEVELS, CANARY_RISK_OFF, LABELS as RISK_LABELS
from src.classify.score import HORIZON_MONTHS, STRONG, WEAK
from src.config.asset_allocation import PHASE_ASSETS
from src.config.reliability import KINDS, READINGS
from src.config.sector_regime import INTENSITY_NOTES, SECTOR_NAMES, SECTOR_REGIME, SPREAD_BY_REGIME
from src.config.ucits import NO_EQUIVALENT, SOURCE as UCITS_SOURCE, UCITS
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


# Il regime in parole semplici: prima la frase costruita dagli assi, poi il nome (che segue il libro) come dettaglio.
AXIS_WORD = {"up": "accelera", "down": "rallenta"}
AXIS_NAME = ("la crescita", "l'inflazione")
BORDER = "al confine"  # asse vicino alla soglia, nelle etichette "Incerto: X / Y"


def cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def axes_phrase(growth_state: str, inflation_state: str) -> str:
    """Frase dagli stati degli assi (assess: growth_state, inflation_state): "crescita accelera, inflazione rallenta"."""
    return f"crescita {AXIS_WORD[growth_state]}, inflazione {AXIS_WORD[inflation_state]}"


def label_phrase(label: str) -> str:
    """Frase di un'etichetta di regime. In "Incerto: X / Y" i due regimi differiscono su un solo asse: quell'asse e'
    "al confine" (Incerto: Stagflazione / Deflazione = "crescita rallenta, inflazione al confine")."""
    axes = [REGIME_AXES[r] for r in label_regimes(label)]
    words = [AXIS_WORD[axes[0][k]] if len({x[k] for x in axes}) == 1 else BORDER for k in (0, 1)]
    return f"crescita {words[0]}, inflazione {words[1]}"


def uncertain_note(a: dict) -> str:
    """Perche' un'area e' "Incerto: X / Y": quale asse e' vicino alla soglia e quale regime arriverebbe se cambiasse
    direzione. Vuoto se il regime e' netto. a: risultato di assess()."""
    pair = label_regimes(a["regime_label"])
    if len(pair) < 2:
        return ""
    alt = next(r for r in pair if r != a["regime"])
    k = 0 if REGIME_AXES[alt][0] != REGIME_AXES[a["regime"]][0] else 1
    state = (a["growth_state"], a["inflation_state"])[k]
    return (f"Incerto fra {pair[0]} e {pair[1]}: {AXIS_NAME[k]} {AXIS_WORD[state]} di poco ed è vicina alla soglia. "
            f"Se {'accelerasse' if state == 'down' else 'rallentasse'}, il regime diventerebbe {alt}.")


def badge_html(kind: str) -> str:
    """Etichetta di affidabilita' (Verificato, Teoria, Descrittivo: src/config/reliability.py), con il significato nel tooltip."""
    var, meaning = KINDS[kind]
    return f'<span class="rel" style="--c:var(--{var})" title="{escape(meaning)}">{escape(kind)}</span>'


def reliability_html(key: str, extra: str = "") -> str:
    """Riga sotto il titolo di una lettura: etichetta e frase semplice (READINGS[key]), piu' un testo facoltativo che
    la lega alla pagina. I numeri solo nel Metodo."""
    r = READINGS[key]
    return f'<p class="note rel-line">{badge_html(r.kind)} {escape(r.plain)}{" " + escape(extra) if extra else ""}</p>'


def reliability_table_html() -> str:
    """Pagina Metodo: tutte le letture per etichetta, con la frase semplice e i numeri della verifica."""
    out = []
    for kind, (_, meaning) in KINDS.items():
        rows = "".join(
            f'<div class="row" style="align-items:flex-start"><span class="grow"><b style="font-weight:600">{escape(r.name)}</b>'
            f'<small class="muted" style="display:block;font-size:13px;line-height:19px">{escape(r.plain)}</small>'
            f'<small style="display:block;font-size:12px;line-height:18px;margin-top:4px">{escape(r.numbers)} '
            f'<span class="mono muted">({escape(r.source)})</span></small></span></div>'
            for r in READINGS.values() if r.kind == kind)
        out.append(f'<div><p class="note rel-line">{badge_html(kind)} {escape(meaning)}</p><div class="list">{rows}</div></div>')
    return (f'<div class="si card"><div class="head"><h3>Quanto fidarsi di ogni lettura</h3><span class="note">etichette '
            f'delle pagine e numeri delle verifiche</span></div>{"".join(out)}</div>')


def hero_html(eyebrow: str, title: str, lead: str) -> str:
    """lead: html gia' sicuro."""
    return f'<div class="hero"><span class="eyebrow">{escape(eyebrow)}</span><h1>{title}</h1><p class="lead">{lead}</p></div>'



def ribbon_html(values: pd.Series, color, months: int = RIBBON_MONTHS, thin: bool = False, ticks: bool = True, text=str) -> str:
    """Nastro mensile (dal piu' vecchio a oggi). color: funzione valore -> colore CSS; text: valore -> testo del tooltip."""
    v = values.dropna().iloc[-months:]
    if v.empty:
        return ""
    cells = "".join(f'<i style="background:{color(x)}" title="{month_it(d, True)}: {escape(text(x))}"></i>' for d, x in v.items())
    out = f'<div class="ribbon{" thin" if thin else ""}" role="img" aria-label="storico mensile">{cells}</div>'
    if ticks:
        out += f'<div class="ticks"><span>{month_it(v.index[0], True)}</span><span>{month_it(v.index[-1], True)}</span></div>'
    return out



def legend_html() -> str:
    """Colori del nastro dei regimi: prima la frase, poi il nome."""
    return '<div class="meta">' + "".join(
        f'<span>{_dot(regime_color(r))} {cap(label_phrase(r))} <span class="muted">· {r}</span></span>' for r in REGIMES) + "</div>"


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
    chip = (f'<span class="chip tint" style="--c:{regime_color(estimate)};white-space:normal">Più probabile: '
            f'{escape(label_phrase(estimate))} · {escape(estimate)}</span>' if estimate else "")
    return (
        f'<div class="prow"><span>{_dot("var(--r-stag)")} Inflazione in salita</span>'
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



def stat_tile_html(href: str, eyebrow: str, value: int, total: int, state: str, color: str, bar: str, note: str,
                   kind: str | None = None) -> str:
    """Card in alto nella pagina Oggi: un numero su un totale, lo stato a parole e una barra; porta al dettaglio.
    `note` e' HTML gia' pronto; kind: etichetta di affidabilita'."""
    return (
        f'<a class="card tile" href="{escape(href)}" target="_self"><span class="eyebrow">{escape(eyebrow)}</span>'
        f'{f"<span style=\"align-self:flex-start;margin-top:-6px\">{badge_html(kind)}</span>" if kind else ""}'
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
            f'{reliability_html("phase_assets")}<div class="wave-l wave-a">{"".join(cols)}</div>')


def changes_html(items: list[tuple[str, str]], month: pd.Timestamp) -> str:
    """Cosa e' cambiato dal mese scorso (src/classify/changes.summary): una riga per frase, con l'etichetta di
    affidabilita' della lettura (chiave di READINGS)."""
    rows = "".join(f'<div class="row" style="align-items:flex-start"><span class="grow">{escape(text)}</span>'
                   f'{badge_html(READINGS[key].kind)}</div>' for key, text in items)
    body = f'<div class="list">{rows}</div>' if rows else "<p>Nessun cambio rispetto al mese prima.</p>"
    return (f'<div class="si card"><div class="head"><h3>Cosa è cambiato dal mese scorso</h3><span class="note">fine '
            f'{month_it(month)} contro il mese prima</span></div>{body}'
            '<p class="note">Regime, fase, tendenza e chi entra o esce dai primi 3 (paesi, classi di asset, Classifica). '
            "L'etichetta dice quanto fidarsi di ogni lettura.</p></div>")


def opportunity_map_html(grid: dict[str, list[dict]], top: list[tuple[str, dict]], phases: dict[str, str | None],
                         month: pd.Timestamp) -> str:
    """Mappa delle occasioni (src/classify/opportunities.py): sopra le migliori in parole, sotto paesi per riga e classi
    per colonna. Cella: punteggio (colore come la Classifica), freccia della teoria per la fase, pallino della tendenza."""
    def cell(area: str, c: dict | None) -> str:
        if c is None:
            return '<span class="mx"></span>'
        arrow = {1: '<b style="color:var(--r-gold)">▲</b>', -1: '<b style="color:var(--r-stag)">▼</b>'}.get(c["freccia"], "")
        dot = "" if c["in_salita"] is None else _dot(f'var(--{"r-gold" if c["in_salita"] else "r-stag"})')
        return (f'<span class="mx opp" title="{escape(opp_sentence(area, c))}"><span class="mono" style="color:'
                f'{score_color(c["punteggio"])}">{c["punteggio"]:.0f}</span>{arrow}{dot}</span>')
    names = list(CLASS_NAMES)
    head = '<span></span><span class="ph"></span>' + "".join(
        f'<span class="eyebrow" style="text-align:center">{escape(CLASS_NAMES[c])}</span>' for c in names)
    rows = "".join(
        f'<b style="--c:{phase_color(phases.get(area))}"><a href="paese?area={quote(area)}" target="_self" '
        f'style="color:inherit">{escape(area)}</a></b>'
        f'<span class="mono ph" style="font-size:12px;color:{phase_color(phases.get(area))}">{escape(phases.get(area) or "n/d")}</span>'
        + "".join(cell(area, next((c for c in cs if c["classe"] == k), None)) for k in names)
        for area, cs in grid.items())
    best_rows = "".join(
        f'<div class="row"><span class="mono muted">{i}</span><span class="grow">{escape(opp_sentence(area, c))}</span></div>'
        for i, (area, c) in enumerate(top, 1))
    return (f'<div class="si card"><div class="head"><h3>Mappa delle occasioni</h3><span class="note">punteggio di fine '
            f'{month_it(month)} · fase di oggi</span></div>{reliability_html("map")}'
            f'<div><span class="eyebrow">Le {len(top)} letture più concordi</span><div class="list">{best_rows}</div></div>'
            f'<div style="overflow-x:auto"><div class="mxg">{head}{rows}</div></div>'
            '<p class="note">Numero = punteggio della classe nel paese, 1-100 (verde = in testa) · '
            '<span style="color:var(--r-gold)">▲</span> <span style="color:var(--r-stag)">▼</span> = più o meno peso per la '
            'fase del ciclo, dalla teoria · pallino = prezzo in valuta locale sopra (verde) o sotto (rosso) la media a 10 '
            'mesi. Il punteggio è la lettura verificata; teoria e tendenza descrivono.</p></div>')


def risk_explain_html(score: float, state: str, when: str, parts: list[tuple[str, str, float]], alarm: bool,
                      book: dict | None = None) -> str:
    """Spiega il punteggio Risk On/Off: la scala a cinque fasce con il segno sul valore, cosa misura e cosa non
    misura, le sei componenti, lo stato del canarino e il canarino a cinque ETF (shared.load_book_canary)."""
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
        f'{reliability_html("risk")}<p class="say"><b>{s}</b> è la media di sei misure di calma dei mercati. Ognuna va da 0 (il momento più teso della '
        f'sua storia) a 100 (il più calmo): 50 è una giornata normale. Oggi: <b>{escape(state)}</b>. La misura più bassa '
        f'è <b>{escape(low[0].lower())}</b> ({low[2]:.0f}).</p>'
        '<p class="say">Più è basso, più la borsa ha oscillato nel mese dopo: dice <b>quanto può muoversi</b>, non in che direzione.</p>'
        f'<div>{bar_rows_html(parts)}</div>'
        f'<p class="note">Canarino {CANARY} {canary}. È anche la sesta misura del punteggio.</p>{_book_canary(book)}</div>'
    )


def _book_canary(book: dict | None) -> str:
    """Riga del canarino a cinque ETF: livello 1-5 con i negativi; vuota senza dati."""
    if not book:
        return ""
    lv = book["level"]
    color = "r-refl" if lv <= CANARY_RISK_OFF else "r-gold"
    neg = ", ".join(book["negative"])
    return (f'<p class="note">Canarino a cinque ETF ({", ".join(BOOK_CANARIES)}), al {book["date"]:%d/%m}: livello '
            f'<b style="color:var(--{color})">{lv}/5, {escape(CANARY_LEVELS[lv - 1])}</b>'
            f'{f" (momentum negativo: {neg})" if neg else ", tutti in salita"}. Conta quanti dei cinque salgono su '
            f'1-12 mesi: 1-3 risk off, 4-5 risk on. Descrittivo: aggiunto al filtro di tendenza, dal 2019 ha ridotto i cali '
            f'ma tolto 3,6 punti di rendimento l\'anno.</p>')



def bar_rows_html(rows: list[tuple[str, str, float]]) -> str:
    """(etichetta, spiegazione, valore 0-100): una barra per riga, colorata con level_var."""
    return "".join(
        f'<div class="brow"><span>{escape(label)}</span><span class="mono">{v:.0f}</span><small>{escape(note)}</small>'
        f'<div class="track"><i style="width:{v:.0f}%;background:var(--{level_var(v)})"></i></div></div>'
        for label, note, v in rows
    )



def area_hero_html(a: dict, sentence: str, markets: tuple[int, int] | None = None) -> str:
    """Titolo = la frase dagli assi; il nome del regime e, per le aree "Incerto", il perche' vengono dopo.
    markets: (asset tipici del regime in salita, asset con un ETF), da asset_allocation.confirmation."""
    color = regime_color(a["regime_label"])
    phase = a["phase"] or "n/d"
    end = a["month"]
    note = uncertain_note(a)
    facts = [
        ("Fase del ciclo", f'<span style="color:{phase_color(a["phase"])}">{escape(phase)}</span>'),
        ("Così da", f'{month_it(a["regime_since"])}<br><span class="muted" style="font-size:13px;font-weight:400">{duration_it(a["regime_since"], end)}</span>'),
        ("Solidità macro", escape(a["confidence"])),
        *([("Conferma mercati", f'{markets[0] / markets[1]:.0%}<br><span class="muted" style="font-size:13px;font-weight:400">'
                                f'asset tipici in salita ({markets[0]} su {markets[1]}): coerenza, non probabilità</span>'
                                f'<span style="margin-top:4px">{badge_html(READINGS["confirmation"].kind)}</span>')]
          if markets and markets[1] else []),
        ("Dati fino a", month_it(end)),
    ]
    cells = "".join(f'<div style="display:flex;flex-direction:column;gap:4px"><span class="eyebrow">{k}</span>'
                    f'<span style="font-size:17px;font-weight:600">{v}</span></div>' for k, v in facts)
    return (
        f'<div class="si card" style="padding:32px;border-radius:28px;background:linear-gradient(160deg,color-mix(in srgb,{color} 14%,var(--surface)),var(--surface) 55%)">'
        f'<span class="eyebrow">Crescita e inflazione oggi · dati PIL a {month_it(a["month"])}</span>'
        f'<h1 style="font-size:clamp(30px,4.6vw,52px);line-height:1.05;font-weight:800;letter-spacing:-0.035em;color:{color}">'
        f'{escape(cap(axes_phrase(a["growth_state"], a["inflation_state"])))}</h1>'
        f'<div style="display:flex;flex-wrap:wrap;align-items:center;gap:8px"><span class="muted" style="font-size:14px">Regime</span>'
        f'<span class="chip tint" style="--c:{color};font-weight:700">{escape(a["regime_label"])}</span></div>'
        + (f'<p style="font-size:15px;line-height:22px;max-width:720px;color:var(--muted)">{escape(note)}</p>' if note else "")
        + f'<p style="font-size:17px;line-height:26px;max-width:720px">{sentence}</p>{reliability_html("regime")}'
        f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:16px;margin-top:8px">{cells}</div></div>'
    )


def regimes_html(areas: dict[str, dict]) -> str:
    """Crescita e inflazione paese per paese: una riga per etichetta, prima la frase e poi il nome del regime, con le
    aree che la condividono. areas: area -> assess(). Ordine: regimi netti come in REGIMES, poi gli incerti."""
    groups: dict[str, list[str]] = {}
    for area, a in areas.items():
        groups.setdefault(a["regime_label"], []).append(area)
    order = sorted(groups, key=lambda lab: (len(label_regimes(lab)), min(REGIMES.index(r) for r in label_regimes(lab))))
    rows = "".join(
        f'<div class="row" style="align-items:flex-start">{_dot(regime_color(lab))}<span class="grow">'
        f'<b style="font-weight:600">{escape(cap(label_phrase(lab)))}</b>'
        f'<small class="muted" style="display:block;font-size:12px">regime {escape(lab)}</small></span>'
        f'<span style="text-align:right">{escape(", ".join(groups[lab]))}</span></div>' for lab in order)
    border = (f"«{BORDER.capitalize()}» = quell'asse è vicino alla soglia: il prossimo dato può cambiarlo, per questo il "
              "regime è «Incerto» fra i due. " if any(len(label_regimes(lab)) > 1 for lab in groups) else "")
    return (f'<div class="si card"><div class="head"><h3>Crescita e inflazione, paese per paese</h3><span class="note">regime macro</span></div>'
            f'{reliability_html("regime")}<div class="list">{rows}</div><p class="note">{border}Il nome del regime viene dalla '
            "tabella crescita × inflazione (sezione Metodo).</p></div>")


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
        f'<div class="si card"><div class="head"><h3>Storico {badge_html(READINGS["regime"].kind)}</h3><span class="note">ultimi {len(h) // 12} anni, un tratto per mese</span></div>'
        f'<div><div class="rlabel">Crescita e inflazione · regime</div>'
        f'{ribbon_html(h["regime"], regime_color, months, ticks=False, text=lambda r: f"{label_phrase(r)} ({r})")}'
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
        f'<div class="si head"><h3 style="font-size:17px;font-weight:600">Indicatori anticipatori {badge_html(READINGS["leading"].kind)}</h3>'
        f'<span class="solid"><span role="img" aria-label="{score} segnali attivi su {total}">{blocks}</span>'
        f'<b style="color:var(--{var})">Rischio {escape(level.lower())} · {score}/{total}</b></span></div>'
    )


def portfolio_html(weights: dict, deltas: dict | None, title: str, subtitle: str, delta_note: str = "vs regimi precedenti",
                   badge: str = "") -> str:
    """badge: HTML sotto il titolo (reliability_html), vuoto per i portafogli statici."""
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
        f'<div class="si two"><div class="card"><div class="head"><h3>{escape(title)}</h3><span class="note">{escape(subtitle)}</span></div>{badge}{donut}</div>'
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
            f'{reliability_html("trend")}<p>{"Nessun cambio" if not changed else "1 cambio" if changed == 1 else f"{changed} cambi"} rispetto al mese prima.</p>'
            f'<div class="list">{items}</div>'
            '<p class="note">Rosso = sotto la media: con il filtro attivo quella quota va in cash. "Esce" e "rientra" = il segnale '
            'è cambiato a fine mese, l\'unico momento in cui il filtro chiede di fare qualcosa. Protegge nei crolli lunghi, '
            'perde qualcosa nei rimbalzi veloci: numeri nella sezione Metodo.</p></div>')


def _signal_rows(rows: list[dict]) -> str:
    """Una riga per segnale con valore, stato e cosa misura (formato di pricing.rows e liquidity.rows)."""
    return "".join(
        f'<div class="row" style="align-items:flex-start"><div class="grow"><b style="font-weight:600">{escape(r["name"])}</b>'
        f'<small class="muted" style="display:block;font-size:12px;line-height:17px">{escape(r["note"])}'
        f'{f" Percentile storico {r['pct']:.0f}." if r["pct"] is not None else ""} Al {r["date"]:%d/%m}.</small></div>'
        f'<span class="mono" style="white-space:nowrap;font-size:13px">{escape(r["value"])}</span>'
        f'<span class="chip tint" style="--c:var(--{r["tone"]})">{escape(r["state"])}</span></div>'
        for r in rows)


def pricing_html(rows: list[dict]) -> str:
    """Livello 1 della pagina Oggi (src/classify/pricing.rows)."""
    return (f'<div class="si card"><div class="head"><h3>Cosa prezza il mercato</h3><span class="note">tassi, credito, opzioni, futures</span></div>'
            f'{reliability_html("pricing")}<div class="list">{_signal_rows(rows)}</div>'
            '<p class="note">Percentile = posizione del valore di oggi fra tutti quelli passati (100 = il più alto). Le curve dei '
            'futures si salvano da ottobre 2026: il loro storico è ancora corto. Backwardation = la merce vale di più subito che fra un '
            'anno (offerta scarsa o domanda forte); contango = il contrario, normale per l\'oro.</p></div>')


def liquidity_html(rows: list[dict]) -> str:
    """Livello 2 della pagina Oggi (src/classify/liquidity.rows): liquidita', Fed e intensita' del regime USA."""
    return (f'<div class="si card"><div class="head"><h3>Liquidità e Fed: quanto pesa il regime USA</h3><span class="note">USA</span></div>'
            f'{reliability_html("liquidity")}<div class="list">{_signal_rows(rows)}</div>'
            '<p class="note">Crescita e inflazione dicono il regime, liquidità e politica della Fed quanto è profondo. Quattro '
            'fattori lo aggravano: PIL annuo sceso di almeno 1 punto in un trimestre, inflazione sopra il 2%, liquidità in calo '
            'su 6 mesi, tasso reale della Fed sopra 1 punto. Il dot plot è la mediana delle previsioni dei membri della Fed, '
            'aggiornata 4 volte l\'anno.</p></div>')


def _monitor_cell(x: float | None, unit: str, sign: int) -> str:
    if x is None or pd.isna(x):
        return '<td class="n">n/d</td>'
    tone = "muted" if sign == 0 or x == 0 else "r-gold" if x * sign > 0 else "r-stag"
    txt = f"{x:+.{2 if abs(x) < 1 else 1}f}{'%' if unit == '%' else ''}".replace(".", ",").replace("-", "−")
    return f'<td style="color:var(--{tone})">{"▲" if x > 0 else "▼" if x < 0 else "·"} {txt}</td>'


def sector_regime_html(regime: str | None) -> str:
    """Settori USA per regime (src/config/sector_regime.py): ▲ long, ▼ short, · neutro, colonna del regime USA di oggi
    evidenziata; sotto, long meno short misurato e le versioni debole e forte."""
    regimes = list(SECTOR_REGIME)
    bg = lambda r: "background:var(--raised);" if r == regime else ""
    head = "".join(f'<th style="{bg(r)}color:{regime_color(r)}">{escape(r)}{" · oggi" if r == regime else ""}</th>' for r in regimes)

    def cell(t: str, r: str) -> str:
        long, short = SECTOR_REGIME[r]
        mark, tone = ("▲", "r-gold") if t in long else ("▼", "r-stag") if t in short else ("·", "muted")
        return f'<td style="{bg(r)}color:var(--{tone});text-align:center">{mark}</td>'
    body = "".join(f'<tr><td>{escape(n.capitalize())} <span class="muted">{t}</span></td>'
                   + "".join(cell(t, r) for r in regimes) + "</tr>" for t, n in SECTOR_NAMES.items())
    spread = ("<tr><td><b>Long meno short, storico</b></td>" + "".join(
        f'<td class="mono" style="{bg(r)}text-align:center">{f"{SPREAD_BY_REGIME[r]:+.1f}".replace(".", ",").replace("-", "−")}</td>'
        for r in regimes) + "</tr>")
    notes = "".join(f"<p><b>{escape(r)}</b>: {escape(n)}</p>" for r, n in INTENSITY_NOTES.items())
    return (f'<div class="si card"><div class="head"><h3>Settori per regime</h3><span class="note">USA</span></div>'
            f'{reliability_html("sector_regime")}'
            f'<div class="tbl"><table class="mtx"><tr><th></th>{head}</tr>{body}{spread}</table></div>{notes}'
            '<p class="note">▲ più peso, ▼ meno peso, · nessuna indicazione. Long meno short = quanto i settori ▲ hanno battuto i ▼ '
            "in punti l'anno, nel mese dopo, con il regime USA come si leggeva allora (1948-2026). Solo la Stagflazione "
            "supera il rumore, ma su quattro regimi uno così esce anche per caso.</p></div>")


def monitor_html(groups: list[tuple[str, list[dict]]], diffusion: pd.Series) -> str:
    """Cruscotto USA (src/classify/monitor.rows): diffusione in cima, tabella delle serie per gruppo, apribile."""
    n = sum(len(r) for _, r in groups)
    body = "".join(
        f'<tr><td colspan="4" style="font-weight:600;padding-top:14px">{escape(g)}</td></tr>' + "".join(
            f'<tr><td>{escape(r["name"])}</td><td class="n">{f"T{(r['date'].month - 1) // 3 + 1} {r['date'].year}" if r["quarterly"] else month_it(r["date"], True)}</td>'
            f'{_monitor_cell(r["prev"], r["unit"], r["sign"])}{_monitor_cell(r["lookback"], r["unit"], r["sign"])}</tr>'
            for r in rows) for g, rows in groups)
    d = diffusion.dropna()
    head = ("" if d.empty else
            f'<p class="say">Delle serie che hanno un verso, <b>{d.iloc[-1]:.0f}%</b> sta meglio di 3 mesi fa '
            f'({"sotto la metà: economia che rallenta" if d.iloc[-1] < 50 else "più della metà: economia che regge"}). '
            f'Tre mesi prima era il {d.iloc[-4]:.0f}%.</p>' if len(d) > 3 else "")
    return (f'<div class="si card"><div class="head"><h3>Cruscotto USA: {n} serie mese per mese</h3><span class="note">USA</span></div>'
            f'{reliability_html("monitor")}{head}'
            f'<details><summary style="cursor:pointer;font-size:13px">Tutte le serie</summary><div class="tbl"><table class="mtx">'
            f'<tr><th></th><th>Ultimo dato</th><th>Sul periodo prima</th><th>Su 3 mesi</th></tr>{body}</table></div></details>'
            '<p class="note">Conta la direzione, non il livello. Verde = meglio per l\'economia, rosso = peggio, grigio = senza '
            'un verso (prezzi, tassi, scorte, import, risparmio). Le serie trimestrali (T) confrontano col trimestre prima.</p></div>')


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
            f'{reliability_html("relations")}<div class="list">{body}</div>'
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
            f'ha anticipato chi batte la media a {HORIZON_MONTHS} mesi.</p></div>')


ACTIVE = '<b style="color:var(--r-gold)">Segnale attivo</b> · '


def ranking_html(rows: list[dict], month: pd.Timestamp, title: str = "Classifica", horizon: int = HORIZON_MONTHS, note: str = "") -> str:
    """rows: ticker, nome, gruppo, punteggio, delta (vs mese prima o None), Tendenza (frazione), prob (0-1), attivo
    (segnale acceso), storico (serie mensile), perche' (testo di why_text); facoltativa freccia (+1/-1: teoria dei
    settori per regime, src/config/sector_regime.py). note: HTML sotto il titolo (reliability_html)."""
    arrow = {1: ' <b style="color:var(--r-gold)" title="Teoria: più peso in questo regime">▲</b>',
             -1: ' <b style="color:var(--r-stag)" title="Teoria: meno peso in questo regime">▼</b>'}
    head = (f'<div class="arow th"><span>#</span><span>Asset</span><span class="opt">Ultimi 12 mesi</span>'
            f'<span class="r opt">Tendenza</span><span class="r opt">Prob. {horizon}m</span><span class="r">Punt.</span><span class="r">Var.</span></div>')
    body = "".join(
        f'<div class="arow"><span class="mono muted">{i}</span>'
        f'<span style="min-width:0"><b style="font-weight:600">{escape(r["nome"])}</b>{arrow.get(r.get("freccia"), "")} '
        f'<span class="mono muted" style="font-size:12px">{escape(r["ticker"])}<span class="opt"> · {escape(r["gruppo"])}</span></span>'
        f'<small class="muted" style="display:block;font-size:12px;line-height:16px">'
        f'{ACTIVE if r["attivo"] else ""}{escape(r["perche"])}</small></span>'
        f'<span class="opt">{ribbon_html(r["storico"], score_color, 12, thin=True, ticks=False)}</span>'
        f'<span class="mono r opt">{r["Tendenza"] * 100:+.1f}%</span><span class="mono r opt">{r["prob"] * 100:.0f}%</span>'
        f'<span class="r"><span class="chip tint mono" style="--c:{score_color(r["punteggio"])};font-weight:700">{r["punteggio"]:.0f}</span></span>'
        f'<span class="r" style="font-size:13px">{_signed(r["delta"]) if r["delta"] is not None else ""}</span></div>'
        for i, r in enumerate(rows, 1)
    )
    sub = note
    return (f'<div class="si card"><div class="head"><h3>{escape(title)}</h3><span class="note">punteggio di fine {month_it(month)}, 1-100</span></div>'
            f'{sub}<div class="list">{head}{body}</div></div>')


def currency_html(row: dict, pos: int, total: int, month: pd.Timestamp, note: str) -> str:
    """La valuta di un paese nella classifica delle valute (src/classify/allocation.currencies): punteggio, posizione,
    probabilita', tendenza e perche'. row: una riga di _alloc_rows (shared); note: reliability_html."""
    trend = row["Tendenza"]
    trend_txt = "n/d" if pd.isna(trend) else f"{trend * 100:+.1f}%".replace(".", ",").replace("-", "−")
    return (f'<div class="si card"><div class="head"><h3>La valuta: {escape(row["nome"])}</h3><span class="note">punteggio '
            f'di fine {month_it(month)}, 1-100</span></div>{note}'
            f'<div class="total" style="border-top:0;padding-top:0;flex-wrap:wrap"><span class="chip tint mono" style="--c:'
            f'{score_color(row["punteggio"])};font-size:22px;font-weight:700">{row["punteggio"]:.0f}</span>'
            f'<span style="font-size:17px;font-weight:600">{pos}ª su {total} valute</span>'
            f'<span class="muted" style="font-size:14px">{escape(row["perche"])}</span></div>'
            f'<p>Probabilità che tenere liquidità in {escape(row["nome"].lower() if row["item"] != "USD" else "dollari")} renda più '
            f'della media delle valute nei 6 mesi dopo: <b class="mono">{row["prob"] * 100:.0f}%</b> · tendenza contro la media a '
            f'10 mesi <b class="mono">{trend_txt}</b>.</p>'
            '<p class="note">Rendimento in dollari di cambio più tasso a breve. Per chi investe in un\'altra valuta, un cambio '
            'che si rafforza aggiunge rendimento agli investimenti in quella valuta, uno che si indebolisce lo toglie.</p></div>')


def ucits_html(tickers: list[str], names: dict[str, str]) -> str:
    """Equivalenti UCITS (src/config/ucits.py) degli ETF USA indicati, per chi investe dall'Italia. names: ticker -> nome
    della riga nell'app. Solo esempi, con fonte e data della verifica."""
    rows = []
    for t in tickers:
        if t not in UCITS:
            continue
        u = UCITS[t]
        if u is None:
            rows.append(f'<tr><td><b>{escape(t)}</b><br><span class="muted" style="font-size:12px">{escape(names.get(t, ""))}</span></td>'
                        f'<td colspan="2" class="muted">{escape(NO_EQUIVALENT.get(t, "Nessun equivalente UCITS chiaro."))}</td></tr>')
            continue
        note = f'<br><span class="muted" style="font-size:12px">{escape(cap(u.note))}</span>' if u.note else ""
        rows.append(f'<tr><td><b>{escape(t)}</b><br><span class="muted" style="font-size:12px">{escape(names.get(t, ""))}</span></td>'
                    f'<td>{escape(u.name)}{note}</td><td class="isin">{escape(u.isin)}'
                    f'{f"<br><span class=muted>{escape(u.ticker)}</span>" if u.ticker else ""}</td></tr>')
    return (f'<div class="si card"><div class="head"><h3>Dall\'Italia: equivalenti UCITS</h3><span class="note">{escape(UCITS_SOURCE)}'
            f'</span></div><div class="tbl"><table class="mtx ucits"><tr><th>ETF USA</th><th>Esempio UCITS</th><th>ISIN · ticker</th></tr>'
            f'{"".join(rows)}</table></div><p class="note">Gli ETF USA di solito non si possono comprare da privati in Italia: '
            "qui un fondo europeo con la stessa esposizione, solo come esempio e non come consiglio. Per cercarlo vale l'ISIN; "
            "il ticker cambia da borsa a borsa. Nota sotto il nome = indice o struttura diversi.</p></div>")


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
                # data-*: filtri del sito statico (public/index.html), che riceve tutti gli eventi e nasconde le righe
                f'<div class="row{" holiday" if e["impact"] == "Holiday" else ""}" data-ccy="{escape(e["country"])}" '
                f'data-impact="{escape(IMPACT_LABELS.get(e["impact"], e["impact"]))}"><span class="mono">{local:%H:%M}</span>'
                f'<span class="chip" style="padding:2px 8px;font-size:12px">{escape(e["country"])}</span>'
                f'<i class="dot" style="background:var(--{IMPACT_VARS.get(e["impact"], "muted")})" title="Impatto {escape(IMPACT_LABELS.get(e["impact"], e["impact"]))}"></i>'
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
    out.append(f'</div>{reliability_html("rrg")}<div class="list">')
    for q, (name, meaning) in RRG_TEXT.items():
        names = ", ".join(f'{r["nome"]} ({r["ticker"]})' for r in sorted(rows, key=lambda r: -r["ratio"]) if r["quadrante"] == q)
        if names:
            out.append(f'<div class="row">{_dot(f"var(--{RRG_VARS[q]})")}<span class="grow"><b>{name}</b>: {escape(names)}'
                       f'<small class="muted" style="display:block;font-size:12px">{meaning}</small></span></div>')
    out.append('</div><p class="note">Forza relativa = asset contro lo S&amp;P 500 rispetto alla sua media a 10 settimane; '
               'slancio = variazione della forza relativa in 3 settimane. Gira in senso orario: in ingresso, in testa, in '
               'raffreddamento, in coda.</p></div>')
    return "".join(out)


def _pct_it(x: float, digits: int = 0) -> str:
    return f"{x * 100:+.{digits}f}".replace(".", ",").replace("-", "−") + "%"


def _months_it(n: int | None) -> str:
    return "non ancora" if n is None else "subito" if n == 0 else f"{n} {'mese' if n == 1 else 'mesi'}"


def lab_html(plain: dict, trend: dict | None, unit: str = "$") -> str:
    """plain/trend: summary() di src/classify/stress.py del portafoglio senza e con filtro di tendenza. unit: "$" con i
    rendimenti in dollari, "€" convertiti in euro (stress.eur_returns)."""
    cols = [("Senza filtro", plain), *([("Con filtro di tendenza", trend)] if trend else [])]
    head = "".join(f"<th>{name}</th>" for name, _ in cols)
    rows = [("Oggi avresti", lambda x: f"{10000 * x['final']:,.0f} {unit}".replace(",", ".")),
            ("Guadagno medio all'anno", lambda x: _pct_it(x["cagr"], 1)),
            ("Calo peggiore", lambda x: _pct_it(x["dd"])),
            ("Attesa più lunga per tornare in pari", lambda x: "mai sotto" if x["under"] == 0 else _months_it(x["under"])),
            ("Mese cattivo, 1 su 20 (VaR 95%)", lambda x: _pct_it(x["var"], 1)),
            ("Media dei mesi peggiori (Expected Shortfall)", lambda x: _pct_it(x["es"], 1)),
            ("Guadagno annuo diviso calo peggiore", lambda x: "nessun calo" if x["ret_dd"] is None else f"{x['ret_dd']:.2f}".replace(".", ","))]
    body = "".join(f"<tr><td>{label}</td>" + "".join(f"<td>{fmt(x)}</td>" for _, x in cols) + "</tr>" for label, fmt in rows)
    verdict = ""
    if trend:
        diff = (trend["cagr"] - plain["cagr"]) * 100
        verdict = (f'<p>Il filtro ha reso <b>{abs(diff):.1f} punti l\'anno {"in più" if diff >= 0 else "in meno"}</b>'.replace(".", ",", 1)
                   + f' e ha portato il calo peggiore da <b class="mono">{_pct_it(plain["dd"])}</b> a <b class="mono">{_pct_it(trend["dd"])}</b>.</p>')
    return (f'<div class="si card"><div class="head"><h3>Come sarebbe andata</h3><span class="note">da {month_it(plain["start"], True)} a oggi</span></div>'
            f'<p>Se a {month_it(plain["start"])} avessi messo <b>10.000 {unit}</b> nel portafoglio qui a fianco:</p>'
            f'<div class="tbl"><table class="mtx"><tr><th></th>{head}</tr>{body}</table></div>{verdict}'
            '<p class="note">Calo peggiore = quanto sei sceso, al massimo, da un picco. Attesa più lunga = il periodo più lungo passato '
            'sotto un picco prima di superarlo. VaR = il mese peggiore 1 volta su 20; Expected Shortfall = quanto perdi in media in '
            'quei mesi, dice meglio il rischio di eventi estremi. Guadagno diviso calo: più alto = più guadagno per ogni punto di calo. '
            f'Il grafico sotto segue 100 {unit} nel tempo. Ribilanciamento ogni mese, ETF in dollari'
            + (", convertiti in euro senza copertura del cambio" if unit == "€" else "")
            + ', senza costi né tasse; il filtro sposta in cash (BIL, T-bill a 1-3 mesi) ogni ETF sotto la sua media a 10 mesi.</p></div>')


def stress_html(rows: list[tuple[str, str, tuple | None, tuple | None, tuple | None]], mc: dict | None, years: int, skipped: list[str],
                unit: str = "$") -> str:
    """rows: (crisi, periodo, (rendimento, drawdown, mesi per recuperare) del portafoglio o None, idem con filtro, idem S&P 500).
    mc: percentile -> valore di 100. unit: "$" o "€" come lab_html."""
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
        money = lambda x: f"{10000 * (1 + x[0]):,.0f} {unit}".replace(",", ".")
        example = (f'<p>Esempio, {escape(name.lower())}: con 10.000 {unit} saresti arrivato a <b class="mono">{money(p)}</b> '
                   f'senza filtro e a <b class="mono">{money(t)}</b> con il filtro.</p>')
    band = (f'<p>Guardando avanti, fra {years} anni 100 {unit} potrebbero diventare circa <b class="mono">{mc[50]:.0f}</b>: '
            f'<b class="mono">{mc[5]:.0f}</b> se va molto male, <b class="mono">{mc[95]:.0f}</b> se va molto bene.</p>' if mc else "")
    note = f" Esclusi perché senza ETF: {escape(', '.join(skipped))}." if skipped else ""
    return (f'<div class="si card"><div class="head"><h3>Grandi crolli</h3><span class="note">cosa sarebbe successo ai tuoi soldi</span></div>'
            f'<p>Le {len(rows)} grandi discese della borsa dal 2007. Per ognuna: <b>quanto avresti perso o guadagnato</b> (sopra) e <b>dopo quanto '
            'tempo saresti tornato alla cifra di partenza</b> (sotto).</p>'
            '<div class="tbl"><table class="mtx"><tr><th></th><th>Il tuo portafoglio</th><th>Con filtro di tendenza</th>'
            f'<th>Solo borsa USA</th></tr>{body}</table></div>{example}{band}'
            '<p class="note">Con filtro di tendenza = vendi ciò che scende sotto la sua media a 10 mesi e lo ricompri quando torna sopra: '
            'aiuta nei crolli lunghi, nei rimbalzi veloci ti fa ricomprare tardi. Solo borsa USA = tutto nell\'S&amp;P 500. '
            'Nessun dato = qualche fondo non esisteva ancora. Ogni classe usa il suo ETF (azionario = SPY, growth = IWF, '
            'value = IWD, difensivo = XLP, credito = LQD, dollaro = UUP, cash = BIL), ribilanciamento mensile, niente costi. La stima a 10 anni rimescola i mesi passati del portafoglio: '
            f'il passato non garantisce il futuro.{note}</p></div>')



