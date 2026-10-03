"""Valutazione completa di un'area: unica fonte per scheduler e app, cosi' etichetta, grafici e storico non divergono."""
import pandas as pd

from src.classify.cycle import phase_history
from src.classify.leading import leading_risk
from src.classify.recession import recession_flags
from src.classify.regime import GROWTH_FALLBACK, GROWTH_INPUT, axis_positions, probabilities, regime_history

# Un dato e' in ritardo anomalo oltre questi giorni dalla data di riferimento (inizio del periodo):
# il CPI di agosto (01/08) esce a meta' settembre, il PIL del 2o trimestre (01/04) a fine luglio,
# la disoccupazione UK (media mobile 3 mesi) circa 10 settimane dopo.
STALE_DAYS = {"growth_yoy": 250, "unemployment_rate": 150}
STALE_DAYS_DEFAULT = 120
CORE_INPUTS = (GROWTH_INPUT, "inflation_yoy")  # se uno di questi e' in ritardo la lettura e' poco affidabile
USED_INPUTS = ("cli", "growth_yoy", "inflation_yoy", "core_inflation_yoy", "unemployment_rate", "recession_prob")

# Solidita' = quanto l'asse piu' debole e' dentro il suo stato, in unita' di banda (1 = sulla soglia d'ingresso).
CONFIDENCE_HIGH = 1.0
CONFIDENCE_MEDIUM = 0.3


def run_start(s: pd.Series) -> pd.Timestamp:
    """Primo mese del tratto finale di valori uguali all'ultimo."""
    changed = s != s.shift()
    return changed[changed].index[-1]


def confidence(growth_state: str, inflation_state: str, xg: float, xi: float, stale: list) -> str:
    margin = min(xg if growth_state == "up" else -xg, xi if inflation_state == "up" else -xi)
    if any(n in stale for n in CORE_INPUTS):
        return "Bassa"
    return "Alta" if margin >= CONFIDENCE_HIGH else "Media" if margin >= CONFIDENCE_MEDIUM else "Bassa"


def assess(area: str, series: dict[str, pd.Series], today: pd.Timestamp | None = None) -> dict | None:
    """None se mancano crescita o inflazione. series: indicatori dell'area come in cache."""
    s = {n: v for n, v in series.items() if v is not None and not v.empty}
    growth_name = GROWTH_INPUT if GROWTH_INPUT in s else GROWTH_FALLBACK
    if growth_name not in s or "inflation_yoy" not in s:
        return None
    hist = regime_history(s[growth_name], s["inflation_yoy"], s.get("core_inflation_yoy"))
    unemployment = s.get("unemployment_rate")
    recession = recession_flags(unemployment, s.get("recession_prob")) if unemployment is not None else None
    phases = phase_history(hist["growth"], unemployment, s.get("growth_yoy"), recession)
    hist = hist.join(phases.rename("phase"), how="left")
    hist["phase"] = hist["phase"].ffill()

    today = today or pd.Timestamp.today().normalize()
    as_of = {n: s[n].index[-1] for n in USED_INPUTS if n in s}
    stale = [n for n, d in as_of.items() if (today - d).days > STALE_DAYS.get(n, STALE_DAYS_DEFAULT)]
    last = hist.iloc[-1]
    xg, xi = axis_positions(last["growth_z"], last["inflation_score"])
    phase = last["phase"] if isinstance(last["phase"], str) else None
    return {
        "area": area,
        "regime": last["regime"],
        "phase": phase,
        "month": hist.index[-1],
        "regime_since": run_start(hist["regime"]),
        "phase_since": run_start(hist["phase"].dropna()) if phase else None,
        "growth_state": last["growth"],
        "inflation_state": last["inflation"],
        "inflation_level": last["inflation_level"],
        "positions": (xg, xi),
        "probabilities": probabilities(last["growth_z"], last["inflation_score"]),
        "confidence": confidence(last["growth"], last["inflation"], xg, xi, stale),
        "recession": bool(recession.iloc[-1]) if recession is not None and not recession.empty else False,
        "leading": leading_risk(area, s),
        "growth_source": growth_name,
        "as_of": as_of,
        "stale": stale,
        "history": hist,
    }
