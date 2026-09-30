import pandas as pd

from src.classify.regime import axis_states, axis_z, probabilities_from_z, regime_name

# Versione mensile del quadrante crescita/inflazione stile Hedgeye GIP: stessa logica di
# regime.py (z della variazione rispetto alla media dei 3 mesi precedenti, 3 stati con isteresi)
# ma su dati mensili tempestivi (produzione industriale, CPI) e con overlay sulla politica
# monetaria. Hedgeye usa stime di consenso a pagamento: qui no.
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
    growth_z = axis_z([industrial_production], resample=False)
    inflation_z = axis_z([inflation], resample=False)
    regime = regime_name(axis_states(growth_z).iloc[-1], axis_states(inflation_z).iloc[-1])
    probs = probabilities_from_z(growth_z.iloc[-1], inflation_z.iloc[-1])
    return {"regime": regime, "probabilities": probs, "policy": policy_stance(fed_funds)}
