import pandas as pd

# Backtest NBER 1970-2026 (scripts/backtest_nber.py): Sahm da solo ha 2 falsi
# allarmi (2003, 2024); Chauvet-Piger >= 50% ne ha 0 ma manca il 2001. Sahm
# confermato da CP >= 10% ha 0 falsi allarmi, nessuna recessione mancata, stessi
# lag di Sahm (0-3 mesi, 7 nel 1973). CP e' la serie smoothed FRED (usa dati
# successivi), quindi in tempo reale la conferma sara' meno pulita.
SAHM_THRESHOLD = 0.5  # punti: media 3m disoccupazione sopra il minimo dei 12 mesi precedenti
CP_CONFIRM = 10.0  # % Chauvet-Piger che conferma un Sahm attivo
CP_CERTAIN = 50.0  # % Chauvet-Piger sufficiente da solo


def sahm_gap(unrate: pd.Series) -> pd.Series:
    """Distanza (punti) della media 3m della disoccupazione dal minimo dei 12 mesi precedenti."""
    ma3 = unrate.resample("MS").mean().dropna().rolling(3).mean()
    return ma3 - ma3.shift(1).rolling(12).min()


def recession_confirmed(unrate: pd.Series, recession_prob: pd.Series) -> bool:
    """True se gli ultimi dati indicano recessione in corso. Dati mancanti = nessun segnale."""
    if unrate.empty or recession_prob.empty:
        return False
    gap = sahm_gap(unrate).dropna()
    sahm_on = not gap.empty and gap.iloc[-1] >= SAHM_THRESHOLD
    cp = recession_prob.iloc[-1]
    return cp >= CP_CERTAIN or (sahm_on and cp >= CP_CONFIRM)
