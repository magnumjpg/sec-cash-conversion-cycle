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
the official bulk extract of the *same* XBRL facts, 2010q1–2025q4. They contain
`sub.txt` (`cik, name, sic, form, period, fy, fp, filed, ...`) and `num.txt`
(`adsh, tag, version, ddate, qtrs, uom, value`), i.e. exactly the fields needed
to implement the charter literally.

Backtest of the trade-off:

| | Frames | FSDS |
|---|---|---|
| Universe / survivorship | broad | broad, **includes delisted filers** |
| `form` / `filed` / `sic` | absent | present |
| Requests | ~800 | 64 (one per quarter) |
| Reproducibility | needs network | cached locally |

Costs: ~100 MB per quarterly zip, ~14 minutes of download. The zips themselves
are not kept (6.4 GB); the filtered extracts (`data/raw/fsds/*.parquet`, ~1.5 MB
per quarter) are cached forever together with the source URL, byte size and
SHA-256 of the zip. The pipeline therefore reruns fully offline.

**Verified:** three well-known issuers (Fastenal, Walmart, Apple) are compared
tag-by-tag against the `companyfacts` API in `src/verify_known_firms.py`
(`outputs/validation.json`, `outputs/tables/known_firm_check.csv`).

---

## D-02. Fiscal-year alignment

The year label is the issuer's own `fy` from the annual report whose `period`
equals the fiscal-year-end date. Fallback is the calendar year of the period end
(used for comparison periods that appear inside another year's 10-K). This is
what makes a January-ending retailer land in FY2020 rather than FY2021.

Consequence: the panel year is a *label*, not a calendar year. Two firms with
different year-ends in the same "year" are up to 11 months apart. Year fixed
effects absorb the common component; nothing else in the design depends on the
label being a calendar year.

---

## D-03. Flow–balance matching on the exact period end

Flows (`qtrs == 4`) and balances (`qtrs == 0`) are merged only when `end` is
identical, and a flow is kept only if `qtrs == 4` (annual duration). The FSDS
`num.txt` has no `start` date, so the charter's "350–380 day duration" test
cannot be applied fact-by-fact; it is applied to the *spacing between
consecutive fiscal-year ends* when building lags (`days_since_prev` in
350–380). Facts with `qtrs` other than 0/4 were dropped at download time.

---

## D-04. Segment and co-registrant facts excluded

`num.txt` rows with a non-empty `segments` or `coreg` field are consolidated
sub-totals of a different scope. Only rows with both empty are used. Without
this filter, segment revenue would be mixed with company revenue.

---

## D-05. Two tags added outside the charter list (last resort only)

| Concept | Charter tags | Added | Why |
|---|---|---|---|
| cash | `CashAndCashEquivalentsAtCarryingValue` | `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents` | post-2018 firms often tag only the combined cash-flow-statement figure |
| net income | `NetIncomeLoss` | `ProfitLoss` | 20-F filers frequently omit `NetIncomeLoss` |
| equity | `StockholdersEquity` | `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest` | coverage only |
| revenue | (4 tags) | `SalesRevenueGoodsNet` | last resort when none of the four exist |

They are always **after** every charter tag in the fallback order, tagged
`tier = "extra"` in `outputs/tables/tag_usage.csv`, and the headline regression
is re-run using only firm-years where the *preferred* charter tag supplied each
input (robustness spec 9 in `outputs/results.json`).

---

## D-06. Plausibility screen for estimation only (~6% of rows)

XBRL contains genuine scale errors: `Assets` tagged in millions (e.g. 5,102
instead of 5,102,000,000), `CostOfRevenue` tagged at 1/1,000 of revenue. They
are a small share of rows but dominate every mean, standard deviation and OLS
coefficient. Estimation therefore drops firm-years with

```
|CCC| <= 3,650 days  AND  total assets >= $1m  AND  revenue >= $1m
```

`outputs/results.json → estimation_screen` reports exactly how many rows and
what the median CCC was in the dropped group. **Headline medians, distributions
and industry tables are computed on the full main sample, without this screen**
(charter §4: never winsorize before computing headline medians).

---

## D-07. Winsorization

1/99 within industry-year (charter). Some industry-year cells have < 50
observations, where a 1% cut clips nothing; those cells fall back to the pooled
1/99 bounds. Both CCC and ROA are winsorized in the regression tables. Raw
(unwinsorized) results are reported as robustness spec 2.

---

## D-08. Persistence specification

`CCC_it = a + rho*CCC_i,t-1 + year FE`, SEs clustered by firm, with **no firm
fixed effect** (charter §5.2). Because a lagged dependent variable plus firm FE
is Nickell-biased in short panels, the firm-FE version is reported separately as
a bound (`persistence.with_firm_fe`), never as the headline.

---

## D-09. Financials, real estate, utilities

Excluded from the main sample (SIC 6000–6999, 6500–6599 ⊂ 6000–6999, and
4900–4999). Kept in `data/processed/panel_full.csv.gz` and used only for
robustness spec 12. Their working-capital ratios are not comparable (no
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
- No causal language. The 2020/2022 cross-sections are descriptive.
- No market returns: no CRSP/Compustat, so no abnormal-return test.
- No attempt to make the panel "representative" of all US listed firms. It is
  the population of 10-K/20-F filers with usable trade working capital.
