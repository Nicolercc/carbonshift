"""
Ingest NYC Building Energy & Water Data Disclosure LL84/LL97 (5zyy-y8am)
→ energy_emissions.

Confirmed field names (from --sample run 2026-06-25):
  nyc_borough_block_and_lot  (BBL — single value in sample, may be list-valued)
  nyc_building_identification (BIN — single value in sample, may be list-valued)
  report_year, property_id, site_eui_kbtu_ft, energy_star_score,
  total_location_based_ghg, borough (='QUEENS' for Queens)

Critical: a single row can list MULTIPLE BBLs and BINs. Each resolved BIN gets
its own energy_emissions row, all sharing the same source_property_id.

Dataset 4t62-jm4m is 2018 vintage — NOT used. Only 5zyy-y8am (CY2022+).
"""

import re
import sqlite3
from datetime import datetime, timezone

from .socrata import paginate, sample


DATASET_ID = "5zyy-y8am"


def _parse_list_field(value) -> list[str]:
    """Parse a field that may hold a single ID or a delimited list."""
    if not value:
        return []
    raw = str(value).strip()
    parts = re.split(r"[,;|\n]+", raw)
    return [p.strip() for p in parts if p.strip()]


def _safe_float(val) -> float | None:
    try:
        v = float(val) if val not in (None, "", "Not Available") else None
        return v
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> int | None:
    try:
        return int(float(val)) if val not in (None, "", "Not Available") else None
    except (ValueError, TypeError):
        return None


def run(conn: sqlite3.Connection) -> int:
    print("Sampling LL84/97 to confirm field names …")
    rows = sample(DATASET_ID)
    if not rows:
        raise RuntimeError("No sample rows from LL84/97 dataset")
    r0 = rows[0]
    print(
        f"  LL84/97 BBL field: nyc_borough_block_and_lot={r0.get('nyc_borough_block_and_lot')!r}\n"
        f"  LL84/97 BIN field: nyc_building_identification={r0.get('nyc_building_identification')!r}\n"
        f"  LL84/97 borough={r0.get('borough')!r}, report_year={r0.get('report_year')!r}"
    )

    queens_bins = {r[0] for r in conn.execute("SELECT bin FROM buildings")}
    queens_bbls = {r[0] for r in conn.execute("SELECT bbl FROM buildings WHERE bbl IS NOT NULL")}
    bbl_to_bin = {
        r[0]: r[1]
        for r in conn.execute("SELECT bbl, bin FROM buildings WHERE bbl IS NOT NULL")
    }

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    expanded = 0

    print("Ingesting LL84/97 (borough='QUEENS') …")
    for page in paginate(DATASET_ID, where="upper(borough)='QUEENS'"):
        batch = []
        for r in page:
            source_property_id = str(r.get("property_id", "") or "")
            reporting_year = _safe_int(r.get("report_year"))
            site_eui = _safe_float(r.get("site_eui_kbtu_ft"))
            energy_star = _safe_int(r.get("energy_star_score"))
            ghg = _safe_float(r.get("total_location_based_ghg"))

            # Resolve BINs from potentially list-valued BBL and BIN fields
            raw_bins = _parse_list_field(r.get("nyc_building_identification"))
            raw_bbls = _parse_list_field(r.get("nyc_borough_block_and_lot"))

            resolved_bins: set[str] = set()
            for b in raw_bins:
                if b in queens_bins:
                    resolved_bins.add(b)
            for bbl in raw_bbls:
                bbl_padded = bbl.zfill(10)
                if bbl_padded in queens_bbls:
                    mapped_bin = bbl_to_bin.get(bbl_padded)
                    if mapped_bin:
                        resolved_bins.add(mapped_bin)

            if not resolved_bins:
                continue

            if len(resolved_bins) > 1:
                expanded += 1

            for bin_val in resolved_bins:
                batch.append((
                    bin_val,
                    reporting_year,
                    site_eui,
                    energy_star,
                    ghg,
                    source_property_id,
                ))

        conn.executemany(
            """
            INSERT INTO energy_emissions
              (building_id, reporting_year, site_eui, energy_star_score,
               ghg_emissions_metric_tons_co2e, source_property_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            batch,
        )
        conn.commit()
        inserted += len(batch)
        print(f"  … {inserted:,} energy_emissions rows inserted ({expanded} multi-BIN expansions so far)")

    print(f"LL84/97 done: {inserted:,} rows inserted, {expanded} source rows expanded to multiple BINs")
    return inserted
