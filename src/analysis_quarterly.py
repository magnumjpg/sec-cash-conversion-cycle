"""
Quarterly shock tests: 2020 COVID and 2022 inflation at 10-Q resolution.

Exposure is the clean annual CCC in the fiscal year *before* the shock
(FY2019 for 2020, FY2021 for 2022).  Outcomes are measured in the issuer's
10-Q windows with a period end inside the shock calendar year, Q1-Q3:

    YoY revenue growth, YoY gross-margin change, cash/assets, write-down/COGS

The pooled regression includes 2-digit SIC and calendar-quarter fixed effects,
with SEs clustered by firm.  Per-quarter cross-sections are also written so the
reader can see whether a weak annual result was hiding a sharp Q1/Q2 effect.

Run:
    python src/analysis_quarterly.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analysis import ols_cluster, r, stars, winsorize  # noqa: E402
from json_utils import write_json  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT = ROOT / "outputs"
TABLES = OUT / "tables"

OUTCOMES = {
    "sales_growth": "sales_growth_yoy",
    "gross_margin_change": "gross_margin_change_yoy",
    "cash_ratio": "cash_ratio_q",
    "write_down": "write_down_to_cogs_q",
}
SHOCKS = {2020: 2019, 2022: 2021}


def pre_shock_ccc(annual: pd.DataFrame) -> pd.DataFrame:
    a = annual.copy()
    a["ccc_pre"] = winsorize(a["ccc_clean"], [a["sic2"], a["fiscal_year"]])
    return a[["cik", "fiscal_year", "sic2", "ccc_pre"]].rename(
        columns={"fiscal_year": "pre_year"})


def fit_pooled(d: pd.DataFrame, ycol: str, xcol: str) -> dict:
    d = d.dropna(subset=[ycol, xcol, "sic2", "quarter"]).copy()
    if len(d) < 30:
        return {"beta": None, "se": None, "t": None, "p": None, "stars": "",
                "n": int(len(d)), "n_firms": int(d["cik"].nunique()),
                "model": "insufficient observations"}
    d["_y"] = winsorize(d[ycol], [d["quarter"]], min_group=10**9)
    dummies = pd.concat([
        pd.get_dummies(d["sic2"], prefix="ind", drop_first=True, dtype=float),
        pd.get_dummies(d["quarter"], prefix="q", drop_first=True, dtype=float),
    ], axis=1)
    X = pd.concat([d[[xcol]], dummies], axis=1)
    res = ols_cluster(d["_y"], X, groups=d["cik"])
    return {
        "beta": r(res.params[xcol]), "se": r(res.bse[xcol]),
        "t": r(res.tvalues[xcol]), "p": r(res.pvalues[xcol]),
        "stars": stars(res.pvalues[xcol]), "n": int(res.nobs),
        "n_firms": int(d["cik"].nunique()),
        "model": (f"{ycol} (winsorized 1/99 by quarter) on {xcol} + "
                  "2-digit SIC FE + quarter FE; SE clustered by firm"),
    }


def fit_quarter(d: pd.DataFrame, ycol: str, xcol: str) -> dict:
    d = d.dropna(subset=[ycol, xcol, "sic2"]).copy()
    if len(d) < 20:
        return {"beta": None, "se": None, "t": None, "p": None, "stars": "",
                "n": int(len(d)), "n_firms": int(d["cik"].nunique()),
                "model": "insufficient observations"}
    d["_y"] = winsorize(d[ycol], [d["sic2"]], min_group=10**9)
    dm = pd.get_dummies(d["sic2"], prefix="ind", drop_first=True, dtype=float)
    res = ols_cluster(d["_y"], pd.concat([d[[xcol]], dm], axis=1), cov="HC1")
    return {
        "beta": r(res.params[xcol]), "se": r(res.bse[xcol]),
        "t": r(res.tvalues[xcol]), "p": r(res.pvalues[xcol]),
        "stars": stars(res.pvalues[xcol]), "n": int(res.nobs),
        "n_firms": int(d["cik"].nunique()),
        "model": (f"{ycol} (winsorized 1/99) on {xcol} + 2-digit SIC FE; "
                  "one quarter, HC1 SE"),
    }


def main() -> dict:
    q_path = PROC / "quarterly_panel.parquet"
    if not q_path.exists():
        payload = {"available": False,
                   "reason": "quarterly panel absent; run src/build_quarterly.py"}
        write_json(OUT / "quarterly_results.json", payload)
        print("quarterly panel absent - wrote an explicit unavailable block")
        return payload
    q = pd.read_parquet(q_path)
    annual = pd.read_parquet(PROC / "panel.parquet")
    pre = pre_shock_ccc(annual)

    # Calendar window, not the issuer's fy label: the period end must fall in the
    # shock year, and only calendar Q1-Q3 are used.  A December-2020 period end is
    # reported in the 10-K for December filers, so including calendar Q4 would mix
    # a thin, non-December subsample into the last cell.
    d = q[q["calendar_year"].isin(SHOCKS)].copy()
    d = d[d["quarter"].str[-2:].isin(["Q1", "Q2", "Q3"])].copy()
    # Exposure is the annual balance sheet for shock_year - 1.  Do not join on
    # the 10-Q's own fy label: for a December filer that label is the shock
    # year (a 2020Q1 10-Q carries fy=2020), which would put the outcome and the
    # exposure in the same fiscal year.
    d["pre_year"] = d["calendar_year"].map(SHOCKS)
    d = d.merge(pre, on=["cik", "pre_year"], how="inner",
                suffixes=("", "_annual"))

    results: dict = {
        "available": True,
        "source": "SEC FSDS 10-Q, 2019q1-2022q4 (filings filed 2019-2022)",
        "pre_shock_measure": ("clean annual CCC: FY2019 for the 2020 shock, "
                              "FY2021 for the 2022 shock"),
        "window": ("period ends in calendar Q1-Q3 of the shock year, from 10-Q "
                   "filings; calendar Q4 is only in the 10-K for December filers"),
        "quarters_used": sorted(d["quarter"].dropna().unique().tolist()),
        "n_firm_quarters": int(len(d)),
        "n_firms": int(d["cik"].nunique()),
        "pooled": {},
        "by_quarter": [],
        "coverage": {
            "sales_growth": int(d["sales_growth_yoy"].notna().sum()),
            "gross_margin_change": int(d["gross_margin_change_yoy"].notna().sum()),
            "cash_ratio": int(d["cash_ratio_q"].notna().sum()),
            "write_down": int(d["write_down_to_cogs_q"].notna().sum()),
        },
        "note": ("quarterly outcomes are calendar quarters (period end in Q1-Q3); "
                 "Q1 growth is measured against the same fiscal quarter a year "
                 "earlier.  The tests are descriptive."),
    }

    for shock_year, pre_year in SHOCKS.items():
        s = d[d["calendar_year"] == shock_year].copy()
        key = str(shock_year)
        results["pooled"][key] = {}
        for name, col in OUTCOMES.items():
            results["pooled"][key][name] = fit_pooled(s, col, "ccc_pre")
            for quarter, g in s.groupby("quarter"):
                row = fit_quarter(g, col, "ccc_pre")
                row.update({"shock_year": shock_year, "quarter": quarter,
                            "outcome": name})
                results["by_quarter"].append(row)

    results["by_quarter"] = sorted(
        results["by_quarter"], key=lambda x: (x["shock_year"], x["quarter"], x["outcome"]))
    TABLES.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results["by_quarter"]).to_csv(
        TABLES / "quarterly_shock_coefficients.csv", index=False)
    write_json(OUT / "quarterly_results.json", results)
    print(f"quarterly shock: {len(d):,} firm-quarters, "
          f"{d['cik'].nunique():,} firms")
    return results


if __name__ == "__main__":
    main()
