"""
Build a quarterly 10-Q panel for the 2020/2022 shock tests.

The annual 10-K panel cannot resolve a shock that lasted weeks.  This module
uses the 2019q1-2022q4 FSDS cache (10-Q forms, qtrs 0/1) to build one
observation per firm-fiscal-quarter:

    revenue_q, cogs_q, gross_margin_q, cash/assets, write-down/COGS
    DSO/DIO/DPO/CCC at the quarter-end balance, with quarterly flows annualised

Only Q1-Q3 are used for outcomes; the pre-shock CCC is taken from the annual
panel (FY2019 for 2020, FY2021 for 2022), so the exposure variable is the same
annual balance-sheet measure used in the headline, measured before the shock.

Run:
    python src/build_quarterly.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_panel import add_ap_quality  # noqa: E402
from json_utils import write_json  # noqa: E402
from tags import (  # noqa: E402
    CONCEPT_OF_TAG, INSTANT_CONCEPTS, TAG_RANK, TIER_OF_TAG, sic2,
)

ROOT = Path(__file__).resolve().parents[1]
RAWQ = ROOT / "data" / "raw" / "fsds_q"
PROC = ROOT / "data" / "processed"
OUT = ROOT / "outputs"
FORMS_Q = {"10-Q", "10-Q/A"}
# A 2018 period is kept only so that 2019Q1 has a year-earlier comparison.
QUARTER_YEAR_MIN, QUARTER_YEAR_MAX = 2018, 2022


def load_raw_q() -> tuple[pd.DataFrame, pd.DataFrame]:
    subs = sorted(RAWQ.glob("*_sub.parquet"))
    if not subs:
        raise FileNotFoundError(
            "no quarterly cache - run `python src/download_sec.py --quarterly` first")
    sub = pd.concat([pd.read_parquet(f) for f in subs], ignore_index=True)
    num = pd.concat([pd.read_parquet(f.with_name(f.name.replace("_sub", "_num")))
                    for f in subs], ignore_index=True)
    sub = sub.drop_duplicates("adsh", keep="last")
    sub = sub[sub["form"].isin(FORMS_Q)].copy()
    for c in ["cik", "period", "fy", "filed"]:
        sub[c] = pd.to_numeric(sub[c], errors="coerce").astype("Int64")
    sub = sub.dropna(subset=["cik", "period", "fy"]).copy()
    sub["cik"] = sub["cik"].astype("int64")
    sub["fy"] = sub["fy"].astype("int64")
    sub["period"] = sub["period"].astype("int64")
    num["qtrs"] = pd.to_numeric(num["qtrs"], errors="coerce").astype("Int64")
    num["value"] = pd.to_numeric(num["value"], errors="coerce")
    num["ddate"] = pd.to_numeric(num["ddate"], errors="coerce").astype("Int64")
    num = num.dropna(subset=["ddate", "value"]).copy()
    num["ddate"] = num["ddate"].astype("int64")
    return sub, num


def resolve_q(subs: pd.DataFrame, nums: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    log: dict = {}
    merged = nums.merge(
        subs[["adsh", "cik", "name", "sic", "form", "period", "fy", "fp", "filed"]],
        on="adsh", how="inner",
    )
    # Current period facts only: a 10-Q also carries prior-year comparatives.
    merged = merged[merged["ddate"] == merged["period"]].copy()
    log["n_rows_current_period"] = int(len(merged))
    ifrs = ~merged["version"].astype(str).str.startswith("us-gaap")
    log["n_rows_ifrs_excluded"] = int(ifrs.sum())
    merged = merged[~ifrs].copy()
    merged["concept"] = merged["tag"].map(CONCEPT_OF_TAG)
    merged["rank"] = merged["tag"].map(TAG_RANK)
    merged = merged.dropna(subset=["concept"]).copy()
    merged = merged[merged["uom"] == "USD"].copy()
    log["n_rows_project_tags_usd"] = int(len(merged))

    merged = merged.sort_values(["cik", "tag", "ddate", "qtrs", "filed", "adsh"])
    before = len(merged)
    merged = merged.drop_duplicates(["cik", "tag", "ddate", "qtrs"], keep="last")
    log["duplicate_tag_values_collapsed"] = int(before - len(merged))

    merged = merged.sort_values(["cik", "ddate", "qtrs", "concept", "rank"])
    best = merged.drop_duplicates(["cik", "ddate", "qtrs", "concept"], keep="first").copy()
    usage = (best.groupby(["concept", "tag"]).size().reset_index(name="firm_quarters"))
    usage["tier"] = usage["tag"].map(TIER_OF_TAG)

    inst = best[best["concept"].isin(INSTANT_CONCEPTS) & (best["qtrs"] == 0)]
    flow = best[~best["concept"].isin(INSTANT_CONCEPTS) & (best["qtrs"] == 1)]
    log["instant_facts"] = int(len(inst))
    log["quarterly_flow_facts"] = int(len(flow))

    def pivot(b: pd.DataFrame) -> pd.DataFrame:
        v = b.pivot(index=["cik", "ddate"], columns="concept", values="value")
        t = b.pivot(index=["cik", "ddate"], columns="concept", values="tag")
        t.columns = [f"tag_{c}" for c in t.columns]
        return pd.concat([v, t], axis=1)

    wide = pivot(flow).merge(pivot(inst), on=["cik", "ddate"], how="inner",
                             suffixes=("", "_bal")).reset_index()
    wide = add_ap_quality(wide)
    # One label per firm-quarter: prefer the current 10-Q.
    labels = (subs.sort_values(["cik", "period", "filed"])
              .drop_duplicates(["cik", "period"], keep="last")
              [["cik", "period", "fy", "fp", "form", "sic", "name"]]
              .rename(columns={"period": "ddate"}))
    wide = wide.merge(labels, on=["cik", "ddate"], how="left")
    wide["sic2"] = wide["sic"].map(sic2)
    # Calendar labels are derived from the period end, not from `fy`: a small
    # number of filings carry an implausible fiscal-year focus (a 2020 10-Q
    # tagged fy=2010), and the shock window is calendar time, not an issuer label.
    period_end = pd.to_datetime(wide["ddate"].astype(str), format="%Y%m%d",
                                errors="coerce")
    wide["calendar_year"] = period_end.dt.year.astype("Int64")
    wide["quarter"] = (period_end.dt.year.astype(str) + "Q"
                       + period_end.dt.quarter.astype(str))
    log["fiscal_year_labels_implausible"] = int(
        (wide["fy"] - wide["calendar_year"]).abs().gt(1).sum())
    # Stale amendments filed in 2019-2022 can quote a 2016 period end; they are
    # not part of a 2018-2022 quarterly panel and would only pollute the labels.
    in_window = wide["calendar_year"].between(QUARTER_YEAR_MIN, QUARTER_YEAR_MAX)
    log["firm_quarters_outside_window"] = int((~in_window).sum())
    wide = wide[in_window].copy()
    log["firm_quarters"] = int(len(wide))
    log["firms"] = int(wide["cik"].nunique())
    return wide, usage, log


def add_measures(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["revenue_q"] = d["revenue"]
    d["cogs_q"] = d["cogs"]
    d["net_income_q"] = d["net_income"]
    d["write_down_q"] = d["inventory_write_down"]
    d["dso_q"] = 365 * d["ar"] / (d["revenue_q"] * 4)
    d["dio_q"] = 365 * d["inventory"] / (d["cogs_q"] * 4)
    d["dpo_q"] = 365 * d["ap_clean"] / (d["cogs_q"] * 4)
    d["ccc_q"] = d["dso_q"] + d["dio_q"] - d["dpo_q"]
    d["gross_margin_q"] = (d["revenue_q"] - d["cogs_q"]) / d["revenue_q"]
    d["cash_ratio_q"] = d["cash"] / d["assets"]
    d["write_down_to_cogs_q"] = d["write_down_q"] / d["cogs_q"]
    d["log_assets_q"] = np.log(d["assets"].where(d["assets"] > 0))
    return d


def add_yoy(d: pd.DataFrame) -> pd.DataFrame:
    """Match each quarter to its own period one year earlier.

    A fiscal-year/fiscal-period label is not unique: transition periods and
    amended filings can put two period ends under the same (fy, fp), and a
    label join then duplicates rows.  Matching the actual period end to the
    observation closest to one year earlier is unique by construction and
    tolerates 52/53-week fiscal calendars (within 45 days).
    """
    d = d.copy()
    d["_ddate"] = pd.to_datetime(d["ddate"].astype(str), format="%Y%m%d",
                                 errors="coerce")
    cols = ["revenue_q", "cogs_q", "gross_margin_q", "write_down_to_cogs_q",
            "ccc_q"]
    prior = d[["cik", "_ddate"] + cols].dropna(subset=["_ddate"]).copy()
    prior["_ddate_prior"] = prior["_ddate"] + pd.DateOffset(years=1)
    prior = prior.rename(columns={c: f"{c}_prior" for c in cols})
    prior = prior.drop(columns=["_ddate"]).sort_values("_ddate_prior")

    cur = d.sort_values("_ddate").reset_index(drop=True)
    d = pd.merge_asof(
        cur, prior,
        left_on="_ddate", right_on="_ddate_prior", by="cik",
        direction="nearest", tolerance=pd.Timedelta(days=45),
    )
    d = d.drop(columns=["_ddate"])
    d["sales_growth_yoy"] = d["revenue_q"] / d["revenue_q_prior"] - 1
    d["gross_margin_change_yoy"] = d["gross_margin_q"] - d["gross_margin_q_prior"]
    d["write_down_change_yoy"] = (d["write_down_to_cogs_q"]
                                  - d["write_down_to_cogs_q_prior"])
    d["ccc_change_qoq"] = d["ccc_q"] - d["ccc_q_prior"]
    return d


def build() -> dict:
    PROC.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    subs, nums = load_raw_q()
    wide, usage, log = resolve_q(subs, nums)
    d = add_measures(wide)
    d = add_yoy(d)
    assert not d.duplicated(["cik", "ddate"]).any(), \
        "quarterly panel must have one row per firm-quarter"
    keep = [
        "cik", "name", "sic", "sic2", "form", "ddate", "fy", "fp", "quarter",
        "calendar_year",
        "revenue_q", "cogs_q", "net_income_q", "gross_margin_q", "cash_ratio_q",
        "write_down_q", "write_down_to_cogs_q", "sales_growth_yoy",
        "gross_margin_change_yoy", "write_down_change_yoy", "ccc_change_qoq",
        "ar", "inventory", "ap", "ap_clean", "ap_quality", "accrued_liabilities",
        "assets", "assets_current", "cash", "ppe_net",
        "dso_q", "dio_q", "dpo_q", "ccc_q",
        "tag_revenue", "tag_cogs", "tag_ar", "tag_inventory", "tag_ap",
    ]
    for c in keep:
        if c not in d.columns:
            d[c] = np.nan
    d = d[keep].sort_values(["cik", "ddate"]).reset_index(drop=True)
    d.to_csv(PROC / "quarterly_panel.csv", index=False)
    d.to_parquet(PROC / "quarterly_panel.parquet", index=False)
    usage.to_csv(OUT / "tables" / "quarterly_tag_usage.csv", index=False)
    stats = {**log, "rows_out": int(len(d)),
             "firms_out": int(d["cik"].nunique()),
             "quarters": sorted(d["quarter"].dropna().unique().tolist()),
             "ap_quality_counts": {str(k): int(v)
                                   for k, v in d["ap_quality"].value_counts().items()},
             "coverage": {
                 "sales_growth_yoy": int(d["sales_growth_yoy"].notna().sum()),
                 "gross_margin_change_yoy": int(d["gross_margin_change_yoy"].notna().sum()),
                 "write_down_to_cogs_q": int(d["write_down_to_cogs_q"].notna().sum()),
             }}
    write_json(OUT / "quarterly_stats.json", stats)
    print(f"quarterly panel: {len(d):,} firm-quarters, "
          f"{d['cik'].nunique():,} firms, {d['quarter'].nunique()} quarters")
    return stats


if __name__ == "__main__":
    build()
