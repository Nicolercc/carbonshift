"""
Ingest three DOB violation datasets → building_violations:
  - DOB Safety Violations (855j-jady)  → source_dataset = 'DOB_SAFETY'
  - DOB Violations legacy (3h2n-5cm9)  → source_dataset = 'DOB_LEGACY'
  - DOB ECB Violations (6bgk-3dad)     → source_dataset = 'DOB_ECB'

Confirmed field names (from --sample run 2026-06-25):

DOB Safety (855j-jady):
  bin, bbl, violation_number, violation_remarks, violation_status,
  violation_issue_date, violation_type

DOB Legacy (3h2n-5cm9):
  NO bin field — has boro, block, lot only.
  isn_dob_bis_viol, boro, block, lot, description, issue_date,
  violation_number, violation_type, violation_category

DOB ECB (6bgk-3dad):
  bin, boro, block, lot, ecb_violation_number, violation_description,
  penality_imposed (dataset typo), balance_due, issue_date, severity,
  isn_dob_bis_extract
"""

import sqlite3
from datetime import datetime, timezone

from .socrata import paginate, sample


ASBESTOS_KEYWORDS = {"asbestos", "acm", "abatement", "acp-5", "acp-7", "acp5", "acp7"}


def _is_asbestos(text: str) -> int:
    if not text:
        return 0
    return 1 if any(kw in text.lower() for kw in ASBESTOS_KEYWORDS) else 0


def _safe_float(val) -> float | None:
    try:
        return float(val) if val not in (None, "") else None
    except (ValueError, TypeError):
        return None


def _build_bbl(boro: str, block: str, lot: str) -> str | None:
    try:
        return str(boro).strip().zfill(1) + str(block).strip().zfill(5) + str(lot).strip().zfill(4)
    except (AttributeError, TypeError):
        return None


