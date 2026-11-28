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
| Ingestion: where each run starts (Open-Meteo) | | |
| Overlap (EIA) | | |
| Overlap (Open-Meteo) | | |
| Loading | full reload / manifest | |
| Version rule | retrieved_at / source stamp | |
| Cleaning | full rebuild / baseline | |
| The clock | `--run-time`, default now | |

### How late our data arrives

#### EIA

_(Tuba — the query and its output: max delay per region and series, D and DF; do old values get revised?)_

#### Open-Meteo

_(İrem)_

### The source's memory

#### EIA

_(Tuba — how far back can we fetch? what outage loses data? how would we notice?)_

#### Open-Meteo

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
| An old file re-loaded | | | |

### monitor.py on the day we tagged

_(Esma — pasted output.)_

## 5. What can still go wrong

_(Everyone — the failures this pipeline would not catch.)_
