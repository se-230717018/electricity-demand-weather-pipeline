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


def main() -> None:
    run_ts = utc_timestamp()
    print(f"Ingestion run started at {run_ts}")
    # Sources are added in the next steps (EIA, Open-Meteo).


if __name__ == "__main__":
    main()