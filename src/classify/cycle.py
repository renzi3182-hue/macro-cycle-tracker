import pandas as pd

# Tarato su backtest storico reale FRED USA (312 trimestri): senza deadband la
# fase cambiava nel 47.6% dei trimestri. Con questa soglia (75° percentile del
# momentum trimestrale osservato) scende al 13.7%, crisi vere restano rilevate.
# Vedi wiki/macro-cycle-tracker.md.
MOMENTUM_DEADBAND = 1.4


def _momentum_direction_series(growth: pd.Series, deadband: float) -> pd.Series:
    directions = []
    prev = None
    for i in range(1, len(growth)):
        raw_momentum = growth.iloc[i] - growth.iloc[i - 1]
        if prev is not None and abs(raw_momentum) < deadband:
            direction = prev
        else:
            direction = "accel" if raw_momentum > 0 else "decel"
        directions.append(direction)
        prev = direction
    return pd.Series(directions, index=growth.index[1:])


def classify_cycle(growth: pd.Series) -> str:
    if len(growth) < 2:
        raise ValueError(f"need at least 2 data points, got {len(growth)}")
    level = growth.iloc[-1]
    momentum_dir = _momentum_direction_series(growth, MOMENTUM_DEADBAND).iloc[-1]
    if level > 0 and momentum_dir == "accel":
        return "Espansione"
    if level > 0 and momentum_dir == "decel":
        return "Rallentamento"
    if level <= 0 and momentum_dir == "decel":
        return "Recessione"
    return "Ripresa"
