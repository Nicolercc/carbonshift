"""
Ingest NYC PLUTO (64uk-42ks) → buildings + building_profiles.

Filters to BBLs present in building_crosswalk (Queens).

Confirmed field names (from --sample run 2026-06-25):
  borough, block, lot, bbl (float string e.g. '2054800111.00000000'), borocode,
  bldgclass, landuse, yearbuilt, numfloors, unitsres, unitstotal,
  lotarea, bldgarea, latitude, longitude, zipcode, address
  NOTE: no 'bin' field in PLUTO — BIN resolved from crosswalk via BBL lookup.
"""

import sqlite3
from datetime import datetime, timezone

from .socrata import paginate, sample


DATASET_ID = "64uk-42ks"


def _normalise_bbl(raw) -> str | None:
    """PLUTO stores BBL as float string e.g. '2054800111.00000000' → '2054800111'."""
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


def run(conn: sqlite3.Connection) -> int:
    print("Sampling PLUTO to confirm field names …")
    rows = sample(DATASET_ID)
    if not rows:
        raise RuntimeError("No sample rows returned from PLUTO")
    print(f"  Confirmed PLUTO BBL sample: {rows[0].get('bbl')!r} (float string format expected)")

    queens_bbls = {r[0] for r in conn.execute("SELECT bbl FROM building_crosswalk WHERE bbl IS NOT NULL")}
    queens_bins_by_bbl = {
        r[0]: r[1]
        for r in conn.execute("SELECT bbl, bin FROM building_crosswalk WHERE bbl IS NOT NULL")
    }
    print(f"  Queens BBLs in crosswalk: {len(queens_bbls):,}")

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0

    # PLUTO borough filter: 'QN' for Queens
    print("Ingesting PLUTO (borough='QN') …")
    for page in paginate(DATASET_ID, where="borough='QN'"):
        buildings_batch = []
        profiles_batch = []

        for r in page:
            bbl = _normalise_bbl(r.get("bbl"))
            if bbl not in queens_bbls:
                continue

            bin_val = queens_bins_by_bbl.get(bbl)

            full_address = ", ".join(
                p for p in (str(r.get("address", "") or ""), str(r.get("zipcode", "") or "")) if p
            )

            buildings_batch.append((
                bin_val,
                bbl,
                None,           # base_bbl not in PLUTO; use crosswalk value if needed later
                "Queens",
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

        conn.executemany(
            """
            INSERT OR REPLACE INTO buildings
              (bin, bbl, base_bbl, borough, block, lot, full_address, zip_code,
               latitude, longitude, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            buildings_batch,
        )
        conn.executemany(
            """
            INSERT OR REPLACE INTO building_profiles
              (building_id, year_built, building_class, land_use, residential_units,
               total_units, number_of_floors, lot_area, building_area,
               source_name, source_updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            profiles_batch,
        )
        conn.commit()
        inserted += len(buildings_batch)
        print(f"  … {inserted:,} PLUTO buildings inserted")

    print(f"PLUTO done: {inserted:,} buildings inserted")
    return inserted
