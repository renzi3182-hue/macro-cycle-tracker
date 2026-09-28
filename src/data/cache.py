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


def write_indicator_series(area: str, indicator: str, series: pd.Series, db_path: Path = DB_PATH) -> None:
    rows = [(area, indicator, str(date.date() if hasattr(date, "date") else date), float(value))
            for date, value in series.items()]
    with get_connection(db_path) as conn:
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
