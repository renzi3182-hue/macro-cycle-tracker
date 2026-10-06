import pandas as pd

from src.classify.score import TREND_MONTHS

# Risk On/Off 0-100 (06/10/2026), spec v2 punto 7: quanto il mercato e' disposto a prendere rischio, a fine mese.
# Tre componenti a pesi uguali, ognuna gia' 0-100 (alto = risk on), senza ottimizzazione:
# - VIX basso: 100 - percentile del VIX sul suo storico fino a quel mese (point-in-time);
# - credito calmo: 100 - percentile dello spread Baa-10Y, stesso calcolo;
# - ampiezza: quota di ETF dell'universo del punteggio sopra la media a 10 mesi.
# Verifica 1999-2026 (scripts/evaluate_risk.py, 325 mesi): NON prevede il rendimento dell'S&P 500 (correlazione con i
# 3 mesi dopo +0.05, -0.17 dal 2014), prevede la volatilita': |rendimento| del mese dopo 5,8% in fascia 0-20 contro
# 2,3% in 80-100, correlazione -0.44 stabile nei due sottoperiodi. Usato come timing (SPY sopra 40, se no SHY)
# fa come il solo filtro di tendenza su SPY (7,9% vs 8,3%/anno, drawdown -23% vs -24%): nessun vantaggio in piu'.
# Soglie provate: 20, 40, 50, nessuna ottimizzata. Va presentato come termometro del rischio, non come segnale.
MIN_HISTORY_MONTHS = 60  # percentile solo con almeno 5 anni di storia
MIN_ASSETS = 8
BANDS = [0, 20, 40, 60, 80, 100]
LABELS = ["Risk Off estremo", "Risk Off", "Neutrale", "Risk On", "Risk On estremo"]


def month_end(s: pd.Series) -> pd.Series:
    return s.resample("MS").last().dropna()


def expanding_percentile(s: pd.Series) -> pd.Series:
    """Percentile 0-100 di ogni valore fra quelli fino a quella data: nessun dato futuro."""
    pct = s.expanding().apply(lambda x: (x <= x[-1]).mean() * 100, raw=True)
    return pct.where(s.expanding().count() >= MIN_HISTORY_MONTHS)


def breadth(px: pd.DataFrame) -> pd.Series:
    """Quota % di asset sopra la media a TREND_MONTHS mesi, fra quelli con la media disponibile."""
    sma = px.rolling(TREND_MONTHS).mean()
    valid = sma.notna() & px.notna()
    n = valid.sum(axis=1)
    return ((px > sma) & valid).sum(axis=1).div(n).mul(100).where(n >= MIN_ASSETS)


def components(vix: pd.Series, credit: pd.Series, px: pd.DataFrame) -> pd.DataFrame:
    """vix e credit giornalieri, px mensile (src/classify/score.monthly_prices). Una riga per mese."""
    return pd.DataFrame({
        "VIX": 100 - expanding_percentile(month_end(vix)),
        "Credito": 100 - expanding_percentile(month_end(credit)),
        "Ampiezza": breadth(px),
    })


def risk_score(comp: pd.DataFrame) -> pd.Series:
    """Media delle componenti disponibili, solo se ci sono tutte e tre."""
    return comp.mean(axis=1).where(comp.notna().all(axis=1))


def label(score: float) -> str:
    return LABELS[min(int(score // 20), len(LABELS) - 1)]
