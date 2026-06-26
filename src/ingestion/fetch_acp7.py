"""
Ingest Asbestos Control Program ACP-7 (vq35-j9qm) → asbestos_projects.

Confirmed field names (from --sample run 2026-06-25):
  tru (control number), bin, bbl, status_description, start_date, end_date,
  contractor_name, air_monitor_name, borough

Note: ACP-5 has no bulk API — not ingested here (see CLAUDE.md Section H).
"""

import sqlite3
from datetime import datetime, timezone

from .socrata import paginate, sample


DATASET_ID = "vq35-j9qm"


def run(conn: sqlite3.Connection) -> int:
    print("Sampling ACP-7 to confirm field names …")
    rows = sample(DATASET_ID)
    if not rows:
        raise RuntimeError("No sample rows from ACP-7 dataset")
    print(f"  ACP-7 sample: tru={rows[0].get('tru')!r}, bin={rows[0].get('bin')!r}, borough={rows[0].get('borough')!r}")

    queens_bins = {r[0] for r in conn.execute("SELECT bin FROM buildings")}
    queens_bbls = {r[0] for r in conn.execute("SELECT bbl FROM buildings WHERE bbl IS NOT NULL")}
    bbl_to_bin = {
        r[0]: r[1]
        for r in conn.execute("SELECT bbl, bin FROM buildings WHERE bbl IS NOT NULL")
    }

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0

    print("Ingesting ACP-7 (BIN prefix '4') …")
    for page in paginate(DATASET_ID, where="bin >= '4000000' AND bin < '5000000'"):
        batch = []
        for r in page:
            bin_val = str(r.get("bin", "") or "").strip()

            # Fallback: resolve via BBL if BIN not in crosswalk
            if not bin_val or bin_val not in queens_bins:
                bbl_val = str(r.get("bbl", "") or "").strip()
                bin_val = bbl_to_bin.get(bbl_val) if bbl_val else None

            if not bin_val or bin_val not in queens_bins:
                continue

            batch.append((
                bin_val,
                str(r.get("tru", "") or ""),           # control number field is 'tru'
                str(r.get("status_description", "") or ""),
                str(r.get("start_date", "") or ""),
                str(r.get("end_date", "") or ""),
                str(r.get("contractor_name", "") or ""),
                str(r.get("air_monitor_name", "") or ""),
            ))

        conn.executemany(
            """
            INSERT INTO asbestos_projects
              (building_id, control_number, project_status, project_start_date,
               project_end_date, contractor_name, air_monitor_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            batch,
        )
        conn.commit()
        inserted += len(batch)
        print(f"  … {inserted:,} ACP-7 projects inserted")

    print(f"ACP-7 done: {inserted:,} projects inserted")
    return inserted
