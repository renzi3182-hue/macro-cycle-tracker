import datetime
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.classify import score
from src.classify.assess import assess
from src.data import cache, fetch_boe, fetch_boj, fetch_calendar, fetch_cot, fetch_ecb, fetch_fred, fetch_fx, fetch_japan, fetch_market, fetch_oecd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MARKET_AREA = "Mercati"
CALENDAR_AREA = "Calendario"
FX_AREA = "Valute"
ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


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


def update_area(area: str, indicator_fetchers: dict) -> None:
    for indicator, fetch_fn in indicator_fetchers.items():
        try:
            cache.write_indicator_series(area, indicator, fetch_fn())
        except Exception:
            logger.exception("%s: fetch fallito per indicatore %s, tengo la serie in cache e continuo", area, indicator)

    # Si classifica sulla cache, non sui soli fetch riusciti: un'API giu' per un giorno non cambia il regime.
    result = assess(area, {n: cache.read_indicator_series(area, n) for n in indicator_fetchers})
    if result is None:
        logger.warning("%s: crescita o inflazione mancanti anche in cache, salto classificazione", area)
        return
    regime, phase = result["regime"], result["phase"] or "n/d"
    last = cache.read_last_two_classifications(area)
    # Una riga solo quando regime o fase cambiano: con aggiornamenti ogni 30 minuti "cambiato dall'ultima volta" sparirebbe subito.
    if not last or (last[0]["regime"], last[0]["phase"]) != (regime, phase):
        cache.write_classification(area, datetime.datetime.now().isoformat(timespec="seconds"), regime, phase)
    if result["stale"]:
        logger.warning("%s: dati in ritardo anomalo: %s", area, ", ".join(result["stale"]))
    logger.info("%s: regime=%s phase=%s solidita=%s (dati a %s)", area, regime, phase, result["confidence"], f"{result['month']:%Y-%m}")


def update_market_context(fred_key: str) -> None:
    """COT, VIX e aspettative di mercato (recessione, inflazione attesa): solo informativi, non entrano nella classificazione. Un fallimento non blocca gli altri."""
    fetchers = {
        "vix": lambda: fetch_fred.fetch_vix(fred_key),
        "move": fetch_market.fetch_move,
        "breakeven_5y": lambda: fetch_fred.fetch_breakeven_5y(fred_key),
        "breakeven_5y5y": lambda: fetch_fred.fetch_breakeven_5y5y(fred_key),
    }
    for name, code in fetch_cot.CONTRACTS.items():
        fetchers[f"cot_{name}"] = lambda code=code: fetch_cot.fetch_net_speculative(code)
    for indicator, fetch_fn in fetchers.items():
        try:
            cache.write_indicator_series(MARKET_AREA, indicator, fetch_fn())
        except Exception:
            logger.exception("%s: fetch fallito, salto e continuo", indicator)

    for name in fetch_cot.CONTRACTS:
        try:
            for group, series in fetch_cot.fetch_net_by_group(name).items():
                cache.write_indicator_series(MARKET_AREA, f"cotg_{name}_{group}", series)
        except Exception:
            logger.exception("cot gruppi %s: fetch fallito, salto e continuo", name)

    fx_fetchers = {name: lambda name=name: fetch_fx.fetch_fx(name, fred_key) for name in fetch_fx.FX_SERIES}
    fx_fetchers.update({f"rate_{c}": lambda c=c: fetch_fx.fetch_short_rate(c, fred_key) for c in fetch_fx.RATE_SERIES})
    for indicator, fetch_fn in fx_fetchers.items():
        try:
            cache.write_indicator_series(FX_AREA, indicator, fetch_fn())
        except Exception:
            logger.exception("valute %s: fetch fallito, salto e continuo", indicator)

    # Calendario eventi: le date future stanno come indicatori (valore 1.0) sotto CALENDAR_AREA.
    events = {"FOMC": fetch_calendar.fetch_fomc_dates}
    try:
        cache.write_events(fetch_calendar.fetch_economic_events())
    except Exception:
        logger.exception("calendario economico: fetch fallito, salto e continuo")
    for name, release_id in fetch_calendar.FRED_RELEASES.items():
        events[name] = lambda release_id=release_id: fetch_calendar.fetch_release_dates(release_id, fred_key)
    for name, fetch_fn in events.items():
        try:
            cache.write_indicator_series(CALENDAR_AREA, name, fetch_fn())
        except Exception:
            logger.exception("calendario %s: fetch fallito, salto e continuo", name)


def update_asset_prices() -> None:
    """Chiusure mensili rettificate degli ETF del punteggio asset (src/classify/score.py). Un ticker che fallisce non blocca gli altri."""
    for ticker in score.UNIVERSE:
        try:
            cache.write_indicator_series(score.ASSET_AREA, ticker, fetch_market.fetch_yahoo(ticker, "max", "1mo", adjusted=True))
        except Exception:
            logger.exception("asset %s: fetch fallito, salto e continuo", ticker)


def main() -> None:
    _load_dotenv()
    fred_key = os.environ.get("FRED_API_KEY", "")
    estat_app_id = os.environ.get("ESTAT_APP_ID", "")
    for area, indicator_fetchers in _areas(fred_key, estat_app_id).items():
        try:
            update_area(area, indicator_fetchers)
        except Exception:
            logger.exception("update fallito per area %s, salto e continuo", area)
    update_market_context(fred_key)
    update_asset_prices()
    cache.write_meta("updated_at", datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))
    if fetch_fred.calls["tried"] and not fetch_fred.calls["ok"]:
        # Exit code 1: il workflow fallisce e GitHub manda la mail. La cache con le altre fonti e' gia' scritta.
        logger.error("tutte le %d chiamate FRED sono fallite (API key o servizio giu')", fetch_fred.calls["tried"])
        sys.exit(1)


if __name__ == "__main__":
    main()
