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

### 2.3 Text, categories, identity and coverage

## 3. Issues register

| ID | Family | Table.column | What | Where / when / how many | Evidence | Cause | Decision | Flag | Investigated by |
|---|---|---|---|---|---|---|---|---|---|
<!-- Tuba: demand rows I-01 … I-09 -->
<!-- İrem: weather + identity rows I-10 … I-19 -->
<!-- Esma: text / category / coverage rows I-20 … -->

### Checked and not found

| Family | Check | Result |
|---|---|---|
<!-- Every family 1–6 must appear at least once, here or in the register. Write the exact check,
e.g. "SELECT COUNT(*) FROM weather WHERE relative_humidity_pct > 100" → 0. -->

## 4. Missing values

<!-- Per substantial pattern: where/when, mechanism (MCAR / MAR / MNAR) with evidence,
what it means for M4 (which comparisons are unsafe, what to exclude or treat separately). -->

### 4.1 Demand

### 4.2 Weather

## 5. Flags and rules

Rules are applied in the order below; the first rule that matches a value wins.

### 5.1 demand_clean.value_mwh_flag

| Order | Flag | Meaning | Rule (with constants) | Cleaned value | Count |
|---|---|---|---|---|---|

### 5.2 weather_clean.*_flag (temperature_c, relative_humidity_pct, precipitation_mm)

| Order | Flag | Meaning | Rule (with constants) | Cleaned value | Count |
|---|---|---|---|---|---|

### 5.3 Constants

<!-- One bullet per constant in src/clean_config.py: why this value, and what changes if you move it. -->

## 6. Mapping and identity decisions

<!-- İrem: region_location.csv and series_type_role.csv — what was matched, how
(exact → normalised key → fuzzy proposal → human decision), match counts, unmatched entries,
evidence for each decision. -->

## 7. Counts and validation

<!-- Esma: final output of python src/clean.py and python src/validate.py, each WARN classified
(world / measurement / pipeline), and how each STOP was made to fail once (validate_selftest.py). -->

### 7.1 clean.py output

### 7.2 validate.py output

### 7.3 WARN classification

### 7.4 Making every STOP fail once

## 8. What we can't say

<!-- Esma (with input from Tuba and İrem): remaining limitations and what M4 must keep in mind. -->
