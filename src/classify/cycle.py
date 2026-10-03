import pandas as pd

from src.classify.regime import monthly

# Fase del ciclo mensile (riscritta il 03/10/2026), 3 ingredienti:
# - momentum: lo stesso asse crescita del regime (direzione del CLI OCSE), cosi' fase e regime non si contraddicono;
# - livello: economia sopra/sotto il trend = PIL annuo contro la sua media degli ultimi 10 anni (rivisto il
#   03/10/2026: la disoccupazione contro la sua media 10 anni coincideva con la crescita sopra il trend a
#   posteriori solo nel 42-57% dei mesi, perche' in Europa e Giappone scende da anni per demografia; il PIL
#   point-in-time arriva al 66-76%). Senza PIL: disoccupazione non in salita sui 12 mesi (60-71%);
# - recessione: solo con conferma da dati "duri" (regola di Sahm, PIL annuo <= 0), mai dal solo CLI.
# Verifica in scripts/evaluate_model.py con ritardi di pubblicazione veri (1990-2026): USA, mesi NBER in
# Rallentamento/Recessione 94% (Recessione 69%), Recessione fuori NBER 2%; ~1 cambio di fase l'anno.
LEVEL_WINDOW_MONTHS = 120
LEVEL_MIN_MONTHS = 60
UNEMPLOYMENT_CHANGE_MONTHS = 12  # solo senza PIL
RECESSION_GDP = 0.0  # PIL annuo <= 0 = recessione confermata

PHASES = ["Espansione", "Rallentamento", "Recessione", "Ripresa"]


def above_potential(unemployment: pd.Series | None, gdp: pd.Series | None) -> pd.Series:
    """True/False per mese, NaN finche' non c'e' abbastanza storia."""
    if gdp is not None and not gdp.empty:
        s = monthly(gdp)
        avg = s.rolling(LEVEL_WINDOW_MONTHS, min_periods=LEVEL_MIN_MONTHS).mean()
        return (s >= avg).where(avg.notna())
    if unemployment is not None and not unemployment.empty:
        change = monthly(unemployment).diff(UNEMPLOYMENT_CHANGE_MONTHS)
        return (change <= 0).where(change.notna())
    raise ValueError("serve il PIL o la disoccupazione per il livello del ciclo")


def phase_name(growth_state: str, above: bool, recession: bool) -> str:
    if recession:
        return "Ripresa" if growth_state == "up" else "Recessione"  # CLI gia' in risalita: si esce dal fondo
    if growth_state == "down":
        return "Rallentamento"
    return "Espansione" if above else "Ripresa"


def phase_history(growth_states: pd.Series, unemployment: pd.Series | None = None, gdp: pd.Series | None = None,
                  recession: pd.Series | None = None) -> pd.Series:
    """Fase per mese. growth_states: 'up'/'down' dell'asse crescita (regime_history()['growth'])."""
    rec = pd.Series(False, index=growth_states.index)
    if recession is not None and not recession.empty:
        rec = rec | recession.reindex(growth_states.index).ffill().fillna(False).astype(bool)
    if gdp is not None and not gdp.empty:
        rec = rec | (monthly(gdp) <= RECESSION_GDP).reindex(growth_states.index).ffill().fillna(False).astype(bool)
    df = pd.DataFrame({"g": growth_states, "a": above_potential(unemployment, gdp), "r": rec}).ffill().dropna()
    return pd.Series([phase_name(g, bool(a), bool(r)) for g, a, r in zip(df["g"], df["a"], df["r"])], index=df.index)
