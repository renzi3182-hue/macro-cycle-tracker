import pandas as pd

# Punteggio asset 1-100 (06/10/2026), stessa idea del punteggio dell'app di riferimento: e' la posizione in classifica
# dell'asset nell'universo, non una media di indicatori. Ogni pilastro si trasforma in percentile fra gli asset
# disponibili quel mese; il punteggio e' il percentile della media dei pilastri.
# Pilastri solo di prezzo, con letteratura solida e pesi uguali (nessuna ottimizzazione):
# - tendenza: prezzo contro la media mobile a 10 mesi (Faber, "A Quantitative Approach to Tactical Asset Allocation", 2007);
# - momentum: rendimento 12 mesi escluso l'ultimo (Jegadeesh-Titman 1993; Moskowitz-Ooi-Pedersen 2012).
# Verifica 1999-2026 (scripts/evaluate_score.py, 21 ETF, 3 mesi): IC +0.074 (t 2.0), positivo in entrambi i
# sottoperiodi; fascia 81-100 +0.41% mediano sulla media dell'universo, 1-20 -0.85%. Migliori 5 ribilanciati
# ogni mese 12.0%/anno, drawdown -18%, contro SPY 11.2% e -51% (senza costi).
# Tolto il pilastro rischio (volatilita' 12 mesi, bassa = meglio): fra classi di asset diverse ha IC -0.10
# (t -2.7) e annullava gli altri. L'anomalia low-volatility vale dentro l'azionario, non fra azioni,
# obbligazioni e cash: la scelta e' fatta dopo aver visto i dati, provate solo 3 varianti.
# Niente pilastro macro: la tabella regime -> asset non batte i portafogli statici (scripts/backtest_assets.py).
# Niente stagionalita': con 20-30 anni di storia per asset e' rumore.
# 11/10/2026, 28 ETF (aggiunti XLC, XLRE, QQQ, IWM, IWF, IWD, SMH per i settori del libro di riferimento, una sola
# variante provata): IC +0.076 (t 2.2), <2014 +0.049 (t 1.0, prima +0.067), >=2014 +0.107 (t 2.2); fascia 81-100
# +0.64% mediano, 1-20 -0.92%; migliori 5 14.6%/anno, drawdown -19% (piu' ETF azionari USA forti, es. QQQ e SMH).
# Tenuti: il totale non peggiora, il sottoperiodo prima del 2014 si'. Storici corti (XLRE 2015, XLC 2018): un ETF
# entra in classifica solo con 12 mesi di prezzi, fino ad allora e' NaN e non conta per MIN_ASSETS.
# 12/10/2026, soglie dell'app di riferimento (entra sopra 80, esce solo sotto 60) contro tutti gli asset sopra 80, 2002-2026
# senza costi: cambi di posizione da 25% a 15% al mese, ma 12,7%/anno contro 13,8%, drawdown uguale (-19%). Con costi
# da ETF il risparmio non copre la differenza: niente isteresi, la classifica resta mensile.
# Verifica point-in-time in scripts/evaluate_score.py.
TREND_MONTHS = 10
MOMENTUM_MONTHS = 12
MOMENTUM_SKIP_MONTHS = 1
MIN_ASSETS = 8  # sotto questi asset con tutti i pilastri, un mese non ha classifica
HORIZON_MONTHS = 3  # orizzonte della verifica: extra-rendimento nei 3 mesi successivi
BANDS = [0, 20, 40, 60, 80, 100]
STRONG, WEAK = 80, 40  # sopra STRONG / fino a WEAK: fasce con extra-rendimento storico positivo / negativo

ASSET_AREA = "Asset"  # area in cache: un indicatore per ticker, chiusura mensile rettificata

