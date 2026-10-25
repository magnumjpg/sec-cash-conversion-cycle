"""
Build the firm-year working-capital panel from cached SEC FSDS extracts.

Rules implemented (charter §3.2, §4):
  * filings: 10-K, 10-K/A, 20-F, 20-F/A, 40-F, 40-F/A only (filtered at download)
  * one value per (cik, tag, end): the latest `filed` wins
  * ordered tag fallbacks (src/tags.py); the winning tag is recorded per concept
  * balance sheet = point in time (qtrs == 0), income statement = annual
    duration (qtrs == 4); a flow is merged to a balance only when the period
    `end` dates are *identical*
  * currency must be USD, else the firm-year is dropped and counted
  * revenue > 0 and COGS > 0 required for the main sample
  * financials (SIC 6000-6999, incl. real estate 6500-6599) and utilities
    (4900-4999) excluded from the main sample but kept, flagged, in panel_full
  * >= 3 usable years per firm

Outputs
-------
data/processed/panel.csv          main sample, firm-year
data/processed/panel.parquet      same, typed
data/processed/panel_full.csv     pre-exclusion rows with exclusion flags
outputs/tables/attrition.csv      CIK/firm-year attrition by reason
outputs/tables/tag_usage.csv      which XBRL tag supplied each concept
outputs/tables/coverage_by_year.csv
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tags import (  # noqa: E402
    FLOW_CONCEPTS, FORMS, INSTANT_CONCEPTS, TAG_MAP, TAG_RANK, CONCEPT_OF_TAG,
    TIER_OF_TAG, sic2, sic_division,
)

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
FSDS = RAW / "fsds"
PROC = ROOT / "data" / "processed"
TABLES = ROOT / "outputs" / "tables"

YEAR_MIN, YEAR_MAX = 2010, 2024
MIN_YEARS_PER_FIRM = 3
LAG_DAYS_MIN, LAG_DAYS_MAX = 350, 380


# ----------------------------------------------------------------------------- loading
def load_raw() -> tuple[pd.DataFrame, pd.DataFrame]:
    sub_files = sorted(FSDS.glob("*_sub.parquet"))
    num_files = sorted(FSDS.glob("*_num.parquet"))
    if not sub_files:
        raise FileNotFoundError("no cached FSDS files - run src/download_sec.py first")
    subs = pd.concat([pd.read_parquet(f) for f in sub_files], ignore_index=True)
    nums = pd.concat([pd.read_parquet(f) for f in num_files], ignore_index=True)

    subs = subs.drop_duplicates("adsh", keep="last")
    subs["cik"] = pd.to_numeric(subs["cik"], errors="coerce").astype("Int64")
    subs = subs.dropna(subset=["cik"])
    subs["cik"] = subs["cik"].astype("int64")
    subs["filed"] = pd.to_numeric(subs["filed"], errors="coerce").astype("Int64")
    subs["fy"] = pd.to_numeric(subs["fy"], errors="coerce").astype("Int64")
    subs["period"] = pd.to_numeric(subs["period"], errors="coerce").astype("Int64")

    nums["qtrs"] = pd.to_numeric(nums["qtrs"], errors="coerce").astype("Int64")
    nums["value"] = pd.to_numeric(nums["value"], errors="coerce")
    nums["ddate"] = pd.to_numeric(nums["ddate"], errors="coerce").astype("Int64")
    nums = nums.dropna(subset=["ddate", "value"])
    nums["ddate"] = nums["ddate"].astype("int64")
    return subs, nums


def to_date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.astype("Int64").astype(str), format="%Y%m%d", errors="coerce")


# ----------------------------------------------------------------------------- tagging
def resolve_tags(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Pick, per (cik, end, concept), the first available tag in rank order.

    Instant concepts (balance sheet) accept only qtrs == 0 facts; flow concepts
    (income statement) accept only qtrs == 4 facts.  The two blocks are then
    merged on an *identical* period end.
    """
    counts: dict[str, int] = {}
    counts["rows_tagged_us_gaap"] = int(len(df))
    counts["rows_non_usd"] = int((df["uom"] != "USD").sum())
    counts["ciks_non_usd"] = int(df.loc[df["uom"] != "USD", "cik"].nunique())
    usd = df[df["uom"] == "USD"].copy()

    usd["concept"] = usd["tag"].map(CONCEPT_OF_TAG)
    usd["rank"] = usd["tag"].map(TAG_RANK)
    usd = usd.dropna(subset=["concept"])

    # latest filed wins for a given (cik, tag, end, qtrs)
    usd = usd.sort_values(["cik", "tag", "ddate", "qtrs", "filed", "adsh"])
    before = len(usd)
    usd = usd.drop_duplicates(["cik", "tag", "ddate", "qtrs"], keep="last")
    counts["duplicate_tag_values_collapsed"] = int(before - len(usd))

    # ordered fallback *within concept*: first non-null tag by rank
    usd = usd.sort_values(["cik", "ddate", "qtrs", "concept", "rank"])
    best = usd.drop_duplicates(["cik", "ddate", "qtrs", "concept"], keep="first").copy()

    usage = (best.groupby(["concept", "tag"])
             .size().reset_index(name="firm_years")
             .sort_values(["concept", "firm_years"], ascending=[True, False]))
    usage["tier"] = usage["tag"].map(TIER_OF_TAG)
    usage["preferred"] = usage["tag"] == usage["concept"].map(
        {c: t[0][0] for c, t in TAG_MAP.items()})

    is_instant = best["concept"].isin(INSTANT_CONCEPTS)
    inst = best[is_instant & (best["qtrs"] == 0)]
    flow = best[~is_instant & (best["qtrs"] == 4)]
    counts["flow_facts_dropped_not_annual_duration"] = int(
        (best.loc[~is_instant & (best["qtrs"] != 4), "concept"].notna()).sum())

    def pivot_block(b: pd.DataFrame) -> pd.DataFrame:
        v = b.pivot(index=["cik", "ddate"], columns="concept", values="value")
        u = b.pivot(index=["cik", "ddate"], columns="concept", values="uom")
        u.columns = [f"uom_{c}" for c in u.columns]
        t = b.pivot(index=["cik", "ddate"], columns="concept", values="tag")
        t.columns = [f"tag_{c}" for c in t.columns]
        return pd.concat([v, u, t], axis=1)

    wide = pivot_block(flow).merge(pivot_block(inst), on=["cik", "ddate"], how="inner",
                                   suffixes=("", "_bal"))
    counts["firm_years_flow_balance_matched_on_exact_end"] = int(len(wide))
    return wide.reset_index(), usage, counts


