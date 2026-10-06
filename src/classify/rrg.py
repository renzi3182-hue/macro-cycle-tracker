import pandas as pd

from src.classify.score import TREND_MONTHS, UNIVERSE

# Rotazione settori USA (06/10/2026), versione mensile e aperta del Relative Rotation Graph di J. de Kempenaer
# (la formula originale non e' pubblica). Forza relativa rs = settore / SPY, poi:
# - RS-Ratio = 100 * rs / media di rs a TREND_MONTHS mesi (sopra 100: il settore fa meglio dell'S&P 500 in tendenza);
# - RS-Momentum = 100 * RS-Ratio / RS-Ratio di MOMENTUM_MONTHS mesi prima (sopra 100: il vantaggio sta crescendo).
# Il settore gira in senso orario: Migliora -> Guida -> Indebolisce -> Arretra.
# Verifica 1999-2026 (scripts/evaluate_rrg.py, 9 settori, 2871 casi): il quadrante NON prevede l'extra-rendimento
# sull'S&P 500. A 3 mesi Guida +0.20%, Arretra +0.16% (differenza t 0.1), segno opposto dal 2014; solo i settori
# in Guida 8,6%/anno contro 8,7% dei 9 a pesi uguali. Va mostrato come mappa descrittiva, non come segnale.
BENCHMARK = "SPY"
MOMENTUM_MONTHS = 3
SECTORS = [t for t, (_, g) in UNIVERSE.items() if g == "Settori USA"]
QUADRANTS = {(True, True): "Guida", (True, False): "Indebolisce", (False, False): "Arretra", (False, True): "Migliora"}


def rrg(px: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """px mensile (src/classify/score.monthly_prices). Ritorna (RS-Ratio, RS-Momentum), una colonna per settore."""
    rs = px[[t for t in SECTORS if t in px]].div(px[BENCHMARK], axis=0)
    ratio = 100 * rs / rs.rolling(TREND_MONTHS).mean()
    return ratio, 100 * ratio / ratio.shift(MOMENTUM_MONTHS)


def quadrant(ratio: float, momentum: float) -> str:
    return QUADRANTS[(ratio >= 100, momentum >= 100)]
