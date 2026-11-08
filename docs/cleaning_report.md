# Cleaning Report — Electricity Demand & Weather Pipeline

Milestone M3 · Data cleaning and quality report.
Profile notebook: [`notebooks/m3_profile.ipynb`](../notebooks/m3_profile.ipynb) ·
Cleaned layer: [`sql/clean_schema.sql`](../sql/clean_schema.sql) ·
Code: [`src/clean.py`](../src/clean.py), [`src/clean_demand.py`](../src/clean_demand.py),
[`src/clean_weather.py`](../src/clean_weather.py), [`src/validate.py`](../src/validate.py) ·
Mappings: [`data/mappings/`](../data/mappings/)

## 1. Summary

We cleaned hourly electricity demand (EIA, series D = actual and DF = day-ahead forecast) for three
US balancing authorities — NYIS, ERCO and CISO — and hourly weather (Open-Meteo: temperature, relative
humidity, precipitation) for one representative city per region, 2019-01-01 to 2026-09-30. The most
important problems are in demand: 184 whole-day zero forecasts and 12 zero actuals in NYIS, three near-zero
dropouts and 22 unreported hours in CISO, and 336 forecast hours that never arrived, all of them in
2024–2026 and in whole days; actual-demand gaps fall on the nights clocks go back. Weather has no missing,
impossible, stuck or spiking values; 343 extreme temperatures (64 high in CISO, 279 low in ERCO) and 9 low
humidity readings are real events and are flagged and kept. The cleaned layer (`demand_clean`,
`weather_clean`) keeps every raw row with its raw value, a cleaned value (NULL where we do not trust it,
never imputed) and a flag that says why, plus two mapping tables loaded from committed CSVs. We still cannot
confirm why forecasts are missing on some days, and one implausible CISO actual value stays in the cleaned
layer because it passes every rule. No M2 changes were needed: the M2 schema and loader are unchanged since
the `m2` tag.

## 2. Profile highlights

### 2.1 Demand
Profiled in `notebooks/m3_profile.ipynb` (demand section, cells 1.1–1.8) by Tuba: 407,180 rows = 3 regions × 2 series (D = actual, DF = day-ahead forecast) over 67,920 UTC hours (2019-01-01T00Z – 2026-09-30T23Z). D medians: CISO 24,389, ERCO 47,324, NYIS 16,857 MWh. Main findings: 23 NULL values (CISO D 22, NYIS D 1); 340 hourly rows never sent (D 4, all on DST fall-back nights; DF 336, in whole local days); 196 zero values in NYIS (D 12, DF 184 — the DF zeros are 8 whole days); 3 near-zero dropout hours in CISO D. No non-zero value repeats for more than 3 hours. DF/D has a median of 0.98–1.00 and only 1 hour outside 0.5–2. The highest values are real heat waves (California, Sep 2022 and Aug 2020); there are no unusually low values.

### 2.2 Weather
Profiled in `notebooks/m3_profile.ipynb` (weather section) by İrem: 203,760 rows (3 locations × 67,920 hours), all in UTC. 0 NULL and 0 out-of-range values. Ranges: temperature −18.3…45.7 °C, humidity 3…100 %, precipitation 0…36.8 mm/h. The extremes line up with known events (Winter Storm Uri 2021, Texas 2023 and California 2024 heat waves, Hurricane Ida 2021). No stuck values (longest natural runs 7 h and 18 h) and no implausible jumps (p99 3.0–3.8 °C/h, max 10.2 °C). Robust z flags 64 hot CISO hours, 279 cold and 9 dry ERCO hours; none in NYIS.

### 2.3 Text, categories, identity and coverage

Every distinct value of `region.respondent`, `region.respondent_name`, `series_type.type_code`,
`series_type.type_name` and `location.location_code` was printed with `repr()` and compared through a
normalised key (NFC → Turkish İ/ı fold → casefold → collapsed spaces): no variants and no stray whitespace or
non-ASCII characters (notebook 3.1). Reading all 252 landed EIA files rather than the M2 table (which keeps
only the latest name) shows one unit (`megawatthours`, 1,221,540 records) and exactly one name per respondent
and per type code (3.2). All 9 Open-Meteo files return the same grid point, elevation and UTC offset for each
location (3.3). Coverage is where the profile found something (3.4–3.5):

