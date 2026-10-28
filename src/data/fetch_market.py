import time
from urllib.parse import quote

import pandas as pd
import requests

from src.data.http import get_with_retry

# Yahoo Finance chart endpoint: non ufficiale, senza chiave. MOVE non e' su FRED.
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
FIRST_TIMESTAMP = -1_500_000_000  # 1922: prima di qualsiasi serie Yahoo (i mensili partono comunque dal 1985)


def fetch_yahoo(symbol: str, range_: str = "5y", interval: str = "1d", adjusted: bool = False) -> pd.Series:
    """Chiusure di un simbolo Yahoo. Con interval='1mo' la data e' il primo del mese, la chiusura l'ultima del mese.
    adjusted=True: chiusure rettificate per dividendi e split (rendimento totale degli ETF)."""
    # range=max con interval=1mo restituisce un punto ogni 3 mesi: per tutto lo storico serve period1/period2
    span = {"period1": FIRST_TIMESTAMP, "period2": int(time.time())} if range_ == "max" else {"range": range_}
    resp = get_with_retry(
        YAHOO_URL.format(symbol=quote(symbol)),
        source="yahoo",
        params={**span, "interval": interval},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    result = resp.json()["chart"]["result"][0]
    closes = result["indicators"]["adjclose"][0]["adjclose"] if adjusted else result["indicators"]["quote"][0]["close"]
    pairs = [(pd.Timestamp(ts, unit="s").normalize(), c) for ts, c in zip(result["timestamp"], closes) if c is not None]
    return pd.Series([c for _, c in pairs], index=[d for d, _ in pairs]).sort_index()


def fetch_move() -> pd.Series:
    """ICE BofA MOVE Index (volatilita' implicita sui Treasury), chiusura giornaliera."""
    return fetch_yahoo("^MOVE")


# Oro, prezzo medio mensile in dollari dal 1833 (dataset pubblico datahub "gold-prices", licenza ODC-PDDL, fonte World
# Bank/Bundesbank): allunga lo storico prima di GLD (2004) per la classifica delle classi di asset.
GOLD_URL = "https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv"


def fetch_gold_monthly() -> pd.Series:
    resp = get_with_retry(GOLD_URL, source="datahub", timeout=60)
    rows = [line.split(",") for line in resp.text.splitlines()[1:] if line.count(",") == 1]
    return pd.Series([float(v) for _, v in rows], index=pd.to_datetime([d for d, _ in rows], format="%Y-%m")).sort_index()


def fetch_skew() -> pd.Series:
    """CBOE SKEW (prezzo delle opzioni put molto fuori dal denaro sull'S&P 500), chiusura giornaliera dal 1990."""
    return fetch_yahoo("^SKEW", "max")


# Put/call ratio delle opzioni su azioni singole CBOE: il CSV storico si ferma al 04/10/2019, poi un JSON per seduta
# (403 nei giorni senza dati: festivi, weekend, seduta non ancora pubblicata).
PUT_CALL_HISTORY_URL = "https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/equitypc.csv"
PUT_CALL_DAILY_URL = "https://cdn.cboe.com/data/us/options/market_statistics/daily/{date}_daily_options"
PUT_CALL_MAX_DAYS = 300  # sedute scaricate per run: il primo riempimento dal 2019 si completa in ~6 run serali
PUT_CALL_RECHECK_DAYS = 14  # si rileggono le sedute senza dato delle ultime 2 settimane: un 403 passeggero non lascia buchi


def fetch_put_call(cached: pd.Series) -> pd.Series:
    """Serie completa del put/call azionario: lo storico in cache (o il CSV, se la cache non c'e') piu' le sedute che
    mancano, al massimo PUT_CALL_MAX_DAYS per volta."""
    s = cached
    if s.empty:
        rows = [line.split(",") for line in get_with_retry(PUT_CALL_HISTORY_URL, source="cboe", timeout=60).text.splitlines()]
        rows = [r for r in rows if len(r) == 5 and r[0][:1].isdigit()]
        s = pd.Series([float(r[4]) for r in rows], index=pd.to_datetime([r[0] for r in rows], format="%m/%d/%Y"))
    new = {}
    days = pd.bdate_range(s.index[-1] - pd.Timedelta(days=PUT_CALL_RECHECK_DAYS), pd.Timestamp.today().normalize())
    for day in days.difference(s.index)[:PUT_CALL_MAX_DAYS]:
        try:
            resp = get_with_retry(PUT_CALL_DAILY_URL.format(date=f"{day:%Y-%m-%d}"), source="cboe", timeout=30)
            value = next((r["value"] for r in resp.json()["ratios"] if r["name"] == "EQUITY PUT/CALL RATIO"), None)
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 403:
                continue  # seduta senza dati (festivo o non ancora pubblicata)
            break  # altro errore: si tengono i giorni gia' letti, il resto al prossimo run
        except Exception:
            break
        if value is not None:  # giorno senza rapporto azionario: saltato, non butta via gli altri
            new[day] = float(value)
    return pd.concat([s, pd.Series(new, dtype=float)]).sort_index() if new else s


# Curve dei futures: Yahoo ha solo i contratti non ancora scaduti, quindi niente storico della forma della curva.
# Si salva la fotografia di oggi e, a ogni run, un numero riassuntivo che accumula lo storico da qui in avanti.
MONTH_CODES = "FGHJKMNQUVXZ"
FUTURES = {"petrolio": ("CL", "NYM"), "oro": ("GC", "CMX"), "rame": ("HG", "CMX"), "fed_funds": ("ZQ", "CBT")}
CURVE_MONTHS = 14  # dal mese corrente: copre il contratto a ~12 mesi anche quando il primo e' gia' scaduto
STALE_DAYS = 7  # un contratto senza prezzo da piu' di una settimana non e' quotato (es. mese gia' scaduto)


def fetch_futures_curve(root: str, exchange: str, today: pd.Timestamp | None = None, months: int = CURVE_MONTHS) -> pd.Series:
    """Ultimo prezzo dei contratti dei prossimi `months` mesi; indice = primo giorno del mese di scadenza.
    I mesi che il future non quota (l'oro tratta solo alcuni mesi) si saltano."""
    today = (today or pd.Timestamp.today()).normalize()
    start = today.replace(day=1)
    out = {}
    for i in range(months):
        m = start + pd.DateOffset(months=i)
        try:
            s = fetch_yahoo(f"{root}{MONTH_CODES[m.month - 1]}{m:%y}.{exchange}", "1mo")
        except (requests.exceptions.HTTPError, KeyError, TypeError, IndexError):
            continue  # contratto che Yahoo non ha, o quotato ma senza scambi (risposta senza prezzi)
        if not s.empty and (today - s.index[-1]).days <= STALE_DAYS:
            out[m] = s.iloc[-1]
    return pd.Series(out, dtype=float)


def curve_slope(curve: pd.Series) -> float | None:
    """Pendenza a 12 mesi in %: contratto piu' vicino a 12 mesi dal primo, contro il primo. Sotto zero = backwardation
    (il mercato paga di piu' la merce subito: offerta scarsa), sopra = contango."""
    if len(curve) < 2:
        return None
    target = curve.index[0] + pd.DateOffset(months=12)
    far = curve.index[abs(curve.index - target).argmin()]
    months = (far.year - curve.index[0].year) * 12 + far.month - curve.index[0].month
    if months < 6:
        return None
    return (curve[far] / curve.iloc[0] - 1) * 100 * 12 / months


def fed_path(curve: pd.Series) -> float | None:
    """Variazione dei tassi Fed attesa in ~12 mesi, punti %: tasso implicito (100 - prezzo) del contratto a ~12 mesi
    meno quello del primo. Sotto zero = il mercato prezza tagli."""
    if len(curve) < 2:
        return None
    target = curve.index[0] + pd.DateOffset(months=12)
    far = curve.index[abs(curve.index - target).argmin()]
    return (100 - curve[far]) - (100 - curve.iloc[0])