def _ingest_safety(conn: sqlite3.Connection, queens_bins: set, now: str) -> int:
    """DOB Safety Violations — has BIN field directly."""
    dataset_id = "855j-jady"
    print(f"Sampling DOB Safety ({dataset_id}) …")
    rows = sample(dataset_id)
    if not rows:
        raise RuntimeError("No sample rows from DOB Safety")
    print(f"  DOB Safety fields: bin={rows[0].get('bin')!r}, violation_number={rows[0].get('violation_number')!r}")

    inserted = 0
    print("Ingesting DOB Safety Violations (BIN prefix '4') …")
    for page in paginate(dataset_id, where="bin >= '4000000' AND bin < '5000000'"):
        batch = []
        for r in page:
            bin_val = str(r.get("bin", "") or "").strip()
            if not bin_val or not bin_val.startswith("4") or bin_val not in queens_bins:
                continue

            desc = str(r.get("violation_remarks", "") or "")
            batch.append((
                bin_val,
                "DOB_SAFETY",
                "DOB",
                str(r.get("violation_number", "") or ""),
                str(r.get("violation_type", "") or ""),
                str(r.get("violation_type", "") or ""),
                str(r.get("violation_issue_date", "") or ""),
                str(r.get("violation_status", "") or ""),
                desc,
                None,
                None,
                _is_asbestos(desc),
                str(r.get("violation_number", "") or ""),
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
        print(f"  … {inserted:,} DOB Safety violations inserted")

    print(f"DOB Safety done: {inserted:,} inserted")
    return inserted


def _ingest_legacy(conn: sqlite3.Connection, queens_bbls: set, bbl_to_bin: dict, now: str) -> int:
    """DOB Legacy Violations — NO bin field; resolve via BBL constructed from boro+block+lot."""
    dataset_id = "3h2n-5cm9"
    print(f"Sampling DOB Legacy ({dataset_id}) …")
    rows = sample(dataset_id)
    if not rows:
        raise RuntimeError("No sample rows from DOB Legacy")
    print(f"  DOB Legacy fields: boro={rows[0].get('boro')!r} (no bin field — using boro+block+lot)")

    inserted = 0
    print("Ingesting DOB Legacy Violations (boro='4') …")
    for page in paginate(dataset_id, where="boro='4'"):
        batch = []
        for r in page:
            bbl = _build_bbl(
                str(r.get("boro", "") or ""),
                str(r.get("block", "") or ""),
                str(r.get("lot", "") or ""),
            )
            if not bbl or bbl not in queens_bbls:
                continue

            bin_val = bbl_to_bin.get(bbl)
            desc = str(r.get("description", "") or "")
            raw_id = str(r.get("isn_dob_bis_viol", "") or r.get("violation_number", "") or "")

            batch.append((
                bin_val,
                "DOB_LEGACY",
                "DOB",
                str(r.get("violation_number", "") or ""),
                str(r.get("violation_type_code", "") or ""),
                str(r.get("violation_category", "") or r.get("violation_type", "") or ""),
                str(r.get("issue_date", "") or ""),
                "",     # legacy dataset has no status field
                desc,
                None,
                None,
                _is_asbestos(desc),
                raw_id,
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
        print(f"  … {inserted:,} DOB Legacy violations inserted")

    print(f"DOB Legacy done: {inserted:,} inserted")
    return inserted


def _ingest_ecb(conn: sqlite3.Connection, queens_bins: set, now: str) -> int:
    """DOB ECB Violations — has BIN field; note 'penality_imposed' is a dataset typo."""
    dataset_id = "6bgk-3dad"
    print(f"Sampling DOB ECB ({dataset_id}) …")
    rows = sample(dataset_id)
    if not rows:
        raise RuntimeError("No sample rows from DOB ECB")
    print(f"  DOB ECB fields: bin={rows[0].get('bin')!r}, penality_imposed={rows[0].get('penality_imposed')!r}")

    inserted = 0
    print("Ingesting DOB ECB Violations (BIN prefix '4') …")
    for page in paginate(dataset_id, where="bin >= '4000000' AND bin < '5000000'"):
        batch = []
        for r in page:
            bin_val = str(r.get("bin", "") or "").strip()
            if not bin_val or not bin_val.startswith("4") or bin_val not in queens_bins:
                continue

            desc = str(r.get("violation_description", "") or "")
            raw_id = str(r.get("isn_dob_bis_extract", "") or r.get("ecb_violation_number", "") or "")

            batch.append((
                bin_val,
                "DOB_ECB",
                "DOB",
                str(r.get("ecb_violation_number", "") or ""),
                str(r.get("violation_type", "") or ""),
                str(r.get("severity", "") or ""),
                str(r.get("issue_date", "") or ""),
                str(r.get("ecb_violation_status", "") or r.get("hearing_status", "") or ""),
                desc,
                _safe_float(r.get("penality_imposed")),   # dataset typo preserved
                _safe_float(r.get("balance_due")),
                _is_asbestos(desc),
                raw_id,
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
        print(f"  … {inserted:,} DOB ECB violations inserted")

    print(f"DOB ECB done: {inserted:,} inserted")
    return inserted


def run(conn: sqlite3.Connection) -> int:
    queens_bins = {r[0] for r in conn.execute("SELECT bin FROM buildings")}
    queens_bbls = {r[0] for r in conn.execute("SELECT bbl FROM buildings WHERE bbl IS NOT NULL")}
    bbl_to_bin = {
        r[0]: r[1]
        for r in conn.execute("SELECT bbl, bin FROM buildings WHERE bbl IS NOT NULL")
    }
    print(f"  Queens BINs for DOB filter: {len(queens_bins):,}")

    now = datetime.now(timezone.utc).isoformat()
    total = 0
    total += _ingest_safety(conn, queens_bins, now)
    total += _ingest_legacy(conn, queens_bbls, bbl_to_bin, now)
    total += _ingest_ecb(conn, queens_bins, now)

    print(f"All DOB datasets done: {total:,} total violations inserted")
    return total