| Series | Rows | Missing of 67,920 | Where the missing hours are |
|---|---|---|---|
| CISO D | 67,918 | 2 | 2019, 2021 (DST fall-back nights) |
| ERCO D | 67,919 | 1 | 2021 |
| NYIS D | 67,919 | 1 | 2021 |
| CISO DF | 67,800 | 120 | 2024: 49 · 2025: 48 · 2026: 23 |
| ERCO DF | 67,800 | 120 | 2025: 48 · 2026: 72 |
| NYIS DF | 67,824 | 96 | 2026: 96 |

DF is complete for 2019–2023 in all three regions; every missing forecast hour falls in 2024–2026.

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
| I-W01 | 3 Unusual | weather.temperature_c | Very hot hours for Los Angeles | CISO, 64 h (≈ ≥ 39 °C); max 45.7 °C on 2024-09-06 21:00 UTC | robust z > 3.5; dates match the Sept 2020 and Sept 2024 Southern California heat waves | real weather event | keep the value | `unusual_high` | İrem Çakmak |
| I-W02 | 3 Unusual | weather.temperature_c | Freezing hours for Houston | ERCO, 279 h (≈ ≤ −1 °C); min −10.9 °C on 2021-02-16 12:00 UTC | robust z < −3.5; Winter Storm Uri, the week the Texas grid failed | real weather event, highly relevant to demand | keep the value | `unusual_low` | İrem Çakmak |
| I-W03 | 3 Unusual | weather.relative_humidity_pct | Very dry hours for Houston | ERCO, 9 h (≈ ≤ 13 %) | robust z < −3.5 | real (dry air mass) | keep the value | `unusual_low` | İrem Çakmak |
| I-W04 | 3 Unusual | weather.precipitation_mm | Extreme hourly rainfall | NYIS 33.8 mm on 2021-09-02 01:00 UTC; CISO 18.9 mm on 2023-09-02 07:00 UTC | NYIS matches the remnants of Hurricane Ida; no event identified for CISO | real (NYIS) / unknown (CISO) | keep; not flaggable because MAD = 0 | none (`ok`) | İrem Çakmak |
| I-W05 | 6 Identity | location ↔ region | Weather point linked to region only by a shared code | 3 locations | M1–M2 assumption, never written down | implicit join | explicit mapping in `region_location.csv` (§6) | — | İrem Çakmak |
| I-W06 | 6 Identity | location.latitude / longitude | Returned coordinates differ from requested ones | 3 locations, e.g. NYIS 40.71, −74.01 → 40.738, −74.043 | M2 `location` vs `.env` | Open-Meteo snaps to its model grid cell | store the returned values; record both in the mapping note | — | İrem Çakmak |
| I-E01 | 1 Missing | demand (DF rows) | Day-ahead forecast rows absent for whole days, only in recent years | CISO 120 h, ERCO 120 h, NYIS 96 h; all in 2024–2026; 0 in 2019–2023 | year table, notebook 3.5: gaps of 48, 72 and 96 h (whole days; CISO 49 / 23 match DST-length days); same day-block shape as I-03 and I-05 | inferred: no forecast published for those days | rows cannot be created (no imputation); `validate.py` WARN "DF has as many hours as D" | — (absent rows) | Esma Gül Baş |
| I-E02 | 5 Text, categories | raw `value-units` (not loaded in M2) | The unit exists only in the raw files, not in the database | all 1,221,540 records in 252 files | notebook 3.2: one value, `megawatthours` | confirmed: EIA response field | unit recorded as a category decision in `series_type_role.csv` (`unit = MWh`) so analyses can see it | — | Esma Gül Baş |

### Checked and not found

