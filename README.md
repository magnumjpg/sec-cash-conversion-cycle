# Cash Conversion and Resilience — 15 Years of SEC Filings

**At a glance**

- **Question:** how long is the cash conversion cycle (CCC) of US listed firms, and is it associated with profitability and with the 2020/2022 shocks?
- **Data:** SEC XBRL Financial Statement Data Sets, fiscal years 2010–2024, **25,341 firm-years / 3,158 firms**.
- **Method:** CCC from fiscal-year-end balances; firm+year FE for the ROA association; pooled and firm-FE AR(1) for persistence.
- **Headline:** pooled firm-year median CCC **74.97 days** (median of firm-level medians **66.34**); CCC–ROA **β = +0.000139**.
- **Main caveat:** the CCC level is tag-sensitive (11.0% of panel rows use an AP fallback), persistence is a **range (ρ ≈ 0.27–0.69)**, and everything here is descriptive.

**Question.** How long is the cash conversion cycle (CCC) of US listed firms, is
it a stable characteristic or a fast mean-reverting ratio, and is it associated
with profitability and with how firms fared in the 2020 demand shock and the
2022 cost shock?

**Answer in one line.** The pooled firm-year median CCC is **75 days** on 25,341
firm-years (the median of firm-level medians is 66.3), and CCC is mostly a
*firm* trait rather than an industry one (64.2% of its variance is between
firms, 6.0% between industries). Persistence is a **range, not a point**: a
pooled AR(1) gives ρ = 0.685 (half-life 1.8 years, biased up by persistent
between-firm differences), a firm-FE AR(1) gives 0.266 (half-life 0.5 years,
Nickell-biased down), and an Anderson–Hsiao IV gives 0.409. In this sample CCC
is *positively* but weakly associated with ROA (β = +0.000139, n = 23,408) — the
opposite of the working-capital story — while its FY2020/FY2022 shock exposure
is weak and non-monotone.

---

## Building the panel

The panel is built from SEC XBRL filings, not from a vendor. The source is the
SEC Financial Statement Data Sets (bulk extracts of the same facts as
`companyfacts`), 2010q1–2025q4 quarterly extracts. Reasons for preferring the
bulk files, and the checks that were run before switching, are in
`DECISIONS.md → D-01`.

| Step | Firm-years |
|---|---:|
| Flow and balance facts matched on the same fiscal-year end | 116,988 |
| − duplicate fiscal-year label | −1,567 |
| − fiscal year outside 2010–2024 | −9,556 |
| **In the 2010–2024 window** | **105,865** |
| − missing revenue / COGS / AR / inventory / AP | −77,938 |
| − revenue ≤ 0 or COGS ≤ 0 | −267 |
| − negative balance-sheet item | −1 |
| − financials & real estate (SIC 6000–6999) | −364 |
| − utilities (SIC 4900–4999) | −449 |
| − fewer than 3 usable years | −1,505 |
| **Main sample** | **25,341** |

The 77,938-row missing-input drop is not one homogeneous bucket. Inventory is
missing in 63,363 of those rows (81.3%), COGS in 55,272 (70.9%), AR in 47,782
(61.3%), AP in 31,957 (41.0%) and revenue in 26,071 (33.5%); 57,563 rows
(73.9%) miss more than one input and 20,375 (26.1%) miss exactly one. The item
counts overlap and sum to 224,445 item-cells, so they must not be read as
disjoint groups. The full table is `outputs/tables/attrition_missing_items.csv`.

The main sample covers **3,158 firms**, fiscal years **2010–2024**, and **58
two-digit SIC industries** (35 with at least 100 firm-years). Coverage is
**1,313 to 1,948 firm-years per year** (lowest in 2024, highest in 2013); the
decline is not decomposed here. Tag choices are explicit and counted
in `outputs/tables/tag_usage.csv`; `DATA.md` reports the full attrition and tag
usage. An **internal spot check** against the `companyfacts` API for Fastenal,
Walmart and Apple is **63/63 exact matches** across 7 concepts and 3 fiscal
years (`outputs/validation.json`). The denominator is every comparison the
design sets out to make, not only the ones that returned a value: the match
allows a ±7-day gap because the panel stores month-end fiscal-year ends while
`companyfacts` stores the issuer's exact period end (Apple's FY2019 10-K closes
on 2019-09-28). This check validates the extractor's parsing and period
alignment for three issuers; it does **not** validate the tag choice, the
ordered fallback logic or coverage of the wider panel.

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

