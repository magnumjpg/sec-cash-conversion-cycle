# LIMITATIONS

## What this does not prove

- **No causality.** CCC is chosen jointly with industry, growth, bargaining
  power, supplier terms and product mix. Every coefficient here is an
  association. In this sample the CCC–ROA coefficient is *positive*; that does
  not mean that lengthening the CCC raises ROA, any more than a negative
  coefficient would license the opposite.
- **No dollar value of a CCC day.** That requires a cost of capital, a financing
  mix and an assumption about what happens to the freed cash. The baseline specification
  forbids it and nothing in this pipeline identifies it.
- **No market test.** Without CRSP/Compustat there are no returns, no abnormal
  performance, no event windows. "Resilience" is measured with accounting
  outcomes only.
- **The annual shock exercises are cross-sections.** They are one observation
  per firm, with industry fixed effects. They cannot separate a CCC effect from
  an unobserved firm characteristic correlated with CCC (customer concentration,
  product durability, channel mix). The quarterly panel adds repeated
  observations but keeps a single pre-shock annual exposure and is still
  descriptive.

## Data limitations

- **Coverage, not representativeness.** The panel is the population of annual
  SEC filers with usable trade working capital. It is not a random sample of US
  firms, and it under-represents service firms (no inventory → no DIO), which is
  exactly where negative CCC is most common. The share of negative-CCC firms is
  therefore a lower bound for the whole listed universe.
- **Trade-AP reconstruction is deliberately limited.** The clean-AP headline
  covers 24,272 of 26,974 firm-years (89.98%). The combined
  `AccountsPayableAndAccruedLiabilitiesCurrent` tag is split only when
  `AccruedLiabilitiesCurrent` exists and the residual is positive: that recovers
  **71 rows, 2.56% of the 2,773 fallback rows**. The other **2,702 rows are
  excluded** as `fallback_contaminated`. If those firms differ systematically,
  the clean median (80.38 days) is not the all-firm median. The all-row mixed
  sensitivity is 75.42 days, and the two bound the level from below/above
  depending on the direction of the accrual.
- **The combined tag is a different concept.** The contaminated rows have a
  median CCC of 3.69 days and DPO of 112.39, against 80.38 and 47.91 on clean
  AP; 48.22% of them have negative CCC against 11.64% on clean AP. The headline
  negative share is therefore 11.64%, not the 15.33% that mixing concepts would
  produce. The fallback is still visible in `tag_ap` and in `tag_usage.csv` for
  provenance; it is just not treated as a trade payable in the headline.
- **XBRL scale errors.** Roughly 4% of clean-AP rows are dropped *for
  estimation* because assets or revenue are tagged at the wrong scale. This is a
  real property of the source, not of this pipeline. Headline medians keep those
  rows; the dropped group has a much lower median CCC (−108.29 vs 82.05), so the
  screen is not neutral.
- **20-F / IFRS.** IFRS filers are excluded outright. US-GAAP 20-F filers remain.
  The panel is therefore US-listed, mostly US-domiciled.
- **Restatements.** "Latest filing wins" only over filings up to 2025-12-31.
  Later amendments are not captured until the cache is extended.
- **Write-down coverage is selected.** 4,657 annual rows (17.3%) / 959 firms
  report `InventoryWriteDown` or `InventoryImpairmentLoss`. The outcome is
  estimated on that minority; firms that do not report the tag are not in the
  regression. The quarterly write-down outcome is even thinner: 187 and 194
  observations in the 2020/2022 pooled tests. A null coefficient there is a
  statement about the reporting subsample, not about the population.
- **The quarterly panel is short.** 2019q1–2022q4 covers a pre-shock 2019
  balance, the 2020 shock, a pre-shock 2021 balance and the 2022 shock. It cannot
  extend the quarterly analysis to 2023–2024, and it does not include Q4 because
  a December period end is filed in the 10-K, not the 10-Q.
- **Textbook CCC caveats.** Revenue is a flow including markup, COGS is a cost;
  DSO and DIO are not strictly comparable in units. This is standard practice and
  it is why the ratios are used as *relative* measures, not as cash amounts.
- **Fiscal-year labels.** The annual year is the issuer's label. Firms with
  different year-ends in the same "year" can be up to 11 months apart. This is
  why the annual shock tables say FY2020/FY2022 and why the quarterly panel uses
  calendar period ends instead.

## Econometric limitations

- **Short panels and two biased persistence estimators.** T ≈ 10. The pooled
  AR(1) excludes firm FE, so it is biased **upward** by persistent between-firm
  differences (ρ = 0.688, half-life 1.86 years). The firm-FE AR(1) is
  Nickell-biased **downward** (ρ = 0.243, half-life 0.49 years). An
  Anderson–Hsiao IV gives 0.413 (SE 0.145). The result is a range, 0.24–0.69,
  not a point; `1 − ρ` from the pooled model is not a within-firm speed.
