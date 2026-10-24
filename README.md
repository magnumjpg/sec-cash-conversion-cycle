# Cash Conversion and Resilience — 15 Years of SEC Filings

**Question.** How long is the cash conversion cycle (CCC) of US listed firms, is
it a stable characteristic or a fast mean-reverting ratio, and is it associated
with profitability and with how firms fared in the 2020 demand shock and the
2022 cost shock?

**Answer in one line.** The CCC is high (median 75 days), mostly a *firm* trait
rather than an industry one, quite persistent (ρ = 0.685, half-life 1.8 years),
and in this sample it is *positively* associated with ROA — the opposite of the
working-capital story — while its 2020/2022 shock exposure is weak and
non-monotone.

---

## Building the panel

The panel is built from SEC XBRL filings, not from a vendor. The source is the
SEC Financial Statement Data Sets (bulk extracts of the same facts as
`companyfacts`), 2010–2025 filings. Reasons for preferring the bulk files, and
the checks that were run before switching, are in `DECISIONS.md → D-01`.

| Step | Firm-years |
|---|---:|
| Flow and balance facts matched on the same fiscal-year end | 105,865 |
| − missing revenue / COGS / AR / inventory / AP | −77,938 |
| − revenue ≤ 0 or COGS ≤ 0 | −267 |
| − negative balance-sheet item | −1 |
| − financials & real estate (SIC 6000–6999) | −364 |
| − utilities (SIC 4900–4999) | −449 |
| − fewer than 3 usable years | −1,505 |
| **Main sample** | **25,341** |

The main sample covers **3,158 firms**, fiscal years **2010–2024**, and **58
two-digit SIC industries** (35 with at least 100 firm-years). Coverage is
**1,313 to 1,948 firm-years per year** (lowest in 2024, highest in 2013); this
pipeline does not decompose that decline. Tag choices are explicit and counted
in `outputs/tables/tag_usage.csv`; `DATA.md` reports the full attrition and tag
usage. Cross-source validation against the `companyfacts` API for Fastenal,
Walmart and Apple is **49/49 exact matches** across 7 concepts and 3 fiscal
years (`outputs/validation.json`).

All ratios use fiscal-year-end balances. Lags are used only when consecutive
fiscal-year ends are 350–380 days apart, so a year-end change does not create a
fake 15-month year.

## 1. Level and structure

| Measure | Median, days |
|---|---:|
| DSO (receivables / revenue) | 49.10 |
| DIO (inventory / COGS) | 84.27 |
| DPO (payables / COGS) | 50.99 |
| **CCC = DSO + DIO − DPO** | **74.97** |

The cross-section is wide (p25 = 25.97, p75 = 134.58) and **15.84% of firm-years
have a negative CCC**. Industry medians run from **−8.08 days in restaurants**
to **134.80 days in instruments**; communications (2.63), personal services
(7.84) and petroleum refining (18.87) also sit near or below zero. That is the
"negative CCC as a business model" group: they collect from customers before
they pay suppliers.

The decomposition is the more interesting result. On the screened, winsorized
sample (n = 23,846), only **6.0% of CCC variance is between industries**, while
**64.2% is between firms** and **35.8% is within firms over time**. Industry
labels explain very little; firm-specific terms and customer/supplier
relationships explain a lot. This is why the rest of the project estimates firm
effects rather than treating "industry practice" as the unit of analysis.

Headline medians are computed on the **unscreened** sample, as the charter
requires. Raw means are unusable — mean CCC is −249.7 days with an SD of
103,401 — because roughly 6% of XBRL rows contain scale errors (assets tagged in
millions, COGS off by 1,000×). For estimation only, rows with |CCC| > 3,650
days, assets < $1m or revenue < $1m are dropped: **1,495 rows (5.90%)**. The
screen is not neutral: the dropped group has a median CCC of −197.41 days, and
the kept sample's median is 77.93 days. That difference is disclosed, not
hidden.

## 2. Persistence: a slow-moving trait, not a fixed one

`CCC_it = α + ρ·CCC_i,t−1 + year FE`. Standard errors clustered by firm; no firm
fixed effect in the headline (Nickell bias with T ≈ 10 — the firm-FE version is
reported as a bound).