The components are separate median days on 25,341 firm-years, so they do not add
up: 49.10 + 84.27 − 50.99 = 82.38. The **pooled firm-year median CCC is 74.97
days**, while the **median of firm-level median CCC is 66.34 days**; the two are
different statistics and neither is "the" median firm. The 7.4-day gap between
82.38 and 74.97 is not an error; it is what happens when medians of ratios are
combined. The CCC row is the headline; the component rows describe the
distribution of each term.

The cross-section is wide (p25 = 25.97, p75 = 134.58) and **15.84% of firm-years
have a negative CCC**. Industry medians run from **−8.08 days in restaurants**
to **134.80 days in instruments**; communications (2.63), personal services
(7.84) and petroleum refining (18.87) also sit near or below zero. That is the
"negative CCC as a business model" group: they collect from customers before
they pay suppliers.

The pooled CCC level mixes two payables concepts, and the project does not hide
it. In the main panel, 2,799 firm-years (11.0%) use
`AccountsPayableAndAccruedLiabilitiesCurrent` rather than
`AccountsPayableCurrent`; in the pre-filter tagged universe the fallback share is
21.6% (`results.json → tag_sensitivity.fallback_share_tag_usage`). Preferred-AP
firm-years have a median CCC of **80.54 days** and median DPO of **47.99**;
fallback-AP firm-years have a median CCC of **3.76 days** and median DPO of
**111.69**. The fallback adds accrued liabilities to trade payables, so it raises
DPO and *lowers* CCC: the pooled 74.97 days understates the preferred-tag level.
The fallback is retained because the charter mandates ordered fallbacks, not
because the two tags are interchangeable. Robustness spec 9 restricts every
input to the preferred charter tag and is therefore the cleaner measurement; it
gives β = +0.000123, t = 1.83, p = 0.068 on n = 4,542 — weaker than the
mixed-tag headline and no longer significant at 5%.

The negative tail is also tag-sensitive. **48.1% of the fallback rows are
negative**, against **11.8% of the 22,542 preferred-tag rows**. The fallback
supplies 1,347 of the 4,014 negative rows (33.6%). The headline 15.84% is
therefore not a clean business-model count: on preferred-tag rows alone it is
11.83%. The direction is conservative for the "negative CCC exists" claim, but
individual fallback rows may reflect accrued liabilities rather than trade
payables.

The decomposition is the more interesting result, and it is two partitions, not
one. On the screened, winsorized sample (n = 23,846):

- **between industries vs within industries:** 6.0% between 2-digit SIC
  industries, 94.0% within them;
- **between firms vs within firms over time:** 64.2% between firms, 35.8% within
  a firm across years.

The two shares cannot be added: "between industries" is nested inside "between
firms", so 6.0 + 64.2 + 35.8 = 106.0, not 100. Industry labels explain very
little; unobserved firm-level factors — business model, bargaining power,
product mix — account for most of the level differences. This is why the rest
of the project estimates firm effects rather than treating "industry practice"
as the unit of analysis.

Headline medians are computed on the **unscreened** sample, as the charter
requires. Raw means are unusable — mean CCC is −249.7 days with an SD of
103,401 — because roughly 6% of rows are not interpretable at face value (mostly
XBRL scale errors: assets tagged in millions, COGS off by 1,000×, plus micro-caps).
For estimation only, rows with |CCC| > 3,650
days, assets < $1m or revenue < $1m are dropped: **1,495 rows (5.90%)**. The
screen is not neutral: the dropped group has a median CCC of −197.41 days, and
the kept sample's median is 77.93 days. That difference is disclosed, not
hidden.

## 2. Persistence: a range, bounded by two biased estimators

Two estimators bracket the AR(1) coefficient; neither is the truth on its own.

- **Pooled AR(1):** `CCC_it = α + ρ·CCC_i,t−1 + year FE`, SEs clustered by firm,
  **no firm FE**. ρ = **0.685** (half-life 1.83 years). Because time-invariant
  firm differences remain in the error, this estimate is **biased upward** as a
  measure of within-firm persistence.
