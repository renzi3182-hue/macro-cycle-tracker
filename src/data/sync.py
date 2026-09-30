"""Scarica la cache aggiornata dal workflow GitHub Actions (release `data-latest` del repo di deploy).

Non e' una chiamata alle API dei dati: e' il file data/cache.db gia' calcolato. Si scarica solo se piu' recente
del file locale, quindi in locale (dove update_data e' appena girato) non sovrascrive nulla."""
import os
import tempfile
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

DATA_URL = "https://github.com/renzi3182-hue/macro-cycle-tracker/releases/download/data-latest/cache.db"
DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "cache.db"


def sync_cache(url: str = DATA_URL, db_path: Path = DB_PATH) -> bool:
    """True se ha sostituito il file locale. Qualsiasi errore di rete lascia la cache com'e'."""
    try:
        head = requests.head(url, allow_redirects=True, timeout=15)
        if head.status_code != 200 or "Last-Modified" not in head.headers:
            return False
        remote = parsedate_to_datetime(head.headers["Last-Modified"]).timestamp()
        if db_path.exists() and db_path.stat().st_mtime >= remote:
            return False
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=db_path.parent, delete=False) as tmp:
            tmp.write(resp.content)
        os.replace(tmp.name, db_path)
        return True
    except (requests.RequestException, OSError):
        return False
