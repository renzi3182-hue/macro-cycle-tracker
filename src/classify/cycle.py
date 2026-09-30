import pandas as pd

from src.classify.regime import axis_states, axis_z, to_quarterly

# Fase del ciclo = livello della crescita (PIL annuo) rispetto al TREND dell'area + momentum.
# Il momentum e' lo stesso asse crescita del regime (PIL + CLI OCSE, stati su/laterale/giu' con banda
# adattiva): niente piu' soglia fissa tarata sugli USA, che teneva l'Eurozona in "decelerazione" dal 2021.
# Il livello si misura contro la media degli ultimi 10 anni della stessa area, non contro zero.
LEVEL_TREND_QUARTERS = 40
RECESSION_LEVEL = 0.0  # PIL annuo <= 0 con momentum in calo = Recessione anche senza conferma esterna


def classify_cycle(
    growth: pd.Series,
    leading_risk_level: str | None = None,
    recession_confirmed: bool = False,
    momentum_inputs: list | None = None,
) -> str:
    """growth: PIL annuo. momentum_inputs: serie dell'asse crescita (default: solo growth)."""
    if recession_confirmed:  # Sahm + Chauvet-Piger (recession.py) battono il PIL, che rileva in ritardo
        return "Recessione"
    quarterly = to_quarterly(growth)
    level = quarterly.iloc[-1]
    above_trend = level >= quarterly.tail(LEVEL_TREND_QUARTERS).mean()
    momentum = axis_states(axis_z(momentum_inputs or [growth])).iloc[-1]

    if momentum == "down":
        return "Recessione" if level <= RECESSION_LEVEL else "Rallentamento"
    if momentum == "up" and not above_trend:
        return "Ripresa"
    if momentum == "flat" and not above_trend:
        return "Recessione" if level <= RECESSION_LEVEL else "Rallentamento"  # sotto trend e fermo
    # Il PIL e' in ritardo: se curva/credito/condizioni finanziarie sono gia' in stress
    # (vedi leading.py) l'espansione viene declassata a rallentamento.
    return "Rallentamento" if leading_risk_level == "Alto" else "Espansione"

