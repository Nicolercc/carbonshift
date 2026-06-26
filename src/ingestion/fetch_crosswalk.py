"""
Ingest NYC Building Footprints (5zhs-2jue) → building_crosswalk.

Queens filter: BIN starts with '4' (borough code 4).
This must run before all other fetchers — every other table joins through here.

Confirmed field names (from --sample run 2026-06-25):
  bin, base_bbl, mappluto_bbl  (no plain 'bbl' field — mappluto_bbl is the billing BBL)
"""

import sqlite3
from datetime import datetime, timezone

from .socrata import paginate, sample


DATASET_ID = "5zhs-2jue"

BIN_FIELD = "bin"
BBL_FIELD = "mappluto_bbl"   # billing BBL; no plain 'bbl' exists in this dataset
BASE_BBL_FIELD = "base_bbl"


def run(conn: sqlite3.Connection) -> int:
    print("Sampling Building Footprints to confirm field names …")
    rows = sample(DATASET_ID)
    if not rows:
        raise RuntimeError("No sample rows returned from Building Footprints dataset")

    actual_keys = set(rows[0].keys())
    for field in (BIN_FIELD, BBL_FIELD, BASE_BBL_FIELD):
        if field not in actual_keys:
            raise ValueError(
                f"Expected field '{field}' not found in Building Footprints. "
                f"Actual fields: {sorted(actual_keys)}"
            )
    print(f"  Fields confirmed: {BIN_FIELD}, {BBL_FIELD}, {BASE_BBL_FIELD}")

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    skipped = 0

    print("Ingesting Building Footprints (Queens BIN prefix '4') …")
    for page in paginate(DATASET_ID, where=f"{BIN_FIELD} >= '4000000' AND {BIN_FIELD} < '5000000'"):
        batch = []
        for r in page:
            bin_val = str(r.get(BIN_FIELD, "")).strip()
            if not bin_val or not bin_val.startswith("4"):
                skipped += 1
                continue
            bbl_val = str(r.get(BBL_FIELD, "") or "").strip() or None
            base_bbl_val = str(r.get(BASE_BBL_FIELD, "") or "").strip() or None
            batch.append((bin_val, bbl_val, base_bbl_val, "4", now))

        conn.executemany(
            """
            INSERT OR REPLACE INTO building_crosswalk
              (bin, bbl, base_bbl, borough_code, source_updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            batch,
        )
        conn.commit()
        inserted += len(batch)
        print(f"  … {inserted:,} crosswalk rows inserted")

    print(f"Building Footprints done: {inserted:,} inserted, {skipped:,} skipped")
    return inserted
