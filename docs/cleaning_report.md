# Cleaning Report — Electricity Demand & Weather Pipeline

Milestone M3 · Data cleaning and quality report.
Profile notebook: [`notebooks/m3_profile.ipynb`](../notebooks/m3_profile.ipynb) ·
Cleaned layer: [`sql/clean_schema.sql`](../sql/clean_schema.sql) ·
Code: [`src/clean.py`](../src/clean.py), [`src/clean_demand.py`](../src/clean_demand.py),
[`src/clean_weather.py`](../src/clean_weather.py), [`src/validate.py`](../src/validate.py) ·
Mappings: [`data/mappings/`](../data/mappings/)

<!--
WHO WRITES WHAT (delete this comment block before the final commit)
  §1 Summary, §2 Profile highlights (text/identity/coverage), §7, §8 ..... Esma
  §3 register rows + "checked and not found" rows for demand .............. Tuba
  §3 register rows + "checked and not found" rows for weather + identity .. İrem
  §4 Missing values: demand patterns ...................................... Tuba
  §4 Missing values: weather patterns ..................................... İrem
  §5 Flags, rules and constants: demand ................................... Tuba
  §5 Flags, rules and constants: weather .................................. İrem
  §6 Mapping and identity decisions ....................................... İrem
Only edit your own parts. git pull before you start and again before you push.
-->

## 1. Summary

<!-- Esma: 5–6 sentences. What data; the most important problems; what the cleaned layer contains;
what we still can't say. Also: M2 issues fixed since the m2 tag (if none, say "none"). -->

## 2. Profile highlights

<!-- The tables/figures from the notebook that led to findings, one short paragraph each.
Demand (Tuba), weather (İrem), text / identity / coverage (Esma). -->

### 2.1 Demand
Profiled in `notebooks/m3_profile.ipynb` (demand section, cells 1.1–1.8) by Tuba: 407,180 rows = 3 regions × 2 series (D = actual, DF = day-ahead forecast) over 67,920 UTC hours (2019-01-01T00Z – 2026-09-30T23Z). D medians: CISO 24,389, ERCO 47,324, NYIS 16,857 MWh. Main findings: 23 NULL values (CISO D 22, NYIS D 1); 340 hourly rows never sent (D 4, all on DST fall-back nights; DF 336, in whole local days); 196 zero values in NYIS (D 12, DF 184 — the DF zeros are 8 whole days); 3 near-zero dropout hours in CISO D. No non-zero value repeats for more than 3 hours. DF/D has a median of 0.98–1.00 and only 1 hour outside 0.5–2. The highest values are real heat waves (California, Sep 2022 and Aug 2020); there are no unusually low values.

### 2.2 Weather
Profiled in `notebooks/m3_profile.ipynb` (weather section) by İrem: 203,760 rows (3 locations × 67,920 hours), all in UTC. 0 NULL and 0 out-of-range values. Ranges: temperature −18.3…45.7 °C, humidity 3…100 %, precipitation 0…36.8 mm/h. The extremes line up with known events (Winter Storm Uri 2021, Texas 2023 and California 2024 heat waves, Hurricane Ida 2021). No stuck values (longest natural runs 7 h and 18 h) and no implausible jumps (p99 3.0–3.8 °C/h, max 10.2 °C). Robust z flags 64 hot CISO hours, 279 cold and 9 dry ERCO hours; none in NYIS.

### 2.3 Text, categories, identity and coverage

## 3. Issues register

