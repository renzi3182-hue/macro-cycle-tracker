import numpy as np
import pandas as pd

# Punteggio asset 1-100 a cinque pilastri (19/10/2026), struttura dell'app di riferimento: Tendenza, Momentum, Rischio,
# Stagionalita', Macro. Il punteggio e' tarato sulla probabilita' di battere la media degli asset nei 3 mesi successivi.
# Differenza voluta dall'app di riferimento: la taratura e' walk-forward. Ogni mese una regressione logistica stima i pesi
# dei pilastri solo sui casi gia' conclusi (esito a 3 mesi noto), e i pesi non sono scelti a mano. Un pilastro inutile
# prende un peso vicino a zero da solo; i pesi di oggi si vedono nella pagina Classifica.
# - Tendenza: prezzo contro la media mobile a 10 mesi (Faber 2007).
# - Momentum: rendimento 12 mesi escluso l'ultimo (Jegadeesh-Titman 1993; Moskowitz-Ooi-Pedersen 2012).
# - Rischio: volatilita' 12 mesi, bassa = punteggio del pilastro alto. Il peso lo decide la regressione: fra classi di
#   asset diverse esce negativo (gli asset piu' volatili hanno battuto la media), come gia' visto nella prima versione.
# - Stagionalita': extra-rendimento medio dell'asset negli stessi 3 mesi di calendario degli anni passati (Heston-Sadka
#   2008), almeno 10 anni di storia.
# - Macro: extra-rendimento medio a 3 mesi dell'asset nei mesi passati con lo stesso regime USA di oggi. Il regime e'
#   spostato di MACRO_LAG_MONTHS mesi per il ritardo di pubblicazione del PIL; usa pero' i dati rivisti, non quelli
#   dell'epoca (stesso limite di scripts/backtest_assets.py).
# Storico esteso: prima della nascita di ogni ETF si usano i rendimenti di serie gratuite piu' lunghe (PROXY): mercato
# e settori USA dalla Kenneth French Data Library (dal 1926), Treasury da rendimenti FRED con un'approssimazione per
# duration. La regressione si addestra cosi' su ~90 anni invece di ~25; la verifica e il punteggio mostrato restano
# solo sui mesi con il prezzo vero dell'ETF.
# Verifica (scripts/evaluate_score.py, 19/10/2026, 32 ETF, 1999-2026, stessi mesi e asset della prima versione):
# IC +0.081 (t 2.7) contro +0.075 (t 2.2); <2014 +0.056 contro +0.062, >=2014 +0.111 contro +0.088. Fasce in ordine
# (1-20 -1,10% mediano, 81-100 +0,55%; prima -0,58% e +0,75%): separa meglio gli asset da evitare, un po' peggio i
# migliori. 2002-2026 senza costi: migliori 5 ribilanciati ogni mese 14,2%/anno, drawdown -28%, contro 14,5% e -18%
# della prima versione (SPY 11,2% e -51%); segnale attivo (entra sopra 80, esce sotto 60) 12,4% e -26%.
# Pesi solo positivi (_fit), scelta motivata a priori (ogni pilastro lavora solo nella direzione per cui esiste) ma
# fatta dopo aver visto la versione libera: IC +0.091 (t 3.1) ma migliori 5 12,3%/anno e drawdown -40%, perche' il
# peso negativo del Rischio premiava gli asset piu' volatili. Con i pesi positivi il Rischio esce (peso 0).
# Altre varianti, versione libera: senza un pilastro alla volta IC fra 0,081 e 0,094; addestrata solo sui mesi con ETF
# veri (senza storico esteso) IC +0.076 e migliori 5 8,3%/anno nel 2000-2026: lo storico esteso serve.
# Taratura fuori campione: probabilita' prevista 40-45% -> 43% di volte sopra la media; 50-55% -> 53%; 55-60% -> 54%.
#
# Prima versione (06-19/10/2026, solo Tendenza e Momentum a pesi uguali, punteggio = percentile della media dei
# percentili): IC +0.075 (t 2.2) su 32 ETF; il pilastro rischio da solo IC -0.10 (t -2.7) a pesi uguali annullava gli
# altri; rendimento da dividendo come pilastro valutazione IC -0.026 (t -0.8), scartato; entrare sopra 80 e uscire
# sotto 60 riduceva i cambi del 40% ma rendeva 1,1 punti l'anno in meno (12,7% contro 13,8%, 2002-2026).
TREND_MONTHS = 10
MOMENTUM_MONTHS = 12
MOMENTUM_SKIP_MONTHS = 1
RISK_MONTHS = 12
SEASONAL_MIN_YEARS = 10
MACRO_LAG_MONTHS = 4  # PIL del trimestre pubblicato circa un mese dopo la fine: 4 mesi dall'inizio del trimestre
MACRO_MIN_CASES = 24  # mesi passati con lo stesso regime, sotto questi il pilastro e' neutro
MIN_ASSETS = 8  # sotto questi asset con tendenza e momentum, un mese non ha classifica
HORIZON_MONTHS = 3  # orizzonte della taratura e della verifica: extra-rendimento nei 3 mesi successivi
MIN_TRAIN_MONTHS = 120  # mesi di storia (esiti noti) prima della prima stima
REFIT_MONTHS = 12  # i pesi si ristimano ogni 12 mesi: piu' spesso cambia poco e rallenta l'app
L2 = 1.0  # piccola penalita' sui pesi: stime stabili con pilastri correlati (tendenza e momentum)
BANDS = [0, 20, 40, 60, 80, 100]
STRONG, WEAK = 80, 40  # sopra STRONG / fino a WEAK: fasce con extra-rendimento storico positivo / negativo
ENTER, EXIT = 80, 60  # segnale attivo sopra ENTER, si spegne solo sotto EXIT
PILLARS = ["Tendenza", "Momentum", "Rischio", "Stagionalità", "Macro"]

