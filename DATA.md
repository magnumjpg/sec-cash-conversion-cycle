# DATA

Everything here is built from public SEC filings. No synthetic, imputed or
vendor-adjusted data enter the panel. Every number in `README.md` is produced by
`src/run_all.py` and stored in `outputs/results.json` (annual) or
`outputs/quarterly_results.json` (quarterly).

## 1. Sources

| Source | URL | Used for |
|---|---|---|
| SEC Financial Statement Data Sets (FSDS) | `https://www.sec.gov/files/dera/data/financial-statement-data-sets/{q}.zip` | annual panel, 2010q1–2025q4 |
| SEC FSDS, same files | same URL | 10-Q shock panel, 2019q1–2022q4 |
| SEC company tickers | `https://www.sec.gov/files/company_tickers.json` | ticker/exchange lookup only |
| SEC company tickers + exchange | `https://www.sec.gov/files/company_tickers_exchange.json` | `data/raw/tickers.parquet` |
| SEC `companyfacts` API | `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` | internal spot check, 3 issuers only |

The initial design considered `companyfacts` and evaluated the Frames API. Frames were
tested and rejected because the payload has no `form`, `filed`, `fp` or `sic`,
which makes three standard panel criteria unenforceable (10-K-only, latest-filing-wins,
SIC exclusions). FSDS is the SEC's own bulk extract of the same XBRL facts,
exposes all of those fields, and includes delisted filers. Full reasoning and the
trade-off table: `DECISIONS.md → D-01`.

The quarterly shock cache (2019q1–2022q4) is a **second filtered view of the
same quarterly zips**, not a second source. Annual files keep 10-K/20-F forms
with `qtrs` 0/4; the quarterly files keep 10-Q/10-Q/A forms with `qtrs` 0/1.
They are stored in separate directories so the annual build cannot mix 10-Q
facts into a 10-K panel.

User-Agent sent to the SEC: `portfolio-research/1.0 (${SEC_CONTACT})`, where
`SEC_CONTACT` is an environment variable. Set it before running the downloader,
e.g. `export SEC_CONTACT=you@example.com` (bash) or
`$env:SEC_CONTACT="you@example.com"` (PowerShell). The fallback contact is
`portfolio-research@example.com`; no personal address is stored in the repo.
Requests are throttled to **4 per second** (specification ceiling: 5), with 6 retries
and exponential backoff.

## 2. What is cached, and where

```
data/
  manifest.json                     provenance for every cached file (committed)
  raw/                              NOT committed (gitignored)
    fsds/
      2010q1_sub.parquet            filtered sub.txt: forms, SIC, fy, filed
      2010q1_num.parquet            filtered num.txt: project tags, USD, qtrs 0/4
      2010q1_forms.parquet          form counts before filtering
      ...                           one triplet per quarter, 64 quarters
    fsds_q/
      2019q1_sub.parquet            10-Q/10-K filings for the shock cache
      2019q1_num.parquet            project tags, USD, qtrs 0/1
      2019q1_forms.parquet
      ...                           one triplet per quarter, 16 quarters
    zips/                           empty: source zips deleted after extraction
    company_tickers*.json
    tickers.parquet
    companyfacts/CIK*.json         spot-check cache (3 firms)
  processed/
    panel.csv                     main sample, inspectable (committed)
    panel.parquet                 same, typed (gitignored)
    panel_full.csv.gz             incl. financials/utilities (gitignored)
    quarterly_panel.csv           firm-quarter 10-Q panel (committed)
    quarterly_panel.parquet       same, typed (gitignored)
```

Volumes from the latest build:

| Item | Count / size |
|---|---|
| Annual quarters cached | 64 (2010q1–2025q4) |
| Quarterly shock quarters cached | 16 (2019q1–2022q4) |
| Source zips downloaded | 64, **5.49 GB**, deleted after extraction |
| Derived parquet files retained | 240 (192 annual + 48 quarterly), **76.9 MB** |
| Manifest entries | 306 (242 retained on disk, 64 source zips with hash only) |
| Annual filings in cache | 105,027 |
| Usable annual firm-years after all filters | 26,974 (3,320 firms) |
| Clean trade-AP firm-years | 24,272 (3,010 firms) |
| Quarterly firm-quarters | 72,811 (8,097 firms, 20 quarters) |
| Quarterly shock sample | 8,588 firm-quarters (1,852 firms) |

