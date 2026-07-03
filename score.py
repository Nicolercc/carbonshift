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


def _verify_violation_history(conn) -> None:
    """Refuse to score against a violations table that looks like a filtered,
    active-only export instead of the full history.

    Scoring requires the FULL violation history including closed/resolved
    records — the risk model's violation-count and "no measured LL84 data"
    factors assume `building_violations` reflects everything ever filed, not
    just what's currently open. A dataset containing only OPEN/ACTIVE-style
    statuses would silently understate every risk score with no error, which
    is worse than failing loud here. Never point DATABASE_URL at a database
    whose building_violations table has been filtered down to an
    active-only display export when running score.py — score.py needs the
    same complete table run.py populates.
    """
    total = conn.execute("SELECT COUNT(*) FROM building_violations").fetchone()[0]
    if total == 0:
        return  # an empty table is a separate (ingestion) problem, not this guard's job

    closed_like = conn.execute(
        """
        SELECT COUNT(*) FROM building_violations
        WHERE current_status ILIKE '%CLOSED%'
           OR current_status ILIKE '%DISMISS%'
           OR current_status ILIKE '%RESOLVE%'
        """
    ).fetchone()[0]

    if closed_like == 0:
        raise RuntimeError(
            f"building_violations has {total:,} rows but 0 are closed/dismissed/"
            "resolved — every row looks OPEN/ACTIVE-only. This looks like a "
            "filtered, active-only export rather than the full violation "
            "history scoring requires. Refusing to run. Point DATABASE_URL at "
            "a database with the complete building_violations table (as "
            "populated by run.py) before running score.py again."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="CarbonShift scoring pipeline")
    parser.add_argument("--carbon-only", action="store_true", help="Run carbon estimates only")
    parser.add_argument("--risk-only",   action="store_true", help="Run risk scoring only")
    parser.add_argument("--building",    help="Score a single building by BIN (risk only)")
    args = parser.parse_args()

    init_db()
    conn = get_connection()
    _verify_violation_history(conn)

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
