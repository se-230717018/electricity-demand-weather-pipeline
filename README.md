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