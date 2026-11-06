"""Data-quality expectations as code (Milestone M3).

Checks the cleaned layer and prints one line per check: PASS, WARN or STOP.
Exits with status 1 if any STOP check fails; WARNs are printed every run but
do not stop the pipeline. Run from the repository root after clean.py:

    python src/validate.py              # checks data/grid.db
    python src/validate.py <db_path>    # checks another copy (used by validate_selftest.py)
"""

import sys
from pathlib import Path

import clean_config as cfg
from db import DB_PATH, connect

# Flags whose cleaned value must be NULL (untrusted). Same lists as sql/clean_schema.sql.
DEMAND_NULL_FLAGS = ("missing_not_reported", "invalid_nonpositive", "invalid_dropout", "stuck_value")

# Every value below reaches SQL through a placeholder; the SQL text itself is fixed.
SQL = {
    "demand_rows": "SELECT COUNT(*) FROM demand",
    "demand_clean_rows": "SELECT COUNT(*) FROM demand_clean",
    "weather_rows": "SELECT COUNT(*) FROM weather",
    "weather_clean_rows": "SELECT COUNT(*) FROM weather_clean",
    "demand_nonpositive": "SELECT COUNT(*) FROM demand_clean WHERE value_mwh <= 0",
    "demand_untrusted_kept": "SELECT COUNT(*) FROM demand_clean "
                             "WHERE value_mwh_flag IN (?, ?, ?, ?) AND value_mwh IS NOT NULL",
    "temp_out": "SELECT COUNT(*) FROM weather_clean WHERE temperature_c < ? OR temperature_c > ?",
    "humidity_out": "SELECT COUNT(*) FROM weather_clean "
                    "WHERE relative_humidity_pct < ? OR relative_humidity_pct > ?",
    "precip_out": "SELECT COUNT(*) FROM weather_clean WHERE precipitation_mm < ?",
    "null_share": """
        SELECT r.respondent || ' ' || s.type_code, COUNT(*), SUM(d.value_mwh IS NULL)
        FROM demand_clean d
        JOIN region r ON r.region_key = d.region_key
        JOIN series_type s ON s.type_key = d.type_key
        GROUP BY 1 ORDER BY 1""",
    "latest_demand": """
        SELECT r.respondent, MAX(d.period_utc)
        FROM demand_clean d JOIN region r ON r.region_key = d.region_key
        WHERE d.value_mwh IS NOT NULL
        GROUP BY r.respondent ORDER BY 1""",
    "latest_weather": """
        SELECT l.location_code, MAX(w.observed_at)
        FROM weather_clean w JOIN location l ON l.location_key = w.location_key
        WHERE w.temperature_c IS NOT NULL
        GROUP BY l.location_code ORDER BY 1""",
    "df_vs_d_hours": """
        SELECT r.respondent,
               SUM(m.role = 'actual'), SUM(m.role = 'forecast')
        FROM demand_clean d
        JOIN region r ON r.region_key = d.region_key
        JOIN map_series_type m ON m.type_key = d.type_key
        GROUP BY r.respondent ORDER BY 1""",
    "flag_count": "SELECT COUNT(*) FROM demand_clean WHERE value_mwh_flag = ?",
    "unmapped_locations": "SELECT COUNT(*) FROM location WHERE location_key NOT IN "
                          "(SELECT location_key FROM map_region_location)",
    "unmapped_types": "SELECT COUNT(*) FROM series_type WHERE type_key NOT IN "
                      "(SELECT type_key FROM map_series_type)",
}

results = []


def check(level_if_bad, name, ok, detail):
    status = "PASS" if ok else level_if_bad
    results.append(status)
    print(f"{status:<4}  {name:<52} {detail}")


def one(con, key, params=()):
    return con.execute(SQL[key], params).fetchone()[0]


