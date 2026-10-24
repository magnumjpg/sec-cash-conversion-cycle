"""
XBRL tag mapping (versioned).

Every concept is resolved through an *ordered* fallback list; the first tag
with a usable value for a given firm-year wins, and the tag actually used is
counted and reported in outputs/tables/tag_usage.csv.

Column `tier` tells where a tag comes from:
  "charter"  -> listed in the project charter (00_charters/02_working_capital_sec.md)
  "extra"    -> not in the charter; added as a last-resort fallback, documented in
                DECISIONS.md (D-05).  Never preferred over a charter tag.

Mapping version: 1.0.0  (2026-10)
"""

from __future__ import annotations

MAPPING_VERSION = "1.0.0"

# concept -> list of (tag, tier)
TAG_MAP: dict[str, list[tuple[str, str]]] = {
    "revenue": [
        ("RevenueFromContractWithCustomerExcludingAssessedTax", "charter"),
        ("RevenueFromContractWithCustomerIncludingAssessedTax", "charter"),
        ("SalesRevenueNet", "charter"),
        ("Revenues", "charter"),
        ("SalesRevenueGoodsNet", "extra"),
    ],
    "cogs": [
        ("CostOfGoodsAndServicesSold", "charter"),
        ("CostOfRevenue", "charter"),
        ("CostOfGoodsSold", "charter"),
    ],
    "ar": [
        ("AccountsReceivableNetCurrent", "charter"),
        ("AccountsReceivableGrossCurrent", "charter"),
        ("ReceivablesNetCurrent", "charter"),
    ],
    "inventory": [
        ("InventoryNet", "charter"),
        ("InventoryFinishedGoodsNetOfReserves", "charter"),
        ("InventoryGross", "charter"),
    ],
    "ap": [
        ("AccountsPayableCurrent", "charter"),
        ("AccountsPayableAndAccruedLiabilitiesCurrent", "charter"),
    ],
    "op_income": [
        ("OperatingIncomeLoss", "charter"),
    ],
    "net_income": [
        ("NetIncomeLoss", "charter"),
        # `ProfitLoss` is the consolidated bottom line including NCI; only used
        # when NetIncomeLoss is absent (foreign filers on 20-F, mostly).
        ("ProfitLoss", "extra"),
    ],
    "assets": [
        ("Assets", "charter"),
    ],
    "assets_current": [
        ("AssetsCurrent", "charter"),
    ],
    "liabilities_current": [
        ("LiabilitiesCurrent", "charter"),
    ],
    "cash": [
        ("CashAndCashEquivalentsAtCarryingValue", "charter"),
        # Post-2018 cash-flow-statement tag; same point-in-time concept.
        ("CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents", "extra"),
    ],
    "equity": [
        ("StockholdersEquity", "charter"),
        ("StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest", "extra"),
    ],
}

# Balance-sheet (point-in-time, qtrs == 0) vs income-statement (duration, qtrs == 4).
INSTANT_CONCEPTS = ["ar", "inventory", "ap", "assets", "assets_current",
                    "liabilities_current", "cash", "equity"]
FLOW_CONCEPTS = ["revenue", "cogs", "op_income", "net_income"]

# Used by download_sec.py to slice num.txt before caching.
TAG_UNIVERSE: set[str] = {tag for tags in TAG_MAP.values() for tag, _ in tags}

# Rank used for the deterministic "first non-null fallback wins" rule.
TAG_RANK: dict[str, int] = {
    tag: rank for tags in TAG_MAP.values() for rank, (tag, _) in enumerate(tags)
}
CONCEPT_OF_TAG: dict[str, str] = {
    tag: concept for concept, tags in TAG_MAP.items() for tag, _ in tags
}
TIER_OF_TAG: dict[str, str] = {
    tag: tier for tags in TAG_MAP.values() for tag, tier in tags
}
PREFERRED_TAG: dict[str, str] = {c: tags[0][0] for c, tags in TAG_MAP.items()}

FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}

# 2-digit SIC -> short label (SIC divisions; used only for display/grouping).
SIC_DIVISIONS: dict[str, str] = {
    "01": "Agriculture", "02": "Agriculture", "07": "Agriculture", "08": "Agriculture", "09": "Agriculture",
    "10": "Mining & energy", "12": "Mining & energy", "13": "Mining & energy", "14": "Mining & energy",
    "15": "Construction", "16": "Construction", "17": "Construction",
    "20": "Food & tobacco", "21": "Food & tobacco", "22": "Textiles", "23": "Apparel",
    "24": "Wood & furniture", "25": "Wood & furniture", "26": "Paper", "27": "Printing & publishing",
    "28": "Chemicals & pharma", "29": "Petroleum refining", "30": "Rubber & plastics",
    "31": "Leather", "32": "Stone, clay & glass", "33": "Primary metals",
    "34": "Fabricated metal", "35": "Machinery & computers", "36": "Electronics",
    "37": "Transport equipment", "38": "Instruments", "39": "Misc. manufacturing",
    "40": "Railroads", "41": "Transport", "42": "Trucking & logistics", "43": "Postal",
    "44": "Water transport", "45": "Air transport", "46": "Pipelines", "47": "Transport services",
    "48": "Communications", "49": "Utilities",
    "50": "Wholesale durables", "51": "Wholesale non-durables",
    "52": "Building materials retail", "53": "General merchandise retail", "54": "Food retail",
    "55": "Auto & fuel retail", "56": "Apparel retail", "57": "Home furnishings retail",
    "58": "Restaurants", "59": "Specialty retail",
    "60": "Banks", "61": "Credit institutions", "62": "Securities", "63": "Insurance",
    "64": "Insurance agents", "65": "Real estate", "67": "Holding & investment",
    "70": "Hotels", "72": "Personal services", "73": "Business services",
    "75": "Auto services", "76": "Misc. repair", "78": "Motion pictures", "79": "Entertainment",
    "80": "Health services", "81": "Legal services", "82": "Education",
    "83": "Social services", "86": "Membership orgs", "87": "Engineering services",
    "89": "Misc. services", "91": "Public administration", "99": "Conglomerate",
}


def sic2(cik_sic) -> str | None:
    """First two digits of a 4-digit SIC code, zero padded (e.g. 7372 -> '73')."""
    try:
        s = int(cik_sic)
    except (TypeError, ValueError):
        return None
    if s <= 0:
        return None
    return f"{s // 100:02d}"


def sic_division(cik_sic) -> str:
    s2 = sic2(cik_sic)
    if s2 is None:
        return "Unknown"
    return SIC_DIVISIONS.get(s2, f"SIC {s2}")
