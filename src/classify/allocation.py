"""Allocazione di lungo periodo (21/10/2026; PAC e investimenti fissi, orizzonte 6-12 mesi, non trading): tre
classifiche con punteggio 1-100 relativo (posizione fra gli elementi del mese, 50 = meta' classifica).
- Paesi: azioni delle 9 aree, rendimento totale in dollari.
- Classi di asset dentro ogni paese: azioni, decennale di Stato, liquidita' a 3 mesi, oro, in valuta locale.
- Valute: le 8 valute dell'app, rendimento in dollari di tenere liquidita' in quella valuta (cambio + tasso).
Come la Classifica (score.py): pilastri in posizione relativa, regressione logistica con pesi solo positivi
(score._fit), probabilita' di battere la media nei 6 mesi dopo; il punteggio e' la posizione per probabilita'.
Fonti: fiducia di consumatori e imprese e tassi OCSE, cambio reale BIS, COT CFTC, mercati per paese French, ETF Yahoo,
cambi e tassi FRED, oro datahub. Verifica a rotazione e periodo finale bloccato: scripts/evaluate_allocation.py.
"""
import math

import numpy as np
import pandas as pd

from src.classify.score import _fit

AREA = "Allocazione"  # area in cache delle serie usate solo qui (src/scheduler/update_data.update_allocation)
HORIZON = 6  # mesi: orizzonte della taratura e della verifica (allocazione 6-12 mesi, non trading)
MIN_TRAIN_MONTHS = 60  # mesi con esito noto prima di una stima
MIN_ITEMS = 5  # sotto questi elementi con dati, un mese non ha classifica
ENTER, EXIT = 80, 60  # piu' peso sopra ENTER, si toglie sotto EXIT (come la Classifica)

# Verifica a rotazione (come le slide dell'app di riferimento): quattro periodi di 7 anni, in ognuno le regole si
# stimano su tutto quello che c'e' prima della finestra di verifica (gli ultimi 3 anni del periodo) e si provano
# sulla finestra, senza ristimare. Le varianti si scelgono solo su queste quattro finestre.
FOLDS = [("1991-01-01", "1995-01-01", "1997-12-01"), ("1998-01-01", "2002-01-01", "2004-12-01"),
         ("2005-01-01", "2009-01-01", "2011-12-01"), ("2012-01-01", "2016-01-01", "2018-12-01")]
# Periodo finale bloccato: mai usato per scegliere pilastri, segni o parametri. Pesi stimati con gli esiti noti
# a fine 2018 e tenuti fissi fino a oggi.
HOLDOUT_START = "2019-01-01"

# Esito della verifica (scripts/evaluate_allocation.py, 21/10/2026, orizzonte 6 mesi, niente costi), mostrato nella
# pagina Allocazione. Un segnale vale solo se ha vantaggio sia nelle finestre di verifica sia nel periodo finale.
# - Paesi: finestre IC +0.047 (t 0.6); finale IC +0.084 (t 0.8), migliori 3 9,6%/anno contro 10,4% a pesi uguali e
#   16,2% degli USA, battono il 38% di 500 portafogli a caso. Nessun vantaggio: descrittiva.
# - Classi di asset: finestre IC +0.214 (t 2.9); finale IC +0.256 (t 3.1), anche con l'esito dal mese dopo (+0.252,
#   controllo sulle medie mensili di decennale e oro) e senza la liquidita' (+0.251). Migliore classe per paese 12,8%/anno
#   con drawdown -10,5% contro 8,5% e -4,9% a pesi uguali, 7,5% e -12,4% del 60/40, 6,9% e -8,9% dell'All Weather;
#   batte tutti i 500 portafogli a caso. Vantaggio dimostrato: segnale.
# - Valute: finestre IC +0.262 (t 3.5), quasi tutto dal carry; finale IC +0.063 (t 0.5), migliori 2 2,5%/anno contro
#   1,3% a pesi uguali e 2,9% del solo dollaro, battono l'87% dei portafogli a caso (p 0.13). Il vantaggio delle
#   finestre non regge dopo il 2019: descrittiva.
# Varianti: pilastri e segni decisi prima, una sola versione per classifica. Sui paesi provate nelle finestre 4 varianti
# con meno pilastri (IC fra +0.006 e +0.071, tutte con t sotto 1): rumore, tenuta la versione completa.
EDGE = {"Paesi": False, "Classi di asset": True, "Valute": False}
VERIFICA = {
    "Paesi": "IC +0,08 (t 0,8) · migliori 3: 9,6% l'anno contro 10,4% a pesi uguali · meglio del 38% dei portafogli a caso",
    "Classi di asset": "IC +0,26 (t 3,1) · migliore classe: 12,8% l'anno contro 8,5% a pesi uguali e 7,5% del 60/40 · "
                       "meglio di tutti i 500 portafogli a caso",
    "Valute": "IC +0,06 (t 0,5) · migliori 2: 2,5% l'anno contro 1,3% a pesi uguali · meglio dell'87% dei portafogli a caso",
}


