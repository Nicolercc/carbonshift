"""
Validation checkpoints (Section G of CLAUDE.md).
Run after all ingestion is complete to verify data quality before downstream use.
"""

import sqlite3


def _pct(a: int, b: int) -> str:
    return f"{a / b * 100:.1f}%" if b else "n/a"


def run(conn: sqlite3.Connection) -> None:
    print("\n" + "=" * 60)
    print("VALIDATION REPORT")
    print("=" * 60)

    # 1. Table row counts
    tables = [
        "building_crosswalk",
        "buildings",
        "building_profiles",
        "building_violations",
        "asbestos_projects",
        "energy_emissions",
    ]
    print("\n--- Row counts ---")
    for table in tables:
        (count,) = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        print(f"  {table:<35} {count:>10,}")

    # 2. Crosswalk join coverage
    print("\n--- Crosswalk join coverage ---")
    (total_bins,) = conn.execute("SELECT COUNT(*) FROM building_crosswalk").fetchone()
    (bins_with_bbl,) = conn.execute(
        "SELECT COUNT(*) FROM building_crosswalk WHERE bbl IS NOT NULL AND bbl != ''"
    ).fetchone()
    print(f"  Total Queens BINs in crosswalk:  {total_bins:>10,}")
    print(f"  BINs with resolved BBL:          {bins_with_bbl:>10,}  ({_pct(bins_with_bbl, total_bins)})")

    # 3. PLUTO → crosswalk join
    (pluto_matched,) = conn.execute(
        "SELECT COUNT(DISTINCT b.bin) FROM buildings b "
        "JOIN building_crosswalk c ON b.bin = c.bin"
    ).fetchone()
    print(f"  Buildings matched to crosswalk:  {pluto_matched:>10,}  ({_pct(pluto_matched, total_bins)} of Queens BINs)")

    # 4. Measured vs. modeled split
    print("\n--- Energy disclosure coverage ---")
    (total_bldgs,) = conn.execute("SELECT COUNT(*) FROM buildings").fetchone()
    (with_energy,) = conn.execute(
        "SELECT COUNT(DISTINCT building_id) FROM energy_emissions"
    ).fetchone()
    without_energy = total_bldgs - with_energy
    print(f"  Total buildings:                 {total_bldgs:>10,}")
    print(f"  With measured energy (LL84/97):  {with_energy:>10,}  ({_pct(with_energy, total_bldgs)})")
    print(f"  Need modelled estimate:          {without_energy:>10,}  ({_pct(without_energy, total_bldgs)})")

    # 5. Violations breakdown by source
    print("\n--- Violations by source dataset ---")
    rows = conn.execute(
        "SELECT source_dataset, COUNT(*) FROM building_violations GROUP BY source_dataset ORDER BY 2 DESC"
    ).fetchall()
    for source, cnt in rows:
        print(f"  {source:<35} {cnt:>10,}")

    # 6. Asbestos flags
    (asbestos_viol,) = conn.execute(
        "SELECT COUNT(*) FROM building_violations WHERE is_asbestos_related = 1"
    ).fetchone()
    (asbestos_proj,) = conn.execute("SELECT COUNT(*) FROM asbestos_projects").fetchone()
    print(f"\n--- Asbestos signals ---")
    print(f"  Violations flagged asbestos-related:  {asbestos_viol:>8,}")
    print(f"  ACP-7 projects:                       {asbestos_proj:>8,}")

    # 7. Duplicate energy rows warning (LL84 expansion)
    (dup_energy,) = conn.execute(
        "SELECT COUNT(*) FROM ("
        "  SELECT building_id, reporting_year, COUNT(*) as c "
        "  FROM energy_emissions GROUP BY building_id, reporting_year HAVING c > 1"
        ")"
    ).fetchone()
    if dup_energy:
        print(f"\n  WARNING: {dup_energy:,} (building_id, reporting_year) pairs have >1 energy_emissions row")
        print("  This may indicate LL84 multi-property rows were expanded correctly, or may signal duplicates.")
    else:
        print("\n  No duplicate (building_id, reporting_year) pairs in energy_emissions — good.")

    # 8. Zero-count warnings
    print("\n--- Sanity checks ---")
    warnings = []
    if total_bins == 0:
        warnings.append("CRITICAL: building_crosswalk is empty — crosswalk ingestion failed")
    if total_bldgs == 0:
        warnings.append("CRITICAL: buildings table is empty — PLUTO ingestion failed")
    for source, cnt in rows:
        if cnt == 0:
            warnings.append(f"WARNING: no violations from {source}")
    if asbestos_proj == 0:
        warnings.append("NOTE: no ACP-7 projects found (check filter or dataset availability)")

    if warnings:
        for w in warnings:
            print(f"  {w}")
    else:
        print("  All sanity checks passed.")

    print("\n" + "=" * 60 + "\n")
