"""Build demand_clean from the M2 demand table (M3).

Reads M2 tables with SELECT only. Does not open, commit or roll back the
connection: clean.py owns the transaction.

Every demand row goes into demand_clean exactly once (same primary key).
Flag order - the first rule that matches wins (see docs/cleaning_report.md):
  1 missing_not_reported  raw value is NULL                          -> NULL
  2 invalid_nonpositive   value <= 0 MWh                             -> NULL
  3 invalid_dropout       value < DROPOUT_FRACTION x series median   -> NULL
  4 stuck_value           same value for >= STUCK_RUN_HOURS hours    -> NULL
  5 forecast_mismatch     forecast rows only: DF / D out of range    -> kept
  6 unusual_high / _low   |robust z| > ROBUST_Z_UNUSUAL               -> kept
  7 ok                                                               -> kept
Median and MAD are computed per region x series, after rules 1-4.
No imputation: an untrusted value stays NULL.
"""

from datetime import datetime, timedelta
from statistics import median

from clean_config import (
    DF_D_RATIO_MAX,
    DF_D_RATIO_MIN,
    DROPOUT_FRACTION,
    ROBUST_Z_SCALE,
    ROBUST_Z_UNUSUAL,
    STUCK_RUN_HOURS,
)

NULL_FLAGS = ("missing_not_reported", "invalid_nonpositive", "invalid_dropout", "stuck_value")
ONE_HOUR = timedelta(hours=1)
TIME_FORMAT = "%Y-%m-%dT%H:%MZ"

READ_SQL = """
SELECT d.region_key, d.type_key, d.period_utc, d.value_mwh, r.respondent, m.role
FROM demand d
JOIN region r ON r.region_key = d.region_key
LEFT JOIN map_series_type m ON m.type_key = d.type_key
ORDER BY d.region_key, d.type_key, d.period_utc
"""

INSERT_SQL = """
INSERT INTO demand_clean (region_key, type_key, period_utc, value_mwh_raw, value_mwh, value_mwh_flag)
VALUES (?, ?, ?, ?, ?, ?)
"""


def _read_series(con):
    """Group the M2 rows by (region_key, type_key); each series is in time order."""
    series = {}
    for region_key, type_key, period, value, respondent, role in con.execute(READ_SQL):
        if role is None:
            raise ValueError(
                f"series type key {type_key} has no role - add it to data/mappings/series_type_role.csv"
            )
        key = (region_key, type_key)
        if key not in series:
            series[key] = {"respondent": respondent, "role": role, "rows": []}
        series[key]["rows"].append([period, value, None])  # [period_utc, raw value, flag]
    return series


def _flag_invalid(rows):
    """Rules 1-3: missing, non-positive and dropout values."""
    positives = [value for _, value, _ in rows if value is not None and value > 0]
    dropout_limit = DROPOUT_FRACTION * median(positives) if positives else 0.0
    for row in rows:
        value = row[1]
        if value is None:
            row[2] = "missing_not_reported"
        elif value <= 0:
            row[2] = "invalid_nonpositive"
        elif value < dropout_limit:
            row[2] = "invalid_dropout"


def _flag_stuck(rows):
    """Rule 4: the same value in STUCK_RUN_HOURS or more consecutive hours.

    A run breaks on a different value, a NULL value or a missing hour.
    Rows already flagged by rules 1-3 keep their earlier flag.
    """
    run = []
    previous_value, previous_time = None, None
    for row in rows + [[None, None, None]]:  # sentinel closes the last run
        value = row[1]
        time = datetime.strptime(row[0], TIME_FORMAT) if row[0] is not None else None
        continues = (
            value is not None
            and value == previous_value
            and time is not None
            and previous_time is not None
            and time - previous_time == ONE_HOUR
        )
        if not continues:
            if len(run) >= STUCK_RUN_HOURS:
                for stuck_row in run:
                    if stuck_row[2] is None:
                        stuck_row[2] = "stuck_value"
            run = []
        if value is not None:
            run.append(row)
        previous_value, previous_time = value, time


def _flag_forecast_mismatch(rows, actual_by_hour):
    """Rule 5 (forecast series only): DF / D outside [DF_D_RATIO_MIN, DF_D_RATIO_MAX].

    Only compared where the actual value for the same hour is trusted.
    """
    for row in rows:
        if row[2] is not None:
            continue
        actual = actual_by_hour.get(row[0])
        if actual is None:
            continue
        ratio = row[1] / actual
        if ratio < DF_D_RATIO_MIN or ratio > DF_D_RATIO_MAX:
            row[2] = "forecast_mismatch"


def _flag_unusual(rows):
    """Rule 6: robust z = ROBUST_Z_SCALE * (x - median) / MAD, after rules 1-4."""
    trusted = [value for _, value, flag in rows if flag not in NULL_FLAGS]
    if not trusted:
        return
    centre = median(trusted)
    mad = median(abs(value - centre) for value in trusted)
    if mad == 0:
        return  # no spread: robust z is undefined, nothing is flagged
    for row in rows:
        if row[2] is not None:
            continue
        z = ROBUST_Z_SCALE * (row[1] - centre) / mad
        if z > ROBUST_Z_UNUSUAL:
            row[2] = "unusual_high"
        elif z < -ROBUST_Z_UNUSUAL:
            row[2] = "unusual_low"


def clean_demand(con):
    series = _read_series(con)

    # Actual series first: forecast rows are compared with the cleaned actual values.
    order = sorted(series, key=lambda key: (series[key]["role"] != "actual", key))
    trusted_actuals = {}  # region_key -> {period_utc: trusted actual value}

    for key in order:
        region_key, _ = key
        rows = series[key]["rows"]
        _flag_invalid(rows)
        _flag_stuck(rows)
        if series[key]["role"] == "forecast":
            _flag_forecast_mismatch(rows, trusted_actuals.get(region_key, {}))
        _flag_unusual(rows)
        for row in rows:
            if row[2] is None:
                row[2] = "ok"
        if series[key]["role"] == "actual":
            trusted_actuals[region_key] = {
                period: value for period, value, flag in rows if flag not in NULL_FLAGS
            }

    params = []
    flags = {}
    for key in order:
        region_key, type_key = key
        respondent = series[key]["respondent"]
        counts = flags.setdefault(respondent, {})
        for period, value, flag in series[key]["rows"]:
            cleaned = None if flag in NULL_FLAGS else value
            params.append((region_key, type_key, period, value, cleaned, flag))
            counts[flag] = counts.get(flag, 0) + 1
    con.executemany(INSERT_SQL, params)

    rows = con.execute("SELECT COUNT(*) FROM demand_clean").fetchone()[0]
    raw_rows = con.execute("SELECT COUNT(*) FROM demand").fetchone()[0]
    return {"table": "demand_clean", "rows": rows, "raw_rows": raw_rows, "flags": flags}