"""
Estimation: descriptive CCC structure, persistence, CCC-ROA association,
2020/2022 cross-sections, and the charter's robustness battery.

Everything that ends up in README.md is written to outputs/results.json by this
module. All estimates are associations; no causal language is implied.

    python src/analysis.py
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from linearmodels.panel import PanelOLS

warnings.filterwarnings("ignore", category=FutureWarning)

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT = ROOT / "outputs"
TABLES = OUT / "tables"
sys.path.insert(0, str(Path(__file__).resolve().parent))

MIN_IND_FIRM_YEARS = 100      # industries reported individually
MIN_IND_FIRMS = 5


# ----------------------------------------------------------------------------- helpers
def r(x, nd: int = 6):
    try:
        if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
            return None
        return round(float(x), nd)
    except (TypeError, ValueError):
        return x


def winsorize(s: pd.Series, groups: list[pd.Series], lower=0.01, upper=0.99,
              min_group: int = 50) -> pd.Series:
    """Winsorize within groups; thin groups fall back to pooled quantiles.

    Industry-year cells with < min_group observations would otherwise keep their
    own extremes (a 1% cut of 30 observations clips nothing), so the pooled
    sample bound is used instead.
    """
    g = s.groupby(groups)
    n = g.transform("size")
    lo = g.transform(lambda x: x.quantile(lower))
    hi = g.transform(lambda x: x.quantile(upper))
    lo_pool, hi_pool = s.quantile(lower), s.quantile(upper)
    lo = lo.where(n >= min_group, lo_pool)
    hi = hi.where(n >= min_group, hi_pool)
    return s.clip(lo, hi)


def add_winsorized(p: pd.DataFrame) -> pd.DataFrame:
    """Winsorized analysis variables (1/99 within industry-year, pooled fallback)."""
    p = p.sort_values(["cik", "fiscal_year"]).copy()
    for col in ["ccc", "dso", "dio", "dpo", "roa", "gross_margin", "nwc_to_sales"]:
        p[f"{col}_w"] = winsorize(p[col], [p["sic2"], p["fiscal_year"]])
    mask = p["days_since_prev"].between(350, 380)
    for col in ["ccc", "dso", "dio", "dpo"]:
        p[f"{col}_w_lag"] = p.groupby("cik")[f"{col}_w"].shift(1).where(mask)
    return p


def plausibility_screen(p: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Drop observations whose *ratios* are not interpretable.

    XBRL contains genuine scale errors (e.g. Assets tagged in millions rather
    than dollars, COGS tagged at 1/1000 of revenue). They are ~5% of rows, all
    micro-caps or clearly mis-tagged, and they dominate any mean, SD or OLS
    estimate. Headline medians are computed on the unscreened sample.
    """
    m = (p["ccc"].abs() <= 3650) & (p["assets"] >= 1e6) & (p["revenue"] >= 1e6)
    dropped = p[~m]
    info = {
        "n_before": int(len(p)),
        "n_after": int(m.sum()),
        "n_dropped": int((~m).sum()),
        "share_dropped": r((~m).mean()),
        "dropped_abs_ccc_gt_3650": int((p["ccc"].abs() > 3650).sum()),
        "dropped_assets_lt_1m": int((p["assets"] < 1e6).sum()),
        "dropped_revenue_lt_1m": int((p["revenue"] < 1e6).sum()),
        "rule": "|CCC| <= 3650 days & total assets >= $1m & revenue >= $1m",
        "median_ccc_dropped": r(dropped["ccc"].median()),
        "median_ccc_kept": r(p.loc[m, "ccc"].median()),
    }
    return p[m].copy(), info


def ols_cluster(y: pd.Series, X: pd.DataFrame, groups: pd.Series | None = None,
                cov: str = "HC1"):
    X = sm.add_constant(X, has_constant="add")
    mod = sm.OLS(y.astype(float), X.astype(float), missing="drop")
    if groups is not None:
        res = mod.fit(cov_type="cluster", cov_kwds={"groups": groups})
    else:
        res = mod.fit(cov_type=cov)
    return res


