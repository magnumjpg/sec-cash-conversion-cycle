# DECISIONS — 02_working_capital_sec

Chronological log of binding choices, including where the charter was not
followed literally and why. Nothing here changes the numbers silently: every
deviation is also flagged in METHOD.md / LIMITATIONS.md.

---

## D-01. Source: SEC Financial Statement Data Sets instead of the Frames API

**Charter:** `companyfacts` (preferred) or Frames API (recommended alternative);
explicitly warns that 10,000 `companyfacts` downloads are infeasible.

**What I tested.** The Frames API works and returns a broad panel, but the
payload has only `cik, entityName, loc, end, val, accn` — it does **not** expose
`form`, `fp`, `filed`, or `sic`. Three charter rules are therefore unenforceable
from Frames alone:

1. keep only 10-K/10-K/A/20-F/40-F (frames mix 10-K and 10-Q facts),
2. "latest `filed` wins" (no `filed` field),
3. exclude financials/utilities by SIC (no SIC field; would need ~4,000 extra
   submissions requests, i.e. the very volume the charter rules out).

**Decision.** Use the SEC **Financial Statement Data Sets** (FSDS,
`https://www.sec.gov/files/dera/data/financial-statement-data-sets/{q}.zip`),
the official bulk extract of the *same* XBRL facts, 2010q1–2025q4 for the annual
panel and 2019q1–2022q4 for the quarterly shock panel. They contain
`sub.txt` (`cik, name, sic, form, period, fy, fp, filed, ...`) and `num.txt`
(`adsh, tag, version, ddate, qtrs, uom, value`), i.e. exactly the fields needed
to implement the charter literally.

Backtest of the trade-off:

| | Frames | FSDS |
|---|---|---|
| Universe / survivorship | broad | broad, **includes delisted filers** |
| `form` / `filed` / `sic` | absent | present |
| Requests | ~800 | 64 annual + 16 quarterly extracts |
| Reproducibility | needs network | cached locally |

Costs: ~100 MB per quarterly zip, ~5.49 GB of source zips for the two caches.
The zips themselves are not kept; the filtered extracts (`data/raw/fsds/*.parquet`,
`data/raw/fsds_q/*.parquet`, ~77 MB) are cached forever together with the source
URL, byte size and SHA-256 of the zip. The pipeline therefore reruns fully
offline.

**Internal spot check:** three well-known issuers (Fastenal, Walmart, Apple) are
compared tag-by-tag against the `companyfacts` API in
`src/verify_known_firms.py` (`outputs/validation.json`,
`outputs/tables/known_firm_check.csv`). This checks that the extractor parses
and period-aligns the facts it selected; it does not validate the tag choice,
the ordered fallback logic or coverage outside those three issuers.

---

## D-02. Fiscal-year alignment

