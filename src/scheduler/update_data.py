import datetime
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.classify.cycle import classify_cycle
from src.classify.regime import classify_regime
from src.data import cache, fetch_boe, fetch_ecb, fetch_fred, fetch_japan

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    return {
        "USA": {
            "growth_yoy": lambda: fetch_fred.fetch_growth_yoy(fred_key),
            "inflation_yoy": lambda: fetch_fred.fetch_inflation_yoy(fred_key),
            "unemployment_rate": lambda: fetch_fred.fetch_unemployment_rate(fred_key),
        },
        "Eurozona": {
            "growth_yoy": lambda: fetch_ecb.fetch_growth_yoy("EA20"),
            "inflation_yoy": lambda: fetch_ecb.fetch_inflation_yoy("EA"),
            "unemployment_rate": lambda: fetch_ecb.fetch_unemployment_rate("EA21"),
        },
        "Italia": {
            "growth_yoy": lambda: fetch_ecb.fetch_growth_yoy("IT"),
            "inflation_yoy": lambda: fetch_ecb.fetch_inflation_yoy("IT"),
            "unemployment_rate": lambda: fetch_ecb.fetch_unemployment_rate("IT"),
        },
        "UK": {
            "growth_yoy": fetch_boe.fetch_growth_yoy,
            "inflation_yoy": fetch_boe.fetch_inflation_yoy,
            "unemployment_rate": fetch_boe.fetch_unemployment_rate,
        },
        "Giappone": {
            "growth_yoy": lambda: fetch_japan.fetch_growth_yoy(estat_app_id),
            "inflation_yoy": lambda: fetch_japan.fetch_inflation_yoy(estat_app_id),
            "unemployment_rate": lambda: fetch_japan.fetch_unemployment_rate(estat_app_id),
        },
    }


def update_area(area: str, indicator_fetchers: dict) -> None:
    series_by_indicator = {}
    for indicator, fetch_fn in indicator_fetchers.items():
        try:
            series = fetch_fn()
            cache.write_indicator_series(area, indicator, series)
            series_by_indicator[indicator] = series
        except Exception:
            logger.exception("%s: fetch fallito per indicatore %s, salto e continuo", area, indicator)

    if "growth_yoy" not in series_by_indicator or "inflation_yoy" not in series_by_indicator:
        logger.warning("%s: crescita o inflazione mancanti, salto classificazione", area)
        return

    growth = series_by_indicator["growth_yoy"]
    regime = classify_regime(growth, series_by_indicator["inflation_yoy"])
    phase = classify_cycle(growth)
    computed_at = datetime.datetime.now().isoformat(timespec="seconds")
    cache.write_classification(area, computed_at, regime, phase)
    logger.info("%s: regime=%s phase=%s", area, regime, phase)


def main() -> None:
    _load_dotenv()
    fred_key = os.environ.get("FRED_API_KEY", "")
    estat_app_id = os.environ.get("ESTAT_APP_ID", "")
    for area, indicator_fetchers in _areas(fred_key, estat_app_id).items():
        try:
            update_area(area, indicator_fetchers)
        except Exception:
            logger.exception("update fallito per area %s, salto e continuo", area)


if __name__ == "__main__":
    main()
