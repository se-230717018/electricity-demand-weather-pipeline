"""Shared database helpers for the M2 loader, checks and queries.

Every script connects through connect(), so foreign keys are always enforced.
The other helpers turn raw-file values into what the schema expects.
"""
import math
import re
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "grid.db"
SCHEMA_PATH = ROOT / "sql" / "schema.sql"

# "20261010T194440Z_NYIS_page001.json" -> groups for 2026-10-10T19:44:40Z
_FILE_TS = re.compile(r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z_")
# "2019-01-01T00" (EIA) or "2019-01-01T00:00" (Open-Meteo)
_HOUR = re.compile(r"^(\d{4}-\d{2}-\d{2})T(\d{2})(?::(\d{2}))?$")


def connect(db_path=DB_PATH) -> sqlite3.Connection:
    """Open the database, switch foreign keys on, and make sure every table exists."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")  # first thing, on every connection
    con.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))  # safe to repeat
    return con


def retrieved_at_from_filename(path) -> str:
    """UTC retrieval time from a landed file name, as YYYY-MM-DDTHH:MM:SSZ.

    Raises ValueError for a name without a timestamp: provenance is required,
    so such a file must stop the load rather than be guessed.
    """
    match = _FILE_TS.match(Path(path).name)
    if not match:
        raise ValueError(f"raw file name has no UTC timestamp: {Path(path).name}")
    y, mo, d, h, mi, s = match.groups()
    return f"{y}-{mo}-{d}T{h}:{mi}:{s}Z"


def to_utc_hour(text):
    """'2019-01-01T00' or '2019-01-01T00:00' -> '2019-01-01T00:00Z'; None if unparseable.

    Both sources already deliver UTC (EIA by definition, Open-Meteo because we
    request timezone=GMT and the loader checks utc_offset_seconds == 0).
    """
    if not isinstance(text, str):
        return None
    match = _HOUR.match(text.strip())
    if not match:
        return None
    day, hour, minute = match.group(1), match.group(2), match.group(3) or "00"
    try:
        datetime.strptime(f"{day} {hour}:{minute}", "%Y-%m-%d %H:%M")  # real date?
    except ValueError:
        return None
    return f"{day}T{hour}:{minute}Z"


def to_number(value):
    """Return (number, cleaned).

    number is a float, or None when the value is missing or not a finite number.
    cleaned is True when the value was turned into None, so the loader can count it.
    """
    if isinstance(value, bool):
        return None, True
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            return None, True
    else:  # None or anything else
        return None, True
    if not math.isfinite(number):
        return None, True
    return number, False