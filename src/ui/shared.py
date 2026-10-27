"""Testi e calcoli delle pagine usati sia dall'app Streamlit (src/app.py) sia dall'export del sito statico
(src/scheduler/export_site.py): stesse frasi e stessi numeri nelle due versioni."""
import pandas as pd
import streamlit as st

from src.classify import intermarket as im
from src.classify.assess import USED_INPUTS, assess
from src.classify.leading import SIGNALS
from src.classify.risk import CANARY, FILL_DAYS, canary, components as risk_components, risk_score
from src.classify.score import UNIVERSE, pillars
from src.classify.stress import PROXY
from src.config.asset_allocation import ALL_WEATHER_WEIGHTS, ASSET_ALLOCATION, LAZY_PORTFOLIOS
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


@st.cache_data
def load_assessment(area: str) -> dict | None:
    """Stesso calcolo dello scheduler (src/classify/assess.py): etichetta, grafici e storico non possono divergere."""
    series = {n: load_indicator(area, n) for n in {*USED_INPUTS, *LEADING_KEYS}}
    a = assess(area, series)
    if a:
        a["label"] = area
    return a


@st.cache_data
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
