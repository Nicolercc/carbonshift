"""
Shared query logic used by both the CLI (query.py) and the web app.
All functions accept a sqlite3.Connection and return plain dicts / lists.
"""

import json
import sqlite3


def search_buildings(
    conn: sqlite3.Connection,
    q: str,
    limit: int = 100,
    zip_code: str = "",
    building_class: str = "",
    year_min: int | None = None,
    year_max: int | None = None,
    has_violations: bool = False,
    has_asbestos: bool = False,
    has_energy: bool = False,
    risk_label: str = "",
) -> list[dict]:
    q = q.strip()

    where_parts = []
    params: dict = {"q": q, "like": f"%{q}%", "limit": limit}

    # Keyword / identifier match
    if q:
        where_parts.append(
            "(b.bin = :q OR b.bbl = :q OR b.zip_code = :q OR b.full_address ILIKE :like)"
        )

    # Advanced filters
    if zip_code:
        where_parts.append("b.zip_code = :zip_code")
        params["zip_code"] = zip_code

    if building_class:
        where_parts.append("bp.building_class LIKE :building_class")
        params["building_class"] = f"{building_class}%"

    if year_min is not None:
        where_parts.append("bp.year_built >= :year_min")
        params["year_min"] = year_min

    if year_max is not None:
        where_parts.append("bp.year_built <= :year_max")
        params["year_max"] = year_max

    if has_violations:
        where_parts.append(
            "EXISTS (SELECT 1 FROM building_violations v WHERE v.building_id = b.bin)"
        )

    if has_asbestos:
        where_parts.append(
            "EXISTS (SELECT 1 FROM building_violations v WHERE v.building_id = b.bin AND v.is_asbestos_related=1)"
        )

    if has_energy:
        where_parts.append(
            "EXISTS (SELECT 1 FROM energy_emissions e WHERE e.building_id = b.bin)"
        )

    if risk_label:
        where_parts.append("rs.risk_label = :risk_label")
        params["risk_label"] = risk_label

    where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    rows = conn.execute(
        f"""
        SELECT b.bin, b.bbl, b.full_address, b.zip_code, b.borough,
               b.latitude, b.longitude,
               bp.year_built, bp.building_class, bp.building_area, bp.number_of_floors,
               bp.residential_units,
               (SELECT COUNT(*) FROM building_violations v WHERE v.building_id = b.bin) AS violation_count,
               (SELECT COUNT(*) FROM building_violations v WHERE v.building_id = b.bin AND v.is_asbestos_related = 1) AS asbestos_count,
               (SELECT ghg_emissions_metric_tons_co2e FROM energy_emissions e WHERE e.building_id = b.bin ORDER BY reporting_year DESC LIMIT 1) AS latest_ghg,
               rs.risk_score, rs.risk_label,
               ce.estimated_ghg_metric_tons, ce.eui_source
        FROM buildings b
        LEFT JOIN building_profiles bp ON bp.building_id = b.bin
        LEFT JOIN building_risk_scores rs ON rs.building_id = b.bin
        LEFT JOIN carbon_estimates ce ON ce.building_id = b.bin
        {where_sql}
        ORDER BY b.full_address
        LIMIT :limit
        """,
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_building(conn: sqlite3.Connection, bin_val: str) -> dict | None:
    row = conn.execute(
        """
        SELECT b.bin, b.bbl, b.base_bbl, b.full_address, b.zip_code, b.borough,
               b.block, b.lot, b.latitude, b.longitude,
               bp.year_built, bp.building_class, bp.land_use,
               bp.residential_units, bp.total_units, bp.number_of_floors,
               bp.lot_area, bp.building_area, bp.source_name,
               rs.risk_score, rs.risk_label, rs.confidence_label, rs.risk_detail,
               ce.estimated_ghg_metric_tons, ce.eui_source, ce.site_eui,
               ce.peer_building_count
        FROM buildings b
        LEFT JOIN building_profiles bp ON bp.building_id = b.bin
        LEFT JOIN building_risk_scores rs ON rs.building_id = b.bin
        LEFT JOIN carbon_estimates ce ON ce.building_id = b.bin
        WHERE b.bin = ?
        """,
        (bin_val,),
    ).fetchone()
    return dict(row) if row else None


def get_violations(
    conn: sqlite3.Connection,
    bin_val: str,
    limit: int | None = None,
) -> list[dict]:
    limit_sql = "LIMIT :limit" if limit is not None else ""
    params = {"bin": bin_val}
    if limit is not None:
        params["limit"] = limit
    rows = conn.execute(
        f"""
        SELECT source_dataset, issuing_agency, violation_number, violation_class,
               severity, issue_date, current_status, violation_description,
               penalty_imposed, balance_due, is_asbestos_related
        FROM building_violations
        WHERE building_id = :bin
        ORDER BY issue_date DESC
        {limit_sql}
        """,
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_energy(conn: sqlite3.Connection, bin_val: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT reporting_year, site_eui, energy_star_score,
               ghg_emissions_metric_tons_co2e, source_property_id
        FROM energy_emissions
        WHERE building_id = ?
        ORDER BY reporting_year DESC
        """,
        (bin_val,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_asbestos(
    conn: sqlite3.Connection,
    bin_val: str,
    limit: int | None = None,
) -> list[dict]:
    limit_sql = "LIMIT :limit" if limit is not None else ""
    params = {"bin": bin_val}
    if limit is not None:
        params["limit"] = limit
    rows = conn.execute(
        f"""
        SELECT control_number, project_status, project_start_date,
               project_end_date, contractor_name, air_monitor_name
        FROM asbestos_projects
        WHERE building_id = :bin
        ORDER BY project_start_date DESC
        {limit_sql}
        """,
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def run_sql(conn: sqlite3.Connection, sql: str) -> tuple[list[str], list[dict]]:
    stripped = sql.strip().lstrip(";").strip()
    if not stripped.upper().startswith("SELECT"):
        raise ValueError("Only SELECT statements are allowed.")
    cursor = conn.execute(stripped)
    cols = [d[0] for d in cursor.description] if cursor.description else []
    rows = [dict(r) for r in cursor.fetchall()]
    return cols, rows


def stats_summary(conn: sqlite3.Connection) -> dict:
    def one(sql):
        return conn.execute(sql).fetchone()[0] or 0

    return {
        "buildings":              one("SELECT COUNT(*) FROM buildings"),
        "crosswalk":              one("SELECT COUNT(*) FROM building_crosswalk"),
        "violations":             one("SELECT COUNT(*) FROM building_violations"),
        "asbestos_violations":    one("SELECT COUNT(*) FROM building_violations WHERE is_asbestos_related=1"),
        "asbestos_projects":      one("SELECT COUNT(*) FROM asbestos_projects"),
        "energy_rows":            one("SELECT COUNT(*) FROM energy_emissions"),
        "buildings_with_energy":  one("SELECT COUNT(DISTINCT building_id) FROM energy_emissions"),
        "carbon_estimates":       one("SELECT COUNT(*) FROM carbon_estimates"),
        "risk_scored":            one("SELECT COUNT(*) FROM building_risk_scores"),
        "high_risk":              one("SELECT COUNT(*) FROM building_risk_scores WHERE risk_label IN ('High','Critical')"),
    }


def carbon_source_counts(conn: sqlite3.Connection) -> dict:
    """Count carbon_estimates rows grouped by eui_source for confidence UI."""
    rows = conn.execute(
        """
        SELECT eui_source, COUNT(*) AS n
        FROM carbon_estimates
        GROUP BY eui_source
        """
    ).fetchall()
    by_source = {r["eui_source"]: r["n"] for r in rows if r["eui_source"]}
    measured = by_source.get("measured", 0)
    class_median = by_source.get("class_median", 0)
    borough_median = by_source.get("borough_median", 0)
    return {
        "measured": measured,
        "class_median": class_median,
        "borough_median": borough_median,
        "total": measured + class_median + borough_median,
    }


def data_health_summary(conn: sqlite3.Connection) -> dict:
    """Return product-facing data health checks for frontend/debug surfaces."""
    expected_tables = [
        "building_crosswalk",
        "buildings",
        "building_profiles",
        "building_violations",
        "asbestos_projects",
        "energy_emissions",
        "carbon_estimates",
        "building_risk_scores",
        "building_footprints",
    ]

    table_counts: dict[str, int | None] = {}
    for table in expected_tables:
        try:
            table_counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except Exception:
            table_counts[table] = None

    def safe_one(sql: str) -> int | None:
        try:
            row = conn.execute(sql).fetchone()
            return int(row[0] or 0) if row else None
        except Exception:
            return None

    return {
        "tables": table_counts,
        "map_readiness": {
            "buildings_with_coordinates": safe_one(
                "SELECT COUNT(*) FROM buildings WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
            ),
            "buildings_with_footprints": safe_one(
                "SELECT COUNT(DISTINCT bin) FROM building_footprints"
            ),
            "buildings_with_scores": safe_one(
                "SELECT COUNT(*) FROM building_risk_scores WHERE risk_score IS NOT NULL"
            ),
            "buildings_with_carbon_estimates": safe_one(
                "SELECT COUNT(*) FROM carbon_estimates"
            ),
        },
        "known_gaps": [
            "Manhattan energy/emissions ingestion is not complete yet.",
            "Some frontend copy and viewport defaults may still be Queens-first.",
            "API consumers should treat null scores, carbon estimates, and geometry as expected states.",
        ],
    }


def buildings_geojson(
    conn: sqlite3.Connection,
    q: str = "",
    limit: int = 5000,
    zip_code: str = "",
    building_class: str = "",
    year_min: int | None = None,
    year_max: int | None = None,
    risk_label: str = "",
    has_asbestos: bool = False,
) -> dict:
    """
    Return a GeoJSON FeatureCollection of buildings with lat/lon.
    Used by the Leaflet map. Only includes buildings with coordinates.
    """
    # Include buildings that have either a real footprint polygon or lat/lon
    # coordinates. A building with a footprint but missing lat/lon is still
    # mappable; a building with neither is not.
    where_parts = [
        "(bf.geom IS NOT NULL OR (b.latitude IS NOT NULL AND b.longitude IS NOT NULL))"
    ]
    params: dict = {"limit": limit}

    if q:
        where_parts.append(
            "(b.bin = :q OR b.bbl = :q OR b.zip_code = :q OR b.full_address ILIKE :like)"
        )
        params["q"] = q
        params["like"] = f"%{q}%"

    if zip_code:
        where_parts.append("b.zip_code = :zip_code")
        params["zip_code"] = zip_code

    if building_class:
        where_parts.append("bp.building_class LIKE :building_class")
        params["building_class"] = f"{building_class}%"

    if year_min is not None:
        where_parts.append("bp.year_built >= :year_min")
        params["year_min"] = year_min

    if year_max is not None:
        where_parts.append("bp.year_built <= :year_max")
        params["year_max"] = year_max

    if risk_label:
        where_parts.append("rs.risk_label = :risk_label")
        params["risk_label"] = risk_label

    if has_asbestos:
        where_parts.append(
            "EXISTS (SELECT 1 FROM building_violations v WHERE v.building_id = b.bin AND v.is_asbestos_related=1)"
        )

    where_sql = "WHERE " + " AND ".join(where_parts)

    rows = conn.execute(
        f"""
        SELECT b.bin, b.full_address, b.zip_code, b.latitude, b.longitude,
               bp.year_built, bp.building_class, bp.building_area,
               rs.risk_score, rs.risk_label,
               ce.estimated_ghg_metric_tons, ce.eui_source,
               (SELECT COUNT(*) FROM building_violations v WHERE v.building_id = b.bin) AS violation_count,
               (SELECT COUNT(*) FROM building_violations v WHERE v.building_id = b.bin AND v.is_asbestos_related=1) AS asbestos_count,
               ST_AsGeoJSON(bf.geom) AS geom_json
        FROM buildings b
        LEFT JOIN building_profiles bp ON bp.building_id = b.bin
        LEFT JOIN building_risk_scores rs ON rs.building_id = b.bin
        LEFT JOIN carbon_estimates ce ON ce.building_id = b.bin
        LEFT JOIN LATERAL (
            SELECT geom
            FROM building_footprints
            WHERE bin = b.bin
            ORDER BY ST_Area(geom) DESC
            LIMIT 1
        ) bf ON TRUE
        {where_sql}
        ORDER BY rs.risk_score DESC NULLS LAST
        LIMIT :limit
        """,
        params,
    ).fetchall()

    features = []
    for r in rows:
        geom_json = r["geom_json"]
        if geom_json:
            geometry = json.loads(geom_json)
        else:
            geometry = {
                "type": "Point",
                "coordinates": [r["longitude"], r["latitude"]],
            }
        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "bin":           r["bin"],
                "address":       r["full_address"] or "",
                "zip":           r["zip_code"] or "",
                "year_built":    r["year_built"],
                "building_class": r["building_class"] or "",
                "building_area": r["building_area"],
                "risk_score":    r["risk_score"],
                "risk_label":    r["risk_label"] or "Unscored",
                "ghg":           round(float(r["estimated_ghg_metric_tons"]), 1) if r["estimated_ghg_metric_tons"] else None,
                "ghg_source":    r["eui_source"] or "",
                "violations":    r["violation_count"],
                "asbestos":      r["asbestos_count"],
            },
        })

    return {"type": "FeatureCollection", "features": features}
