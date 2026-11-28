# Pipeline — Electricity Demand & Weather

Milestone M5 · Runner: [`src/run_pipeline.py`](../src/run_pipeline.py) · Monitor: [`src/monitor.py`](../src/monitor.py) ·
Schedule: [`ops/`](../ops/)

> **Who writes what** (delete this box before the final commit). Edit only your own parts; `git pull` before you start
> and again before you push. İrem: everything Open-Meteo. Tuba: everything EIA. Esma: graph, runner, operations,
> schedule, run log, monitor. Drills: whoever ran the drill writes its entry.

## 1. The graph

_(Esma — diagram ingest → load → clean → validate; one line per step: input, output, rebuildable from.)_

## 2. Design decisions

| Decision | Our choice | Why |
|---|---|---|
| Ingestion: where each run starts (EIA) | | |
| Ingestion: where each run starts (Open-Meteo) | Per location: the last hour with a value in the newest landed file, minus the overlap (`START_DATE` if nothing has landed). Ends on the day before `--run-time`. | Starting from the data, not the retrieval time, closes any gap: the first incremental run (27 Nov) requested 20 Sep–26 Nov and filled 1 Oct–26 Nov (+4,104 rows) on its own. The run-time day is never requested because the archive fills it with forecast values, including hours after the run time. |
| Overlap (EIA) | | |
| Overlap (Open-Meteo) | 10 days (`OPEN_METEO_OVERLAP_DAYS` in `src/ingest.py`) | Values older than 8 days never changed between two retrievals, and the reanalysis (ERA5) lags ~6 days (delay table below). 10 days covers both with a margin; the cost is 240 extra hours per location per run. |
| Loading | full reload / manifest | |
| Version rule | retrieved_at | Neither source has a version stamp, so the file's UTC retrieval time is used. Guarded upsert `WHERE excluded.retrieved_at > <table>.retrieved_at` (weather and location: `src/load_weather.py`). Shown in the "old file re-loaded" drill. |
| Cleaning | full rebuild | Flags are always computed on the whole history, so batch boundaries cannot change them. Consequence: old flags can change as history grows — after adding 1 Oct–26 Nov weather, CISO's `unusual_high` temperature hours went from 64 to 76 because the median and MAD moved. |
| The clock | `--run-time`, default now | |

### How late our data arrives

#### EIA

_(Tuba — the query and its output: max delay per region and series, D and DF; do old values get revised?)_

#### Open-Meteo
| Evidence | Result |
|---|---|
| Same period (2019-01-01 … 2026-09-30) retrieved on 2026-10-08 and 2026-10-24, compared per (location, hour) | 0 of 203,760 values changed in temperature, humidity or precipitation. Every hour was already ≥ 8 days old at the first retrieval. |
| Request up to "today", measured 2026-11-27 17:32 UTC | The default archive returns complete values up to 2026-11-27 23:00 UTC, i.e. 5.5 hours **after** the measurement: the most recent hours are forecast values, not observations. |
| Same window with `models=era5` | ERA5 ends on 2026-11-21 23:00 UTC: the reanalysis lags 5.8 days. |

So Open-Meteo data has no delay in the usual sense (it is always "there"), but the most recent days are provisional. We never request the run-time day, and every run re-fetches the last 10 days so that provisional values are replaced by later versions (newest `retrieved_at` wins). What we could not measure: how often values *younger* than 8 days change.
_(İrem)_

### The source's memory

#### EIA

_(Tuba — how far back can we fetch? what outage loses data? how would we notice?)_

#### Open-Meteo
The historical archive goes back to 1940, so an outage of any length can be recovered: the next run asks from the last landed hour, whatever its age. A very long outage is caught up in chunks of at most `OPEN_METEO_MAX_CATCHUP_DAYS` (3,650 days) per run. A stopped Open-Meteo feed would show in freshness from the run time and in completeness (`monitor.py`); a failed request makes `ingest.py` exit 1.
_(İrem)_

## 3. Operations

_(Esma — run by hand, rebuild / backfill, exit codes, logs.)_

- Run by hand:
- Rebuild / backfill:
- Exit codes: 0 success · 1 a step failed (see the closing line and the run log) · 2 bad arguments ·
  75 already running · 124 a step timed out
- Logs:

## 4. Evidence

### The schedule

_(Esma — machine, interval, ops/ file.)_

### The run log

_(Esma — one query and its output: first run, last run, runs, days, failures by step and cause.)_

### Missed runs

_(Esma — what we did, the ALARM, completeness before and after.)_

### Drills

| Drill | Who | What we did | What the run log / runner / monitor showed |
|---|---|---|---|
| Credential failure | | | |
| A step that fails | | | |
| A step that hangs | | | |
| Two runs at once | | | |
| Missed runs | | | |
| An old file re-loaded | İrem | On a copy of the database and raw folder (`/tmp/m5_drill`): a fake NYIS file with 99.9 °C at 2026-09-25 12:00 UTC, loaded first with an older stamp (`20261001T000000Z`), then with a newer one (`20261231T000000Z`). | Before: 12.9 °C from `20261127T181404Z_NYIS.json`. Older stamp: still 12.9 °C, same file — the old file could not undo the newer value. Newer stamp (control): 99.9 °C. The newest `retrieved_at` wins whatever the load order; the real database was not touched. |

### monitor.py on the day we tagged

_(Esma — pasted output.)_

## 5. What can still go wrong
**Open-Meteo / weather (İrem):**
- **Provisional values younger than 8 days** may change in ways our 10-day overlap does not cover; we have not measured it.
- **The default archive model can change** (Open-Meteo's "best match" mixes models). A change would silently shift values; comparing two retrievals would only catch it inside the overlap window.
- **The newest landed file decides the start.** A file landed by hand with a later timestamp but less data could make the next run start too late. Files should only be landed by `ingest.py`.
- **Demand and weather can end on different days** while EIA ingestion is not incremental; validate.py's "latest hour" WARN shows it.

_(Everyone — the failures this pipeline would not catch.)_