| Family | Check | Result |
|---|---|---|
| 1 Missing | `weather.<variable> IS NULL`, 3 variables × 3 locations (İrem) | 0 |
| 2 Invalid | temperature outside −60…60 °C, humidity outside 0…100 %, precipitation < 0 mm (İrem) | 0 |
| 4 Sequence | same weather value in ≥ 24 consecutive hours (İrem) | 0 (longest: 7 h temperature, 18 h humidity at 100 %) |
| 1 Missing | `value_mwh IS NULL` in every DF series and in ERCO D (Tuba) | 0 |
| 2 Invalid | `value_mwh <= 0` in CISO and ERCO, D and DF (Tuba) | 0 |
| 2 Invalid | value below 50 % of its series median, ERCO D and DF (Tuba) | 0 |
| 3 Unusual | robust z < −3.5 in all 6 demand series (Tuba) | 0 |
| 4 Sequence | same non-zero demand value in ≥ 6 consecutive hours (Tuba) | 0 (longest: 3 h) |
| 4 Sequence | hourly temperature change > 12 °C (İrem) | 0 (largest: 10.2 °C) |
| 5 Category | every series type has one role in `series_type_role.csv` (D → actual, DF → forecast, MWh) (Tuba) | 2 of 2 matched, 0 unmatched |
| 5 Text, categories | `repr()` of every distinct respondent, respondent_name, type_code, type_name, location_code; normalised-key grouping, notebook 3.1 (Esma) | No variants, no leading/trailing/double spaces, no non-ASCII or non-NFC values |
| 5 Text, categories | distinct `value-units` across all 252 landed EIA files, notebook 3.2 (Esma) | One unit: `megawatthours` |
| 6 Identity | distinct respondent-name per respondent and type-name per type across all 252 EIA files, notebook 3.2 (Esma) | Exactly one each: no renamed entity |
| 6 Identity | grid latitude, longitude, elevation and `utc_offset_seconds` per location across all 9 Open-Meteo files, notebook 3.3 (Esma) | Identical in every file |
| 6 Identity | first and last hour of every series and location, notebook 3.4 (Esma) | All start 2019-01-01T00:00Z and end 2026-09-30T23:00Z: no entity stops where another starts |
| 1 Missing | `SELECT COUNT(*) FROM quarantine`, notebook 3.5 (Esma) | 0 |

## 4. Missing values

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

Thresholds were proposed before profiling, checked against the profile in `notebooks/m3_profile.ipynb`, and
agreed at the team meeting; two weather values (spike 12 °C/h, stuck run 24 h) were set from the profile instead
of the initial proposal. All constants live in `src/clean_config.py`.

**Demand (`src/clean_config.py`, DEMAND section, Tuba):**

| Constant | Value | Why |
|---|---|---|
| `DROPOUT_FRACTION` | 0.10 | Real low values are ≥ 47 % of their series median, the dropouts ≤ 0.4 % (notebook 1.5); 10 % sits in the empty gap between them, so any value from about 1 % to 45 % flags the same 3 hours. |
| `STUCK_RUN_HOURS` | 6 h | The longest natural run of the same non-zero value is 3 h (notebook 1.6); 6 h leaves a margin and still catches a frozen feed within a quarter of a day. |
| `DF_D_RATIO_MIN`, `DF_D_RATIO_MAX` | 0.5, 2.0 | Median DF/D is 0.98–1.00 (notebook 1.7); a forecast half or double the actual is far outside normal forecast error. Flags 1 hour (ratio 2.21); a wider band would flag none. |
| `ROBUST_Z_UNUSUAL` | 3.5 | Standard cut-off for the modified z-score (Iglewicz & Hoaglin); robust to the outliers it looks for, unlike mean ± 3 SD. |
| `ROBUST_Z_SCALE` | 0.6745 | Makes the MAD comparable to a standard deviation in the modified z-score. |
| `WARN_NULL_SHARE` | 0.01 | The largest NULL share after cleaning is 0.27 % (NYIS DF); a share above 1 % would signal a new problem rather than the known ones. |

**Weather (`src/clean_config.py`, WEATHER section, İrem):**

| Constant | Value | Why |
|---|---|---|
| `TEMP_MIN_C`, `TEMP_MAX_C` | −60, 60 °C | Beyond any recorded US city extreme; profile range −18.3…45.7 °C, 0 outside |
| `HUMIDITY_MIN_PCT`, `HUMIDITY_MAX_PCT` | 0, 100 % | Relative humidity is a percentage by definition; profile 3…100 % |
| `PRECIP_MIN_MM` | 0 mm | Negative precipitation is impossible; profile min 0.0 |
| `WEATHER_STUCK_RUN_HOURS` | 24 h | Longest natural runs: 7 h (temperature, at night) and 18 h (humidity at 100 % saturation). 24 h leaves a margin and still catches a frozen feed |
| `TEMP_SPIKE_C_PER_HOUR` | 12 °C | ≈ 3× the p99 hourly change (3.0–3.8 °C) and above the largest observed jump (10.2 °C, a real thunderstorm) |
| `WEATHER_ROBUST_Z_UNUSUAL` | 3.5 | Standard cut-off for the modified z-score (Iglewicz & Hoaglin); same as demand. Uses `ROBUST_Z_SCALE` = 0.6745 |

