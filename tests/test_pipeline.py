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
                "ccc_roa", "shock_2020", "shock_2022", "robustness_ccc_roa",
                "robustness_persistence", "attrition", "tag_usage"]:
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
