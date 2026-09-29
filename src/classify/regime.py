import math

import pandas as pd

TREND_WINDOW = 3

# Tarate su backtest storico reale FRED USA 1948-2026 (310 trimestri): senza
# deadband il regime cambiava nel 45.5% dei trimestri (rumore statistico su
# variazioni piccole). Con queste soglie (75° percentile delle variazioni
# trimestrali osservate) scende al 15.5%, e le crisi vere (2008, 2020, 2021-22)
# restano rilevate correttamente. Vedi wiki/macro-cycle-tracker.md.
GROWTH_DEADBAND = 2.0
INFLATION_DEADBAND = 1.4
# Probabilita' che una direzione sia "up": logistica sulla distanza dalla media
# precedente, con P = 0.75 quando la distanza uguaglia il deadband. E' una
# convenzione, non una stima calibrata su frequenze storiche.
PROB_AT_DEADBAND = 0.75


def _direction_series(series: pd.Series, window: int, deadband: float) -> pd.Series:
    if len(series) < window + 1:
        raise ValueError(f"need at least {window + 1} data points, got {len(series)}")
    directions = []
    prev = None
    for i in range(window, len(series)):
        baseline = series.iloc[i - window:i].mean()
        delta = series.iloc[i] - baseline
        if prev is not None and abs(delta) < deadband:
            direction = prev
        else:
            direction = "up" if delta > 0 else "down"
        directions.append(direction)
        prev = direction
    return pd.Series(directions, index=series.index[window:])


def _regime_name(growth_dir: str, inflation_dir: str) -> str:
    if growth_dir == "up" and inflation_dir == "down":
        return "Reflazione"
    if growth_dir == "up" and inflation_dir == "up":
        return "Espansione"
    if growth_dir == "down" and inflation_dir == "up":
        return "Stagflazione"
    return "Deflazione"


def classify_regime(growth: pd.Series, inflation: pd.Series) -> str:
    growth_dir = _direction_series(growth, TREND_WINDOW, GROWTH_DEADBAND).iloc[-1]
    inflation_dir = _direction_series(inflation, TREND_WINDOW, INFLATION_DEADBAND).iloc[-1]
    return _regime_name(growth_dir, inflation_dir)


def regime_history(growth: pd.Series, inflation: pd.Series, quarters: int = 20) -> pd.Series:
    """Regime per trimestre (ultimi `quarters`), stessa logica di classify_regime su serie trimestrali."""
    df = pd.DataFrame({
        "g": growth.resample("QE").last(),
        "i": inflation.resample("QE").last(),
    }).dropna()
    g_dir = _direction_series(df["g"], TREND_WINDOW, GROWTH_DEADBAND)
    i_dir = _direction_series(df["i"], TREND_WINDOW, INFLATION_DEADBAND)
    return pd.Series([_regime_name(g, i) for g, i in zip(g_dir, i_dir)], index=g_dir.index).tail(quarters)


def direction_position(growth: pd.Series, inflation: pd.Series, window: int = TREND_WINDOW) -> tuple[float, float]:
    """(inflazione, crescita) come distanza dalla media precedente in unita' di deadband: +-1 = soglia di cambio direzione."""
    dg = growth.iloc[-1] - growth.iloc[-window - 1:-1].mean()
    di = inflation.iloc[-1] - inflation.iloc[-window - 1:-1].mean()
    return di / INFLATION_DEADBAND, dg / GROWTH_DEADBAND


def _prob_up(series: pd.Series, window: int, deadband: float) -> float:
    if len(series) < window + 1:
        raise ValueError(f"need at least {window + 1} data points, got {len(series)}")
    delta = series.iloc[-1] - series.iloc[-window - 1:-1].mean()
    k = math.log(PROB_AT_DEADBAND / (1 - PROB_AT_DEADBAND)) / deadband
    return 1 / (1 + math.exp(-k * delta))


def regime_probabilities(
    growth: pd.Series,
    inflation: pd.Series,
    window: int = TREND_WINDOW,
    growth_deadband: float = GROWTH_DEADBAND,
    inflation_deadband: float = INFLATION_DEADBAND,
) -> dict:
    """Probabilita' dei 4 regimi, assumendo crescita e inflazione indipendenti."""
    pg = _prob_up(growth, window, growth_deadband)
    pi = _prob_up(inflation, window, inflation_deadband)
    return {
        "Reflazione": pg * (1 - pi),
        "Espansione": pg * pi,
        "Stagflazione": (1 - pg) * pi,
        "Deflazione": (1 - pg) * (1 - pi),
    }
