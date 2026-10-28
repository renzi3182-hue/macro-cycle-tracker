import math

import pandas as pd

# Regime macro = crescita x inflazione, con la regola dell'app di riferimento (riscritto l'08/10/2026).
# L'app di riferimento e' quella scelta dall'utente: sulle 14 letture note (dashboard 10/2026, libro Q1 2024, trimestri
# 2015-2022 dal blog dell'autore) questa regola ne riproduce 13; il modello precedente (direzione del CLI
# OCSE + inflazione contro il 2%) 5, cioe' quanto il caso. Differenza di fondo: qui la crescita e' la
# VELOCITA' del PIL (annuo in accelerazione o in rallentamento sul trimestre prima), non il livello di attivita'
# in salita. Esempio USA 10/2026: CLI ancora in salita, ma PIL annuo 2,7% -> 2,1% = rallentamento -> Stagflazione.
# Prezzo: ~3 cambi di regime l'anno e lettura in tempo reale diversa da quella a posteriori ~1 mese su 2
# (il PIL esce 1 mese dopo il trimestre e viene rivisto). La fase del ciclo resta sul CLI (src/classify/cycle.py).
# Verifica in scripts/evaluate_model.py (sezione Letture di riferimento).
GROWTH_INPUT = "growth_yoy"
GROWTH_FALLBACK = "cli"
GROWTH_CHANGE_MONTHS = 3  # un trimestre: il PIL trimestrale riportato a mensile cambia ogni 3 mesi
GROWTH_BAND = 0.0  # niente zona neutra: accelera o rallenta, come l'app di riferimento
GROWTH_SCALE = 0.4  # per indicatori e solidita': z della variazione che vale "1" sulla scala dell'asse

# Inflazione "alta" se il CPI totale (media 3 mesi) sale rispetto ai 3 mesi prima: conta solo la direzione, come nel
# cap. 7 del libro di riferimento (scelta dell'utente del 25/10/2026: quando libro e app di riferimento divergono vale
# il libro). Fino al 25/10/2026 era alta anche con la media di totale + core sopra il 2,5%: 15/29 letture note contro
# 18/29 di ora (il libro 2023-2024 da 3/13 a 9/13, la dashboard dell'app di riferimento 2026Q3 da 3/5 a 1/5);
# numeri e costi in spec.md. Il core resta solo nel livello mostrato in pagina.
INFLATION_HIGH = 0.0  # punteggio = variazione 3 mesi della media 3 mesi, punti %
INFLATION_LOW = 0.0
INFLATION_SCALE = 0.5  # come GROWTH_SCALE, in punti %

CONFIRM_MONTHS = 1  # nessuna conferma: il PIL cambia una volta a trimestre
MIN_SCALE_MONTHS = 24  # sotto questi punti la deviazione standard usa tutto il campione

# Probabilita' (09/10/2026): regime del TRIMESTRE IN CORSO come risultera' a dati completi, non dell'etichetta
# (che usa l'ultimo PIL pubblicato, come l'app di riferimento). Regressione logistica dello stato a posteriori di ogni asse
# sulla lettura in tempo reale, 9 aree 2000-2026 con i ritardi di pubblicazione veri (scripts/evaluate_model.py,
# sezione Calibrazione). Crescita: l'ultimo PIL pubblicato non dice nulla sul trimestre dopo (peso ~0, e' gia'
# passato un trimestre); qualcosa dice l'attivita' mensile (produzione industriale, CLI dove manca), quindi la
# probabilita' resta vicina al 50% e puo' favorire un regime diverso dall'etichetta. Inflazione: persistente,
# lo stato a dati completi e' quello in tempo reale nell'84% dei mesi dal 2015 (88% con la soglia del 2,5%, tolta il
# 25/10/2026). Pesi senza intercetta (50% sulla soglia).
PROB_ACTIVITY_WEIGHT = 0.24  # per unita' di z della variazione 3 mesi dell'attivita'
PROB_INFLATION_WEIGHT = 4.2  # per punto % del punteggio d'inflazione (stimato 4,21 sul 2000-2014, 4,15 su tutto)

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


def inflation_score(headline: pd.Series) -> pd.Series:
    """Sopra 0 = inflazione in salita: media 3 mesi del CPI totale contro i 3 mesi prima, in punti %."""
    h = monthly(headline).rolling(GROWTH_CHANGE_MONTHS).mean()
    return (h - h.shift(GROWTH_CHANGE_MONTHS)).dropna()


def axis_states(score: pd.Series, high: float, low: float, confirm: int = CONFIRM_MONTHS) -> pd.Series:
    """'up' sopra high, 'down' sotto low, in mezzo resta lo stato precedente; un cambio vale dopo `confirm` mesi."""
    states, current, pending, count = [], None, None, 0
    for v in score:
        if current is None:
            current = "up" if v > (high + low) / 2 else "down"
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


AXIS_STATES = ("up", "down")
REGIME_AXES = {regime_name(g, i): (g, i) for g in AXIS_STATES for i in AXIS_STATES}  # "Goldilocks" -> ("up", "down")


def axis_positions(g_z: float, i_score: float) -> tuple[float, float]:
    """(crescita, inflazione) in unita' di scala dalla soglia: 0 = sulla soglia. Per indicatori e solidita'."""
    return g_z / GROWTH_SCALE, (i_score - (INFLATION_HIGH + INFLATION_LOW) / 2) / INFLATION_SCALE


def activity_z(industrial_production: pd.Series | None = None, cli: pd.Series | None = None) -> pd.Series:
    """Attivita' mensile per le probabilita': variazione 3 mesi della produzione industriale annua (media 3 mesi)
    o, dove manca, del CLI OCSE, in deviazioni standard."""
    if industrial_production is not None and not industrial_production.empty:
        return growth_z(monthly(industrial_production).rolling(GROWTH_CHANGE_MONTHS).mean().dropna())
    if cli is not None and not cli.empty:
        return growth_z(cli)
    return pd.Series(dtype=float)


def _logistic(x: float) -> float:
    return 1 / (1 + math.exp(-max(-30.0, min(30.0, x))))


def probabilities(activity: float | None, i_score: float) -> dict:
    """Probabilita' dei 4 regimi per il trimestre in corso, assi indipendenti. Senza attivita' la crescita vale 50%."""
    pg = 0.5 if activity is None or math.isnan(activity) else _logistic(PROB_ACTIVITY_WEIGHT * activity)
    pi = _logistic(PROB_INFLATION_WEIGHT * i_score)
    return {
        "Goldilocks": pg * (1 - pi),
        "Reflazione": pg * pi,
        "Stagflazione": (1 - pg) * pi,
        "Deflazione": (1 - pg) * (1 - pi),
    }


def regime_history(growth: pd.Series, headline: pd.Series, core: pd.Series | None = None) -> pd.DataFrame:
    """Regime per mese con i due assi. growth: PIL annuo (o CLI); headline/core: inflazione annua.
    Gli assi hanno date diverse: l'ultimo stato noto di un asse resta valido finche' non arriva il nuovo."""
    gz, isc = growth_z(growth), inflation_score(headline)
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