## 6. Mapping and identity decisions

**Weather locations (İrem):** `data/mappings/region_location.csv` makes the location ↔ region link an explicit decision instead of the M1–M2 assumption that a shared code means the same place: NYIS → New York, ERCO → Houston, CISO → Los Angeles (decided by İrem Çakmak, 2026-11-05). Each note records the requested and returned grid coordinates (Open-Meteo snaps to the centre of its model grid cell, e.g. NYIS 40.71, −74.01 → 40.738, −74.043) and why the match is approximate. All 3 rows matched.

During the build, a copy-paste error left every row in the CSV twice. `clean.py` refused to load it ("NYIS is decided more than once") and rolled back, so the duplicate never reached the database. The file was corrected to one header and three rows.

**Series types (Tuba):** `data/mappings/series_type_role.csv` records what the two EIA type codes mean:
`D` → `actual` and `DF` → `forecast`, both in MWh (decided by Tuba Arpaçay, 2026-11-06), with EIA's type names
and unit as evidence. `clean_demand.py` reads the role from this mapping instead of hard-coding the codes, so the
forecast-vs-actual rule (`forecast_mismatch`) follows the documented decision. Both codes matched exactly
(2 of 2); there were no unmatched entries and no fuzzy step was needed.

## 7. Counts and validation

### 7.1 clean.py output

```
demand_clean: 407,180 rows (raw: 407,180)
weather_clean: 203,760 rows (raw: 203,760)
demand_clean.value_mwh_flag
  entity          ok  missing_not_reported  invalid_nonpositive  invalid_dropout  stuck_value  forecast_mismatch  unusual_high  unusual_low
  CISO D      66,218                    22                    0                3            0                  0         1,675            0
  CISO DF     65,878                     0                    0                0            0                  1         1,921            0
  ERCO D      67,674                     0                    0                0            0                  0           245            0
  ERCO DF     67,591                     0                    0                0            0                  0           209            0
  NYIS D      67,167                     1                   12                0            0                  0           739            0
  NYIS DF     66,762                     0                  184                0            0                  0           878            0
weather_clean.temperature_c_flag
  entity          ok  missing_not_reported  invalid_out_of_range  stuck_value  spike  unusual_high  unusual_low
  CISO        67,856                     0                     0            0      0            64            0
  ERCO        67,641                     0                     0            0      0             0          279
  NYIS        67,920                     0                     0            0      0             0            0
weather_clean.relative_humidity_pct_flag
  CISO        67,920 · ERCO 67,911 ok + 9 unusual_low · NYIS 67,920 ok
weather_clean.precipitation_mm_flag
  CISO, ERCO, NYIS: 67,920 ok each
mappings: region_location.csv 3 rows loaded · all matched
mappings: series_type_role.csv 2 rows loaded · all matched
M2 tables unchanged: OK (hashed before and after)
STATUS: COMPLETE
```

Running `clean.py` a second time gives identical output: the build empties and rebuilds the cleaned
layer inside one transaction, so it is idempotent.

### 7.2 validate.py output

```
PASS  demand_clean row count equals demand                 407,180 = 407,180
PASS  weather_clean row count equals weather               203,760 = 203,760
PASS  no cleaned demand value <= 0 MWh                     0 found
PASS  no cleaned weather value outside its valid range     0 found (temp -60.0..60.0 C, humidity 0.0..100.0 %, precip >= 0.0 mm)
PASS  untrusted demand flags carry a NULL cleaned value    0 rows break this
PASS  foreign_key_check                                    OK
PASS  every location and series type is mapped             0 unmapped
PASS  NULL share at most 1% per region x series            all within
PASS  every region and location has data in the latest hour latest 2026-09-30T23:00Z; 6 of 6
WARN  DF has as many hours as D in every region            hours missing in DF: CISO 118, ERCO 119, NYIS 95
PASS  no stuck_value flags in demand_clean                 0 rows
WARN  no forecast_mismatch flags in demand_clean           1 rows

10 PASS · 2 WARN · 0 STOP
```