| ID | Family | Table.column | What | Where / when / how many | Evidence | Cause | Decision | Flag | Investigated by |
|---|---|---|---|---|---|---|---|---|---|
| I-01 | 1 Missing | demand.value_mwh | Value NULL in the source (empty / non-numeric) | 23 h: CISO D 22 (2019-02-02 … 2023-11-14; 9 in 2019, 5 on 2021-08-29…31, none after Nov 2023); NYIS D 1 (2021-11-07 05:00 UTC) | `value_mwh IS NULL` (notebook 1.2); M2 load counted 23 | CISO: unknown; NYIS: inferred — DST fall-back night, repeated 01:00 local hour | keep the row, value NULL, no imputation | `missing_not_reported` | Tuba Arpaçay |
| I-02 | 1 Missing | demand (rows) | D hours never sent | 4 rows: CISO 2019-11-03 06:00 UTC; CISO, ERCO, NYIS 2021-11-07 06:00 UTC | hourly calendar vs. rows (notebook 1.3) | inferred — both dates are US DST fall-back nights; the repeated hour is not reported | no row inserted, nothing imputed; counted here | — | Tuba Arpaçay |
| I-03 | 1 Missing | demand (rows) | DF hours never sent, in whole local days | 336 rows, all from Nov 2024: CISO 120 (DST switch days 2024-11-03, 2025-03-09, 2025-11-02, 2026-03-08; 23 h in March, 25 h in November), ERCO 120 (2025-12-05/06, 2026-08-06, 2026-08-09, 2026-09-04), NYIS 96 (2026-05-13, 2026-05-19, 2026-08-09, 2026-09-04) | notebook 1.3; ERCO and NYIS share 2026-08-09 and 2026-09-04 | inferred — the source did not publish a forecast for those days | no row inserted; DF coverage is a WARN in validate.py | — | Tuba Arpaçay |
| I-04 | 2 Invalid | demand.value_mwh | Zero actual demand | NYIS D 12 h (2019-04-18, 2024-01-18, 2024-10-09 ×2, 2025-01-15, 2025-01-16, and a 6 h run on 2026-02-10 00–05 UTC) | `value_mwh <= 0` (notebook 1.4) | reporting error — a whole region cannot use 0 MWh | value NULL | `invalid_nonpositive` | Tuba Arpaçay |
| I-05 | 2 Invalid | demand.value_mwh | Forecast published as 0 for whole days | NYIS DF 184 h = 8 blocks × 23 h (2019-01-03, 2019-02-15, 2019-08-20, 2024-06-28, 2024-10-13, 2025-03-14, 2025-09-09, 2026-04-09) | notebook 1.5; same day-block shape as I-03 | inferred — no forecast produced, encoded as 0 instead of a missing row | value NULL | `invalid_nonpositive` | Tuba Arpaçay |
| I-06 | 2 Invalid | demand.value_mwh | Dropout: near-zero demand | CISO D 2019-12-20 00–02 UTC: 14, 91, 96 MWh (≤ 0.4 % of the median 24,389) | ratio to series median (notebook 1.4–1.5); the next-lowest value in any series is 47 % of its median | reporting dropout | value NULL | `invalid_dropout` | Tuba Arpaçay |
| I-07 | 3 Unusual | demand.value_mwh | Very high demand | 5,667 h: CISO D 1,675 / DF 1,921, ERCO 245 / 209, NYIS 739 / 878; max CISO D 51,104 MWh on 2022-09-07 01:00 UTC | robust z > 3.5 (notebook 1.8); top hours = California heat waves of 6–9 Sep 2022 and 18–19 Aug 2020, D and DF agree | real event | keep the value | `unusual_high` | Tuba Arpaçay |
| I-08 | 4 Cross-field | demand.value_mwh (DF vs D) | Forecast far from actual | 1 h: CISO 2025-07-31 21:00 UTC, D 11,819 vs DF 26,135 (ratio 2.21) | DF/D outside 0.5–2 (notebook 1.7); median DF/D 0.98–1.00 | inferred — the actual looks too low (a July afternoon at 48 % of the median), not the forecast | keep both values, flag the DF row; D listed in §8 | `forecast_mismatch` | Tuba Arpaçay |
<!-- İrem: weather + identity rows I-10 … I-19 -->
<!-- Esma: text / category / coverage rows I-20 … -->
| I-W01 | 3 Unusual | weather.temperature_c | Very hot hours for Los Angeles | CISO, 64 h (≈ ≥ 39 °C); max 45.7 °C on 2024-09-06 21:00 UTC | robust z > 3.5; dates match the Sept 2020 and Sept 2024 Southern California heat waves | real weather event | keep the value | `unusual_high` | İrem Çakmak |
| I-W02 | 3 Unusual | weather.temperature_c | Freezing hours for Houston | ERCO, 279 h (≈ ≤ −1 °C); min −10.9 °C on 2021-02-16 12:00 UTC | robust z < −3.5; Winter Storm Uri, the week the Texas grid failed | real weather event, highly relevant to demand | keep the value | `unusual_low` | İrem Çakmak |
| I-W03 | 3 Unusual | weather.relative_humidity_pct | Very dry hours for Houston | ERCO, 9 h (≈ ≤ 13 %) | robust z < −3.5 | real (dry air mass) | keep the value | `unusual_low` | İrem Çakmak |
| I-W04 | 3 Unusual | weather.precipitation_mm | Extreme hourly rainfall | NYIS 33.8 mm on 2021-09-02 01:00 UTC; CISO 18.9 mm on 2023-09-02 07:00 UTC | NYIS matches the remnants of Hurricane Ida; no event identified for CISO | real (NYIS) / unknown (CISO) | keep; not flaggable because MAD = 0 | none (`ok`) | İrem Çakmak |
| I-W05 | 6 Identity | location ↔ region | Weather point linked to region only by a shared code | 3 locations | M1–M2 assumption, never written down | implicit join | explicit mapping in `region_location.csv` (§6) | — | İrem Çakmak |
| I-W06 | 6 Identity | location.latitude / longitude | Returned coordinates differ from requested ones | 3 locations, e.g. NYIS 40.71, −74.01 → 40.738, −74.043 | M2 `location` vs `.env` | Open-Meteo snaps to its model grid cell | store the returned values; record both in the mapping note | — | İrem Çakmak |