def fiscal_year_map(subs: pd.DataFrame) -> pd.DataFrame:
    """(cik, period_end) -> fiscal-year label taken from the annual report itself."""
    fy = subs[(subs["fp"] == "FY") & subs["period"].notna() & subs["fy"].notna()].copy()
    fy = fy.sort_values(["cik", "period", "filed"])
    fy = fy.drop_duplicates(["cik", "period"], keep="last")
    return fy[["cik", "period", "fy"]].rename(columns={"period": "ddate", "fy": "fy_label"})


# ----------------------------------------------------------------------------- panel
def build_panel() -> dict:
    PROC.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)

    subs, nums = load_raw()
    log: dict = {}
    log["n_annual_filings_cached"] = int(len(subs))
    log["n_ciks_with_annual_filing"] = int(subs["cik"].nunique())

    merged = nums.merge(subs[["adsh", "cik", "sic", "form", "filed", "period", "fy", "fp"]],
                        on="adsh", how="inner")
    log["n_num_rows_matched_to_annual_filings"] = int(len(merged))

    # IFRS filers (ifrs-full taxonomy) are out of scope -> counted, not silently dropped
    ifrs_mask = ~merged["version"].astype(str).str.startswith("us-gaap")
    log["n_rows_ifrs_taxonomy_excluded"] = int(ifrs_mask.sum())
    merged = merged[~ifrs_mask].drop(columns=["version"])

    wide, usage, tag_counts = resolve_tags(merged)
    log.update(tag_counts)
    log["n_ciks_with_a_project_tag"] = int(wide["cik"].nunique())

    panel = wide
    pmeta = (merged.sort_values(["cik", "ddate", "filed"])
             .groupby(["cik", "ddate"])
             .agg(filed=("filed", "max"), form=("form", "last"))
             .reset_index())
    panel = panel.merge(pmeta, on=["cik", "ddate"], how="left")

    panel = panel.merge(fiscal_year_map(subs), on=["cik", "ddate"], how="left")
    panel["_is_fy_period"] = panel["fy_label"].notna()
    panel["fy_label"] = panel["fy_label"].fillna(panel["ddate"] // 10000)
    panel["fy_label"] = panel["fy_label"].astype(int)

    # A transition/long period can make two ends share one fiscal-year label.
    before = len(panel)
    log["firm_years_flow_balance_matched_on_exact_end"] = int(before)
    log["firms_flow_balance_matched_on_exact_end"] = int(panel["cik"].nunique())
    panel = panel.sort_values(["cik", "fy_label", "_is_fy_period", "ddate"])
    panel = panel.drop_duplicates(["cik", "fy_label"], keep="last")
    log["firm_years_dropped_duplicate_fiscal_year"] = int(before - len(panel))

    panel["fiscal_year"] = panel["fy_label"]
    in_window = (panel["fiscal_year"] >= YEAR_MIN) & (panel["fiscal_year"] <= YEAR_MAX)
    log["firm_years_outside_2010_2024_window"] = int((~in_window).sum())
    panel = panel[in_window].copy()
    log["firm_years_in_2010_2024_window"] = int(len(panel))

    # universe metadata: latest SIC / name / ticker per CIK
    meta = subs.sort_values("filed").drop_duplicates("cik", keep="last")[["cik", "name", "sic"]]
    panel = panel.merge(meta, on="cik", how="left")
    try:
        tk = pd.read_parquet(RAW / "tickers.parquet")
        tk = tk.rename(columns={"name": "ticker_name"}).drop(columns=["ticker_name"], errors="ignore")
        panel = panel.merge(tk, on="cik", how="left")
    except Exception:  # noqa: BLE001
        panel["ticker"] = pd.NA
        panel["exchange"] = pd.NA

    panel["sic"] = pd.to_numeric(panel["sic"], errors="coerce")
    panel["sic2"] = panel["sic"].map(sic2)
    panel["sic3"] = (panel["sic"] // 10).astype("Int64")
    panel["industry"] = panel["sic"].map(sic_division)
    panel["fiscal_year_end"] = to_date(panel["ddate"])
    panel["filed_date"] = to_date(panel["filed"])

    # ---------------- measurement filters, counted one by one
    rows: list[dict] = []

    def record(step: str, df: pd.DataFrame, level: str = "firm-year") -> None:
        rows.append({
            "level": level,
            "step": step,
            "n": int(len(df)),
            "firms": int(df["cik"].nunique()) if len(df) else 0,
        })

    def record_n(step: str, n: int, firms: int | None = None) -> None:
        rows.append({"level": "firm-year", "step": step, "n": int(n), "firms": firms})

    # fact-level attrition (rows of num.txt, not firm-years)
    rows.append({"level": "fact",
                 "step": "F0. us-gaap facts, project tags, annual filings, consolidated, qtrs 0/4",
                 "n": int(log.get("rows_tagged_us_gaap", 0)), "firms": None})
    rows.append({"level": "fact", "step": "F1. dropped: reporting currency not USD",
                 "n": int(log.get("rows_non_usd", 0)), "firms": int(log.get("ciks_non_usd", 0))})
    rows.append({"level": "fact", "step": "F2. dropped: IFRS taxonomy (ifrs-full)",
                 "n": int(log.get("n_rows_ifrs_taxonomy_excluded", 0)), "firms": None})
    rows.append({"level": "fact", "step": "F3. dropped: duplicate tag/period, older filing",
                 "n": int(log.get("duplicate_tag_values_collapsed", 0)), "firms": None})
    rows.append({"level": "fact", "step": "F4. dropped: flow fact without annual duration (qtrs != 4)",
                 "n": int(log.get("flow_facts_dropped_not_annual_duration", 0)), "firms": None})

    record_n("0. flow+balance matched on exact fiscal-year end",
             log["firm_years_flow_balance_matched_on_exact_end"],
             log.get("firms_flow_balance_matched_on_exact_end"))
    record_n("0a. dropped: duplicate fiscal-year label",
             log["firm_years_dropped_duplicate_fiscal_year"])
    record_n("0b. dropped: fiscal year outside 2010-2024",
             log["firm_years_outside_2010_2024_window"])
    record_n("0c. firm-years in 2010-2024 window",
             log["firm_years_in_2010_2024_window"])

    u = panel[[c for c in panel.columns if c.startswith("uom_")]]
    usd_ok = ~(u.notna() & (u != "USD")).any(axis=1)
    record("1. dropped: firm-year with mixed/non-USD currency", panel[~usd_ok])
    panel = panel[usd_ok].copy()

    need = ["revenue", "cogs", "ar", "inventory", "ap"]
    present = panel[need].notna().all(axis=1)
    record("2. dropped: missing revenue/COGS/AR/inventory/AP", panel[~present])
    panel = panel[present].copy()

    pos = (panel["revenue"] > 0) & (panel["cogs"] > 0)
    record("3. dropped: revenue<=0 or COGS<=0", panel[~pos])
    panel = panel[pos].copy()

    bal_ok = (panel[["ar", "inventory", "ap"]] >= 0).all(axis=1)
    record("4. dropped: negative balance-sheet item", panel[~bal_ok])
    panel = panel[bal_ok].copy()

    recap = panel[need].abs().sum(axis=1)
    rec_ok = recap > 0
    record("5. dropped: all working-capital items zero", panel[~rec_ok])
    panel = panel[rec_ok].copy()

    fin = panel["sic"].between(6000, 6999)
    record("6. dropped: financials & real estate (SIC 6000-6999)", panel[fin])
    util = panel["sic"].between(4900, 4999)
    record("7. dropped: utilities (SIC 4900-4999)", panel[util & ~fin])
    panel["is_financial"] = fin
    panel["is_utility"] = util
    panel_all = panel.copy()          # kept for the robustness table
    panel = panel[~fin & ~util].copy()

    counts = panel.groupby("cik")["fiscal_year"].nunique()
    keep = counts[counts >= MIN_YEARS_PER_FIRM].index
    record(f"8. dropped: fewer than {MIN_YEARS_PER_FIRM} usable years", panel[~panel["cik"].isin(keep)])
    panel = panel[panel["cik"].isin(keep)].copy()
    record("9. MAIN SAMPLE", panel)

    panel = panel.sort_values(["cik", "ddate"]).reset_index(drop=True)

    # ---------------- measures (charter §4)
    def add_core_measures(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["dso"] = 365 * df["ar"] / df["revenue"]
        df["dio"] = 365 * df["inventory"] / df["cogs"]
        df["dpo"] = 365 * df["ap"] / df["cogs"]
        df["ccc"] = df["dso"] + df["dio"] - df["dpo"]
        df["negative_ccc"] = (df["ccc"] < 0).astype(int)
        df["gross_margin"] = (df["revenue"] - df["cogs"]) / df["revenue"]
        df["roa"] = df["net_income"] / df["assets"]
        df["cash_ratio"] = df["cash"] / df["assets"]
        df["current_ratio"] = df["assets_current"] / df["liabilities_current"]
        df["nwc_to_sales"] = (df["ar"] + df["inventory"] - df["ap"]) / df["revenue"]
        df["log_assets"] = np.log(df["assets"].where(df["assets"] > 0))
        return df

    panel_all = add_core_measures(panel_all)
    panel = add_core_measures(panel)

    p = panel
    p["days_since_prev"] = p.groupby("cik")["fiscal_year_end"].diff().dt.days
    lag_ok = p["days_since_prev"].between(LAG_DAYS_MIN, LAG_DAYS_MAX)
    for col in ["ccc", "dso", "dio", "dpo", "ar", "inventory", "ap", "revenue",
                "cogs", "gross_margin", "roa", "assets"]:
        p[f"{col}_lag"] = p.groupby("cik")[col].shift(1).where(lag_ok)

    p["dso_avg"] = 365 * (p["ar"] + p["ar_lag"]) / 2 / p["revenue"]
    p["dio_avg"] = 365 * (p["inventory"] + p["inventory_lag"]) / 2 / p["cogs"]
    p["dpo_avg"] = 365 * (p["ap"] + p["ap_lag"]) / 2 / p["cogs"]
    p["ccc_avg"] = p["dso_avg"] + p["dio_avg"] - p["dpo_avg"]
    p["ccc_change"] = p["ccc"] - p["ccc_lag"]
    p["sales_growth"] = p["revenue"] / p["revenue_lag"] - 1
    p["ccc_volatility"] = p.groupby("cik")["ccc"].transform(lambda s: s.std(ddof=1))

    p["tag_revenue"] = p["tag_revenue"].astype(str)
    p["tag_cogs"] = p["tag_cogs"].astype(str)
    p["tag_ar"] = p["tag_ar"].astype(str)
    p["tag_inventory"] = p["tag_inventory"].astype(str)
    p["tag_ap"] = p["tag_ap"].astype(str)

    # ---------------- write
    keep_cols = [
        "cik", "name", "ticker", "exchange", "sic", "sic2", "sic3", "industry",
        "fiscal_year", "fiscal_year_end", "form", "filed_date", "revenue", "cogs",
        "ar", "inventory", "ap", "assets", "assets_current", "liabilities_current",
        "cash", "equity", "net_income", "op_income",
        "dso", "dio", "dpo", "ccc", "dso_avg", "dio_avg", "dpo_avg", "ccc_avg",
        "negative_ccc", "gross_margin", "roa", "cash_ratio", "current_ratio",
        "nwc_to_sales", "log_assets", "sales_growth", "ccc_change", "ccc_volatility",
        "ccc_lag", "dso_lag", "dio_lag", "dpo_lag", "gross_margin_lag", "roa_lag",
        "assets_lag", "revenue_lag",
        "days_since_prev", "tag_revenue", "tag_cogs", "tag_ar", "tag_inventory", "tag_ap",
    ]
    main = p[keep_cols].copy()
    main.to_csv(PROC / "panel.csv", index=False)
    main.to_parquet(PROC / "panel.parquet", index=False)

    full_cols = [c for c in keep_cols + ["is_financial", "is_utility"] if c in panel_all.columns]
    p_full = panel_all[full_cols].copy()
    p_full.to_csv(PROC / "panel_full.csv.gz", index=False, compression="gzip")

    att = pd.DataFrame(rows)
    att.to_csv(TABLES / "attrition.csv", index=False)

    usage_out = usage.copy()
    usage_out["share_of_concept"] = usage_out["firm_years"] / usage_out.groupby("concept")[
        "firm_years"].transform("sum")
    usage_out.to_csv(TABLES / "tag_usage.csv", index=False)

    cov = (main.groupby("fiscal_year")
           .agg(firms=("cik", "nunique"), rows=("cik", "size"),
                ccc_median=("ccc", "median"))
           .reset_index())
    cov.to_csv(TABLES / "coverage_by_year.csv", index=False)

    stats = {
        "panel_rows": int(len(main)),
        "panel_firms": int(main["cik"].nunique()),
        "year_min": int(main["fiscal_year"].min()),
        "year_max": int(main["fiscal_year"].max()),
        "n_industries_sic2": int(main["sic2"].nunique()),
        "attrition": att.to_dict(orient="records"),
        "tag_usage_top": usage_out.head(40).to_dict(orient="records"),
        "raw": {k: int(v) for k, v in log.items()},
        "rows_per_year": cov.set_index("fiscal_year")["rows"].to_dict(),
    }
    with open(ROOT / "outputs" / "panel_stats.json", "w", encoding="utf-8") as fh:
        json.dump(stats, fh, indent=2, default=int)

    print(f"panel: {len(main):,} firm-years, {main['cik'].nunique():,} firms, "
          f"{main['fiscal_year'].min()}-{main['fiscal_year'].max()}")
    print(att.to_string(index=False))
    return stats


if __name__ == "__main__":
    build_panel()
