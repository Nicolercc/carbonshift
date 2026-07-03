#!/usr/bin/env python3
"""Populate building_crosswalk + buildings + building_profiles for Manhattan.

Source: building_footprints (already loaded by fetch_manhattan_footprints.py)
        + PLUTO Socrata API (64uk-42ks), borough='MN'.

Run AFTER fetch_manhattan_footprints.py. Footprints must already be in
building_footprints before this script can build the crosswalk.

This is the same two-step join used for Queens:
  1. building_crosswalk  ← Manhattan rows from building_footprints (BIN+BBL)
  2. buildings / building_profiles ← PLUTO 'MN', filtered to crosswalk BBLs
"""
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from dotenv import load_dotenv
load_dotenv()

import psycopg2
import requests
from psycopg2.extras import execute_values

DATABASE_URL = os.getenv("DATABASE_URL")
SOCRATA_TOKEN = os.getenv("SOCRATA_APP_TOKEN", "")
PLUTO_DATASET = "64uk-42ks"
PAGE_SIZE = 50_000

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set.")
    sys.exit(1)


# ── helpers ───────────────────────────────────────────────────────────────────

def _normalise_bbl(raw) -> str | None:
    if not raw:
        return None
    try:
        return str(int(float(str(raw).strip())))
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> int | None:
    try:
        return int(float(val)) if val not in (None, "", "NA") else None
    except (ValueError, TypeError):
        return None


def _safe_float(val) -> float | None:
    try:
        return float(val) if val not in (None, "", "NA") else None
    except (ValueError, TypeError):
        return None


def socrata_pages(dataset_id: str, where: str):
    url = f"https://data.cityofnewyork.us/resource/{dataset_id}.json"
    offset = 0
    while True:
        params = {
            "$limit": PAGE_SIZE,
            "$offset": offset,
            "$where": where,
            "$$app_token": SOCRATA_TOKEN,
        }
        for attempt in range(3):
            try:
                r = requests.get(url, params=params, timeout=60)
                r.raise_for_status()
                rows = r.json()
                break
            except Exception as e:
                if attempt == 2:
                    raise
                print(f"  Retry {attempt + 1}: {e}")
                time.sleep(2 ** attempt)
        if not rows:
            break
        yield rows
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE


# ── step 1: crosswalk from building_footprints ────────────────────────────────

def build_crosswalk(conn):
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()

    cur.execute("""
        INSERT INTO building_crosswalk (bin, bbl, base_bbl, borough_code, source_updated_at)
        SELECT
            bin,
            mappluto_bbl AS bbl,
            base_bbl,
            '1',
            %s
        FROM building_footprints
        WHERE bin >= '1000000' AND bin < '2000000'
        ON CONFLICT (bin) DO NOTHING
    """, (now,))
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM building_crosswalk WHERE borough_code = '1'")
    count = cur.fetchone()[0]
    cur.close()
    print(f"  building_crosswalk: {count:,} Manhattan rows")
    return count


# ── step 2: buildings + building_profiles from PLUTO ──────────────────────────

def fetch_pluto(conn):
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()

    # Load crosswalk for Manhattan: bbl → bin lookup
    cur.execute("""
        SELECT bbl, bin FROM building_crosswalk
        WHERE borough_code = '1' AND bbl IS NOT NULL
    """)
    mn_bins_by_bbl = {row[0]: row[1] for row in cur.fetchall()}
    mn_bbls = set(mn_bins_by_bbl.keys())
    print(f"  Crosswalk BBLs available for join: {len(mn_bbls):,}")

    inserted = 0
    skipped = 0
    t0 = time.time()

    for page in socrata_pages(PLUTO_DATASET, where="borough='MN' AND bldgarea > 0"):
        buildings_batch = []
        profiles_batch = []

        for r in page:
            bbl = _normalise_bbl(r.get("bbl"))
            if bbl not in mn_bbls:
                skipped += 1
                continue

            bin_val = mn_bins_by_bbl[bbl]
            full_address = ", ".join(
                p for p in (
                    str(r.get("address", "") or ""),
                    str(r.get("zipcode", "") or ""),
                ) if p
            )

            buildings_batch.append((
                bin_val,
                bbl,
                None,
                "Manhattan",
                str(r.get("block", "") or ""),
                str(r.get("lot", "") or ""),
                full_address,
                str(r.get("zipcode", "") or ""),
                _safe_float(r.get("latitude")),
                _safe_float(r.get("longitude")),
                now,
                now,
            ))

            profiles_batch.append((
                bin_val,
                _safe_int(r.get("yearbuilt")),
                str(r.get("bldgclass", "") or ""),
                str(r.get("landuse", "") or ""),
                _safe_int(r.get("unitsres")),
                _safe_int(r.get("unitstotal")),
                _safe_int(r.get("numfloors")),
                _safe_float(r.get("lotarea")),
                _safe_float(r.get("bldgarea")),
                "PLUTO",
                now,
            ))

        if buildings_batch:
            execute_values(
                cur,
                """
                INSERT INTO buildings
                  (bin, bbl, base_bbl, borough, block, lot, full_address,
                   zip_code, latitude, longitude, created_at, updated_at)
                VALUES %s
                ON CONFLICT (bin) DO NOTHING
                """,
                buildings_batch,
                page_size=2000,
            )
            execute_values(
                cur,
                """
                INSERT INTO building_profiles
                  (building_id, year_built, building_class, land_use,
                   residential_units, total_units, number_of_floors,
                   lot_area, building_area, source_name, source_updated_at)
                VALUES %s
                """,
                profiles_batch,
                page_size=2000,
            )
            conn.commit()
            inserted += len(buildings_batch)

        elapsed = time.time() - t0
        print(f"  PLUTO page done — matched {inserted:,}, skipped {skipped:,}  ({elapsed:.0f}s)")

    cur.close()
    return inserted


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    conn = psycopg2.connect(DATABASE_URL)

    print("Step 1: Building crosswalk from Manhattan footprints …")
    crosswalk_count = build_crosswalk(conn)

    print(f"\nStep 2: PLUTO fetch for Manhattan (borough='MN', bldgarea > 0) …")
    buildings_count = fetch_pluto(conn)

    conn.close()

    print(f"\n── Results ──────────────────────────────────────")
    print(f"  Manhattan crosswalk rows:  {crosswalk_count:,}")
    print(f"  Manhattan buildings added: {buildings_count:,}")
    print(f"  Join efficiency:           {buildings_count / crosswalk_count * 100:.1f}%  "
          f"(Queens was 91.4%)")


if __name__ == "__main__":
    main()
