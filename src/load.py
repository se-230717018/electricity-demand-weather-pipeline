"""Build the SQLite database from the landed raw files (Milestone M2).

Reads data/raw/ only; it never calls an API. Run from the repository root:

    python src/load.py

The whole load is one transaction: if anything fails, nothing from this run is
written. Running it again on the same raw files leaves the database unchanged.
"""

import sys
from pathlib import Path

from db import DB_PATH, ROOT, connect, retrieved_at_from_filename
from load_eia import load_eia
from load_weather import load_weather

RAW_DIR = ROOT / "data" / "raw"

# Fixed SQL text per table: no table name or value is ever formatted into SQL.
COUNT_SQL = {
    "region": "SELECT COUNT(*) FROM region",
    "series_type": "SELECT COUNT(*) FROM series_type",
    "location": "SELECT COUNT(*) FROM location",
    "demand": "SELECT COUNT(*) FROM demand",
    "weather": "SELECT COUNT(*) FROM weather",
    "quarantine": "SELECT COUNT(*) FROM quarantine",
}


def list_raw_files(raw_dir, source):
    """[(path, retrieved_at), ...] for one source, oldest retrieval first."""
    folder = Path(raw_dir) / source
    paths = folder.glob("*.json") if folder.is_dir() else []
    files = [(path, retrieved_at_from_filename(path)) for path in paths]
    return sorted(files, key=lambda item: (item[1], item[0].name))


def table_counts(con):
    return {table: con.execute(sql).fetchone()[0] for table, sql in COUNT_SQL.items()}


def print_summary(files, before, after, results, fk_problems):
    dates = sorted(retrieved_at[:10] for _, retrieved_at in files)
    new = {table: after[table] - before[table] for table in after}
    cleaned = sum(r["values_cleaned"] for r in results)
    quarantined = sum(r["quarantined"] for r in results)

    print(f"files read: {len(files)} raw files ({dates[0]} .. {dates[-1]})")
    for r in results:
        print(f"  {r['source']}: {r['files']} files")
    print(f"regions: {after['region']} in database ({new['region']} new this run)")
    print(f"series types: {after['series_type']} in database ({new['series_type']} new this run)")
    print(f"locations: {after['location']} in database ({new['location']} new this run)")
    print(f"demand: {after['demand']:,} in database (+{new['demand']:,} this run)")
    print(f"weather: {after['weather']:,} in database (+{new['weather']:,} this run)")
    print(f"values cleaned: {cleaned:,} (missing or non-numeric -> NULL)")
    print(f"quarantined: {quarantined:,} records this run ({after['quarantine']:,} in quarantine table)")
    print("foreign_key_check: " + ("OK" if not fk_problems else f"{len(fk_problems)} PROBLEMS"))
    print("STATUS: " + ("COMPLETE" if not fk_problems else "INCOMPLETE"))


def run_load(db_path=DB_PATH, raw_dir=RAW_DIR):
    """Load every raw file into the database at db_path. Returns the table counts."""
    eia_files = list_raw_files(raw_dir, "eia")
    weather_files = list_raw_files(raw_dir, "open_meteo")
    files = eia_files + weather_files
    if not files:
        raise SystemExit(f"No raw files in {raw_dir}. Run python src/ingest.py first.")

    con = connect(db_path)
    try:
        before = table_counts(con)
        try:
            with con:  # one transaction: commit on success, roll back on any error
                con.execute("BEGIN")
                eia = load_eia(con, eia_files)  # regions first: locations refer to them
                weather = load_weather(con, weather_files)
        except Exception:
            print("STATUS: FAILED - the load was rolled back, nothing from this run was written")
            raise
        after = table_counts(con)
        fk_problems = con.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        con.close()

    eia["source"], weather["source"] = "eia", "open_meteo"
    print_summary(files, before, after, [eia, weather], fk_problems)
    return after


if __name__ == "__main__":
    try:
        run_load()
    except Exception as exc:
        print(f"ERROR: {exc.__class__.__name__}: {exc}")
        sys.exit(1)
