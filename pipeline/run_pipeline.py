"""
Master pipeline script — runs all data fetchers then processes output.

Usage:
    conda activate research
    python pipeline/run_pipeline.py

    # Use a specific data vintage (ACS year, PEP vintage, QWI end year):
    python pipeline/run_pipeline.py --vintage 2024

    # Skip specific stages (e.g. if GA DPH files not yet downloaded):
    python pipeline/run_pipeline.py --vintage 2024 --skip ga_dph

    # Run only the processing step (re-use cached fetched data):
    python pipeline/run_pipeline.py --only process
"""

import argparse
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


STAGES = [
    ("population",  "fetch_population",  "fetch_population"),
    ("acs",         "fetch_acs",         "fetch_acs"),
    ("employment",  "fetch_employment",  "fetch_employment"),
    ("qcew",        "fetch_qcew",        "fetch_qcew"),
    ("bea_gdp",     "fetch_bea_gdp",     "fetch_bea_gdp"),
    ("hud_permits", "fetch_hud_permits", "fetch_hud_permits"),
    ("gosa",        "fetch_gosa",        "fetch_gosa"),
    ("oasis",        "fetch_oasis",       "fetch_oasis"),
    ("ga_dph",      "fetch_ga_dph",      "fetch_ga_dph"),
    ("forecast",    "fetch_forecast",    "fetch_forecast"),
    ("process",     "process",           "process_all"),
]


def run_stage(label: str, module_name: str, func_name: str) -> bool:
    """Import and run a single pipeline stage. Returns True on success."""
    print(f"\n{'='*60}")
    print(f"  STAGE: {label.upper()}")
    print(f"{'='*60}")
    t0 = time.time()
    try:
        mod = __import__(module_name)
        func = getattr(mod, func_name)
        func()
        elapsed = time.time() - t0
        print(f"  ✓ {label} completed in {elapsed:.1f}s")
        return True
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  ✗ {label} FAILED after {elapsed:.1f}s: {e}")
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="ARC 21-County Dashboard data pipeline")
    parser.add_argument(
        "--vintage", type=int, default=None,
        metavar="YEAR",
        help="Data vintage year (ACS, PEP, QWI end year). Default: current_year-1, "
             "with per-source fallback if that vintage isn't published yet."
    )
    parser.add_argument(
        "--skip", nargs="+", default=[],
        metavar="STAGE",
        help="Stage names to skip (e.g. --skip ga_dph gosa)"
    )
    parser.add_argument(
        "--only", nargs="+", default=[],
        metavar="STAGE",
        help="Run only these stages (e.g. --only process)"
    )
    args = parser.parse_args()

    # Set vintage env var BEFORE importing any pipeline modules so config.py
    # picks it up at import time (modules are imported lazily inside run_stage).
    if args.vintage is not None:
        os.environ["ARC_VINTAGE"] = str(args.vintage)
    vintage = int(os.environ.get("ARC_VINTAGE", str(datetime.now().year - 1)))

    skip_set = set(args.skip)
    only_set = set(args.only)

    print("\nARC 21-County Dashboard — Data Pipeline")
    print(f"Vintage: {vintage}")
    print(f"Stages: {[s[0] for s in STAGES]}")
    if skip_set:
        print(f"Skipping: {sorted(skip_set)}")
    if only_set:
        print(f"Running only: {sorted(only_set)}")

    results = {}
    total_start = time.time()

    for label, module, func in STAGES:
        if only_set and label not in only_set:
            print(f"\n  -- Skipping {label} (not in --only list)")
            continue
        if label in skip_set:
            print(f"\n  -- Skipping {label} (--skip)")
            continue
        results[label] = run_stage(label, module, func)

    # ── Summary ───────────────────────────────────────────────────────────────
    total_elapsed = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE  ({total_elapsed:.1f}s total)")
    print(f"{'='*60}")
    for label, ok in results.items():
        status = "✓" if ok else "✗ FAILED"
        print(f"  {status:12} {label}")

    failed = [k for k, v in results.items() if not v]
    if failed:
        print(f"\n  {len(failed)} stage(s) failed: {failed}")
        sys.exit(1)
    else:
        print("\n  All stages succeeded.")


if __name__ == "__main__":
    main()


