"""
Download and cache SEC XBRL data for the working-capital project.

Source choice (see DECISIONS.md, D-01): the SEC "Financial Statement Data Sets"
(FSDS), the official bulk extract of the same XBRL facts served by
`data.sec.gov/api/xbrl/companyfacts`.  FSDS is used instead of the Frames API
because Frames do not expose `form`, `fp`, `filed` or `sic`, which the charter
requires in order to (a) keep 10-K/20-F filings only and (b) let the latest
filing win.  FSDS carries exactly those fields, plus SIC, and covers delisted
filers (no survivorship filter).

Everything is cached under data/raw/ so that `python src/run_all.py` can rebuild
the whole project without network access.

Usage
-----
    python src/download_sec.py                # all quarters + ticker lists
    python src/download_sec.py --force        # re-download everything
    python src/download_sec.py --quarters 2020q1 2020q2
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
FSDS_DIR = RAW / "fsds"
ZIP_DIR = RAW / "zips"
MANIFEST = ROOT / "data" / "manifest.json"

USER_AGENT = "Jaime Perez portfolio research magnum.jpg@gmail.com"
HEADERS = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}

FSDS_URL = "https://www.sec.gov/files/dera/data/financial-statement-data-sets/{q}.zip"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
TICKERS_EXCH_URL = "https://www.sec.gov/files/company_tickers_exchange.json"

# Politeness: <= 4 requests/second (charter asks for <= 5/s).
MIN_INTERVAL = 0.25
MAX_RETRIES = 6

# 2010q1..2025q4: covers every 10-K/20-F filed from Jan-2010 to Dec-2025, i.e.
# fiscal years 2009-2024 (FY2009 is needed as the lag for 2010).
QUARTERS = [f"{y}q{q}" for y in range(2010, 2026) for q in range(1, 5)]

# Only tags used downstream are cached; keeps each quarter's cache to a few MB.
from tags import TAG_UNIVERSE  # noqa: E402  (same directory when run as a script)

FORM_KEEP = ["10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"]

SUB_COLS = ["adsh", "cik", "name", "sic", "form", "period", "fy", "fp", "filed", "fye"]
NUM_COLS = ["adsh", "tag", "version", "ddate", "qtrs", "uom", "segments", "coreg", "value"]

_last_request = 0.0


def _throttle() -> None:
    global _last_request
    wait = MIN_INTERVAL - (time.time() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.time()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_manifest() -> dict:
    if MANIFEST.exists():
        with open(MANIFEST, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return {"generated_at_utc": None, "user_agent": USER_AGENT, "files": []}


def _save_manifest(man: dict) -> None:
    man["generated_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(man, fh, indent=2, sort_keys=False)
    os.replace(tmp, MANIFEST)


def _record(man: dict, url: str, path: Path, note: str = "", source_bytes: int | None = None) -> None:
    entry = {
        "url": url,
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": note,
    }
    if source_bytes is not None:
        entry["source_bytes"] = source_bytes
    man["files"] = [f for f in man["files"] if f["path"] != entry["path"]]
    man["files"].append(entry)
    man["files"].sort(key=lambda f: f["path"])


def fetch(url: str, dest: Path, man: dict, force: bool = False, note: str = "") -> Path:
    """Download `url` to `dest` with retries and exponential backoff."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        return dest
    for attempt in range(MAX_RETRIES):
        try:
            _throttle()
            r = requests.get(url, headers=HEADERS, timeout=180, stream=True)
            if r.status_code == 200:
                tmp = dest.with_suffix(dest.suffix + ".part")
                with open(tmp, "wb") as fh:
                    for chunk in r.iter_content(1 << 20):
                        fh.write(chunk)
                os.replace(tmp, dest)
                _record(man, url, dest, note=note, source_bytes=dest.stat().st_size)
                _save_manifest(man)
                return dest
            if r.status_code == 404:
                raise FileNotFoundError(f"404 {url}")
            raise IOError(f"HTTP {r.status_code} for {url}")
        except FileNotFoundError:
            raise
        except Exception as exc:  # noqa: BLE001 - retry anything transient
            backoff = (2 ** attempt) + random.uniform(0, 1)
            print(f"  ! {exc} -> retry {attempt + 1}/{MAX_RETRIES} in {backoff:.1f}s", flush=True)
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(backoff)
    raise RuntimeError("unreachable")