- **Weak controls.** `log(assets)`, gross margin, capital intensity and asset
  turnover are coarse. There is no control for growth opportunities, supplier
  concentration, or payment terms. The capital controls reduce the coefficient
  only slightly (+0.000124 without them, +0.000130 with them); they do not
  identify a mechanism.
- **The positive CCC–ROA sign is mostly between firms.** The headline within-firm
  coefficient is +0.000130, but the between-firm regression gives +0.000525 and
  the components point in different directions: DSO +0.000473, DIO −0.000055
  (p = 0.084), DPO −0.000108. "Longer CCC is associated with higher ROA" is a
  cross-sectional composition statement, not a within-firm lever. More payables
  are associated with **lower** ROA.
- **Winsorization choices move coefficients.** Reported with and without.
- **Persistence is definition-sensitive.** The pooled ρ falls from 0.688 to
  0.552 on raw clean CCC and 0.543 when |CCC| > 365 days are dropped; average
  balances raise it to 0.782, and the firm-FE estimate is 0.243. All are
  reported; the level should be quoted together with the estimator and
  definition, not as "the" persistence of the CCC.
- **The ROA association is small in economic terms.** β = 0.000130 is 1.30
  percentage points of ROA per 100 CCC days, or 0.055 SD of ROA per SD of CCC.
  It is a within-firm association conditional on gross margin and capital
  controls; the unconditional association is larger (+0.000187).
- **The typical firm shows no CCC–ROA relation.** An independent rank check
  (Spearman correlation of winsorized clean CCC and ROA within each firm, firms
  with at least three years) has a median of −0.014, and only 47.2% of firms
  have a positive one. That is **no monotone association in the median firm**,
  not a negative majority: the remaining 52.8% are zero or negative. The linear
  coefficient is identified off firms with large CCC variation and is not a
  pattern visible in the median firm. The check is `rank_check` in
  `results.json`, computed by the pipeline rather than by hand.
- **The annual shock windows are fiscal years, not calendar shocks.** The annual
  cross-sections use the issuer's `fy` label. 29.0% of FY2020 rows and 28.3% of
  FY2022 rows have a non-December year-end, so a June-ending firm's "2020"
  outcome spans July 2019–June 2020, up to eleven months away from the
  March–April 2020 shock. The December-only re-estimation is in
  `results.json.shock_window`: the FY2020 revenue result stays undetectable
  (t = 0.81), the FY2020 ROA coefficient stays positive (t = 2.29), and the
  FY2022 margin slope loses significance (t = −1.50).
- **The quarterly result does not confirm the annual margin result.** With
  calendar Q1–Q3 outcomes and the prior fiscal year's clean CCC as exposure, no
  pooled quarterly coefficient clears 5%. The 2022 gross-margin coefficient is
  **positive** (+0.000023, t = 1.89, p = 0.059), while the annual FY2022
  coefficient is negative. This is not a reconciliation; it is evidence that the
  annual negative slope is not robust to timing and resolution. The quarterly
  estimates are imprecise, so the correct statement is "not detectable", not
  "no effect".
- **Multiple specifications, one dataset.** The robustness table is a set of
  specifications, not a pre-registration. No correction for multiple testing
  (including the 24 quarterly quarter-outcome cells); the p-values should be
  read as descriptive.
- **Attrition is not random.** Firms with ≥3 usable years are larger, older and
  more likely to be industrial/retail. The results describe that population. The
  largest drop (76,218 firm-years missing an input) is concentrated in inventory
  (63,376) and COGS (55,285), with 74.5% of those rows missing more than one
  input; the decomposition is in `results.json → attrition_missing_items`.

## Engineering limitations

- The FSDS `num.txt` has no `start` date, so annual duration is identified by the
  SEC's own `qtrs == 4` flag plus 350–380-day spacing between fiscal-year ends,
  not by recomputing each fact's duration. Quarterly duration uses `qtrs == 1`.
- The internal spot check against `companyfacts` covers 3 issuers × 3 years ×
  7 concepts. It validates parsing and period alignment for those issuers, not
  the tag choice, the ordered fallback logic or coverage. It is a spot check,
  not a full reconciliation.
- The quarterly panel deliberately derives `quarter` from the period end, not
  from `fy`/`fp`, because a handful of filings carry implausible fiscal-year
  labels. The annual panel keeps the issuer's `fy` label for continuity; the two
  are not interchangeable.
- The quarterly YoY match uses the period end one year earlier (within 45 days),
  not a `(fy, fp)` label join. A label join duplicated 292 rows in an earlier
  build because transition periods can share a fiscal-year/period label.
