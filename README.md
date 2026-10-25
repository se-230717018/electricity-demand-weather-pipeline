# Electricity Demand & Weather Pipeline

A data pipeline that collects hourly electricity demand for three U.S. grid regions together with
hourly weather data, as the foundation for testing whether weather improves day-ahead demand forecasts.

## The question

Can weather data improve day-ahead electricity demand forecasts? We will predict next-day hourly
demand for three U.S. balancing authorities (New York, Texas, California) from temperature, humidity,
time-of-day and calendar features, and compare our forecasts against the day-ahead forecasts EIA
already publishes (series DF), which gives us a real-world benchmark. We will also explain how strongly
demand depends on temperature in each region, and whether the relationship is driven by cooling,
heating, or both.

## Data sources

Full provenance, licences and known issues are in **[docs/sources.md](docs/sources.md)**.

- **EIA Hourly Electric Grid Monitor** — hourly demand (D) and day-ahead forecast (DF) for NYIS, ERCO and CISO. *Source: U.S. Energy Information Administration.*
- **Open-Meteo Historical Weather API** — hourly temperature, humidity and precipitation for one representative city per region. *[Weather data by Open-Meteo.com](https://open-meteo.com/), licensed under CC BY 4.0.*

## How to run it

Requirements: Python 3.10+ and Git.

**1. Clone the repository**
```bash
git clone https://github.com/se-230717018/electricity-demand-weather-pipeline.git
cd electricity-demand-weather-pipeline
```

**2. Create and activate a virtual environment**
```bash
python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate
```

**3. Install the requirements**
```bash
pip install -r requirements.txt
```

**4. Configure environment variables**

Copy the template and fill in your own EIA API key (free: https://www.eia.gov/opendata/register.php):
```bash
# Windows (PowerShell):
Copy-Item .env.example .env
# macOS / Linux:
cp .env.example .env
```

| Variable | Meaning |
|---|---|
| `EIA_API_KEY` | Your personal EIA API key (never commit it) |
| `START_DATE`, `END_DATE` | Date range for both sources, UTC, `YYYY-MM-DD` |
| `EIA_RESPONDENTS` | Comma-separated balancing authorities, e.g. `NYIS,ERCO,CISO` |
| `OPENMETEO_LOCATIONS` | One city per region as `CODE:LAT:LON`, comma-separated |
| `OPENMETEO_HOURLY` | Weather variables to request |

`.env` is listed in `.gitignore` and is never committed.

**5. Run the ingestion**

From the repository root:
```bash
python src/ingest.py
```

A full run makes about 85 requests and takes a few minutes. It ends with a summary showing, for each
source, how many files and records were retrieved and whether anything failed. Every run writes new
files named with a UTC timestamp, so earlier raw files are never overwritten.

## Repository structure

```
.
├── README.md          ← this file
├── .gitignore         ← keeps .env, raw data and local environments out of Git
├── .env.example       ← template of required environment variables (no real values)
├── requirements.txt   ← Python dependencies
├── data/
│   └── raw/           ← landed data, exactly as received (not committed, see below)
│       ├── eia/         <UTC timestamp>_<REGION>_pageNNN.json
│       └── open_meteo/  <UTC timestamp>_<REGION>.json
├── src/
│   └── ingest.py      ← ingestion script: retries, timeouts, pagination, raw landing, run summary
└── docs/
    └── sources.md     ← data source cards
```

**Why raw data is not in the repository:** `data/raw/` is git-ignored. Raw files grow with every run,
and raw EIA responses are tied to a personal API key. Anyone with their own key can regenerate the
data by following the steps above.

## Status

M1 — ingestion complete

## Team

| Name | GitHub |
|---|---|
| Esma Gül Baş | [se-230717042](https://github.com/se-230717042) |
| İrem Çakmak | [se-230717018](https://github.com/se-230717018) |
| Tuba Arpaçay | [se-230717038](https://github.com/se-230717038) |

## Decisions (M2)

### Unknown references

Every weather location must belong to a known grid region (`location.region_key` is a foreign key to `region`).
A location whose code (from the raw file name, e.g. `NYIS`) has no matching `region.respondent` is **not loaded and
not silently dropped**: it is written to the `quarantine` table with `reason = 'unknown region'`, the source file,
a short reference and the raw record. The same rule applies to weather rows that belong to such a location.
Quarantined records are counted in the load summary, so nothing disappears without a trace.

### Change over time

Every ingestion run re-downloads the full period, so the same (location, hour) can arrive in several raw files.
We treat this as **type 1 change: the latest retrieval wins**. Rows are upserted with
`ON CONFLICT ... DO UPDATE ... WHERE excluded.retrieved_at >= weather.retrieved_at`, so a newer file overwrites
an older value and an older file never overwrites a newer one. The database keeps only the current value; the full
history remains in the timestamped raw files under `data/raw/`, which are never overwritten.

### Known issues — Open-Meteo

- **Parallel arrays:** the API returns `time`, `temperature_2m`, `relative_humidity_2m` and `precipitation` as
  separate arrays. The loader zips them by index into one row per hour.
- **Timestamp format:** Open-Meteo uses `YYYY-MM-DDTHH:MM`, EIA uses `YYYY-MM-DDTHH`. Both are normalised to
  `YYYY-MM-DDTHH:MMZ` (UTC) so that `weather.observed_at` and `demand.period_utc` can be joined directly.
- **Time zone:** all files are requested with `timezone=GMT`. The loader checks `utc_offset_seconds`; a file that is
  not in UTC is not loaded as-is.
- **Grid snapping:** the stored latitude/longitude are the ones Open-Meteo returned (centre of the model grid cell),
  not the ones we requested, e.g. NYIS requested 40.71, -74.01 → returned 40.738, -74.043.
- **One city per region:** each balancing authority is represented by a single city. Real grid regions span several
  climates (especially ERCO and CISO), so the weather is an approximation of the region's weather.
- **Model data:** values come from Open-Meteo's historical weather models, not from physical weather stations.
- **Missing values:** a `null` in Open-Meteo means the hour is not yet in the archive (end-of-period lag). It is
  stored as `NULL`, never as 0, and counted in the load summary.

### Key test findings — Open-Meteo (`src/key_tests_weather.py`)

Tested on one ingestion run (3 files, 203,760 hourly rows, 67,920 per location):

| Test | Result |
|---|---|
| Duplicate (location, time) within one run | 0 — the natural key holds |
| Files with `utc_offset_seconds` ≠ 0 | 0 — all files are UTC |
| Null values (temperature, humidity, precipitation) | 0 — END_DATE is set a few days back, so the archive lag did not affect our period |
| Location codes without an EIA region | none — NYIS, ERCO and CISO all match |

Across two runs the same 203,760 (location, hour) pairs appear twice, as expected; the latest-wins upsert keeps one.

### Keys

| Table | Key | Why it holds |
|---|---|---|
| `region` | surrogate `region_key`; natural key `respondent` (UNIQUE) | Key test: every respondent has exactly one `respondent-name` |
| `series_type` | surrogate `type_key`; natural key `type_code` (UNIQUE) | Key test: every type (`D`, `DF`) has exactly one `type-name` |
| `demand` | `(region_key, type_key, period_utc)` | Key test: 0 duplicate `(respondent, type, period)` in 407,180 raw records |
| `weather` | `(location_key, observed_at)` | See the Open-Meteo key test findings above |

Surrogate keys are integers assigned by SQLite, so joins stay short and do not depend on source codes. Entities and events are loaded with `INSERT ... ON CONFLICT DO UPDATE ... WHERE excluded.retrieved_at >= <table>.retrieved_at`: the newest file wins, and existing surrogate keys never change (no `INSERT OR REPLACE`). Loading the same files twice gives the same row counts.

### Missing values

- **EIA `value` empty or not a number** means *not reported*, not zero. It is stored as `NULL` and counted as `values_cleaned` in the run summary. In our run: **23 of 407,180** values (CISO demand 22, NYIS demand 1; none in the day-ahead forecast).
- **EIA record with a missing `respondent`, `type` or an unparseable `period`** cannot be keyed, so it goes to `quarantine` with a reason instead of being dropped silently. In our run: 0.
- **A file that cannot be read** (broken JSON, no `response.data`) stops the whole load and nothing is written (atomic load).
- Open-Meteo `null` values are described under *Known issues – Open-Meteo*.

### Key test findings – EIA (`src/key_tests_eia.py`)

One ingestion run (`20261010T154440Z`), 84 files:

| Test | Result |
|---|---|
| Records | 407,180 |
| Records with a missing key field | 0 |
| Duplicate `(respondent, type, period)` | 0 |
| Respondents with more than one name | 0 |
| Types with more than one name | 0 |
| Empty or non-numeric `value` | 23 (CISO `D` 22, NYIS `D` 1) |

## Analytical query

`sql/queries/demand_by_temperature.sql` answers: *how does electricity demand change with outdoor temperature in each region?*

Grain of the result: one row = one region × one 5 °C temperature band. Only actual demand (`D`) is used. Each demand hour is joined to its region's weather point at the same UTC hour; hours where demand or temperature is `NULL` are left out, and `hours` shows how many hours each average rests on.

Run it:

```bash
sqlite3 -header -column data/grid.db < sql/queries/demand_by_temperature.sql
```

Output (full load, 2026-10-10 run):

| respondent | band (°C) | hours | avg demand (MWh) | min | max |
|---|---|---:|---:|---:|---:|
| CISO | 0–5 | 451 | 23,000 | 16,725 | 29,071 |
| CISO | 5–10 | 5,573 | 22,695 | 13,519 | 31,226 |
| CISO | 10–15 | 17,082 | 22,939 | 91 | 30,636 |
| CISO | 15–20 | 21,593 | 24,531 | 14 | 43,002 |
| CISO | 20–25 | 12,872 | 27,069 | 12,224 | 45,116 |
| CISO | 25–30 | 6,862 | 29,143 | 12,193 | 50,378 |
| CISO | 30–35 | 2,980 | 31,905 | 11,819 | 51,104 |
| CISO | 35–40 | 435 | 35,483 | 21,829 | 50,609 |
| CISO | 40–45 | 47 | 39,686 | 31,492 | 46,643 |
| CISO | 45–50 | 1 | 40,700 | 40,700 | 40,700 |
| ERCO | -15 – -10 | 4 | 46,086 | 45,747 | 46,555 |
| ERCO | -10 – -5 | 67 | 62,405 | 43,776 | 78,155 |
| ERCO | -5–0 | 295 | 62,507 | 42,938 | 80,150 |
| ERCO | 0–5 | 1,518 | 53,233 | 36,083 | 76,612 |
| ERCO | 5–10 | 4,435 | 45,617 | 27,903 | 76,186 |
| ERCO | 10–15 | 6,989 | 41,668 | 27,670 | 62,440 |
| ERCO | 15–20 | 10,677 | 40,324 | 27,449 | 63,368 |
| ERCO | 20–25 | 17,986 | 44,652 | 29,221 | 78,210 |
| ERCO | 25–30 | 18,520 | 55,765 | 33,055 | 86,050 |
| ERCO | 30–35 | 6,552 | 68,503 | 43,840 | 91,075 |
| ERCO | 35–40 | 868 | 77,625 | 56,703 | 90,741 |
| ERCO | 40–45 | 8 | 80,872 | 77,781 | 84,242 |
| NYIS | -20 – -15 | 66 | 20,277 | 17,094 | 24,105 |
| NYIS | -15 – -10 | 417 | 20,334 | 16,021 | 24,728 |
| NYIS | -10 – -5 | 1,448 | 18,915 | 0 | 24,206 |
| NYIS | -5–0 | 5,780 | 17,916 | 0 | 23,253 |
| NYIS | 0–5 | 9,714 | 17,090 | 12,110 | 22,741 |
| NYIS | 5–10 | 10,185 | 15,851 | 0 | 21,504 |
| NYIS | 10–15 | 9,698 | 14,980 | 10,731 | 20,586 |
| NYIS | 15–20 | 10,457 | 15,472 | 0 | 22,240 |
| NYIS | 20–25 | 12,082 | 18,222 | 10,779 | 28,287 |
| NYIS | 25–30 | 6,385 | 21,538 | 11,073 | 30,339 |
| NYIS | 30–35 | 1,545 | 24,608 | 12,858 | 30,919 |
| NYIS | 35–40 | 134 | 27,840 | 21,365 | 31,857 |
| NYIS | 40–45 | 7 | 28,321 | 27,641 | 29,255 |

**Reading it:** ERCO and NYIS show a U shape: demand is lowest around 10–20 °C and rises in both cold (heating) and hot (cooling) hours. CISO rises steadily with temperature; it has few cold hours, so cooling dominates. Bands with very few hours (e.g. CISO 45–50 °C, 1 hour) should not be over-interpreted.

**Known issue (EIA):** some hours report demand of 0 or near 0 MWh (NYIS min 0, CISO min 14 and 91). These are numeric values, so they are loaded as reported, not turned into NULL; they look like reporting errors and pull a band's minimum down, while the averages, built on thousands of hours, are barely affected.