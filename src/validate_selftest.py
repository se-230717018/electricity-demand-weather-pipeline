"""Make every STOP check in validate.py fail once, on purpose (Milestone M3, section 6.2).

Each scenario breaks one thing in a temporary copy of data/grid.db, runs
validate.py on that copy and expects exit status 1. The real database is
never touched. Run from the repository root after clean.py:

    python src/validate_selftest.py
"""

import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from db import DB_PATH, ROOT

VALIDATE = ROOT / "src" / "validate.py"

# Each scenario: (STOP check it targets, fixed SQL that breaks the copy).
SCENARIOS = [
    ("demand_clean row count equals demand",
     "DELETE FROM demand_clean WHERE rowid = (SELECT MIN(rowid) FROM demand_clean)"),
    ("weather_clean row count equals weather",
     "DELETE FROM weather_clean WHERE rowid = (SELECT MIN(rowid) FROM weather_clean)"),
    ("no cleaned demand value <= 0 MWh",
     "UPDATE demand_clean SET value_mwh_raw = -5, value_mwh = -5, value_mwh_flag = 'ok' "
     "WHERE rowid = (SELECT MIN(rowid) FROM demand_clean)"),
    ("no cleaned weather value outside its valid range",
     "UPDATE weather_clean SET relative_humidity_pct_raw = 150, relative_humidity_pct = 150, "
     "relative_humidity_pct_flag = 'ok' WHERE rowid = (SELECT MIN(rowid) FROM weather_clean)"),
    ("untrusted demand flags carry a NULL cleaned value",
     "UPDATE demand_clean SET value_mwh_raw = 1, value_mwh = 1, value_mwh_flag = 'invalid_dropout' "
     "WHERE rowid = (SELECT MIN(rowid) FROM demand_clean)"),
    ("foreign_key_check",
     "INSERT INTO location (location_code, region_key, retrieved_at, source_file) "
     "VALUES ('ZZ_ORPHAN', 999999, '2026-01-01T00:00:00Z', 'selftest')"),
    ("every location and series type is mapped",
     "DELETE FROM map_series_type WHERE rowid = (SELECT MIN(rowid) FROM map_series_type)"),
]


def main():
    if not DB_PATH.exists():
        sys.exit("No database at data/grid.db. Run python src/load.py and python src/clean.py first.")
    passed = 0
    with tempfile.TemporaryDirectory() as tmp:
        for name, sql in SCENARIOS:
            copy = Path(tmp) / "selftest.db"
            shutil.copyfile(DB_PATH, copy)
            con = sqlite3.connect(copy)  # foreign keys left off on purpose, to plant the fault
            con.execute("PRAGMA ignore_check_constraints = ON")  # lets the fault past the schema's CHECKs
            with con:
                con.execute(sql)
            con.close()
            out = subprocess.run([sys.executable, str(VALIDATE), str(copy)], capture_output=True, text=True)
            stop_line = next((l for l in out.stdout.splitlines() if l.startswith("STOP") and name in l), None)
            ok = out.returncode == 1 and stop_line is not None
            passed += ok
            print(f"{'OK  ' if ok else 'FAIL'}  broke '{name}' -> exit {out.returncode}; "
                  + (stop_line.strip() if stop_line else "no STOP line for this check"))
    print(f"\n{passed}/{len(SCENARIOS)} STOP checks failed when they should")
    sys.exit(0 if passed == len(SCENARIOS) else 1)


if __name__ == "__main__":
    main()
