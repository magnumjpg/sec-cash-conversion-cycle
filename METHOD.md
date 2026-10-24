# METHOD

## 1. Sample construction

**Universe.** Every CIK that filed a 10-K, 10-K/A, 20-F/A or 40-F between
2010-01-01 and 2025-12-31 in the SEC Financial Statement Data Sets. The frame is
the filing population, not today's ticker list, so delisted firms stay in. That
removes the survivorship filter but not survivorship bias in the tag coverage:
a firm that stopped filing in 2015 contributes 2010–2015 only.

**Pipeline.** `download_sec.py` → `build_panel.py` → `analysis.py` →
`figures.py`, orchestrated by `run_all.py`. The raw cache is 64 quarterly
extracts; after the first download the whole pipeline runs offline.

**Rules applied, in order** (all counts in `outputs/tables/attrition.csv` and
`results.json → attrition`):

1. forms: 10-K, 10-K/A, 20-F, 20-F/A, 40-F, 40-F/A only.
2. taxonomy: `us-gaap` only. IFRS (`ifrs-full`) filers are excluded and counted.
   This drops most 20-F filers that report under IFRS.
3. facts: consolidated only (`segments` and `coreg` empty); `uom = USD`.
4. one value per `(cik, tag, end, qtrs)`: **latest `filed` wins**.
5. ordered tag fallbacks per concept (`src/tags.py`, version 1.0.0); the winning
   tag is recorded in every panel row (`tag_revenue`, `tag_ar`, …) and counted
   in `outputs/tables/tag_usage.csv`.
6. balance sheet = `qtrs == 0`, income statement = `qtrs == 4`; merged only on an
   **identical period end**.
7. fiscal year = issuer's `fy` label for that period end (January year-ends are
   labelled the way the company labels them).
8. window 2010–2024.
9. `revenue > 0`, `COGS > 0`, and non-missing `AR`, `inventory`, `AP`.
10. exclude SIC 6000–6999 (financials, includes real estate 6500–6599) and
    4900–4999 (utilities).
11. at least 3 usable fiscal years per firm.

## 2. Measures

Point-in-time balances at fiscal year end, flows for the fiscal year:

```
DSO = 365 * AR  / revenue
DIO = 365 * INV / COGS
DPO = 365 * AP  / COGS
CCC = DSO + DIO - DPO
```

Robustness versions use average balances `mean(t, t-1)` and an alternative DPO
denominator (revenue). Additional variables: gross margin, ROA (net income /
assets), cash/assets, current ratio, `(AR+INV-AP)/revenue`, ΔCCC, and the
within-firm standard deviation of CCC.

Lags are used only when consecutive fiscal-year ends are 350–380 days apart, so
a firm that changes its year-end does not generate a fake 15-month "year".

## 3. Estimation

**Structure.** Median and IQR of CCC by 2-digit SIC; share of firms with a
negative CCC by industry and year; variance decomposition
(`SS_between / SS_total`) for industry and for firm.

**Persistence.** `CCC_it = a + rho·CCC_i,t-1 + year FE + e_it`, SEs clustered by
firm. Half-life `ln(0.5)/ln(rho)`. No firm FE in the headline (with a lagged
dependent variable and T≈10 the firm-FE estimate is Nickell-biased); the
firm-FE version is reported as a bound. Same model for DSO, DIO, DPO, and by
2-digit industry. Both the current and the lagged value are bounded to
`|x| <= 3,650` days, because a firm-year that passes the screen can still follow
an uninterpretable one.

**CCC and profitability.**
`ROA_it = a_i + d_t + b·CCC_it + c·log(assets)_it + d·gross_margin_it + e_it`,
firm and year FE, SEs clustered by firm. Standardised coefficient =
`b · sd(CCC) / sd(ROA)` on the estimation sample.

**Shock cross-sections** (descriptive, not causal):

```
y_i = a + b·CCC_i,pre + industry FE + e_i
```

- 2020: `y` = revenue growth 2019→2020, ROA 2020, cash/assets 2020;
  `CCC_i,pre` = CCC in FY2019.
- 2022: `y` = gross-margin change 2021→2022, ROA 2022; `CCC_i,pre` = CCC FY2021.

HC1 standard errors. Quintile tables are in `results.json` and drive the
figures.

**Robustness.** Average balances; no winsorization; revenue-denominated DPO;
negative-CCC-only and non-negative-CCC-only; balanced 2015–2024 panel; dropping
|CCC|>365; 3-digit vs 2-digit SIC FE; no controls (firm+year FE only); only
firm-years where the charter's preferred tag supplied every input; including
financials/utilities (`panel_full`).

## 4. Data-quality guards

- **Plausibility screen for estimation** (see DECISIONS D-06): `|CCC| <= 3,650`,
  assets ≥ $1m, revenue ≥ $1m. XBRL scale errors (Assets in millions, COGS at
  1/1,000) otherwise dominate means and OLS. Headline medians are computed
  *without* this screen.
- **Winsorization** at 1/99 within industry-year, with pooled bounds for thin
  cells (<50 observations); applied to CCC and ROA in every regression.
- **Cross-source validation** of Fastenal, Walmart and Apple against the
  `companyfacts` API, tag by tag, in `outputs/validation.json`.

## 5. Reproduction

```
python src/run_all.py          # download (cached) → panel → validation → results → figures
python src/run_all.py --test   # same + pytest
python src/analysis.py         # re-estimate only
```

`outputs/run_log.json` records each step's status and wall-clock time.
