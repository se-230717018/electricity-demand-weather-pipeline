"""Ingestion script: fetches raw data from EIA and Open-Meteo and lands it in data/raw/.

Run from the repository root:  python src/ingest.py
"""

import os
import sys
import time
from datetime import datetime, timezone
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


def fetch_open_meteo(run_ts: str) -> dict:
    """One request per representative location; each response is saved unmodified."""
    start = get_env("START_DATE")
    end = get_env("END_DATE")
    hourly = get_env("OPENMETEO_HOURLY")
    files, records, failures = 0, 0, []

    for code, lat, lon in parse_locations(get_env("OPENMETEO_LOCATIONS")):
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start,
            "end_date": end,
            "hourly": hourly,
            "timezone": "GMT",  # UTC, so hours line up with EIA
        }
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


def main() -> None:
    run_ts = utc_timestamp()
    print(f"Ingestion run started at {run_ts}")
    results = [fetch_open_meteo(run_ts)]
    print("\nRun summary")
    for r in results:
        status = "OK" if not r["failures"] else f"{len(r['failures'])} FAILED"
        print(f"  {r['source']}: {r['files']} files, {r['records']} records - {status}")







if __name__ == "__main__":
    main()