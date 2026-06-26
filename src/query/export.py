"""
CSV export utilities — used by both CLI and web download endpoints.
"""

import csv
import io
import sqlite3

from .lookup import run_sql


EXPORT_QUERIES = {
    "buildings": """
        SELECT b.bin, b.bbl, b.full_address, b.zip_code, b.borough,
               bp.year_built, bp.building_class, bp.land_use,
               bp.residential_units, bp.total_units, bp.number_of_floors,
               bp.lot_area, bp.building_area
        FROM buildings b
        LEFT JOIN building_profiles bp ON bp.building_id = b.bin
        ORDER BY b.full_address
    """,
    "violations": """
        SELECT bv.building_id, b.full_address,
               bv.source_dataset, bv.issuing_agency,
               bv.violation_number, bv.violation_class, bv.severity,
               bv.issue_date, bv.current_status, bv.violation_description,
               bv.penalty_imposed, bv.balance_due, bv.is_asbestos_related
        FROM building_violations bv
        LEFT JOIN buildings b ON b.bin = bv.building_id
        ORDER BY bv.issue_date DESC
    """,
    "energy": """
        SELECT ee.building_id, b.full_address,
               ee.reporting_year, ee.site_eui, ee.energy_star_score,
               ee.ghg_emissions_metric_tons_co2e, ee.source_property_id
        FROM energy_emissions ee
        LEFT JOIN buildings b ON b.bin = ee.building_id
        ORDER BY ee.reporting_year DESC, b.full_address
    """,
    "asbestos": """
        SELECT ap.building_id, b.full_address,
               ap.control_number, ap.project_status,
               ap.project_start_date, ap.project_end_date,
               ap.contractor_name, ap.air_monitor_name
        FROM asbestos_projects ap
        LEFT JOIN buildings b ON b.bin = ap.building_id
        ORDER BY ap.project_start_date DESC
    """,
}


def export_to_csv_string(conn: sqlite3.Connection, name: str, custom_sql: str = "") -> str:
    """Return a CSV string for a named export or a custom SQL query."""
    sql = custom_sql or EXPORT_QUERIES.get(name)
    if not sql:
        raise ValueError(f"Unknown export name '{name}'. Choose from: {', '.join(EXPORT_QUERIES)}")

    cols, rows = run_sql(conn, sql)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=cols)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def export_to_file(conn: sqlite3.Connection, name: str, path: str, custom_sql: str = "") -> int:
    """Write CSV export to a file. Returns row count."""
    content = export_to_csv_string(conn, name, custom_sql)
    lines = content.count("\n") - 1  # subtract header
    with open(path, "w", newline="") as f:
        f.write(content)
    return max(lines, 0)
