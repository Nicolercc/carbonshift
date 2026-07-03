#!/usr/bin/env python3
"""Ingest Manhattan building violations → building_violations.

Sources (same four as Queens):
  HPD Housing Maintenance Code Violations  wvxf-dwi5  filter: boroid='1'
  DOB Safety Violations                    855j-jady  filter: bin 1000000-1999999
  DOB Violations (legacy BIS)              3h2n-5cm9  filter: boro='1'
  DOB ECB Violations                       6bgk-3dad  filter: bin 1000000-1999999

All four are hardcoded to Queens (boroid/boro='4', bin prefix '4') in the
existing Queens pipeline scripts — this script is the Manhattan equivalent.

Borough filter values confirmed against live API:
  HPD: boroid='1'  (sample returned boroid='1' for Manhattan records)
  DOB Legacy: boro='1'  (sample returned boro='1', field name is 'boro')
  DOB Safety/ECB: BIN integer range — Socrata string-comparison filter

Raw API counts before allowlist filtering (confirmed 2026-07-03):
  HPD:         2,114,209
  DOB Safety:    310,624
  DOB Legacy:    918,323
  DOB ECB:       471,497

Post-filter counts (against 39,733 Manhattan buildings allowlist) will be
lower; they are not known in advance. Guard: loaded > 0, loaded <= raw count.
"""
import os
import sys
import time
from datetime import datetime, timezone
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

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set.")
    sys.exit(1)

ASBESTOS_KEYWORDS = {"asbestos", "acm", "abatement", "acp-5", "acp-7", "acp5", "acp7"}

RAW_COUNTS = {
    "HPD":        2_114_209,
    "DOB_SAFETY":   310_624,
    "DOB_LEGACY":   918_323,
    "DOB_ECB":      471_497,
}


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


