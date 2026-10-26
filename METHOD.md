# METHOD

## 1. Sample construction

**Universe.** Every CIK that filed a 10-K, 10-K/A, 20-F, 20-F/A or 40-F between
2010-01-01 and 2025-12-31 in the SEC Financial Statement Data Sets. The frame is
the filing population, not today's ticker list, so delisted firms stay in. That
removes the survivorship filter but not survivorship bias in the tag coverage:
a firm that stopped filing in 2015 contributes 2010–2015 only.

**Pipeline.** `download_sec.py` → `build_panel.py` → `build_quarterly.py` →
`analysis_quarterly.py` → `analysis.py` → `figures.py`, orchestrated by
`run_all.py`. The raw cache is 64 annual quarterly extracts plus 16 quarterly
shock extracts; after the first download the whole pipeline runs offline.

**Rules applied, in order** (all counts in `outputs/tables/attrition.csv` and
`results.json → attrition`):

1. forms: 10-K, 10-K/A, 20-F, 20-F/A, 40-F, 40-F/A only.
2. taxonomy: `us-gaap` only. IFRS (`ifrs-full`) filers are excluded and counted.
   This drops most 20-F filers that report under IFRS.
3. facts: consolidated only (`segments` and `coreg` empty); `uom = USD`.
4. one value per `(cik, tag, end, qtrs)`: **latest `filed` wins**.
5. ordered tag fallbacks per concept (`src/tags.py`, version **2.0.0**); the
   winning tag is recorded in every panel row (`tag_revenue`, `tag_ar`, …) and
   counted in `outputs/tables/tag_usage.csv`.
6. balance sheet = `qtrs == 0`, income statement = `qtrs == 4`; merged only on an
   **identical period end**.
7. fiscal year = issuer's `fy` label for that period end (January year-ends are
   labelled the way the company labels them).
8. window 2010–2024.
9. `revenue > 0`, `COGS > 0`, and non-missing `AR`, `inventory`, `AP`. The
   missing-input drop is decomposed by item in
   `outputs/tables/attrition_missing_items.csv`: of 76,218 rows, inventory is
   missing in 63,376, COGS in 55,285, AR in 47,795, AP in 28,551 and revenue in
   26,073; 56,799 rows (74.5%) miss more than one input, so the item counts
   overlap.
10. exclude SIC 6000–6999 (financials, includes real estate 6500–6599) and
    4900–4999 (utilities).
11. at least 3 usable fiscal years per firm.

The main sample is **26,974 firm-years / 3,320 firms**. Of these, **24,272
firm-years / 3,010 firms** have a clean trade payable (direct or reconstructed)
and form the headline sample.

## 2. Measures

Point-in-time balances at fiscal year end, flows for the fiscal year:

```
DSO = 365 * AR  / revenue
DIO = 365 * INV / COGS
DPO = 365 * AP_clean / COGS
CCC = DSO + DIO - DPO
```

`AP_clean` is the trade payable, not the combined AP-plus-accruals line:

```
AP_clean = AccountsPayableCurrent or AccountsPayableTradeCurrent          -> direct
         = AccountsPayableAndAccruedLiabilitiesCurrent
           - AccruedLiabilitiesCurrent, if positive                       -> reconstructed
         = missing                                                        -> fallback_contaminated
```

The reconstructed residual is kept only when positive; the contaminated rows are
excluded from the clean headline and from every regression that uses `ccc_clean`.
The all-row mixed-AP measure `ccc` is retained as a sensitivity and is reported
in `results.json → tag_sensitivity` and `persistence_all_rows_mixed_ap`.

Robustness versions use average balances `mean(t, t-1)` and an alternative DPO
denominator (revenue). Additional variables: gross margin, ROA (net income /
assets), cash/assets, current ratio, `(AR+INV-AP)/revenue`, ΔCCC, the
within-firm standard deviation of CCC, **capital intensity** (net PP&E / assets,
with a non-current-asset-share fallback) and **asset turnover** (revenue /
assets). The last two are the controls added in mapping 2.0.0.

Lags are used only when consecutive fiscal-year ends are 350–380 days apart, so
a firm that changes its year-end does not generate a fake 15-month "year".

## 3. Estimation

**Structure.** Median and IQR of CCC by 2-digit SIC; share of firms with a
negative CCC by industry and year; variance decomposition
(`SS_between / SS_total`) for industry and for firm. These are **two overlapping
partitions**, not one decomposition: between-industry (6.24%) and
within-industry (93.76%) is one split; between-firm (64.54%) and within-firm
(35.46%) is the other. They are reported separately and never summed.

**Persistence.** Two estimators bound the AR(1) coefficient; neither is the
parameter. The **pooled** model is
`CCC_it = a + rho·CCC_i,t-1 + year FE + e_it`, SEs clustered by firm. It omits
time-invariant firm traits, so persistent between-firm differences are absorbed
into rho and the estimate is **biased upward** as a within-firm speed. The
**firm-FE** model adds firm fixed effects; with a lagged dependent variable and
T ≈ 10 it is **Nickell-biased downward**. The headline result is therefore a
range: pooled rho = 0.688 (half-life 1.86 years) and firm-FE rho = 0.243
(half-life 0.49 years), with the truth between them. An **Anderson–Hsiao IV**
(first difference, year dummies, lagged difference instrumented by the
twice-lagged level) gives 0.413 (SE 0.145). Half-life `ln(0.5)/ln(rho)`;
`1 - rho` from the pooled model is not interpreted as a within-firm adjustment
speed. Same models for DSO, DIO, DPO (clean AP for DPO), and by 2-digit
industry. The industry table is labelled **pooled (between + within firm)**; a
firm-FE rho is reported alongside it for every industry where the within
transformation is estimable. Both the current and the lagged value are bounded
to `|x| <= 3,650` days, because a firm-year that passes the screen can still
follow an uninterpretable one.

