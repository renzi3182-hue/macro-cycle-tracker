"""Valutazione completa di un'area: unica fonte per scheduler e app, cosi' etichetta, grafici e storico non divergono."""
import pandas as pd

from src.classify.cycle import momentum_states, phase_history
from src.classify.leading import leading_risk
from src.classify.recession import recession_flags
from src.classify.regime import (
    ACTIVITY_INPUTS, GROWTH_FALLBACK, GROWTH_INPUT, activity_z, axis_positions, probabilities, regime_history,
)

# Un dato e' in ritardo anomalo oltre questi giorni dalla data di riferimento (inizio del periodo):
# il CPI di agosto (01/08) esce a meta' settembre, il PIL del 2o trimestre (01/04) a fine luglio,
# la disoccupazione UK (media mobile 3 mesi) circa 10 settimane dopo.
STALE_DAYS = {"growth_yoy": 250, "unemployment_rate": 150}
STALE_DAYS_DEFAULT = 120
CORE_INPUTS = (GROWTH_INPUT, "inflation_yoy")  # se uno di questi e' in ritardo la lettura e' poco affidabile
# Serie FRED ad alta frequenza (area, indicatore): massimo ritardo in giorni di calendario. Giornaliere 5
# (weekend + un festivo), settimanali 14 (NFCI e sussidi escono 4-6 giorni dopo la settimana di riferimento).
HIGH_FREQ_MAX_DAYS = {
    ("USA", "yield_curve"): 5, ("USA", "credit_spread"): 5, ("Mercati", "vix"): 5,
    ("Mercati", "breakeven_5y"): 5, ("Mercati", "breakeven_5y5y"): 5,
    ("USA", "fin_conditions"): 14, ("USA", "claims"): 14,
}
USED_INPUTS = ("cli", "growth_yoy", "inflation_yoy", "core_inflation_yoy", "unemployment_rate", "recession_prob", "industrial_production")

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


def stale_high_freq(last_dates: dict[tuple[str, str], pd.Timestamp | None], today: pd.Timestamp | None = None) -> list:
    """Chiavi di HIGH_FREQ_MAX_DAYS con l'ultimo dato troppo vecchio o assente."""
    today = today or pd.Timestamp.today().normalize()
    return [k for k, days in HIGH_FREQ_MAX_DAYS.items()
            if last_dates.get(k) is None or (today - last_dates[k]).days > days]


def assess(area: str, series: dict[str, pd.Series], today: pd.Timestamp | None = None) -> dict | None:
    """None se mancano crescita o inflazione. series: indicatori dell'area come in cache."""
    s = {n: v for n, v in series.items() if v is not None and not v.empty}
    growth_name = GROWTH_INPUT if GROWTH_INPUT in s else GROWTH_FALLBACK
    if growth_name not in s or "inflation_yoy" not in s:
        return None
    hist = regime_history(s[growth_name], s["inflation_yoy"], s.get("core_inflation_yoy"))
    unemployment = s.get("unemployment_rate")
    recession = recession_flags(unemployment, s.get("recession_prob")) if unemployment is not None else None
    momentum = momentum_states(s["cli"]) if "cli" in s else hist["growth"]
    phases = phase_history(momentum, unemployment, s.get("growth_yoy"), recession)
    hist = hist.join(phases.rename("phase"), how="left")
    hist["phase"] = hist["phase"].ffill()

    today = today or pd.Timestamp.today().normalize()
    as_of = {n: s[n].index[-1] for n in USED_INPUTS if n in s}
    stale = [n for n, d in as_of.items() if (today - d).days > STALE_DAYS.get(n, STALE_DAYS_DEFAULT)]
    last = hist.iloc[-1]
    xg, xi = axis_positions(last["growth_z"], last["inflation_score"])
    act = activity_z(s.get("industrial_production"), s.get("cli"))
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
        "probabilities": (probs := probabilities(act.iloc[-1] if not act.empty else None, last["inflation_score"])),
        "inflation_prob": probs["Reflazione"] + probs["Stagflazione"],  # unico asse prevedibile, la crescita e' ~50%
        "activity": (next(n for n in ACTIVITY_INPUTS if n in s), act.iloc[-1]) if not act.empty else None,
        "confidence": confidence(last["growth"], last["inflation"], xg, xi, stale),
        "recession": bool(recession.iloc[-1]) if recession is not None and not recession.empty else False,
        "leading": leading_risk(area, s),
        "growth_source": growth_name,
        "as_of": as_of,
        "stale": stale,
        "history": hist,
    }
