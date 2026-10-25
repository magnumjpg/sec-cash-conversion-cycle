# ANALYSIS_LOG — how the working-capital panel was built

A record of what was tried, what broke, and what changed. Not a polished
narrative: the point is that the false starts are visible.

---

## 1. Choosing a source, and rejecting the obvious one

The charter preferred `companyfacts` and suggested the Frames API as a fallback.
`companyfacts` for 3,000+ issuers is thousands of requests; the charter itself
rules that out.

The Frames API was tested and works, but its payload has only
`cik, entityName, loc, end, val, accn`. It does **not** expose `form`, `filed` or
`sic`. That makes three charter rules unenforceable:

- keep only annual reports (Frames mixes 10-K and 10-Q facts);
- "latest filing wins" (no filing date to sort on);
- exclude financials and utilities by SIC (no SIC).

**Decision:** use the SEC Financial Statement Data Sets — the same XBRL facts,
delivered as quarterly bulk files with `sub.txt` and `num.txt`. 2010q1–2025q4,
64 quarters, cached and hashed. See `DECISIONS.md → D-01`.

**What this cost:** the bulk format is less convenient than an API and the tag
mapping had to be written by hand.

---

## 2. Matching flows to stocks

`num.txt` has no `start` date, so annual flows cannot be matched to balances by
interval arithmetic. The join used:

- annual duration facts identified by the SEC's own `qtrs == 4` flag;
- all facts matched on `(cik, fiscal-year end)`;
- consecutive years required to be 350–380 days apart, so a year-end change does
  not create a fake 15-month "year".

Result: **116,988** firm-years with a flow and a balance on the same period end;
after dropping 1,567 duplicate fiscal-year labels and 9,556 rows outside the
2010–2024 window, **105,865** enter the measurement filters.

---

## 3. The screen, and the number that forced it

First descriptive run: mean CCC **−249.7 days**, standard deviation **103,401**.

That is not a heavy tail, it is a data problem. Inspection found two causes:

1. XBRL scale errors — total assets tagged in millions, COGS off by 1,000×;
2. micro-caps with revenues under $1m, where one day of receivables moves the
   ratio by thousands of days.

**Decision:** keep the full sample for headline medians (the charter asks for
medians), but screen for estimation: |CCC| ≤ 3,650 days, assets ≥ $1m, revenue
≥ $1m. That removes **1,495 rows (5.90%)**.

**The uncomfortable part:** the screen is not neutral. Dropped rows have a
median CCC of **−197 days**; kept rows have **+77.9**. Both are reported. A
reader who wants the unscreened median gets 75.0 days; a reader who wants the
estimation sample gets 77.9.

---

## 4. Internal spot check against the API we did not use

Three issuers — Fastenal, Walmart, Apple — three fiscal years, seven concepts
each: revenue, COGS, receivables, inventory, payables, assets, net income.

**63/63 exact matches** against `companyfacts`, maximum relative difference 0.0.

The first version of this check reported 49/49, and that number was wrong in a
way worth recording. The code filtered to comparisons where both values were
non-null *before* computing the denominator, so it deleted ten Apple rows whose
only defect was that the panel stores a month-end period end (2019-09-30) while
the 10-K closes two days earlier (2019-09-28). Four more rows were skipped
outright. The fix matches within ±7 days and keeps every attempted comparison in
the denominator: 3 firms × 7 concepts × 3 years = 63.

This is an **internal spot check**, not a validation of the tag mapping. It
shows that the extractor parses and period-aligns the tags it selected for three
very different filers. It does **not** test whether the ordered fallback chose
the right tag, whether a different tag would have been preferable, or whether
the extract covers firms outside those three issuers.

---

## 5. The persistence bug

First AR(1) run on raw CCC: ρ ≈ **0.00001**.

Cause: the specification bounded the *current* CCC value to |x| ≤ 3,650 but not
the lag. One extreme lagged value dominated the regression and flattened the
slope.

**Fix:** bound both sides. Raw ρ became **0.536**; the winsorized pooled
headline **0.685**. The bug is recorded because the first number looked like a
real result ("CCC is not persistent at all") and was not.

