"""Prove the database's guarantees instead of claiming them (Milestone M2).

Runs six checks and prints PASS or FAIL for each. It never touches the real
database: checks 1-4 and 6 work on a temporary copy of data/grid.db, and
check 5 builds a fresh temporary database. Run from the repository root:

    python src/load.py      # build data/grid.db first
    python src/checks.py
"""

import contextlib
import io
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

from db import DB_PATH, connect, retrieved_at_from_filename
from load import RAW_DIR, run_load, table_counts

# Fixed SQL per table, so whole-table contents can be compared (no formatting).
CONTENT_SQL = {
    "region": "SELECT * FROM region ORDER BY respondent",
    "series_type": "SELECT * FROM series_type ORDER BY type_code",
    "location": "SELECT * FROM location ORDER BY location_code",
    "demand": "SELECT * FROM demand ORDER BY region_key, type_key, period_utc",
    "weather": "SELECT * FROM weather ORDER BY location_key, observed_at",
    "quarantine": "SELECT source, source_file, record_ref, reason, raw_record, retrieved_at "
                  "FROM quarantine ORDER BY source, source_file, record_ref",
}

INSERT_REGION = "INSERT INTO region (respondent, respondent_name, retrieved_at, source_file) VALUES (?, ?, ?, ?)"
INSERT_TYPE = "INSERT INTO series_type (type_code, type_name, retrieved_at, source_file) VALUES (?, ?, ?, ?)"
INSERT_DEMAND = ("INSERT INTO demand (region_key, type_key, period_utc, value_mwh, retrieved_at, source_file) "
                 "VALUES (?, ?, ?, ?, ?, ?)")
NOW = "2026-10-24T00:00:00Z"
results = []


def report(name, passed, detail):
    results.append(passed)
    print(f"{name}: {'PASS' if passed else 'FAIL'} - {detail}")


def rejected(con, sql, params):
    """True if the database refuses the statement. Nothing is ever kept."""
    try:
        con.execute(sql, params)
    except sqlite3.Error as exc:
        con.rollback()
        return True, f"rejected ({exc})"
    con.rollback()
    return False, "accepted, but should have been rejected"


def contents(con):
    return {table: con.execute(sql).fetchall() for table, sql in CONTENT_SQL.items()}


def quiet_load(db_path, raw_dir):
    """Run the real loader without printing its summary."""
    with contextlib.redirect_stdout(io.StringIO()):
        run_load(db_path, raw_dir)


def sample_raw_dir(tmp):
    """A small raw folder: the first few landed files of each source (copies)."""
    sample = Path(tmp) / "raw"
    for source, n in (("eia", 3), ("open_meteo", 3)):
        (sample / source).mkdir(parents=True)
        for path in sorted((RAW_DIR / source).glob("*.json"))[:n]:
            shutil.copy(path, sample / source / path.name)
    return sample


def main():
    if not DB_PATH.exists():
        sys.exit("No database at data/grid.db. Run python src/load.py first.")

    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "check.db"
        shutil.copyfile(DB_PATH, copy)
        con = connect(copy)

        # Make sure there is one region and one series type to point at.
        if con.execute("SELECT COUNT(*) FROM region").fetchone()[0] == 0:
            con.execute(INSERT_REGION, ("CHECK", "check region", NOW, "checks.py"))
        if con.execute("SELECT COUNT(*) FROM series_type").fetchone()[0] == 0:
            con.execute(INSERT_TYPE, ("CHK", "check type", NOW, "checks.py"))
        con.commit()
        region_key, respondent = con.execute("SELECT region_key, respondent FROM region LIMIT 1").fetchone()
        type_key = con.execute("SELECT type_key FROM series_type LIMIT 1").fetchone()[0]
        missing_region = con.execute("SELECT COALESCE(MAX(region_key), 0) + 1000 FROM region").fetchone()[0]

        # 1. Duplicate natural key
        ok, detail = rejected(con, INSERT_REGION, (respondent, "duplicate", NOW, "checks.py"))
        report("1 duplicate natural key", ok, detail)

        # 2. Orphan event
        ok, detail = rejected(con, INSERT_DEMAND,
                              (missing_region, type_key, "2019-01-01T00:00Z", 1.0, NOW, "checks.py"))
        report("2 orphan event", ok, detail)

        # 3. NULL in a key column
        ok, detail = rejected(con, INSERT_DEMAND, (region_key, type_key, None, 1.0, NOW, "checks.py"))
        report("3 NULL key", ok, detail)

        # 4. Wrong type (text into a REAL column)
        ok, detail = rejected(con, INSERT_DEMAND,
                              (region_key, type_key, "1999-01-01T00:00Z", "n/a", NOW, "checks.py"))
        report("4 wrong type", ok, detail)
        con.close()

        # 5. Idempotence: load the same raw files twice into a fresh database.
        sample = sample_raw_dir(tmp)
        fresh = Path(tmp) / "fresh.db"
        quiet_load(fresh, sample)
        con = connect(fresh)
        first_counts, first_rows = table_counts(con), contents(con)
        con.close()
        quiet_load(fresh, sample)
        con = connect(fresh)
        second_counts, second_rows = table_counts(con), contents(con)
        con.close()
        same = first_counts == second_counts and first_rows == second_rows
        report("5 idempotence", same and sum(first_counts.values()) > 0,
               f"counts after 1st load {first_counts}, after 2nd load {second_counts}")

        # 6. Atomicity: a valid new file followed by a broken one must change nothing.
        con = connect(copy)
        before = table_counts(con)
        con.close()
        bad_raw = Path(tmp) / "bad_raw"
        (bad_raw / "eia").mkdir(parents=True)
        good = {"response": {"total": "1", "data": [{
            "period": "2019-01-01T00", "respondent": "ZZCHECK", "respondent-name": "atomicity check",
            "type": "D", "type-name": "Demand", "value": "1"}]}}
        (bad_raw / "eia" / "20990101T000000Z_ZZCHECK_page001.json").write_text(json.dumps(good))
        (bad_raw / "eia" / "20990101T000001Z_ZZCHECK_page002.json").write_text("{ this is not json")
        try:
            quiet_load(copy, bad_raw)
            failed = False
        except Exception:
            failed = True
        con = connect(copy)
        after = table_counts(con)
        con.close()
        report("6 atomicity", failed and before == after,
               f"load {'failed' if failed else 'did NOT fail'}; counts before {before}, after {after}")

    print(f"\n{sum(results)}/{len(results)} checks passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
