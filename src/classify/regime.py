import math

import pandas as pd

# Regime macro mensile = direzione della crescita x pressione dell'inflazione (riscritto il 03/10/2026).
# Verifica in scripts/evaluate_model.py, con i ritardi di pubblicazione veri (PIL +4 mesi, CPI e CLI +1):
# il modello precedente (trimestrale, z della variazione di PIL e CPI, stato "laterale") coincideva con
# la lettura a posteriori solo nel 5-20% dei mesi ed era "Transizione" il 40-60% del tempo. La seconda
# derivata del PIL non si vede in tempo reale con dati gratuiti: anche il miglior modello a momentum
# arriva al ~60%. Questo coincide nell'88-91% dei mesi e cambia ~1 volta l'anno.
#
# Crescita: direzione del CLI OCSE su 3 mesi (sopra/sotto il ritmo di trend). Nelle vintage ALFRED
# 2018-2026 la direzione del CLI resta la stessa dopo le revisioni nel 79-93% dei casi; il LIVELLO
# rispetto a 100 no (66-88%), per questo non si usa. Senza CLI: direzione del PIL annuo.
GROWTH_INPUT = "cli"
GROWTH_FALLBACK = "growth_yoy"
GROWTH_CHANGE_MONTHS = 3
GROWTH_BAND = 0.4  # z della variazione: sopra +BAND "up", sotto -BAND "down", in mezzo resta lo stato precedente

# Inflazione: livello (media totale + core) rispetto al target delle banche centrali, corretto per la
# direzione del totale su 3 mesi. Solo livello: Europa in "Stagflazione" a fine 2008 con prezzi gia' in
# caduta; solo direzione: rumore. Punteggio = (livello - target) + peso * variazione 3 mesi, punti %.
INFLATION_INPUTS = ("inflation_yoy", "core_inflation_yoy")
INFLATION_TARGET = 2.0  # Fed, BCE, BoE, BoJ (dal 2013)
INFLATION_DIRECTION_WEIGHT = 1.0
INFLATION_HIGH = 0.5  # punteggio sopra: inflazione alta/in salita
INFLATION_LOW = -0.25  # punteggio sotto: inflazione sotto controllo/in calo

CONFIRM_MONTHS = 2  # un asse cambia stato solo se il nuovo regge 2 mesi: cambi di regime ~1.7 -> ~1.1 l'anno
MIN_SCALE_MONTHS = 24  # sotto questi punti la deviazione standard usa tutto il campione
PROB_AT_BAND = 0.75  # probabilita' di "up" quando un asse e' esattamente sulla soglia d'ingresso

REGIMES = ["Goldilocks", "Reflazione", "Stagflazione", "Deflazione"]


def monthly(series: pd.Series) -> pd.Series:
    """Un valore per mese (inizio mese). Un dato trimestrale resta valido finche' non arriva il successivo."""
    return series.resample("MS").last().ffill()


def growth_z(series: pd.Series) -> pd.Series:
    """Variazione a 3 mesi in deviazioni standard della stessa serie fino a quel momento (point-in-time)."""
    m = monthly(series)
    d = (m - m.shift(GROWTH_CHANGE_MONTHS)).dropna()
    scale = d.expanding(min_periods=MIN_SCALE_MONTHS).std().fillna(d.std()).fillna(0)
    return d / scale.clip(lower=1e-9)


def inflation_level(headline: pd.Series, core: pd.Series | None = None) -> pd.Series:
    parts = [monthly(headline)] + ([monthly(core)] if core is not None and not core.empty else [])
    return pd.concat(parts, axis=1).mean(axis=1)


def inflation_score(headline: pd.Series, core: pd.Series | None = None) -> pd.Series:
    h = monthly(headline)
    return ((inflation_level(headline, core) - INFLATION_TARGET) + INFLATION_DIRECTION_WEIGHT * (h - h.shift(GROWTH_CHANGE_MONTHS))).dropna()


def axis_states(score: pd.Series, high: float, low: float, confirm: int = CONFIRM_MONTHS) -> pd.Series:
    """'up' sopra high, 'down' sotto low, in mezzo resta lo stato precedente; un cambio vale dopo `confirm` mesi."""
    states, current, pending, count = [], None, None, 0
    for v in score:
        if current is None:
            current = "up" if v >= (high + low) / 2 else "down"
        raw = "up" if v > high else "down" if v < low else current
        if raw == current:
            pending, count = None, 0
        else:
            count = count + 1 if raw == pending else 1
            pending = raw
            if count >= confirm:
                current, pending, count = raw, None, 0
        states.append(current)
    return pd.Series(states, index=score.index, dtype=object)


def regime_name(growth_state: str, inflation_state: str) -> str:
    if growth_state == "up":
        return "Reflazione" if inflation_state == "up" else "Goldilocks"
    return "Stagflazione" if inflation_state == "up" else "Deflazione"


def _up_probability(x: float) -> float:
    """x = distanza dalla soglia in unita' di banda: x = 1 -> PROB_AT_BAND."""
    k = math.log(PROB_AT_BAND / (1 - PROB_AT_BAND))
    return 1 / (1 + math.exp(-k * max(-10.0, min(10.0, x))))


def axis_positions(g_z: float, i_score: float) -> tuple[float, float]:
    """(crescita, inflazione) in unita' di banda: +-1 = soglia d'ingresso in su/giu'."""
    mid, half = (INFLATION_HIGH + INFLATION_LOW) / 2, (INFLATION_HIGH - INFLATION_LOW) / 2
    return g_z / GROWTH_BAND, (i_score - mid) / half


def probabilities(g_z: float, i_score: float) -> dict:
    """Probabilita' dei 4 regimi, assumendo i due assi indipendenti. Stima, non frequenza storica."""
    xg, xi = axis_positions(g_z, i_score)
    pg, pi = _up_probability(xg), _up_probability(xi)
    return {
        "Goldilocks": pg * (1 - pi),
        "Reflazione": pg * pi,
        "Stagflazione": (1 - pg) * pi,
        "Deflazione": (1 - pg) * (1 - pi),
    }


def regime_history(growth: pd.Series, headline: pd.Series, core: pd.Series | None = None) -> pd.DataFrame:
    """Regime per mese con i due assi. growth: CLI (o PIL annuo); headline/core: inflazione annua.
    Gli assi hanno date diverse: l'ultimo stato noto di un asse resta valido finche' non arriva il nuovo."""
    gz, isc = growth_z(growth), inflation_score(headline, core)
    if gz.empty or isc.empty:
        raise ValueError(f"servono almeno {GROWTH_CHANGE_MONTHS + 1} mesi di crescita e inflazione")
    df = pd.DataFrame({
        "growth_z": gz,
        "growth": axis_states(gz, GROWTH_BAND, -GROWTH_BAND),
        "inflation_score": isc,
        "inflation": axis_states(isc, INFLATION_HIGH, INFLATION_LOW),
        "inflation_level": inflation_level(headline, core),
    }).ffill().dropna(subset=["growth", "inflation"])
    df["regime"] = [regime_name(g, i) for g, i in zip(df["growth"], df["inflation"])]
    return df


def classify_regime(growth: pd.Series, headline: pd.Series, core: pd.Series | None = None) -> str:
    return regime_history(growth, headline, core)["regime"].iloc[-1]
