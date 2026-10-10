import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.scheduler import update_data


def test_history_regime_key_collapses_uncertain_pairs():
    assert update_data.history_regime_key({"regime": "Reflazione", "regime_label": "Reflazione"}) == "Reflazione"
    assert update_data.history_regime_key({"regime": "Reflazione", "regime_label": "Incerto: Reflazione / Stagflazione"}) == "Incerto"
    assert update_data.history_regime_key({"regime": "Deflazione", "regime_label": "Incerto: Stagflazione / Deflazione"}) == "Incerto"


def test_record_failure_strips_query_string_and_api_key():
    update_data.FETCH_FAILURES.clear()
    exc = Exception("502 Server Error: Bad Gateway for url: https://api.stlouisfed.org/fred/series/observations?series_id=CPILFENS&api_key=SECRET123")
    update_data._record_failure("USA", "core_inflation_yoy", exc)
    failure = update_data.FETCH_FAILURES[-1]
    assert "SECRET123" not in failure["message"]
    assert "?" not in failure["message"]
    assert failure["message"].startswith("502 Server Error")
    update_data.FETCH_FAILURES.clear()
