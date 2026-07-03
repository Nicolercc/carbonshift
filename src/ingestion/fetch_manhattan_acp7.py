#!/usr/bin/env python3
"""Ingest Manhattan ACP-7 asbestos projects → asbestos_projects.

Source: Asbestos Control Program ACP-7 (vq35-j9qm)
Filter: bin >= '1000000' AND bin < '2000000'
BBL fallback: if BIN not in Manhattan buildings, resolve via BBL field.

Confirmed fields (same as Queens): tru, bin, bbl, status_description,
start_date, end_date, contractor_name, air_monitor_name.

Raw API count before allowlist filtering (confirmed 2026-07-03): 139,407
Guard: loaded > 0 and loaded <= 139,407.
"""
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

DATABASE_URL = os.getenv("DATABASE_URL")
SOCRATA_TOKEN = os.getenv("SOCRATA_APP_TOKEN", "")
PAGE_SIZE = 50_000
RAW_COUNT = 139_407

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set.")
    sys.exit(1)


def socrata_pages(dataset_id: str, where: str, order: str = ":id"):
    url = f"https://data.cityofnewyork.us/resource/{dataset_id}.json"
    offset = 0
    while True:
        params = {
            "$limit": PAGE_SIZE,
            "$offset": offset,
            "$where": where,
            "$order": order,
            "$$app_token": SOCRATA_TOKEN,
        }
        for attempt in range(3):
            try:
                r = requests.get(url, params=params, timeout=120)
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


def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("Loading Manhattan building allowlists …")
    cur.execute("SELECT bin FROM buildings WHERE borough = 'Manhattan'")
    mn_bins = {row[0] for row in cur.fetchall()}
    cur.execute("SELECT bbl, bin FROM buildings WHERE borough = 'Manhattan' AND bbl IS NOT NULL")
    rows = cur.fetchall()
    bbl_to_bin = {row[0]: row[1] for row in rows}
    mn_bbls = set(bbl_to_bin.keys())
    print(f"  Manhattan BINs: {len(mn_bins):,}  BBLs: {len(mn_bbls):,}")

    cur.execute("SELECT COUNT(*) FROM asbestos_projects WHERE building_id LIKE '1%'")
    start_count = cur.fetchone()[0]
    loaded = start_count
    t0 = time.time()

    print(f"\n── ACP-7 (bin 1000000–1999999)  raw API count: {RAW_COUNT:,} ──")
    for page in socrata_pages("vq35-j9qm", "bin >= '1000000' AND bin < '2000000'"):
        batch = []
        for r in page:
            bin_val = str(r.get("bin", "") or "").strip()

            # BIN-first; fall back to BBL if BIN not in our buildings
            if not bin_val or bin_val not in mn_bins:
                bbl_val = str(r.get("bbl", "") or "").strip()
                bin_val = bbl_to_bin.get(bbl_val) if bbl_val else None

            if not bin_val or bin_val not in mn_bins:
                continue

            batch.append((
                bin_val,
                str(r.get("tru", "") or ""),
                str(r.get("status_description", "") or ""),
                str(r.get("start_date", "") or ""),
                str(r.get("end_date", "") or ""),
                str(r.get("contractor_name", "") or ""),
                str(r.get("air_monitor_name", "") or ""),
            ))

        if batch:
            execute_values(
                cur,
                """
                INSERT INTO asbestos_projects
                  (building_id, control_number, project_status, project_start_date,
                   project_end_date, contractor_name, air_monitor_name)
                VALUES %s
                ON CONFLICT (building_id, control_number) DO NOTHING
                """,
                batch,
                page_size=2000,
            )
            conn.commit()
        cur.execute("SELECT COUNT(*) FROM asbestos_projects WHERE building_id LIKE '1%'")
        loaded = cur.fetchone()[0]
        print(f"  loaded {loaded:,}  elapsed {time.time()-t0:.0f}s")

    cur.close()

    # Guard
    if loaded == 0:
        print(f"GUARD FAIL: 0 rows loaded — something went wrong.")
        conn.close()
        sys.exit(1)
    if loaded > RAW_COUNT:
        print(f"GUARD FAIL: {loaded:,} loaded > raw {RAW_COUNT:,} — logic error.")
        conn.close()
        sys.exit(1)

    pct = loaded / RAW_COUNT * 100
    print(f"  Guard OK: {loaded:,} loaded / {RAW_COUNT:,} raw ({pct:.1f}% matched allowlist)")
    print(f"\n── ACP-7 complete ──────────────────────────────────────────────")
    print(f"  Manhattan asbestos_projects: {loaded:,}")
    print(f"  New rows this run:           {loaded - start_count:,}")
    print(f"  Queens is:                   4,237")
    print(f"  Ratio:                       {loaded/4237:.2f}×")

    conn.close()


if __name__ == "__main__":
    main()
