"""Testi e calcoli delle pagine per l'export del sito statico (src/scheduler/export_site.py)."""
from functools import cache as memo

import pandas as pd

from src.classify import allocation as al
from src.classify import intermarket as im
from src.classify import liquidity, monitor, pricing
from src.classify.assess import USED_INPUTS, assess
from src.classify.leading import SIGNALS
from src.classify.risk import (
    BOOK_CANARIES, CANARY, FILL_DAYS, canary, canary_level, components as risk_components, momentum_13612w, risk_score)
from src.classify.rrg import weekly_prices
from src.classify.score import ASSET_AREA, UNIVERSE, monthly_prices, pillars
from src.classify.stress import PROXY, common_window, portfolio_returns, summary, trend_returns
from src.config.asset_allocation import ALL_WEATHER_WEIGHTS, ASSET_ALLOCATION, LAZY_PORTFOLIOS
from src.ui.cards import reliability_html, why_text
from src.ui.data import load_indicator

AREAS = {"USA": "USA", "Eurozona": "EUR", "Italia": "ITA", "UK": "UK", "Giappone": "JP",
         "Canada": "CA", "Cina": "CN", "Australia": "AU", "India": "IN"}
LEADING_KEYS = sorted({key for signals in SIGNALS.values() for _, key, _ in signals})
INPUT_LABELS = {
    "cli": "CLI OCSE", "growth_yoy": "PIL annuo", "inflation_yoy": "Inflazione", "core_inflation_yoy": "Inflazione core",
    "unemployment_rate": "Disoccupazione", "recession_prob": "Prob. recessione (Chauvet-Piger)",
    "industrial_production": "Produzione industriale",
}
LEADING_LABELS = {
    "yield_curve": "Curva 10Y-breve (pp)", "credit_spread": "Spread Baa-10Y (pp)", "fin_conditions": "NFCI",
    "cli": "CLI OCSE", "esi": "Sentiment ESI", "btp_bund": "Spread BTP-Bund (pp)", "tankan": "Tankan grandi manif.",
}
PHASE_MEANING = {
    "Espansione": "crescita sopra il trend e in accelerazione",
    "Rallentamento": "lo slancio della crescita si sta esaurendo",
    "Recessione": "contrazione confermata da disoccupazione o PIL",
    "Ripresa (sotto trend)": "crescita sotto il trend ma in miglioramento",
}
TREND_NAMES = {"SPY": "Azionario", "TLT": "Treasury lunga durata", "IEF": "Treasury medio termine", "TIP": "Indicizzate inflazione",
               "GLD": "Oro", "DBC": "Materie prime"}
RISK_PROFILE_LABELS = {"Basso": "Conservativo", "Medio": "Bilanciato", "Alto": "Aggressivo"}
ALL_WEATHER = "All Weather"
STATIC_PORTFOLIOS = {ALL_WEATHER: ALL_WEATHER_WEIGHTS, **LAZY_PORTFOLIOS}  # pesi fissi, indipendenti da regime e profilo
STRESS_ASSETS = sorted({*PROXY, *ALL_WEATHER_WEIGHTS, *(a for v in ASSET_ALLOCATION.values() for a in v)})

RISK_SAY = {
    "Risk Off estremo": "Mercati in forte tensione: gli investitori scappano dal rischio.",
    "Risk Off": "Mercati nervosi: gli investitori riducono il rischio.",
    "Neutrale": "Mercati né calmi né nervosi.",
    "Risk On": "Mercati tranquilli: gli investitori accettano rischio.",
    "Risk On estremo": "Mercati molto tranquilli: gli investitori cercano rischio.",
}
RISK_PARTS = [("VIX", "Calma in borsa", "volatilità (VIX) rispetto alla sua storia"),
              ("Credito", "Calma sul credito", "stress sulle obbligazioni societarie"),
              ("Ampiezza", "Asset in salita", "quota sopra la media a 200 sedute"),
              ("Struttura", "Paura sul breve assente", "VIX a 1 mese contro VIX a 3 mesi"),
              ("Consumi", "Voglia di spendere", "consumi discrezionali contro beni di base (XLY/XLP)"),
              ("Canarino", "Obbligazioni anti-inflazione", "momentum di TIP, spesso scende prima delle tensioni")]


