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
                "DATA.md", "METHOD.md", "LIMITATIONS.md", "DECISIONS.md"]:
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
                "tag_usage"]:
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


def test_raw_cache_integrity():
    """Every cached quarter loads, and each accession appears in exactly one quarter."""
    fsds = ROOT / "data" / "raw" / "fsds"
    subs = sorted(fsds.glob("*_sub.parquet"))
    assert len(subs) == 64, f"expected 64 cached quarters, found {len(subs)}"
    adsh = []
    for f in subs:
        assert f.with_name(f.name.replace("_sub", "_num")).exists()
        df = pd.read_parquet(f, columns=["adsh"])
        assert len(df) > 0
        adsh.append(set(df["adsh"]))
    total = sum(len(a) for a in adsh)
    assert total == len(set().union(*adsh)), "an accession appears in two quarterly files"


def test_manifest_hashes(results):
    man = json.loads((ROOT / "data" / "manifest.json").read_text())
    entries = {e["path"]: e for e in man["files"]}
    assert len(entries) >= 64 * 3
    for p, e in entries.items():
        assert len(e["sha256"]) == 64
    # every cached derived file is described in the manifest
    for f in (ROOT / "data" / "raw" / "fsds").glob("*.parquet"):
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
