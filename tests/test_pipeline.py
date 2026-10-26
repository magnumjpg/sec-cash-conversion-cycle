"""Invariants for the working-capital pipeline.  Run: python -m pytest -q tests"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
PANEL = ROOT / "data" / "processed" / "panel.csv"
RESULTS = ROOT / "outputs" / "results.json"
FSDS = ROOT / "data" / "raw" / "fsds"
FSDS_Q = ROOT / "data" / "raw" / "fsds_q"
QPANEL = ROOT / "data" / "processed" / "quarterly_panel.parquet"
QPANEL_CSV = ROOT / "data" / "processed" / "quarterly_panel.csv"
QRESULTS = ROOT / "outputs" / "quarterly_results.json"
QSTATS = ROOT / "outputs" / "quarterly_stats.json"

requires_raw_cache = pytest.mark.skipif(
    not FSDS.exists() or not any(FSDS.glob("*_sub.parquet")),
    reason="raw SEC cache absent; rebuild with src/download_sec.py",
)
requires_quarterly = pytest.mark.skipif(
    not (QPANEL.exists() or QPANEL_CSV.exists()),
    reason="quarterly panel absent; run src/build_quarterly.py",
)


@pytest.fixture(scope="session")
def panel() -> pd.DataFrame:
    assert PANEL.exists(), "run `python src/run_all.py` first"
    return pd.read_csv(PANEL, low_memory=False)


@pytest.fixture(scope="session")
def results() -> dict:
    assert RESULTS.exists(), "run `python src/run_all.py` first"
    return json.loads(RESULTS.read_text())


@pytest.fixture(scope="session")
def qpanel() -> pd.DataFrame:
    if QPANEL.exists():
        return pd.read_parquet(QPANEL)
    assert QPANEL_CSV.exists(), "run `python src/build_quarterly.py` first"
    return pd.read_csv(QPANEL_CSV, low_memory=False)


@pytest.fixture(scope="session")
def qresults() -> dict:
    assert QRESULTS.exists(), "run `python src/analysis_quarterly.py` first"
    return json.loads(QRESULTS.read_text())


def test_files_exist():
    for rel in ["data/manifest.json", "outputs/results.json", "README.md",
                "DATA.md", "METHOD.md", "LIMITATIONS.md", "DECISIONS.md",
                "outputs/tables/attrition_missing_items.csv",
                "outputs/quarterly_results.json", "outputs/quarterly_stats.json",
                "outputs/figures/fig7_quarterly_shock.png",
                "requirements.txt", "LICENSE"]:
        assert (ROOT / rel).exists(), f"missing {rel}"


def test_ccc_identity(panel):
    recomputed = panel["dso"] + panel["dio"] - panel["dpo"]
    assert np.allclose(panel["ccc"], recomputed, atol=1e-6)
    # and the underlying formulas
    assert np.allclose(panel["dso"], 365 * panel["ar"] / panel["revenue"], atol=1e-6)
    assert np.allclose(panel["dio"], 365 * panel["inventory"] / panel["cogs"], atol=1e-6)
    assert np.allclose(panel["dpo"], 365 * panel["ap"] / panel["cogs"], atol=1e-6)


def test_clean_ccc_identity(panel):
    """The headline measure uses trade AP, not AP+accruals."""
    clean = panel["ccc_clean"].notna()
    contaminated = panel["ap_quality"] == "fallback_contaminated"
    assert int(clean.sum()) == int((~contaminated).sum())
    assert np.allclose(panel.loc[clean, "dpo_clean"],
                       365 * panel.loc[clean, "ap_clean"] / panel.loc[clean, "cogs"],
                       atol=1e-6)
    assert np.allclose(panel.loc[clean, "ccc_clean"],
                       panel.loc[clean, "dso"] + panel.loc[clean, "dio"]
                       - panel.loc[clean, "dpo_clean"], atol=1e-6)
    assert np.allclose(panel.loc[clean, "negative_ccc_clean"],
                       (panel.loc[clean, "ccc_clean"] < 0).astype(float), atol=1e-12)


def test_ap_quality_partition(panel):
    """Direct trade AP, reconstructed residual, or explicitly contaminated."""
    direct = panel["ap_quality"] == "direct"
    recon = panel["ap_quality"] == "reconstructed"
    cont = panel["ap_quality"] == "fallback_contaminated"
    assert set(panel["ap_quality"].unique()) <= {"direct", "reconstructed",
                                                 "fallback_contaminated"}
    assert (direct | recon | cont).all()
    assert panel.loc[direct, "tag_ap"].isin(
        ["AccountsPayableCurrent", "AccountsPayableTradeCurrent"]).all()
    assert np.allclose(panel.loc[direct, "ap_clean"], panel.loc[direct, "ap"],
                       atol=1e-6)
    assert panel.loc[cont, "tag_ap"].eq(
        "AccountsPayableAndAccruedLiabilitiesCurrent").all()
    assert np.allclose(panel.loc[recon, "ap_clean"],
                       panel.loc[recon, "ap"]
                       - panel.loc[recon, "accrued_liabilities"], atol=1e-6)
    assert (panel.loc[recon, "ap_clean"] > 0).all()
    assert panel.loc[cont, "ap_clean"].isna().all()


def test_trade_ap_helper():
    """The scalar rule and the vectorised panel logic must agree."""
    from tags import trade_ap
    assert trade_ap(100.0, "AccountsPayableCurrent", None) == (100.0, "direct")
    assert trade_ap(100.0, "AccountsPayableTradeCurrent", 40.0) == (100.0, "direct")
    assert trade_ap(100.0, "AccountsPayableAndAccruedLiabilitiesCurrent", 40.0) \
        == (60.0, "reconstructed")
    # an accrual split at or above the combined line is not a trade payable
    assert trade_ap(100.0, "AccountsPayableAndAccruedLiabilitiesCurrent", 120.0) \
        == (None, "fallback_contaminated")
    assert trade_ap(100.0, "AccountsPayableAndAccruedLiabilitiesCurrent", None) \
        == (None, "fallback_contaminated")
    assert trade_ap(None, "AccountsPayableCurrent", 40.0) == (None, "missing")


def test_no_negative_revenue_or_cogs(panel):
    assert (panel["revenue"] > 0).all()
    assert (panel["cogs"] > 0).all()


def test_firm_year_unique(panel):
    dup = panel.duplicated(["cik", "fiscal_year"])
    assert not dup.any(), f"{dup.sum()} duplicated firm-years"


def test_fiscal_years_in_range(panel):
    assert panel["fiscal_year"].between(2010, 2024).all()


def test_min_years_per_firm(panel):
    counts = panel.groupby("cik")["fiscal_year"].nunique()
    assert (counts >= 3).all()


def test_no_financials_or_utilities(panel):
    assert not panel["sic"].between(6000, 6999).any()
    assert not panel["sic"].between(4900, 4999).any()


def test_required_fields(panel):
    for col in ["revenue", "cogs", "ar", "inventory", "ap", "ccc", "roa"]:
        assert col in panel.columns
    assert panel[["revenue", "cogs", "ar", "inventory", "ap", "ccc"]].notna().all().all()


def test_panel_size_stable(results):
    # guards against a silent filter change: the panel is rebuilt from a frozen cache
    assert results["panel"]["rows"] == len(pd.read_csv(PANEL, usecols=["cik"]))
    assert results["panel"]["rows"] > 5000
    assert results["panel"]["firms"] > 500


def test_results_keys(results):
    for key in ["meta", "panel", "descriptives", "industries", "by_year", "persistence",
                "ccc_roa", "ccc_roa_baseline", "ccc_roa_between",
                "ccc_roa_industry_year", "ccc_roa_components",
                "shock_2020", "shock_2022", "shock_window", "shock_quarterly",
                "write_down_coverage", "ap_quality", "rank_check",
                "funnel", "robustness_ccc_roa", "robustness_persistence", "attrition",
                "attrition_missing_items", "tag_usage", "tag_sensitivity",
                "robustness_summary"]:
        assert key in results, f"missing results.json key: {key}"


def test_persistence_bounds(results):
    rho = results["persistence"]["beta"]
    assert 0 < rho < 1, f"AR(1) rho outside (0,1): {rho}"
    hl = results["persistence"]["half_life_years"]
    assert 0 < hl < 50


def test_headline_numbers_match_panel(panel, results):
    clean = panel["ccc_clean"].notna()
    assert abs(results["panel"]["median_ccc"] - panel["ccc_clean"].median()) < 0.05
    assert abs(results["panel"]["share_negative_ccc"]
               - panel["negative_ccc_clean"].mean()) < 1e-6
    assert results["panel"]["rows_clean_ap"] == int(clean.sum())
    # the mixed-AP sensitivity is reported separately and must stay larger
    assert abs(results["panel"]["median_ccc_all_rows"] - panel["ccc"].median()) < 0.05
    assert results["panel"]["median_ccc_all_rows"] < results["panel"]["median_ccc"]


def test_ap_quality_stats_match_panel(panel, results):
    aq = results["ap_quality"]
    counts = panel["ap_quality"].value_counts().to_dict()
    assert aq["counts"] == {k: int(v) for k, v in counts.items()}
    assert aq["clean_rows"] == int(counts.get("direct", 0) + counts.get("reconstructed", 0))
    # reconstruction is rare precisely because the combined tag is used when the
    # accrual split is absent; the panel must not pretend otherwise
    assert 0 < aq["counts"].get("reconstructed", 0) < 0.05 * len(panel)
    assert aq["counts"]["fallback_contaminated"] > 1000


def test_lags_respect_fiscal_spacing(panel):
    ok = panel["ccc_lag"].notna()
    assert panel.loc[ok, "days_since_prev"].between(350, 380).all()


def test_tag_usage_covers_concepts(results):
    concepts = {row["concept"] for row in results["tag_usage"]}
    for c in ["revenue", "cogs", "ar", "inventory", "ap"]:
        assert c in concepts


@requires_raw_cache
def test_raw_cache_integrity():
    """Every cached quarter loads, and each accession appears in exactly one quarter."""
    subs = sorted(FSDS.glob("*_sub.parquet"))
    assert len(subs) == 64, f"expected 64 cached quarters, found {len(subs)}"
    adsh = []
    for f in subs:
        assert f.with_name(f.name.replace("_sub", "_num")).exists()
        df = pd.read_parquet(f, columns=["adsh"])
        assert len(df) > 0
        adsh.append(set(df["adsh"]))
    total = sum(len(a) for a in adsh)
    assert total == len(set().union(*adsh)), "an accession appears in two quarterly files"


@requires_raw_cache
def test_quarterly_cache_integrity():
    subs = sorted(FSDS_Q.glob("*_sub.parquet"))
    assert len(subs) == 16, f"expected 16 quarterly shock files, found {len(subs)}"
    adsh = []
    for f in subs:
        assert f.with_name(f.name.replace("_sub", "_num")).exists()
        df = pd.read_parquet(f, columns=["adsh", "form"])
        assert len(df) > 0
        forms = set(df["form"].astype(str))
        # the cache is a filing-quarter, not a form-quarter; build_quarterly.py
        # filters to 10-Q/10-Q/A.  What matters here is that the cache is sane
        # and every file actually contains 10-Qs.
        assert forms <= {"10-Q", "10-Q/A", "10-K", "10-K/A", "20-F", "20-F/A",
                         "40-F", "40-F/A"}, f"unexpected forms in {f.name}: {forms}"
        assert any(form.startswith("10-Q") for form in forms)
        adsh.append(set(df["adsh"]))
    assert sum(len(a) for a in adsh) == len(set().union(*adsh))


@requires_quarterly
def test_quarterly_panel_integrity(qpanel):
    """One row per firm-quarter, calendar labels, and the clean-AP identities."""
    assert not qpanel.duplicated(["cik", "ddate"]).any()
    assert qpanel["calendar_year"].between(2018, 2022).all()
    period_end = pd.to_datetime(qpanel["ddate"].astype(str), format="%Y%m%d")
    expected = (period_end.dt.year.astype(str) + "Q"
                + period_end.dt.quarter.astype(str))
    assert (qpanel["quarter"] == expected).all()

    ok = qpanel["ccc_q"].notna()
    assert np.allclose(
        qpanel.loc[ok, "ccc_q"],
        qpanel.loc[ok, "dso_q"] + qpanel.loc[ok, "dio_q"] - qpanel.loc[ok, "dpo_q"],
        atol=1e-6,
    )
    clean = qpanel["ap_quality"] != "fallback_contaminated"
    ok = clean & qpanel["dpo_q"].notna() & (qpanel["cogs_q"] > 0)
    assert np.allclose(
        qpanel.loc[ok, "dpo_q"],
        365 * qpanel.loc[ok, "ap_clean"]
        / (qpanel.loc[ok, "cogs_q"] * 4),
        atol=1e-6,
    )
    assert qpanel.loc[~clean, "ap_clean"].isna().all()
    assert set(qpanel["ap_quality"].unique()) <= {"direct", "reconstructed",
                                                  "fallback_contaminated"}


@requires_quarterly
def test_quarterly_stats_match_panel(qpanel):
    stats = json.loads(QSTATS.read_text())
    assert stats["rows_out"] == len(qpanel)
    assert stats["firms_out"] == qpanel["cik"].nunique()
    assert stats["firm_quarters"] == stats["rows_out"]
    assert 0 <= stats["firm_quarters_outside_window"] < 1000
    counts = qpanel["ap_quality"].value_counts().to_dict()
    assert stats["ap_quality_counts"] == {k: int(v) for k, v in counts.items()}
    assert stats["quarters"] == sorted(qpanel["quarter"].dropna().unique().tolist())


def test_quarterly_results_use_pre_shock_exposure(qresults):
    """The 10-Q window is calendar, and the exposure is the prior fiscal year."""
    assert qresults["available"] is True
    assert qresults["quarters_used"] == [
        "2020Q1", "2020Q2", "2020Q3", "2022Q1", "2022Q2", "2022Q3"]
    assert qresults["n_firm_quarters"] > 5000
    assert qresults["n_firms"] > 1000
    # With the exposure measured before the shock and the window aligned to
    # calendar Q1-Q3, no pooled coefficient clears 5%.  The closest is the
    # 2022 gross-margin change; the earlier cash-ratio result came from a
    # same-year exposure and does not survive.
    pooled = qresults["pooled"]
    for year in ["2020", "2022"]:
        for name, spec in pooled[year].items():
            assert spec["n"] > 100, f"{year}.{name} lost almost all rows"
            assert spec["p"] > 0.05, f"{year}.{name} is unexpectedly significant"
    gm22 = pooled["2022"]["gross_margin_change"]
    assert gm22["beta"] > 0
    assert 0.05 < gm22["p"] < 0.10
    # 6 calendar quarters x 4 outcomes
    assert len(qresults["by_quarter"]) == 24
    assert {row["quarter"] for row in qresults["by_quarter"]} == {
        "2020Q1", "2020Q2", "2020Q3", "2022Q1", "2022Q2", "2022Q3"}


@requires_raw_cache
def test_manifest_hashes(results):
    man = json.loads((ROOT / "data" / "manifest.json").read_text())
    entries = {e["path"]: e for e in man["files"]}
    assert len(entries) >= 64 * 3
    for p, e in entries.items():
        assert len(e["sha256"]) == 64
    # every cached derived file is described in the manifest
    for f in list(FSDS.glob("*.parquet")) + list(FSDS_Q.glob("*.parquet")):
        rel = str(f.relative_to(ROOT)).replace("\\", "/")
        assert rel in entries, f"{rel} missing from manifest"


def test_validation_denominator_is_complete():
    """3 firms x 7 concepts x 3 years; failures stay in the denominator."""
    val = json.loads((ROOT / "outputs" / "validation.json").read_text())
    expected = len(val["firms"]) * len(val["concepts"]) * len(val["years"])
    assert expected == 63
    assert val["n_comparisons"] == expected
    assert val["n_match"] + val["n_unavailable"] == val["n_comparisons"]
    assert val["all_match"] is True
    assert val["max_abs_rel_diff"] == 0.0
    rows = pd.read_csv(ROOT / "outputs" / "tables" / "known_firm_check.csv")
    assert len(rows) == expected
    assert rows["match"].all()


def test_funnel_bridge(results, panel):
    """Every exclusion is counted and the bridge closes to the main sample."""
    f = results["funnel"]
    assert (f["firm_years_matched_on_exact_end"]
            - f["firm_years_dropped_duplicate_fiscal_year"]
            - f["firm_years_outside_window"]
            == f["firm_years_in_window"])
    assert f["firm_years_in_window"] > f["firm_years_main_sample"]
    # no firm-year can vanish between the window and the final sample
    assert f["firm_years_main_sample"] == len(panel)
    assert f["firms_main_sample"] == panel["cik"].nunique()
    att = pd.read_csv(ROOT / "outputs" / "tables" / "attrition.csv")
    bridge = att[att["step"].str.startswith(("0. ", "0a.", "0b.", "0c."))]
    assert len(bridge) == 4, "funnel bridge rows missing from attrition.csv"


def test_rank_check_is_produced(results):
    rc = results["rank_check"]
    assert rc["n_firms"] > 1000
    assert -1 <= rc["median_spearman"] <= 1
    assert 0 <= rc["share_positive"] <= 1
    # 0.00 / 48.1%: the median firm does not reproduce the positive sign
    assert abs(rc["median_spearman"]) < 0.05
    assert 0.45 < rc["share_positive"] < 0.52


def test_variance_partitions_sum_to_one_each(results):
    v = results["descriptives"]["variance_decomposition"]
    assert abs(v["share_between_industries_sic2"]
               + v["share_within_industries_sic2"] - 1) < 1e-6
    assert abs(v["share_between_firms"] + v["share_within_firms"] - 1) < 1e-6
    # the two partitions are nested, so the three-way sum exceeds 1; that is
    # documented in README/METHOD rather than "fixed" by renormalising
    three_way = (v["share_between_industries_sic2"] + v["share_between_firms"]
                 + v["share_within_firms"])
    assert three_way > 1.0


def test_persistence_components_match_json(results):
    """The table rows must be the winsorized estimates in results.json."""
    tbl = pd.read_csv(ROOT / "outputs" / "tables" / "table_persistence.csv")
    tbl = tbl.set_index("metric")
    comp = results["persistence_dso_dio_dpo"]
    for i, name in enumerate(["dso", "dio", "dpo"], start=5):
        row = tbl.loc[f"{i}. {name.upper()} only"]
        assert abs(row["value"] - comp[name]["beta"]) < 1e-6
        assert int(row["n"]) == comp[name]["n"]


def test_shock_window_december_check(results):
    w = results["shock_window"]
    assert 0 < w["share_non_december_fy2020"] < 0.5
    assert 0 < w["share_non_december_fy2022"] < 0.5
    pairs = [("shock_2020_december", "shock_2020"),
             ("shock_2022_december", "shock_2022")]
    for dec_key, full_key in pairs:
        for name, spec in w[dec_key].items():
            assert spec["n"] > 100, f"{dec_key}.{name} lost almost all rows"
            assert spec["n"] < results[full_key][name]["n"]
    # the calendar-aligned FY2022 margin slope no longer clears 5%
    assert abs(w["shock_2022_december"]["margin_change"]["t"]) < 1.96


def test_tag_usage_denominator(panel):
    """tag_usage.csv shares are of the tagged universe, not the panel."""
    t = pd.read_csv(ROOT / "outputs" / "tables" / "tag_usage.csv")
    for concept, g in t.groupby("concept"):
        assert abs(g["share_of_concept"].sum() - 1) < 1e-6
    # panel-level counts do sum to the panel, and differ from the CSV counts
    ap = panel["tag_ap"].value_counts()
    assert ap.sum() == len(panel)
    assert ap["AccountsPayableCurrent"] != int(
        t[(t.concept == "ap") & (t.preferred)]["firm_years"].iloc[0])


def test_robustness_count_is_computed_from_pvalues(results):
    """The 7-of-11 claim must be the p-values in the table, not a typed count."""
    rows = results["robustness_ccc_roa"]
    main = [r for r in rows if r.get("sample") == "main" and r.get("p") is not None]
    summary = results["robustness_summary"]
    assert summary["n_specs_main_sample"] == len(main)
    assert summary["n_significant_p05"] == sum(1 for r in main if r["p"] < 0.05)
    assert summary["n_positive"] == sum(1 for r in main if r["beta"] > 0)
    # spec 11 keeps only firm-years on the charter's preferred tag for every
    # input; it is the strictest tag test and does not clear 5%
    spec11 = next(r for r in rows if r["spec"].startswith("11."))
    assert spec11["n"] == results["tag_sensitivity"]["preferred_only_ccc_roa"]["n"]
    assert spec11["p"] > 0.05
    assert spec11["n"] < 5000


def test_tag_sensitivity_matches_panel(panel, results):
    ts = results["tag_sensitivity"]
    pref = panel["tag_ap"].isin(["AccountsPayableCurrent",
                                 "AccountsPayableTradeCurrent"])
    fb = panel["tag_ap"] == "AccountsPayableAndAccruedLiabilitiesCurrent"
    recon = panel["ap_quality"] == "reconstructed"
    cont = panel["ap_quality"] == "fallback_contaminated"
    clean = panel["ccc_clean"].notna()
    assert ts["preferred_ap"]["n"] == int(pref.sum())
    assert ts["fallback_ap"]["n"] == int(fb.sum())
    assert ts["reconstructed_ap"]["n"] == int(recon.sum())
    assert ts["contaminated_ap"]["n"] == int(cont.sum())
    assert ts["clean_ap"]["n"] == int(clean.sum())
    blocks = [
        ("preferred_ap", pref, "ccc", "dpo", "negative_ccc"),
        ("fallback_ap", fb, "ccc", "dpo", "negative_ccc"),
        # reconstructed rows are only meaningful on the clean measurement
        ("reconstructed_ap", recon, "ccc_clean", "dpo_clean",
         "negative_ccc_clean"),
        ("contaminated_ap", cont, "ccc", "dpo", "negative_ccc"),
    ]
    for key, mask, ccc, dpo, neg in blocks:
        assert abs(ts[key]["ccc_median"] - panel.loc[mask, ccc].median()) < 1e-6
        assert abs(ts[key]["dpo_median"] - panel.loc[mask, dpo].median()) < 1e-6
        assert abs(ts[key]["negative_ccc_share"]
                   - panel.loc[mask, neg].mean()) < 1e-6
    assert abs(ts["clean_ap"]["ccc_median"]
               - panel.loc[clean, "ccc_clean"].median()) < 1e-6
    assert abs(ts["clean_ap"]["dpo_median"]
               - panel.loc[clean, "dpo_clean"].median()) < 1e-6
    assert abs(ts["fallback_share_panel"] - fb.mean()) < 1e-6
    assert abs(ts["reconstructed_share_of_fallback"] - recon.sum() / fb.sum()) < 1e-6
    firm_med = panel.groupby("cik")["ccc_clean"].median()
    assert abs(ts["median_of_firm_median_ccc"] - firm_med.median()) < 1e-6
    assert ts["n_firms"] == int(firm_med.notna().sum())
    # the fallback is a different concept and must lower the pooled level
    assert ts["fallback_ap"]["ccc_median"] < ts["preferred_ap"]["ccc_median"]
    assert ts["fallback_ap"]["dpo_median"] > ts["preferred_ap"]["dpo_median"]
    # nearly all fallback rows cannot be reconstructed: the combined tag is
    # used precisely when the accrual split is absent
    assert ts["reconstructed_share_of_fallback"] < 0.05
    assert ts["contaminated_ap"]["n"] > 1000


def test_persistence_reports_a_range(results):
    p = results["persistence"]
    fe = p["with_firm_fe"]
    iv = p["anderson_hsiao"]
    assert 0 < fe["rho"] < p["beta"] < 1
    assert fe["rho"] < iv["rho"] < p["beta"]
    assert 0 < fe["half_life_years"] < p["half_life_years"]
    assert abs(fe["half_life_years"] - np.log(0.5) / np.log(fe["rho"])) < 1e-6
    assert iv["n"] < p["n"]
    # the industry table is labelled pooled and carries a firm-FE column
    byind = p["by_industry"]
    assert byind and all("rho_firm_fe" in row for row in byind)
    assert all("pooled" in row["model"] for row in byind)


def test_attrition_missing_decomposition(results):
    rows = results["attrition_missing_items"]
    by_item = {r["item"]: r["n_firm_years"] for r in rows}
    total = by_item["any item missing (rows dropped)"]
    assert total == 76218
    for item in ["revenue", "cogs", "ar", "inventory", "ap"]:
        assert 0 < by_item[item] <= total
    assert (by_item["exactly one item missing"]
            + by_item["more than one item missing"]) == total
    assert by_item["more than one item missing"] > by_item["exactly one item missing"]
    assert by_item["missing item-cells (sum of the five rows above)"] == sum(
        by_item[i] for i in ["revenue", "cogs", "ar", "inventory", "ap"])
    csv = pd.read_csv(ROOT / "outputs" / "tables" / "attrition_missing_items.csv")
    assert len(csv) == len(rows)


def test_rank_check_note_matches_numbers(results):
    rc = results["rank_check"]
    assert "no monotone" in rc["note"]
    assert "most firms are negative" not in rc["note"]
    assert abs(rc["median_spearman"]) < 0.05
    assert 0.45 < rc["share_positive"] < 0.52


def test_user_agent_has_no_personal_address():
    """The SEC contact is an environment variable, not a hard-coded address."""
    for rel in ["src/download_sec.py", "src/verify_known_firms.py"]:
        text = (ROOT / rel).read_text(encoding="utf-8").lower()
        assert "gmail" not in text
        assert "magnum" not in text
        assert "sec_contact" in text


def _reject_nonfinite(token):
    raise ValueError(f"non-finite JSON constant: {token}")


def test_json_outputs_are_strict():
    """NaN/Infinity are invalid JSON; undefined values must serialise as null."""
    paths = [RESULTS, ROOT / "outputs" / "panel_stats.json",
             ROOT / "outputs" / "validation.json",
             ROOT / "outputs" / "run_log.json",
             ROOT / "outputs" / "quarterly_results.json",
             ROOT / "outputs" / "quarterly_stats.json",
             ROOT / "data" / "manifest.json"]
    parsed = {}
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "NaN" not in text, f"{path.name} contains NaN"
        assert "Infinity" not in text, f"{path.name} contains Infinity"
        parsed[path.name] = json.loads(text, parse_constant=_reject_nonfinite)

    # the nulls are deliberate: an undefined half-life cannot be a number
    p = parsed["results.json"]["persistence"]
    null_hl = [row for row in p["by_industry"]
               if row["half_life_firm_fe"] is None]
    assert null_hl, "expected an undefined industry firm-FE half-life"
    for row in null_hl:
        assert row["rho_firm_fe"] is None or not 0 < row["rho_firm_fe"] < 1
    raw_rows = parsed["results.json"]["persistence_raw_ccc"]["by_industry"]
    assert any(row["half_life_years"] is None for row in raw_rows)

    # attrition firm counts are undefined for aggregate-only steps
    att = parsed["panel_stats.json"]["attrition"]
    assert any(row["firms"] is None for row in att)
    assert all(row["firms"] is None or isinstance(row["firms"], (int, float))
               for row in att)