**CCC and profitability.**
`ROA_it = a_i + d_t + b·CCC_it + c·log(assets)_it + d·gross_margin_it + k·capital_intensity_it + l·asset_turnover_it + e_it`,
firm and year FE, SEs clustered by firm. Standardised coefficient =
`b · sd(CCC) / sd(ROA)` on the estimation sample. The headline is the version
with both capital controls; the version without them is reported as a
sensitivity. The pipeline also estimates:

- **industry × year fixed effects**, to absorb sector-specific shocks;
- a **between-firm** regression on firm means with SIC fixed effects;
- **component** regressions replacing CCC with DSO, DIO and DPO separately.

**Annual shock cross-sections** (descriptive, not causal):

```
y_i = a + b·CCC_i,pre + industry FE + e_i
```

- FY2020: `y` = revenue growth FY2019→FY2020, ROA FY2020, cash/assets FY2020,
  inventory write-down / COGS FY2020; `CCC_i,pre` = clean CCC in FY2019.
- FY2022: `y` = gross-margin change FY2021→FY2022, ROA FY2022, write-down /
  COGS FY2022; `CCC_i,pre` = clean CCC FY2021.

HC1 standard errors. Quintile tables are in `results.json` and drive the
figures. The year is the issuer's fiscal-year label, not a calendar year, so the
same code is also run on December year-ends only (29.0% of FY2020 and 28.3% of
FY2022 rows are non-December); that calendar-aligned check is
`results.json.shock_window`.

**Quarterly 10-Q shock panel.** `build_quarterly.py` constructs one row per
firm-quarter from 10-Q facts, with calendar labels derived from the period end:

```
quarter = calendar quarter of ddate
flows   = qtrs == 1 (revenue, COGS, net income, write-down)
stocks  = qtrs == 0 (AR, inventory, AP, cash, assets, PP&E)
```

For each shock year `S ∈ {2020, 2022}`, outcomes are measured in period ends
inside calendar Q1–Q3 of `S` (a December period end is reported in the 10-K, not
the 10-Q, so Q4 would mix a thin non-December subsample into the last cell). The
exposure is the annual clean-AP CCC of fiscal year `S − 1`, **not** the 10-Q's
own `fy` label: a December filer's 2020Q1 10-Q carries `fy = 2020`, and joining
on it would put the outcome and the exposure in the same fiscal year. The model is

```
y_iq = a + b·CCC_i,pre + industry FE + calendar-quarter FE + e_iq
```

with SEs clustered by firm. YoY outcomes match each quarter to its own period
end one year earlier (within 45 days), which is unique even when a transition
period shares a fiscal-year/period label. Per-quarter cross-sections are also
written to `outputs/tables/quarterly_shock_coefficients.csv`. The tests are
descriptive: 24 quarter-outcome cells, no multiple-testing correction.

**Robustness.** Average balances; no winsorization; revenue-denominated DPO;
negative-CCC-only and non-negative-CCC-only; balanced 2015–2024 panel; dropping
|CCC|>365; 3-digit vs 2-digit SIC FE; no controls (firm+year FE only); only
firm-years where the charter's preferred tag supplied every input (including
`InventoryNet` and a direct trade-AP tag); including financials/utilities
(`panel_full`). The number of main-sample specifications significant at 5% is
computed from the p-values in `robustness_ccc_roa`, not typed:
`robustness_summary.n_significant_p05` over `n_specs_main_sample` (currently
**9 of 13**; all 13 coefficients are positive).

## 4. Data-quality guards

- **Plausibility screen for estimation** (see DECISIONS D-06): `|CCC| <= 3,650`,
  assets ≥ $1m, revenue ≥ $1m. XBRL scale errors (Assets in millions, COGS at
  1/1,000) otherwise dominate means and OLS. The screen drops 1,040 clean-AP
  rows (4.28%); headline medians are computed *without* this screen.
- **Winsorization** at 1/99 within industry-year, with pooled bounds for thin
  cells (<50 observations); applied to CCC and ROA in every regression.
- **Trade-AP contamination is reconstructed or excluded, not averaged in.**
  Direct trade AP is used as reported; the combined AP-plus-accruals tag is
  split only where `AccruedLiabilitiesCurrent` exists and the residual is
  positive (71 rows, 2.56% of fallback rows); the remaining 2,702 rows are
  flagged `fallback_contaminated` and excluded from `ccc_clean`. The all-row
  mixed measure is reported as a sensitivity: median CCC 75.42 versus 80.38 on
  clean AP.
- **Write-down outcome is measured, with coverage disclosed.** 4,657 panel rows
  (17.3%) / 959 firms report `InventoryWriteDown` or `InventoryImpairmentLoss`;
  the coefficient is estimated on that selected subsample.
- **Internal spot check** of Fastenal, Walmart and Apple against the
  `companyfacts` API, tag by tag, in `outputs/validation.json`. It checks parsing
  and period alignment for three issuers; it does not validate the tag choice,
  the fallback order or coverage of the wider panel.

## 5. Reproduction

```
python src/run_all.py          # download (cached) → panels → validation → results → figures
python src/run_all.py --test   # same + pytest
python src/analysis.py         # re-estimate annual results only
python src/analysis_quarterly.py  # re-estimate the quarterly shock tests only
```

`outputs/run_log.json` records each step's status and wall-clock time.