The zips are not kept; the **SHA-256 of each zip is**. This is the provenance
chain: `manifest.json` pins the exact source file that produced each parquet,
and the parquet hashes pin what the panel was built from. Each of the 2019–2022
zips is used twice (annual and quarterly filters), so 64 unique zips support
both caches.

## 3. Manifest schema

`data/manifest.json` is a single object:

```json
{
  "generated_at_utc": "2026-10-26T10:48:46+00:00",
  "user_agent": "portfolio-research/1.0 (portfolio-research@example.com)",
  "files": [
    {
      "url": "https://www.sec.gov/files/dera/data/financial-statement-data-sets/2021q4.zip",
      "path": "data/raw/fsds/2021q4_sub.parquet",
      "bytes": 28519,
      "sha256": "9a94959e737bbd9c2777e70fd6ade69cb09f8cf484f9cda9cd5473641aa4dbce",
      "fetched_at_utc": "2026-10-26T10:48:46+00:00",
      "note": "derived from …/2021q4.zip (102642081 bytes); sub/num filtered to annual forms + project tags",
      "source_bytes": 102642081,
      "retained": true
    }
  ]
}
```

For a deleted zip the entry keeps `url`, `bytes`, `sha256` and
`retained: false`; `note` explains that it was removed after extraction. There
is one such entry per quarter, including 2021q4 (re-fetched on 2026-10-25 to
close a provenance gap left by an earlier concurrent download).

## 4. Downstream filters (attrition)

From `outputs/results.json → attrition` and `outputs/tables/attrition.csv`:

| Level | Step | Rows | Firms |
|---|---|---:|---:|
| fact | us-gaap facts, project tags, annual forms, consolidated, qtrs 0/4 | 2,795,447 | |
| fact | dropped: reporting currency not USD | 66,359 | 419 |
| fact | dropped: IFRS taxonomy (`ifrs-full`) | 23,795 | |
| fact | dropped: duplicate tag/period, older filing | 1,368,693 | |
| fact | dropped: flow fact with `qtrs != 4` | 1,624 | |
| firm-year | flow + balance matched on identical fiscal-year end | 117,001 | 14,270 |
| firm-year | dropped: duplicate fiscal-year label | 1,567 | |
| firm-year | dropped: fiscal year outside 2010–2024 | 9,556 | |
| firm-year | in the 2010–2024 window | 105,878 | 14,234 |
| firm-year | dropped: missing revenue/COGS/AR/inventory/AP | 76,218 | 12,408 |
| firm-year | dropped: revenue ≤ 0 or COGS ≤ 0 | 279 | 226 |
| firm-year | dropped: negative balance-sheet item | 1 | 1 |
| firm-year | dropped: financials & real estate (SIC 6000–6999) | 390 | 90 |
| firm-year | dropped: utilities (SIC 4900–4999) | 474 | 81 |
| firm-year | dropped: fewer than 3 usable years | 1,542 | 927 |
| **firm-year** | **main sample** | **26,974** | **3,320** |
| firm-year | of which clean trade AP (direct or reconstructed) | 24,272 | 3,010 |

Segment (`segments`) and co-registrant (`coreg`) facts were dropped at download
time; they are not counted as separate rows above. The panel is industrial and
retail by construction, because it requires inventory and COGS.

The single "missing revenue/COGS/AR/inventory/AP" step (76,218 rows) is
decomposed in `outputs/tables/attrition_missing_items.csv` and
`results.json → attrition_missing_items`. A row can miss several inputs, so the
item counts overlap and are **not** disjoint:

| Missing item | Firm-years | Share of the 76,218 |
|---|---:|---:|
| Inventory | 63,376 | 83.2% |
| COGS | 55,285 | 72.5% |
| Accounts receivable | 47,795 | 62.7% |
| Accounts payable | 28,551 | 37.5% |
| Revenue | 26,073 | 34.2% |
| **More than one item missing** | **56,799** | **74.5%** |
| Exactly one item missing | 19,419 | 25.5% |
| Missing item-cells (sum of the five item rows) | 221,080 | - |

Inventory and COGS dominate the drop: 83.2% of the excluded rows have no
inventory fact and 72.5% no COGS, which is the expected consequence of requiring
a manufacturer/retailer working-capital cycle. The overlap is large (74.5% miss
more than one input), so quoting any single item as "the" reason would be
misleading.

## 5. Tag usage