def panel_fit(df: pd.DataFrame, y: str, xs: list[str], entity: bool, time: bool):
    d = df.dropna(subset=[y] + xs).copy()
    d = d.set_index(["cik", "fiscal_year"])
    mod = PanelOLS(d[y], d[xs], entity_effects=entity, time_effects=time, drop_absorbed=True)
    return mod.fit(cov_type="clustered", cluster_entity=True), len(d)


def stars(p):
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


def summarize(res, term: str) -> dict:
    if hasattr(res, "std_errors"):      # linearmodels PanelResults
        se, tstat, pval = res.std_errors, res.tstats, res.pvalues
    else:                               # statsmodels RegressionResults
        se, tstat, pval = res.bse, res.tvalues, res.pvalues
    return {
        "beta": r(res.params.get(term)),
        "se": r(se.get(term)),
        "t": r(tstat.get(term)),
        "p": r(pval.get(term)),
        "n": int(res.nobs),
        "stars": stars(pval.get(term, 1.0)),
    }


# ----------------------------------------------------------------------------- descriptives
def descriptives(p: pd.DataFrame, p_est: pd.DataFrame | None = None
                 ) -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    out: dict = {}
    for var in ["ccc", "dso", "dio", "dpo", "negative_ccc", "gross_margin", "roa",
                "cash_ratio", "current_ratio", "nwc_to_sales", "ccc_volatility"]:
        s = p[var].dropna()
        out[var] = {
            "mean": r(s.mean()), "sd": r(s.std()), "p10": r(s.quantile(0.10)),
            "p25": r(s.quantile(0.25)), "median": r(s.median()),
            "p75": r(s.quantile(0.75)), "p90": r(s.quantile(0.90)),
            "n": int(s.size),
        }
        if p_est is not None and var in p_est.columns:
            e = p_est[var].dropna()
            out[var].update({"mean_screened": r(e.mean()), "sd_screened": r(e.std()),
                             "median_screened": r(e.median()), "n_screened": int(e.size)})

    ind = (p.groupby(["sic2", "industry"])
           .agg(firm_years=("cik", "size"), firms=("cik", "nunique"),
                ccc_median=("ccc", "median"), ccc_q25=("ccc", lambda s: s.quantile(0.25)),
                ccc_q75=("ccc", lambda s: s.quantile(0.75)),
                ccc_mean=("ccc", "mean"),
                dso_median=("dso", "median"), dio_median=("dio", "median"),
                dpo_median=("dpo", "median"),
                neg_ccc_share=("negative_ccc", "mean"),
                gross_margin_median=("gross_margin", "median"),
                roa_median=("roa", "median"))
           .reset_index())
    ind = ind[(ind["firm_years"] >= MIN_IND_FIRM_YEARS) & (ind["firms"] >= MIN_IND_FIRMS)]
    ind = ind.sort_values("ccc_median")
    ind.to_csv(TABLES / "industry_summary.csv", index=False)

    yr = (p.groupby("fiscal_year")
          .agg(firms=("cik", "nunique"), rows=("cik", "size"),
               ccc_median=("ccc", "median"), ccc_mean=("ccc", "mean"),
               ccc_q25=("ccc", lambda s: s.quantile(0.25)),
               ccc_q75=("ccc", lambda s: s.quantile(0.75)),
               neg_ccc_share=("negative_ccc", "mean"),
               dso_median=("dso", "median"), dio_median=("dio", "median"),
               dpo_median=("dpo", "median"),
               gross_margin_median=("gross_margin", "median"),
               roa_median=("roa", "median"))
          .reset_index())
    yr.to_csv(TABLES / "year_summary.csv", index=False)

    # variance decomposition: between vs within industry, and between vs within firm
    src = p_est if p_est is not None else p
    col = "ccc_w" if (p_est is not None and "ccc_w" in p_est.columns) else "ccc"
    ccc = src[col].dropna()
    grand = ccc.mean()
    ss_total = float(((ccc - grand) ** 2).sum())

    def eta2(keys: pd.Series) -> float:
        gm = src.loc[ccc.index].groupby(keys.loc[ccc.index])[col]
        ss_b = float((gm.count() * (gm.mean() - grand) ** 2).sum())
        return ss_b / ss_total

    out["variance_decomposition"] = {
        "share_between_industries_sic2": r(eta2(src["sic2"])),
        "share_within_industries_sic2": r(1 - eta2(src["sic2"])),
        "share_between_firms": r(eta2(src["cik"])),
        "share_within_firms": r(1 - eta2(src["cik"])),
        "n_obs": int(ccc.size),
        "based_on": ("winsorized CCC on the screened sample" if col == "ccc_w"
                     else "raw CCC on the full sample"),
    }
    return out, ind, yr, p


