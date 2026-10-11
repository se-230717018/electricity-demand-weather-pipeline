# Data Source Cards

Provenance records for every source used by this pipeline: where the data comes from,
on what terms, and what we already know about its quirks.

---

## 1. EIA — Hourly electricity demand and day-ahead demand forecast

```
source_name: EIA Hourly Electric Grid Monitor (Form EIA-930) — hourly demand (D) and day-ahead demand forecast (DF) by balancing authority
provider: U.S. Energy Information Administration (EIA)
url: https://www.eia.gov/opendata/ (endpoint: https://api.eia.gov/v2/electricity/rto/region-data/data/)
access_method: REST API v2, JSON; free personal API key required (read from the EIA_API_KEY environment variable)
licence: Public domain (U.S. government data) — https://www.eia.gov/about/copyrights_reuse.php
terms_notes: EIA data may be reused freely; EIA asks to be cited as the source ("Source: U.S. Energy Information Administration"). API keys are personal and must not be shared or published.
update_cadence: hourly (near real-time; records for the current day are already present)
coverage: hourly data from 2019-01-01T00 (UTC) to present. Our pipeline retrieves three balancing authorities — NYIS (New York), ERCO (Texas), CISO (California) — and two series (D, DF), for START_DATE to END_DATE in .env (currently 2019-01-01 to 2026-09-30). Roughly 407,000 records.
record_meaning: one row = one hour × one balancing authority × one series type (D = actual demand, DF = EIA's day-ahead forecast); value in megawatthours
join_key: respondent + period (UTC hour) (joins to: region_locations → Open-Meteo weather on location code + UTC hour)
first_retrieved: 2026-10-10T15:44:40Z
known_issues: see list below
```

**Known issues**

- **Row limit and pagination:** the API returns at most 5,000 rows per request and adds an "incomplete return" warning when there are more. The script pages with `offset`/`length` until `response.total` is reached (~28 pages per region), using a fixed sort order (period, type) so pages stay stable.
- **Numbers delivered as text:** `value` and `response.total` arrive as strings. Left untouched in raw files; to be converted in M3.
- **Missing forecast hours:** a complete pull would have 2 series × 67,920 hours = 135,840 records per region, but our full run on 2026-10-10 returned NYIS 135,743 (97 missing), ERCO 135,719 (121 missing) and CISO 135,718 (122 missing). This is consistent with our M0 check that the DF series has roughly 100 fewer hours than D (e.g. NYIS: 67,833 D vs 67,733 DF). Whether all gaps are in DF will be confirmed in M3; they must be handled before benchmarking our forecast against DF.
- **Timestamp format:** `period` is `YYYY-MM-DDTHH` in UTC, which differs from Open-Meteo's `YYYY-MM-DDTHH:MM`. Needs a common type before joining.
- **Unsorted by default:** without an explicit sort, records are not returned in chronological order.
- **Repeated descriptive fields:** `respondent-name` and `type-name` repeat on every row; to be normalised into lookup tables in M2.
- **API key in raw responses:** Checked on 2026-10-10: raw files do not contain the API key. Either way, raw EIA files are never committed (data/raw/ is git-ignored).
- **Raw file layout:** one file per page, `data/raw/eia/<UTC timestamp>_<REGION>_pageNNN.json`.

---

## 2. Open-Meteo — Hourly historical weather

```
source_name: Open-Meteo Historical Weather API — hourly weather at one representative city per region
provider: Open-Meteo (open-meteo.com)
url: https://open-meteo.com/en/docs/historical-weather-api (endpoint: https://archive-api.open-meteo.com/v1/archive)
access_method: REST API, JSON; no API key required (free for non-commercial use)
licence: CC BY 4.0
terms_notes: free for non-commercial use within Open-Meteo's fair-use request limits. Redistribution is allowed under CC BY 4.0 with attribution ("Weather data by Open-Meteo.com", linking to https://open-meteo.com/). Attribution is included in our README.
update_cadence: daily; the archive lags the present by a few days
coverage: historical hourly data going back decades, global. Our pipeline retrieves three locations — New York (NYIS, 40.71, -74.01), Houston (ERCO, 29.76, -95.37), Los Angeles (CISO, 34.05, -118.24) — for START_DATE to END_DATE in .env (currently 2019-01-01 to 2026-09-30), in UTC. Variables: temperature_2m (°C), relative_humidity_2m (%), precipitation (mm).
record_meaning: one entry = one hour at one location; delivered as parallel arrays (time[i] belongs with temperature_2m[i], relative_humidity_2m[i], precipitation[i])
join_key: location code + time (UTC hour) (joins to: EIA demand on respondent + period)
first_retrieved: 2026-10-08T09:39:27Z
known_issues: see list below
```

**Known issues**

- **Column-oriented format:** data arrives as parallel arrays, not rows. Saved unmodified; to be reshaped into rows in M3.
- **Grid snapping:** the returned latitude/longitude differ slightly from the requested ones, because Open-Meteo answers with the centre of the model grid cell containing the point.
- **Time zone:** results depend on the `timezone` parameter (we saw a 4-hour shift between `America/New_York` and `GMT` in M0). The script always requests `timezone=GMT` so hours align with EIA's UTC periods.
- **Archive lag:** the most recent days can be missing or `null`, so END_DATE is set a few days in the past.
- **Timestamp format:** `time` is `YYYY-MM-DDTHH:MM`, unlike EIA's `YYYY-MM-DDTHH`.
- **One city per region:** each balancing authority is represented by a single city. This is a simplification: real grid regions span many climates (especially ERCO and CISO).
- **Model data, not station measurements:** values come from Open-Meteo's historical weather models, not from a physical weather station at that exact point.
- **Raw file layout:** one file per location per run, `data/raw/open_meteo/<UTC timestamp>_<REGION>.json`.