| Specification | ρ | Half-life, years | N |
|---|---:|---:|---:|
| **Headline (winsorized CCC)** | **0.685** (SE 0.023) | **1.83** | 20,576 |
| Raw CCC | 0.536 | 1.11 | 20,724 |
| Drop \|CCC\| > 365 days | 0.509 | 1.03 | 19,794 |
| Average balances | 0.662 | 1.68 | 17,691 |
| DSO only | 0.518 | 1.05 | 20,770 |
| DIO only | 0.523 | 1.07 | 20,748 |
| DPO only | 0.573 | 1.25 | 20,703 |
| Firm FE (Nickell-biased bound) | 0.266 | — | 20,576 |

About **31% of the gap to a firm's long-run CCC closes each year** (1 − ρ =
0.315). So CCC is persistent enough to be a meaningful firm characteristic, but
not so persistent that "improving CCC by X days" is a one-off lever: the
half-life is under two years, and the raw/trimmed estimates are lower still
(0.51–0.54). The level is definition-sensitive; quote it with the definition.

## 3. CCC and ROA: positive, small, and against the prior

`ROA_it = α_i + δ_t + β·CCC_it + γ·log(assets)_it + θ·gross_margin_it + ε_it`,
firm and year fixed effects, SEs clustered by firm, CCC and ROA winsorized 1/99
within industry-year.

| | Estimate |
|---|---:|
| β (ROA per CCC day) | **+0.000139** |
| SE / t / p | 0.000036 / 3.81 / 0.00014 |
| Standardized β (SD of ROA per SD of CCC) | 0.060 |
| N / firms | 23,408 / 2,994 |
| Within R² | 0.069 |

The sign is **positive**: 100 extra CCC days are associated with **+1.39
percentage points of ROA**, or 0.060 SD per SD. This contradicts the charter's
prior ("expect negative β") and should be stated plainly. It survives every ROA
specification in the robustness table (11 of 11 positive; 8 of 11 significant at
5%), ranging from +0.000040 with average balances to +0.000376 when
|CCC| > 365 is dropped. Without the gross-margin control the coefficient is
larger (+0.000184, SE 0.000039), so the controls attenuate rather than create
the result.

Two readings are consistent with the data, and this design cannot separate
them. (i) Long-CCC firms are concentrated in high-margin, made-to-order
manufacturing (instruments, machinery), where inventory and receivables are
part of a profitable business model. (ii) Firms with more working capital may
be able to support more sales and absorb shocks. A third reading — that
lengthening CCC *causes* higher ROA — is not supported by this design and is not
claimed. The association is small: 0.06 SD.

## 4. Shock exposure: mostly null, one weak margin result

Cross-sections with 2-digit SIC fixed effects and HC1 standard errors;
pre-shock CCC is the winsorized lagged value. Descriptive only.

| Outcome | β per CCC day | t | N |
|---|---:|---:|---:|
| 2020 revenue growth (2019→2020) | +0.000071 | 0.38 | 1,347 |
| 2020 ROA | +0.000244 | 3.29 | 1,344 |
| 2020 cash / assets | −0.000048 | −1.07 | 1,329 |
| 2022 gross-margin change (2021→2022), β × 100, pp | −0.006 | −2.37 | 1,441 |
| 2022 ROA | −0.000005 | −0.05 | 1,440 |

- **2020 demand shock:** no association with revenue growth. The quintile
  pattern is noise (+2.9%, −2.4%, −3.6%, −3.6%, +0.9%), and the 2020 ROA
  coefficient, though significant, is non-monotone (Q1 −2.1%, Q2 +1.3%,
  Q3 +2.0%, Q4 +1.8%, Q5 −1.4%). Cash holdings show nothing (t = −1.07).
- **2022 cost shock:** the linear margin slope is negative and significant at
  5% (−0.006 pp per CCC day, i.e. −0.6 pp per 100 days), but the quintile
  medians are **not monotone** (−0.81, −0.35, −0.75, −0.41, −0.93 pp). The
  slope is driven by both tails, not by a clean dose–response. 2022 ROA is
  flat.

