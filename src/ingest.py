"""Ingestion script: fetches raw data from EIA and Open-Meteo and lands it in data/raw/.

Run from the repository root:  python src/ingest.py
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
TIMEOUT_SECONDS = 30
MAX_ATTEMPTS = 5
BASE_DELAY_SECONDS = 2


class AuthError(Exception):
    """401/403 - credentials are wrong; never retried."""


class FetchError(Exception):
    """Request failed after all retries, or returned an unusable response."""


def get_env(name: str) -> str:
    """Read a required setting from the environment, or stop with a clear message."""
    value = os.environ.get(name)
    if not value:
        sys.exit(f"ERROR: environment variable {name} is not set. See .env.example.")
    return value


def utc_timestamp() -> str:
    """UTC time as e.g. 20261012T091244Z, used in raw file names."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def http_get(url: str, params: dict | None = None) -> requests.Response:
    """GET with timeout; retries 429/5xx/network errors with exponential backoff."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        delay = BASE_DELAY_SECONDS * 2 ** (attempt - 1)
        try:
            response = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)
        except (requests.Timeout, requests.ConnectionError) as exc:
            reason = f"network error ({exc.__class__.__name__})"
        else:
            status = response.status_code
            if status in (401, 403):
                raise AuthError(f"authentication failed (HTTP {status}) for {url}")
            if status == 429:
                reason = "rate limited (HTTP 429)"
                retry_after = response.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    delay = max(delay, int(retry_after))
            elif status >= 500:
                reason = f"server error (HTTP {status})"
            elif status >= 400:
                raise FetchError(f"HTTP {status} for {url}")
            else:
                return response

        if attempt == MAX_ATTEMPTS:
            raise FetchError(f"giving up after {MAX_ATTEMPTS} attempts: {reason} for {url}")
        print(f"  attempt {attempt} failed: {reason}; retrying in {delay}s")
        time.sleep(delay)


def save_raw(source: str, run_ts: str, content: bytes, suffix: str = "", ext: str = "json") -> Path:
    """Write the response bytes unmodified. Mode 'xb' refuses to overwrite an existing file."""
    folder = RAW_DIR / source
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{run_ts}{suffix}.{ext}"
    with open(path, "xb") as f:
        f.write(content)
    return path


OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"


def parse_locations(raw: str) -> list[tuple[str, str, str]]:
    """'NYIS:40.71:-74.01,ERCO:...' -> [('NYIS', '40.71', '-74.01'), ...]"""
    locations = []
    for item in raw.split(","):
        parts = item.strip().split(":")
        if len(parts) != 3:
            sys.exit(f"ERROR: bad entry in OPENMETEO_LOCATIONS: '{item}' (expected CODE:LAT:LON)")
        locations.append((parts[0], parts[1], parts[2]))
    return locations


OPEN_METEO_OVERLAP_DAYS = 10        # re-fetch the last 10 days every run; values older than 8 days never changed between our Oct 8 and Oct 24 retrievals, and ERA5 lags ~6 days (docs/pipeline.md)
OPEN_METEO_MAX_CATCHUP_DAYS = 3650  # at most ~10 years per run; a longer outage is caught up over several runs


def parse_run_time(text: str | None) -> datetime:
    """'2026-11-20T08:10Z' -> UTC datetime; None -> now."""
    if text is None:
        return datetime.now(timezone.utc)
    return datetime.strptime(text, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)


def last_open_meteo_hour(code: str) -> datetime | None:
    """Latest hour with a value in the newest landed file for this location; None if nothing landed yet."""
    files = sorted((RAW_DIR / "open_meteo").glob(f"*_{code}.json"))  # names start with the UTC timestamp
    if not files:
        return None
    hourly = json.loads(files[-1].read_text(encoding="utf-8")).get("hourly", {})
    times = [t for t, v in zip(hourly.get("time", []), hourly.get("temperature_2m", [])) if v is not None]
    if not times:
        return None
    return datetime.strptime(max(times), "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)


def open_meteo_window(code: str, run_time: datetime) -> tuple[str, str]:
    """Dates to request: from the last landed hour minus the overlap, up to the day before the run time.

    The day of the run time is never requested: the archive fills it with forecast values,
    including hours after the run time, and raw responses are saved unmodified.
    """
    end = (run_time - timedelta(days=1)).date()
    last = last_open_meteo_hour(code)
    if last is None:
        start = datetime.strptime(get_env("START_DATE"), "%Y-%m-%d").date()
    else:
        start = (last - timedelta(days=OPEN_METEO_OVERLAP_DAYS)).date()
    start = min(start, end)
    if (end - start).days > OPEN_METEO_MAX_CATCHUP_DAYS:
        end = start + timedelta(days=OPEN_METEO_MAX_CATCHUP_DAYS)
    return start.isoformat(), end.isoformat()


def fetch_open_meteo(run_ts: str, run_time: datetime) -> dict:
    """One request per representative location for its own window; each response is saved unmodified."""
    hourly = get_env("OPENMETEO_HOURLY")
    files, records, failures = 0, 0, []

    for code, lat, lon in parse_locations(get_env("OPENMETEO_LOCATIONS")):
        start, end = open_meteo_window(code, run_time)
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start,
            "end_date": end,
            "hourly": hourly,
            "timezone": "GMT",  # UTC, so hours line up with EIA
        }
        print(f"  Open-Meteo {code}: requesting {start} .. {end}")
        try:
            response = http_get(OPEN_METEO_URL, params)
            body = response.json()  # also checks that we really received JSON
            times = body.get("hourly", {}).get("time", [])
            if not times:
                raise FetchError("empty or unexpected response (no hourly data)")
        except (FetchError, ValueError) as exc:
            failures.append(f"{code}: {exc}")
            print(f"  Open-Meteo {code}: FAILED - {exc}")
            continue

        path = save_raw("open_meteo", run_ts, response.content, suffix=f"_{code}")
        files += 1
        records += len(times)
        print(f"  Open-Meteo {code}: {len(times)} hourly records -> {path.relative_to(RAW_DIR.parent.parent)}")

    return {"source": "Open-Meteo", "files": files, "records": records, "failures": failures}


EIA_URL = "https://api.eia.gov/v2/electricity/rto/region-data/data/"
EIA_PAGE_SIZE = 5000  # EIA's maximum rows per request
EIA_PERIOD_FMT = "%Y-%m-%dT%H"  # EIA hourly period, UTC, e.g. 2026-11-20T08
EIA_OVERLAP_HOURS = 48  # re-fetch the last 48 hours every run, so late-published hours are picked up


def last_eia_hour(resp: str) -> datetime | None:
    """Latest hour with a demand (D) value in the newest landed run for this region; None if nothing landed yet."""
    files = sorted((RAW_DIR / "eia").glob(f"*_{resp}_page*.json"))  # names start with the UTC timestamp
    if not files:
        return None
    newest_run = files[-1].name.split("_")[0]
    periods = []
    for path in files:
        if not path.name.startswith(newest_run + "_"):
            continue
        rows = json.loads(path.read_text(encoding="utf-8")).get("response", {}).get("data") or []
        periods += [r["period"] for r in rows if r.get("type") == "D" and r.get("value") is not None]
    if not periods:
        return None
    return datetime.strptime(max(periods), EIA_PERIOD_FMT).replace(tzinfo=timezone.utc)


def eia_window(resp: str, run_time: datetime) -> tuple[str, str, bool]:
    """Hours to request: from the last landed hour minus the overlap, up to the hour of the run time.

    Returns (start, end, incremental); incremental is False on the first run (full history from START_DATE).
    """
    end = run_time.replace(minute=0, second=0, microsecond=0)
    last = last_eia_hour(resp)
    if last is None:
        start = datetime.strptime(get_env("START_DATE"), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        start = last - timedelta(hours=EIA_OVERLAP_HOURS)
    start = min(start, end)
    return start.strftime(EIA_PERIOD_FMT), end.strftime(EIA_PERIOD_FMT), last is not None


def fetch_eia(run_ts: str, run_time: datetime) -> dict:
    """All pages of hourly demand (D) and day-ahead forecast (DF), one region at a time, each for its own window."""
    api_key = get_env("EIA_API_KEY")
    respondents = [r.strip() for r in get_env("EIA_RESPONDENTS").split(",")]
    files, records, failures = 0, 0, []

    for resp in respondents:
        start, end, incremental = eia_window(resp, run_time)
        print(f"  EIA {resp}: requesting {start} .. {end}")
        offset, page, total = 0, 1, None
        try:
            while total is None or offset < total:
                params = {
                    "api_key": api_key,
                    "frequency": "hourly",
                    "data[0]": "value",
                    "facets[respondent][]": resp,
                    "facets[type][]": ["D", "DF"],
                    "start": start,
                    "end": end,
                    "sort[0][column]": "period",
                    "sort[0][direction]": "asc",
                    "sort[1][column]": "type",
                    "sort[1][direction]": "asc",
                    "offset": offset,
                    "length": EIA_PAGE_SIZE,
                }
                response = http_get(EIA_URL, params)
                body = response.json()
                rows = body.get("response", {}).get("data")
                if total is None:
                    total = int(body.get("response", {}).get("total", 0))
                    if total == 0:
                        if incremental:  # nothing new published yet in this window; not an error
                            break
                        raise FetchError("EIA reports 0 records for this query")
                if not rows:
                    raise FetchError(f"empty page at offset {offset} (expected {total} records)")

                save_raw("eia", run_ts, response.content, suffix=f"_{resp}_page{page:03d}")
                files += 1
                records += len(rows)
                offset += len(rows)
                page += 1
            print(f"  EIA {resp}: {offset} records in {page - 1} pages")
        except (FetchError, ValueError) as exc:
            failures.append(f"{resp}: {exc}")
            print(f"  EIA {resp}: FAILED after {page - 1} pages - {exc}")

    return {"source": "EIA", "files": files, "records": records, "failures": failures}


def main() -> None:
    parser = argparse.ArgumentParser(description="Land raw EIA and Open-Meteo data in data/raw/.")
    parser.add_argument("--run-time", help="pipeline clock, e.g. 2026-11-20T08:10Z (default: now, UTC)")
    args = parser.parse_args()
    run_time = parse_run_time(args.run_time)

    run_ts = utc_timestamp()  # wall clock: the real retrieval time, used in file names and retrieved_at
    print(f"Ingestion run started at {run_ts} (run time {run_time:%Y-%m-%dT%H:%MZ})")
    results = [fetch_eia(run_ts, run_time), fetch_open_meteo(run_ts, run_time)]
    print("\nRun summary")
    for r in results:
        status = "OK" if not r["failures"] else f"{len(r['failures'])} FAILED"
        print(f"  {r['source']}: {r['files']} files, {r['records']} records - {status}")

    if any(r["failures"] for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()