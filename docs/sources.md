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
- **Missing forecast hours:** the DF series has roughly 100 fewer hours than D (e.g. NYIS: 67,833 D vs 67,733 DF in our M0 check). Must be handled before benchmarking our forecast against DF.
- **Timestamp format:** `period` is `YYYY-MM-DDTHH` in UTC, which differs from Open-Meteo's `YYYY-MM-DDTHH:MM`. Needs a common type before joining.
- **Unsorted by default:** without an explicit sort, records are not returned in chronological order.
- **Repeated descriptive fields:** `respondent-name` and `type-name` repeat on every row; to be normalised into lookup tables in M2.
- **API key in raw responses:** Checked on 2026-10-10: raw files do not contain the API key. Either way, raw EIA files are never committed (data/raw/ is git-ignored).
- **Raw file layout:** one file per page, `data/raw/eia/<UTC timestamp>_<REGION>_pageNNN.json`.