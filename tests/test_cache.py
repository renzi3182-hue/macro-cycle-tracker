import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.data import cache


def test_write_and_read_indicator_series(tmp_path):
    db_path = tmp_path / "test.db"
    series = pd.Series([1.0, 2.0, 3.0], index=pd.date_range("2024-01-01", periods=3, freq="MS"))

    cache.write_indicator_series("USA", "growth_yoy", series, db_path=db_path)
    result = cache.read_indicator_series("USA", "growth_yoy", db_path=db_path)

    assert list(result.values) == [1.0, 2.0, 3.0]
    assert len(result) == 3


def test_read_missing_series_returns_empty(tmp_path):
    db_path = tmp_path / "test.db"
    result = cache.read_indicator_series("USA", "growth_yoy", db_path=db_path)
    assert result.empty


def test_write_indicator_series_upserts(tmp_path):
    db_path = tmp_path / "test.db"
    dates = pd.date_range("2024-01-01", periods=2, freq="MS")
    cache.write_indicator_series("USA", "growth_yoy", pd.Series([1.0, 2.0], index=dates), db_path=db_path)
    cache.write_indicator_series("USA", "growth_yoy", pd.Series([9.0, 2.0], index=dates), db_path=db_path)

    result = cache.read_indicator_series("USA", "growth_yoy", db_path=db_path)
    assert list(result.values) == [9.0, 2.0]


def test_classifications_roundtrip(tmp_path):
    db_path = tmp_path / "test.db"
    cache.write_classification("USA", "2026-01-01T00:00:00", "Espansione", "Espansione", db_path=db_path)
    cache.write_classification("USA", "2026-02-01T00:00:00", "Stagflazione", "Rallentamento", db_path=db_path)

    last_two = cache.read_last_two_classifications("USA", db_path=db_path)

    assert len(last_two) == 2
    assert last_two[0]["regime"] == "Stagflazione"
    assert last_two[1]["regime"] == "Espansione"


def test_classifications_empty(tmp_path):
    db_path = tmp_path / "test.db"
    assert cache.read_last_two_classifications("USA", db_path=db_path) == []


def test_write_indicator_series_drops_stale_dates(tmp_path):
    # fonte passata da trimestrale a mensile: le date vecchie non devono restare mescolate
    db_path = tmp_path / "test.db"
    cache.write_indicator_series("UK", "cpi", pd.Series([1.0], index=pd.to_datetime(["2020-02-15"])), db_path=db_path)
    cache.write_indicator_series("UK", "cpi", pd.Series([2.0], index=pd.to_datetime(["2020-03-01"])), db_path=db_path)
    assert list(cache.read_indicator_series("UK", "cpi", db_path=db_path).values) == [2.0]


def test_migrate_phase_names(tmp_path):
    db_path = tmp_path / "test.db"
    cache.write_classification("USA", "2026-01-01T00:00:00", "Goldilocks", "Ripresa", db_path=db_path)
    cache.write_classification("USA", "2026-02-01T00:00:00", "Goldilocks", "Espansione", db_path=db_path)

    cache.migrate_phase_names("Ripresa", "Ripresa (sotto trend)", db_path=db_path)
    with cache.get_connection(db_path) as conn:
        phases = [r[0] for r in conn.execute("SELECT phase FROM classifications ORDER BY computed_at")]
    assert phases == ["Ripresa (sotto trend)", "Espansione"]

    cache.migrate_phase_names("Ripresa", "Ripresa (sotto trend)", db_path=db_path)  # idempotente
    with cache.get_connection(db_path) as conn:
        phases = [r[0] for r in conn.execute("SELECT phase FROM classifications ORDER BY computed_at")]
    assert phases == ["Ripresa (sotto trend)", "Espansione"]


def test_meta_roundtrip(tmp_path):
    db = tmp_path / "t.db"
    assert cache.read_meta("updated_at", db_path=db) is None
    cache.write_meta("updated_at", "2026-09-30T10:00:00+00:00", db_path=db)
    cache.write_meta("updated_at", "2026-09-30T11:00:00+00:00", db_path=db)
    assert cache.read_meta("updated_at", db_path=db) == "2026-09-30T11:00:00+00:00"
