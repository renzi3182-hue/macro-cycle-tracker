import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "cache.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS indicators (
    area TEXT NOT NULL,
    indicator TEXT NOT NULL,
    date TEXT NOT NULL,
    value REAL NOT NULL,
    PRIMARY KEY (area, indicator, date)
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events (
    date TEXT NOT NULL,  -- UTC ISO 8601
    country TEXT NOT NULL,  -- valuta: USD, EUR, ...
    title TEXT NOT NULL,
    impact TEXT NOT NULL,  -- Low / Medium / High / Holiday
    forecast TEXT NOT NULL,
    previous TEXT NOT NULL,
    PRIMARY KEY (date, country, title)
);
CREATE TABLE IF NOT EXISTS classifications (
    area TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    regime TEXT NOT NULL,
    phase TEXT NOT NULL
);
"""


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA)
    return conn


MIN_KEEP_RATIO = 0.5  # una serie nuova con meno della meta' dei punti in cache e' sospetta (API cambiata)
MAX_LAST_DATE_REGRESSION_DAYS = 365
GUARD_MIN_POINTS = 24  # sotto questi punti (es. date future del calendario) la serie si sostituisce senza controlli


def write_indicator_series(area: str, indicator: str, series: pd.Series, db_path: Path = DB_PATH) -> None:
    """Sostituisce la serie. Rifiuta (ValueError) serie vuote o molto piu' corte/vecchie di quella in cache:
    una fonte che risponde male non deve cancellare lo storico, che e' anche l'unica copia dei dati."""
    series = series[pd.notna(series)]
    if series.empty:
        raise ValueError(f"{area}/{indicator}: serie vuota, cache non toccata")
    rows = [(area, indicator, str(date.date() if hasattr(date, "date") else date), float(value))
            for date, value in series.items()]
    with get_connection(db_path) as conn:
        old_n, old_last = conn.execute(
            "SELECT COUNT(*), MAX(date) FROM indicators WHERE area = ? AND indicator = ?", (area, indicator)
        ).fetchone()
        new_last = max(r[2] for r in rows)
        guarded = old_n >= GUARD_MIN_POINTS
        if guarded and len(rows) < old_n * MIN_KEEP_RATIO:
            raise ValueError(f"{area}/{indicator}: {len(rows)} punti contro {old_n} in cache, cache non toccata")
        if guarded and (pd.Timestamp(old_last) - pd.Timestamp(new_last)).days > MAX_LAST_DATE_REGRESSION_DAYS:
            raise ValueError(f"{area}/{indicator}: ultimo dato {new_last} contro {old_last} in cache, cache non toccata")
        # Sostituisce la serie intera: se la fonte cambia (dataset o frequenza) non restano righe vecchie mescolate.
        conn.execute("DELETE FROM indicators WHERE area = ? AND indicator = ?", (area, indicator))
        conn.executemany(
            "INSERT OR REPLACE INTO indicators (area, indicator, date, value) VALUES (?, ?, ?, ?)",
            rows,
        )


def read_indicator_series(area: str, indicator: str, db_path: Path = DB_PATH) -> pd.Series:
    with get_connection(db_path) as conn:
        df = pd.read_sql_query(
            "SELECT date, value FROM indicators WHERE area = ? AND indicator = ? ORDER BY date",
            conn,
            params=(area, indicator),
        )
    if df.empty:
        return pd.Series(dtype=float)
    return pd.Series(df["value"].values, index=pd.to_datetime(df["date"]))


def write_classification(area: str, computed_at: str, regime: str, phase: str, db_path: Path = DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO classifications (area, computed_at, regime, phase) VALUES (?, ?, ?, ?)",
            (area, computed_at, regime, phase),
        )


def read_last_two_classifications(area: str, db_path: Path = DB_PATH) -> list[dict]:
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "SELECT computed_at, regime, phase FROM classifications WHERE area = ? "
            "ORDER BY computed_at DESC LIMIT 2",
            (area,),
        )
        rows = cur.fetchall()
    return [{"computed_at": r[0], "regime": r[1], "phase": r[2]} for r in rows]


EVENTS_KEEP_DAYS = 14


def write_events(events: list[dict], now: pd.Timestamp | None = None, db_path: Path = DB_PATH) -> None:
    """Upsert degli eventi del calendario; tiene gli ultimi EVENTS_KEEP_DAYS giorni (il feed copre solo la settimana in corso)."""
    cutoff = ((now or pd.Timestamp.now(tz="UTC")) - pd.Timedelta(days=EVENTS_KEEP_DAYS)).isoformat()
    rows = [(e["date"], e["country"], e["title"], e["impact"], e["forecast"], e["previous"]) for e in events]
    with get_connection(db_path) as conn:
        conn.executemany("INSERT OR REPLACE INTO events VALUES (?, ?, ?, ?, ?, ?)", rows)
        conn.execute("DELETE FROM events WHERE date < ?", (cutoff,))


def read_events(db_path: Path = DB_PATH) -> list[dict]:
    with get_connection(db_path) as conn:
        cur = conn.execute("SELECT date, country, title, impact, forecast, previous FROM events ORDER BY date, country, title")
        return [dict(zip(("date", "country", "title", "impact", "forecast", "previous"), r)) for r in cur.fetchall()]


def write_meta(key: str, value: str, db_path: Path = DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))


def read_meta(key: str, db_path: Path = DB_PATH) -> str | None:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None
