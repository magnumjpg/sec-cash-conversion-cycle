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

requires_raw_cache = pytest.mark.skipif(
    not FSDS.exists() or not any(FSDS.glob("*_sub.parquet")),
    reason="raw SEC cache absent; rebuild with src/download_sec.py",
)


@pytest.fixture(scope="session")
def panel() -> pd.DataFrame:
    assert PANEL.exists(), "run `python src/run_all.py` first"
    return pd.read_csv(PANEL, low_memory=False)


@pytest.fixture(scope="session")
def results() -> dict:
    assert RESULTS.exists(), "run `python src/run_all.py` first"
    return json.loads(RESULTS.read_text())


def test_files_exist():
    for rel in ["data/manifest.json", "outputs/results.json", "README.md",
                "DATA.md", "METHOD.md", "LIMITATIONS.md", "DECISIONS.md",
                "outputs/tables/attrition_missing_items.csv",
                "requirements.txt", "LICENSE"]:
        assert (ROOT / rel).exists(), f"missing {rel}"


def test_ccc_identity(panel):
    recomputed = panel["dso"] + panel["dio"] - panel["dpo"]
    assert np.allclose(panel["ccc"], recomputed, atol=1e-6)
    # and the underlying formulas
    assert np.allclose(panel["dso"], 365 * panel["ar"] / panel["revenue"], atol=1e-6)
    assert np.allclose(panel["dio"], 365 * panel["inventory"] / panel["cogs"], atol=1e-6)
    assert np.allclose(panel["dpo"], 365 * panel["ap"] / panel["cogs"], atol=1e-6)


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
                "ccc_roa", "shock_2020", "shock_2022", "shock_window", "rank_check",
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
    assert abs(results["panel"]["median_ccc"] - panel["ccc"].median()) < 0.05
    assert abs(results["panel"]["share_negative_ccc"] - panel["negative_ccc"].mean()) < 1e-6


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
def test_manifest_hashes(results):
    man = json.loads((ROOT / "data" / "manifest.json").read_text())
    entries = {e["path"]: e for e in man["files"]}
    assert len(entries) >= 64 * 3
    for p, e in entries.items():
        assert len(e["sha256"]) == 64
    # every cached derived file is described in the manifest
    for f in FSDS.glob("*.parquet"):
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
    # spec 9 now filters inventory as well and is the preferred-tag estimate
    spec9 = next(r for r in rows if r["spec"].startswith("9."))
    assert spec9["n"] == results["tag_sensitivity"]["preferred_only_ccc_roa"]["n"]
    assert spec9["p"] > 0.05
    assert spec9["n"] < 5000


def test_tag_sensitivity_matches_panel(panel, results):
    ts = results["tag_sensitivity"]
    pref = panel["tag_ap"] == "AccountsPayableCurrent"
    fb = panel["tag_ap"] == "AccountsPayableAndAccruedLiabilitiesCurrent"
    assert ts["preferred_ap"]["n"] == int(pref.sum())
    assert ts["fallback_ap"]["n"] == int(fb.sum())
    assert abs(ts["preferred_ap"]["ccc_median"] - panel.loc[pref, "ccc"].median()) < 1e-6
    assert abs(ts["fallback_ap"]["ccc_median"] - panel.loc[fb, "ccc"].median()) < 1e-6
    assert abs(ts["preferred_ap"]["dpo_median"] - panel.loc[pref, "dpo"].median()) < 1e-6
    assert abs(ts["fallback_ap"]["dpo_median"] - panel.loc[fb, "dpo"].median()) < 1e-6
    assert abs(ts["fallback_share_panel"] - fb.mean()) < 1e-6
    firm_med = panel.groupby("cik")["ccc"].median().median()
    assert abs(ts["median_of_firm_median_ccc"] - firm_med) < 1e-6
    # the fallback is a different concept and must lower the pooled level
    assert ts["fallback_ap"]["ccc_median"] < ts["preferred_ap"]["ccc_median"]
    assert ts["fallback_ap"]["dpo_median"] > ts["preferred_ap"]["dpo_median"]


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
    assert total == 77938
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
