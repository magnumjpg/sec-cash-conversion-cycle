# DATA

Everything here is built from public SEC filings. No synthetic, imputed or
vendor-adjusted data enter the panel. Every number in `README.md` is produced by
`src/run_all.py` and stored in `outputs/results.json`.

## 1. Sources

| Source | URL | Used for |
|---|---|---|
| SEC Financial Statement Data Sets (FSDS) | `https://www.sec.gov/files/dera/data/financial-statement-data-sets/{q}.zip` | main panel, 2010q1–2025q4 |
| SEC company tickers | `https://www.sec.gov/files/company_tickers.json` | ticker/exchange lookup only |
| SEC company tickers + exchange | `https://www.sec.gov/files/company_tickers_exchange.json` | `data/raw/tickers.parquet` |
| SEC `companyfacts` API | `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` | validation of 3 issuers only |

The charter preferred `companyfacts` and suggested the Frames API. Frames were
tested and rejected because the payload has no `form`, `filed`, `fp` or `sic`,
which makes three charter rules unenforceable (10-K-only, latest-filing-wins,
SIC exclusions). FSDS is the SEC's own bulk extract of the same XBRL facts,
exposes all of those fields, and includes delisted filers. Full reasoning and the
trade-off table: `DECISIONS.md → D-01`.

User-Agent sent to the SEC: `Jaime Perez portfolio research magnum.jpg@gmail.com`.
Requests are throttled to **4 per second** (charter ceiling: 5), with 6 retries
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
    zips/                           empty: source zips deleted after extraction
    company_tickers*.json
    tickers.parquet
    companyfacts/CIK*.json         validation cache (3 firms)
  processed/
    panel.csv                     main sample, inspectable (committed)
    panel.parquet                 same, typed (gitignored)
    panel_full.csv.gz             incl. financials/utilities (gitignored)
```

Volumes from the latest build:

| Item | Count / size |
|---|---|
| Quarters cached | 64 (2010q1–2025q4) |
| Source zips downloaded | 64, **5.39 GB**, deleted after extraction |
| Derived parquet files retained | 192 (sub + num + forms per quarter), **33.2 MB** |
| Manifest entries | 258 (194 retained on disk, 64 source zips with hash only) |
| Annual filings in cache | 105,027 |
| Usable firm-years after all filters | 25,341 (3,158 firms) |

The zips are not kept; the **SHA-256 of each zip is**. This is the provenance
chain: `manifest.json` pins the exact source file that produced each parquet,
and the parquet hashes pin what the panel was built from.

## 3. Manifest schema

`data/manifest.json` is a single object:

```json
{
  "generated_at_utc": "2026-10-24T22:34:11+00:00",
  "user_agent": "Jaime Perez portfolio research magnum.jpg@gmail.com",
  "files": [
    {
      "url": "https://www.sec.gov/files/dera/data/financial-statement-data-sets/2021q4.zip",
      "path": "data/raw/fsds/2021q4_sub.parquet",
      "bytes": 28519,
      "sha256": "9a94959e737bbd9c2777e70fd6ade69cb09f8cf484f9cda9cd5473641aa4dbce",
      "fetched_at_utc": "2026-10-24T22:34:11+00:00",
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
| fact | us-gaap facts, project tags, annual forms, consolidated, qtrs 0/4 | 2,536,529 | |
| fact | dropped: reporting currency not USD | 60,858 | 416 |
| fact | dropped: IFRS taxonomy (`ifrs-full`) | 23,790 | |
| fact | dropped: duplicate tag/period, older filing | 1,257,640 | |
| fact | dropped: flow fact with `qtrs != 4` | 1,603 | |
| firm-year | flow + balance matched on identical fiscal-year end | 105,865 | 14,232 |
| firm-year | dropped: missing revenue/COGS/AR/inventory/AP | 77,938 | 12,525 |
| firm-year | dropped: revenue ≤ 0 or COGS ≤ 0 | 267 | 216 |
| firm-year | dropped: negative balance-sheet item | 1 | 1 |
| firm-year | dropped: financials & real estate (SIC 6000–6999) | 364 | 85 |
| firm-year | dropped: utilities (SIC 4900–4999) | 449 | 79 |
| firm-year | dropped: fewer than 3 usable years | 1,505 | 905 |
| **firm-year** | **main sample** | **25,341** | **3,158** |

Segment (`segments`) and co-registrant (`coreg`) facts were dropped at download
time; they are not counted as separate rows above. The panel is industrial and
retail by construction, because it requires inventory and COGS.

## 5. Tag usage

Recorded per row in `tag_revenue`, `tag_cogs`, `tag_ar`, `tag_inventory`,
`tag_ap`; aggregated in `outputs/tables/tag_usage.csv`. Shares below are of the
25,341 panel rows.

| Concept | Tag | Rows | Share | Tier |
|---|---|---:|---:|---|
| revenue | `RevenueFromContractWithCustomerExcludingAssessedTax` | 7,860 | 31.0% | charter (preferred) |
| revenue | `SalesRevenueNet` | 7,181 | 28.3% | charter |
| revenue | `Revenues` | 6,890 | 27.2% | charter |
| revenue | `RevenueFromContractWithCustomerIncludingAssessedTax` | 1,704 | 6.7% | charter |
| revenue | `SalesRevenueGoodsNet` | 1,706 | 6.7% | **extra** (last resort) |
| cogs | `CostOfGoodsAndServicesSold` | 12,558 | 49.6% | charter (preferred) |
| cogs | `CostOfRevenue` | 7,684 | 30.3% | charter |
| cogs | `CostOfGoodsSold` | 5,099 | 20.1% | charter |
| ar | `AccountsReceivableNetCurrent` | 22,454 | 88.6% | charter (preferred) |
| ar | `ReceivablesNetCurrent` | 2,777 | 11.0% | charter |
| ar | `AccountsReceivableGrossCurrent` | 110 | 0.4% | charter |
| inventory | `InventoryNet` | 25,158 | 99.3% | charter (preferred) |
| inventory | `InventoryGross` | 112 | 0.4% | charter |
| inventory | `InventoryFinishedGoodsNetOfReserves` | 71 | 0.3% | charter |
| ap | `AccountsPayableCurrent` | 22,542 | 89.0% | charter (preferred) |
| ap | `AccountsPayableAndAccruedLiabilitiesCurrent` | 2,799 | 11.0% | charter |

No `extra` tag is used for COGS, receivables, inventory or payables in the
final panel. Robustness spec 9 restricts to firm-years where the *preferred*
charter tag supplied every input.

## 6. Validation against `companyfacts`

`src/verify_known_firms.py` compares the panel, tag by tag, with the latest 10-K
fact at the same fiscal-year end for Fastenal (CIK 815556), Walmart (104169) and
Apple (320193), for fiscal years 2019, 2022 and 2023, across 7 concepts.

Result (`outputs/validation.json`, `outputs/tables/known_firm_check.csv`):

```
n_comparisons = 49
n_match       = 49
max_abs_rel_diff = 0.0
all_match     = true
```

This is a spot check of tag mapping and period alignment, not a full
reconciliation of the panel.

## 7. Offline rebuild and known data gaps

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
- `companyfacts` is cached for three issuers only. It is a validation source,
  deliberately not a data source for the panel.
