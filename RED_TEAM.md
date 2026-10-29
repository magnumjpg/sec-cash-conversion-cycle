# Robustness Analysis and Boundary Conditions

Technical assessment of identification strategies, taxonomy classification choices, and econometric robustness checks.
Each objection is followed by what the project does about it and what remains
unresolved.

---

## "A positive CCC–ROA coefficient is economically implausible. You have a coding error."

It was checked before anything was written. The clean-AP coefficient is positive
in the baseline (+0.000124), with capital-intensity and asset-turnover controls
(+0.000130), with industry × year FE (+0.000131), with raw unwinsorized
variables (+0.000191), and in all 13 main-sample specifications (12 ROA variants
plus a 2020 growth placebo); 9 of 13 are significant at 5%. It is weaker under
the cleanest tag measurement (spec 11, preferred tags only: β = +0.000122,
p = 0.086).

But the more important correction is interpretive. The **between-firm**
coefficient is +0.000525 (t = 4.80), four times the headline. The positive sign
is mostly a composition fact: firms in instruments, machinery and made-to-order
manufacturing carry inventory and receivables because that is their business
model, and they earn higher margins. The within-firm components are not a
"longer CCC is better" story: DSO +0.000473, DIO −0.000055 (p = 0.084), DPO
−0.000108. More payables are associated with **lower** ROA.

**Unresolved:** the design cannot separate product mix from a
financing-capacity story. A within-firm event study around deliberate CCC
changes would be needed.

---

## 2. Within-Firm vs Between-Firm Identification (Industry Controls)

No. The headline specification has firm fixed effects, so industry is absorbed
by construction. The variance decomposition is the relevant number, and it is
two overlapping partitions, not one: only **6.24%** of CCC variance is between
two-digit industries (93.76% within them), while **64.54%** is between firms
(35.46% within a firm over time). Adding the three numbers gives 106.24%
precisely because "between industries" is nested inside "between firms".

That is the substantive finding that survives the objection: "industry practice"
explains very little of working-capital levels.

---

## 3. Distributional Skewness and Winsorization Robustness

Correct, and the README says so. The mean is uninterpretable because a small
share of XBRL facts are tagged at the wrong scale (assets in millions, COGS off
by 1,000×) and because micro-caps produce ratios with tiny denominators.

The response is threefold:

1. Headline levels are **medians**, not means.
2. Estimation drops |CCC| > 3,650 days, assets < $1m or revenue < $1m:
   **1,040 rows (4.28%)**.
3. The screen is not neutral and the size of the distortion is disclosed: the
   dropped group has a median CCC of **−108.29 days**, versus +82.05 in the kept
   sample.

**Unresolved:** the dropped rows are not random. Firms that tag at the wrong
scale may differ systematically. They are excluded rather than repaired, because
repairing them would require reading 1,040 filings.

---

## 4. Persistence Estimators (Pooled AR(1), Firm-FE & Anderson-Hsiao)

Partly fair, and the project now says so. The 0.688 is a pooled AR(1) with year
FE and no firm FE. It is consistent, but it keeps persistent between-firm
differences in the error, so it is an **upper bound** on the within-firm speed.
Adding firm FE gives ρ = 0.243 (half-life 0.49 years), but that estimate is
Nickell-biased **downward** with T ≈ 10, so it is a lower bound. An
Anderson–Hsiao IV gives 0.413 (SE 0.145), between the two.

The honest statement is a **range**, not a point: the truth is somewhere between
0.24 and 0.69, with a half-life between roughly half a year and under two years.
The project does not claim that "31% of the gap closes each year"; that number is
only the pooled `1 − ρ` and is not a within-firm adjustment speed.

**Also:** the estimate is definition-sensitive. Raw clean CCC gives 0.552;
dropping |CCC| > 365 gives 0.543; average balances give 0.782. The project
quotes the range together with the definitions.

---

## 5. Statistical Power of Shock Response Tests

Agreed, and the README does not claim it is. With N ≈ 1,326 and a noisy outcome,
the confidence interval on the 2020 revenue-growth coefficient is wide enough to
contain economically meaningful effects in either direction. The correct reading
is **"not detectable in this cross-section"**, not "CCC did not matter in 2020".

The 2022 annual margin result is the opposite problem: it is significant in the
linear specification (t = −2.06) and non-monotone in quintiles. That pattern is
consistent with tails, not with a dose–response, and is described that way. It is
also window-sensitive: restricting to December year-ends, so the outcome covers
January–December 2022, moves t to −1.50 and it no longer clears 5%.

**The quarterly panel reinforces the caution, not the result.** With calendar
Q1–Q3 outcomes and prior-FY exposure, no pooled coefficient clears 5%; the 2022
gross-margin coefficient is *positive* (+0.000023, t = 1.89, p = 0.059). The
annual negative slope is not confirmed at quarterly resolution.

**Unresolved:** no placebo outcome, no pre-trend, no matched control group. Each
of those would improve the design; none is present.

---

## 6. Survivorship Bias and Minimum Time-Series Filtering (3-Year Rule)

It does select firms with at least three usable consecutive years. That makes the
panel a description of established SEC filers with trade working capital, not of
all listed firms. Firms that IPO'd and died within two years are absent, which
probably truncates the left tail of distress.

The project states the population explicitly and does not generalise beyond it.
The **11.64%** negative-CCC share is presented as a **lower bound** for the
listed universe on the industry-mix dimension (service firms without inventory
are excluded by the data). It is also tag-sensitive: the contaminated
combined-tag rows are 48.22% negative, but they are excluded from the clean
headline, so the headline share is 11.64%, not the all-row 15.33%.

---

## 7. Trade Payables Decomposition and Sample Truncation

