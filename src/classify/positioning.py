import pandas as pd

CROWDED_PERCENTILE = 90  # >= : speculatori molto long rispetto agli ultimi 5 anni (segnale contrarian)
WASHED_OUT_PERCENTILE = 10  # <= : molto short


def percentile_rank(series: pd.Series) -> float:
    """Percentile (0-100) dell'ultimo valore rispetto all'intera serie."""
    if series.empty:
        raise ValueError("empty series")
    return float((series <= series.iloc[-1]).mean() * 100)


def positioning_label(pct: float) -> str:
    if pct >= CROWDED_PERCENTILE:
        return "Affollato long"
    if pct <= WASHED_OUT_PERCENTILE:
        return "Affollato short"
    return "Neutro"