The annual year label is the issuer's own `fy` from the annual report whose
`period` equals the fiscal-year-end date. Fallback is the calendar year of the
period end (used for comparison periods that appear inside another year's 10-K).
This is what makes a January-ending retailer land in FY2020 rather than FY2021.

Consequence: the annual panel year is a *label*, not a calendar year. Two firms
with different year-ends in the same "year" are up to 11 months apart. Year fixed
effects absorb the common component in the panel models, but the **annual shock
cross-sections do depend on the label**: 29.0% of FY2020 rows and 28.3% of FY2022
rows have a non-December year-end. The main tables therefore say "FY2020/FY2022",
and `results.json.shock_window` reports a December-only re-estimation so the
calendar alignment can be checked. The FY2022 margin slope falls from −0.0060
(t = −2.06) to −0.0056 (t = −1.50) on December year-ends.

**The quarterly panel does not use this label.** Its `quarter` is the calendar
quarter of the period end, because a handful of 10-Qs carry an implausible
fiscal-year focus and the shock is calendar time. See D-13.

---

## D-03. Flow–balance matching on the exact period end

Flows and balances are merged only when the period end is identical, and an
annual flow is kept only if `qtrs == 4`. The FSDS `num.txt` has no `start` date,
so the charter's "350–380 day duration" test cannot be applied fact-by-fact; it
is applied to the *spacing between consecutive fiscal-year ends* when building
lags (`days_since_prev` in 350–380). Facts with `qtrs` other than 0/4 were
dropped at annual download time. The quarterly cache keeps `qtrs` 0/1: instant
balances and one-quarter flows.

---

## D-04. Segment and co-registrant facts excluded

`num.txt` rows with a non-empty `segments` or `coreg` field are consolidated
sub-totals of a different scope. Only rows with both empty are used. Without
this filter, segment revenue would be mixed with company revenue.

---

## D-05. Tags added outside the charter list (last resort only)

| Concept | Charter tags | Added | Why |
|---|---|---|---|
| cash | `CashAndCashEquivalentsAtCarryingValue` | `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents` | post-2018 firms often tag only the combined cash-flow-statement figure |
| net income | `NetIncomeLoss` | `ProfitLoss` | 20-F filers frequently omit `NetIncomeLoss` |
| equity | `StockholdersEquity` | `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest` | coverage only |
| revenue | (4 tags) | `SalesRevenueGoodsNet` | last resort when none of the four exist |
| AP | `AccountsPayableCurrent` | `AccountsPayableTradeCurrent` | direct trade payable when the current-payables tag is absent |
| accrued liabilities | `AccruedLiabilitiesCurrent` | `OtherAccruedLiabilitiesCurrent` | split the combined AP-plus-accruals tag |
| PP&E | `PropertyPlantAndEquipmentNet` | `PropertyPlantAndEquipmentNetExcludingCapitalLeasedAssets` | capital-intensity control |
| write-down | `InventoryWriteDown` | `InventoryImpairmentLoss` | charter resilience outcome |

They are always **after** every charter tag in the fallback order, tagged
`tier = "extra"` in `outputs/tables/tag_usage.csv`, and the headline regression
is re-run using only firm-years where the *preferred* charter tag supplied each
input (robustness spec 11 in `outputs/results.json`). Spec 11 requires
`InventoryNet` as well as the preferred revenue/COGS/AR/AP tags; it estimates
β = +0.000122 (t = 1.72, p = 0.086, n = 4,543) and is the cleaner measurement,
weaker than the clean-AP headline.

The AP fallback `AccountsPayableAndAccruedLiabilitiesCurrent` is a different
concept (AP plus accruals). It is reconstructed only when
`AccruedLiabilitiesCurrent` is available; see D-12.

---

## D-06. Plausibility screen for estimation only (~4% of rows)

XBRL contains genuine scale errors: `Assets` tagged in millions (e.g. 5,102
instead of 5,102,000,000), `CostOfRevenue` tagged at 1/1,000 of revenue. They
are a small share of rows but dominate every mean, standard deviation and OLS
coefficient. Estimation therefore drops firm-years with

```
|CCC| <= 3,650 days  AND  total assets >= $1m  AND  revenue >= $1m
```

`outputs/results.json → estimation_screen` reports exactly how many rows and
what the median CCC was in the dropped group: 1,040 clean-AP rows (4.28%),
median CCC −108.29 in the dropped group against 82.05 in the kept group.
**Headline medians, distributions and industry tables are computed on the full
main sample, without this screen** (charter §4: never winsorize before computing
headline medians).

---

## D-07. Winsorization

1/99 within industry-year (charter). Some industry-year cells have < 50
observations, where a 1% cut clips nothing; those cells fall back to the pooled
1/99 bounds. Both CCC and ROA are winsorized in the regression tables. Raw
(unwinsorized) results are reported as robustness spec 4.

---

## D-08. Persistence specification: report a range, not a point

The pooled model `CCC_it = a + rho*CCC_i,t-1 + year FE`, SEs clustered by firm,
with **no firm fixed effect** (charter §5.2), gives rho = 0.688. It is consistent
but omits time-invariant firm traits, so persistent between-firm differences are
part of rho and the estimate is biased **upward** as a within-firm speed.

The firm-FE version is reported alongside it (`persistence.with_firm_fe`):
rho = 0.243. Because a lagged dependent variable plus firm FE is Nickell-biased
in short panels (T ≈ 10), that estimate is biased **downward**. Neither is the
parameter. An Anderson–Hsiao IV on first differences
(`persistence.anderson_hsiao`) gives 0.413 (SE 0.145), between the two. The
headline is therefore the range **0.24–0.69** (half-life 0.5–1.9 years), and
`1 - rho` from the pooled model is not described as the share of a firm's gap
that closes each year.

The by-industry table uses the same pooled estimator and is labelled
"pooled (between + within firm)"; a firm-FE rho is reported per industry where
estimable, with the caveat that the industry-level within estimates are noisy.

---

## D-09. Financials, real estate, utilities

Excluded from the main sample (SIC 6000–6999, 6500–6599 ⊂ 6000–6999, and
4900–4999). Kept in `data/processed/panel_full.csv.gz` and used only for
robustness spec 14. Their working-capital ratios are not comparable (no
inventory, no trade payables in the usual sense).

---

## D-10. Restatement window

"Latest `filed` wins" is applied over filings up to **2025-12-31**. Amendments
filed after that date are not in the cache, so a handful of FY2024 figures may
be superseded later. Rerunning `download_sec.py` adds later quarters without
touching the code.

---

## D-11. What is deliberately *not* done

- No dollar value of a CCC day. It needs a cost of capital and an explicit
  financing assumption; the charter forbids it and it is not identified here.
- No causal language. The FY2020/FY2022 cross-sections and the quarterly tests
  are descriptive.
- No market returns: no CRSP/Compustat, so no abnormal-return test.
- No attempt to make the panel "representative" of all US listed firms. It is
  the population of 10-K/20-F filers with usable trade working capital.
- No imputation of the missing accrual split. The combined AP tag is
  reconstructed only when the issuer reports the split; otherwise the row is
  excluded from the clean measure rather than filled with an average.

---

## D-12. Trade-AP reconstruction, write-downs and the re-download

This decision replaces the earlier "inventory write-downs are not measured"
entry. The audit remediation re-downloaded the cache with three extra concepts
(`accrued_liabilities`, `ppe_net`, `inventory_write_down`) and changed the
payables rule.

**Trade AP.** `AccountsPayableCurrent` (and `AccountsPayableTradeCurrent`) are
direct trade payables. `AccountsPayableAndAccruedLiabilitiesCurrent` is AP plus
accruals; it is converted to trade AP only when
`AccruedLiabilitiesCurrent` is present and
`AP+accruals − accrued liabilities > 0`. That reconstructs **71 of 2,773
fallback rows (2.56%)**. The remaining **2,702 rows are flagged
`fallback_contaminated` and excluded** from the clean headline and from
`ccc_clean`. Reasons:

1. the combined tag is used precisely when the split is absent, so
   reconstruction is not available for most fallback rows;
2. the contaminated group has a median CCC of 3.69 days against 80.38 on clean
   AP, so averaging the two concepts would manufacture a level, not measure one;
3. a 71-row reconstruction is too small to change the level, but keeping the
   rule explicit prevents a silent concept switch.

The all-row mixed measure is retained as a sensitivity (median 75.42 days,
negative share 15.33%) and is not used in regressions.

**Write-downs.** `InventoryWriteDown` / `InventoryImpairmentLoss` are now
extracted. 4,657 annual panel rows (17.3%) / 959 firms report a write-down; the
quarterly panel has 396 observations before the shock window and 187/194 in the
2020/2022 pooled tests. The outcome is estimated on that selected subsample;
coverage is reported rather than assumed representative.

**Consequence for the headline.** The clean-AP median is **80.38 days**
(24,272 rows), not the mixed-AP 75.42. The difference is the accrual component
of the fallback, not a change in the underlying firms.

---

## D-13. Quarterly shock design: calendar window and prior-FY exposure

The annual 10-K panel cannot resolve a shock that lasted weeks. The quarterly
panel therefore uses 10-Q/10-Q/A facts from 2019q1–2022q4:

- **Calendar labels, not `fy`.** `quarter` is derived from `ddate`. A 10-Q for a
  period ending March 2020 is 2020Q1 regardless of the filing's fiscal-year
  focus; three filings carry an implausible `fy` label.
- **Q1–Q3 only.** A December period end is filed in the 10-K, not the 10-Q; Q4
  would mix a thin non-December subsample into the last cell.
- **Exposure = prior fiscal year.** The 10-Q's own `fy` is mostly the shock year
  (a December filer's 2020Q1 10-Q carries `fy = 2020`), so the merge uses
  `fiscal_year = shock_year − 1` (FY2019 for 2020, FY2021 for 2022). Joining on
  the 10-Q `fy` put exposure and outcome in the same year and produced a
  spurious 2022 cash/assets coefficient (t = −2.52 in the earlier build); the
  corrected specification gives t = −0.43.
- **YoY by period end, not `(fy, fp)`.** A label join duplicated 292 rows
  because transition periods can share a fiscal-year/period label; the match now
  uses the period end one year earlier (within 45 days), which is unique.
- **No pooled coefficient clears 5%.** With 8,588 shock firm-quarters / 1,852
  firms, the closest is the 2022 gross-margin change (+0.000023, t = 1.89,
  p = 0.059). The annual FY2022 negative margin slope is not confirmed
  quarterly. The tests are descriptive and are not corrected for the 24
  quarter-outcome cells.