# ----------------------------------------------------------------------------- persistence
def persistence(p: pd.DataFrame, scale_col: str = "ccc") -> tuple[dict, pd.DataFrame]:
    d = p.dropna(subset=[scale_col, f"{scale_col}_lag"]).copy()
    # bound the lag as well: a kept year can still follow an uninterpretable one
    d = d[(d[scale_col].abs() <= 3650) & (d[f"{scale_col}_lag"].abs() <= 3650)]
    if len(d) < 30:
        empty = {"beta": None, "se": None, "t": None, "p": None, "stars": "", "n": int(len(d)),
                 "half_life_years": None, "mean_reversion_1_minus_rho": None,
                 "by_industry": [], "with_firm_fe": {}, "model": "insufficient observations"}
        return empty, pd.DataFrame()
    res, n = panel_fit(d, scale_col, [f"{scale_col}_lag"], entity=False, time=True)
    rho = res.params[f"{scale_col}_lag"]
    out = summarize(res, f"{scale_col}_lag")
    out.update({
        "model": "y_it = a + rho*y_i,t-1 + year FE; SE clustered by firm",
        "r2": r(res.rsquared),
        "half_life_years": r(np.log(0.5) / np.log(rho)) if 0 < rho < 1 else None,
        "mean_reversion_1_minus_rho": r(1 - rho),
        "n_firms": int(d["cik"].nunique()),
    })

    # with firm FE (Nickell-biased; reported for completeness only)
    res_fe, n_fe = panel_fit(d, scale_col, [f"{scale_col}_lag"], entity=True, time=True)
    out["with_firm_fe"] = {
        "rho": r(res_fe.params[f"{scale_col}_lag"]),
        "se": r(res_fe.std_errors[f"{scale_col}_lag"]),
        "n": int(n_fe),
        "note": "biased downward with short panels (Nickell); upper/lower bound only",
    }

    # by 2-digit industry
    rows = []
    for sic2, g in d.groupby("sic2"):
        if g["cik"].nunique() < 20 or len(g) < MIN_IND_FIRM_YEARS:
            continue
        try:
            gi = g.set_index(["cik", "fiscal_year"])
            m = PanelOLS(gi[scale_col], gi[[f"{scale_col}_lag"]],
                         entity_effects=False, time_effects=True, drop_absorbed=True)
            ri = m.fit(cov_type="clustered", cluster_entity=True)
            rho_i = ri.params[f"{scale_col}_lag"]
            rows.append({
                "sic2": sic2, "industry": g["industry"].iloc[0],
                "rho": r(rho_i), "se": r(ri.std_errors[f"{scale_col}_lag"]),
                "half_life_years": r(np.log(0.5) / np.log(rho_i)) if 0 < rho_i < 1 else None,
                "n": int(ri.nobs), "firms": int(g["cik"].nunique()),
            })
        except Exception:  # noqa: BLE001
            continue
    byind = pd.DataFrame(rows).sort_values("rho", ascending=False)
    byind.to_csv(TABLES / f"persistence_by_industry_{scale_col}.csv", index=False)
    out["by_industry"] = byind.to_dict(orient="records")
    return out, byind


