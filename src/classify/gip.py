import pandas as pd

from src.classify.regime import TREND_WINDOW, _direction_series, regime_probabilities

# Versione mensile e "onesta" del quadrante crescita/inflazione stile Hedgeye GIP:
# stessa logica di regime.py (direzione rispetto alla media dei 3 mesi precedenti)
# ma su dati mensili tempestivi (produzione industriale, CPI) e con overlay sulla
# politica monetaria. Hedgeye usa stime di consenso a pagamento: qui no.
# Deadband = 75° percentile delle variazioni mensili storiche dal 1975 (stessa
# convenzione di regime.py/cycle.py).
GIP_GROWTH_DEADBAND = 1.4  # punti % di INDPRO YoY
GIP_INFLATION_DEADBAND = 0.6  # punti % di CPI YoY
FED_MOVE_THRESHOLD = 0.25  # punti % di variazione dei Fed Funds in FED_MOVE_MONTHS
FED_MOVE_MONTHS = 6


def policy_stance(fed_funds: pd.Series) -> str:
    if len(fed_funds) <= FED_MOVE_MONTHS:
        return "n/d"
    change = fed_funds.iloc[-1] - fed_funds.iloc[-1 - FED_MOVE_MONTHS]
    if change >= FED_MOVE_THRESHOLD:
        return "Restrittiva"
    if change <= -FED_MOVE_THRESHOLD:
        return "Espansiva"
    return "Neutrale"


def gip_view(industrial_production: pd.Series, inflation: pd.Series, fed_funds: pd.Series) -> dict:
    """Regime mensile alternativo (USA), probabilita' per regime e stance della Fed."""
    growth_dir = _direction_series(industrial_production, TREND_WINDOW, GIP_GROWTH_DEADBAND).iloc[-1]
    inflation_dir = _direction_series(inflation, TREND_WINDOW, GIP_INFLATION_DEADBAND).iloc[-1]
    regime = {
        ("up", "down"): "Reflazione", ("up", "up"): "Espansione",
        ("down", "up"): "Stagflazione", ("down", "down"): "Deflazione",
    }[(growth_dir, inflation_dir)]
    probs = regime_probabilities(
        industrial_production, inflation, TREND_WINDOW, GIP_GROWTH_DEADBAND, GIP_INFLATION_DEADBAND
    )
    return {"regime": regime, "probabilities": probs, "policy": policy_stance(fed_funds)}
