"""Load Open-Meteo raw files into the location, weather and quarantine tables.
"""
import json

from db import to_number, to_utc_hour

SOURCE = "open_meteo"

# Open-Meteo variables, in the same order as the weather columns in UPSERT_WEATHER
VARIABLES = ["temperature_2m", "relative_humidity_2m", "precipitation"]

UPSERT_LOCATION = """
INSERT INTO location (location_code, region_key, latitude, longitude, elevation_m, retrieved_at, source_file)
VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (location_code) DO UPDATE SET
    region_key   = excluded.region_key,
    latitude     = excluded.latitude,
    longitude    = excluded.longitude,
    elevation_m  = excluded.elevation_m,
    retrieved_at = excluded.retrieved_at,
    source_file  = excluded.source_file
WHERE excluded.retrieved_at >= location.retrieved_at
"""

UPSERT_WEATHER = """
INSERT INTO weather (location_key, observed_at, temperature_c, relative_humidity_pct, precipitation_mm,
                     retrieved_at, source_file)
VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (location_key, observed_at) DO UPDATE SET
    temperature_c         = excluded.temperature_c,
    relative_humidity_pct = excluded.relative_humidity_pct,
    precipitation_mm      = excluded.precipitation_mm,
    retrieved_at          = excluded.retrieved_at,
    source_file           = excluded.source_file
WHERE excluded.retrieved_at >= weather.retrieved_at
"""

INSERT_QUARANTINE = """
INSERT INTO quarantine (source, source_file, record_ref, reason, raw_record, retrieved_at)
VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT (source, source_file, record_ref) DO NOTHING
"""


def _quarantine(con, path, record_ref, reason, raw, retrieved_at):
    con.execute(INSERT_QUARANTINE, (SOURCE, path.name, record_ref, reason, json.dumps(raw), retrieved_at))


def _value(raw_value):
    """(number or None, cleaned?). An Open-Meteo null means 'not in the archive yet' -> NULL, counted."""
    if raw_value is None:
        return None, True
    return to_number(raw_value)


def load_weather(con, files):
    """files: [(Path, retrieved_at), ...] sorted oldest -> newest. Returns a summary dict."""
    summary = {"files": 0, "values_cleaned": 0, "quarantined": 0}

    for path, retrieved_at in files:
        # File-level problems raise on purpose: load.py then rolls back everything
        body = json.loads(path.read_text(encoding="utf-8"))
        code = path.stem.split("_", 1)[1]  # 20261008T093927Z_NYIS -> NYIS
        hourly = body["hourly"]
        times = hourly["time"]
        columns = [hourly[name] for name in VARIABLES]
        if any(len(col) != len(times) for col in columns):
            raise ValueError(f"{path.name}: hourly arrays have different lengths")
        summary["files"] += 1

        location_meta = {
            "location_code": code,
            "latitude": body.get("latitude"),
            "longitude": body.get("longitude"),
            "elevation": body.get("elevation"),
            "utc_offset_seconds": body.get("utc_offset_seconds"),
            "hours_in_file": len(times),
        }

        # 1) Hours must be UTC, otherwise they would not line up with EIA
        if body.get("utc_offset_seconds") != 0:
            _quarantine(con, path, f"{code}|file", "not UTC", location_meta, retrieved_at)
            summary["quarantined"] += 1
            continue

        # 2) The location must belong to a known region (foreign key)
        row = con.execute("SELECT region_key FROM region WHERE respondent = ?", (code,)).fetchone()
        if row is None:
            _quarantine(con, path, f"{code}|file", "unknown region", location_meta, retrieved_at)
            summary["quarantined"] += 1
            continue
        region_key = row[0]

        # 3) Location: one row per code, latest retrieval wins
        con.execute(UPSERT_LOCATION, (code, region_key, body.get("latitude"), body.get("longitude"),
                                      body.get("elevation"), retrieved_at, path.name))
        location_key = con.execute(
            "SELECT location_key FROM location WHERE location_code = ?", (code,)
        ).fetchone()[0]

        # 4) Weather: parallel arrays -> one row per hour
        rows = []
        for i, raw_time in enumerate(times):
            observed_at = to_utc_hour(raw_time)
            if observed_at is None:
                raw = {"time": raw_time, **{name: hourly[name][i] for name in VARIABLES}}
                _quarantine(con, path, f"{code}|{raw_time}", "unparseable time", raw, retrieved_at)
                summary["quarantined"] += 1
                continue
            values = []
            for col in columns:
                number, cleaned = _value(col[i])
                values.append(number)
                summary["values_cleaned"] += int(cleaned)
            rows.append((location_key, observed_at, *values, retrieved_at, path.name))

        con.executemany(UPSERT_WEATHER, rows)

    return summary