### Checked and not found

| Family | Check | Result |
|---|---|---|
<!-- Every family 1–6 must appear at least once, here or in the register. Write the exact check,
e.g. "SELECT COUNT(*) FROM weather WHERE relative_humidity_pct > 100" → 0. -->
| 1 Missing | `weather.<variable> IS NULL`, 3 variables × 3 locations (İrem) | 0 |
| 2 Invalid | temperature outside −60…60 °C, humidity outside 0…100 %, precipitation < 0 mm (İrem) | 0 |
| 4 Sequence | same weather value in ≥ 24 consecutive hours (İrem) | 0 (longest: 7 h temperature, 18 h humidity at 100 %) |
| 1 Missing | `value_mwh IS NULL` in every DF series and in ERCO D (Tuba) | 0 |
| 2 Invalid | `value_mwh <= 0` in CISO and ERCO, D and DF (Tuba) | 0 |
| 2 Invalid | value below 50 % of its series median, ERCO D and DF (Tuba) | 0 |
| 3 Unusual | robust z < −3.5 in all 6 demand series (Tuba) | 0 |
| 4 Sequence | same non-zero demand value in ≥ 6 consecutive hours (Tuba) | 0 (longest: 3 h) |
| 5 Category | every series type has one role in `series_type_role.csv` (D → actual, DF → forecast, MWh) (Tuba) | 2 of 2 matched, 0 unmatched | | 0 (largest: 10.2 °C) |
## 4. Missing values

<!-- Per substantial pattern: where/when, mechanism (MCAR / MAR / MNAR) with evidence,
what it means for M4 (which comparisons are unsafe, what to exclude or treat separately). -->

### 4.1 Demand
- **23 NULL values (I-01).** CISO D 22: spread over 2019–2023 (9 in 2019), with one cluster of 5 on 29–31 Aug 2021 and none after Nov 2023. Not clearly MCAR — the values bunch in time — but the cause is not documented: mechanism **unknown**. NYIS D 1: the DST fall-back night 2021-11-07 05:00 UTC. It depends on the clock (an observed variable), so **MAR, inferred**.
- **4 missing D rows (I-02).** All at 06:00 UTC on US DST fall-back nights, i.e. the repeated 01:00 local hour. Missingness depends on the calendar: **MAR, inferred**.
- **336 missing DF rows (I-03) and 184 DF zeros (I-05).** Always whole local days, never single hours. CISO gaps are exactly the DST switch days; ERCO and NYIS share two gap days, which points to the source not publishing a forecast. Depends on the date, not on the demand value: **MAR, inferred**.
- **What this means for M4/M7.** Any model-vs-EIA comparison must use only hours where both D and DF are trusted (≈ 520 DF hours are missing or zero, all NYIS DF zeros included). Daily totals on DST days cover 23 or 25 local hours, so aggregate in UTC. Nothing is imputed; the largest NULL share is NYIS DF 0.27 % (184 / 67,824), below the 1 % WARN line.

