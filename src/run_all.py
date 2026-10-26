"""
One command rebuilds the project from cached raw data:

    python src/run_all.py                # download (cached) -> panels -> analysis -> figures
    python src/run_all.py --skip-download
    python src/run_all.py --test         # ... and run the test suite

The download step is idempotent: a quarter already cached in data/raw/fsds (annual
10-K/20-F facts) or data/raw/fsds_q (10-Q facts for the 2019-2022 shock panel) is
not fetched again, so the pipeline runs fully offline.
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))

import analysis  # noqa: E402
import analysis_quarterly  # noqa: E402
import build_panel  # noqa: E402
import build_quarterly  # noqa: E402
import download_sec  # noqa: E402
import figures  # noqa: E402
from json_utils import write_json  # noqa: E402

LOG = ROOT / "outputs" / "run_log.json"


def step(name: str, fn, log: list) -> None:
    t0 = time.time()
    print(f"\n=== {name} ===", flush=True)
    status, err = "ok", None
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        status, err = "failed", f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
        raise
    finally:
        log.append({"step": name, "status": status, "seconds": round(time.time() - t0, 1),
                    "error": err})
        print(f"--- {name}: {status} ({time.time() - t0:.1f}s)", flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-download", action="store_true")
    ap.add_argument("--skip-validation", action="store_true")
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args(argv)

    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    log: list[dict] = []
    t0 = time.time()

    if not args.skip_download:
        step("download_sec", lambda: download_sec.main([]), log)
        step("download_sec_quarterly", lambda: download_sec.main(["--quarterly"]), log)
    step("build_panel", build_panel.build_panel, log)
    step("build_quarterly", build_quarterly.build, log)
    step("analysis_quarterly", analysis_quarterly.main, log)
    if not args.skip_validation:
        try:
            step("verify_known_firms", __import__("verify_known_firms").main, log)
        except Exception:  # noqa: BLE001 - network-dependent, never fatal
            print("validation skipped (offline?)", flush=True)
    step("analysis", analysis.main, log)
    step("figures", figures.main, log)
    if args.test:
        import subprocess
        step("pytest", lambda: subprocess.run(
            [sys.executable, "-m", "pytest", "-q", str(ROOT / "tests")], check=True), log)

    LOG.parent.mkdir(parents=True, exist_ok=True)
    payload = {"started_utc": started,
               "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "total_seconds": round(time.time() - t0, 1),
               "steps": log}
    write_json(LOG, payload)
    print(f"\nTotal: {time.time() - t0:.1f}s -> {LOG.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
