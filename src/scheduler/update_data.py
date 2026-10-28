import datetime
import json
import logging
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.classify import allocation, cycle, intermarket, monitor, risk, score, stress
from src.classify.assess import UNCERTAIN_PREFIX, assess
from src.data import cache, fetch_bis, fetch_boe, fetch_boj, fetch_calendar, fetch_cot, fetch_ecb, fetch_french, fetch_fred, fetch_fx, fetch_japan, fetch_market, fetch_oecd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MARKET_AREA = "Mercati"
CALENDAR_AREA = "Calendario"
FX_AREA = "Valute"
FUTURES_AREA = "Futures"  # curva di oggi per contratto: indice = mese di scadenza
SLOW_AREAS = {MARKET_AREA, FX_AREA, FUTURES_AREA, score.ASSET_AREA, score.HISTORY_AREA, intermarket.AREA, allocation.AREA}  # aggiornate solo nel run completo
ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"

# Fetch falliti in questo run: mostrati sul sito (export_site.warnings_html), senza query string (puo' contenere api_key:
# data/cache.db e' pubblicata come release pubblica).
FETCH_FAILURES: list[dict] = []


def _record_failure(area: str, indicator: str, exc: Exception) -> None:
    FETCH_FAILURES.append({
        "area": area, "indicator": indicator,
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "message": str(exc).split("?", 1)[0][:200],
    })


