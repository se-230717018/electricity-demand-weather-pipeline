# Exploratory Analysis — Electricity Demand & Weather Pipeline

Milestone M4 · Notebook: [`notebooks/m4_eda.ipynb`](../notebooks/m4_eda.ipynb) · Figures: [`figures/`](../figures/) ·
Helpers: [`src/explore.py`](../src/explore.py)

> **Who writes what** (delete this box before the final commit). Edit only your own sections, in this order:
> Tuba (§3, §4 shape part, §7) → İrem (§5, §6) → Esma (§1, §2, §4 coverage part, §8 lists, §9).
> `git pull` before you start and again before you push. Add your own rows to the findings table in §8.

## 1. Summary

_(Esma — 5–6 sentences: the question, the answer as far as exploration can give it, how sure we are, the main thing
that could change it. M3 issues fixed since the m3 tag: none / list.)_

## 2. Raw versus cleaned

EIA's day-ahead forecast error (MAPE of DF against actual demand D, UTC hours) computed twice
(notebook 2.1, figure `f6_raw_vs_clean_mape.png`):

| Region | Raw M2 tables: hours | Raw MAPE | Cleaned layer: hours | Cleaned MAPE | Change |
|---|---|---|---|---|---|
| NYIS | 67,810 | 2.92 % | 67,626 | 2.66 % | −0.26 pts |
| ERCO | 67,799 | 2.43 % | 67,799 | 2.43 % | 0.00 pts |
| CISO | 67,776 | 8.61 % | 67,773 | 5.13 % | −3.48 pts |

*Raw* = the M2 tables as loaded, every hour where both values exist and actual demand is not zero.
*Cleaned* = `demand_clean`, both values kept by cleaning (flags `ok`, `unusual_high`, `unusual_low`,
`forecast_mismatch`).

Cleaning changes the key number most in CISO, and the whole change comes from **three hours**: the raw and
cleaned counts differ by exactly 3, the near-zero actual values of 2019-12-20 (14, 91 and 96 MWh, M3 issue I-06).
Against forecasts of about 24,000 MWh their percentage errors run to tens of thousands of percent, so three hours out
of 67,776 lift the mean by 3.5 points. In NYIS the 184 hours with a forecast published as 0 (M3 I-05) each count as a
100 % error in the raw tables (184 × 100 % / 67,810 ≈ 0.27 points). ERCO has no flagged values, so nothing changes. The
raw ranking (CISO far behind) is mostly an artefact; after cleaning, CISO's forecast is still the least accurate of the
three, but by about 2.5 points, not 6.

## 3. The question and its summary

_(Tuba — the question in one sentence; the summary that answers it and why; results with n; the alternative summary
and whether it ranks the regions the same way.)_

## 4. What the data is made of

### 4.1 Shape

_(Tuba — histogram with the chosen bin width and why, ECDF or log scale; overall and per region; what the shape means
for the summary in §3.)_

### 4.2 Coverage, coverage rules and the flag filter

**Coverage.** Share of possible UTC hours with a trusted D–DF pair, per region and year (notebook 2.4; possible
hours: 8,760, or 8,784 in leap years and 6,552 for 2026 up to 30 September):

| Region | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|
| NYIS | 99.20 | 100.00 | 99.98 | 100.00 | 100.00 | 99.44 | 99.45 | 98.09 |
| ERCO | 100.00 | 100.00 | 99.99 | 100.00 | 100.00 | 100.00 | 99.45 | 98.90 |
| CISO | 99.85 | 99.97 | 99.93 | 99.97 | 99.98 | 99.44 | 99.45 | 99.65 |

Coverage is high everywhere, but the monthly view (figure `f2_forecast_coverage.png`) shows where it is thin: the
lowest month is 96.6 % in 2019–2023 and 93.2 % in 2024–2026 (CISO, November 2024). The gaps are whole days — days
with no published forecast (M3 I-03, I-E01) and NYIS forecast-zero days (I-05) — so recent years contribute fewer
comparable hours, and a monthly average for an affected month rests on one to three fewer days.

**Coverage rule.** A daily aggregate counts only with at least `DAILY_MIN_HOURS = 20` trusted hours. Twenty keeps the
23- and 25-hour DST days and days missing a single hour, but drops days where most hours are absent. A monthly
aggregate needs `MONTHLY_MIN_DAYS = 25` complete days. With and without the daily rule, the mean daily MAPE is:
NYIS 2.657 % (2,830 days) vs 2.658 % (2,805 days kept); ERCO 2.427 % vs 2.430 % (2,821 of 2,829); CISO 5.130 % vs
5.122 % (2,821 of 2,829). The rule changes almost nothing *because* the gaps are whole days: a day is either complete
or absent, rarely half-filled. We keep the rule so that a future partial day cannot slip into a daily average.

**Flag filter.** The key number under two filters: our main filter (every value cleaning kept, including real
extremes flagged `unusual_*`) and `ok` only:

| Region | Main filter: hours | MAPE | `ok` only: hours | MAPE | Change |
|---|---|---|---|---|---|
| NYIS | 67,626 | 2.658 % | 66,674 | 2.657 % | −0.001 pts |
| ERCO | 67,799 | 2.429 % | 67,533 | 2.432 % | +0.004 pts |
| CISO | 67,773 | 5.129 % | 65,602 | 5.154 % | +0.025 pts |

Dropping the flagged extremes removes up to 2,171 hours (CISO, mostly summer peaks) but moves the MAPE by at most
0.03 points, and in CISO it *raises* it: EIA forecasts the extreme-demand hours no worse than ordinary hours. We report
the main filter, because M3 established that the `unusual_*` values are real events, and leaving out the hottest hours
would bias any temperature analysis.

## 5. Time

_(İrem — the clock and why; edges; patterns at two time scales; calendar / holidays.)_

## 6. Relationships

_(İrem — binned medians / scatter first; Pearson and Spearman and which describes the picture better; what drives it;
what is left when it is removed; within-period comparison.)_

## 7. The comparison

_(Tuba — the difference with a 95% interval: unit (days), method (bootstrap, N_BOOT, seed); composition check; how
many comparisons we looked at before choosing this one.)_

## 8. Findings

Every member adds at least two rows. Label: *exploratory* (seen in this data, not yet tested elsewhere) or
*confirmed* (holds by construction or arithmetic, or tested on held-out data).

| ID | Finding | Evidence | Label | What would change it | Explored by |
|---|---|---|---|---|---|
| F-01 | _(one sentence)_ | _(figure / query)_ | _exploratory_ | _(…)_ | _(name)_ |

### Back to cleaning

_(Anything exploration showed the cleaned layer got wrong or missed — also added to `docs/cleaning_report.md` and fixed in
`src/clean.py`. "None found" is fine if true.)_

### Forward to modelling

_(Questions M7 should answer; what M7 must be careful about: thin periods, leakage, seasonality, variables that only exist
after the outcome.)_

## 9. What we can't say

_(Esma, with input from Tuba and İrem — limits of the data, thin groups, exploratory findings.)_
