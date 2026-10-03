import pandas as pd

# Backtest NBER 1970-2026 (scripts/backtest_nber.py): Sahm da solo ha 2 falsi
# allarmi (2003, 2024); Chauvet-Piger >= 50% ne ha 0 ma manca il 2001. Sahm
# confermato da CP >= 10% ha 0 falsi allarmi, nessuna recessione mancata, stessi
# lag di Sahm (0-3 mesi, 7 nel 1973). CP e' la serie smoothed FRED (usa dati
# successivi), quindi in tempo reale la conferma sara' meno pulita.
# Fuori dagli USA non c'e' una probabilita' tipo CP: Sahm deve reggere 2 mesi di fila. La disoccupazione
# europea e' rumorosa (Italia ago 2026: Sahm 0.5 per un mese con PIL +1%); la conferma toglie quel falso
# allarme e nello storico 2000-2022 perde solo 0-3 punti di mesi di recessione (scripts/evaluate_model.py).
SAHM_THRESHOLD = 0.5  # punti: media 3m disoccupazione sopra il minimo dei 12 mesi precedenti
SAHM_CONFIRM_MONTHS = 2  # senza probabilita' CP
CP_CONFIRM = 10.0  # % Chauvet-Piger che conferma un Sahm attivo
CP_CERTAIN = 50.0  # % Chauvet-Piger sufficiente da solo


def sahm_gap(unrate: pd.Series) -> pd.Series:
    """Distanza (punti) della media 3m della disoccupazione dal minimo dei 12 mesi precedenti."""
    ma3 = unrate.resample("MS").mean().dropna().rolling(3).mean()
    return ma3 - ma3.shift(1).rolling(12).min()


def recession_flags(unrate: pd.Series, recession_prob: pd.Series | None = None) -> pd.Series:
    """Recessione in corso, mese per mese. Con la probabilita' Chauvet-Piger (USA) Sahm va confermato."""
    if unrate.empty:
        return pd.Series(dtype=bool)
    sahm = sahm_gap(unrate) >= SAHM_THRESHOLD
    if recession_prob is None or recession_prob.empty:
        return sahm.rolling(SAHM_CONFIRM_MONTHS).min().fillna(0).astype(bool)
    cp = recession_prob.resample("MS").last().reindex(sahm.index).ffill()
    return (sahm & (cp >= CP_CONFIRM)) | (cp >= CP_CERTAIN)


def recession_confirmed(unrate: pd.Series, recession_prob: pd.Series) -> bool:
    """True se gli ultimi dati indicano recessione in corso. Dati mancanti = nessun segnale."""
    if unrate.empty or recession_prob.empty:
        return False
    flags = recession_flags(unrate, recession_prob)
    return not flags.empty and bool(flags.iloc[-1])