- **Firm-FE AR(1):** the same model with firm fixed effects. ρ = **0.266**
  (half-life 0.52 years). With T ≈ 10, a lagged dependent variable and firm FE
  is **Nickell-biased downward**, so this is a lower bound.
- **Anderson–Hsiao IV:** first differences with year dummies, instrumenting the
  lagged difference with the twice-lagged level. ρ = **0.409** (SE 0.128,
  N = 14,435), between the two.

The defensible statement is a range of roughly **0.27–0.69**, with a half-life
of roughly **0.5–1.8 years**, not a point estimate. The pooled
`1 − ρ = 0.315` is an implication of that pooled AR(1), not the within-firm
speed at which a firm's gap to its long-run CCC closes; this design does not
identify the latter.

| Specification | ρ | Half-life, years | N |
|---|---:|---:|---:|
| **Pooled AR(1) (winsorized CCC, year FE, no firm FE)** | **0.685** (SE 0.023) | **1.83** | 20,576 |
| Firm FE (Nickell-biased downward) | 0.266 (SE 0.045) | 0.52 | 20,576 |
| Anderson–Hsiao IV (first differences) | 0.409 (SE 0.128) | 0.77 | 14,435 |
| Raw CCC, pooled | 0.536 | 1.11 | 20,724 |
| Drop \|CCC\| > 365 days, pooled | 0.509 | 1.03 | 19,794 |
| Average balances, pooled | 0.662 | 1.68 | 17,691 |
| DSO only (winsorized), pooled | 0.723 | 2.14 | 20,576 |
| DIO only (winsorized), pooled | 0.651 | 1.62 | 20,576 |
| DPO only (winsorized), pooled | 0.618 | 1.44 | 20,564 |

The by-industry table uses the same **pooled** estimator (year FE only, so it
mixes between- and within-firm variation) and is labelled that way in
`outputs/tables/persistence_by_industry_ccc.csv`; a firm-FE ρ is reported
alongside it for every industry where the within transformation is estimable.
Those industry firm-FE estimates are noisy, and one is slightly negative, so
they should not be read as precise industry speeds.

CCC is persistent enough to be a meaningful firm characteristic, but the data
do not support a single "X% of the gap closes each year" claim: the pooled and
within estimators disagree by a factor of about 2.6.

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
prior ("expect negative β") and should be stated plainly. The sign holds in all
11 main-sample specifications in the robustness table (ten ROA variants and a
2020 growth placebo), but only **7 of 11** are significant at 5%
(`robustness_summary.n_significant_p05`), ranging from
+0.000040 with average balances to +0.000376 when |CCC| > 365 is dropped. The
cleanest measurement — spec 9, which requires the preferred charter tag for
every input — is weaker still (β = +0.000123, p = 0.068), so the tag mixture is
not generating the positive sign but it does flatter its precision. Without the
gross-margin control the coefficient is larger (+0.000184, SE 0.000039), so the
controls attenuate rather than create the result.

Two readings are consistent with the data, and this design cannot separate
them. (i) Long-CCC firms are concentrated in high-margin, made-to-order
manufacturing (instruments, machinery), where inventory and receivables are
part of a profitable business model. (ii) Firms with more working capital may
be able to support more sales and absorb shocks. A third reading — that
lengthening CCC *causes* higher ROA — is not supported by this design and is not
claimed. The association is small: 0.06 SD.

## 4. Shock exposure: weak and non-monotone

Cross-sections with 2-digit SIC fixed effects and HC1 standard errors;
pre-shock CCC is the winsorized lagged value. Descriptive only. The labels are
issuer **fiscal years**, not calendar windows: 28.6% of FY2020 rows and 28.4% of
FY2022 rows have a non-December year-end, so a June-ending firm's "FY2020"
covers July 2019–June 2020. A December-only re-estimation is reported below.

| Outcome | β per CCC day | t | N |
|---|---:|---:|---:|
| FY2020 revenue growth (FY2019→FY2020) | +0.000071 | 0.38 | 1,347 |
| FY2020 ROA | +0.000244 | 3.29 | 1,344 |
| FY2020 cash / assets | −0.000048 | −1.07 | 1,329 |
| FY2022 gross-margin change (FY2021→FY2022), β × 100, pp | −0.006 | −2.37 | 1,441 |
| FY2022 ROA | −0.000005 | −0.05 | 1,440 |