That was not the end of the persistence problem. The pooled 0.685 has no firm
fixed effect, so it also contains persistent between-firm differences; the
firm-FE estimate is **0.266** (half-life 0.52 years), Nickell-biased downward.
An Anderson–Hsiao IV gives **0.409** (SE 0.128). The project now reports the
range **0.27–0.69**, not a point, and no longer says that 31% of a firm's gap
closes each year.

---

## 6. The sign that would not cooperate

The charter's prior: higher CCC → lower profitability. The estimate came out
**positive**: +0.000139 (t = 3.81).

Before writing anything, three checks:

1. No controls, firm and year FE only: +0.000184 (t = 4.72). Larger, not smaller.
2. Raw variables, no winsorization: +0.000140.
3. Eleven main-sample specifications: positive in all, significant in seven.

So the sign is not an artefact of the controls or of winsorization. The project
reports it as contrary to the prior and offers two non-causal readings (product
mix; working capital as a support for sales), explicitly rejecting the causal
one.

**Independent check by the lead:** a from-scratch re-estimation on `panel.csv`
gives +0.000140 (t = 3.92). A within-firm rank correlation has median 0.00 and is
positive for only 48.1% of firms: the median firm shows **no monotone** CCC–ROA
association, not a negative one. The coefficient is identified off firms with
large CCC variation and is not a pattern in the median firm. This is computed by
the pipeline (`results.json.rank_check`, 2,852 firms), not by hand; it makes the
result weaker, not stronger, and is included for that reason.

---

## 7. The shocks

Two cross-sections, one observation per firm:

- **FY2020 demand shock** (pre-shock FY2019 CCC): revenue-growth coefficient
  +0.000071, t = 0.38 — not detectable, not "no effect". ROA is significant but
  non-monotone across quintiles. Cash ratio is not detectable either.
- **FY2022 cost shock**: gross-margin change coefficient −0.00006, t = −2.37. The
  quintile medians are **not monotone** (−0.81, −0.35, −0.75, −0.41, −0.93 pp),
  which means the linear slope is tail-driven.

The labels are issuer fiscal years, not calendar windows: 28.6% of FY2020 rows
and 28.4% of FY2022 rows have a non-December year-end. Re-estimating on December
year-ends only leaves the FY2020 revenue result undetectable (t = 0.72) and the
FY2020 ROA coefficient positive (t = 2.87), but moves the FY2022 margin slope to
−0.0059 with t = −1.72, so it no longer clears 5%. That check is stored in
`results.json.shock_window`.

Both are labelled descriptive. No placebo, no pre-trend, no matched controls.

---

## 8. What is missing, and why it stays missing

Inventory write-downs were a charter outcome. The cached tag slice never
contained the write-down tags, and the source zips were deleted after the panel
was built.

Options were: re-download 64 quarters and rebuild, or document the gap. With the
rest of the project complete, the gap was documented (`DECISIONS.md → D-12`)
rather than rushed. This is the main unfinished item in the project and is
listed as such in the README.

---

## 9. Figures

Six figures, two review rounds:

- Fig 1 (CCC by industry) had two industries both labelled "Wood & furniture"
  (SIC 24 and 25). Fixed to "Lumber & wood" and "Furniture", which required
  rebuilding the panel because the label is stored on it.
- Fig 4's legend overlapped the lower-right points; moved.
- Fig 6 keeps the non-monotone quintiles rather than a smoothed line, because the
  non-monotonicity is the finding.

Every annotation is read from `results.json` at draw time, so a figure cannot
silently disagree with the table.

---

## 10. The external audit, and what it changed

A read-only audit of the finished project found eight issues. Six were real
defects, not stylistic quibbles, and all were fixed before the final run:

1. **Spot-check denominator.** 49/49 was a success-only denominator; it is now
   63/63 with every attempted comparison kept (see §4).
2. **Funnel bridge.** The table started at 105,865 and silently dropped 11,123
   rows (1,567 duplicate labels + 9,556 outside the window). The funnel now starts
   at 116,988 and shows each subtraction.
3. **Persistence rows contradicted the JSON.** `table_persistence.csv` estimated
   the component rows on *raw* DSO/DIO/DPO while the headline used winsorized
   values. The rows are now winsorized (0.723 / 0.651 / 0.618) and match the
   headline.
