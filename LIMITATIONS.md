# LIMITATIONS

## What this does not prove

- **No causality.** CCC is chosen jointly with industry, growth, bargaining
  power, supplier terms and product mix. Every coefficient here is an
  association. In this sample the CCC–ROA coefficient is *positive*; that does
  not mean that lengthening the CCC raises ROA, any more than a negative
  coefficient would license the opposite.
- **No dollar value of a CCC day.** That requires a cost of capital, a financing
  mix and an assumption about what happens to the freed cash. The charter
  forbids it and nothing in this pipeline identifies it.
- **No market test.** Without CRSP/Compustat there are no returns, no abnormal
  performance, no event windows. "Resilience" is measured with accounting
  outcomes only.
- **The 2020 and 2022 exercises are cross-sections.** They are one observation
  per firm, with industry fixed effects. They cannot separate a CCC effect from
  an unobserved firm characteristic correlated with CCC (customer concentration,
  product durability, channel mix).

## Data limitations

- **Coverage, not representativeness.** The panel is the population of annual
  SEC filers with usable trade working capital. It is not a random sample of US
  firms, and it under-represents service firms (no inventory → no DIO), which is
  exactly where negative CCC is most common. The share of negative-CCC firms is
  therefore a lower bound for the whole listed universe.
- **Tag heterogeneity.** The mapping is explicit and versioned, but a firm that
  reports "accounts receivable" inside an "other receivables" line will be
  missing rather than approximately right. Tag fallbacks mix concepts
  (`AccountsPayableAndAccruedLiabilitiesCurrent` includes accruals), which biases
  DPO upward for firms on that fallback. `tag_usage.csv` quantifies how often
  each fallback is used, and robustness spec 9 restricts to preferred tags.
- **XBRL scale errors.** Roughly 6% of rows are dropped *for estimation* because
  assets or revenue are tagged at the wrong scale. This is a real property of
  the source, not of this pipeline. Headline medians keep those rows; the
  dropped group has a much lower median CCC, so the screen is not neutral.
- **20-F / IFRS.** IFRS filers are excluded outright. US-GAAP 20-F filers remain.
  The panel is therefore US-listed, mostly US-domiciled.
- **Restatements.** "Latest filing wins" only over filings up to 2025-12-31.
  Later amendments are not captured until the cache is extended.
- **Inventory write-downs are not measured.** They are one of the charter's
  three resilience outcomes, but the cached tag slice does not contain
  write-down tags and the source zips were deleted. Recovering them requires a
  re-download of the quarterly extracts (`DECISIONS.md → D-12`).
- **No quarterly data.** Seasonality is invisible. A December-ending retailer
  and a January-ending one are compared at their own year-end, which is the
  right point for annual ratios but hides peak-vs-trough working capital.
- **Textbook CCC caveats.** Revenue is a flow including markup, COGS is a cost;
  DSO and DIO are not strictly comparable in units. This is standard practice and
  it is why the ratios are used as *relative* measures, not as cash amounts.
- **Fiscal-year labels.** The year is the issuer's label. Firms with different
  year-ends in the same "year" can be up to 11 months apart.

## Econometric limitations

- **Short panels.** T ≈ 10. The firm-FE AR(1) is Nickell-biased downward; the
  headline excludes firm FE for that reason, at the cost of not controlling for
  time-invariant firm traits in the persistence regression.
- **Weak controls.** `log(assets)` and gross margin are coarse. There is no
  control for growth opportunities, supplier concentration, or payment terms.
- **Winsorization choices move coefficients.** Reported with and without.
- **Persistence is definition-sensitive.** The headline ρ = 0.685 falls to
  0.536 on raw CCC and 0.509 when |CCC| > 365 days are dropped. All estimates
  are far from zero, but the level should be quoted together with the
  definition, not as "the" persistence of the CCC.
- **The ROA association is small in economic terms.** β = 0.000139 is 1.39
  percentage points of ROA per 100 CCC days, or 0.060 SD of ROA per SD of CCC.
  It is a within-firm association conditional on gross margin; the unconditional
  association (no controls) is larger, 0.000184.
- **Attrition is not random.** Firms with ≥3 usable years are larger, older and
  more likely to be industrial/retail. The results describe that population.
- **Multiple specifications, one dataset.** The robustness table is a set of
  specifications, not a pre-registration. No correction for multiple testing;
  the p-values should be read as descriptive.

## Engineering limitations

- The FSDS `num.txt` has no `start` date, so annual duration is identified by the
  SEC's own `qtrs == 4` flag plus 350–380-day spacing between fiscal-year ends,
  not by recomputing each fact's duration.
- Validation against `companyfacts` covers 3 issuers × 3 years × 7 concepts. It
  is a spot check, not a full reconciliation.
