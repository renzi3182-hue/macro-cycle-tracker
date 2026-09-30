import math

import pandas as pd

TREND_WINDOW = 3

# Serie (nomi degli indicatori in cache) che alimentano i due assi; quelle mancanti si saltano.
# Il CLI OCSE e' mensile e anticipa il PIL: da solo il PIL arriva con ~4 mesi di ritardo.
GROWTH_INPUTS = ("growth_yoy", "cli")
INFLATION_INPUTS = ("inflation_yoy", "core_inflation_yoy")

# Ogni asse ha 3 stati (su / laterale / giù) sulla variazione rispetto alla media dei trimestri
# precedenti, misurata in deviazioni standard della STESSA serie fino a quel momento (point-in-time):
# la banda si adatta a ogni area (l'Eurozona si muove meno degli USA) invece di una soglia fissa.
# Isteresi: si entra in su/giù oltre ENTER, si esce solo sotto EXIT, per non oscillare sul confine.
# Valori convenzionali, non calibrati sul backtest (vedi scripts/backtest_regime.py).
FLAT_BAND_ENTER = 0.3
FLAT_BAND_EXIT = 0.1
# Conferma su 2 periodi: cambi regime 35-44% -> 21-26% dei trimestri, ma la svolta arriva 1 trimestre dopo
# (GFC 2008Q4 letto come Stagflazione invece di Deflazione). Si tiene 1: meglio rumore che svolte in ritardo.
CONFIRM_PERIODS = 1
MIN_SCALE_PERIODS = 8  # sotto questi punti la deviazione standard usa tutto il campione
# Probabilita' che una direzione sia "up": logistica su z, P = 0.75 quando z = FLAT_BAND_ENTER.
PROB_AT_BAND = 0.75
Z_CLIP = 10.0  # evita l'overflow del logistico su serie quasi piatte (scala ~0)

REGIMES = ["Goldilocks", "Reflazione", "Stagflazione", "Deflazione"]
TRANSITION = "Transizione"  # almeno un asse laterale: nessun quadrante netto


def to_quarterly(series: pd.Series) -> pd.Series:
    """Ultimo valore di ogni trimestre. La finestra e la scala sono in trimestri: una serie
    mensile va portata a trimestri prima. Il trimestre in corso usa l'ultimo mese disponibile."""
    return series.resample("QE").last().dropna()


def pick_inputs(series_by_name: dict, names: tuple) -> list:
    return [series_by_name[n] for n in names if n in series_by_name and not series_by_name[n].empty]


def _as_list(inputs) -> list:
    return [inputs] if isinstance(inputs, pd.Series) else list(inputs)


def _z_series(series: pd.Series, window: int, resample: bool) -> pd.Series:
    if series.empty:
        return series
    s = to_quarterly(series) if resample else series
    delta = (s - s.rolling(window).mean().shift(1)).dropna()
    if delta.empty:
        return delta
    scale = delta.expanding(min_periods=MIN_SCALE_PERIODS).std().fillna(delta.std()).fillna(0)
    return delta / scale.clip(lower=1e-9)  # serie piatta: delta 0 -> z 0; scala nulla e delta != 0 -> z enorme


def _standardize(z: pd.Series) -> pd.Series:
    scale = z.expanding(min_periods=MIN_SCALE_PERIODS).std().fillna(z.std()).fillna(0)
    return z / scale.clip(lower=1e-9)


def axis_z(inputs, window: int = TREND_WINDOW, resample: bool = True) -> pd.Series:
    """z di un asse: media degli z delle serie disponibili in ogni periodo (se ne manca una, conta l'altra)."""
    zs = [z for z in (_z_series(s, window, resample) for s in _as_list(inputs)) if not z.empty]
    if not zs:
        raise ValueError(f"servono almeno {window + 1} punti per almeno una serie")
    # la media di z poco correlati ha varianza < 1: senza ri-standardizzare la banda laterale si allarga
    return _standardize(pd.concat(zs, axis=1).mean(axis=1)) if len(zs) > 1 else zs[0]


def _raw_state(v: float, prev: str) -> str:
    if v > FLAT_BAND_ENTER or (prev == "up" and v > FLAT_BAND_EXIT):
        return "up"
    if v < -FLAT_BAND_ENTER or (prev == "down" and v < -FLAT_BAND_EXIT):
        return "down"
    return "flat"


def axis_states(z: pd.Series) -> pd.Series:
    """Stato dell'asse con isteresi di soglia e conferma: cambia solo se il nuovo stato regge CONFIRM_PERIODS periodi."""
    states, current, pending, count = [], "flat", None, 0
    for v in z:
        raw = _raw_state(v, current)
        if raw == current:
            pending, count = None, 0
        elif raw == pending:
            count += 1
        else:
            pending, count = raw, 1
        if pending is not None and count >= CONFIRM_PERIODS:
            current, pending, count = pending, None, 0
        states.append(current)
    return pd.Series(states, index=z.index)


def regime_name(growth_state: str, inflation_state: str) -> str:
    if "flat" in (growth_state, inflation_state):
        return TRANSITION
    if growth_state == "up":
        return "Reflazione" if inflation_state == "up" else "Goldilocks"
    return "Stagflazione" if inflation_state == "up" else "Deflazione"


def regime_history(growth, inflation, quarters: int = 20) -> pd.Series:
    """Regime per trimestre (ultimi `quarters`). growth/inflation: una serie o una lista di serie.
    Gli assi hanno date diverse (il PIL esce dopo il CPI): lo stato piu' vecchio resta valido finche' non arriva il nuovo."""
    df = pd.DataFrame({"g": axis_states(axis_z(growth)), "i": axis_states(axis_z(inflation))}).ffill().dropna()
    return pd.Series([regime_name(g, i) for g, i in zip(df["g"], df["i"])], index=df.index).tail(quarters)


def classify_regime(growth, inflation) -> str:
    return regime_history(growth, inflation, quarters=1).iloc[-1]


def direction_position(growth, inflation) -> tuple[float, float]:
    """(inflazione, crescita) come z dell'ultimo periodo in unita' di banda: +-1 = soglia di ingresso in su/giu'."""
    return axis_z(inflation).iloc[-1] / FLAT_BAND_ENTER, axis_z(growth).iloc[-1] / FLAT_BAND_ENTER


def probabilities_from_z(growth_z: float, inflation_z: float) -> dict:
    """Probabilita' dei 4 regimi, assumendo crescita e inflazione indipendenti."""
    k = math.log(PROB_AT_BAND / (1 - PROB_AT_BAND)) / FLAT_BAND_ENTER
    pg, pi = (1 / (1 + math.exp(-k * max(-Z_CLIP, min(Z_CLIP, z)))) for z in (growth_z, inflation_z))
    return {
        "Goldilocks": pg * (1 - pi),
        "Reflazione": pg * pi,
        "Stagflazione": (1 - pg) * pi,
        "Deflazione": (1 - pg) * (1 - pi),
    }


def regime_probabilities(growth, inflation) -> dict:
    return probabilities_from_z(axis_z(growth).iloc[-1], axis_z(inflation).iloc[-1])
