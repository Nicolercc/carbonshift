#!/usr/bin/env python3
"""
CarbonShift data ingestion pipeline — Queens MVP.

Usage:
  python run.py                  # full pipeline
  python run.py --step crosswalk # single step
  python run.py --validate-only  # skip ingestion, run validation only
  python run.py --sample         # print 5-row samples from all datasets and exit
"""

import argparse
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from src.db.init_db import get_connection, init_db
from src.ingestion import (
    fetch_crosswalk,
    fetch_pluto,
    fetch_hpd,
    fetch_dob,
    fetch_acp7,
    fetch_ll84_97,
)
from src.ingestion.socrata import sample
from src.validate import check_coverage


DATASETS = {
    "5zhs-2jue": "Building Footprints (crosswalk)",
    "64uk-42ks": "PLUTO",
    "wvxf-dwi5": "HPD Housing Maintenance Code Violations",
    "855j-jady": "DOB Safety Violations",
    "3h2n-5cm9": "DOB Violations (legacy)",
    "6bgk-3dad": "DOB ECB Violations",
    "vq35-j9qm": "ACP-7 Asbestos Projects",
    "5zyy-y8am": "LL84/LL97 Energy & Emissions",
}

STEPS = {
    "crosswalk": fetch_crosswalk.run,
    "pluto":     fetch_pluto.run,
    "hpd":       fetch_hpd.run,
    "dob":       fetch_dob.run,
    "acp7":      fetch_acp7.run,
    "ll84":      fetch_ll84_97.run,
}


def run_samples() -> None:
    print("Pulling 5-row samples from all datasets to inspect field names …\n")
    for dataset_id, name in DATASETS.items():
        print(f"{'=' * 60}")
        print(f"Dataset: {name} ({dataset_id})")
        try:
            rows = sample(dataset_id)
            if rows:
                print(f"Fields: {list(rows[0].keys())}")
                print(f"Sample row: {rows[0]}")
            else:
                print("  No rows returned")
        except Exception as exc:
            print(f"  ERROR: {exc}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="CarbonShift data ingestion pipeline")
    parser.add_argument(
        "--step",
        choices=list(STEPS.keys()),
        help="Run only a single ingestion step",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Skip ingestion; run validation report only",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Print 5-row samples from all datasets and exit",
    )
    args = parser.parse_args()

    if args.sample:
        run_samples()
        return

    print("Initialising database …")
    init_db()
    conn = get_connection()

    if args.validate_only:
        check_coverage.run(conn)
        conn.close()
        return

    steps_to_run = {args.step: STEPS[args.step]} if args.step else STEPS

    start = time.monotonic()
    for name, fn in steps_to_run.items():
        print(f"\n{'─' * 60}")
        print(f"STEP: {name.upper()}")
        print(f"{'─' * 60}")
        step_start = time.monotonic()
        try:
            fn(conn)
        except Exception as exc:
            print(f"\nERROR in step '{name}': {exc}", file=sys.stderr)
            raise
        elapsed = time.monotonic() - step_start
        print(f"Step '{name}' completed in {elapsed:.1f}s")

    total = time.monotonic() - start
    print(f"\nAll steps completed in {total:.1f}s")

    if not args.step:
        check_coverage.run(conn)

    conn.close()


if __name__ == "__main__":
    main()