ASSET_AREA = "Asset"  # area in cache: un indicatore per ticker, chiusura mensile rettificata
HISTORY_AREA = "Storico"  # area in cache: rendimenti mensili French (per settore e Mkt) e rendimenti FRED in %

# ETF USA con storico lungo (dati Yahoo rettificati per dividendi). ticker -> (nome, gruppo)
UNIVERSE = {
    "SPY": ("USA", "Paesi"), "EZU": ("Eurozona", "Paesi"), "EWI": ("Italia", "Paesi"), "EWU": ("Regno Unito", "Paesi"),
    "EWJ": ("Giappone", "Paesi"), "EEM": ("Emergenti", "Paesi"), "EWC": ("Canada", "Paesi"), "EWA": ("Australia", "Paesi"),
    "MCHI": ("Cina", "Paesi"), "INDA": ("India", "Paesi"),
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
# Serie piu' lunghe per gli anni prima dell'ETF. Settori French (12 industrie) -> settore SPDR piu' vicino.
PROXY = {"SPY": "Mkt", "XLK": "BusEq", "XLF": "Money", "XLV": "Hlth", "XLE": "Enrgy", "XLI": "Manuf", "XLY": "Shops",
         "XLP": "NoDur", "XLU": "Utils", "XLB": "Chems", "XLC": "Telcm"}
# Treasury: rendimento mensile ~ cedola/12 - duration * variazione del rendimento (FRED, dal 1953). Duration tipiche.
BOND_PROXY = {"IEF": ("GS10", 7.5), "TLT": ("GS10", 16.0), "SHY": ("GS1", 1.9)}
HISTORY_SERIES = sorted({*PROXY.values(), *(s for s, _ in BOND_PROXY.values())})


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
    """Pilastri di solo prezzo, valori grezzi per mese e ticker: piu' alto = meglio."""
    return {
        "Tendenza": px / px.rolling(TREND_MONTHS).mean() - 1,
        "Momentum": px.shift(MOMENTUM_SKIP_MONTHS) / px.shift(MOMENTUM_MONTHS) - 1,
        "Rischio": -px.pct_change(fill_method=None).rolling(RISK_MONTHS).std(),
    }


def proxy_returns(history: dict[str, pd.Series]) -> pd.DataFrame:
    """Rendimenti mensili delle serie lunghe, una colonna per ticker (PROXY e BOND_PROXY), indice = inizio mese."""
    out = {t: history[s] for t, s in PROXY.items() if s in history}
    for t, (s, duration) in BOND_PROXY.items():
        if s in history:
            y = history[s].resample("MS").mean()
            out[t] = y.shift(1) / 1200 - duration * y.diff() / 100
    return pd.DataFrame(out)


def extended_prices(px: pd.DataFrame, proxies: pd.DataFrame | None) -> pd.DataFrame:
    """Prezzi mensili degli ETF allungati all'indietro con i rendimenti di proxies fino al primo prezzo vero."""
    r = px.pct_change(fill_method=None)
    if proxies is not None and not proxies.empty:
        idx = proxies.index.union(r.index)
        idx = pd.date_range(idx[0], idx[-1], freq="MS")
        r = r.reindex(idx)
        for t in proxies.columns.intersection(px.columns):
            first = px[t].first_valid_index()
            if first is not None:
                before = idx <= first
                r.loc[before, t] = proxies[t].reindex(idx)[before]
    started = (r.notna() | px.reindex(r.index).notna()).cummax()
    return (1 + r.fillna(0)).cumprod().where(started)


def forward_excess(px: pd.DataFrame, s: pd.DataFrame) -> pd.DataFrame:
    """Rendimento dei HORIZON_MONTHS mesi successivi meno la media dell'universo, dove c'e' un punteggio."""
    fwd = px.shift(-HORIZON_MONTHS) / px - 1
    return fwd.sub(fwd.mean(axis=1), axis=0).where(s.notna())


def seasonality(px: pd.DataFrame) -> pd.DataFrame:
    """Extra-rendimento medio (contro la media degli asset) nei HORIZON_MONTHS mesi di calendario dopo il mese t,
    sugli anni gia' passati. NaN con meno di SEASONAL_MIN_YEARS anni."""
    r = px.pct_change(fill_method=None)
    ex = r.sub(r.mean(axis=1), axis=0)
    out = pd.DataFrame(np.nan, index=px.index, columns=px.columns)
    for m in range(1, 13):
        ahead = [(m + k - 1) % 12 + 1 for k in range(1, HORIZON_MONTHS + 1)]
        sel = ex[ex.index.month.isin(ahead)]
        at = px.index[px.index.month == m]
        total, n = sel.cumsum().reindex(at, method="ffill"), sel.notna().cumsum().reindex(at, method="ffill")
        out.loc[at] = (total / n * HORIZON_MONTHS).where(n >= SEASONAL_MIN_YEARS * HORIZON_MONTHS).values
    return out


def macro(px: pd.DataFrame, regime: pd.Series | None) -> pd.DataFrame:
    """Extra-rendimento medio a HORIZON_MONTHS mesi dell'asset nei mesi passati (esito gia' noto) con lo stesso regime
    di oggi. regime: etichetta mensile USA (assess()["history"]["regime"])."""
    out = pd.DataFrame(np.nan, index=px.index, columns=px.columns)
    if regime is None or regime.empty:
        return out
    reg = regime.copy()
    reg.index = reg.index.to_period("M").to_timestamp()
    reg = reg[~reg.index.duplicated(keep="last")].reindex(px.index).ffill().shift(MACRO_LAG_MONTHS)
    fwd = px.shift(-HORIZON_MONTHS) / px - 1
    known, reg_known = fwd.sub(fwd.mean(axis=1), axis=0).shift(HORIZON_MONTHS), reg.shift(HORIZON_MONTHS)
    for name in reg.dropna().unique():
        same = known.where(reg_known == name, axis=0)
        n = same.notna().cumsum()
        out = out.where(reg != name, (same.cumsum() / n).where(n >= MACRO_MIN_CASES))
    return out


def _logistic(x: np.ndarray, y: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Regressione logistica con penalita' L2 (non sull'intercetta), metodo di Newton. x con colonna di 1 in testa."""
    pen = L2 * np.diag(np.r_[0.0, np.ones(x.shape[1] - 1)])
    for _ in range(25):
        p = 1 / (1 + np.exp(-x @ w))
        step = np.linalg.solve((x * (p * (1 - p))[:, None]).T @ x + pen, x.T @ (p - y) + pen @ w)
        w = w - step
        if np.abs(step).max() < 1e-6:
            break
    return w


def _fit(x: np.ndarray, y: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Pesi dei pilastri solo positivi: un pilastro che i dati vorrebbero al contrario esce (peso 0) e si ristima."""
    active = np.ones(x.shape[1], bool)
    while True:
        w = np.where(active, w, 0.0)
        w[active] = _logistic(x[:, active], y, w[active])
        negative = active & (w < 0)
        negative[0] = False  # l'intercetta puo' essere negativa
        if not negative.any():
            return w
        active &= ~negative


def model(px: pd.DataFrame, proxies: pd.DataFrame | None = None, regime: pd.Series | None = None) -> dict:
    """Punteggio a cinque pilastri tarato walk-forward. px: prezzi mensili degli ETF (mesi chiusi); proxies:
    proxy_returns(); regime: regime USA mensile. Ritorna, sui mesi di px:
    score 1-100 (percentile della probabilita' fra gli asset del mese), prob (probabilita' 0-1 di battere la media a
    HORIZON_MONTHS mesi), contrib (per pilastro: peso * posizione, la spinta sulla probabilita'), weights (pesi per
    mese di stima). NaN per asset senza tendenza e momentum o mesi con meno di MIN_ASSETS asset o di storia."""
    ext = extended_prices(px, proxies)
    raw = {**pillars(ext), "Stagionalità": seasonality(ext), "Macro": macro(ext, regime)}
    valid = raw["Tendenza"].notna() & raw["Momentum"].notna()
    ranks = {k: (raw[k].rank(axis=1, pct=True) - 0.5).fillna(0).where(valid) for k in PILLARS}  # mancante = neutro
    feats = np.stack([ranks[k].values for k in PILLARS], axis=-1)
    fwd = ext.shift(-HORIZON_MONTHS) / ext - 1
    fwd = fwd.sub(fwd.mean(axis=1), axis=0).where(valid)
    y = np.where(fwd.notna(), (fwd > 0).astype(float), np.nan)
    month_ok = valid.sum(axis=1).values >= MIN_ASSETS
    prob = np.full(valid.shape, np.nan)
    weights, w, last_fit = {}, np.zeros(len(PILLARS) + 1), None
    for i in np.flatnonzero(month_ok):
        if last_fit is None or i - last_fit >= REFIT_MONTHS:
            known = slice(0, i - HORIZON_MONTHS + 1)  # a fine mese i l'esito e' noto fino al mese i - HORIZON
            x, t = feats[known].reshape(-1, len(PILLARS)), y[known].reshape(-1)
            ok = ~np.isnan(x).any(axis=1) & ~np.isnan(t)
            if month_ok[known].sum() < MIN_TRAIN_MONTHS:
                continue
            w, last_fit = _fit(np.c_[np.ones(ok.sum()), x[ok]], t[ok], w), i
        weights[ext.index[i]] = w
        row = feats[i]
        good = ~np.isnan(row).any(axis=1)
        prob[i, good] = 1 / (1 + np.exp(-(w[0] + row[good] @ w[1:])))
    prob = pd.DataFrame(prob, index=ext.index, columns=ext.columns).reindex(index=px.index, columns=px.columns)
    prob = prob.where(px.notna())
    prob = prob.where(prob.notna().sum(axis=1) >= MIN_ASSETS, axis=0)
    weights = pd.DataFrame(weights, index=["Costante", *PILLARS]).T.reindex(px.index).dropna()
    contrib = {k: ranks[k].reindex(index=px.index, columns=px.columns).mul(weights[k], axis=0).where(prob.notna()) for k in PILLARS}
    score = (prob.rank(axis=1, pct=True) * 100).round().clip(lower=1)
    return {"score": score, "prob": prob, "contrib": contrib, "weights": weights}


def scores(px: pd.DataFrame, proxies: pd.DataFrame | None = None, regime: pd.Series | None = None) -> pd.DataFrame:
    return model(px, proxies, regime)["score"]


def hysteresis(s: pd.DataFrame, enter: float = ENTER, exit_: float = EXIT) -> pd.DataFrame:
    """True da quando il punteggio supera enter finche' non scende sotto exit_ (o sparisce)."""
    out, held = [], pd.Series(False, index=s.columns)
    for _, row in s.iterrows():
        held = (row > enter) | (held & (row >= exit_))
        out.append(held)
    return pd.DataFrame(out, index=s.index)


def band_table(s: pd.DataFrame, excess: pd.DataFrame) -> pd.DataFrame:
    """Per fascia di punteggio: casi, extra-rendimento mediano e medio (%), % di volte sopra la media."""
    long = pd.DataFrame({"score": s.stack(), "excess": excess.stack()}).dropna()
    long["fascia"] = pd.cut(long["score"], BANDS, labels=[f"{a + 1}-{b}" for a, b in zip(BANDS, BANDS[1:])])
    return long.groupby("fascia", observed=True)["excess"].agg(
        casi="size", mediana=lambda x: x.median() * 100, media=lambda x: x.mean() * 100, sopra=lambda x: (x > 0).mean() * 100)