Recorded per row in `tag_revenue`, `tag_cogs`, `tag_ar`, `tag_inventory`,
`tag_ap`; aggregated in `outputs/tables/tag_usage.csv`. **The two tables do not
share a denominator, deliberately.** `tag_usage.csv` is computed before the
panel filters, so `share_of_concept` is the share of the firm-years that reported
*any* tag for that concept (e.g. COGS `CostOfGoodsAndServicesSold` is 43.9% of
24,015 + 20,911 + 9,791 tagged firm-years). The table below is computed on the
final 26,974 panel rows, after the missing-input and window filters, so the same
tag is 49.7% of the panel. Neither is wrong; a reader comparing them must use the
labelled denominator rather than assume they are the same.

| Concept | Tag | Rows | Share | Tier |
|---|---|---:|---:|---|
| revenue | `RevenueFromContractWithCustomerExcludingAssessedTax` | 8,342 | 30.9% | primary taxonomy (preferred) |
| revenue | `SalesRevenueNet` | 7,630 | 28.3% | standard taxonomy |
| revenue | `Revenues` | 7,309 | 27.1% | standard taxonomy |
| revenue | `RevenueFromContractWithCustomerIncludingAssessedTax` | 1,823 | 6.8% | standard taxonomy |
| revenue | `SalesRevenueGoodsNet` | 1,870 | 6.9% | **extra** (last resort) |
| cogs | `CostOfGoodsAndServicesSold` | 13,408 | 49.7% | primary taxonomy (preferred) |
| cogs | `CostOfRevenue` | 8,107 | 30.1% | standard taxonomy |
| cogs | `CostOfGoodsSold` | 5,459 | 20.2% | standard taxonomy |
| ar | `AccountsReceivableNetCurrent` | 23,967 | 88.9% | primary taxonomy (preferred) |
| ar | `ReceivablesNetCurrent` | 2,890 | 10.7% | standard taxonomy |
| ar | `AccountsReceivableGrossCurrent` | 117 | 0.4% | standard taxonomy |
| inventory | `InventoryNet` | 26,776 | 99.3% | primary taxonomy (preferred) |
| inventory | `InventoryGross` | 127 | 0.5% | standard taxonomy |
| inventory | `InventoryFinishedGoodsNetOfReserves` | 71 | 0.3% | standard taxonomy |
| ap | `AccountsPayableCurrent` | 22,564 | 83.7% | primary taxonomy (preferred) |
| ap | `AccountsPayableTradeCurrent` | 1,637 | 6.1% | **extra** (direct trade AP) |
| ap | `AccountsPayableAndAccruedLiabilitiesCurrent` | 2,773 | 10.3% | standard taxonomy |

New concepts added in tag mapping **2.0.0**:

| Concept | Tag(s) | Panel rows | Used for |
|---|---|---:|---|
| `accrued_liabilities` | `AccruedLiabilitiesCurrent` (86.3% of tagged), `OtherAccruedLiabilitiesCurrent` (extra, 13.7%) | 16,987 | reconstruct trade AP from the combined tag |
| `ppe_net` | `PropertyPlantAndEquipmentNet` (99.97%), `PropertyPlantAndEquipmentNetExcludingCapitalLeasedAssets` (extra) | 25,637 | capital-intensity control |
| `inventory_write_down` | `InventoryWriteDown` / `InventoryImpairmentLoss` | 4,657 | quarterly and annual shock outcome |

No `extra` tag is used for COGS, receivables or inventory in the final panel.
Robustness spec 11 restricts to firm-years where the *preferred* primary tag
supplied every input (including `InventoryNet` and a direct trade-AP tag); it is
the cleaner measurement, and it is weaker than the clean-AP headline
(β = +0.000122, t = 1.72, p = 0.086, n = 4,543).

### 5a. Trade-AP reconstruction

The fallback `AccountsPayableAndAccruedLiabilitiesCurrent` is AP plus accruals,
not a like-for-like substitute. The reconstruction rule is:

```
if tag == AccountsPayableCurrent or AccountsPayableTradeCurrent:
    ap_clean = ap; quality = direct
elif tag == AccountsPayableAndAccruedLiabilitiesCurrent and AccruedLiabilitiesCurrent > 0:
    ap_clean = ap - accrued_liabilities; quality = reconstructed (only if > 0)
else:
    ap_clean = missing; quality = fallback_contaminated
```

The reconstruction is deliberately conservative: it recovers only **71 of the
2,773 fallback rows (2.56%)**, because the combined tag is used precisely when
the issuer does not report the accrual split. The resulting measurement
distribution is:

| AP measurement | Firm-years | CCC median, days | DPO median, days | Negative CCC |
|---|---:|---:|---:|---:|
| Direct trade AP | 24,201 | 80.53 | 47.90 | 11.53% |
| Reconstructed AP | 71 | 7.24 | 90.41 | 47.89% |
| **Clean AP (direct + reconstructed)** | **24,272** | **80.38** | **47.91** | **11.64%** |
| Contaminated AP | 2,702 | 3.69 | 112.39 | 48.22% |
| All rows (mixed AP) | 26,974 | 75.42 | 50.69 | 15.33% |

The contaminated rows are 10.0% of the panel and their median CCC is 3.7 days
against 80.4 on clean AP. The headline uses clean AP; the all-row number is a
sensitivity. The fallback is kept in `tag_ap` and in `tag_usage.csv` for
provenance, but it is not used as a trade payable in the headline measure.

## 6. Internal spot check against `companyfacts`

`src/verify_known_firms.py` compares the panel, tag by tag, with the latest 10-K
fact close to the same fiscal-year end for Fastenal (CIK 815556), Walmart
(104169) and Apple (320193), for fiscal years 2019, 2022 and 2023, across 7
concepts. The panel stores the FSDS month-end `ddate` while `companyfacts` stores
the issuer's exact period end (Apple's FY2019 closes on 2019-09-28), so the
matcher accepts a ±7-day gap; that is how the same period is compared rather than
two different ones.

This is an **internal spot check of parsing and period alignment**, not a
validation of the tag mapping: it uses the same tag selected by the panel and
does not test whether the ordered fallback chose the right concept, whether
another tag would have been preferable, or how well the extract covers firms
outside these three issuers.

Result (`outputs/validation.json`, `outputs/tables/known_firm_check.csv`):

```
n_comparisons = 63
n_match       = 63
n_unavailable = 0
max_abs_rel_diff = 0.0
all_match     = true
```

The denominator is 3 firms × 7 concepts × 3 years = 63. Failures stay in it: an
earlier version filtered to comparisons that had returned a value and reported
49/49, hiding 10 Apple rows whose only problem was the two-day period-end gap.

## 7. Quarterly panel

`src/build_quarterly.py` reads the 16 quarterly files and keeps:

- 10-Q and 10-Q/A forms only;
- current-period facts (`ddate == period`);
- one-quarter flows (`qtrs == 1`) and instant balances (`qtrs == 0`);
- USD, `us-gaap` facts only;
- period ends in calendar 2018–2022 (2018 is kept only to provide a year-earlier
  comparison for 2019Q1).

The panel has **72,811 firm-quarters / 8,097 firms / 20 quarters**. The 20
quarters include 2018Q1–2018Q4, which are not shock years but are needed for
year-on-year growth in 2019. Quarterly labels are derived from the period-end
date, not from the filing's `fy`/`fp`; three filings carry an implausible fiscal
year label, and 174 firm-quarters fall outside the calendar window.

`outputs/quarterly_stats.json` records every filter and count. Tag usage for the
quarterly panel is in `outputs/tables/quarterly_tag_usage.csv`.

## 8. Offline rebuild and known data gaps

- `python src/run_all.py` reruns the full pipeline from cache. Since every
  quarter is present, no network access is needed.
- `python src/download_sec.py --offline` rebuilds `manifest.json` from whatever
  parquet files exist (hashes recomputed, provenance note marked as such).
- `python src/download_sec.py --force --quarters 2021q4` re-fetches one quarter
  and restores its source-zip hash.
- FSDS quarterly files can be revised by the SEC. The manifest hashes pin the
  version used here; a fresh download may therefore produce slightly different
  bytes. The panel counts and headline results in this repo refer to the pinned
  cache.
- `companyfacts` is cached for three issuers only. It is an internal spot-check
  source, deliberately not a data source for the panel.
- **Write-down coverage is selected.** 4,657 annual rows (17.3%) and 959 firms
  report a write-down tag; the outcome is not available for the rest. The
  quarterly panel has 396 write-down/COGS observations before the shock window
  and 187/194 in the 2020/2022 pooled regressions. This is a tag-coverage gap,
  not a random sample.
- **The quarterly panel is short.** 2019q1–2022q4 supports a pre-shock 2019
  balance, the 2020 shock, a pre-shock 2021 balance and the 2022 shock; it cannot
  extend the quarterly analysis to 2023–2024.
