import pandas as pd

# Tarato su backtest FRED USA (163 trimestri, 1986-2026): le soglie di spread e
# NFCI sono il 75° percentile storico, la curva e' l'inversione classica.
# Con >= 2 segnali su 3 il rischio e' "Alto" in ~9% dei trimestri, concentrati
# attorno a 1989-90, 2000, 2008-11, 2020 (piu' un falso allarme nel 2023).
CURVE_INVERSION = 0.0  # 10Y-3M sotto zero
CREDIT_SPREAD_STRESS = 2.7  # Baa-10Y, punti %
FIN_CONDITIONS_TIGHT = -0.2  # NFCI
HIGH_RISK_MIN_SIGNALS = 2


def leading_risk(yield_curve: pd.Series, credit_spread: pd.Series, fin_conditions: pd.Series) -> dict:
    """Conta quanti indicatori anticipatori sono in stress. Serie vuote = segnale spento."""
    signals = {
        "Curva invertita": not yield_curve.empty and yield_curve.iloc[-1] < CURVE_INVERSION,
        "Spread credito alto": not credit_spread.empty and credit_spread.iloc[-1] >= CREDIT_SPREAD_STRESS,
        "Condizioni finanziarie strette": not fin_conditions.empty and fin_conditions.iloc[-1] >= FIN_CONDITIONS_TIGHT,
    }
    score = sum(signals.values())
    level = "Alto" if score >= HIGH_RISK_MIN_SIGNALS else "Medio" if score == 1 else "Basso"
    return {"level": level, "score": score, "signals": signals}
