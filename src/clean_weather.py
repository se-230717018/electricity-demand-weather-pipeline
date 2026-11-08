"""Build weather_clean from the M2 weather table (M3).

Reads M2 tables with SELECT only. Does not open, commit or roll back the
connection: clean.py owns the transaction.

Every weather row goes into weather_clean exactly once (same primary key).
Each of the three variables gets its own raw / cleaned / flag columns.
Flag order per variable - the first rule that matches wins (see docs/cleaning_report.md):
  1 missing_not_reported  raw value is NULL                                -> NULL
  2 invalid_out_of_range  outside the physical range in clean_config        -> NULL
  3 stuck_value           same value for >= WEATHER_STUCK_RUN_HOURS hours   -> NULL
  4 spike                 |change from the previous hour| > threshold       -> NULL
  5 unusual_high / _low   |robust z| > WEATHER_ROBUST_Z_UNUSUAL              -> kept
  6 ok                                                                     -> kept
Which rules apply to which variable is set in VARIABLE_RULES below.
Median and MAD are computed per location x variable, after rules 1-4.
No imputation: an untrusted value stays NULL.
"""

from datetime import datetime, timedelta
from statistics import median

from clean_config import (
    HUMIDITY_MAX_PCT,
    HUMIDITY_MIN_PCT,
    PRECIP_MIN_MM,
    ROBUST_Z_SCALE,
    TEMP_MAX_C,
    TEMP_MIN_C,
    TEMP_SPIKE_C_PER_HOUR,
    WEATHER_ROBUST_Z_UNUSUAL,
    WEATHER_STUCK_RUN_HOURS,
)

NULL_FLAGS = ("missing_not_reported", "invalid_out_of_range", "stuck_value", "spike")
ONE_HOUR = timedelta(hours=1)
TIME_FORMAT = "%Y-%m-%dT%H:%MZ"

# column: (minimum, maximum, check stuck?, spike threshold or None, check unusual?)
# - humidity: no spike rule (it moves with rain and fog by design), stuck rule kept
# - precipitation: zero for many hours is normal (no stuck rule), and MAD = 0 (no robust z)
VARIABLE_RULES = {
    "temperature_c": (TEMP_MIN_C, TEMP_MAX_C, True, TEMP_SPIKE_C_PER_HOUR, True),
    "relative_humidity_pct": (HUMIDITY_MIN_PCT, HUMIDITY_MAX_PCT, True, None, True),
    "precipitation_mm": (PRECIP_MIN_MM, None, False, None, False),
}
COLUMNS = list(VARIABLE_RULES)

READ_SQL = """
SELECT w.location_key, l.location_code, w.observed_at,
       w.temperature_c, w.relative_humidity_pct, w.precipitation_mm
FROM weather w
JOIN location l ON l.location_key = w.location_key
ORDER BY w.location_key, w.observed_at
"""

INSERT_SQL = """
INSERT INTO weather_clean (
    location_key, observed_at,
    temperature_c_raw, temperature_c, temperature_c_flag,
    relative_humidity_pct_raw, relative_humidity_pct, relative_humidity_pct_flag,
    precipitation_mm_raw, precipitation_mm, precipitation_mm_flag)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def _read_locations(con):
    """Group the M2 rows by location; each location is in time order."""
    locations = {}
    for location_key, code, observed_at, *values in con.execute(READ_SQL):
        loc = locations.setdefault(location_key, {"code": code, "times": [], "observed_at": [],
                                                  "values": {c: [] for c in COLUMNS}})
        loc["observed_at"].append(observed_at)
        loc["times"].append(datetime.strptime(observed_at, TIME_FORMAT))
        for column, value in zip(COLUMNS, values):
            loc["values"][column].append(value)
    return locations


def _flag_range(values, flags, minimum, maximum):
    """Rules 1-2: missing and physically impossible values."""
    for i, value in enumerate(values):
        if value is None:
            flags[i] = "missing_not_reported"
        elif (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
            flags[i] = "invalid_out_of_range"


def _flag_stuck(times, values, flags):
    """Rule 3: the same value in WEATHER_STUCK_RUN_HOURS or more consecutive hours.

    A run breaks on a different value, a NULL value or a missing hour.
    Rows already flagged by rules 1-2 keep their earlier flag.
    """
    start = 0
    for i in range(1, len(values) + 1):
        continues = (
            i < len(values)
            and values[i] is not None
            and values[i] == values[i - 1]
            and times[i] - times[i - 1] == ONE_HOUR
        )
        if not continues:
            if values[start] is not None and i - start >= WEATHER_STUCK_RUN_HOURS:
                for j in range(start, i):
                    if flags[j] is None:
                        flags[j] = "stuck_value"
            start = i


def _flag_spike(times, values, flags, threshold):
    """Rule 4: |value - previous hour's value| > threshold flags the later hour.

    Only compared when both hours are consecutive and both are still trusted.
    """
    for i in range(1, len(values)):
        if flags[i] is not None or flags[i - 1] is not None:
            continue
        if times[i] - times[i - 1] != ONE_HOUR:
            continue
        if abs(values[i] - values[i - 1]) > threshold:
            flags[i] = "spike"


def _flag_unusual(values, flags):
    """Rule 5: robust z = ROBUST_Z_SCALE * (x - median) / MAD, after rules 1-4."""
    trusted = [v for v, f in zip(values, flags) if f is None]
    if not trusted:
        return
    centre = median(trusted)
    mad = median(abs(v - centre) for v in trusted)
    if mad == 0:
        return  # no spread: robust z is undefined, nothing is flagged
    for i, value in enumerate(values):
        if flags[i] is not None:
            continue
        z = ROBUST_Z_SCALE * (value - centre) / mad
        if z > WEATHER_ROBUST_Z_UNUSUAL:
            flags[i] = "unusual_high"
        elif z < -WEATHER_ROBUST_Z_UNUSUAL:
            flags[i] = "unusual_low"


def _flag_variable(times, values, rules):
    minimum, maximum, check_stuck, spike_threshold, check_unusual = rules
    flags = [None] * len(values)
    _flag_range(values, flags, minimum, maximum)
    if check_stuck:
        _flag_stuck(times, values, flags)
    if spike_threshold is not None:
        _flag_spike(times, values, flags, spike_threshold)
    if check_unusual:
        _flag_unusual(values, flags)
    return [flag or "ok" for flag in flags]


def clean_weather(con):
    locations = _read_locations(con)

    params = []
    summary = {}
    for location_key, loc in locations.items():
        flags_by_column = {
            column: _flag_variable(loc["times"], loc["values"][column], rules)
            for column, rules in VARIABLE_RULES.items()
        }
        counts = summary.setdefault(loc["code"], {c: {} for c in COLUMNS})
        for i, observed_at in enumerate(loc["observed_at"]):
            row = [location_key, observed_at]
            for column in COLUMNS:
                raw = loc["values"][column][i]
                flag = flags_by_column[column][i]
                cleaned = None if flag in NULL_FLAGS else raw
                row += [raw, cleaned, flag]
                counts[column][flag] = counts[column].get(flag, 0) + 1
            params.append(tuple(row))
    con.executemany(INSERT_SQL, params)

    rows = con.execute("SELECT COUNT(*) FROM weather_clean").fetchone()[0]
    raw_rows = con.execute("SELECT COUNT(*) FROM weather").fetchone()[0]
    return {"table": "weather_clean", "rows": rows, "raw_rows": raw_rows, "flags": summary}