### 7.3 WARN classification

| WARN | Detail | World, measurement or pipeline? | Why |
|---|---|---|---|
| DF has as many hours as D | CISO 118, ERCO 119, NYIS 95 fewer DF hours | **Source (measurement)** — not our pipeline | M1 fetched every page until `response.total` was reached and the M1 counts match M2 exactly; M2 key tests found no duplicates. The gaps are whole days in 2024–2026 (I-E01): the provider did not publish a forecast for those days. |
| No forecast_mismatch flags | 1 hour: CISO 2025-07-31T21Z, D = 11,819, DF = 26,135 (ratio 2.21) | **Measurement** — most likely in the *actual* value | A July afternoon at 48 % of the CISO median is implausible, but it is above the 10 % dropout threshold, so the D value is kept (see §8). |

### 7.4 Making every STOP fail once

`src/validate_selftest.py` copies `data/grid.db` to a temporary folder, breaks one thing per scenario,
runs `validate.py` on the copy and requires exit status 1 and the matching STOP line. The real
database is never touched. Output of the final run: **7/7 STOP checks failed when they should.**

| STOP check | How it was broken on the copy | Result |
|---|---|---|
| demand_clean row count equals demand | deleted one row from `demand_clean` | STOP 407,179 != 407,180, exit 1 |
| weather_clean row count equals weather | deleted one row from `weather_clean` | STOP 203,759 != 203,760, exit 1 |
| no cleaned demand value <= 0 MWh | set one row to raw = cleaned = −5, flag `ok` | STOP 1 found, exit 1 |
| no cleaned weather value outside its valid range | set one humidity value to 150 %, flag `ok` | STOP 1 found, exit 1 |
| untrusted demand flags carry a NULL cleaned value | set flag `invalid_dropout` but kept the value (schema CHECKs switched off on the copy) | STOP 1 row breaks this, exit 1 |
| foreign_key_check | inserted a location pointing at a non-existent region (foreign keys off on the copy) | STOP 1 problem, exit 1 |
| every location and series type is mapped | deleted one row from `map_series_type` | STOP 1 unmapped, exit 1 |

## 8. What we can't say

**Weather (İrem):**
- Robust z is computed over the whole year, so it ignores seasonality: a mild hour in July and one in January look equally normal. NYIS has 0 unusual hours because its seasonal spread (MAD 8.2 °C) is so wide.
- One city per region is an approximation. ERCO (all of Texas) and CISO (coastal Los Angeles vs. hot inland California) span several climates.
- Weather values are model output (reanalysis), not station measurements at that exact point.
- Precipitation extremes are not flagged: most hours are 0 mm, so MAD = 0 and robust z is undefined.

**Demand (Tuba):**
- Thresholds are whole-series, not seasonal. CISO D 2025-07-31 21:00 UTC (11,819 MWh) is far too low for a July afternoon but stays `ok`: 48 % of the median, robust z ≈ −3.2. Only its DF row is flagged (`forecast_mismatch`).
- The causes of the CISO NULLs, the missing DF days and the NYIS DF zero days are inferred from their patterns; EIA does not document them.
- In early 2019 CISO D is often far below DF (DF/D up to ~1.9). Actuals may be under-reported then; nothing is flagged.
- A model-vs-EIA comparison (M7) is only fair on hours where both D and DF are trusted.

**Coverage (Esma):**
- DF exists for every hour of 2019–2023 but misses whole days in 2024–2026 (I-E01), and NYIS DF has 8 zero days
  (I-05). M4 must compare DF with D only on hours where both are trusted, and report how many hours each year
  contributes: recent years have fewer comparable hours.
- The repeated autumn hour is missing from D on DST fall-back nights (I-02); hour-of-day averages around those
  nights rest on one fewer observation. Aggregate in UTC, not local time.
- The quarantine table is empty, so no record was set aside; every problem above is inside the cleaned tables as a flag.