def ranks(raw: dict[str, pd.DataFrame], valid: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Posizione relativa del mese, da -0,5 a +0,5 (alto = meglio); dato mancante = neutro (0) dove l'elemento e'
    valido. Ogni pilastro arriva gia' orientato: il segno atteso e' deciso prima di guardare i risultati."""
    return {k: (v.reindex_like(valid).rank(axis=1, pct=True) - 0.5).fillna(0).where(valid) for k, v in raw.items()}


def forward_excess(px: pd.DataFrame, horizon: int = HORIZON) -> pd.DataFrame:
    """Rendimento dei `horizon` mesi dopo meno la media degli elementi del mese."""
    fwd = px.shift(-horizon) / px - 1
    return fwd.sub(fwd.mean(axis=1), axis=0)


def months_of(index: pd.Index) -> pd.DatetimeIndex:
    """Mese di ogni riga: l'indice e' il mese, o (area, mese) per la classifica delle classi di asset."""
    return pd.DatetimeIndex(index.get_level_values(-1))


def by_month(row_values: pd.Series) -> pd.Series:
    """Media per mese dei valori per riga (con indice (area, mese) fa la media fra le aree)."""
    return row_values.groupby(months_of(row_values.index)).mean() if row_values.index.nlevels > 1 else row_values


def segmented_prob(feats: dict[str, pd.DataFrame], excess: pd.DataFrame, cuts: list, horizon: int = HORIZON,
                   min_items: int = MIN_ITEMS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Probabilita' di battere la media nei `horizon` mesi dopo. A ogni data di cuts i pesi si stimano solo sugli
    esiti gia' noti a quella data (mese + horizon <= cut) e valgono fino alla data dopo. Ritorna (prob, pesi per cut)."""
    names = list(feats)
    valid = next(iter(feats.values())).reindex_like(excess).notna()  # ranks(): stessa maschera per ogni pilastro
    x = np.stack([feats[k].reindex_like(excess).values for k in names], axis=-1)
    y = np.where(excess.notna() & valid, (excess > 0).astype(float), np.nan)
    row_ok = valid.sum(axis=1).values >= min_items
    months = months_of(excess.index)
    prob, weights = np.full(excess.shape, np.nan), {}
    cuts = [pd.Timestamp(c) for c in cuts]
    for c, nxt in zip(cuts, cuts[1:] + [months.max() + pd.offsets.MonthBegin()]):
        known = (months + pd.DateOffset(months=horizon) <= c) & row_ok
        if len(set(months[known])) < MIN_TRAIN_MONTHS:
            continue
        xx, tt = x[known].reshape(-1, len(names)), y[known].reshape(-1)
        ok = ~np.isnan(xx).any(axis=1) & ~np.isnan(tt)
        w = _fit(np.c_[np.ones(ok.sum()), xx[ok]], tt[ok], np.zeros(len(names) + 1))
        weights[c] = w
        rows = (months >= c) & (months < nxt) & row_ok
        z = w[0] + np.nan_to_num(x[rows]) @ w[1:]
        prob[rows] = np.where(valid.values[rows], 1 / (1 + np.exp(-z)), np.nan)
    return (pd.DataFrame(prob, index=excess.index, columns=excess.columns),
            pd.DataFrame(weights, index=["Costante", *names]).T)


def to_score(prob: pd.DataFrame) -> pd.DataFrame:
    """Punteggio 1-100 = posizione relativa del mese (50 = meta' classifica)."""
    return (prob.rank(axis=1, pct=True) * 100).round().clip(lower=1)


def live_cuts(index: pd.Index) -> list[pd.Timestamp]:
    """Ristima ogni gennaio: il modello mostrato nell'app."""
    m = months_of(index).unique().sort_values()
    return list(m[m.month == 1])


def fold_prob(feats: dict[str, pd.DataFrame], excess: pd.DataFrame, horizon: int = HORIZON,
              min_items: int = MIN_ITEMS) -> pd.DataFrame:
    """Probabilita' fuori campione solo nelle finestre di verifica di FOLDS (stima ferma all'inizio della finestra)."""
    out = pd.DataFrame(np.nan, index=excess.index, columns=excess.columns)
    months = months_of(excess.index)
    for _, start, end in FOLDS:
        p, _ = segmented_prob(feats, excess, [start], horizon, min_items)
        inside = (months >= start) & (months <= end)
        out[inside] = p[inside]
    return out


def holdout_prob(feats: dict[str, pd.DataFrame], excess: pd.DataFrame, horizon: int = HORIZON,
                 min_items: int = MIN_ITEMS) -> tuple[pd.DataFrame, pd.Series]:
    """Probabilita' nel periodo finale (solo quelle righe) con i pesi stimati a fine 2018 e mai ristimati."""
    p, w = segmented_prob(feats, excess, [HOLDOUT_START], horizon, min_items)
    return p[months_of(p.index) >= HOLDOUT_START], w.iloc[0] if len(w) else pd.Series(dtype=float)


def ic(signal: pd.DataFrame, excess: pd.DataFrame, horizon: int = HORIZON) -> tuple[float, float, int]:
    """IC medio mensile (Spearman) e t-stat. Gli esiti a `horizon` mesi si sovrappongono: t su n/horizon mesi."""
    both = signal.notna() & excess.notna()
    rows = signal.where(both).rank(axis=1).corrwith(excess.where(both).rank(axis=1), axis=1).dropna()
    m = by_month(rows)
    n = len(m)
    if n < 3 or m.std() == 0:
        return float("nan"), float("nan"), n
    return m.mean(), m.mean() / m.std() * math.sqrt(n / horizon), n


def top_returns(score: pd.DataFrame, ret1: pd.DataFrame, k: int) -> pd.Series:
    """Rendimento del mese dopo dei migliori k a pesi uguali (ret1: rendimento del mese t+1 sulla riga t)."""
    top = score.rank(axis=1, ascending=False, method="first") <= k
    ret1 = ret1.reindex(index=score.index, columns=score.columns)
    return by_month(ret1.where(top).mean(axis=1).where(score.notna().sum(axis=1) >= k))


def random_portfolios(score: pd.DataFrame, ret1: pd.DataFrame, k: int, n: int = 500, seed: int = 0) -> np.ndarray:
    """Rendimento annuo di n portafogli che ogni mese prendono k elementi a caso fra quelli con un punteggio."""
    rng = np.random.default_rng(seed)
    keep = score.notna().sum(axis=1) >= k
    avail = score[keep].notna().values
    r = ret1.reindex(index=score.index, columns=score.columns)[keep].fillna(0).values
    index = score.index[keep]
    out = np.empty(n)
    for j in range(n):
        noise = np.where(avail, rng.random(avail.shape), -1)
        pick = noise >= -np.sort(-noise, axis=1)[:, [k - 1]]
        out[j] = annual(by_month(pd.Series((r * pick).sum(axis=1) / k, index=index)))
    return out


def annual(r: pd.Series) -> float:
    r = r.dropna()
    return float(((1 + r).prod() ** (12 / len(r)) - 1) * 100) if len(r) else float("nan")


def max_drawdown(r: pd.Series) -> float:
    w = (1 + r.dropna()).cumprod()
    return float((w / w.cummax() - 1).min() * 100) if len(w) else float("nan")


# ---------------------------------------------------------------------------------------------------------------------
# Dati: tutto mensile, indice = inizio mese, valore = stato a fine mese. Un dato macro entra solo quando e' pubblicato.
AREAS = ["USA", "Eurozona", "Italia", "UK", "Giappone", "Canada", "Cina", "Australia", "India"]
CCY = {"USA": "USD", "Eurozona": "EUR", "Italia": "EUR", "UK": "GBP", "Giappone": "JPY", "Canada": "CAD",
       "Cina": "CNY", "Australia": "AUD", "India": "INR"}
CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CNY", "INR"]
CCY_AREA = {"USD": "USA", "EUR": "Eurozona", "GBP": "UK", "JPY": "Giappone", "CAD": "Canada", "AUD": "Australia",
            "CNY": "Cina", "INR": "India"}
# ETF azionario del paese (area Asset di score.py); prima della sua nascita il rendimento viene da serie piu' lunghe.
COUNTRY_ETF = {"USA": "SPY", "Eurozona": "EZU", "Italia": "EWI", "UK": "EWU", "Giappone": "EWJ", "Canada": "EWC",
               "Cina": "MCHI", "Australia": "EWA", "India": "INDA"}
YAHOO = {"FXI": "FXI", "BSESN": "^BSESN"}  # Cina 2004-2011 (FXI), India 1997-2012 (Sensex in rupie, solo prezzo)
EURO_FRENCH = ["Francia", "Germania", "Italia", "Spagna", "Olanda"]  # Eurozona prima di EZU (2000), media semplice
DEM_PER_EUR, ITL_PER_EUR = 1.95583, 1936.27
FX_FRED = {"EUR": ("eurusd", 1), "GBP": ("gbpusd", 1), "JPY": ("usdjpy", -1), "CAD": ("usdcad", -1),
           "AUD": ("audusd", 1), "CNY": ("usdcny", -1), "INR": ("usdinr", -1)}
# Futures CFTC per valuta (fetch_cot.CONTRACTS): CNY e INR non ne hanno. Classi di asset: solo USA.
COT_CCY = {"USD": "Dollaro (DXY)", "EUR": "Euro", "GBP": "Sterlina", "JPY": "Yen", "CAD": "Dollaro canadese",
           "AUD": "Dollaro australiano"}
COT_ASSET_USA = {"Azioni": "S&P 500", "Obbligazioni": "Treasury 10Y", "Oro": "Oro"}
COT_WEEKS, COT_MIN_WEEKS = 260, 104  # percentile sugli ultimi 5 anni, almeno 2
SURVEY_LAG = 1  # fiducia OCSE e CPI: il dato del mese esce il mese dopo
RATIO_LAG = 6  # E/P annuali di French (dicembre): usati da giugno dell'anno dopo
REER_YEARS = 10
BOND_DURATION = 7.5  # rendimento del decennale ~ cedola/12 - duration * variazione del rendimento (come score.py)
ASSETS = ["Azioni", "Obbligazioni", "Liquidità", "Oro"]
TREND_MONTHS, MOM_MONTHS, CHANGE_MONTHS = 10, 12, 12


def _monthly(s: pd.Series, how: str = "last") -> pd.Series:
    s = s.dropna()
    return s if s.empty else getattr(s.resample("MS"), how)()


def _grid(frames: dict, lag: int, grid: pd.DatetimeIndex, fill: int = 3) -> pd.DataFrame:
    """Serie mensili su una griglia, spostate di `lag` mesi (pubblicazione), riempite per al massimo `fill` mesi."""
    out = {}
    for k, v in frames.items():
        m = _monthly(v)
        out[k] = m.reindex(grid.union(m.index)).ffill(limit=fill).reindex(grid).shift(lag)
    return pd.DataFrame(out, index=grid)


def fx_usd_per_local(read, grid: pd.DatetimeIndex) -> pd.DataFrame:
    """Dollari per unita' di valuta locale, per area (Italia in lire prima del 1999, Eurozona dal marco)."""
    out = {"USD": pd.Series(1.0, index=grid)}
    for ccy, (name, sign) in FX_FRED.items():
        s = _monthly(read("Valute", name))
        out[ccy] = s if sign > 0 else 1 / s
    euro = out["EUR"]
    by_area = {a: out[CCY[a]] for a in AREAS}
    by_area["Eurozona"] = euro.combine_first(DEM_PER_EUR / _monthly(read("Valute", "usddem")))
    by_area["Italia"] = euro.combine_first(ITL_PER_EUR / _monthly(read("Valute", "usditl")))
    return pd.DataFrame({a: s.reindex(grid) for a, s in by_area.items()}, index=grid)


def equity_usd_returns(read, asset_px: pd.DataFrame, history_mkt: pd.Series, grid: pd.DatetimeIndex) -> pd.DataFrame:
    """Rendimento totale mensile in dollari per area: ETF dove esiste, prima French (USA: mercato French, Eurozona:
    media di 5 paesi), Cina FXI, India Sensex convertito in dollari (senza dividendi)."""
    fr = {n: _monthly(read(AREA, f"{n}_usd"), "sum") for n in {*EURO_FRENCH, "UK", "Giappone", "Canada", "Australia"}}
    fallback = {"USA": history_mkt, "Eurozona": pd.DataFrame({n: fr[n] for n in EURO_FRENCH}).mean(axis=1),
                **{a: fr[a] for a in ("Italia", "UK", "Giappone", "Canada", "Australia")},
                "Cina": _monthly(read(AREA, "FXI")).pct_change(fill_method=None),
                "India": (_monthly(read(AREA, "BSESN")) / _monthly(read("Valute", "usdinr"))).pct_change(fill_method=None)}
    out = {}
    for a in AREAS:
        etf = asset_px[COUNTRY_ETF[a]].pct_change(fill_method=None) if COUNTRY_ETF[a] in asset_px else pd.Series(dtype=float)
        first, fb = etf.first_valid_index(), fallback[a]
        out[a] = etf.combine_first(fb if first is None else fb[fb.index <= first])
    return pd.DataFrame(out).reindex(grid)


def _prices(r: pd.DataFrame) -> pd.DataFrame:
    """Indice di prezzo dai rendimenti, NaN prima del primo rendimento."""
    return (1 + r.fillna(0)).cumprod().where(r.notna().cummax())


def _cot(read, name: str, grid: pd.DatetimeIndex) -> pd.Series:
    """Percentile 0-1 degli speculatori (netto in % dell'open interest) sugli ultimi 5 anni, a fine mese."""
    s = read("Mercati", f"cot_{name}").dropna()
    if s.empty:
        return pd.Series(np.nan, index=grid)
    return _monthly(s.rolling(COT_WEEKS, min_periods=COT_MIN_WEEKS).rank(pct=True)).reindex(grid)


def load(read, asset_px: pd.DataFrame, history_mkt: pd.Series, today: pd.Timestamp | None = None) -> dict:
    """Serie mensili per le tre classifiche, fino all'ultimo mese chiuso. read(area, indicatore) -> pd.Series (cache);
    asset_px: prezzi mensili degli ETF (score.monthly_prices); history_mkt: rendimenti mensili del mercato USA French."""
    today = pd.Timestamp.today() if today is None else today
    grid = pd.date_range("1975-01-01", today.normalize().replace(day=1) - pd.offsets.MonthBegin(), freq="MS")
    per_area = lambda name, lag=0: _grid({a: read(AREA, f"{a}_{name}") for a in AREAS}, lag, grid)
    policy = _grid({a: read("Valute", f"rate_{CCY[a]}") for a in AREAS}, 0, grid)
    policy["Eurozona"] = policy["Eurozona"].combine_first(_grid({"x": read("Valute", "rate_DEM")}, 0, grid)["x"])
    euro_ep = pd.DataFrame({n: read(AREA, f"{n}_ep") for n in EURO_FRENCH}).mean(axis=1)
    ep = _grid({**{a: read(AREA, f"{a}_ep") for a in ("UK", "Giappone", "Canada", "Australia", "Italia")},
                "Eurozona": euro_ep}, RATIO_LAG, grid, fill=12)
    return {
        "grid": grid,
        "fx": fx_usd_per_local(read, grid),
        "equity_usd": equity_usd_returns(read, asset_px, history_mkt, grid),
        "rate": per_area("rate_3m").combine_first(policy),  # 3 mesi OCSE, se manca il tasso a breve di currency.py
        "yield_10y": per_area("yield_10y"),
        "cci": per_area("cci", SURVEY_LAG), "bci": per_area("bci", SURVEY_LAG),
        "inflation": _grid({a: read(a, "inflation_yoy") for a in AREAS}, SURVEY_LAG, grid),
        "ep": ep.reindex(columns=AREAS),
        "gold": _grid({"gold": read(AREA, "gold")}, 0, grid)["gold"],
        "reer": _grid({c: read(AREA, f"reer_{c}") for c in CURRENCIES}, 0, grid),
        "cot": pd.DataFrame({c: _cot(read, n, grid) for c, n in COT_CCY.items()}, index=grid).reindex(columns=CURRENCIES),
        "cot_usa": {a: _cot(read, n, grid) for a, n in COT_ASSET_USA.items()},
    }


def _trend_mom(px: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    return px / px.rolling(TREND_MONTHS).mean() - 1, px.shift(1) / px.shift(MOM_MONTHS) - 1


# ---------------------------------------------------------------------------------------------------------------------
# Pilastri. Il segno di ognuno e' deciso a priori dalla letteratura (scripts/evaluate_allocation.py, spec.md); la
# regressione con pesi solo positivi toglie da sola un pilastro che nei dati lavora al contrario.
def countries(d: dict) -> dict:
    """Classifica paesi: azioni del paese, rendimento totale in dollari."""
    px = _prices(d["equity_usd"])
    trend, mom = _trend_mom(px)
    raw = {
        "Tendenza": trend,
        "Momentum": mom,
        "Fiducia": -(d["cci"] - 100),  # consumatori euforici = rendimenti dopo piu' bassi (Schmeling 2009): contrarian
        "Ciclo": d["bci"].diff(CHANGE_MONTHS),  # fiducia delle imprese in salita (macro momentum, Brooks 2017)
        "Tassi": -d["yield_10y"].diff(CHANGE_MONTHS),  # decennale in discesa = politica monetaria che aiuta
        "Valore": d["ep"],  # utili / prezzo alto = mercato a buon mercato (French, 6 aree: le altre neutre)
    }
    return _panel(raw, px, d["equity_usd"].shift(-1))


def _by_asset(**cols) -> pd.DataFrame:
    """Un pilastro della classifica per classi di asset: una colonna per asset, quelle non date valgono 0 (neutre)."""
    ref = next(iter(cols.values()))
    return pd.DataFrame({k: cols.get(k, 0 * ref) for k in ASSETS})


def asset_classes(d: dict) -> dict:
    """Classi di asset dentro ogni paese, in valuta locale. Indice (area, mese), colonne ASSETS."""
    fx, raw_all, px_all, r1_all = d["fx"], {}, {}, {}
    for a in AREAS:
        y, rate = d["yield_10y"][a], d["rate"][a]
        gold = d["gold"] / fx[a]
        r = pd.DataFrame({
            "Azioni": (1 + d["equity_usd"][a]) * fx[a].shift(1) / fx[a] - 1,
            "Obbligazioni": y.shift(1) / 1200 - BOND_DURATION * y.diff() / 100,
            "Liquidità": rate.shift(1) / 1200,
            "Oro": gold / gold.shift(1) - 1,
        })
        px = _prices(r)
        trend, mom = _trend_mom(px)
        slope, cycle, dshort, mood = y - rate, d["bci"][a].diff(CHANGE_MONTHS), rate.diff(CHANGE_MONTHS), d["cci"][a] - 100
        cot = d["cot_usa"] if a == "USA" else {k: pd.Series(np.nan, index=d["grid"]) for k in COT_ASSET_USA}
        raw_all[a] = {
            "Tendenza": trend, "Momentum": mom,
            # curva ripida: crescita attesa, favorisce obbligazioni (rendimento) e azioni, sfavorisce la liquidita'
            "Curva": _by_asset(Azioni=slope, Obbligazioni=slope, **{"Liquidità": -slope}),
            # imprese piu' fiduciose: azioni meglio, obbligazioni peggio (macro momentum, Brooks 2017)
            "Ciclo": _by_asset(Azioni=cycle, Obbligazioni=-cycle),
            # tassi a breve in discesa: aiuta azioni, obbligazioni e oro, peggiora la liquidita'
            "Tassi": _by_asset(Azioni=-dshort, Obbligazioni=-dshort, Oro=-dshort, **{"Liquidità": dshort}),
            # consumatori euforici: meno azioni, piu' obbligazioni (contrarian)
            "Fiducia": _by_asset(Azioni=-mood, Obbligazioni=mood),
            # COT (solo USA, futures S&P 500, Treasury 10Y, oro): si segue la pressione degli speculatori (Fan et al. 2020)
            "COT": pd.DataFrame({k: cot.get(k, pd.Series(np.nan, index=d["grid"])) for k in ASSETS}),
        }
        px_all[a], r1_all[a] = px, r.shift(-1)
    raw = {k: pd.concat({a: raw_all[a][k] for a in AREAS}) for k in raw_all[AREAS[0]]}
    return _panel(raw, pd.concat(px_all), pd.concat(r1_all), min_items=3)


def currencies(d: dict) -> dict:
    """Valute: rendimento in dollari di tenere liquidita' in quella valuta (cambio + tasso a breve)."""
    fx = pd.DataFrame({c: d["fx"][CCY_AREA[c]] for c in CURRENCIES})
    rate = pd.DataFrame({c: d["rate"][CCY_AREA[c]] for c in CURRENCIES})
    r = fx / fx.shift(1) * (1 + rate.shift(1) / 1200) - 1
    infl = pd.DataFrame({c: d["inflation"][CCY_AREA[c]] for c in CURRENCIES})
    reer = d["reer"]
    raw = {
        "Carry": rate,  # tasso a breve alto = rendimento in piu' (Lustig-Verdelhan 2007)
        "Tasso reale": rate - infl,
        "Momentum": fx.shift(1) / fx.shift(MOM_MONTHS) - 1,  # solo cambio, 12 mesi escluso l'ultimo
        "Valore": -(reer / reer.rolling(REER_YEARS * 12, min_periods=60).mean() - 1),  # sotto la media = a buon mercato
        "COT": d["cot"],  # si segue la pressione degli speculatori (Fan et al. 2020)
        "Ciclo": pd.DataFrame({c: d["bci"][CCY_AREA[c]].diff(CHANGE_MONTHS) for c in CURRENCIES}),  # economic momentum
    }
    px = _prices(r)
    raw["Tendenza"] = px / px.rolling(TREND_MONTHS).mean() - 1
    return _panel(raw, px, r.shift(-1))


def _panel(raw: dict, px: pd.DataFrame, ret1: pd.DataFrame, min_items: int = MIN_ITEMS) -> dict:
    """Pilastri in posizione relativa, extra-rendimento a HORIZON mesi e rendimento del mese dopo. Valido = elemento
    con prezzo, tendenza e momentum, in un mese (o area-mese) con almeno min_items elementi validi."""
    valid = px.notna() & raw["Momentum"].reindex_like(px).notna() & raw["Tendenza"].reindex_like(px).notna()
    valid = valid.where(valid.sum(axis=1) >= min_items, False)
    if px.index.nlevels > 1:
        excess = pd.concat({a: forward_excess(px.loc[a].where(valid.loc[a])) for a in px.index.get_level_values(0).unique()})
    else:
        excess = forward_excess(px.where(valid))
    return {"feats": ranks(raw, valid), "raw": raw, "excess": excess.where(valid), "ret1": ret1.where(valid),
            "px": px, "min_items": min_items}


def model(panel: dict, pillars: list[str] | None = None) -> dict:
    """Modello mostrato nell'app: pesi ristimati ogni gennaio solo sul passato. Ritorna score, prob, weights."""
    feats = {k: v for k, v in panel["feats"].items() if pillars is None or k in pillars}
    prob, w = segmented_prob(feats, panel["excess"], live_cuts(panel["excess"].index), min_items=panel["min_items"])
    return {"score": to_score(prob), "prob": prob, "weights": w}
