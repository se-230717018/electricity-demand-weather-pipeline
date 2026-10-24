"""Load EIA hourly demand files into region, series_type and demand.

Contract (M2 plan, section 4):
- Uses the connection it is given; never commits, rolls back or starts a
  transaction. load.py wraps the whole load in one `with con:`, so any error
  undoes everything (atomic).
- A file that cannot be read, or has no response.data list, raises an error.
- A value that is not a number becomes NULL and is counted (values_cleaned).
- A record with a missing or unparseable key goes to quarantine.
- Values reach SQL only through ? placeholders.
- Upserts: the row with the newest retrieved_at wins.
"""
import json
from pathlib import Path

from db import to_number, to_utc_hour

SOURCE = "eia"

UPSERT_REGION = """
INSERT INTO region (respondent, respondent_name, retrieved_at, source_file)
VALUES (?, ?, ?, ?)
ON CONFLICT (respondent) DO UPDATE SET
    respondent_name = excluded.respondent_name,
    retrieved_at    = excluded.retrieved_at,
    source_file     = excluded.source_file
WHERE excluded.retrieved_at >= region.retrieved_at
"""

UPSERT_TYPE = """
INSERT INTO series_type (type_code, type_name, retrieved_at, source_file)
VALUES (?, ?, ?, ?)
ON CONFLICT (type_code) DO UPDATE SET
    type_name    = excluded.type_name,
    retrieved_at = excluded.retrieved_at,
    source_file  = excluded.source_file
WHERE excluded.retrieved_at >= series_type.retrieved_at
"""

UPSERT_DEMAND = """
INSERT INTO demand (region_key, type_key, period_utc, value_mwh, retrieved_at, source_file)
VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT (region_key, type_key, period_utc) DO UPDATE SET
    value_mwh    = excluded.value_mwh,
    retrieved_at = excluded.retrieved_at,
    source_file  = excluded.source_file
WHERE excluded.retrieved_at >= demand.retrieved_at
"""

INSERT_QUARANTINE = """
INSERT INTO quarantine (source, source_file, record_ref, reason, raw_record, retrieved_at)
VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT (source, source_file, record_ref) DO NOTHING
"""

SELECT_REGION_KEY = "SELECT region_key FROM region WHERE respondent = ?"
SELECT_TYPE_KEY = "SELECT type_key FROM series_type WHERE type_code = ?"


def _read_records(path):
    """Return the list of records in one EIA file; raise if the file is unusable."""
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)  # broken JSON raises here, on purpose
    response = payload.get("response") if isinstance(payload, dict) else None
    data = response.get("data") if isinstance(response, dict) else None
    if not isinstance(data, list):
        raise ValueError(f"{Path(path).name}: no response.data list")
    return data


def _text(record, field):
    """Stripped non-empty string, or None."""
    value = record.get(field)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def load_eia(con, files):
    """files: [(Path, retrieved_at), ...] sorted oldest to newest."""
    summary = {"files": 0, "values_cleaned": 0, "quarantined": 0}

    for path, retrieved_at in files:
        path = Path(path)
        source_file = path.name
        records = _read_records(path)

        regions, types, rows, bad = {}, {}, [], []
        for i, rec in enumerate(records):
            if not isinstance(rec, dict):
                bad.append((f"#{i}", "record is not an object", rec))
                continue

            respondent = _text(rec, "respondent")
            type_code = _text(rec, "type")
            period_raw = rec.get("period")
            period = to_utc_hour(period_raw)
            ref = f"{respondent}|{type_code}|{period_raw}|#{i}"

            if respondent is None:
                bad.append((ref, "missing respondent", rec))
                continue
            if type_code is None:
                bad.append((ref, "missing type", rec))
                continue
            if period is None:
                bad.append((ref, "missing or unparseable period", rec))
                continue

            regions[respondent] = _text(rec, "respondent-name")
            types[type_code] = _text(rec, "type-name")

            value, cleaned = to_number(rec.get("value"))
            if cleaned:
                summary["values_cleaned"] += 1
            rows.append((respondent, type_code, period, value))

        # 1) entities first, so demand rows can point at them
        con.executemany(UPSERT_REGION,
                        [(r, name, retrieved_at, source_file) for r, name in regions.items()])
        con.executemany(UPSERT_TYPE,
                        [(t, name, retrieved_at, source_file) for t, name in types.items()])

        region_keys = {r: con.execute(SELECT_REGION_KEY, (r,)).fetchone()[0] for r in regions}
        type_keys = {t: con.execute(SELECT_TYPE_KEY, (t,)).fetchone()[0] for t in types}

        # 2) events
        con.executemany(UPSERT_DEMAND,
                        [(region_keys[r], type_keys[t], p, v, retrieved_at, source_file)
                         for r, t, p, v in rows])

        # 3) records we could not load
        con.executemany(INSERT_QUARANTINE,
                        [(SOURCE, source_file, ref, reason,
                          json.dumps(rec, ensure_ascii=False, sort_keys=True), retrieved_at)
                         for ref, reason, rec in bad])

        summary["files"] += 1
        summary["quarantined"] += len(bad)

    return summary