"""Build the cleaned layer from the M2 tables (Milestone M3).

Reads the M2 tables only (never raw files, never the API) and writes the
cleaned tables and the mapping tables. Run from the repository root:

    python src/load.py && python src/clean.py

Rules this script enforces:
- M2 tables are never changed: their contents are hashed before and after the
  build, inside the same transaction; any difference rolls the build back.
- The whole build is one transaction: if anything fails, the cleaned layer is
  left exactly as it was before the run.
- Each cleaned table must end with the same number of rows as its M2 table.
"""

import csv
import hashlib
import sys

from clean_config import MAPPINGS_DIR
from clean_demand import clean_demand
from clean_weather import clean_weather
from db import DB_PATH, ROOT, connect

CLEAN_SCHEMA = ROOT / "sql" / "clean_schema.sql"

# Fixed SQL per M2 table, ordered, so the contents can be hashed (no formatting).
M2_CONTENT_SQL = {
    "region": "SELECT * FROM region ORDER BY region_key",
    "series_type": "SELECT * FROM series_type ORDER BY type_key",
    "location": "SELECT * FROM location ORDER BY location_key",
    "demand": "SELECT * FROM demand ORDER BY region_key, type_key, period_utc",
    "weather": "SELECT * FROM weather ORDER BY location_key, observed_at",
    "quarantine": "SELECT * FROM quarantine ORDER BY quarantine_id",
}

# Cleaned table -> (SQL counting its rows, SQL counting its M2 table's rows).
ROW_COUNT_SQL = {
    "demand_clean": ("SELECT COUNT(*) FROM demand_clean", "SELECT COUNT(*) FROM demand"),
    "weather_clean": ("SELECT COUNT(*) FROM weather_clean", "SELECT COUNT(*) FROM weather"),
}

# Rebuild strategy: empty the cleaned layer, then rebuild it, inside one transaction.
# Only cleaned and mapping tables appear here; M2 tables are never deleted from.
CLEAR_SQL = (
    "DELETE FROM demand_clean",
    "DELETE FROM weather_clean",
    "DELETE FROM map_region_location",
    "DELETE FROM map_series_type",
)

DEMAND_FLAGS_SQL = """
SELECT r.respondent || ' ' || s.type_code AS entity, d.value_mwh_flag, COUNT(*)
FROM demand_clean d
JOIN region r ON r.region_key = d.region_key
JOIN series_type s ON s.type_key = d.type_key
GROUP BY entity, d.value_mwh_flag
"""

# One fixed query per weather variable (column names are never formatted into SQL).
WEATHER_FLAGS_SQL = {
    "temperature_c": "SELECT l.location_code, w.temperature_c_flag, COUNT(*) FROM weather_clean w "
                     "JOIN location l ON l.location_key = w.location_key GROUP BY 1, 2",
    "relative_humidity_pct": "SELECT l.location_code, w.relative_humidity_pct_flag, COUNT(*) FROM weather_clean w "
                             "JOIN location l ON l.location_key = w.location_key GROUP BY 1, 2",
    "precipitation_mm": "SELECT l.location_code, w.precipitation_mm_flag, COUNT(*) FROM weather_clean w "
                        "JOIN location l ON l.location_key = w.location_key GROUP BY 1, 2",
}

DEMAND_FLAG_ORDER = ("ok", "missing_not_reported", "invalid_nonpositive", "invalid_dropout",
                     "stuck_value", "forecast_mismatch", "unusual_high", "unusual_low")
WEATHER_FLAG_ORDER = ("ok", "missing_not_reported", "invalid_out_of_range", "stuck_value",
                      "spike", "unusual_high", "unusual_low")


def m2_fingerprint(con):
    """SHA-256 of every M2 table's full contents."""
    digests = {}
    for table, sql in M2_CONTENT_SQL.items():
        h = hashlib.sha256()
        for row in con.execute(sql):
            h.update(repr(row).encode("utf-8"))
        digests[table] = h.hexdigest()
    return digests


def read_mapping(name, key_column):
    """Rows of data/mappings/<name>; a key decided twice is an error, not a guess."""
    path = MAPPINGS_DIR / name
    if not path.exists():
        return None
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(fh)]
    seen = set()
    for row in rows:
        key = row.get(key_column, "")
        if key in seen:
            raise ValueError(f"{name}: '{key}' is decided more than once - keep one row per {key_column}")
        seen.add(key)
    return rows