4. **Variance shares added to 106%.** They are two overlapping partitions, not
   one. The README and RED_TEAM now present each partition separately and say why
   they do not sum to 100.
5. **Negative CCC is tag-sensitive.** 48.1% of the 2,799 rows using
   `AccountsPayableAndAccruedLiabilitiesCurrent` are negative, against 11.8% of
   the 22,542 preferred-tag rows; without the fallback the share is 11.83%, not
   15.84%. Both numbers are now reported.
6. **FY labels are not calendar windows.** The shock sections now say FY2020 /
   FY2022 and report the December-only sensitivity.

Two were nits, also fixed: the rank-check numbers are now produced by the
pipeline, and the CCC level table states that its components are separate medians
and do not add to 74.97 (49.10 + 84.27 − 50.99 = 82.38).

The audit also flagged `tag_usage.csv` shares that differ from `DATA.md`. They
are not wrong: the CSV uses the pre-filter tagged universe and `DATA.md` uses the
final panel. `DATA.md` now states both denominators.

---

## 11. Second audit: measurement, not formatting

A later review found issues that changed numbers rather than presentation:

1. **Robustness spec 9 was incomplete.** It filtered on preferred revenue, COGS,
   AR and AP but not `InventoryNet`. Adding the inventory condition leaves 4,542
   usable observations, β = +0.000123 (t = 1.83, p = 0.068), and reduces the
   significant main-sample specifications from 8/11 to 7/11. The count is now
   computed from the p-values (`robustness_summary`), not typed.
2. **The headline CCC level mixes two AP concepts.** Preferred-AP rows have a
   median CCC of 80.54 days and fallback rows 3.76; the fallback adds accruals
   and raises DPO, so the pooled 74.97 understates the preferred level. The
   pooled sample remains the headline because the charter mandates ordered
   fallbacks, but the mix and its direction are now in
   `results.json → tag_sensitivity`.
3. **Persistence was overstated.** 0.685 is a pooled AR(1); with firm FE it is
   0.266 (half-life 0.52 years), and Anderson–Hsiao IV gives 0.409. The project
   now reports the range 0.27–0.69 and describes the pooled `1 - rho` as an
   implication of that model, not a within-firm speed.
4. **The rank-check note said the opposite of its own numbers.** Median Spearman
   0.00 and 48.1% positive mean no monotone relation in the median firm, not a
   negative majority.
5. **The 77,938-row missing-input drop was one opaque bucket.** It is now
   decomposed by item; inventory (63,363) and COGS (55,272) dominate, and 73.9%
   of the dropped rows miss more than one input.
6. **"63/63" was called validation when it is a spot check.** It is now labelled
   an internal spot check everywhere, with an explicit statement that it does not
   validate tag choice, fallback order or coverage.

The audit's half-life of 0.63 years for the firm-FE estimate was an arithmetic
slip: `ln(0.5)/ln(0.266)` is 0.52, and that is the value reported.

---

## What I would do differently

1. **Check the lag bound before interpreting an AR(1).** A ρ of 0.00001 is a
   specification bug until proven otherwise.
2. **Decide the screen before looking at the mean.** The mean CCC was garbage and
   should have been anticipated from the XBRL scale problem.
3. **Keep the source zips.** Deleting them to save disk is why write-downs are
   missing.
4. **Run the rank check earlier.** The linear coefficient looked more robust
   before the within-firm median correlation was computed.

---

## Honest summary

The project set out to measure whether working capital predicts profitability
and resilience. It found:

- a large, stable descriptive fact (pooled median CCC 75 days; DIO alone is 84
  days and DPO offsets half of the operating cycle);
- that industry explains little of it (6% of variance) and firm identity a lot
  (64%);
- a persistence range of 0.27–0.69, not a single half-life;
- a positive, small CCC–ROA association, against the prior, which survives
  specification checks but is significant in only 7 of 11 main-sample
  specifications and is invisible in the median firm;
- no detectable 2020 revenue effect, and a 2022 margin effect that is
  non-monotone.

That is a descriptive project with one uncomfortable result, not a causal story.
