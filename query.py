#!/usr/bin/env python3
"""
CarbonShift CLI query tool.

Subcommands:
  search <term>              Search by address keyword, BIN, BBL, or zip code
  building <BIN>             Full detail for a single building
  sql "<SELECT ...>"         Run any SELECT query, print results
  export <name> [--out FILE] Export a named dataset to CSV
                             Names: buildings, violations, energy, asbestos

Examples:
  python query.py search "Jamaica"
  python query.py search 11101
  python query.py building 4059918
  python query.py sql "SELECT COUNT(*) FROM building_violations WHERE is_asbestos_related=1"
  python query.py export buildings
  python query.py export violations --out queens_violations.csv
"""

import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from src.db.init_db import get_connection
from src.query.lookup import search_buildings, get_building, get_violations, get_energy, get_asbestos, run_sql
from src.query.export import export_to_file, export_to_csv_string, EXPORT_QUERIES


# ── formatting helpers ────────────────────────────────────────────────────────

def _hr(char="─", width=72):
    print(char * width)


def _table(rows: list[dict], cols: list[str] | None = None) -> None:
    if not rows:
        print("  (no rows)")
        return
    cols = cols or list(rows[0].keys())
    widths = {c: max(len(str(c)), max(len(str(r.get(c, "") or "")) for r in rows)) for c in cols}
    widths = {c: min(w, 60) for c, w in widths.items()}  # cap column width

    header = "  " + "  ".join(str(c).ljust(widths[c]) for c in cols)
    print(header)
    print("  " + "  ".join("─" * widths[c] for c in cols))
    for r in rows:
        line = "  " + "  ".join(str(r.get(c, "") or "")[:widths[c]].ljust(widths[c]) for c in cols)
        print(line)


def _kv(label: str, value, indent: int = 2) -> None:
    prefix = " " * indent
    print(f"{prefix}{label:<28}{value}")


# ── subcommand handlers ───────────────────────────────────────────────────────

def cmd_search(conn, args) -> None:
    term = " ".join(args.term)
    print(f"\nSearching for: {term!r}\n")
    results = search_buildings(conn, term, limit=args.limit)
    if not results:
        print("  No buildings found.")
        return

    print(f"  {len(results)} result(s)\n")
    cols = ["bin", "full_address", "zip_code", "year_built", "building_class",
            "building_area", "violation_count", "asbestos_count", "latest_ghg"]
    _table(results, cols)
    print()


def cmd_building(conn, args) -> None:
    bin_val = args.bin.strip()
    bldg = get_building(conn, bin_val)
    if not bldg:
        print(f"  No building found with BIN {bin_val}")
        sys.exit(1)

    _hr("═")
    print(f"  {bldg['full_address'] or '(no address)'}")
    _hr("═")

    print("\n  IDENTIFIERS")
    _hr()
    _kv("BIN", bldg["bin"])
    _kv("BBL", bldg["bbl"])
    _kv("Base BBL", bldg["base_bbl"])
    _kv("Borough", bldg["borough"])
    _kv("Block / Lot", f"{bldg['block']} / {bldg['lot']}")
    _kv("Zip Code", bldg["zip_code"])
    if bldg["latitude"]:
        _kv("Lat / Lon", f"{bldg['latitude']}, {bldg['longitude']}")

    print("\n  BUILDING PROFILE")
    _hr()
    _kv("Year Built", bldg["year_built"])
    _kv("Building Class", bldg["building_class"])
    _kv("Land Use", bldg["land_use"])
    _kv("Floors", bldg["number_of_floors"])
    _kv("Residential Units", bldg["residential_units"])
    _kv("Total Units", bldg["total_units"])
    if bldg["building_area"]:
        _kv("Building Area (sq ft)", f"{float(bldg['building_area']):,.0f}")
    if bldg["lot_area"]:
        _kv("Lot Area (sq ft)", f"{float(bldg['lot_area']):,.0f}")

    # Energy
    energy = get_energy(conn, bin_val)
    if energy:
        print("\n  ENERGY & EMISSIONS")
        _hr()
        _table(energy, ["reporting_year", "ghg_emissions_metric_tons_co2e", "site_eui", "energy_star_score"])

    # Violations summary
    violations = get_violations(conn, bin_val)
    asbestos_count = sum(1 for v in violations if v["is_asbestos_related"])
    print(f"\n  VIOLATIONS  ({len(violations)} total, {asbestos_count} asbestos-related)")
    _hr()
    if violations:
        _table(violations, ["source_dataset", "issue_date", "violation_class",
                            "current_status", "violation_description"])

    # Asbestos projects
    asbestos = get_asbestos(conn, bin_val)
    if asbestos:
        print(f"\n  ASBESTOS PROJECTS  ({len(asbestos)})")
        _hr()
        _table(asbestos, ["control_number", "project_status", "project_start_date",
                          "project_end_date", "contractor_name"])
    print()


def cmd_sql(conn, args) -> None:
    sql = " ".join(args.sql)
    try:
        cols, rows = run_sql(conn, sql)
    except ValueError as e:
        print(f"  Error: {e}")
        sys.exit(1)

    print(f"\n  {len(rows)} row(s)\n")
    _table(rows, cols)
    print()


def cmd_export(conn, args) -> None:
    name = args.name
    out_path = args.out or f"{name}.csv"

    if name == "sql":
        if not args.sql:
            print("  --sql required when exporting custom SQL")
            sys.exit(1)
        count = export_to_file(conn, "", out_path, custom_sql=" ".join(args.sql))
    else:
        if name not in EXPORT_QUERIES:
            print(f"  Unknown export '{name}'. Choose: {', '.join(EXPORT_QUERIES)}")
            sys.exit(1)
        count = export_to_file(conn, name, out_path)

    print(f"  Exported {count:,} rows → {out_path}")


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="CarbonShift query & export CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # search
    p_search = sub.add_parser("search", help="Search buildings by address, BIN, BBL, or zip")
    p_search.add_argument("term", nargs="+", help="Search term")
    p_search.add_argument("--limit", type=int, default=50, help="Max results (default 50)")

    # building
    p_bldg = sub.add_parser("building", help="Full detail for one building by BIN")
    p_bldg.add_argument("bin", help="Building Identification Number")

    # sql
    p_sql = sub.add_parser("sql", help="Run a SELECT query")
    p_sql.add_argument("sql", nargs="+", help="SQL statement (quote the whole thing)")

    # export
    p_export = sub.add_parser("export", help="Export a dataset to CSV")
    p_export.add_argument("name", choices=list(EXPORT_QUERIES.keys()) + ["sql"],
                          help="Named export or 'sql' for custom query")
    p_export.add_argument("--out", help="Output file path (default: <name>.csv)")
    p_export.add_argument("--sql", nargs="+", help="Custom SQL when name=sql")

    args = parser.parse_args()
    conn = get_connection()

    dispatch = {
        "search": cmd_search,
        "building": cmd_building,
        "sql": cmd_sql,
        "export": cmd_export,
    }
    dispatch[args.cmd](conn, args)
    conn.close()


if __name__ == "__main__":
    main()