def load_mappings(con):
    """Load both mapping CSVs; return a short report with unmatched entries."""
    report = []

    rows = read_mapping("region_location.csv", "location_code")
    if rows is None:
        report.append(("region_location.csv", 0, ["file not found"]))
    else:
        unmatched, loaded = [], 0
        for row in rows:
            loc = con.execute("SELECT location_key FROM location WHERE location_code = ?",
                              (row["location_code"],)).fetchone()
            reg = con.execute("SELECT region_key FROM region WHERE respondent = ?",
                              (row["respondent"],)).fetchone()
            if loc is None or reg is None:
                unmatched.append(f"{row['location_code']} -> {row['respondent']}")
                continue
            con.execute("INSERT INTO map_region_location (location_key, region_key, city, decided_by, decided_at, note) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (loc[0], reg[0], row["city"], row["decided_by"], row["decided_at"], row["note"]))
            loaded += 1
        for (code,) in con.execute("SELECT location_code FROM location WHERE location_key NOT IN "
                                   "(SELECT location_key FROM map_region_location)"):
            unmatched.append(f"location {code} has no mapping row")
        report.append(("region_location.csv", loaded, unmatched))

    rows = read_mapping("series_type_role.csv", "type_code")
    if rows is None:
        report.append(("series_type_role.csv", 0, ["file not found"]))
    else:
        unmatched, loaded = [], 0
        for row in rows:
            typ = con.execute("SELECT type_key FROM series_type WHERE type_code = ?",
                              (row["type_code"],)).fetchone()
            if typ is None:
                unmatched.append(row["type_code"])
                continue
            con.execute("INSERT INTO map_series_type (type_key, role, unit, decided_by, decided_at, note) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (typ[0], row["role"], row["unit"], row["decided_by"], row["decided_at"], row["note"]))
            loaded += 1
        for (code,) in con.execute("SELECT type_code FROM series_type WHERE type_key NOT IN "
                                   "(SELECT type_key FROM map_series_type)"):
            unmatched.append(f"series type {code} has no mapping row")
        report.append(("series_type_role.csv", loaded, unmatched))
    return report


def print_flag_table(title, rows, order):
    counts = {}
    for entity, flag, n in rows:
        counts.setdefault(entity, {})[flag] = n
    print(title)
    print("  " + "entity".ljust(10) + "".join(f.rjust(22) for f in order))
    for entity in sorted(counts):
        print("  " + entity.ljust(10) + "".join(f"{counts[entity].get(f, 0):>22,}" for f in order))


def run_clean(db_path=DB_PATH):
    con = connect(db_path)
    try:
        con.executescript(CLEAN_SCHEMA.read_text(encoding="utf-8"))  # creates the layer if missing
        before = m2_fingerprint(con)
        try:
            with con:  # one transaction: the old cleaned layer stays if anything below fails
                con.execute("BEGIN")
                for sql in CLEAR_SQL:
                    con.execute(sql)
                mapping_report = load_mappings(con)
                clean_demand(con)
                clean_weather(con)
                if m2_fingerprint(con) != before:
                    raise RuntimeError("an M2 table changed during cleaning - rolled back")
                counts = {t: (con.execute(c).fetchone()[0], con.execute(r).fetchone()[0])
                          for t, (c, r) in ROW_COUNT_SQL.items()}
                for table, (clean_rows, raw_rows) in counts.items():
                    if clean_rows not in (0, raw_rows):
                        raise RuntimeError(f"{table} has {clean_rows} rows but its M2 table has {raw_rows}")
        except Exception:
            print("STATUS: FAILED - the cleaning run was rolled back; the cleaned layer is unchanged")
            raise

        not_built = [t for t, (c, r) in counts.items() if c == 0 and r > 0]
        for table, (clean_rows, raw_rows) in counts.items():
            note = "  <- not built yet" if table in not_built else ""
            print(f"{table}: {clean_rows:,} rows (raw: {raw_rows:,}){note}")
        print_flag_table("demand_clean.value_mwh_flag", con.execute(DEMAND_FLAGS_SQL).fetchall(), DEMAND_FLAG_ORDER)
        for column, sql in WEATHER_FLAGS_SQL.items():
            print_flag_table(f"weather_clean.{column}_flag", con.execute(sql).fetchall(), WEATHER_FLAG_ORDER)
        unmatched_total = 0
        for name, loaded, unmatched in mapping_report:
            unmatched_total += len(unmatched)
            print(f"mappings: {name} {loaded} rows loaded"
                  + (f" · unmatched: {', '.join(unmatched)}" if unmatched else " · all matched"))
        print("M2 tables unchanged: OK (hashed before and after)")
        complete = not not_built and unmatched_total == 0
        print("STATUS: " + ("COMPLETE" if complete else "INCOMPLETE"))
        return complete
    finally:
        con.close()


if __name__ == "__main__":
    try:
        ok = run_clean()
    except Exception as exc:
        print(f"ERROR: {exc.__class__.__name__}: {exc}")
        sys.exit(1)
    sys.exit(0 if ok else 1)