def download_tickers(man: dict, force: bool = False) -> None:
    """Universe listings (used only as a ticker/exchange lookup for readability)."""
    for url, name in [(TICKERS_URL, "company_tickers.json"),
                      (TICKERS_EXCH_URL, "company_tickers_exchange.json")]:
        dest = RAW / name
        if dest.exists() and not force:
            continue
        try:
            fetch(url, dest, man, force=force, note="SEC company ticker listing")
        except Exception as exc:  # noqa: BLE001
            print(f"  ! ticker list failed ({name}): {exc}", flush=True)

    # Normalised ticker table: cik -> ticker/exchange (optional join).
    out = RAW / "tickers.parquet"
    try:
        with open(RAW / "company_tickers_exchange.json", "r", encoding="utf-8") as fh:
            js = json.load(fh)
        tk = pd.DataFrame(js["data"], columns=js["fields"])
        tk["cik"] = tk["cik"].astype("int64")
        tk = tk.drop_duplicates("cik")
        tk.to_parquet(out, index=False)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! ticker normalisation skipped: {exc}", flush=True)


def _parse_quarter(zip_path: Path, quarter: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Read sub.txt / num.txt from an FSDS zip and keep only what we need."""
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        if "sub.txt" not in names or "num.txt" not in names:
            raise ValueError(f"{quarter}: unexpected zip layout {sorted(names)}")
        sub = pd.read_csv(zf.open("sub.txt"), sep="\t", dtype=str, na_values=[""])
        form_counts = sub["form"].value_counts().rename_axis("form").reset_index(name="filings")
        form_counts["quarter"] = quarter
        sub = sub[[c for c in SUB_COLS if c in sub.columns]].copy()

        sub = sub[sub["form"].isin(FORM_KEEP)].copy()
        sub["cik"] = pd.to_numeric(sub["cik"], errors="coerce").astype("Int64")

        keep_adsh = set(sub["adsh"])
        chunks = []
        reader = pd.read_csv(
            zf.open("num.txt"), sep="\t", dtype=str, na_values=[""],
            usecols=NUM_COLS, chunksize=500_000,
        )
        for chunk in reader:
            chunk = chunk[chunk["tag"].isin(TAG_UNIVERSE)]
            if chunk.empty:
                continue
            chunk = chunk[chunk["adsh"].isin(keep_adsh)]
            if chunk.empty:
                continue
            # Consolidated totals only: drop segment/co-registrant breakdowns.
            chunk = chunk[chunk["segments"].isna() & chunk["coreg"].isna()]
            chunk = chunk[chunk["qtrs"].isin(["0", "4"])]
            if chunk.empty:
                continue
            chunks.append(chunk)
        num = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame(columns=NUM_COLS)
        num["qtrs"] = pd.to_numeric(num["qtrs"], errors="coerce").astype("Int64")
        num["value"] = pd.to_numeric(num["value"], errors="coerce")
        num["ddate"] = pd.to_numeric(num["ddate"], errors="coerce").astype("Int64")

    return sub, num, form_counts


def download_quarter(quarter: str, man: dict, force: bool = False) -> dict:
    out_sub = FSDS_DIR / f"{quarter}_sub.parquet"
    out_num = FSDS_DIR / f"{quarter}_num.parquet"
    out_forms = FSDS_DIR / f"{quarter}_forms.parquet"
    if out_sub.exists() and out_num.exists() and out_forms.exists() and not force:
        return {"quarter": quarter, "status": "cached"}

    url = FSDS_URL.format(q=quarter)
    zip_path = ZIP_DIR / f"{quarter}.zip"
    fetch(url, zip_path, man, force=force, note=f"SEC FSDS {quarter}")
    src_bytes = zip_path.stat().st_size
    sub, num, form_counts = _parse_quarter(zip_path, quarter)

    FSDS_DIR.mkdir(parents=True, exist_ok=True)
    sub.to_parquet(out_sub, index=False)
    num.to_parquet(out_num, index=False)
    form_counts.to_parquet(out_forms, index=False)

    # The raw zip is ~100 MB per quarter. We keep the *derived* extract in
    # data/raw/ (hash recorded) and drop the zip to keep the cache ~1 GB.
    if not os.environ.get("KEEP_SEC_ZIPS"):
        zip_path.unlink(missing_ok=True)

    note = f"derived from {url} ({src_bytes} bytes); sub/num filtered to annual forms + project tags"
    for p in (out_sub, out_num, out_forms):
        _record(man, url, p, note=note, source_bytes=src_bytes)
    _save_manifest(man)
    return {"quarter": quarter, "status": "downloaded", "src_bytes": src_bytes,
            "sub_rows": int(len(sub)), "num_rows": int(len(num))}


def build_manifest_from_cache() -> dict:
    """Rebuild data/manifest.json from whatever is cached (offline safety net)."""
    man = _load_manifest()
    for p in sorted(FSDS_DIR.glob("*.parquet")):
        entry = {
            "url": FSDS_URL.format(q=p.name.split("_")[0]),
            "path": str(p.relative_to(ROOT)).replace("\\", "/"),
            "bytes": p.stat().st_size,
            "sha256": _sha256(p),
            "fetched_at_utc": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc)
            .isoformat(timespec="seconds"),
            "note": "reconstructed from local cache",
        }
        man["files"] = [f for f in man["files"] if f["path"] != entry["path"]]
        man["files"].append(entry)
    man["files"].sort(key=lambda f: f["path"])
    man = finalize_manifest(man)
    _save_manifest(man)
    return man


def finalize_manifest(man: dict) -> dict:
    """Mark which entries are still on disk (source zips are deleted after extraction)."""
    for f in man["files"]:
        p = ROOT / f["path"]
        f["retained"] = p.exists()
        if not p.exists() and f["path"].endswith(".zip"):
            f["note"] = (f.get("note", "") +
                         "; source zip deleted after extraction, sha256 kept for provenance").strip("; ")
    return man


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Download & cache SEC XBRL data")
    ap.add_argument("--quarters", nargs="*", default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--offline", action="store_true", help="rebuild manifest from cache only")
    args = ap.parse_args(argv)

    RAW.mkdir(parents=True, exist_ok=True)
    FSDS_DIR.mkdir(parents=True, exist_ok=True)
    man = _load_manifest()

    if args.offline:
        build_manifest_from_cache()
        print(f"manifest rebuilt from cache: {MANIFEST}")
        return 0

    download_tickers(man, force=args.force)

    quarters = args.quarters or QUARTERS
    t0 = time.time()
    done = failed = 0
    for i, q in enumerate(quarters, 1):
        try:
            res = download_quarter(q, man, force=args.force)
            done += 1
            extra = ""
            if res["status"] == "downloaded":
                extra = f" src={res['src_bytes'] / 1e6:.0f}MB rows={res['num_rows']:,}"
            print(f"[{i:>2}/{len(quarters)}] {q}: {res['status']}{extra} "
                  f"({time.time() - t0:.0f}s)", flush=True)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"[{i:>2}/{len(quarters)}] {q}: FAILED {exc}", flush=True)

    print(f"\ndone={done} failed={failed} elapsed={time.time() - t0:.0f}s -> {MANIFEST}")
    _save_manifest(finalize_manifest(man))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())