| December year-ends only | β per CCC day | t | N |
|---|---:|---:|---:|
| FY2020 revenue growth | +0.000152 | 0.72 | 939 |
| FY2020 ROA | +0.000216 | 2.87 | 937 |
| FY2022 gross-margin change, β × 100, pp | −0.0059 | −1.72 | 1,025 |
| FY2022 ROA | −0.000037 | −0.37 | 1,024 |

- **FY2020 demand shock:** revenue growth is not detectable (t = 0.38, and
  t = 0.72 on December year-ends), so the data cannot distinguish "no
  association" from "too imprecise to see one". The quintile pattern is
  non-monotone (+2.9%, −2.4%, −3.6%, −3.6%, +0.9%), and the FY2020 ROA
  coefficient, though significant, is non-monotone (Q1 −2.1%, Q2 +1.3%,
  Q3 +2.0%, Q4 +1.8%, Q5 −1.4%). Cash holdings show nothing (t = −1.07).
- **FY2022 cost shock:** the full-sample linear margin slope is negative
  (−0.006 pp per CCC day, i.e. −0.6 pp per 100 days, t = −2.37), but the
  December-only slope is −0.0059 with t = −1.72, so it does not survive the
  calendar-aligned check at 5%. The quintile medians are **not monotone**
  (−0.81, −0.35, −0.75, −0.41, −0.93 pp). The slope is driven by both tails,
  not by a clean dose–response. FY2022 ROA is flat.

Read together: if CCC mattered for resilience, the 2020 revenue and cash
outcomes are a natural place to look, and no association is detectable there.
The FY2022 margin result is the only one that would survive a casual read, and
it loses significance when the outcome window is aligned to the calendar.

One charter outcome is **absent**: inventory write-downs. The cached tag slice
does not contain write-down tags and the source zips were deleted, so recovering
them requires re-downloading the quarterly extracts (`DECISIONS.md → D-12`). The
resilience evidence here is profitability, revenue, cash and gross margin only.

## What this does not prove

- **No causality.** CCC is chosen jointly with industry, growth, bargaining
  power, supplier terms and product mix. A positive CCC–ROA coefficient does not
  mean that lengthening CCC raises ROA.
- **No dollar value of a CCC day.** That needs a cost of capital, a financing
  mix and an assumption about what happens to the freed cash. It is not
  identified here and is deliberately not computed.
- **No market test.** Without CRSP/Compustat there are no returns or event
  windows; "resilience" is accounting profitability and cash only.
- **No inventory write-down outcome.** Write-down tags were never extracted;
  recovering them needs a cache rebuild (`DECISIONS.md → D-12`).
- **The shock exercises are cross-sections.** One observation per firm plus
  industry FE cannot separate CCC from an unobserved firm trait correlated with
  it.
- **Not representative of all listed firms.** Requiring inventory and COGS
  selects industrial and retail firms, so 15.84% negative CCC is a lower bound
  for the listed universe on that dimension; it is also tag-sensitive (11.8% on
  preferred-tag rows, 48.1% on the accrued-liabilities fallback).
- **The CCC level is tag-mixed.** 11.0% of panel firm-years use an AP fallback
  that includes accrued liabilities; it lowers the pooled CCC median (74.97)
  relative to the preferred-tag median (80.54). Spec 9 isolates preferred tags
  and is weaker (`p = 0.068`), not stronger.
- **No identified within-firm adjustment speed.** The pooled AR(1) (0.685) is
  biased up by persistent firm differences and the firm-FE AR(1) (0.266) is
  Nickell-biased down; the data bound the parameter, they do not pin it down.
- **Definition sensitivity.** Winsorization, trimming and the persistence
  estimator move the persistence estimate between 0.27 and 0.69 and the ROA
  coefficient between 0.00004 and 0.00038. Full list: `LIMITATIONS.md`.

## Literature and positioning

The working-capital literature mostly reports a *negative* association between
CCC and profitability; this panel is a descriptive measurement exercise, not a
causal test, and its positive coefficient is a fact to explain rather than a
policy lever.

- **Deloof (2003), "Does Working Capital Management Affect Profitability of
  Belgian Firms?", *Journal of Business Finance & Accounting*.** Establishes the
  negative CCC–profitability prior on firm-level panel data; informs the
  benchmark this project contradicts.
