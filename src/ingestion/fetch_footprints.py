#!/usr/bin/env python3
"""Ingest Queens building footprints from NYC Open Data into Postgres.

Source: Building Footprints (5zhs-2jue) — Queens BIN range filter.
Destination: building_footprints table in Postgres with PostGIS geometry.
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from dotenv import load_dotenv
load_dotenv()

import psycopg2
import requests
from psycopg2.extras import execute_values

DATASET_URL = "https://data.cityofnewyork.us/resource/5zhs-2jue.json"
QUEENS_WHERE = "bin >= '4000000' AND bin < '5000000'"
PAGE_SIZE = 5000
EXPECTED_ROWS = 86_677

DATABASE_URL = os.getenv("DATABASE_URL")
SOCRATA_TOKEN = os.getenv("SOCRATA_APP_TOKEN", "")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set.")
    sys.exit(1)


def fetch_page(offset: int) -> list[dict]:
    params = {
        "$limit": PAGE_SIZE,
        "$offset": offset,
        "$where": QUEENS_WHERE,
        "$$app_token": SOCRATA_TOKEN,
    }
    for attempt in range(3):
        try:
            r = requests.get(DATASET_URL, params=params, timeout=60)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == 2:
                raise
            print(f"  Retry {attempt + 1}: {e}")
            time.sleep(2 ** attempt)
    return []


def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("Enabling PostGIS extension...")
    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    conn.commit()

    print("Creating building_footprints table and indexes...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS building_footprints (
            doitt_id         TEXT PRIMARY KEY,
            bin              TEXT,
            mappluto_bbl     TEXT,
            base_bbl         TEXT,
            last_status_type TEXT,
            feature_code     TEXT,
            geom             geometry(MultiPolygon, 4326)
        )
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_footprints_bin  ON building_footprints (bin)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_footprints_geom ON building_footprints USING GIST (geom)"
    )
    conn.commit()
    print("Schema ready.")

    offset = 0
    total = 0
    t0 = time.time()

    while True:
        rows = fetch_page(offset)
        if not rows:
            break

        batch = []
        for row in rows:
            geom = row.get("the_geom")
            if not geom:
                continue
            # Dataset is consistently MultiPolygon; guard against bare Polygon
            # which would violate the column type constraint.
            if geom.get("type") == "Polygon":
                geom = {"type": "MultiPolygon", "coordinates": [geom["coordinates"]]}

            batch.append((
                str(row.get("doitt_id", "")),
                str(row.get("bin", "")).strip(),
                str(row.get("mappluto_bbl") or ""),
                str(row.get("base_bbl") or ""),
                row.get("last_status_type", ""),
                row.get("feature_code", ""),
                json.dumps(geom),
            ))

        if batch:
            execute_values(
                cur,
                """
                INSERT INTO building_footprints
                    (doitt_id, bin, mappluto_bbl, base_bbl,
                     last_status_type, feature_code, geom)
                VALUES %s
                ON CONFLICT (doitt_id) DO NOTHING
                """,
                batch,
                template=(
                    "(%s, %s, %s, %s, %s, %s,"
                    " ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))"
                ),
                page_size=500,
            )
            conn.commit()
            total += len(batch)

        elapsed = time.time() - t0
        print(
            f"  offset={offset:>6}  page={len(rows):>5}  "
            f"total={total:>6,}  {elapsed:.0f}s"
        )

        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    cur.close()
    conn.close()

    elapsed = time.time() - t0
    if total != EXPECTED_ROWS:
        print(
            f"\nROW COUNT MISMATCH — loaded {total:,}, expected {EXPECTED_ROWS:,}. "
            f"Difference: {total - EXPECTED_ROWS:+,}."
        )
        print("Do not proceed to lookup.py changes until the gap is explained.")
        sys.exit(1)

    print(f"\nDone — {total:,} footprints loaded in {elapsed:.0f}s. Count matches expected.")


if __name__ == "__main__":
    main()
