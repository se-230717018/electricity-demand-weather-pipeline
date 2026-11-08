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

### 2.2 Weather
Profiled in `notebooks/m3_profile.ipynb` (weather section) by İrem: 203,760 rows (3 locations × 67,920 hours), all in UTC. 0 NULL and 0 out-of-range values. Ranges: temperature −18.3…45.7 °C, humidity 3…100 %, precipitation 0…36.8 mm/h. The extremes line up with known events (Winter Storm Uri 2021, Texas 2023 and California 2024 heat waves, Hurricane Ida 2021). No stuck values (longest natural runs 7 h and 18 h) and no implausible jumps (p99 3.0–3.8 °C/h, max 10.2 °C). Robust z flags 64 hot CISO hours, 279 cold and 9 dry ERCO hours; none in NYIS.

### 2.3 Text, categories, identity and coverage

## 3. Issues register

| ID | Family | Table.column | What | Where / when / how many | Evidence | Cause | Decision | Flag | Investigated by |
|---|---|---|---|---|---|---|---|---|---|
<!-- Tuba: demand rows I-01 … I-09 -->
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
| 4 Sequence | hourly temperature change > 12 °C (İrem) | 0 (largest: 10.2 °C) |
## 4. Missing values

<!-- Per substantial pattern: where/when, mechanism (MCAR / MAR / MNAR) with evidence,
what it means for M4 (which comparisons are unsafe, what to exclude or treat separately). -->

### 4.1 Demand

### 4.2 Weather
No missing weather values in our period: 0 NULL in all 3 variables × 3 locations (203,760 rows). The only known cause of `null` in Open-Meteo is the archive lag at the end of the period: the most recent days are not yet in the archive. That missingness depends on *time* (an observed variable), not on the weather value itself, so it is **MAR**. We avoid it by setting END_DATE a few days in the past. If it ever appears, the value stays NULL with `missing_not_reported`; nothing is filled in.

## 5. Flags and rules

Rules are applied in the order below; the first rule that matches a value wins.

### 5.1 demand_clean.value_mwh_flag

| Order | Flag | Meaning | Rule (with constants) | Cleaned value | Count |
|---|---|---|---|---|---|

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