- **García-Teruel & Martínez-Solano (2007), "Effects of Working Capital
  Management on SME Profitability", *International Journal of Managerial
  Finance*.** Extends that prior to small firms and short panels; informs the
  role of sample composition.
- **Hill, Kelly & Highfield (2010), "Net Operating Working Capital Behavior: A
  First Look", *Financial Management*.** Documents large cross-firm differences
  in working-capital intensity; motivates the between-firm variance
  decomposition here.
- **Baños-Caballero, García-Teruel & Martínez-Solano (2014), "Working Capital
  Management, Corporate Performance, and Financial Constraints", *Journal of
  Business Research*.** Shows the CCC–performance relation can be non-linear and
  financing-constrained; informs why a single linear slope is only descriptive.
- **Aktas, Croci & Petmezas (2015), "Is Working Capital Management
  Value-Enhancing? Evidence from Firm Performance and Investments", *Journal of
  Corporate Finance*.** Links working-capital adjustment to investment and
  value; informs the interpretation of CCC as a firm trait rather than a free
  lever.
- **Fazzari & Petersen (1993), "Working Capital and Fixed Investment", *RAND
  Journal of Economics*.** Treats working capital as a financing constraint;
  informs the 2020/2022 shock framing and the limits of an accounting-only
  resilience test.
- **Bates, Kahle & Stulz (2009), "Why Do U.S. Firms Hold So Much More Cash than
  They Used To?", *Journal of Finance*.** Documents the secular rise in
  corporate liquidity; informs the cash/assets outcome and the need to separate
  cash policy from working-capital policy.

The gap this project fills is measurement, not identification: the contribution
is a reproducible 2010–2024 XBRL panel with **tag-level provenance for every
input**, an explicit fallback map, and a disclosure of what the tag mix does to
the headline level. It is not a causal estimate of the return to shortening the
CCC, and it does not use the CRSP/Compustat data that most of the cited papers
use.

## Reproduce

```
python src/download_sec.py            # all cached quarters (no-op if present)
python src/run_all.py                 # panel → validation → results → figures
python src/run_all.py --test          # same + pytest
python src/analysis.py                # re-estimate only
python src/figures.py                 # redraw figures only
```

`outputs/run_log.json` records each step's status, duration and error (if any).
The pipeline reruns fully offline from `data/raw/`; `data/manifest.json` pins
the URL, byte size and SHA-256 of every source file. All JSON outputs are strict
JSON: undefined numbers are written as `null`, never `NaN` or `Infinity`. Data
volumes, cache layout and the full attrition funnel are in `DATA.md`.

| Command | Status |
|---|---|
| `python src/download_sec.py` | ok — 64/64 quarters cached |
| `python src/download_sec.py --quarters 2021q4 --force` | ok (24 s) |
| `python src/build_panel.py` | ok — 25,341 / 3,158 |
| `python src/analysis.py` | ok |
| `python src/figures.py` | ok — 6 figures |
| `python src/verify_known_firms.py` | ok — internal spot check 63/63 |
| `python src/run_all.py --skip-download --test` | ok — 29 tests passed |

## Files

```
02_working_capital_sec/
  README.md  DATA.md  METHOD.md  LIMITATIONS.md  DECISIONS.md
  RED_TEAM.md  ANALYSIS_LOG.md  .gitignore
  src/
    tags.py              tag mapping, versioned; SIC division labels
    json_utils.py        strict JSON writers (NaN/Infinity -> null)
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
    raw/                 not committed; rebuilt from the manifest (DATA.md)
  outputs/
    results.json         canonical numbers used in this README
    validation.json      internal spot check (Fastenal / Walmart / Apple)
    tables/*.csv         attrition, missing-input decomposition, tag usage,
                         industry/year summaries, robustness
    figures/*.png        6 figures
  requirements.txt       pinned Python dependencies
  LICENSE                MIT
  .github/workflows/ci.yml  install + pytest on Python 3.11
```

Figures: CCC by industry (fig1), persistence scatter (fig2), CCC vs ROA within
firm-year (fig3), 2020 shock exposure (fig4), CCC time series (fig5), 2022
margin change by pre-shock CCC quintile (fig6).

## Headline numbers, all from `outputs/results.json`