def socrata_pages(dataset_id: str, where: str):
    url = f"https://data.cityofnewyork.us/resource/{dataset_id}.json"
    offset = 0
    while True:
        params = {
            "$limit": PAGE_SIZE,
            "$offset": offset,
            "$where": where,
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


INSERT_SQL = """
INSERT INTO building_violations
  (building_id, source_dataset, issuing_agency, violation_number,
   violation_class, severity, issue_date, current_status,
   violation_description, penalty_imposed, balance_due,
   is_asbestos_related, raw_record_id)
VALUES %s
"""


def _flush(cur, batch):
    if not batch:
        return
    execute_values(cur, INSERT_SQL, batch, page_size=2000)


def guard(source: str, loaded: int):
    raw = RAW_COUNTS[source]
    if loaded == 0:
        print(f"  GUARD FAIL: {source} loaded 0 rows — something went wrong.")
        sys.exit(1)
    if loaded > raw:
        print(f"  GUARD FAIL: {source} loaded {loaded:,} > raw API count {raw:,} — logic error.")
        sys.exit(1)
    pct = loaded / raw * 100
    print(f"  Guard OK: {loaded:,} loaded / {raw:,} raw borough-filtered ({pct:.1f}% matched allowlist)")


# ── HPD ───────────────────────────────────────────────────────────────────────

def ingest_hpd(conn, mn_bbls: set, bbl_to_bin: dict) -> int:
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    t0 = time.time()

    print(f"\n── HPD (boroid='1')  raw API count: {RAW_COUNTS['HPD']:,} ──")
    for page in socrata_pages("wvxf-dwi5", "boroid='1'"):
        batch = []
        for r in page:
            bbl = _build_bbl(
                str(r.get("boroid", "") or ""),
                str(r.get("block", "") or ""),
                str(r.get("lot", "") or ""),
            )
            if not bbl or bbl not in mn_bbls:
                continue
            bin_val = bbl_to_bin.get(bbl)
            desc = str(r.get("novdescription", "") or "")
            batch.append((
                bin_val, "HPD", "HPD",
                str(r.get("violationid", "") or ""),
                str(r.get("class", "") or ""),
                str(r.get("class", "") or ""),
                str(r.get("novissueddate", "") or r.get("inspectiondate", "") or ""),
                str(r.get("currentstatus", "") or ""),
                desc, None, None,
                _is_asbestos(desc),
                str(r.get("violationid", "") or ""),
            ))
        _flush(cur, batch)
        conn.commit()
        inserted += len(batch)
        print(f"  offset ~{inserted:,}  elapsed {time.time()-t0:.0f}s")

    cur.close()
    guard("HPD", inserted)
    return inserted


# ── DOB Safety ────────────────────────────────────────────────────────────────

def ingest_dob_safety(conn, mn_bins: set) -> int:
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    t0 = time.time()

    print(f"\n── DOB Safety (bin 1000000–1999999)  raw API count: {RAW_COUNTS['DOB_SAFETY']:,} ──")
    for page in socrata_pages("855j-jady", "bin >= '1000000' AND bin < '2000000'"):
        batch = []
        for r in page:
            bin_val = str(r.get("bin", "") or "").strip()
            if not bin_val or bin_val not in mn_bins:
                continue
            desc = str(r.get("violation_remarks", "") or "")
            batch.append((
                bin_val, "DOB_SAFETY", "DOB",
                str(r.get("violation_number", "") or ""),
                str(r.get("violation_type", "") or ""),
                str(r.get("violation_type", "") or ""),
                str(r.get("violation_issue_date", "") or ""),
                str(r.get("violation_status", "") or ""),
                desc, None, None,
                _is_asbestos(desc),
                str(r.get("violation_number", "") or ""),
            ))
        _flush(cur, batch)
        conn.commit()
        inserted += len(batch)
        print(f"  offset ~{inserted:,}  elapsed {time.time()-t0:.0f}s")

    cur.close()
    guard("DOB_SAFETY", inserted)
    return inserted


# ── DOB Legacy ────────────────────────────────────────────────────────────────

def ingest_dob_legacy(conn, mn_bbls: set, bbl_to_bin: dict) -> int:
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    t0 = time.time()

    print(f"\n── DOB Legacy (boro='1')  raw API count: {RAW_COUNTS['DOB_LEGACY']:,} ──")
    for page in socrata_pages("3h2n-5cm9", "boro='1'"):
        batch = []
        for r in page:
            bbl = _build_bbl(
                str(r.get("boro", "") or ""),
                str(r.get("block", "") or ""),
                str(r.get("lot", "") or ""),
            )
            if not bbl or bbl not in mn_bbls:
                continue
            bin_val = bbl_to_bin.get(bbl)
            desc = str(r.get("description", "") or "")
            raw_id = str(r.get("isn_dob_bis_viol", "") or r.get("violation_number", "") or "")
            batch.append((
                bin_val, "DOB_LEGACY", "DOB",
                str(r.get("violation_number", "") or ""),
                str(r.get("violation_type_code", "") or ""),
                str(r.get("violation_category", "") or r.get("violation_type", "") or ""),
                str(r.get("issue_date", "") or ""),
                "",
                desc, None, None,
                _is_asbestos(desc),
                raw_id,
            ))
        _flush(cur, batch)
        conn.commit()
        inserted += len(batch)
        print(f"  offset ~{inserted:,}  elapsed {time.time()-t0:.0f}s")

    cur.close()
    guard("DOB_LEGACY", inserted)
    return inserted


# ── DOB ECB ───────────────────────────────────────────────────────────────────

def ingest_dob_ecb(conn, mn_bins: set) -> int:
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    t0 = time.time()

    print(f"\n── DOB ECB (bin 1000000–1999999)  raw API count: {RAW_COUNTS['DOB_ECB']:,} ──")
    for page in socrata_pages("6bgk-3dad", "bin >= '1000000' AND bin < '2000000'"):
        batch = []
        for r in page:
            bin_val = str(r.get("bin", "") or "").strip()
            if not bin_val or bin_val not in mn_bins:
                continue
            desc = str(r.get("violation_description", "") or "")
            raw_id = str(r.get("isn_dob_bis_extract", "") or r.get("ecb_violation_number", "") or "")
            batch.append((
                bin_val, "DOB_ECB", "DOB",
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
        _flush(cur, batch)
        conn.commit()
        inserted += len(batch)
        print(f"  offset ~{inserted:,}  elapsed {time.time()-t0:.0f}s")

    cur.close()
    guard("DOB_ECB", inserted)
    return inserted


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("Loading Manhattan building allowlists …")
    cur.execute("SELECT bin FROM buildings WHERE borough = 'Manhattan'")
    mn_bins = {row[0] for row in cur.fetchall()}

    cur.execute("SELECT bbl, bin FROM buildings WHERE borough = 'Manhattan' AND bbl IS NOT NULL")
    rows = cur.fetchall()
    mn_bbls = {row[0] for row in rows}
    bbl_to_bin = {row[0]: row[1] for row in rows}
    cur.close()

    print(f"  Manhattan BINs:  {len(mn_bins):,}")
    print(f"  Manhattan BBLs:  {len(mn_bbls):,}")

    hpd    = ingest_hpd(conn, mn_bbls, bbl_to_bin)
    safety = ingest_dob_safety(conn, mn_bins)
    legacy = ingest_dob_legacy(conn, mn_bbls, bbl_to_bin)
    ecb    = ingest_dob_ecb(conn, mn_bins)

    total = hpd + safety + legacy + ecb

    # Final tally vs Queens baseline
    queens_violations = 460_927
    print(f"\n── Manhattan violations complete ───────────────────────────────")
    print(f"  HPD:        {hpd:>10,}")
    print(f"  DOB Safety: {safety:>10,}")
    print(f"  DOB Legacy: {legacy:>10,}")
    print(f"  DOB ECB:    {ecb:>10,}")
    print(f"  TOTAL:      {total:>10,}")
    print(f"  Queens was: {queens_violations:>10,}")
    print(f"  Ratio:       {total/queens_violations:.2f}×  (pre-ingestion estimate was ~1.54×/building × 0.50 buildings = ~0.77× total)")

    conn.close()


if __name__ == "__main__":
    main()
