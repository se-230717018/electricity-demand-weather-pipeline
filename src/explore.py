"""Helpers for the M4 exploration notebook (notebooks/m4_eda.ipynb).

Exploration never changes data: every connection here is read-only, and
table_hashes() lets the notebook prove the database is unchanged at the end.
No value is ever formatted into SQL; pass values through ? placeholders.
"""

import hashlib
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "grid.db"
FIG_DIR = ROOT / "figures"

# Fixed SQL per table, ordered, so contents can be hashed (no formatting).
HASH_SQL = {
    "region": "SELECT * FROM region ORDER BY region_key",
    "series_type": "SELECT * FROM series_type ORDER BY type_key",
    "location": "SELECT * FROM location ORDER BY location_key",
    "demand": "SELECT * FROM demand ORDER BY region_key, type_key, period_utc",
    "weather": "SELECT * FROM weather ORDER BY location_key, observed_at",
    "quarantine": "SELECT * FROM quarantine ORDER BY quarantine_id",
    "demand_clean": "SELECT * FROM demand_clean ORDER BY region_key, type_key, period_utc",
    "weather_clean": "SELECT * FROM weather_clean ORDER BY location_key, observed_at",
    "map_region_location": "SELECT * FROM map_region_location ORDER BY location_key",
    "map_series_type": "SELECT * FROM map_series_type ORDER BY type_key",
}


def connect_ro(db_path=DB_PATH) -> sqlite3.Connection:
    """Open the database read-only: any write raises an error instead of changing data."""
    db_path = Path(db_path).resolve()
    if not db_path.exists():
        raise FileNotFoundError(f"{db_path} not found - run python src/load.py and python src/clean.py first")
    return sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)


def query(con, sql, params=()) -> pd.DataFrame:
    """Run a fixed SQL text with ? placeholders and return a DataFrame."""
    return pd.read_sql_query(sql, con, params=params)


def table_hashes(con) -> dict:
    """SHA-256 of every table's full contents, to show the notebook changed nothing."""
    digests = {}
    for table, sql in HASH_SQL.items():
        h = hashlib.sha256()
        for row in con.execute(sql):
            h.update(repr(row).encode("utf-8"))
        digests[table] = h.hexdigest()
    return digests


def expected_hours(start_date, end_date) -> int:
    """Number of UTC hours from start_date 00:00 to end_date 23:00 inclusive."""
    return int((pd.Timestamp(end_date) - pd.Timestamp(start_date)).days + 1) * 24


def to_local(utc_series, tz) -> pd.Series:
    """'2019-01-01T00:00Z' strings -> timezone-aware local timestamps (explicit conversion)."""
    return pd.to_datetime(utc_series, utc=True).dt.tz_convert(tz)


def save_fig(fig, name, dpi=150):
    """Write a figure to figures/<name>.png (figures come from code, never screenshots)."""
    FIG_DIR.mkdir(exist_ok=True)
    path = FIG_DIR / f"{name}.png"
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    return path
