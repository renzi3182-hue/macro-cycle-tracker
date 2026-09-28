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
        "USA": lambda: (fetch_fred.fetch_growth_yoy(fred_key), fetch_fred.fetch_inflation_yoy(fred_key)),
        "Eurozona": lambda: (fetch_ecb.fetch_growth_yoy("EA20"), fetch_ecb.fetch_inflation_yoy("EA")),
        "Italia": lambda: (fetch_ecb.fetch_growth_yoy("IT"), fetch_ecb.fetch_inflation_yoy("IT")),
        "UK": lambda: (fetch_boe.fetch_growth_yoy(), fetch_boe.fetch_inflation_yoy()),
        "Giappone": lambda: (
            fetch_japan.fetch_growth_yoy(estat_app_id),
            fetch_japan.fetch_inflation_yoy(estat_app_id),
        ),
    }


def update_area(area: str, fetch_fn) -> None:
    growth, inflation = fetch_fn()
    cache.write_indicator_series(area, "growth_yoy", growth)
    cache.write_indicator_series(area, "inflation_yoy", inflation)
    regime = classify_regime(growth, inflation)
    phase = classify_cycle(growth)
    computed_at = datetime.datetime.now().isoformat(timespec="seconds")
    cache.write_classification(area, computed_at, regime, phase)
    logger.info("%s: regime=%s phase=%s", area, regime, phase)


def main() -> None:
    _load_dotenv()
    fred_key = os.environ.get("FRED_API_KEY", "")
    estat_app_id = os.environ.get("ESTAT_APP_ID", "")
    for area, fetch_fn in _areas(fred_key, estat_app_id).items():
        try:
            update_area(area, fetch_fn)
        except Exception:
            logger.exception("update fallito per area %s, salto e continuo", area)


if __name__ == "__main__":
    main()
