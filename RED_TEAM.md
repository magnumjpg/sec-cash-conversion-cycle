# RED_TEAM — attacking the working-capital project

Written from the position of a referee who does not want to accept the result.
Each objection is followed by what the project does about it and what remains
unresolved.

---

## "A positive CCC–ROA coefficient is economically implausible. You have a coding error."

It was checked before anything was written. The coefficient is positive in the
baseline (+0.000139), in the no-controls specification (+0.000184), with raw
unwinsorized variables (+0.000140), and in 8 of 11 specifications. The sign does
not come from the controls: removing gross margin makes it larger.

It is also not evidence that lengthening the CCC raises ROA. The most plausible
reading is product mix: firms in instruments, machinery and made-to-order
manufacturing carry inventory and receivables because that is their business
model, and they earn higher margins.

**Unresolved:** the design cannot separate that from a financing-capacity story.
A within-firm event study around deliberate CCC changes would be needed.

---

## "Then your result is just industry fixed effects."

No. The headline specification has firm fixed effects, so industry is absorbed
by construction. The variance decomposition is the relevant number and it points
the other way: only **6.0%** of CCC variance is between two-digit industries,
while **64.2%** is between firms and **35.8%** is within firms over time.

That is the substantive finding that survives the objection: "industry practice"
explains very little of working-capital levels.

---

## "Your mean CCC is −250 days with an SD of 103,000. That is not data, that is garbage."

Correct, and the README says so. The mean is uninterpretable because a small
share of XBRL facts are tagged at the wrong scale (assets in millions, COGS off
by 1,000×) and because micro-caps produce ratios with tiny denominators.

The response is threefold:

1. Headline levels are **medians**, not means.
2. Estimation drops |CCC| > 3,650 days, assets < $1m or revenue < $1m:
   **1,495 rows (5.90%)**.
3. The screen is not neutral and the size of the distortion is disclosed: the
   dropped group has a median CCC of **−197 days**, versus +77.9 in the kept
   sample.

**Unresolved:** the dropped rows are not random. Firms that tag at the wrong
scale may differ systematically. They are excluded rather than repaired, because
repairing them would require reading 1,495 filings.

---

## "Persistence of 0.685 is a mechanical artefact of not having firm fixed effects."

Partly fair. The headline is an AR(1) with year FE and no firm FE, which is
consistent but omits time-invariant firm traits. Adding firm FE gives ρ = 0.266,
but that estimate is Nickell-biased downward with T ≈ 10.

The honest statement is a **bound**, not a point: the truth is somewhere between
0.27 and 0.69, and the half-life between roughly one and three years. The README
reports the firm-FE version in the same table, labelled as biased, rather than
hiding it.

**Also:** the estimate is definition-sensitive. Raw CCC gives 0.536; dropping
|CCC| > 365 gives 0.509. The project quotes 0.685 together with the definition.

---

## "Your shock tests have no power. A t-statistic of 0.38 is not evidence of no effect."

Agreed, and the README does not claim it is. With N ≈ 1,347 and a noisy outcome,
the confidence interval on the 2020 revenue-growth coefficient is wide enough to
contain economically meaningful effects in either direction. The correct reading
is **"not detectable in this cross-section"**, not "CCC did not matter in 2020".

The 2022 margin result is the opposite problem: it is significant in the linear
specification and non-monotone in quintiles. That pattern is consistent with
tails, not with a dose–response, and is described that way.

**Unresolved:** no placebo outcome, no pre-trend, no matched control group. Each
of those would improve the design; none is present.

---

## "The 3-year rule selects survivors and biases everything."

It does select firms with at least three usable consecutive years. That makes the
panel a description of established SEC filers with trade working capital, not of
all listed firms. Firms that IPO'd and died within two years are absent, which
probably truncates the left tail of distress.

The project states the population explicitly and does not generalise beyond it.
The 15.84% negative-CCC share is presented as a **lower bound** for the listed
universe, because service firms without inventory are excluded by the data
requirements.

---

## "Why should I trust a panel you built yourself?"

Three checks:

1. **Cross-source validation.** Seven concepts across three fiscal years for
   Fastenal, Walmart and Apple, compared to the `companyfacts` API:
   **49/49 exact matches**, maximum relative difference 0.0.
2. **A published attrition funnel.** 2,536,529 us-gaap facts → 105,865 matched
   firm-years → 25,341 in the main sample, with every exclusion counted.
3. **A manifest with SHA-256 hashes** for 64 quarterly source files, so a silent
   upstream revision is detectable.

**Unresolved:** three firms is a spot check, not a reconciliation. A random
sample of 100 firms would be better and is not done.

---

## "Your screen drops firms with negative CCC — that is the interesting group."

It does not select on the sign of CCC. The screen is on magnitude (|CCC| > 3,650
days), size (assets and revenue ≥ $1m) and data validity. Negative-CCC firms
remain: 15.84% of the unscreened sample and 12.61% of the screened one.

That said, the screen does remove extreme negative values, and the kept negative
tail is thinner than the raw one. Robustness spec 5 restricts to negative-CCC
firm-years and the coefficient stays positive (+0.000106, p = 0.046), which is
the relevant check.

---

## "No inventory write-downs means you did not test resilience."

This is the strongest unaddressed gap. Write-downs were one of the charter's
three resilience outcomes, and they are absent because the cached tag slice never
included the write-down tags and the source zips were deleted to save space.

The project does not substitute gross margin for write-downs and call it the
same thing. It says the outcome is missing, explains why, and lists the exact
fix (re-download the 64 quarterly extracts with the write-down tags). See
`DECISIONS.md → D-12`.

---

## "This is descriptive accounting, not research."

It is descriptive, deliberately. The charter asked for a real panel, honest
measurement and no fake causal claims; it did not ask for an identification
strategy the data cannot support.

The contribution is the dataset and the three measurements that are not obvious
before looking: a 75-day median CCC, a CCC that is mostly a firm rather than an
industry trait, and a positive rather than negative ROA association. Those are
worth reporting precisely because the prior pointed the other way.
