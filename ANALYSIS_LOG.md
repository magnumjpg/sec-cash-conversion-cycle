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

Result: **105,865** firm-years with the five inputs present.

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

## 4. Validating the panel against the API we did not use

Three issuers — Fastenal, Walmart, Apple — three fiscal years, seven concepts
each: revenue, COGS, receivables, inventory, payables, assets, net income.

**49/49 exact matches** against `companyfacts`, maximum relative difference 0.0.

This does not prove the whole panel is right. It proves the tag mapping and the
fiscal-year join are right for three very different filers, which is the failure
mode that would otherwise go unnoticed.

---

## 5. The persistence bug

First AR(1) run on raw CCC: ρ ≈ **0.00001**.

Cause: the specification bounded the *current* CCC value to |x| ≤ 3,650 but not
the lag. One extreme lagged value dominated the regression and flattened the
slope.

**Fix:** bound both sides. Raw ρ became **0.536**; the winsorized headline
**0.685**. The bug is recorded because the first number looked like a real result
("CCC is not persistent at all") and was not.

---

## 6. The sign that would not cooperate

The charter's prior: higher CCC → lower profitability. The estimate came out
**positive**: +0.000139 (t = 3.81).

Before writing anything, three checks:

1. No controls, firm and year FE only: +0.000184 (t = 4.72). Larger, not smaller.
2. Raw variables, no winsorization: +0.000140.
3. Eleven specifications: positive in all, significant in eight.

So the sign is not an artefact of the controls or of winsorization. The project
reports it as contrary to the prior and offers two non-causal readings (product
mix; working capital as a support for sales), explicitly rejecting the causal
one.

**Independent check by the lead:** a from-scratch re-estimation on `panel.csv`
gives +0.000140 (t = 3.92). A within-firm rank correlation has median 0.00 and is
positive for only 48.2% of firms, so the coefficient is identified off firms with
large CCC variation and is not a pattern in the median firm. This is now in
`LIMITATIONS.md`; it makes the result weaker, not stronger, and is included for
that reason.

---

## 7. The shocks

Two cross-sections, one observation per firm:

- **2020 demand shock** (pre-shock 2019 CCC): revenue growth coefficient
  +0.000071, t = 0.38. Null. ROA is significant but non-monotone across
  quintiles. Cash ratio is null.
- **2022 cost shock**: gross-margin change coefficient −0.00006, t = −2.37. The
  quintile medians are **not monotone** (−0.81, −0.35, −0.75, −0.41, −0.93 pp),
  which means the linear slope is tail-driven.

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

- a large, stable descriptive fact (median CCC 75 days, half of it inventory);
- that industry explains little of it (6% of variance) and firm identity a lot
  (64%);
- a positive, small CCC–ROA association, against the prior, which survives
  specification checks but is invisible in the median firm;
- no detectable 2020 revenue effect, and a 2022 margin effect that is
  non-monotone.

That is a descriptive project with one uncomfortable result, not a causal story.