# ETF USA con storico lungo (dati Yahoo rettificati per dividendi). ticker -> (nome, gruppo)
UNIVERSE = {
    "SPY": ("USA", "Paesi"), "EZU": ("Eurozona", "Paesi"), "EWI": ("Italia", "Paesi"), "EWU": ("Regno Unito", "Paesi"),
    "EWJ": ("Giappone", "Paesi"), "EEM": ("Emergenti", "Paesi"),
    "XLK": ("Tecnologia", "Settori USA"), "XLF": ("Finanziari", "Settori USA"), "XLV": ("Salute", "Settori USA"),
    "XLE": ("Energia", "Settori USA"), "XLI": ("Industriali", "Settori USA"), "XLY": ("Consumi discrezionali", "Settori USA"),
    "XLP": ("Consumi di base", "Settori USA"), "XLU": ("Utility", "Settori USA"), "XLB": ("Materiali", "Settori USA"),
    "XLC": ("Comunicazioni", "Settori USA"), "XLRE": ("Immobiliare", "Settori USA"),
    "QQQ": ("Nasdaq 100", "Indici USA"), "IWM": ("Russell 2000", "Indici USA"), "IWF": ("Growth", "Indici USA"),
    "IWD": ("Value", "Indici USA"), "SMH": ("Semiconduttori", "Indici USA"),
    "TLT": ("Treasury 20+ anni", "Obbligazioni"), "IEF": ("Treasury 7-10 anni", "Obbligazioni"),
    "TIP": ("Indicizzate inflazione", "Obbligazioni"), "SHY": ("Treasury 1-3 anni", "Obbligazioni"),
    "GLD": ("Oro", "Materie prime"), "DBC": ("Materie prime", "Materie prime"),
}


def monthly_prices(prices: dict[str, pd.Series]) -> pd.DataFrame:
    """Una colonna per ticker, ultima chiusura di ogni mese (indice = inizio mese)."""
    return pd.DataFrame({t: s.resample("MS").last() for t, s in prices.items() if not s.empty})


def complete_months(px: pd.DataFrame, today: pd.Timestamp | None = None) -> pd.DataFrame:
    """Toglie il mese in corso: il punteggio vale a chiusura di mese, come nella verifica. Indice di date (inizio
    mese) o di periodi mensili (scripts/backtest_assets.py)."""
    today = pd.Timestamp.today() if today is None else today
    months = px.index.to_timestamp() if isinstance(px.index, pd.PeriodIndex) else px.index
    return px[months < today.normalize().replace(day=1)]


def pillars(px: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Valori grezzi dei pilastri, per mese e ticker: piu' alto = meglio."""
    return {
        "Tendenza": px / px.rolling(TREND_MONTHS).mean() - 1,
        "Momentum": px.shift(MOMENTUM_SKIP_MONTHS) / px.shift(MOMENTUM_MONTHS) - 1,
    }


def scores(px: pd.DataFrame) -> pd.DataFrame:
    """Punteggio 1-100 per mese e ticker. NaN per un asset senza tutti i pilastri o un mese con meno di MIN_ASSETS."""
    ranks = [p.rank(axis=1, pct=True) for p in pillars(px).values()]
    avg = sum(ranks) / len(ranks)  # NaN se manca anche un solo pilastro
    s = (avg.rank(axis=1, pct=True) * 100).round().clip(lower=1)
    return s.where(avg.notna().sum(axis=1) >= MIN_ASSETS, axis=0)


def forward_excess(px: pd.DataFrame, s: pd.DataFrame) -> pd.DataFrame:
    """Rendimento dei HORIZON_MONTHS mesi successivi meno la media dell'universo, dove c'e' un punteggio."""
    fwd = px.shift(-HORIZON_MONTHS) / px - 1
    return fwd.sub(fwd.mean(axis=1), axis=0).where(s.notna())


def band_table(s: pd.DataFrame, excess: pd.DataFrame) -> pd.DataFrame:
    """Per fascia di punteggio: casi, extra-rendimento mediano e medio (%), % di volte sopra la media."""
    long = pd.DataFrame({"score": s.stack(), "excess": excess.stack()}).dropna()
    long["fascia"] = pd.cut(long["score"], BANDS, labels=[f"{a + 1}-{b}" for a, b in zip(BANDS, BANDS[1:])])
    return long.groupby("fascia", observed=True)["excess"].agg(
        casi="size", mediana=lambda x: x.median() * 100, media=lambda x: x.mean() * 100, sopra=lambda x: (x > 0).mean() * 100)
