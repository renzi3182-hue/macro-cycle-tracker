import json
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


def test_macro_only_skips_markets_and_keeps_their_failures(monkeypatch):
    calls, meta = [], {"fetch_failures": json.dumps([
        {"area": "Mercati", "indicator": "vix", "time": "2026-10-19T22:00:00", "message": "x"},
        {"area": "USA", "indicator": "growth_yoy", "time": "2026-10-19T22:00:00", "message": "y"}])}
    monkeypatch.setattr(update_data, "_load_dotenv", lambda: None)
    monkeypatch.setattr(update_data.cache, "migrate_phase_names", lambda *a: None)
    monkeypatch.setattr(update_data, "_areas", lambda *a: {})
    monkeypatch.setattr(update_data.fetch_fred, "calls", {"tried": 0, "ok": 0})
    monkeypatch.setattr(update_data.cache, "read_meta", meta.get)
    monkeypatch.setattr(update_data.cache, "write_meta", meta.__setitem__)
    for name in ("update_calendar", "update_market_context", "update_asset_prices", "update_history", "update_intermarket", "update_allocation"):
        monkeypatch.setattr(update_data, name, lambda *a, name=name: calls.append(name))
    update_data.main(["--macro-only"])
    assert calls == ["update_calendar"]
    assert [f["indicator"] for f in json.loads(meta["fetch_failures"])] == ["vix"]  # USA si e' riprovata
    calls.clear()
    update_data.main([])
    assert calls == ["update_calendar", "update_market_context", "update_asset_prices", "update_history", "update_intermarket",
                     "update_allocation"]