def _load_dotenv(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _areas(fred_key: str, estat_app_id: str) -> dict:
    def curve(area):
        return lambda: fetch_fred.fetch_spread(*fetch_fred.CURVES[area], fred_key)

    areas = {
        "USA": {
            "growth_yoy": lambda: fetch_fred.fetch_growth_yoy(fred_key),
            "inflation_yoy": lambda: fetch_fred.fetch_inflation_yoy(fred_key),
            "core_inflation_yoy": lambda: fetch_fred.fetch_core_inflation_yoy(fred_key),
            "unemployment_rate": lambda: fetch_fred.fetch_unemployment_rate(fred_key),
            "industrial_production": lambda: fetch_fred.fetch_industrial_production_yoy(fred_key),
            "fed_funds": lambda: fetch_fred.fetch_fed_funds(fred_key),
            "recession_prob": lambda: fetch_fred.fetch_recession_probability(fred_key),
            "yield_curve": lambda: fetch_fred.fetch_yield_curve(fred_key),
            "credit_spread": lambda: fetch_fred.fetch_credit_spread(fred_key),
            "fin_conditions": lambda: fetch_fred.fetch_financial_conditions(fred_key),
            # solo informativi (non nel punteggio di rischio, tarato su NBER con i 3 segnali sopra)
            "claims": lambda: fetch_fred.fetch_claims(fred_key),
            "permits": lambda: fetch_fred.fetch_permits(fred_key),
            "philly_fed": lambda: fetch_fred.fetch_philly_fed(fred_key),
            "gdpnow": lambda: fetch_fred.fetch_gdpnow(fred_key),
        },
        "Eurozona": {
            "growth_yoy": lambda: fetch_ecb.fetch_growth_yoy("EA21"),
            "inflation_yoy": lambda: fetch_ecb.fetch_inflation_yoy("EA"),
            "core_inflation_yoy": lambda: fetch_ecb.fetch_core_inflation_yoy("EA"),
            "unemployment_rate": lambda: fetch_ecb.fetch_unemployment_rate("EA21"),
            "esi": lambda: fetch_ecb.fetch_sentiment("EA21"),
            "yield_curve": curve("Eurozona"),
        },
        "Italia": {
            "growth_yoy": lambda: fetch_ecb.fetch_growth_yoy("IT"),
            "inflation_yoy": lambda: fetch_ecb.fetch_inflation_yoy("IT"),
            "core_inflation_yoy": lambda: fetch_ecb.fetch_core_inflation_yoy("IT"),
            "unemployment_rate": lambda: fetch_ecb.fetch_unemployment_rate("IT"),
            "esi": lambda: fetch_ecb.fetch_sentiment("IT"),
            "btp_bund": lambda: fetch_fred.fetch_spread(*fetch_fred.BTP_BUND, fred_key),
        },
        "UK": {
            "growth_yoy": fetch_boe.fetch_growth_yoy,
            "inflation_yoy": fetch_boe.fetch_inflation_yoy,
            "core_inflation_yoy": fetch_boe.fetch_core_inflation_yoy,
            "unemployment_rate": fetch_boe.fetch_unemployment_rate,
            "yield_curve": curve("UK"),
        },
        "Giappone": {
            "growth_yoy": lambda: fetch_japan.fetch_growth_yoy(estat_app_id),
            "inflation_yoy": lambda: fetch_japan.fetch_inflation_yoy(estat_app_id),
            "unemployment_rate": lambda: fetch_japan.fetch_unemployment_rate(estat_app_id),
            "tankan": fetch_boj.fetch_tankan,
            "yield_curve": curve("Giappone"),
        },
    }
    for area in fetch_oecd.OECD_ONLY:
        areas[area] = {
            "growth_yoy": lambda area=area: fetch_oecd.fetch_growth_yoy(area),
            "inflation_yoy": lambda area=area: fetch_oecd.fetch_inflation_yoy(area),
        }
        if area in fetch_oecd.CORE_AREAS:
            areas[area]["core_inflation_yoy"] = lambda area=area: fetch_oecd.fetch_inflation_yoy(area, core=True)
        if area in fetch_fred.UNEMPLOYMENT_INTL:
            areas[area]["unemployment_rate"] = lambda area=area: fetch_fred.fetch_unemployment_rate(fred_key, fetch_fred.UNEMPLOYMENT_INTL[area])
    for area in fetch_oecd.IP_AREAS:
        areas[area]["industrial_production"] = lambda area=area: fetch_oecd.fetch_industrial_production_yoy(area)
    for area, fetchers in areas.items():
        fetchers["cli"] = lambda area=area: fetch_oecd.fetch_cli(area)
    return areas


def history_regime_key(result: dict) -> str:
    """Valore di 'regime' da scrivere nello storico classifications: 'Incerto' conta come un valore unico,
    cosi' entrare/uscire dall'incertezza e' un cambio ma scambiare la coppia di regimi restando incerti no."""
    return "Incerto" if result["regime_label"].startswith(UNCERTAIN_PREFIX) else result["regime"]


def update_area(area: str, indicator_fetchers: dict) -> None:
    for indicator, fetch_fn in indicator_fetchers.items():
        try:
            cache.write_indicator_series(area, indicator, fetch_fn())
        except Exception as e:
            logger.exception("%s: fetch fallito per indicatore %s, tengo la serie in cache e continuo", area, indicator)
            _record_failure(area, indicator, e)

    # Si classifica sulla cache, non sui soli fetch riusciti: un'API giu' per un giorno non cambia il regime.
    result = assess(area, {n: cache.read_indicator_series(area, n) for n in indicator_fetchers})
    if result is None:
        logger.warning("%s: crescita o inflazione mancanti anche in cache, salto classificazione", area)
        return
    regime, phase = result["regime"], result["phase"] or "n/d"
    history_regime = history_regime_key(result)
    last = cache.read_last_two_classifications(area)
    # Una riga solo quando regime o fase cambiano: con aggiornamenti ogni 30 minuti "cambiato dall'ultima volta" sparirebbe subito.
    if not last or (last[0]["regime"], last[0]["phase"]) != (history_regime, phase):
        cache.write_classification(area, datetime.datetime.now().isoformat(timespec="seconds"), history_regime, phase)
    if result["stale"]:
        logger.warning("%s: dati in ritardo anomalo: %s", area, ", ".join(result["stale"]))
    logger.info("%s: regime=%s phase=%s solidita=%s (dati a %s)", area, regime, phase, result["confidence"], f"{result['month']:%Y-%m}")


def update_market_context(fred_key: str) -> None:
    """COT, VIX e aspettative di mercato (recessione, inflazione attesa): solo informativi, non entrano nella classificazione. Un fallimento non blocca gli altri."""
    fetchers = {
        "vix": lambda: fetch_fred.fetch_vix(fred_key),
        "vix3m": lambda: fetch_fred.fetch_vix3m(fred_key),
        "move": fetch_market.fetch_move,
        # Risk On/Off (src/classify/risk.py): tutto lo storico giornaliero, il percentile parte dal 1999 come nella verifica
        **{t.lower(): lambda t=t: fetch_market.fetch_yahoo(t, "max", "1d", adjusted=True) for t in ("XLY", "XLP")},
        "breakeven_5y": lambda: fetch_fred.fetch_breakeven_5y(fred_key),
        "breakeven_5y5y": lambda: fetch_fred.fetch_breakeven_5y5y(fred_key),
        "skew": fetch_market.fetch_skew,
        "put_call": lambda: fetch_market.fetch_put_call(cache.read_indicator_series(MARKET_AREA, "put_call")),
        # Liquidita' e politica monetaria (src/classify/liquidity.py)
        "net_liquidity": lambda: fetch_fred.fetch_net_liquidity(fred_key),
        "m2_yoy": lambda: fetch_fred.fetch_m2_yoy(fred_key),
        "fed_target": lambda: fetch_fred.fetch_level(fetch_fred.SERIES_FED_TARGET_UPPER, fred_key),
        "dot_plot": lambda: fetch_fred.fetch_level(fetch_fred.SERIES_DOT_PLOT, fred_key),
    }
    for indicator, fetch_fn in fetchers.items():
        try:
            cache.write_indicator_series(MARKET_AREA, indicator, fetch_fn())
        except Exception as e:
            logger.exception("%s: fetch fallito, salto e continuo", indicator)
            _record_failure(MARKET_AREA, indicator, e)

    for name, code in fetch_cot.CONTRACTS.items():  # speculatori in cot_, commercial in cotc_
        try:
            for prefix, series in zip(("cot", "cotc"), fetch_cot.fetch_net_legacy(code)):
                cache.write_indicator_series(MARKET_AREA, f"{prefix}_{name}", series)
        except Exception as e:
            logger.exception("cot %s: fetch fallito, salto e continuo", name)
            _record_failure(MARKET_AREA, f"cot_{name}", e)

    for name in fetch_cot.CONTRACTS:
        try:
            for group, series in fetch_cot.fetch_net_by_group(name).items():
                cache.write_indicator_series(MARKET_AREA, f"cotg_{name}_{group}", series)
        except Exception as e:
            logger.exception("cot gruppi %s: fetch fallito, salto e continuo", name)
            _record_failure(MARKET_AREA, f"cotg_{name}", e)

    update_futures()

    fx_fetchers = {name: lambda name=name: fetch_fx.fetch_fx(name, fred_key) for name in fetch_fx.FX_SERIES}
    fx_fetchers.update({f"rate_{c}": lambda c=c: fetch_fx.fetch_short_rate(c, fred_key) for c in fetch_fx.RATE_SERIES})
    for indicator, fetch_fn in fx_fetchers.items():
        try:
            cache.write_indicator_series(FX_AREA, indicator, fetch_fn())
        except Exception as e:
            logger.exception("valute %s: fetch fallito, salto e continuo", indicator)
            _record_failure(FX_AREA, indicator, e)


def update_futures() -> None:
    """Curve dei futures (src/data/fetch_market.FUTURES): la fotografia di oggi sotto FUTURES_AREA, sostituita a ogni run,
    e il numero riassuntivo di oggi (pendenza o percorso dei tassi Fed) aggiunto al suo storico in MARKET_AREA."""
    today = pd.Timestamp.today().normalize()
    for name, (root, exchange) in fetch_market.FUTURES.items():
        try:
            # Fed Funds fino a dicembre dell'anno prossimo: e' l'ultima data del dot plot che conta (src/classify/liquidity.py)
            months = max(fetch_market.CURVE_MONTHS, 25 - today.month) if name == "fed_funds" else fetch_market.CURVE_MONTHS
            curve = fetch_market.fetch_futures_curve(root, exchange, today, months)
            cache.write_indicator_series(FUTURES_AREA, name, curve)
            value = (fetch_market.fed_path if name == "fed_funds" else fetch_market.curve_slope)(curve)
            if value is None:
                raise ValueError(f"{name}: curva con {len(curve)} contratti, numero non calcolabile")
            indicator = f"futures_{name}"
            history = cache.read_indicator_series(MARKET_AREA, indicator)
            cache.write_indicator_series(MARKET_AREA, indicator, pd.concat([history[history.index != today], pd.Series({today: value})]))
        except Exception as e:
            logger.exception("futures %s: fetch fallito, salto e continuo", name)
            _record_failure(FUTURES_AREA, name, e)


def update_monitor(fred_key: str) -> None:
    """Serie USA del cruscotto (src/classify/monitor.py), nel loro livello. Una serie che fallisce non blocca le altre."""
    for key, series_id in monitor.FRED_SERIES.items():
        try:
            cache.write_indicator_series(monitor.AREA, key, fetch_fred.fetch_level(series_id, fred_key))
        except Exception as e:
            logger.exception("cruscotto %s: fetch fallito, salto e continuo", key)
            _record_failure(monitor.AREA, key, e)


def update_calendar(fred_key: str) -> None:
    """Calendario della settimana (Forex Factory, con i dati usciti) e date future di FOMC e rilasci FRED."""
    # Calendario eventi: le date future stanno come indicatori (valore 1.0) sotto CALENDAR_AREA.
    events = {"FOMC": fetch_calendar.fetch_fomc_dates}
    try:
        cache.write_events(fetch_calendar.fetch_economic_events())
    except Exception as e:
        logger.exception("calendario economico: fetch fallito, salto e continuo")
        _record_failure(CALENDAR_AREA, "economico", e)
    for name, release_id in fetch_calendar.FRED_RELEASES.items():
        events[name] = lambda release_id=release_id: fetch_calendar.fetch_release_dates(release_id, fred_key)
    for name, fetch_fn in events.items():
        try:
            cache.write_indicator_series(CALENDAR_AREA, name, fetch_fn())
        except Exception as e:
            logger.exception("calendario %s: fetch fallito, salto e continuo", name)
            _record_failure(CALENDAR_AREA, name, e)


def update_asset_prices() -> None:
    """Chiusure mensili rettificate degli ETF del punteggio asset (src/classify/score.py) e di quelli che servono solo a
    filtro di tendenza e stress test (stress.EXTRA_ETF) o al canarino del libro (risk.BOOK_CANARIES). Un ticker che
    fallisce non blocca gli altri."""
    for ticker in dict.fromkeys([*score.UNIVERSE, *stress.EXTRA_ETF, *risk.BOOK_CANARIES]):
        try:
            cache.write_indicator_series(score.ASSET_AREA, ticker, fetch_market.fetch_yahoo(ticker, "max", "1mo", adjusted=True))
        except Exception as e:
            logger.exception("asset %s: fetch fallito, salto e continuo", ticker)
            _record_failure(score.ASSET_AREA, ticker, e)


def update_history(fred_key: str) -> None:
    """Serie lunghe per allungare lo storico del punteggio asset (score.PROXY, score.BOND_PROXY): rendimenti mensili
    French dal 1926 e rendimenti dei Treasury FRED. Una fonte che fallisce non blocca l'altra."""
    fetchers = {"french": fetch_french.fetch_french,
                **{s: lambda s=s: {s: fetch_fred.fetch_level(s, fred_key)} for s in score.HISTORY_SERIES if s.startswith("GS")}}
    for name, fetch_fn in fetchers.items():
        try:
            for indicator, series in fetch_fn().items():
                if indicator in score.HISTORY_SERIES:
                    cache.write_indicator_series(score.HISTORY_AREA, indicator, series)
        except Exception as e:
            logger.exception("storico %s: fetch fallito, salto e continuo", name)
            _record_failure(score.HISTORY_AREA, name, e)


def update_intermarket(fred_key: str) -> None:
    """Chiusure giornaliere degli ultimi anni per la pagina Intermarket (src/classify/intermarket.py): FRED dove
    esiste, Yahoo (rettificati) per ETF e rame. Una serie che fallisce non blocca le altre."""
    fetchers = {t: lambda t=t: fetch_market.fetch_yahoo(t, f"{intermarket.YEARS}y", "1d", adjusted=True) for t in intermarket.YAHOO}
    fetchers.update({s: lambda s=s: fetch_fred.fetch_daily(s, fred_key, intermarket.YEARS) for s in intermarket.FRED_SERIES})
    for name, fetch_fn in fetchers.items():
        try:
            cache.write_indicator_series(intermarket.AREA, name, fetch_fn())
        except Exception as e:
            logger.exception("intermarket %s: fetch fallito, salto e continuo", name)
            _record_failure(intermarket.AREA, name, e)


def update_allocation() -> None:
    """Serie per le classifiche di lungo periodo (src/classify/allocation.py): fiducia e tassi OCSE per area,
    mercati per paese French, cambio reale BIS, oro mensile, Cina e India prima degli ETF (Yahoo). Una fonte che fallisce non blocca le altre."""
    fetchers = {
        **{f"{a}_{n}": lambda a=a, n=n: {f"{a}_{n}": fetch_oecd.fetch_sentiment(a, n)}
           for a in fetch_oecd.MARKET_AREAS for n in fetch_oecd.SENTIMENT},
        **{f"{a}_{n}": lambda a=a, n=n: {f"{a}_{n}": fetch_oecd.fetch_finmark(a, n)}
           for a in fetch_oecd.MARKET_AREAS for n in fetch_oecd.FINMARK},
        "french": fetch_french.fetch_countries,
        "reer": lambda: {f"reer_{c}": s for c, s in fetch_bis.fetch_reer().items()},
        "gold": lambda: {"gold": fetch_market.fetch_gold_monthly()},
        **{t: lambda t=t, y=y: {t: fetch_market.fetch_yahoo(y, "max", "1mo", adjusted=True)} for t, y in allocation.YAHOO.items()},
    }
    for name, fetch_fn in fetchers.items():
        try:
            for indicator, series in fetch_fn().items():
                if not series.empty:
                    cache.write_indicator_series(allocation.AREA, indicator, series)
        except Exception as e:
            logger.exception("allocazione %s: fetch fallito, salto e continuo", name)
            _record_failure(allocation.AREA, name, e)


def main(argv: list[str] | None = None) -> None:
    """--macro-only: solo dati macro e calendario (escono durante il giorno); mercati, COT, valute e ETF hanno
    chiusure giornaliere o settimanali e si aggiornano nel run completo della sera."""
    macro_only = "--macro-only" in (sys.argv[1:] if argv is None else argv)
    _load_dotenv()
    cache.migrate_phase_names("Ripresa", cycle.RECOVERY_BELOW_TREND)
    FETCH_FAILURES.clear()
    fred_key = os.environ.get("FRED_API_KEY", "")
    estat_app_id = os.environ.get("ESTAT_APP_ID", "")
    for area, indicator_fetchers in _areas(fred_key, estat_app_id).items():
        try:
            update_area(area, indicator_fetchers)
        except Exception:
            logger.exception("update fallito per area %s, salto e continuo", area)
    update_calendar(fred_key)
    update_monitor(fred_key)
    if macro_only:
        # i fallimenti dell'ultimo run completo restano visibili finche' quelle fonti non si riprovano
        FETCH_FAILURES.extend(f for f in json.loads(cache.read_meta("fetch_failures") or "[]") if f["area"] in SLOW_AREAS)
    else:
        update_market_context(fred_key)
        update_asset_prices()
        update_history(fred_key)
        update_intermarket(fred_key)
        update_allocation()
    cache.write_meta("updated_at", datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))
    cache.write_meta("fetch_failures", json.dumps(FETCH_FAILURES))
    if fetch_fred.calls["tried"] and not fetch_fred.calls["ok"]:
        # Exit code 1: il workflow fallisce e GitHub manda la mail. La cache con le altre fonti e' gia' scritta.
        logger.error("tutte le %d chiamate FRED sono fallite (API key o servizio giu')", fetch_fred.calls["tried"])
        sys.exit(1)


if __name__ == "__main__":
    main()
