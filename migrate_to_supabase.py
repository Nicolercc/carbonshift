#!/usr/bin/env python3
"""One-time migration: copy all data from local Postgres to Supabase.

Source: DATABASE_URL (local carbonshift_queens)
Destination: SUPABASE_DATABASE_URL

Run after schema_pg.sql has been applied to Supabase.
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import execute_values

SRC_URL = os.getenv("DATABASE_URL")
DST_URL = os.getenv("SUPABASE_DATABASE_URL")

if not SRC_URL:
    print("ERROR: DATABASE_URL (local Postgres) not set.")
    sys.exit(1)
if not DST_URL:
    print("ERROR: SUPABASE_DATABASE_URL not set.")
    sys.exit(1)

src = psycopg2.connect(SRC_URL)
dst = psycopg2.connect(DST_URL)
src_cur = src.cursor()
dst_cur = dst.cursor()

# FK-safe order: parents before children.
# id columns are GENERATED ALWAYS AS IDENTITY on child tables — skip them;
# Postgres assigns new IDs. Safe because no FK references these id values.
TABLES = [
    ("building_crosswalk",      None,  None),
    ("buildings",               None,  None),
    ("building_profiles",       None,  None),
    ("building_violations",     "id",  2000),
    ("asbestos_projects",       "id",  2000),
    ("energy_emissions",        "id",  2000),
    ("building_risk_scores",    None,  None),
    ("carbon_estimates",        None,  None),
    ("building_record_sources", "id",  2000),
]

print("Migrating scalar tables...\n")
for table, skip_col, page_size in TABLES:
    t0 = time.time()
    src_cur.execute(f"SELECT * FROM {table} LIMIT 0")
    all_cols = [d[0] for d in src_cur.description]
    cols = [c for c in all_cols if c != skip_col]
    col_sql = ", ".join(cols)

    src_cur.execute(f"SELECT {col_sql} FROM {table}")
    rows = src_cur.fetchall()

    if not rows:
        print(f"  {table}: 0 rows — skipped")
        continue

    execute_values(
        dst_cur,
        f"INSERT INTO {table} ({col_sql}) VALUES %s ON CONFLICT DO NOTHING",
        rows,
        page_size=page_size or 2000,
    )
    dst.commit()
    elapsed = time.time() - t0
    print(f"  {table}: {len(rows):,} rows  ({elapsed:.1f}s)")

print("\nMigrating building_footprints (86,677 rows with PostGIS geometry)...")
src_cur.execute("""
    SELECT doitt_id, bin, mappluto_bbl, base_bbl,
           last_status_type, feature_code,
           ST_AsText(geom) AS geom_wkt
    FROM building_footprints
""")

FOOT_PAGE = 500
total = 0
t0 = time.time()
while True:
    batch = src_cur.fetchmany(FOOT_PAGE)
    if not batch:
        break
    execute_values(
        dst_cur,
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
            " ST_SetSRID(ST_GeomFromText(%s), 4326))"
        ),
        page_size=FOOT_PAGE,
    )
    dst.commit()
    total += len(batch)
    if total % 10000 == 0:
        print(f"  footprints: {total:,} / 86,677  ({time.time()-t0:.0f}s)")

elapsed = time.time() - t0
print(f"  building_footprints: {total:,} rows  ({elapsed:.1f}s)")

src_cur.close()
dst_cur.close()
src.close()
dst.close()

print("\nMigration complete.")
