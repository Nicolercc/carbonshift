#!/usr/bin/env python3
"""Verify Postgres data matches SQLite after migration."""
import os
import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

from src.db.init_db import get_pg_connection

DB_PATH = os.getenv("DB_PATH", "data/carbonshift.db")
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set.")
    sys.exit(1)

sq = sqlite3.connect(DB_PATH)
sq.row_factory = sqlite3.Row
pg = get_pg_connection(DATABASE_URL)

COUNT_CHECKS = [
    ("buildings",             "SELECT COUNT(*) FROM buildings"),
    ("building_violations",   "SELECT COUNT(*) FROM building_violations"),
    ("carbon_estimates",      "SELECT COUNT(*) FROM carbon_estimates"),
    ("building_risk_scores",  "SELECT COUNT(*) FROM building_risk_scores"),
    ("energy_emissions",      "SELECT COUNT(*) FROM energy_emissions"),
    ("asbestos_projects",     "SELECT COUNT(*) FROM asbestos_projects"),
    ("building_crosswalk",    "SELECT COUNT(*) FROM building_crosswalk"),
    ("high+critical risk",    "SELECT COUNT(*) FROM building_risk_scores WHERE risk_label IN ('High','Critical')"),
    ("carbon measured",       "SELECT COUNT(*) FROM carbon_estimates WHERE eui_source='measured'"),
    ("buildings with coords", "SELECT COUNT(*) FROM buildings WHERE latitude IS NOT NULL"),
]

all_ok = True
for name, sql in COUNT_CHECKS:
    sq_val = sq.execute(sql).fetchone()[0]
    pg_val = pg.execute(sql).fetchone()[0]
    ok = sq_val == pg_val
    if not ok:
        all_ok = False
    print(f"{'OK' if ok else 'MISMATCH':8s}  {name}: SQLite={sq_val:,}  Postgres={pg_val:,}")

# eui_source breakdown — compare value tuples; avoids column-name casing differences
print()
sq_rows = sq.execute(
    "SELECT eui_source, COUNT(*) FROM carbon_estimates GROUP BY eui_source ORDER BY eui_source"
).fetchall()
pg_rows = pg.execute(
    "SELECT eui_source, COUNT(*) FROM carbon_estimates GROUP BY eui_source ORDER BY eui_source"
).fetchall()
sq_vals = sorted((r[0], r[1]) for r in sq_rows)
pg_vals = sorted((r[0], r[1]) for r in pg_rows)
ok = sq_vals == pg_vals
if not ok:
    all_ok = False
print(f"{'OK' if ok else 'MISMATCH':8s}  eui_source breakdown:")
print(f"          SQLite:   {sq_vals}")
print(f"          Postgres: {pg_vals}")

sq.close()
pg.close()

print()
if all_ok:
    print("All checks passed — Postgres data matches SQLite.")
    sys.exit(0)
else:
    print("Mismatches found — investigate above.")
    sys.exit(1)
