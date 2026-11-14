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

_(Esma — both queries, both results per region, 2–3 sentences explaining the difference.)_

## 3. The question and its summary

_(Tuba — the question in one sentence; the summary that answers it and why; results with n; the alternative summary
and whether it ranks the regions the same way.)_

## 4. What the data is made of

### 4.1 Shape

_(Tuba — histogram with the chosen bin width and why, ECDF or log scale; overall and per region; what the shape means
for the summary in §3.)_

### 4.2 Coverage, coverage rules and the flag filter

_(Esma — coverage table; the coverage rule for every aggregate and why; one result with and without the rule; one key
result with two flag filters and the one we report.)_

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