@memo
def load_assessment(area: str) -> dict | None:
    """Stesso calcolo dello scheduler (src/classify/assess.py): etichetta, grafici e storico non possono divergere."""
    series = {n: load_indicator(area, n) for n in {*USED_INPUTS, *LEADING_KEYS}}
    a = assess(area, series)
    if a:
        a["label"] = area
    return a


@memo
def load_risk() -> pd.DataFrame:
    """Componenti del Risk On/Off (src/classify/risk.py) giornaliere, piu' Punteggio e Allarme (momentum del canarino, sotto zero = allarme)."""
    m = lambda k: load_indicator("Mercati", k)
    px = pd.DataFrame({t: load_indicator(im.AREA, t) for t in UNIVERSE})
    if px.empty:
        return px
    comp = risk_components(m("vix"), m("vix3m"), load_indicator("USA", "credit_spread"), m("xly"), m("xlp"), px)
    return comp.assign(Punteggio=risk_score(comp), Allarme=canary(px[CANARY]).reindex(comp.index).ffill(limit=FILL_DAYS)).dropna()


def describe(a: dict) -> str:
    """I numeri dietro la frase del titolo (area_hero_html), poi la fase del ciclo."""
    growth = ("leading indicator OCSE in " + ("salita" if a["growth_state"] == "up" else "calo") if a["growth_source"] == "cli"
              else "PIL annuo in " + ("aumento" if a["growth_state"] == "up" else "calo") + " sul trimestre prima")
    phase = a["phase"]
    return (
        f"Perché: {growth}; inflazione {a['inflation_change']:+.2f} punti sui 3 mesi prima, livello {a['inflation_level']:.1f}%."
        + (f" Ciclo in <b>{phase}</b>: {PHASE_MEANING[phase]}." if phase else "")
    )


def trend_rows(px: pd.DataFrame, names: dict[str, str] = TREND_NAMES) -> list[tuple[str, str, float, float | None]]:
    """Righe di trend_html: classe di asset, ETF, distanza % dalla media a 10 mesi a fine mese e il mese prima.
    names: ticker -> nome della riga."""
    t = pillars(px)["Tendenza"] * 100
    now, prev = t.iloc[-1].dropna(), t.iloc[-2] if len(t) > 1 else pd.Series(dtype=float)
    return [(name, k, now[k], prev.get(k)) for k, name in names.items() if k in now]


@memo
def load_pricing() -> list[dict]:
    """Righe del livello 1 della pagina Oggi, "Cosa prezza il mercato" (src/classify/pricing.py)."""
    return pricing.rows(pricing.load(load_indicator))


@memo
def load_book_canary() -> dict | None:
    """Canarino del libro (src/classify/risk.py) all'ultimo prezzo, mese in corso compreso: livello 1-5, data e
    canarini con momentum negativo. None se manca un ETF."""
    raw = {t: load_indicator(ASSET_AREA, t) for t in BOOK_CANARIES}
    mom = momentum_13612w(monthly_prices(raw)).dropna()
    if mom.empty or len(mom.columns) < len(BOOK_CANARIES):
        return None
    last = mom.iloc[-1]
    return {"level": int(canary_level(mom).iloc[-1]), "date": min(s.index[-1] for s in raw.values()),
            "negative": [t for t in BOOK_CANARIES if last[t] <= 0]}


@memo
def load_monitor() -> tuple[list, pd.Series]:
    """Gruppi di righe e diffusione del cruscotto USA (src/classify/monitor.py)."""
    d = monitor.load(load_indicator)
    return monitor.rows(d), monitor.diffusion(d)


def load_liquidity(usa: dict | None) -> list[dict]:
    """Righe della card Liquidita' e Fed (src/classify/liquidity.py); usa = load_assessment("USA") per il regime."""
    return liquidity.rows(liquidity.load(load_indicator), usa["regime"] if usa else None)