Read together: if CCC mattered for resilience, the 2020 revenue and cash
outcomes are where it should show up most clearly, and they do not. The 2022
margin result is the only one that would survive a casual read, and its
non-monotonicity argues against over-interpreting it.

## What this does not prove

- **No causality.** CCC is chosen jointly with industry, growth, bargaining
  power, supplier terms and product mix. A positive CCC–ROA coefficient does not
  mean that lengthening CCC raises ROA.
- **No dollar value of a CCC day.** That needs a cost of capital, a financing
  mix and an assumption about what happens to the freed cash. It is not
  identified here and is deliberately not computed.
- **No market test.** Without CRSP/Compustat there are no returns or event
  windows; "resilience" is accounting profitability and cash only.
- **The shock exercises are cross-sections.** One observation per firm plus
  industry FE cannot separate CCC from an unobserved firm trait correlated with
  it.
- **Not representative of all listed firms.** Requiring inventory and COGS
  selects industrial and retail firms, so 15.84% negative CCC is a lower bound
  for the listed universe.
- **Definition sensitivity.** Winsorization and trimming move the persistence
  estimate between 0.51 and 0.69 and the ROA coefficient between 0.00004 and
  0.00038. Full list: `LIMITATIONS.md`.

## Reproduce

```
python src/download_sec.py            # all 64 quarters (cached; no-op if present)
python src/run_all.py                 # panel → validation → results → figures
python src/run_all.py --test          # same + pytest
python src/analysis.py                # re-estimate only
python src/figures.py                 # redraw figures only
```

`outputs/run_log.json` records each step's status, duration and error (if any).
The pipeline reruns fully offline from `data/raw/`; `data/manifest.json` pins
the URL, byte size and SHA-256 of every source file. Data volumes, cache layout
and the full attrition funnel are in `DATA.md`.

| Command | Status |
|---|---|
| `python src/download_sec.py --quarters 2021q4 --force` | ok (24 s) |
| `python src/build_panel.py` | ok — 25,341 / 3,158 |
| `python src/analysis.py` | ok |
| `python src/figures.py` | ok — 6 figures |
| `python src/verify_known_firms.py` | ok — 49/49 |
| `python src/run_all.py --test` | ok — 16 tests passed |

## Files

```
02_working_capital_sec/
  README.md  DATA.md  METHOD.md  LIMITATIONS.md  DECISIONS.md  .gitignore
  src/
    tags.py              tag mapping, versioned; SIC division labels
    download_sec.py      SEC FSDS download, cache, manifest, rate limit
    build_panel.py       facts → firm-year panel, attrition, measures
    analysis.py          descriptives, persistence, CCC–ROA, shocks, robustness
    figures.py           6 figures, every annotation read from results.json
    verify_known_firms.py  spot check vs companyfacts
    run_all.py           one-command orchestration
  tests/test_pipeline.py
  data/
    manifest.json        URLs + bytes + sha256 of every cached file
    processed/panel.csv  main sample (25,341 rows)
  outputs/
    results.json         canonical numbers used in this README
    validation.json      Fastenal / Walmart / Apple check
    tables/*.csv         attrition, tag usage, industry/year summaries, robustness
    figures/*.png        6 figures
```

Figures: CCC by industry (fig1), persistence scatter (fig2), CCC vs ROA within
firm-year (fig3), 2020 shock exposure (fig4), CCC time series (fig5), 2022
margin change by pre-shock CCC quintile (fig6).

## Headline numbers, all from `outputs/results.json`

| Key | Value |
|---|---:|
| `panel.rows` / `panel.firms` | 25,341 / 3,158 |
| `panel.median_ccc` | 74.965423 |
| `panel.share_negative_ccc` | 0.158399 |
| `descriptives.variance_decomposition.share_between_industries_sic2` | 0.060055 |
| `persistence.beta` / `persistence.half_life_years` | 0.685315 / 1.834323 |
| `ccc_roa.beta` / `ccc_roa.t` | 0.000139 / 3.813842 |
| `ccc_roa.beta_standardized` | 0.060372 |
| `shock_2020.revenue_growth.t` | 0.377976 |
| `shock_2022.margin_change.beta` / `.t` | −0.000060 / −2.371609 |
| `validation.n_match` / `validation.n_comparisons` | 49 / 49 |
