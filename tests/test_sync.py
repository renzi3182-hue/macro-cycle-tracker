import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from src.data.sync import sync_cache

URL = "https://example.test/cache.db"
NEWER = "Wed, 01 Oct 2026 10:00:00 GMT"
OLDER = "Mon, 01 Jan 2024 10:00:00 GMT"


def test_downloads_when_remote_is_newer(tmp_path, requests_mock):
    db = tmp_path / "cache.db"
    db.write_bytes(b"old")
    os.utime(db, (1_700_000_000, 1_700_000_000))  # nov 2023
    requests_mock.head(URL, headers={"Last-Modified": NEWER})
    requests_mock.get(URL, content=b"new")
    assert sync_cache(URL, db) is True and db.read_bytes() == b"new"


def test_keeps_local_when_it_is_newer_or_remote_missing(tmp_path, requests_mock):
    db = tmp_path / "cache.db"
    db.write_bytes(b"local")
    requests_mock.head(URL, headers={"Last-Modified": OLDER})
    assert sync_cache(URL, db) is False and db.read_bytes() == b"local"
    requests_mock.head(URL, status_code=404)
    assert sync_cache(URL, db) is False


def test_network_error_leaves_cache_alone(tmp_path, requests_mock):
    db = tmp_path / "cache.db"
    db.write_bytes(b"local")
    requests_mock.head(URL, exc=requests.ConnectionError)
    assert sync_cache(URL, db) is False and db.read_bytes() == b"local"
