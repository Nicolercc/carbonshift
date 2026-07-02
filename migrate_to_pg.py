#!/usr/bin/env python3
"""One-time migration: copy all data from SQLite into Postgres."""
import os
import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import execute_values

DB_PATH = os.getenv("DB_PATH", "data/carbonshift.db")
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set.")
    sys.exit(1)

SCHEMA_PG = Path(__file__).parent / "schema_pg.sql"

sqlite_conn = sqlite3.connect(DB_PATH)
sqlite_conn.row_factory = sqlite3.Row

pg_conn = psycopg2.connect(DATABASE_URL)
pg_cur = pg_conn.cursor()

print("Applying schema...")
for stmt in [s.strip() for s in SCHEMA_PG.read_text().split(";") if s.strip()]:
    pg_cur.execute(stmt)
pg_conn.commit()
print("Schema applied.")

# (table_name, id_col_to_skip_or_None)
# Order is FK-safe: parent tables before child tables.
# id columns on child tables are GENERATED ALWAYS AS IDENTITY — skip them;
# Postgres assigns new sequential IDs. Safe because no FK references these id
# values; all joins use building_id TEXT.
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

for table, skip_col in TABLES:
    probe = sqlite_conn.execute(f"SELECT * FROM {table} LIMIT 0")
    all_cols = [d[0] for d in probe.description]
    cols = [c for c in all_cols if c != skip_col]

    # building_risk_scores: risk_detail may not exist in older SQLite DBs
    # (added via _migrate()); insert NULL for missing column.
    if table == "building_risk_scores" and "risk_detail" not in cols:
        cols_insert = cols + ["risk_detail"]
        rows = sqlite_conn.execute(
            f"SELECT {', '.join(cols)} FROM {table}"
        ).fetchall()
        data = [tuple(r[c] for c in cols) + (None,) for r in rows]
    else:
        cols_insert = cols
        rows = sqlite_conn.execute(
            f"SELECT {', '.join(cols)} FROM {table}"
        ).fetchall()
        data = [tuple(r[c] for c in cols) for r in rows]

    if not data:
        print(f"  {table}: 0 rows")
        continue

    col_names = ", ".join(cols_insert)
    execute_values(
        pg_cur,
        f"INSERT INTO {table} ({col_names}) VALUES %s ON CONFLICT DO NOTHING",
        data,
        page_size=2000,
    )
    pg_conn.commit()
    print(f"  {table}: {len(data):,} rows")

pg_cur.close()
pg_conn.close()
sqlite_conn.close()
print("\nMigration complete.")