### 4.2 Weather
No missing weather values in our period: 0 NULL in all 3 variables × 3 locations (203,760 rows). The only known cause of `null` in Open-Meteo is the archive lag at the end of the period: the most recent days are not yet in the archive. That missingness depends on *time* (an observed variable), not on the weather value itself, so it is **MAR**. We avoid it by setting END_DATE a few days in the past. If it ever appears, the value stays NULL with `missing_not_reported`; nothing is filled in.

## 5. Flags and rules

Rules are applied in the order below; the first rule that matches a value wins.

### 5.1 demand_clean.value_mwh_flag

| Order | Flag | Meaning | Rule (with constants) | Cleaned value | Count |
|---|---|---|---|---|---|
| 1 | `missing_not_reported` | No value from the source | raw value is NULL | NULL | 23 (CISO D 22, NYIS D 1) |
| 2 | `invalid_nonpositive` | Impossible for a whole region | value ≤ 0 MWh | NULL | 196 (NYIS D 12, NYIS DF 184) |
| 3 | `invalid_dropout` | Reporting dropout | value < `DROPOUT_FRACTION` × median of its region × series (positive values) | NULL | 3 (CISO D) |
| 4 | `stuck_value` | Frozen feed | same value in ≥ `STUCK_RUN_HOURS` consecutive hours; a run breaks on a NULL or a missing hour | NULL | 0 |
| 5 | `forecast_mismatch` | Forecast far from actual | forecast rows only: DF / D < `DF_D_RATIO_MIN` or > `DF_D_RATIO_MAX`, where D for the same hour is trusted | kept | 1 (CISO DF) |
| 6 | `unusual_high` / `unusual_low` | Rare but plausible | robust z = `ROBUST_Z_SCALE` · (x − median) / MAD above `ROBUST_Z_UNUSUAL` / below −`ROBUST_Z_UNUSUAL`, per region × series, after rules 1–4 | kept | high 5,667 · low 0 |
| 7 | `ok` | None of the above | — | kept | 401,290 |

Which series is the actual and which the forecast comes from `data/mappings/series_type_role.csv` (via `map_series_type`), not from hard-coded codes. Total 407,180 = row count of `demand`.

### 5.2 weather_clean.*_flag (temperature_c, relative_humidity_pct, precipitation_mm)

| Order | Flag | Meaning | Rule (with constants) | Cleaned value | Count |
|---|---|---|---|---|---|
| 1 | `missing_not_reported` | No value from the source | raw value is NULL (all 3 variables) | NULL | 0 |
| 2 | `invalid_out_of_range` | Physically impossible | temperature outside `TEMP_MIN_C`…`TEMP_MAX_C`; humidity outside `HUMIDITY_MIN_PCT`…`HUMIDITY_MAX_PCT`; precipitation < `PRECIP_MIN_MM` | NULL | 0 |
| 3 | `stuck_value` | Frozen feed | same value in ≥ `WEATHER_STUCK_RUN_HOURS` consecutive hours (temperature, humidity; not precipitation, where long runs of 0 are normal) | NULL | 0 |
| 4 | `spike` | Implausible jump | \|temperature − previous hour\| > `TEMP_SPIKE_C_PER_HOUR`, both hours consecutive and trusted (temperature only) | NULL | 0 |
| 5 | `unusual_high` / `unusual_low` | Rare but plausible | robust z > `WEATHER_ROBUST_Z_UNUSUAL` / < −`WEATHER_ROBUST_Z_UNUSUAL`, per location × variable, after rules 1–4 (temperature, humidity; not precipitation, MAD = 0) | kept | high 64 (CISO temp) · low 288 (ERCO: 279 temp, 9 humidity) |
| 6 | `ok` | None of the above | — | kept | temp 203,417 · humidity 203,751 · precip 203,760 |
### 5.3 Constants