# ----------------------------------------------------------------------------- CCC and ROA
def ccc_roa(p: pd.DataFrame, ccc_col: str = "ccc", controls: bool = True,
            sample: pd.DataFrame | None = None, dep: str = "roa_w") -> dict:
    d = p if sample is None else sample
    xs = [ccc_col] + (["log_assets", "gross_margin"] if controls else [])
    if dep == "roa_w" and "roa_w" not in d.columns:
        d = d.copy()
        d["roa_w"] = winsorize(d["roa"], [d["sic2"], d["fiscal_year"]])
    d = d.dropna(subset=[dep] + xs).copy()
    if len(d) < 30:
        return {"beta": None, "se": None, "t": None, "p": None, "stars": "", "n": int(len(d)),
                "r2_within": None, "n_firms": int(d["cik"].nunique()), "beta_standardized": None,
                "sd_ccc": None, "sd_roa": None, "ccc_days_sd": None,
                "model": "insufficient observations"}
    res, n = panel_fit(d, dep, xs, entity=True, time=True)
    out = summarize(res, ccc_col)
    out["model"] = ("roa_it = firm FE + year FE + b*CCC_it"
                    + (" + log(assets) + gross margin" if controls else "")
                    + "; SE clustered by firm; ROA and CCC winsorized 1/99 industry-year")
    out["r2_within"] = r(res.rsquared_within)
    out["n_firms"] = int(d["cik"].nunique())
    sd_c = d[ccc_col].std()
    sd_roa = d[dep].std()
    out["beta_standardized"] = r(res.params[ccc_col] * sd_c / sd_roa)
    out["sd_ccc"] = r(sd_c)
    out["sd_roa"] = r(sd_roa)
    out["ccc_days_sd"] = r(sd_c)
    return out


# ----------------------------------------------------------------------------- shocks
def shock_cross_section(p: pd.DataFrame, year: int, ycol: str, xcol: str,
                        label: str) -> dict:
    d = p[(p["fiscal_year"] == year)].dropna(subset=[ycol, xcol, "sic2"]).copy()
    if len(d) < 30:
        return {"year": year, "y": ycol, "x": xcol, "label": label, "beta": None,
                "se": None, "t": None, "p": None, "stars": "", "n": int(len(d)),
                "r2": None, "n_firms": int(d["cik"].nunique()), "sd_y": None,
                "quintiles": [], "model": "insufficient observations"}
    # fat tails in accounting ratios: winsorize the dependent variable 1/99
    d["_y"] = winsorize(d[ycol], [d["sic2"]], min_group=10**9)
    dummies = pd.get_dummies(d["sic2"], prefix="ind", drop_first=True, dtype=float)
    X = pd.concat([d[[xcol]], dummies], axis=1)
    res = ols_cluster(d["_y"], X, cov="HC1")
    out = summarize(res, xcol)
    out.update({
        "year": year, "y": ycol, "x": xcol, "label": label,
        "model": (f"{ycol} (winsorized 1/99) on {xcol} + 2-digit SIC FE, "
                  f"cross-section {year}, HC1 SE"),
        "r2": r(res.rsquared),
        "n_firms": int(d["cik"].nunique()),
        "sd_y": r(d["_y"].std()),
    })
    # quintiles of the exposure variable
    try:
        d["q"] = pd.qcut(d[xcol], 5, labels=False, duplicates="drop")
        q = (d.groupby("q").agg(n=("cik", "size"), x_median=(xcol, "median"),
                                y_median=("_y", "median"), y_mean=("_y", "mean"))
             .reset_index())
        out["quintiles"] = [{k: r(v) if k != "n" else int(v) for k, v in row.items()}
                            for row in q.to_dict(orient="records")]
    except Exception:  # noqa: BLE001
        out["quintiles"] = []
    return out