It is a documented measurement choice, not a deletion of inconvenient rows. The
combined tag is AP **plus accrued liabilities**; it is not a trade payable. The
The reconstruction rule recovers trade AP whenever the accrual split exists
(`AP+accruals − accrued liabilities`, kept only if positive), which recovers
**71 of 2,773 fallback rows (2.56%)**. The remaining **2,702 rows** are excluded
from `ccc_clean`, and both the clean and mixed measures are reported:

- clean AP: 24,272 rows, median CCC **80.38** days;
- all rows (mixed AP): 26,974 rows, median CCC **75.42** days;
- contaminated only: 2,702 rows, median CCC **3.69** days.

The reconstruction is small because the combined tag is used precisely when the
split is absent; that is a property of XBRL reporting, not a choice. The
contaminated group's median is so far from the clean group that averaging them
would manufacture a level rather than measure one.

**Unresolved:** the 2,702 excluded rows are not missing at random. If they are
systematically different, the clean headline is a selected 90% of the panel.
The all-row sensitivity bounds the direction of the bias but does not remove it.

---

## 8. Lagged Shock Exposure Timing in Quarterly 10-Q Panel

This was true in an earlier build, and it was caught in the remediation. The
10-Q's own `fy` is mostly the shock year - a December filer's 2020Q1 10-Q carries
`fy = 2020` - so joining the quarterly row to the annual panel on `fy` used the
**same-year** FY2020/FY2022 balance sheet as "pre-shock" exposure. That produced
a spurious 2022 cash/assets coefficient (t = −2.52).

The corrected merge uses `shock_year − 1` (FY2019 for 2020, FY2021 for 2022).
With calendar Q1–Q3 outcomes, the 2022 cash/assets estimate is t = −0.43, and no
pooled coefficient clears 5%. The annual FY2022 margin result is not confirmed
either. The earlier significant quarterly result is reported in
`ANALYSIS_LOG.md → §12` as a bug that was found and fixed, not as a finding.

**Unresolved:** the pre-shock annual balance is a single exposure per firm, so
the quarterly panel does not identify within-firm changes in CCC around the
shock. That would require quarterly exposure measured before each outcome
quarter, which the 10-Q balance sheet can support but the current design does
not use.

---

## 9. Reconciliation Between Annual Cross-Sections and Quarterly Panel

Neither is "right": they answer different questions. The annual test uses a
fiscal-year outcome (one observation per firm), while the quarterly test uses
calendar-quarter outcomes with the prior fiscal year's balance sheet. The annual
FY2022 margin slope is negative (t = −2.06); the quarterly pooled slope is
positive (t = 1.89). The annual result loses significance on December year-ends
(t = −1.50) and is not confirmed quarterly. The honest conclusion is that the
annual negative slope is fragile, not that the quarterly positive slope is a
resilience result.

---

## 10. XBRL Direct Extraction Validation vs Commercial Data Vendors

Three checks:

1. **Internal spot check.** Seven concepts across three fiscal years for
   Fastenal, Walmart and Apple, compared to the `companyfacts` API:
   **63/63 exact matches**, maximum relative difference 0.0. The denominator is
   every comparison the design sets out to make; a ±7-day window matches the
   issuer's exact period end to the panel's month-end convention. This checks
   parsing and period alignment, not the tag choice, the fallback order or
   coverage of the wider panel.
2. **A published attrition funnel.** 2,795,447 us-gaap facts → 117,001 matched
   firm-years → 105,878 in the fiscal-year window (after 1,567 duplicate labels
   and 9,556 outside-window rows) → 26,974 in the main sample, with every
   exclusion counted. The missing-input drop is decomposed by item (76,218
   rows, 221,080 item-cells).
3. **A manifest with SHA-256 hashes** for 64 quarterly source files, plus
   separate annual and quarterly extracts, so a silent upstream revision is
   detectable.

**Unresolved:** three firms is a spot check, not a reconciliation. A random
sample of 100 firms would be better and is not done.

---

## 11. Treatment and Representation of Negative Working Capital Firms

It does not select on the sign of CCC. The screen is on magnitude (|CCC| > 3,650
days), size (assets and revenue ≥ $1m) and data validity. Negative-CCC firms
remain: 11.64% of the clean unscreened sample and 9.41% of the screened one.

That said, the screen does remove extreme negative values, and the kept negative
tail is thinner than the raw one. Robustness spec 7 restricts to negative-CCC
firm-years and the coefficient is +0.000051 (t = 0.81, p = 0.42), i.e. not
detectable in that subsample. The positive headline is not coming from the
negative-CCC tail.

---

## 12. Inventory Impairment Reporting and Resilience Metrics

This was the strongest gap in the earlier build, and it is now addressed. The
cache was re-downloaded with `InventoryWriteDown` and `InventoryImpairmentLoss`.
**4,657 annual panel rows (17.3%) / 959 firms** report a write-down, and the
outcome is estimated in both the annual and quarterly shock tests.

The result is null: FY2020 write-down/COGS t = 0.09, FY2022 t = −0.15; quarterly
2020 t = 0.94, 2022 t = −0.96. Coverage is selected - only issuers that report
the tag enter - so the null describes that subsample, not the population. The
project says so rather than substituting gross margin and calling it the same
thing.

---

## 13. Descriptive Baseline vs Causal Identification Scope

It is descriptive, deliberately. The specification required for a real panel, honest
measurement and no fake causal claims; it did not ask for an identification
strategy the data cannot support.

The contribution is the dataset and the measurements that are not obvious before
looking: a clean-AP pooled median CCC of 80 days, a CCC that is mostly a firm
rather than an industry trait, a positive but mostly **between-firm** ROA
association, and shock results that do not survive a calendar/quarterly
alignment. Those are worth reporting precisely because the prior pointed the
other way - and the persistence result is a range, not the single number the
first draft advertised.