"""Unit tests for src/clean_demand.py: one test per flag rule (M3 flag order).

Each test builds a small in-memory database from the real sql/schema.sql and
sql/clean_schema.sql, runs clean_demand() and checks the flags. No data files
and no grid.db are needed. Run from the repository root:

    python -m unittest discover tests -v
"""

import sqlite3
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from clean_demand import clean_demand  # noqa: E402

START = datetime(2024, 1, 1)
TIME_FORMAT = "%Y-%m-%dT%H:%MZ"


def hours(n, skip=()):
    """n consecutive UTC hours as period_utc strings, leaving out the indexes in skip."""
    return [(START + timedelta(hours=i)).strftime(TIME_FORMAT) for i in range(n) if i not in skip]


def base_values(n):
    """Ordinary demand: 1000..1060 MWh in a 7-hour cycle, so no value repeats in a row."""
    return [1000.0 + (i % 7) * 10 for i in range(n)]


def build_db(actual, forecast=None, periods=None, map_forecast=True):
    """In-memory DB with one region (TEST), series D and DF, and the M3 cleaning tables."""
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript((ROOT / "sql" / "schema.sql").read_text(encoding="utf-8"))
    con.executescript((ROOT / "sql" / "clean_schema.sql").read_text(encoding="utf-8"))

    meta = ("2024-01-01T00:00:00Z", "test")
    con.execute("INSERT INTO region VALUES (1, 'TEST', 'Test region', ?, ?)", meta)
    con.execute("INSERT INTO series_type VALUES (1, 'D', 'Demand', ?, ?)", meta)
    con.execute("INSERT INTO series_type VALUES (2, 'DF', 'Day-ahead demand forecast', ?, ?)", meta)
    con.execute("INSERT INTO map_series_type VALUES (1, 'actual', 'MWh', 'test', '2024-01-01', 'test')")
    if map_forecast:
        con.execute("INSERT INTO map_series_type VALUES (2, 'forecast', 'MWh', 'test', '2024-01-01', 'test')")

    periods = periods or hours(len(actual))
    rows = [(1, 1, p, v) + meta for p, v in zip(periods, actual)]
    if forecast is not None:
        rows += [(1, 2, p, v) + meta for p, v in zip(periods, forecast)]
    con.executemany("INSERT INTO demand VALUES (?, ?, ?, ?, ?, ?)", rows)
    return con


def flags(con, type_key=1):
    """List of (value_mwh, value_mwh_flag) for one series, in time order."""
    return con.execute(
        "SELECT value_mwh, value_mwh_flag FROM demand_clean WHERE type_key = ? ORDER BY period_utc",
        (type_key,),
    ).fetchall()


class CleanDemandTest(unittest.TestCase):

    def db(self, *args, **kwargs):
        con = build_db(*args, **kwargs)
        self.addCleanup(con.close)
        return con

    def test_clean_series_is_all_ok(self):
        con = self.db(base_values(48))
        clean_demand(con)
        self.assertEqual({flag for _, flag in flags(con)}, {"ok"})

    def test_rule1_null_is_missing_not_reported(self):
        values = base_values(48)
        values[5] = None
        con = self.db(values)
        clean_demand(con)
        self.assertEqual(flags(con)[5], (None, "missing_not_reported"))

    def test_rule2_zero_and_negative_are_nonpositive(self):
        values = base_values(48)
        values[5], values[20] = 0.0, -3.0
        con = self.db(values)
        clean_demand(con)
        self.assertEqual(flags(con)[5], (None, "invalid_nonpositive"))
        self.assertEqual(flags(con)[20], (None, "invalid_nonpositive"))

    def test_rule3_tiny_value_is_dropout(self):
        values = base_values(48)
        values[5] = 50.0  # below 10 % of the ~1030 MWh median
        con = self.db(values)
        clean_demand(con)
        self.assertEqual(flags(con)[5], (None, "invalid_dropout"))

    def test_rule4_six_equal_hours_are_stuck(self):
        values = base_values(48)
        values[10:16] = [1030.0] * 6
        con = self.db(values)
        clean_demand(con)
        result = flags(con)
        self.assertTrue(all(row == (None, "stuck_value") for row in result[10:16]))
        self.assertEqual(result[9][1], "ok")
        self.assertEqual(result[16][1], "ok")

    def test_rule4_five_equal_hours_are_not_stuck(self):
        values = base_values(48)
        values[10:15] = [1030.0] * 5
        con = self.db(values)
        clean_demand(con)
        self.assertTrue(all(flag == "ok" for _, flag in flags(con)[10:15]))

    def test_rule4_missing_hour_breaks_the_run(self):
        # 6 equal values, but hour 13 does not exist: two runs of 3 and 3
        periods = hours(49, skip={13})
        values = base_values(48)
        values[10:16] = [1030.0] * 6
        con = self.db(values, periods=periods)
        clean_demand(con)
        self.assertTrue(all(flag == "ok" for _, flag in flags(con)[10:16]))

    def test_rule5_forecast_far_from_actual_is_mismatch_and_kept(self):
        actual = base_values(48)
        forecast = list(actual)
        forecast[7] = actual[7] * 2.5  # DF / D = 2.5 > DF_D_RATIO_MAX
        con = self.db(actual, forecast)
        clean_demand(con)
        self.assertEqual(flags(con, type_key=2)[7], (forecast[7], "forecast_mismatch"))

    def test_rule5_skipped_when_actual_is_untrusted(self):
        actual = base_values(48)
        actual[7] = None  # no trusted D for this hour
        forecast = base_values(48)
        con = self.db(actual, forecast)
        clean_demand(con)
        self.assertEqual(flags(con, type_key=2)[7][1], "ok")

    def test_rule6_extreme_values_are_unusual_and_kept(self):
        values = base_values(48)
        values[5], values[30] = 5000.0, 600.0
        con = self.db(values)
        clean_demand(con)
        self.assertEqual(flags(con)[5], (5000.0, "unusual_high"))
        self.assertEqual(flags(con)[30], (600.0, "unusual_low"))

    def test_every_raw_row_appears_once(self):
        actual = base_values(48)
        actual[3] = None
        con = self.db(actual, base_values(48))
        summary = clean_demand(con)
        self.assertEqual(summary["rows"], summary["raw_rows"])
        self.assertEqual(summary["rows"], 96)

    def test_unmapped_series_type_stops_the_run(self):
        con = self.db(base_values(48), base_values(48), map_forecast=False)
        with self.assertRaises(ValueError):
            clean_demand(con)


if __name__ == "__main__":
    unittest.main()