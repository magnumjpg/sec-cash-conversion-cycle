"""
Internal spot check of the panel against SEC `companyfacts`.

For 3 well-known issuers we pull companyfacts, locate the exact tag + fiscal
year end that the panel used, and compare values. This validates that the
extractor parses and period-aligns the facts it selected; it does not validate
the tag choice, the fallback order or coverage of the wider panel.

    python src/verify_known_firms.py

Writes outputs/tables/known_firm_check.csv and outputs/validation.json.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
CF_DIR = ROOT / "data" / "raw" / "companyfacts"
PROC = ROOT / "data" / "processed"
OUT = ROOT / "outputs"
TABLES = OUT / "tables"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from json_utils import write_json  # noqa: E402
from tags import TAG_MAP  # noqa: E402

UA = {"User-Agent": f"portfolio-research/1.0 ({os.environ.get('SEC_CONTACT', 'portfolio-research@example.com')})"}

# Fastenal (industrial distributor), Walmart (retail), Apple (hardware).
FIRMS = {815556: "Fastenal", 104169: "Walmart", 320193: "Apple"}
CONCEPTS = ["revenue", "cogs", "ar", "inventory", "ap", "assets", "net_income"]
YEARS = [2019, 2022, 2023]


def fetch_facts(cik: int) -> dict:
    CF_DIR.mkdir(parents=True, exist_ok=True)
    p = CF_DIR / f"CIK{cik:010d}.json"
    if not p.exists():
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
        r = requests.get(url, headers=UA, timeout=120)
        r.raise_for_status()
        p.write_bytes(r.content)
    return json.loads(p.read_text())


def facts_for(facts: dict, tag: str, end: str, annual: bool,
              tolerance_days: int = 7) -> float | None:
    """Value for `tag` at the annual/instant period close to `end`.

    The panel stores the FSDS `ddate`, which is a month-end convention, while
    `companyfacts` carries the issuer's exact period end (Apple's FY2019 10-K
    closes on 2019-09-28, not 2019-09-30). A ±7-day window matches the same
    period without allowing two fiscal years to compete.
    """
    node = facts.get("facts", {}).get("us-gaap", {}).get(tag)
    if not node:
        return None
    target = pd.Timestamp(end)
    candidates: list[tuple[int, str, str, float]] = []
    for unit, items in node.get("units", {}).items():
        if unit != "USD":
            continue
        for it in items:
            try:
                gap = abs((pd.Timestamp(it.get("end")) - target).days)
            except (TypeError, ValueError):
                continue
            if gap > tolerance_days:
                continue
            if it.get("form") not in ("10-K", "10-K/A", "20-F", "40-F"):
                continue
            if annual:
                if "start" not in it:
                    continue
                d0 = pd.Timestamp(it["start"])
                d1 = pd.Timestamp(it["end"])
                if not 350 <= (d1 - d0).days <= 380:
                    continue
            else:
                if "start" in it:
                    continue
            candidates.append((gap, it.get("filed", ""), it.get("accn", ""),
                               float(it["val"])))
    if not candidates:
        return None
    # closest period end; for the same end keep the latest filing
    closest = min(c[0] for c in candidates)
    latest = max(c[1:] for c in candidates if c[0] == closest)
    return latest[2]


def main() -> dict:
    panel = pd.read_parquet(PROC / "panel.parquet")
    rows = []
    for cik, label in FIRMS.items():
        sub = panel[panel["cik"] == cik]
        if sub.empty:
            rows.append({"cik": cik, "firm": label, "concept": "ALL", "year": None,
                         "panel_value": None, "companyfacts_value": None,
                         "match": False, "note": "firm not in panel"})
            continue
        try:
            facts = fetch_facts(cik)
        except Exception as exc:  # noqa: BLE001
            rows.append({"cik": cik, "firm": label, "concept": "ALL", "year": None,
                         "panel_value": None, "companyfacts_value": None,
                         "match": None, "note": f"companyfacts unavailable: {exc}"})
            continue
        for year in YEARS:
            fy = sub[sub["fiscal_year"] == year]
            if fy.empty:
                continue
            r = fy.iloc[0]
            end = pd.Timestamp(r["fiscal_year_end"]).strftime("%Y-%m-%d")
            for concept in CONCEPTS:
                tag = r.get(f"tag_{concept}")
                annual = concept in ("revenue", "cogs", "net_income")
                if not isinstance(tag, str) or not tag:
                    tag = None
                    for cand, _ in TAG_MAP[concept]:
                        if facts_for(facts, cand, end, annual) is not None:
                            tag = cand
                            break
                pv = r.get(concept)
                if tag is None:
                    rows.append({"cik": cik, "firm": label, "concept": concept,
                                 "year": year, "tag": None, "fiscal_year_end": end,
                                 "panel_value": None if pd.isna(pv) else float(pv),
                                 "companyfacts_value": None, "match": False,
                                 "rel_diff": None,
                                 "note": "no matching tag in companyfacts within 7 days"})
                    continue
                cf = facts_for(facts, tag, end, annual)
                ok = (cf is not None and pd.notna(pv)
                      and abs(float(pv) - cf) <= max(1.0, 0.002 * abs(cf)))
                rows.append({"cik": cik, "firm": label, "concept": concept, "year": year,
                             "tag": tag, "fiscal_year_end": end,
                             "panel_value": None if pd.isna(pv) else float(pv),
                             "companyfacts_value": cf, "match": bool(ok),
                             "rel_diff": None if (cf in (None, 0) or pd.isna(pv))
                             else round(float(pv) / cf - 1, 6)})

    df = pd.DataFrame(rows)
    TABLES.mkdir(parents=True, exist_ok=True)
    df.to_csv(TABLES / "known_firm_check.csv", index=False)
    # The denominator is every comparison the design sets out to make, not only
    # the ones that happened to return a value.
    attempted = df[df["year"].notna()].copy()
    summary = {
        "firms": list(FIRMS.values()),
        "concepts": CONCEPTS,
        "years": YEARS,
        "n_comparisons": int(len(attempted)),
        "n_match": int(attempted["match"].fillna(False).sum()),
        "all_match": bool(len(attempted) > 0 and attempted["match"].fillna(False).all()),
        "n_unavailable": int(attempted["companyfacts_value"].isna().sum()),
        "max_abs_rel_diff": (float(attempted["rel_diff"].abs().max())
                             if attempted["rel_diff"].notna().any() else None),
        "note": ("internal spot check: panel value vs latest 10-K fact within 7 days "
                 "of the panel fiscal-year end (companyfacts API). It validates "
                 "parsing and period alignment for these three issuers, not the tag "
                 "choice, the fallback order or coverage of the wider panel; "
                 "unavailable comparisons stay in the denominator"),
    }
    write_json(OUT / "validation.json", summary)
    print(json.dumps(summary, indent=2))
    print(attempted[["firm", "concept", "year", "panel_value", "companyfacts_value", "match"]]
          .to_string(index=False))
    return summary


if __name__ == "__main__":
    main()