<!-- One bullet per constant ... -->
**Demand (`src/clean_config.py`, DEMAND section):**

| Constant | Value | Why |
...
| `WARN_NULL_SHARE` | 0.01 | ... |

**Weather (`src/clean_config.py`, WEATHER section):**

<!-- One bullet per constant in src/clean_config.py: why this value, and what changes if you move it. -->
**Weather (`src/clean_config.py`, WEATHER section):**

| Constant | Value | Why |
|---|---|---|
| `TEMP_MIN_C`, `TEMP_MAX_C` | −60, 60 °C | Beyond any recorded US city extreme; profile range −18.3…45.7 °C, 0 outside |
| `HUMIDITY_MIN_PCT`, `HUMIDITY_MAX_PCT` | 0, 100 % | Relative humidity is a percentage by definition; profile 3…100 % |
| `PRECIP_MIN_MM` | 0 mm | Negative precipitation is impossible; profile min 0.0 |
| `WEATHER_STUCK_RUN_HOURS` | 24 h | Longest natural runs: 7 h (temperature, at night) and 18 h (humidity at 100 % saturation). 24 h leaves a margin and still catches a frozen feed |
| `TEMP_SPIKE_C_PER_HOUR` | 12 °C | ≈ 3× the p99 hourly change (3.0–3.8 °C) and above the largest observed jump (10.2 °C, a real thunderstorm) |
| `WEATHER_ROBUST_Z_UNUSUAL` | 3.5 | Standard cut-off for the modified z-score (Iglewicz & Hoaglin); same as demand. Uses `ROBUST_Z_SCALE` = 0.6745 |

## 6. Mapping and identity decisions

<!-- İrem: region_location.csv and series_type_role.csv — what was matched, how
(exact → normalised key → fuzzy proposal → human decision), match counts, unmatched entries,
evidence for each decision. -->
**Demand (Tuba):**
- Thresholds are whole-series, not seasonal. CISO D 2025-07-31 21:00 UTC (11,819 MWh) is far too low for a July afternoon but stays `ok`: 48 % of the median, robust z ≈ −3.2. Only its DF row is flagged (`forecast_mismatch`).
- The causes of the CISO NULLs, the missing DF days and the NYIS DF zero days are inferred from their patterns; EIA does not document them.
- In early 2019 CISO D is often far below DF (DF/D up to ~1.9). Actuals may be under-reported then; nothing is flagged.
- A model-vs-EIA comparison (M7) is only fair on hours where both D and DF are trusted.
**Weather locations (İrem):** `data/mappings/region_location.csv` makes the location ↔ region link an explicit decision instead of the M1–M2 assumption that a shared code means the same place: NYIS → New York, ERCO → Houston, CISO → Los Angeles (decided by İrem Çakmak, 2026-11-05). Each note records the requested and returned grid coordinates (Open-Meteo snaps to the centre of its model grid cell, e.g. NYIS 40.71, −74.01 → 40.738, −74.043) and why the match is approximate. All 3 rows matched.

During the build, a copy-paste error left every row in the CSV twice. `clean.py` refused to load it ("NYIS is decided more than once") and rolled back, so the duplicate never reached the database. The file was corrected to one header and three rows.

## 7. Counts and validation

<!-- Esma: final output of python src/clean.py and python src/validate.py, each WARN classified
(world / measurement / pipeline), and how each STOP was made to fail once (validate_selftest.py). -->

### 7.1 clean.py output

### 7.2 validate.py output

### 7.3 WARN classification

### 7.4 Making every STOP fail once

## 8. What we can't say

<!-- Esma (with input from Tuba and İrem): remaining limitations and what M4 must keep in mind. -->
**Weather (İrem):**
- Robust z is computed over the whole year, so it ignores seasonality: a mild hour in July and one in January look equally normal. NYIS has 0 unusual hours because its seasonal spread (MAD 8.2 °C) is so wide.
- One city per region is an approximation. ERCO (all of Texas) and CISO (coastal Los Angeles vs. hot inland California) span several climates.
- Weather values are model output (reanalysis), not station measurements at that exact point.
- Precipitation extremes are not flagged: most hours are 0 mm, so MAD = 0 and robust z is undefined.
