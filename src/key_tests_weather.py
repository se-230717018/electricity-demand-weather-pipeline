"""Key tests for Open-Meteo raw data.

Reads data/raw/open_meteo only. No API calls, no database.
Run from the repository root: python src/key_tests_weather.py
"""
import json
from pathlib import Path

import pandas as pd

RAW_DIR = Path("data/raw/open_meteo")
EIA_DIR = Path("data/raw/eia")


def read_files(files):
    """Turn each file's parallel arrays into rows; also collect per-file metadata."""
    frames, meta = [], []
    for path in files:
        body = json.loads(path.read_text(encoding="utf-8"))
        code = path.stem.split("_", 1)[1]  # 20261008T093927Z_NYIS -> NYIS
        df = pd.DataFrame(body["hourly"])
        df.insert(0, "location", code)
        frames.append(df)
        meta.append({
            "location": code,
            "file": path.name,
            "utc_offset_seconds": body.get("utc_offset_seconds"),
            "latitude": body.get("latitude"),
            "longitude": body.get("longitude"),
        })
    return pd.concat(frames, ignore_index=True), pd.DataFrame(meta)


def latest_run_files():
    files = sorted(RAW_DIR.glob("*.json"))
    if not files:
        raise SystemExit(f"No files in {RAW_DIR}. Run python src/ingest.py first.")
    latest = max(p.name.split("_", 1)[0] for p in files)
    return latest, [p for p in files if p.name.startswith(latest + "_")], files


def eia_respondents():
    """Region codes from EIA raw files; falls back to EIA_RESPONDENTS in .env."""
    found = set()
    for path in EIA_DIR.glob("*.json"):
        body = json.loads(path.read_text(encoding="utf-8"))
        for row in body.get("response", {}).get("data", []):
            if row.get("respondent"):
                found.add(row["respondent"])
    if found:
        return found, "EIA raw files"
    env = Path(".env")
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("EIA_RESPONDENTS="):
                codes = {c.strip() for c in line.split("=", 1)[1].split(",") if c.strip()}
                return codes, ".env (no EIA raw files found)"
    return set(), "nothing found"


def main():
    run_ts, run_files, all_files = latest_run_files()
    df, meta = read_files(run_files)
    value_cols = [c for c in df.columns if c not in ("location", "time")]

    print(f"Run tested: {run_ts} ({len(run_files)} files, {len(df)} rows)")
    print(df.groupby("location").size().to_string(), "\n")

    # 1. Natural key: (location, time) must be unique within one run
    dup = int(df.duplicated(subset=["location", "time"]).sum())
    print(f"1) Duplicate (location, time) in one run: {dup}  -> {'PASS' if dup == 0 else 'FAIL'}")

    all_df, _ = read_files(all_files)
    dup_all = int(all_df.duplicated(subset=["location", "time"]).sum())
    print(f"   Across all {len(all_files)} files: {dup_all} duplicates "
          "(expected: every run re-downloads the same period; the loader's upsert keeps one)")

    # 2. Every file must be in UTC
    bad_offset = meta[meta["utc_offset_seconds"] != 0]
    print(f"2) Files with utc_offset_seconds != 0: {len(bad_offset)}  -> {'PASS' if bad_offset.empty else 'FAIL'}")
    if not bad_offset.empty:
        print(bad_offset.to_string(index=False))

    # 3. Nulls: how many, and are they only at the end of the period?
    nulls = df[value_cols].isna().sum()
    print("3) Null values per column:")
    print(nulls.to_string())
    null_rows = df[df[value_cols].isna().any(axis=1)]
    if null_rows.empty:
        print("   No nulls at all.")
    else:
        last = pd.to_datetime(df["time"]).max()
        null_times = pd.to_datetime(null_rows["time"])
        at_end = bool((null_times >= last - pd.Timedelta(days=7)).all())
        print(f"   Null rows: {len(null_rows)}, from {null_times.min()} to {null_times.max()}")
        print(f"   All within the last 7 days of the period: {at_end}")

    # 4. Every location code must match an EIA region (future foreign key)
    regions, origin = eia_respondents()
    missing = sorted(set(meta["location"]) - regions)
    print(f"4) Location codes without an EIA region (checked against {origin}): {missing or 'none'}"
          f"  -> {'PASS' if not missing else 'FAIL'}")

    print("\nReturned grid coordinates per location:")
    print(meta[["location", "latitude", "longitude"]].to_string(index=False))


if __name__ == "__main__":
    main()