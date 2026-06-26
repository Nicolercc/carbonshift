#!/usr/bin/env python3
"""
CarbonShift scoring pipeline.

Populates carbon_estimates and building_risk_scores.
Run after `python run.py` completes ingestion.

Usage:
  python score.py                     # both carbon + risk
  python score.py --carbon-only
  python score.py --risk-only
  python score.py --building 4059918  # single building (risk only)
"""

import argparse
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from src.db.init_db import get_connection, init_db
from src.scoring import carbon, risk


def main() -> None:
    parser = argparse.ArgumentParser(description="CarbonShift scoring pipeline")
    parser.add_argument("--carbon-only", action="store_true", help="Run carbon estimates only")
    parser.add_argument("--risk-only",   action="store_true", help="Run risk scoring only")
    parser.add_argument("--building",    help="Score a single building by BIN (risk only)")
    args = parser.parse_args()

    init_db()
    conn = get_connection()

    start = time.monotonic()

    if args.building:
        # Single-building risk score
        from src.scoring.risk import run as risk_run
        # Temporarily filter: easiest is to run full and let it be fast
        print(f"Scoring single building: {args.building}")
        risk_run(conn)
        row = conn.execute(
            "SELECT risk_score, risk_label, confidence_label, risk_detail FROM building_risk_scores WHERE building_id=?",
            (args.building,),
        ).fetchone()
        if row:
            print(f"\n  Score:      {row[0]}  ({row[1]})")
            print(f"  Confidence: {row[2]}")
            print(f"  Detail:     {row[3]}")
        else:
            print(f"  No score generated — BIN {args.building!r} may not be in the database")
        conn.close()
        return

    run_carbon = not args.risk_only
    run_risk   = not args.carbon_only

    if run_carbon:
        print("\n── Carbon Estimates ────────────────────────────────────────")
        t = time.monotonic()
        measured, modelled = carbon.run(conn)
        print(f"   Completed in {time.monotonic()-t:.1f}s")

    if run_risk:
        print("\n── Risk Scoring ────────────────────────────────────────────")
        t = time.monotonic()
        scored = risk.run(conn)
        print(f"   Completed in {time.monotonic()-t:.1f}s")

    print(f"\nTotal scoring time: {time.monotonic()-start:.1f}s")
    conn.close()


if __name__ == "__main__":
    main()
