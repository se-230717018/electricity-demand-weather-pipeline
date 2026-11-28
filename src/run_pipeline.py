"""Run the whole pipeline once: ingest -> load -> clean -> validate (Milestone M5).

Each step runs as its own process. The runner stops at the first step that fails and
exits with that step's code, so a scheduler (Task Scheduler / cron) sees the failure.

    python src/run_pipeline.py                                # fetch, load, clean, validate
    python src/run_pipeline.py --skip-ingest                  # rebuild from landed raw data only
    python src/run_pipeline.py --run-time 2026-11-20T08:10Z   # pipeline clock (default: now, UTC)

Exit codes: 0 success · the failed step's own code (usually 1) · 75 another run is in progress ·
124 a step timed out · 2 bad command-line arguments.

Every step that ran is recorded in data/pipeline_log.db (table pipeline_run), which is kept
outside the main database so a rebuild can never delete the run history.
"""

import argparse
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_DB = ROOT / "data" / "pipeline_log.db"
LOCK_PATH = ROOT / "data" / "pipeline.lock"

# (script, timeout in seconds, accepts --run-time). Timeouts are about 5x the slowest run we have seen,
# so a slow network does not fail the run but a hung step is stopped well before the next scheduled run.
STEPS = [
    ("src/ingest.py", 1800, True),
    ("src/load.py", 1800, False),
    ("src/clean.py", 1800, False),
    ("src/validate.py", 600, False),
]
TIMEOUT_EXIT = 124      # same convention as the Unix `timeout` command
LOCKED_EXIT = 75        # EX_TEMPFAIL: try again later
STALE_LOCK_SECONDS = 2 * 3600  # longer than all timeouts together (6000 s): a lock this old was left by a crash or power loss
DETAIL_MAX = 300        # characters of each step's last output line kept in the log

LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS pipeline_run (
    run_id      TEXT NOT NULL,     -- one per run
    run_time    TEXT NOT NULL,     -- the pipeline's clock, ISO 8601 UTC
    step        TEXT NOT NULL,     -- e.g. 'src/load.py'
    started_at  TEXT NOT NULL,     -- wall clock, ISO 8601 UTC
    finished_at TEXT NOT NULL,
    exit_code   INTEGER NOT NULL,
    detail      TEXT,              -- last line the step printed (its summary), or 'timeout'
    PRIMARY KEY (run_id, step)
) STRICT;
"""
INSERT_RUN = """
INSERT INTO pipeline_run (run_id, run_time, step, started_at, finished_at, exit_code, detail)
VALUES (?, ?, ?, ?, ?, ?, ?)
"""


def wall_clock() -> str:
    """Wall-clock time for log timestamps only; never used for a data decision."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_time_arg(text: str) -> str:
    """argparse type for --run-time: must look like 2026-11-20T08:10Z."""
    try:
        datetime.strptime(text, "%Y-%m-%dT%H:%MZ")
    except ValueError:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DDTHH:MMZ, e.g. 2026-11-20T08:10Z") from None
    return text


def log_step(run_id, run_time, step, started, finished, code, detail):
    """Write one row to the run log; its own short transaction, so a later crash cannot lose it."""
    LOG_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(LOG_DB)
    try:
        con.executescript(LOG_SCHEMA)
        with con:
            con.execute(INSERT_RUN, (run_id, run_time, step, started, finished, code, detail))
    finally:
        con.close()


def last_line(text: str) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    return lines[-1][:DETAIL_MAX] if lines else ""


def run_step(script, timeout, takes_run_time, run_time):
    """Run one step as a separate process. Returns (exit_code, detail)."""
    cmd = [sys.executable, script]
    if takes_run_time:
        cmd += ["--run-time", run_time]
    try:
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        print(out, end="")
        return TIMEOUT_EXIT, f"timeout after {timeout} s"
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    # A step that failed usually explains why on stderr; a step that succeeded, in its last summary line.
    detail = last_line(result.stderr) if result.returncode != 0 and result.stderr else last_line(result.stdout)
    return result.returncode, detail


def acquire_lock() -> bool:
    """Create the lock file atomically. False if another run holds it."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        if time.time() - LOCK_PATH.stat().st_mtime > STALE_LOCK_SECONDS:
            print(f"WARNING: removing stale lock {LOCK_PATH.name} (older than {STALE_LOCK_SECONDS // 3600} h; "
                  "a previous run was killed or the machine lost power)")
            LOCK_PATH.unlink()
    except FileNotFoundError:
        pass
    try:
        fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w") as f:
        f.write(f"pid {os.getpid()} started {wall_clock()}\n")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ingest -> load -> clean -> validate.")
    parser.add_argument("--run-time", type=run_time_arg, help="pipeline clock, e.g. 2026-11-20T08:10Z (default: now, UTC)")
    parser.add_argument("--skip-ingest", action="store_true",
                        help="rebuild from landed raw data without calling any API")
    args = parser.parse_args()
    # The one clock for every data decision in this run; datetime.now() appears elsewhere only in log timestamps.
    run_time = args.run_time or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")

    if not acquire_lock():
        print(f"Another pipeline run is in progress ({LOCK_PATH.name} exists). Nothing was run.")
        return LOCKED_EXIT

    run_id = uuid.uuid4().hex[:8]
    steps = [s for s in STEPS if not (args.skip_ingest and s[0] == "src/ingest.py")]
    try:
        print(f"Pipeline run {run_id} | run time {run_time} | steps: {', '.join(s[0] for s in steps)}")
        for script, timeout, takes_run_time in steps:
            print(f"\n=== {script} ===", flush=True)
            started = wall_clock()
            code, detail = run_step(script, timeout, takes_run_time, run_time)
            log_step(run_id, run_time, script, started, wall_clock(), code, detail)
            if code != 0:
                print(f"\nPIPELINE FAILED at {script} with exit code {code} (run {run_id}); later steps not run.")
                return code
        print(f"\nPIPELINE OK: {len(steps)} steps succeeded (run {run_id}, run time {run_time}).")
        return 0
    finally:
        LOCK_PATH.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
