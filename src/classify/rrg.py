import pandas as pd

from src.classify.score import TREND_MONTHS, UNIVERSE

# Rotazione relativa (06/10/2026), versione aperta del Relative Rotation Graph di J. de Kempenaer (la formula
# originale non e' pubblica). Forza relativa rs = asset / SPY, poi:
# - RS-Ratio = 100 * rs / media di rs a `trend` periodi (sopra 100: l'asset fa meglio dell'S&P 500 in tendenza);
# - RS-Momentum = 100 * RS-Ratio / RS-Ratio di `momentum` periodi prima (sopra 100: il vantaggio sta crescendo).
# L'asset gira in senso orario: Migliora (in ingresso) -> Guida -> Indebolisce (in raffreddamento) -> Arretra.
# Verifica mensile 1999-2026 sui settori (scripts/evaluate_rrg.py, 11 settori con XLC e XLRE dall'11/10/2026, 3073
# casi): il quadrante NON prevede l'extra-rendimento sull'S&P 500. A 3 mesi Guida +0.14%, Arretra 0.00% (differenza
# t 0.5), segno opposto dal 2014; solo i settori in Guida 8,3%/anno contro 8,5% dei settori a pesi uguali.
# Settimanale (12/10/2026), come l'app di riferimento, su tutti i gruppi di UNIVERSE: stessi periodi della mensile applicati
# alle settimane (10 e 3), una sola variante. Verifica 1996-2026 in scripts/evaluate_rrg.py: neanche qui il quadrante
# prevede l'extra-rendimento. Sui 27 asset, a 13 settimane, Guida meno Arretra -0,08 punti (t -0,2), in ingresso
# (Migliora) meno in raffreddamento (Indebolisce) -0,55 (t -1,1); nessun gruppo arriva a |t| 2 su tutto il periodo.
# Va mostrato come mappa descrittiva.
BENCHMARK = "SPY"
MOMENTUM_MONTHS = 3
TREND_WEEKS, MOMENTUM_WEEKS = TREND_MONTHS, MOMENTUM_MONTHS
GROUPS = {g: [t for t, (_, gg) in UNIVERSE.items() if gg == g and t != BENCHMARK] for _, g in UNIVERSE.values()}
SECTORS = GROUPS["Settori USA"]
QUADRANTS = {(True, True): "Guida", (True, False): "Indebolisce", (False, False): "Arretra", (False, True): "Migliora"}


def weekly_prices(daily: pd.DataFrame) -> pd.DataFrame:
    """Ultima chiusura di ogni settimana (venerdi'); la settimana in corso vale con l'ultima chiusura disponibile."""
    return daily.resample("W-FRI").last()


def rrg(px: pd.DataFrame, members: list[str] = SECTORS, trend: int = TREND_MONTHS,
        momentum: int = MOMENTUM_MONTHS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """px mensile (score.monthly_prices) o settimanale (weekly_prices). Ritorna (RS-Ratio, RS-Momentum), una colonna per asset."""
    rs = px[[t for t in members if t in px]].div(px[BENCHMARK], axis=0)
    ratio = 100 * rs / rs.rolling(trend).mean()
    return ratio, 100 * ratio / ratio.shift(momentum)


def quadrant(ratio: float, momentum: float) -> str:
    return QUADRANTS[(ratio >= 100, momentum >= 100)]
