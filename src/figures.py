"""
Figures. Every annotation is read from outputs/results.json (no hand-typed
numbers) so that a figure can never disagree with the pipeline.

    python src/figures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT = ROOT / "outputs"
FIGS = OUT / "figures"
TABLES = OUT / "tables"

sys.path.insert(0, str(ROOT / "src"))
from analysis import add_winsorized, plausibility_screen, winsorize  # noqa: E402
from tags import sic_division  # noqa: E402

plt.rcParams.update({
    "figure.dpi": 140, "savefig.dpi": 140, "font.size": 9,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.6,
    "figure.facecolor": "white", "axes.facecolor": "white",
})
C_MAIN = "#1f4e79"
C_ACC = "#c0504d"
C_GREY = "#7f7f7f"


def twoway_demean(df: pd.DataFrame, cols: list[str], iters: int = 30) -> pd.DataFrame:
    """Alternating projections on firm and year means (balanced-ish panels)."""
    out = df[cols].astype(float).copy()
    for _ in range(iters):
        out = out - out.groupby(df["cik"]).transform("mean")
        out = out - out.groupby(df["fiscal_year"]).transform("mean")
    return out


def fig_industry(ind: pd.DataFrame, res: dict) -> Path:
    d = ind[ind["firm_years"] >= 150].sort_values("ccc_median").copy()
    fig, ax = plt.subplots(figsize=(7.6, max(4.2, 0.26 * len(d) + 1.2)))
    y = np.arange(len(d))
    colors = [C_ACC if m < 0 else C_MAIN for m in d["ccc_median"]]
    ax.barh(y, d["ccc_median"], color=colors, height=0.68, alpha=0.9)
    ax.errorbar(d["ccc_median"], y,
                xerr=[d["ccc_median"] - d["ccc_q25"], d["ccc_q75"] - d["ccc_median"]],
                fmt="none", ecolor="#333333", elinewidth=1.0, capsize=0)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{int(r.sic2)}  {r.industry}  ({int(r.firm_years):,})"
                        for r in d.itertuples()])
    ax.axvline(0, color="black", lw=0.8)
    ax.axvline(res["panel"]["median_ccc"], color=C_GREY, ls="--", lw=1)
    ax.set_xlabel("Cash conversion cycle, days (bar = median, whiskers = IQR)")
    ax.set_title(f"CCC by 2-digit SIC, {res['panel']['year_min']}-{res['panel']['year_max']}\n"
                 f"dashed = sample median ({res['panel']['median_ccc']:.1f} days); "
                 f"industries with >=150 firm-years", fontsize=9.0, loc="left")
    fig.tight_layout()
    p = FIGS / "fig1_ccc_by_industry.png"
    fig.savefig(p)
    plt.close(fig)
    return p


def fig_persistence(p: pd.DataFrame, res: dict) -> Path:
    # same variables as the regression: screened sample, 1/99 winsorized CCC,
    # lag only when the previous fiscal year end is 350-380 days earlier
    d = p.dropna(subset=["ccc_clean_w", "ccc_clean_w_lag"]).copy()
    dd = d[d["ccc_clean_w"].between(-200, 400)
           & d["ccc_clean_w_lag"].between(-200, 400)]

    fig, ax = plt.subplots(figsize=(6.4, 5.0))
    ax.scatter(dd["ccc_clean_w_lag"], dd["ccc_clean_w"], s=4, alpha=0.10,
               color=C_MAIN, linewidths=0)
    bins = pd.qcut(dd["ccc_clean_w_lag"], 30, duplicates="drop")
    bm = dd.groupby(bins).agg(x=("ccc_clean_w_lag", "median"),
                              y=("ccc_clean_w", "median"))
    ax.plot(bm["x"], bm["y"], "o-", color=C_ACC, ms=3.5, lw=1.4, label="binned medians")
    xs = np.linspace(-100, 300, 50)
    rho = res["persistence"]["beta"]
    ax.plot(xs, rho * xs, color="black", lw=1.2, ls="--",
            label=f"AR(1) slope rho = {rho:.3f}")
    ax.axhline(0, color="black", lw=0.6); ax.axvline(0, color="black", lw=0.6)
    ax.set_xlim(-100, 300); ax.set_ylim(-100, 400)
    ax.set_xlabel("CCC in t-1 (days, winsorized 1/99 within industry-year)")
    ax.set_ylabel("CCC in t (days)")
    hl = res["persistence"]["half_life_years"]
    ax.set_title(f"Persistence of CCC: rho = {rho:.3f}, half-life = "
                 f"{hl:.2f} years\nSE clustered by firm; year FE; N = {res['persistence']['n']:,}",
                 fontsize=9.5, loc="left")
    ax.legend(frameon=False, loc="upper left", fontsize=8)
    fig.tight_layout()
    pth = FIGS / "fig2_persistence.png"
    fig.savefig(pth)
    plt.close(fig)
    return pth


def fig_ccc_roa(p: pd.DataFrame, res: dict) -> Path:
    d = p.dropna(subset=["ccc_clean_w", "roa_w", "log_assets", "gross_margin",
                         "capital_intensity_used_w", "asset_turnover_w"]).copy()
    dem = twoway_demean(d, ["ccc_clean_w", "roa_w"])
    d["ccc_dm"], d["roa_dm"] = dem["ccc_clean_w"], dem["roa_w"]
    d = d[d["roa_dm"].between(-0.5, 0.5)]
    xlo, xhi = d["ccc_dm"].quantile([0.01, 0.99])

    q = pd.qcut(d["ccc_dm"], 20, duplicates="drop")
    bm = d.groupby(q).agg(x=("ccc_dm", "median"), y=("roa_dm", "median"), n=("roa_dm", "size"))

    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    ax.scatter(d["ccc_dm"], d["roa_dm"], s=3, alpha=0.05, color=C_GREY, linewidths=0)
    ax.plot(bm["x"], bm["y"], "o-", color=C_MAIN, ms=4, lw=1.5, label="20-bin medians")
    beta = res["ccc_roa"]["beta"]
    xs = np.linspace(bm["x"].min(), bm["x"].max(), 20)
    ax.plot(xs, beta * xs, color=C_ACC, lw=1.4, ls="--", label=f"slope = {beta:.5f} ROA/day")
    ax.axhline(0, color="black", lw=0.6); ax.axvline(0, color="black", lw=0.6)
    ax.set_xlabel("CCC, days (firm and year FE removed; display 1st-99th pct)")
    ax.set_ylabel("ROA (firm and year FE removed)")
    ax.set_xlim(xlo, xhi)
    ax.set_title(f"CCC and ROA within firm-year: beta = {beta:.5f} "
                 f"({res['ccc_roa']['beta_standardized']:.3f} SD of ROA per SD of CCC)\n"
                 f"t = {res['ccc_roa']['t']:.1f}, N = {res['ccc_roa']['n']:,}, "
                 f"firms = {res['ccc_roa']['n_firms']:,}", fontsize=9.5, loc="left")
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    fig.tight_layout()
    pth = FIGS / "fig3_ccc_vs_roa.png"
    fig.savefig(pth)
    plt.close(fig)
    return pth


def fig_shock_2020(p: pd.DataFrame, res: dict) -> Path:
    d = p[p["fiscal_year"] == 2020].dropna(
        subset=["sales_growth", "ccc_clean_w_lag", "industry", "sic2", "sic"]).copy()
    # same left-hand side as the headline cross-section
    d["_y"] = winsorize(d["sales_growth"], [d["sic2"]], min_group=10**9)
    d["division"] = d["sic"].map(sic_division)
    fig, ax = plt.subplots(figsize=(7.0, 5.0))
    top = d["division"].value_counts().head(6).index.tolist()
    palette = ["#1f4e79", "#c0504d", "#4f81bd", "#9bbb59", "#8064a2", "#f79646"]
    for i, div in enumerate(top):
        sub = d[d["division"] == div]
        ax.scatter(sub["ccc_clean_w_lag"], sub["_y"], s=7, alpha=0.30,
                   color=palette[i], linewidths=0,
                   label=f"{div} ({len(sub)})")
    rest = d[~d["division"].isin(top)]
    ax.scatter(rest["ccc_clean_w_lag"], rest["_y"], s=5, alpha=0.12,
               color=C_GREY, linewidths=0, label=f"other ({len(rest)})")
    q = pd.qcut(d["ccc_clean_w_lag"], 10, duplicates="drop")
    bm = d.groupby(q).agg(x=("ccc_clean_w_lag", "median"), y=("_y", "median"))
    ax.plot(bm["x"], bm["y"], "o-", color=C_MAIN, ms=4.5, lw=1.5, label="decile medians")
    b = res["shock_2020"]["revenue_growth"]["beta"]
    xs = np.linspace(bm["x"].min(), bm["x"].max(), 30)
    ax.plot(xs, b * xs + d["_y"].median() - b * d["ccc_clean_w_lag"].median(),
            color=C_ACC, lw=1.3, ls="--", label=f"slope = {b:.5f} per day")
    ax.axhline(0, color="black", lw=0.6); ax.axvline(0, color="black", lw=0.6)
    ax.set_xlim(-100, 400)
    ax.set_ylim(-0.75, 1.0)
    ax.set_xlabel("CCC in 2019, days (winsorized 1/99 within industry-year)")
    ax.set_ylabel("Revenue growth 2019 -> 2020")
    t = res["shock_2020"]["revenue_growth"]["t"]
    ax.set_title(f"2020 demand shock vs pre-shock CCC: slope = {b:.5f}, t = {t:.1f}, "
                 f"N = {res['shock_2020']['revenue_growth']['n']:,}\n"
                 f"2-digit SIC FE, HC1 SE; cross-section, descriptive "
                 f"(axes truncated for display)", fontsize=9.5, loc="left")
    ax.legend(frameon=True, framealpha=0.9, fontsize=6.5, loc="lower right", ncol=2)
    fig.tight_layout()
    pth = FIGS / "fig4_shock_2020.png"
    fig.savefig(pth)
    plt.close(fig)
    return pth


def fig_time_series(yr: pd.DataFrame, res: dict) -> Path:
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    ax.plot(yr["fiscal_year"], yr["ccc_median"], "o-", color=C_MAIN, lw=1.6, ms=4,
            label="median CCC")
    ax.fill_between(yr["fiscal_year"], yr["ccc_q25"], yr["ccc_q75"], color=C_MAIN, alpha=0.12,
                    label="IQR")
    ax.set_xlabel("Fiscal year")
    ax.set_ylabel("CCC, days")
    ax2 = ax.twinx()
    ax2.plot(yr["fiscal_year"], 100 * yr["neg_ccc_share"], "s--", color=C_ACC, lw=1.2, ms=3,
             label="share with CCC < 0 (right)")
    ax2.set_ylabel("Share of firms with negative CCC, %")
    ax2.set_ylim(0, max(20, 100 * yr["neg_ccc_share"].max() * 1.15))
    ax2.grid(False)
    ax2.spines["right"].set_visible(True)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=8, loc="upper left")
    ax.set_title(f"Median CCC and share of negative-CCC firms, "
                 f"{res['panel']['year_min']}-{res['panel']['year_max']} "
                 f"({res['panel']['firms']:,} firms)", fontsize=9.5, loc="left")
    fig.tight_layout()
    pth = FIGS / "fig5_ccc_time_series.png"
    fig.savefig(pth)
    plt.close(fig)
    return pth


def fig_shock_2022(res: dict) -> Path:
    q = pd.DataFrame(res["shock_2022"]["margin_change"]["quintiles"])
    fig, ax = plt.subplots(figsize=(6.0, 4.0))
    x = np.arange(len(q))
    ax.bar(x, q["y_median"] * 100, color=[C_ACC if v < 0 else C_MAIN for v in q["y_median"]])
    ax.set_xticks(x)
    ax.set_xticklabels([f"Q{int(i) + 1}\n{q['x_median'].iloc[i]:.0f}d" for i in x], fontsize=8)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xlabel("Quintile of CCC in 2021 (median days below)")
    ax.set_ylabel("Median gross-margin change 2021->2022, pp")
    b = res["shock_2022"]["margin_change"]["beta"]
    t = res["shock_2022"]["margin_change"]["t"]
    ax.set_title(f"2022 cost shock: margin change by pre-shock CCC\n"
                 f"slope = {100 * b:.3f} pp/day, t = {t:.1f}, N = "
                 f"{res['shock_2022']['margin_change']['n']:,} firm-years", fontsize=9.5, loc="left")
    fig.tight_layout()
    pth = FIGS / "fig6_shock_2022.png"
    fig.savefig(pth)
    plt.close(fig)
    return pth


def fig_quarterly_shock(res: dict) -> Path:
    """Coefficient on pre-shock CCC, one point per (shock year, fiscal quarter)."""
    q = res.get("shock_quarterly", {})
    rows = q.get("by_quarter", []) if q.get("available") else []
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    if rows:
        d = pd.DataFrame(rows)
        d = d[d["beta"].notna() & d["se"].notna()].copy()
        keys = sorted(d[["shock_year", "quarter"]].drop_duplicates()
                      .itertuples(index=False, name=None))
        if not keys:
            raise ValueError("quarterly results contain no estimable coefficient")
        pos = {k: i for i, k in enumerate(keys)}
        series = [
            ("sales_growth", C_MAIN, "o", "revenue growth, YoY", -0.12),
            ("gross_margin_change", C_ACC, "s", "gross-margin change, YoY", 0.12),
        ]
        for outcome, color, marker, label, shift in series:
            sub = d[d["outcome"] == outcome]
            if sub.empty:
                continue
            x = [pos[(row.shock_year, row.quarter)] + shift for row in sub.itertuples()]
            ax.errorbar(x, sub["beta"], yerr=1.96 * sub["se"], fmt=marker,
                        color=color, capsize=2, ms=4.5, lw=1.2, label=label)
        ax.set_xticks(range(len(keys)))
        ax.set_xticklabels([qtr for _, qtr in keys], rotation=30, fontsize=8, ha="right")
        ax.axhline(0, color="black", lw=0.8)
        ax.set_ylabel("Coefficient per pre-shock CCC day")
        ax.set_title("Quarterly 10-Q shock panel (95% CI; industry + quarter FE,\n"
                     "SE clustered by firm; exposure = clean annual CCC of the prior FY)",
                     fontsize=9.5, loc="left")
        ax.legend(frameon=False, fontsize=8)
    else:
        ax.text(0.5, 0.5, "Quarterly cache not available",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
    fig.tight_layout()
    pth = FIGS / "fig7_quarterly_shock.png"
    fig.savefig(pth)
    plt.close(fig)
    return pth


def main() -> None:
    FIGS.mkdir(parents=True, exist_ok=True)
    res = json.loads((OUT / "results.json").read_text())
    p_raw = pd.read_parquet(PROC / "panel.parquet")
    p_clean = p_raw[p_raw["ccc_clean"].notna()].copy()
    p_est, _ = plausibility_screen(p_clean, "ccc_clean")
    p_est = add_winsorized(p_est)
    ind = pd.read_csv(TABLES / "industry_summary.csv")
    yr = pd.read_csv(TABLES / "year_summary.csv")

    made = [
        fig_industry(ind, res),
        fig_persistence(p_est, res),
        fig_ccc_roa(p_est, res),
        fig_shock_2020(p_est, res),
        fig_time_series(yr, res),
        fig_shock_2022(res),
        fig_quarterly_shock(res),
    ]
    for m in made:
        print(f"wrote {m.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