| Key | Value |
|---|---:|
| `panel.rows` / `panel.firms` | 25,341 / 3,158 |
| `panel.median_ccc` | 74.965423 |
| `tag_sensitivity.median_of_firm_median_ccc` | 66.33565 |
| `panel.share_negative_ccc` | 0.158399 |
| `tag_sensitivity.fallback_ap.ccc_median` / `.dpo_median` | 3.759441 / 111.691347 |
| `tag_sensitivity.preferred_ap.ccc_median` / `.dpo_median` | 80.537284 / 47.993974 |
| `tag_sensitivity.preferred_only_ccc_roa.beta` / `.p` | 0.000123 / 0.067856 |
| `descriptives.variance_decomposition.share_between_industries_sic2` | 0.060055 |
| `persistence.beta` / `persistence.half_life_years` | 0.685315 / 1.834323 |
| `persistence.with_firm_fe.rho` / `.half_life_years` | 0.266371 / 0.523974 |
| `persistence.anderson_hsiao.rho` / `.se` | 0.408633 / 0.128076 |
| `robustness_summary.n_significant_p05` / `.n_specs_main_sample` | 7 / 11 |
| `ccc_roa.beta` / `ccc_roa.t` | 0.000139 / 3.813842 |
| `ccc_roa.beta_standardized` | 0.060372 |
| `shock_2020.revenue_growth.t` | 0.377976 |
| `shock_2022.margin_change.beta` / `.t` | −0.000060 / −2.371609 |
| `shock_window.shock_2022_december.margin_change.t` | −1.723595 |
| `rank_check.median_spearman` / `.share_positive` | 0.0 / 0.481066 |
| `validation.n_match` / `validation.n_comparisons` | 63 / 63 |

---

## Resumen en español

El proyecto construye un panel de **25.341 empresas-año (3.158 empresas, 2010–2024)** a partir de los ficheros XBRL de la SEC, no de un proveedor de datos. El ciclo de conversión de caja (CCC) mediano agrupado es de **75 días** (mediana de las medianas por empresa: 66,3; DSO 49,1; DIO 84,3; DPO 51,0; los componentes son medianas separadas y no suman 74,97), y un **15,8%** de las observaciones tiene CCC negativo (11,8% si se excluyen las filas que usan la etiqueta de acreedores con devengos). El nivel está mezclado por etiquetas: las filas con la etiqueta preferida de acreedores tienen CCC mediano de 80,54 días y las de la etiqueta alternativa de 3,76; la alternativa eleva el DPO y por tanto infravalora el CCC agrupado.

El resultado estructural más interesante es que **solo el 6,0% de la varianza del CCC es entre industrias** (94,0% dentro de ellas) y que el **64,2% es entre empresas** (35,8% dentro de la misma empresa a lo largo del tiempo). Son dos particiones solapadas: no suman 100. La etiqueta sectorial explica muy poco; los factores no observados de la empresa explican la mayor parte.

La persistencia es un **rango, no un punto**: el AR(1) agrupado da ρ = 0,685 (semivida 1,8 años, sesgado al alza por diferencias persistentes entre empresas), el AR(1) con efectos fijos de empresa da 0,266 (semivida 0,5 años, sesgado a la baja por Nickell) y el IV de Anderson–Hsiao da 0,409; la verdad está entre ambos, aproximadamente 0,27–0,69. La asociación con la rentabilidad es **positiva y pequeña** (+1,39 puntos de ROA por cada 100 días de CCC, 0,06 desviaciones típicas), en contra de la hipótesis de partida, y solo 7 de las 11 especificaciones principales son significativas al 5%; con la etiqueta preferida en todas las entradas (especificación 9) el coeficiente es más débil (p = 0,068). Se documenta como asociación, no como efecto causal, y se advierte de que la correlación de rangos dentro de la empresa típica es cero (positiva solo en el 48,1% de las empresas): el coeficiente lo identifican las empresas con mucha variación de CCC.

En los shocks de 2020 y 2022 no hay un patrón robusto: el crecimiento de ingresos del año fiscal 2020 no se asocia al CCC (t = 0,38; t = 0,72 si se usan solo cierres de diciembre), y el margen de 2022 tiene pendiente negativa en la muestra completa (t = −2,37) que pierde significación al alinear el cierre a diciembre (t = −1,72), con quintiles no monótonos. La conclusión honesta es descriptiva: el CCC es un rasgo de empresa más que de sector, y su relación con la rentabilidad es débil y no causal.
