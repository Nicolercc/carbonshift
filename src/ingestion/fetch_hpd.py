"""
Ingest HPD Housing Maintenance Code Violations (wvxf-dwi5) → building_violations.

Confirmed field names (from --sample run 2026-06-25):
  boroid, boro, block, lot, class, violationid, novdescription,
  novissueddate, currentstatus, inspectiondate
  NOTE: no 'bbl' field — BBL constructed from boroid + block + lot.
"""

import sqlite3
from datetime import datetime, timezone

from .socrata import paginate, sample


DATASET_ID = "wvxf-dwi5"
SOURCE = "HPD"

ASBESTOS_KEYWORDS = {"asbestos", "acm", "abatement", "acp-5", "acp-7", "acp5", "acp7"}


def _is_asbestos(text: str) -> int:
    if not text:
        return 0
    lower = text.lower()
    return 1 if any(kw in lower for kw in ASBESTOS_KEYWORDS) else 0


def _build_bbl(boroid: str, block: str, lot: str) -> str | None:
    """Construct 10-digit BBL from HPD's separate boro/block/lot fields."""
    try:
        return boroid.zfill(1) + block.zfill(5) + lot.zfill(4)
    except (AttributeError, TypeError):
        return None


def run(conn: sqlite3.Connection) -> int:
    print("Sampling HPD Violations to confirm field names …")
    rows = sample(DATASET_ID)
    if not rows:
        raise RuntimeError("No sample rows from HPD dataset")
    print(f"  HPD sample boroid={rows[0].get('boroid')!r}, block={rows[0].get('block')!r}, lot={rows[0].get('lot')!r}")

    queens_bbls = {r[0] for r in conn.execute("SELECT bbl FROM building_crosswalk WHERE bbl IS NOT NULL")}
    bbl_to_bin = {
        r[0]: r[1]
        for r in conn.execute("SELECT bbl, bin FROM building_crosswalk WHERE bbl IS NOT NULL")
    }
    print(f"  Queens BBLs for HPD filter: {len(queens_bbls):,}")

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0

    print("Ingesting HPD Violations (boroid='4') …")
    for page in paginate(DATASET_ID, where="boroid='4'"):
        batch = []
        for r in page:
            bbl = _build_bbl(
                str(r.get("boroid", "") or ""),
                str(r.get("block", "") or ""),
                str(r.get("lot", "") or ""),
            )
            if not bbl or bbl not in queens_bbls:
                continue

            bin_val = bbl_to_bin.get(bbl)
            desc = str(r.get("novdescription", "") or "")
            issue_date = str(r.get("novissueddate", "") or r.get("inspectiondate", "") or "")

            batch.append((
                bin_val,
                SOURCE,
                "HPD",
                str(r.get("violationid", "") or ""),
                str(r.get("class", "") or ""),           # A/B/C/I
                str(r.get("class", "") or ""),
                issue_date,
                str(r.get("currentstatus", "") or ""),
                desc,
                None,   # HPD does not expose penalty amount in this dataset
                None,
                _is_asbestos(desc),
                str(r.get("violationid", "") or ""),
            ))

        conn.executemany(
            """
            INSERT INTO building_violations
              (building_id, source_dataset, issuing_agency, violation_number,
               violation_class, severity, issue_date, current_status,
               violation_description, penalty_imposed, balance_due,
               is_asbestos_related, raw_record_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            batch,
        )
        conn.commit()
        inserted += len(batch)
        print(f"  … {inserted:,} HPD violations inserted")

    print(f"HPD done: {inserted:,} violations inserted")
    return inserted
