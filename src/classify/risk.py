import pandas as pd

# Risk On/Off 0-100, giornaliero (12/10/2026; la prima versione del 06/10/2026 era a fine mese, spec v2 punto 7):
# quanto il mercato e' disposto a prendere rischio. Cinque componenti a pesi uguali, ognuna gia' 0-100 (alto = risk
# on), senza ottimizzazione:
# - VIX basso: 100 - percentile del VIX sul suo storico fino a quel giorno (point-in-time);
# - credito calmo: 100 - percentile dello spread Baa-10Y, stesso calcolo;
# - ampiezza: quota di ETF dell'universo del punteggio sopra la media a 200 sedute (circa 10 mesi);
# - struttura del VIX: 100 - percentile di VIX / VIX a 3 mesi (sopra 1 = paura concentrata sul breve termine);
# - consumi: percentile di XLY/XLP rispetto alla sua media a 200 sedute (discrezionali contro beni di base).
# Struttura e consumi vengono dal Risk On/Off dell'app di riferimento (letto dalla dashboard il 12/10/2026), con lo stesso
# percentile delle altre componenti invece dei loro punti fissi.
# Verifica (scripts/evaluate_risk.py, 12/10/2026, 3420 sedute 2012-2026, finestra del VIX a 3 mesi): come la
# versione mensile prevede la volatilita', non il rendimento. Correlazione con la volatilita' dei 21 giorni dopo -0.51
# (solo VIX, credito e ampiezza -0.47), -0.52 prima del 2019 e -0.51 dopo; con il rendimento -0.17. Fascia 0-20:
# volatilita' dopo 30%, 80-100: 11%. Struttura e consumi aggiungono poco ma non peggiorano nessun sottoperiodo: tenuti.
# Usato come timing (SPY sopra 40, se no SHY) 11,7%/anno contro 12,2% del filtro di tendenza: nessuno split
# Risk assets/Difensivo/Cash.
# Canarino: momentum 13612W di TIP (Keller-Keuning, Defensive Asset Allocation 2018, che pero' usa VWO e BND;
# l'app di riferimento usa TIP). Mostrato a parte, non entra nel punteggio: come tetto (massimo 59 con canarino in allarme)
# peggiorava la correlazione con la volatilita' (-0.49). 2004-2026: in allarme il 28% delle sedute, calo dell'S&P 500
# oltre il 10% entro 63 sedute 20% contro 11%. Come timing giornaliero 14,4%/anno contro 11,0% di SPY, ma il
# risultato dipende dalla variante (ricerca del 12/10/2026: TIP a 12 mesi 9,1%, segnale a fine mese 10,3% contro 10,9%):
# va letto come allarme sul rischio, non come segnale operativo.
MIN_HISTORY_DAYS = 1260  # percentile solo con almeno 5 anni di sedute
TREND_DAYS = 200
MIN_ASSETS = 8
FILL_DAYS = 5  # calendari diversi (FRED, Yahoo, festivi dei bond): un dato vale al massimo 5 giorni
BANDS = [0, 20, 40, 60, 80, 100]
LABELS = ["Risk Off estremo", "Risk Off", "Neutrale", "Risk On", "Risk On estremo"]
CANARY = "TIP"


def expanding_percentile(s: pd.Series) -> pd.Series:
    """Percentile 0-100 di ogni valore fra quelli fino a quella data: nessun dato futuro."""
    return s.dropna().expanding(MIN_HISTORY_DAYS).rank(method="max", pct=True) * 100


def breadth(px: pd.DataFrame) -> pd.Series:
    """Quota % di asset sopra la media a TREND_DAYS sedute, fra quelli con la media disponibile."""
    sma = px.rolling(TREND_DAYS).mean()
    valid = sma.notna() & px.notna()
    n = valid.sum(axis=1)
    return ((px > sma) & valid).sum(axis=1).div(n).mul(100).where(n >= MIN_ASSETS)


def components(vix: pd.Series, vix3m: pd.Series, credit: pd.Series, xly: pd.Series, xlp: pd.Series,
               px: pd.DataFrame) -> pd.DataFrame:
    """Serie giornaliere; px = chiusure giornaliere rettificate degli ETF dell'universo. Una riga per data."""
    consumer = xly / xlp
    return pd.DataFrame({
        "VIX": 100 - expanding_percentile(vix),
        "Credito": 100 - expanding_percentile(credit),
        "Ampiezza": breadth(px),
        "Struttura": 100 - expanding_percentile(vix / vix3m),
        "Consumi": expanding_percentile(consumer / consumer.rolling(TREND_DAYS).mean() - 1),
    }).ffill(limit=FILL_DAYS)


def risk_score(comp: pd.DataFrame) -> pd.Series:
    """Media delle componenti, solo se ci sono tutte."""
    return comp.mean(axis=1).where(comp.notna().all(axis=1))


def canary(tip: pd.Series) -> pd.Series:
    """Momentum 13612W su sedute (1, 3, 6, 12 mesi pesati 12, 4, 2, 1): sotto zero il canarino e' in allarme."""
    r = lambda days: tip / tip.shift(days) - 1
    return (12 * r(21) + 4 * r(63) + 2 * r(126) + r(252)) / 4


def label(score: float) -> str:
    return LABELS[min(int(score // 20), len(LABELS) - 1)]
