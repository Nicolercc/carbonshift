#!/usr/bin/env python3
"""Ingest Manhattan building footprints from NYC ArcGIS BUILDING_view FeatureServer.

Source: BUILDING_view FeatureServer (layer 0) — Manhattan BIN range, feature_code=2100.
Destination: building_footprints table in Postgres with PostGIS geometry.

This uses the ArcGIS REST API instead of Socrata because the Socrata Building
Footprints export (5zhs-2jue) covers only ~17.8% of the ArcGIS source for Manhattan.
Queens used Socrata (86,677 records = full Queens coverage); Manhattan requires ArcGIS
(44,607 records vs Socrata's 7,946).

Differences from fetch_footprints.py (Queens/Socrata):
  - Pagination: resultOffset/resultRecordCount, not $limit/$offset
  - BIN and DOITT_ID are integers in ArcGIS JSON — converted to str before insert
  - Geometry: ArcGIS returns Polygon via f=geojson; wrapped to MultiPolygon before insert
  - No Socrata app token needed (ArcGIS service is public)
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

FEATURE_SERVER = (
    "https://services6.arcgis.com/yG5s3afENB5iO9fj/arcgis/rest"
    "/services/BUILDING_view/FeatureServer/0/query"
)
MANHATTAN_WHERE = "BIN >= 1000000 AND BIN < 2000000 AND FEATURE_CODE = 2100"
PAGE_SIZE = 2000          # FeatureServer maxRecordCount
EXPECTED_ROWS = 44_607

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set.")
    sys.exit(1)


def fetch_page(offset: int) -> list[dict]:
    params = {
        "where": MANHATTAN_WHERE,
        "outFields": "BIN,DOITT_ID,BASE_BBL,MAPPLUTO_BBL,LAST_STATUS_TYPE,FEATURE_CODE",
        "resultOffset": offset,
        "resultRecordCount": PAGE_SIZE,
        "f": "geojson",
    }
    for attempt in range(3):
        try:
            r = requests.get(FEATURE_SERVER, params=params, timeout=60)
            r.raise_for_status()
            data = r.json()
            return data.get("features", [])
        except Exception as e:
            if attempt == 2:
                raise
            print(f"  Retry {attempt + 1}: {e}")
            time.sleep(2 ** attempt)
    return []


def feature_to_row(feat: dict) -> tuple | None:
    props = feat["properties"]
    geom = feat.get("geometry")
    if not geom:
        return None

    # ArcGIS returns Polygon; schema requires MultiPolygon.
    if geom["type"] == "Polygon":
        geom = {"type": "MultiPolygon", "coordinates": [geom["coordinates"]]}

    bin_val = str(int(props["BIN"])) if props.get("BIN") is not None else None
    doitt_id = str(int(props["DOITT_ID"])) if props.get("DOITT_ID") is not None else None
    if not bin_val or not doitt_id:
        return None

    return (
        doitt_id,
        bin_val,
        props.get("MAPPLUTO_BBL") or "",
        props.get("BASE_BBL") or "",
        props.get("LAST_STATUS_TYPE") or "",
        str(int(props["FEATURE_CODE"])) if props.get("FEATURE_CODE") is not None else "",
        json.dumps(geom),
    )


def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("Ensuring building_footprints table and indexes exist...")
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
    print("Schema ready.\n")

    offset = 0
    total = 0
    skipped = 0
    t0 = time.time()

    while True:
        features = fetch_page(offset)
        if not features:
            break

        batch = []
        for feat in features:
            row = feature_to_row(feat)
            if row:
                batch.append(row)
            else:
                skipped += 1

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
            f"  offset={offset:>6}  page={len(features):>5}  "
            f"total={total:>6,}  skipped={skipped}  {elapsed:.0f}s"
        )

        if len(features) < PAGE_SIZE:
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
        print("Do not proceed to crosswalk/buildings ingestion until the gap is explained.")
        sys.exit(1)

    print(f"\nDone — {total:,} Manhattan footprints loaded in {elapsed:.0f}s. Count matches expected.")
    if skipped:
        print(f"Skipped (missing BIN/DOITT_ID or geometry): {skipped}")


if __name__ == "__main__":
    main()