def trend_vs_hold(px: pd.DataFrame) -> str:
    """Una frase per la card della tendenza: S&P 500 con il filtro (stress.trend_returns) e sempre investito, stessa
    finestra. Vuota se mancano SPY o BIL."""
    if not {"SPY", "BIL"} <= set(px):
        return ""
    hold, trend = portfolio_returns({"SPY": 1.0}, px), trend_returns({"SPY": 1.0}, px)
    win = common_window(hold, trend)
    a, b = summary(trend.loc[win]), summary(hold.loc[win])
    if a is None or b is None:
        return ""
    f = lambda x: f"{x * 100:.1f}".replace(".", ",").replace("-", "−")
    return (f"S&P 500 da {a['start']:%m/%Y}: con il filtro {f(a['cagr'])}% l'anno e calo massimo {f(a['dd'])}%, "
            f"sempre investito {f(b['cagr'])}% e {f(b['dd'])}%. Niente costi né tasse.")


IMPACT_LABELS_IT = {"Alto": "High", "Medio": "Medium", "Basso": "Low", "Festivo": "Holiday"}


@memo
def load_weekly() -> tuple[pd.DataFrame, pd.Timestamp | None]:
    """Chiusure settimanali degli ETF (rotazione, src/classify/rrg.py) e data dell'ultima chiusura giornaliera."""
    daily = pd.DataFrame({t: load_indicator(im.AREA, t) for t in UNIVERSE})
    return (daily, None) if daily.empty else (weekly_prices(daily), daily.index[-1])


def upcoming_events() -> list[dict]:
    today = pd.Timestamp.today().normalize()
    events = []
    for name in ["FOMC", "CPI", "Occupazione (NFP)", "PIL"]:
        future = load_indicator("Calendario", name)
        future = future[future.index >= today]
        if not future.empty:
            events.append({"Evento": name, "Data": future.index[0], "giorni": (future.index[0] - today).days})
    return sorted(events, key=lambda e: e["Data"])


# Strumento d'esempio per classe di asset (solo nomi, non e' un consiglio): azioni = ETF del paese; per gli USA la
# pagina mostra anche i migliori della Classifica dentro la classe.
EXAMPLE = {"Obbligazioni": "Titoli di Stato decennali", "Liquidità": "Liquidità a 3 mesi", "Oro": "Oro (es. GLD)"}
CCY_NAMES = {"USD": "Dollaro USA", "EUR": "Euro", "GBP": "Sterlina", "JPY": "Yen", "CAD": "Dollaro canadese",
             "AUD": "Dollaro australiano", "CNY": "Renminbi", "INR": "Rupia indiana"}
CLASS_GROUPS = {"Azioni": ("Settori USA", "Indici USA"), "Obbligazioni": ("Obbligazioni",), "Oro": ("Materie prime",)}


def _alloc_rows(m: dict, key, names: dict, tickers: dict, gruppo: str, active: pd.Series | None) -> tuple[list[dict], pd.Timestamp]:
    """Righe per ranking_html dall'ultima riga con punteggio. key(month) -> etichetta di riga del mese."""
    s = m["score"].dropna(how="all")
    # ultimo mese con una riga per questa chiave: un paese con dati in ritardo non ha la riga del mese piu' recente
    month = max(mo for mo in al.months_of(s.index).unique() if key(mo) in s.index)
    before = key(month - pd.offsets.MonthBegin())
    now = s.loc[key(month)].dropna().sort_values(ascending=False)
    prev = s.loc[before] if before in s.index else pd.Series(dtype=float)
    w = m["weights"].iloc[-1]
    rows = []
    for item, sc in now.items():
        contrib = {k: m["feats"][k].loc[key(month), item] * w[k] for k in m["feats"]}
        hist = s.xs(key(month)[0], level=0)[item] if s.index.nlevels > 1 else s[item]
        rows.append({"item": item, "ticker": tickers.get(item, item), "nome": names.get(item, item), "gruppo": gruppo, "punteggio": sc,
                     "delta": sc - prev[item] if pd.notna(prev.get(item)) else None,
                     "Tendenza": m["raw"]["Tendenza"].loc[key(month), item], "prob": m["prob"].loc[key(month), item],
                     "attivo": bool(active is not None and active.get(item, False)), "storico": hist, "perche": why_text(contrib)})
    return rows, month


# Classifica dell'Allocazione -> lettura di src/config/reliability.py (etichetta coerente con al.EDGE: test in test_reliability)
ALLOC_READING = {"Paesi": "countries", "Classi di asset": "asset_classes", "Valute": "currencies"}


def _badge(name: str) -> str:
    return reliability_html(ALLOC_READING[name])