def run_checks(db_path=DB_PATH):
    con = connect(db_path)
    try:
        # STOP 1-2: same row count as the raw tables (flag, don't delete).
        for table in ("demand", "weather"):
            raw, clean = one(con, f"{table}_rows"), one(con, f"{table}_clean_rows")
            check("STOP", f"{table}_clean row count equals {table}", raw == clean, f"{clean:,} = {raw:,}"
                  if raw == clean else f"{clean:,} != {raw:,}")

        # STOP 3: no impossible value survives in a cleaned column (family 2 rules).
        bad_demand = one(con, "demand_nonpositive")
        check("STOP", "no cleaned demand value <= 0 MWh", bad_demand == 0, f"{bad_demand} found")
        limits = ("TEMP_MIN_C", "TEMP_MAX_C", "HUMIDITY_MIN_PCT", "HUMIDITY_MAX_PCT", "PRECIP_MIN_MM")
        missing = [name for name in limits if not hasattr(cfg, name)]
        if missing:
            check("STOP", "no cleaned weather value outside its valid range", False,
                  "constants missing in clean_config.py: " + ", ".join(missing))
        else:
            bad_weather = (one(con, "temp_out", (cfg.TEMP_MIN_C, cfg.TEMP_MAX_C))
                           + one(con, "humidity_out", (cfg.HUMIDITY_MIN_PCT, cfg.HUMIDITY_MAX_PCT))
                           + one(con, "precip_out", (cfg.PRECIP_MIN_MM,)))
            check("STOP", "no cleaned weather value outside its valid range", bad_weather == 0,
                  f"{bad_weather} found (temp {cfg.TEMP_MIN_C}..{cfg.TEMP_MAX_C} C, "
                  f"humidity {cfg.HUMIDITY_MIN_PCT}..{cfg.HUMIDITY_MAX_PCT} %, precip >= {cfg.PRECIP_MIN_MM} mm)")

        # STOP 4: an untrusted flag always comes with a NULL cleaned value.
        kept = one(con, "demand_untrusted_kept", DEMAND_NULL_FLAGS)
        check("STOP", "untrusted demand flags carry a NULL cleaned value", kept == 0, f"{kept} rows break this")

        # STOP 5: every reference resolves.
        problems = con.execute("PRAGMA foreign_key_check").fetchall()
        check("STOP", "foreign_key_check", not problems, "OK" if not problems else f"{len(problems)} problems")

        # STOP 6: every location and series type has a mapping decision.
        unmapped = one(con, "unmapped_locations") + one(con, "unmapped_types")
        check("STOP", "every location and series type is mapped", unmapped == 0, f"{unmapped} unmapped")

        # WARN 7: missing share per region x series below the chosen threshold.
        over = []
        for entity, total, nulls in con.execute(SQL["null_share"]):
            if total and nulls / total > cfg.WARN_NULL_SHARE:
                over.append(f"{entity} {nulls / total:.2%}")
        check("WARN", f"NULL share at most {cfg.WARN_NULL_SHARE:.0%} per region x series", not over,
              ", ".join(over) if over else "all within")

        # WARN 8: freshness / coverage - every region and location reaches the latest hour we have.
        latest = con.execute(SQL["latest_demand"]).fetchall() + con.execute(SQL["latest_weather"]).fetchall()
        newest = max((t for _, t in latest), default=None)
        behind = [f"{name} {t}" for name, t in latest if t != newest]
        check("WARN", "every region and location has data in the latest hour", not behind,
              f"latest {newest}; " + (", ".join(behind) if behind else f"{len(latest)} of {len(latest)}"))

        # WARN 9 (data-specific): DF should cover every hour that D covers.
        gaps = [f"{r} {a - f}" for r, a, f in con.execute(SQL["df_vs_d_hours"]) if a != f]
        check("WARN", "DF has as many hours as D in every region", not gaps,
              ("hours missing in DF: " + ", ".join(gaps)) if gaps else "equal")

        # WARN 10 (data-specific): no stuck values and no forecast mismatches.
        for flag in ("stuck_value", "forecast_mismatch"):
            n = one(con, "flag_count", (flag,))
            check("WARN", f"no {flag} flags in demand_clean", n == 0, f"{n} rows")
    finally:
        con.close()
    return "STOP" not in results


if __name__ == "__main__":
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else DB_PATH
    ok = run_checks(db)
    stops, warns = results.count("STOP"), results.count("WARN")
    print(f"\n{results.count('PASS')} PASS · {warns} WARN · {stops} STOP")
    sys.exit(0 if ok else 1)
