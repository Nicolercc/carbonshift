#!/usr/bin/env python3
"""One-time migration: copy all data from local Postgres to Supabase.

Source: DATABASE_URL (local carbonshift_queens)
Destination: SUPABASE_DATABASE_URL

Run after schema_pg.sql has been applied to Supabase.

Idempotent by design: every target table is truncated before it is
repopulated, and rows are streamed in chunks with a commit after each
chunk. A dropped connection only loses the in-flight chunk — re-running
the whole script from scratch is always safe, which matters because
building_violations/building_record_sources have no natural unique key
(only an autoincrement id, which is excluded from the copy), so
"insert on top of a partial run" would silently duplicate rows.
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
dst_cur = dst.cursor()

CHUNK = 5000
BUILDING_VIOLATION_EXPORT_COLUMNS = [
    "building_id",
    "source_dataset",
    "violation_class",
    "issue_date",
    "current_status",
    "violation_description",
    "penalty_imposed",
    "balance_due",
    "is_asbestos_related",
]
BUILDING_VIOLATION_EXPORT_WHERE = "WHERE COALESCE(current_status, '') ~* '(OPEN|ACTIVE)'"

# FK-safe order: parents before children.
# id columns are GENERATED ALWAYS AS IDENTITY on child tables — skip them;
# Postgres assigns new IDs. Safe because no FK references these id values.
TABLES = [
    ("building_crosswalk",      None),
    ("buildings",               None),
    ("building_profiles",       None),
    ("building_violations",     "id"),
    ("asbestos_projects",       "id"),
    ("energy_emissions",        "id"),
    ("building_risk_scores",    None),
    ("carbon_estimates",        None),
    ("building_record_sources", "id"),
]

print("Truncating destination tables (idempotent re-run, not an incremental sync)...")
dst_cur.execute(
    "TRUNCATE TABLE "
    + ", ".join(t for t, _ in TABLES)
    + ", building_footprints RESTART IDENTITY CASCADE"
)
dst.commit()
print("  done\n")

print("Ensuring asbestos_projects uniqueness constraint on Supabase...")
dst_cur.execute("SELECT 1 FROM pg_constraint WHERE conname = 'uq_acp7_building_cn'")
if dst_cur.fetchone():
    print("  uq_acp7_building_cn already present — skipping")
else:
    dst_cur.execute("""
        ALTER TABLE asbestos_projects
        ADD CONSTRAINT uq_acp7_building_cn UNIQUE (building_id, control_number)
    """)
    dst.commit()
    print("  added uq_acp7_building_cn")

print("\nMigrating scalar tables...\n")
for table, skip_col in TABLES:
    t0 = time.time()
    src_meta = src.cursor()
    src_meta.execute(f"SELECT * FROM {table} LIMIT 0")
    all_cols = [d[0] for d in src_meta.description]
    src_meta.close()

    if table == "building_violations":
        cols = BUILDING_VIOLATION_EXPORT_COLUMNS
        where_sql = BUILDING_VIOLATION_EXPORT_WHERE
    else:
        cols = [c for c in all_cols if c != skip_col]
        where_sql = ""
    col_sql = ", ".join(cols)

    src_stream = src.cursor(name=f"stream_{table}")
    src_stream.itersize = CHUNK
    src_stream.execute(f"SELECT {col_sql} FROM {table} {where_sql}")

    total = 0
    while True:
        batch = src_stream.fetchmany(CHUNK)
        if not batch:
            break
        execute_values(
            dst_cur,
            f"INSERT INTO {table} ({col_sql}) VALUES %s",
            batch,
            page_size=CHUNK,
        )
        dst.commit()
        total += len(batch)

    src_stream.close()
    elapsed = time.time() - t0
    if total == 0:
        print(f"  {table}: 0 rows — skipped ({elapsed:.1f}s)")
    else:
        print(f"  {table}: {total:,} rows  ({elapsed:.1f}s)")

print("\nMigrating building_footprints (PostGIS geometry)...")
foot_stream = src.cursor(name="stream_footprints")
foot_stream.itersize = 500
foot_stream.execute("""
    SELECT doitt_id, bin, mappluto_bbl, base_bbl,
           last_status_type, feature_code,
           ST_AsText(geom) AS geom_wkt
    FROM building_footprints
""")

FOOT_PAGE = 500
total = 0
t0 = time.time()
while True:
    batch = foot_stream.fetchmany(FOOT_PAGE)
    if not batch:
        break
    execute_values(
        dst_cur,
        """
        INSERT INTO building_footprints
            (doitt_id, bin, mappluto_bbl, base_bbl,
             last_status_type, feature_code, geom)
        VALUES %s
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
        print(f"  footprints: {total:,}  ({time.time()-t0:.0f}s)")

foot_stream.close()
elapsed = time.time() - t0
print(f"  building_footprints: {total:,} rows  ({elapsed:.1f}s)")

dst_cur.close()
src.close()
dst.close()

print("\nMigration complete.")