# ----------------------------------------------------------------------------- robustness
def robustness(p: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []

    def add(name: str, res: dict, term: str, extra: str = "") -> None:
        rows.append({
            "spec": name,
            "dep_var": "roa",
            "term": term,
            "beta": res.get("beta"), "se": res.get("se"), "t": res.get("t"),
            "p": res.get("p"), "stars": res.get("stars", ""), "n": res.get("n"),
            "firms": res.get("n_firms"),
            "note": extra or res.get("model", ""),
        })

    # baseline: winsorized at 1/99 within industry-year
    p = p.copy()
    p["ccc_w"] = winsorize(p["ccc"], [p["sic2"], p["fiscal_year"]])
    p["roa_w"] = winsorize(p["roa"], [p["sic2"], p["fiscal_year"]])

    base = ccc_roa(p, "ccc_w")
    add("1. baseline: CCC winsorized 1/99 industry-year, firm+year FE, controls",
        base, "ccc_w")

    raw = ccc_roa(p, "ccc", dep="roa")
    add("2. no winsorization (raw CCC and raw ROA)", raw, "ccc")

    avg = ccc_roa(p.dropna(subset=["ccc_avg"]), "ccc_avg")
    add("3. average balances (mean of t and t-1)", avg, "ccc_avg")

    dpo_rev = p.copy()
    dpo_rev["ccc_dpo_rev"] = dpo_rev["dso"] + dpo_rev["dio"] - 365 * dpo_rev["ap"] / dpo_rev["revenue"]
    dpo_rev["ccc_dpo_rev_w"] = winsorize(dpo_rev["ccc_dpo_rev"], [dpo_rev["sic2"], dpo_rev["fiscal_year"]])
    alt = ccc_roa(dpo_rev, "ccc_dpo_rev_w")
    add("4. alternative DPO denominator (revenue)", alt, "ccc_dpo_rev_w")

    neg = ccc_roa(p[p["ccc_w"] < 0], "ccc_w")
    add("5. only negative-CCC firm-years", neg, "ccc_w")

    pos = ccc_roa(p[p["ccc_w"] >= 0], "ccc_w")
    add("6. only non-negative-CCC firm-years", pos, "ccc_w")

    trim = ccc_roa(p[p["ccc_w"].abs() <= 365], "ccc_w")
    add("7. drop |CCC| > 365 days", trim, "ccc_w")

    nocontrol = ccc_roa(p, "ccc_w", controls=False)
    add("11. baseline without controls (firm+year FE only)", nocontrol, "ccc_w")

    bal_years = list(range(2015, 2025))
    bal_firms = (p[p["fiscal_year"].isin(bal_years)].groupby("cik")["fiscal_year"]
                 .nunique().loc[lambda s: s == len(bal_years)].index)
    bal = ccc_roa(p[p["cik"].isin(bal_firms)], "ccc_w")
    add("8. balanced panel 2015-2024 (all 10 years present)", bal, "ccc_w")

    pref = p[(p["tag_revenue"] == "RevenueFromContractWithCustomerExcludingAssessedTax")
             & (p["tag_cogs"] == "CostOfGoodsAndServicesSold")
             & (p["tag_ar"] == "AccountsReceivableNetCurrent")
             & (p["tag_ap"] == "AccountsPayableCurrent")]
    pref_m = ccc_roa(pref, "ccc_w")
    add("9. only firm-years using the charter's preferred tag for every input",
        pref_m, "ccc_w")

    # 3-digit SIC FE in the cross-section instead of 2-digit
    d20 = p[p["fiscal_year"] == 2020].dropna(subset=["sales_growth", "ccc_w_lag", "sic3"]).copy()
    if len(d20) >= 30:
        d20["_y"] = winsorize(d20["sales_growth"], [d20["sic3"]], min_group=10**9)
        dm = pd.get_dummies(d20["sic3"].astype(int), prefix="s3", drop_first=True, dtype=float)
        res3 = ols_cluster(d20["_y"], pd.concat([d20[["ccc_w_lag"]], dm], axis=1))
        rows.append({"spec": "10. 2020 revenue growth: 3-digit SIC FE (vs 2-digit in headline)",
                     "dep_var": "sales_growth_2020", "term": "ccc_w_lag",
                     "beta": r(res3.params["ccc_w_lag"]), "se": r(res3.bse["ccc_w_lag"]),
                     "t": r(res3.tvalues["ccc_w_lag"]), "p": r(res3.pvalues["ccc_w_lag"]),
                     "stars": stars(res3.pvalues["ccc_w_lag"]), "n": int(res3.nobs),
                     "firms": int(d20["cik"].nunique()), "note": ""})

    # including financials & utilities (charter: keep for a robustness table)
    try:
        pf = pd.read_csv(PROC / "panel_full.csv.gz")
        pf["ccc_w"] = winsorize(pf["ccc"], [pf["sic2"], pf["fiscal_year"]])
        finres = ccc_roa(pf, "ccc_w")
        add("12. including financials, real estate & utilities (panel_full)", finres, "ccc_w")
    except Exception as exc:  # noqa: BLE001
        rows.append({"spec": "12. including financials/utilities", "dep_var": "roa",
                     "term": "ccc_w", "beta": None, "se": None, "t": None, "p": None,
                     "stars": "", "n": None, "firms": None, "note": f"failed: {exc}"})

    return rows


def persistence_robustness(p: pd.DataFrame) -> list[dict]:
    p = p.copy()
    p["ccc_w"] = winsorize(p["ccc"], [p["sic2"], p["fiscal_year"]])
    p["ccc_w_lag"] = p.groupby("cik")["ccc_w"].shift(1).where(
        p["days_since_prev"].between(350, 380))
    out = []

    def add(name, df, col):
        df = df.dropna(subset=[col, f"{col}_lag"])
        # bound series and lag: raw accounting ratios carry XBRL scale errors
        df = df[(df[col].abs() <= 3650) & (df[f"{col}_lag"].abs() <= 3650)]
        if len(df) < 30:
            out.append({"spec": name, "term": f"{col}_lag", "rho": None, "se": None,
                        "t": None, "half_life_years": None, "n": int(len(df)), "firms": None})
            return
        res, n = panel_fit(df, col, [f"{col}_lag"], entity=False, time=True)
        rho = res.params[f"{col}_lag"]
        out.append({"spec": name, "term": f"{col}_lag",
                    "rho": r(res.params[f"{col}_lag"]),
                    "se": r(res.std_errors[f"{col}_lag"]),
                    "t": r(res.tstats[f"{col}_lag"]),
                    "half_life_years": r(np.log(0.5) / np.log(rho)) if 0 < rho < 1 else None,
                    "n": int(res.nobs), "firms": int(df["cik"].nunique())})

    add("1. baseline (CCC, winsorized 1/99)", p, "ccc_w")
    add("2. raw CCC", p, "ccc")
    add("3. average balances", p.dropna(subset=["ccc_avg", "ccc_avg_lag"]), "ccc_avg")
    add("4. |CCC| <= 365", p[p["ccc_w"].abs() <= 365], "ccc_w")
    add("5. DSO only", p, "dso")
    add("6. DIO only", p, "dio")
    add("7. DPO only", p, "dpo")
    return out


# ----------------------------------------------------------------------------- main
def main() -> dict:
    TABLES.mkdir(parents=True, exist_ok=True)
    p = pd.read_parquet(PROC / "panel.parquet")
    p = p.sort_values(["cik", "fiscal_year"]).reset_index(drop=True)

    # lags for the robustness columns computed here
    p["ccc_avg_lag"] = p.groupby("cik")["ccc_avg"].shift(1).where(
        p["days_since_prev"].between(350, 380))

    stats_path = OUT / "panel_stats.json"
    panel_stats = json.loads(stats_path.read_text()) if stats_path.exists() else {}

    results: dict = {
        "meta": {
            "project": "02_working_capital_sec",
            "as_of_utc": pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sample_years": [int(p["fiscal_year"].min()), int(p["fiscal_year"].max())],
            "n_firm_years": int(len(p)),
            "n_firms": int(p["cik"].nunique()),
            "n_industries_sic2": int(p["sic2"].nunique()),
            "currency": "USD",
            "forms": "10-K, 10-K/A, 20-F, 20-F/A, 40-F, 40-F/A",
            "adjustment": "none (raw XBRL as filed, latest filing wins)",
            "note": "all estimates are associations, not causal effects",
        },
    }

    p_est, screen = plausibility_screen(p)
    p_est = add_winsorized(p_est)
    results["estimation_screen"] = screen

    desc, ind, yr, p = descriptives(p, p_est)
    results["descriptives"] = desc
    results["panel"] = {
        "rows": int(len(p)),
        "firms": int(p["cik"].nunique()),
        "year_min": int(p["fiscal_year"].min()),
        "year_max": int(p["fiscal_year"].max()),
        "rows_per_year": {int(k): int(v) for k, v in p.groupby("fiscal_year").size().items()},
        "firms_per_year": {int(k): int(v) for k, v in p.groupby("fiscal_year")["cik"].nunique().items()},
        "n_industries_sic2": int(p["sic2"].nunique()),
        "n_industries_reported": int(len(ind)),
        "share_negative_ccc": r(p["negative_ccc"].mean()),
        "median_ccc": r(p["ccc"].median()),
        "median_dso": r(p["dso"].median()),
        "median_dio": r(p["dio"].median()),
        "median_dpo": r(p["dpo"].median()),
    }
    results["industries"] = [
        {k: (r(v) if isinstance(v, float) else v) for k, v in row.items()}
        for row in ind.to_dict(orient="records")
    ]
    results["by_year"] = [
        {k: (r(v) if isinstance(v, float) else v) for k, v in row.items()}
        for row in yr.to_dict(orient="records")
    ]

    rho, _ = persistence(p_est, "ccc_w")
    results["persistence"] = rho
    results["persistence_dso_dio_dpo"] = {c: persistence(p_est, f"{c}_w")[0]
                                          for c in ["dso", "dio", "dpo"]}
    results["persistence_raw_ccc"] = persistence(p_est, "ccc")[0]

    results["ccc_roa"] = ccc_roa(p_est, "ccc_w")
    results["ccc_roa_raw"] = ccc_roa(p_est, "ccc")

    results["shock_2020"] = {
        "revenue_growth": shock_cross_section(p_est, 2020, "sales_growth", "ccc_w_lag",
                                             "2019 CCC vs 2019->2020 revenue growth"),
        "roa": shock_cross_section(p_est, 2020, "roa", "ccc_w_lag", "2019 CCC vs 2020 ROA"),
        "cash_ratio": shock_cross_section(p_est, 2020, "cash_ratio", "ccc_w_lag",
                                          "2019 CCC vs 2020 cash/assets"),
    }
    p_est["margin_change"] = p_est["gross_margin"] - p_est["gross_margin_lag"]
    results["shock_2022"] = {
        "margin_change": shock_cross_section(p_est, 2022, "margin_change", "ccc_w_lag",
                                             "2021 CCC vs 2021->2022 gross-margin change"),
        "roa": shock_cross_section(p_est, 2022, "roa", "ccc_w_lag", "2021 CCC vs 2022 ROA"),
    }

    results["robustness_ccc_roa"] = robustness(p_est)
    results["robustness_persistence"] = persistence_robustness(p_est)

    # attrition + tag usage straight from the panel build
    att_path = TABLES / "attrition.csv"
    if att_path.exists():
        results["attrition"] = pd.read_csv(att_path).to_dict(orient="records")
    tu_path = TABLES / "tag_usage.csv"
    if tu_path.exists():
        tu = pd.read_csv(tu_path)
        results["tag_usage"] = [
            {"concept": row["concept"], "tag": row["tag"], "firm_years": int(row["firm_years"]),
             "share": r(row["share_of_concept"]), "tier": row["tier"]}
            for _, row in tu.iterrows()
        ]
    if panel_stats:
        results["build_log"] = panel_stats.get("raw", {})
        bl = results["build_log"]
        results["funnel"] = {
            "ciks_with_annual_filing": bl.get("n_ciks_with_annual_filing"),
            "ciks_with_project_tag": bl.get("n_ciks_with_a_project_tag"),
            "firm_years_matched_on_exact_end": bl.get("firm_years_flow_balance_matched_on_exact_end"),
            "firm_years_in_window": bl.get("firm_years_in_2010_2024_window"),
            "firm_years_main_sample": int(len(p)),
            "firms_main_sample": int(p["cik"].nunique()),
            "annual_filings_cached": bl.get("n_annual_filings_cached"),
        }
    val_path = OUT / "validation.json"
    if val_path.exists():
        results["validation"] = json.loads(val_path.read_text())

    # headline table for the README
    write_summary_table(results)

    with open(OUT / "results.json", "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    print(f"wrote {OUT / 'results.json'}")
    return results


def write_summary_table(res: dict) -> None:
    rows = []
    for row in res["robustness_ccc_roa"]:
        rows.append(row)
    pd.DataFrame(rows).to_csv(TABLES / "table_ccc_roa_robustness.csv", index=False)

    rows = [{
        "metric": "rho (CCC AR1)",
        "value": res["persistence"]["beta"],
        "se": res["persistence"]["se"],
        "half_life_years": res["persistence"]["half_life_years"],
        "n": res["persistence"]["n"],
    }]
    for spec in res["robustness_persistence"]:
        rows.append({"metric": spec["spec"], "value": spec["rho"], "se": spec["se"],
                     "half_life_years": spec["half_life_years"], "n": spec["n"]})
    pd.DataFrame(rows).to_csv(TABLES / "table_persistence.csv", index=False)


if __name__ == "__main__":
    main()
