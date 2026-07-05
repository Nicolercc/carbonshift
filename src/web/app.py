import csv
import io
import json
import os
import pathlib

from flask import Flask, render_template, request, redirect, url_for, Response, flash, jsonify, abort
from dotenv import load_dotenv

load_dotenv()

from src.db.init_db import get_connection, init_db
from src.query.lookup import (
    search_buildings, get_building, get_violations,
    get_energy, get_asbestos, run_sql, stats_summary,
    buildings_geojson, data_health_summary,
    carbon_source_counts,
)
from src.query.export import export_to_csv_string, EXPORT_QUERIES
from src.query.charts import (
    violations_by_source, buildings_by_decade, building_class_distribution,
    top_ghg_emitters, energy_star_distribution, violations_over_time,
    asbestos_by_status, ghg_by_building_class,
    building_ghg_trend, building_violations_breakdown,
    auto_chart_from_rows,
)

TEMPLATE_DIR = str(pathlib.Path(__file__).parent / "templates")
STATIC_DIR = str(pathlib.Path(__file__).parent / "static")
app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
_secret = os.getenv("FLASK_SECRET")
if not _secret:
    if os.getenv("FLASK_ENV") == "production":
        raise RuntimeError(
            "FLASK_SECRET must be set in production (set the FLASK_SECRET env var)"
        )
    _secret = "carbonshift-dev"
app.secret_key = _secret

# Presentation demo defaults — keep in sync with src/components/map/mapConfig.ts
DEMO_BIN = "1063355"
MAP_GEOJSON_DEFAULT_LIMIT = 2000


def _configured_cors_origins() -> set[str]:
    """Return explicit frontend origins allowed to call the JSON API."""
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "")
    return {origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()}


def _default_dev_cors_origins() -> set[str]:
    if os.getenv("FLASK_ENV") == "production":
        return set()
    return {
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    }


def _cors_origin_for(origin: str | None) -> str | None:
    if not origin:
        return None
    normalized = origin.rstrip("/")
    allowed = _configured_cors_origins() or _default_dev_cors_origins()
    if "*" in allowed and os.getenv("FLASK_ENV") != "production":
        return normalized
    if normalized in allowed:
        return normalized
    return None


@app.after_request
def add_cors_headers(response):
    """Allow a separate Next.js frontend to consume Flask JSON endpoints."""
    allowed_origin = _cors_origin_for(request.headers.get("Origin"))
    if allowed_origin:
        response.headers["Access-Control-Allow-Origin"] = allowed_origin
        response.headers["Access-Control-Allow-Credentials"] = "false"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers.add("Vary", "Origin")
    return response

MAP_MANIFEST_PATH = (
    pathlib.Path(__file__).parent / "static" / "map" / ".vite" / "manifest.json"
)
MAP_STATIC_BASE = "/static/map/"


@app.context_processor
def inject_nav():
    path = request.path
    return {
        "nav_path": path,
        "nav_insights": path in ("/charts", "/insights"),
        "nav_data_tools": path == "/query" or path.startswith("/export/"),
    }


def _load_map_bundle() -> dict | None:
    """Resolve hashed JS/CSS paths from the Vite build manifest."""
    if not MAP_MANIFEST_PATH.is_file():
        return None
    try:
        manifest = json.loads(MAP_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    entry = manifest.get("src/map-entry.tsx")
    if not entry:
        for key, value in manifest.items():
            if key.endswith("map-entry.tsx"):
                entry = value
                break
    if not entry or "file" not in entry:
        return None

    return {
        "js": MAP_STATIC_BASE + entry["file"],
        "css": [MAP_STATIC_BASE + href for href in entry.get("css", [])],
    }


def _conn():
    try:
        return get_connection()
    except RuntimeError as e:
        app.logger.error("Database unavailable: %s", e)
        abort(503)


def _json(obj) -> str:
    return json.dumps(obj, default=str)


def _int_or_none(val) -> int | None:
    try:
        return int(val) if val else None
    except (ValueError, TypeError):
        return None


def _limit_arg(default: int, maximum: int) -> int:
    requested = _int_or_none(request.args.get("limit")) or default
    return max(1, min(requested, maximum))


def _filter_args():
    """Extract advanced filter params from request.args."""
    return {
        "zip_code":       request.args.get("zip", "").strip(),
        "building_class": request.args.get("class", "").strip(),
        "year_min":       _int_or_none(request.args.get("year_min")),
        "year_max":       _int_or_none(request.args.get("year_max")),
        "has_violations": request.args.get("violations") == "1",
        "has_asbestos":   request.args.get("asbestos") == "1",
        "has_energy":     request.args.get("energy") == "1",
        "risk_label":     request.args.get("risk", "").strip(),
    }


def _is_api_request() -> bool:
    return request.path == "/api" or request.path.startswith("/api/")


@app.errorhandler(404)
def handle_not_found(error):
    if _is_api_request():
        return jsonify({"ok": False, "error": "Not found"}), 404
    return error


@app.errorhandler(503)
def handle_service_unavailable(error):
    if _is_api_request():
        return jsonify({"ok": False, "error": "Service unavailable"}), 503
    return error


@app.errorhandler(500)
def handle_internal_error(error):
    if _is_api_request():
        app.logger.error("Unhandled API error: %s", error)
        return jsonify({"ok": False, "error": "Internal server error"}), 500
    return error


# ── pages ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    conn = _conn()
    try:
        stats = stats_summary(conn)
    except Exception:
        stats = {}
    conn.close()
    return render_template("index.html", stats=stats)


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    filters = _filter_args()
    view = request.args.get("view", "table")  # 'table' | 'map'

    conn = _conn()
    results = search_buildings(conn, q, limit=500, **filters)
    conn.close()

    active_filters = {k: v for k, v in filters.items() if v}
    return render_template(
        "results.html",
        q=q,
        results=results,
        filters=filters,
        active_filters=active_filters,
        view=view,
    )


@app.route("/building/<bin_val>")
def building(bin_val):
    conn = _conn()
    bldg = get_building(conn, bin_val)
    if not bldg:
        conn.close()
        flash(f"No building found with BIN {bin_val}", "warning")
        return redirect(url_for("index"))

    violations  = get_violations(conn, bin_val)
    energy      = get_energy(conn, bin_val)
    asbestos    = get_asbestos(conn, bin_val)

    ghg_chart  = building_ghg_trend(conn, bin_val)
    viol_chart = building_violations_breakdown(conn, bin_val)
    conn.close()

    asbestos_count = sum(1 for v in violations if v["is_asbestos_related"])
    return render_template(
        "building.html",
        bldg=bldg,
        violations=violations,
        energy=energy,
        asbestos=asbestos,
        asbestos_count=asbestos_count,
        ghg_chart_json=_json(ghg_chart) if ghg_chart else None,
        viol_chart_json=_json(viol_chart) if viol_chart else None,
    )


@app.route("/query", methods=["GET", "POST"])
def query():
    cols, rows, error, sql, auto_chart_json = [], [], None, "", None

    if request.method == "POST":
        sql = request.form.get("sql", "").strip()
        if sql:
            conn = _conn()
            try:
                cols, rows = run_sql(conn, sql)
                chart = auto_chart_from_rows(cols, rows)
                if chart:
                    auto_chart_json = _json(chart)
            except ValueError as e:
                error = str(e)
            except Exception as e:
                error = f"Query error: {e}"
            finally:
                conn.close()

    return render_template(
        "query.html",
        sql=sql, cols=cols, rows=rows, error=error,
        auto_chart_json=auto_chart_json,
    )


@app.route("/charts")
@app.route("/insights")
def charts():
    tab = request.args.get("tab", "overview")
    if tab == "map":
        return redirect(url_for("map_view", **{k: v for k, v in request.args.items() if k != "tab"}))

    conn = _conn()
    try:
        chart_data = {
            "violations_by_source": _json(violations_by_source(conn)),
            "buildings_by_decade":  _json(buildings_by_decade(conn)),
            "building_class":       _json(building_class_distribution(conn)),
            "top_ghg":              _json(top_ghg_emitters(conn, 20)),
            "energy_star_dist":     _json(energy_star_distribution(conn)),
            "violations_over_time": _json(violations_over_time(conn)),
            "asbestos_by_status":   _json(asbestos_by_status(conn)),
            "ghg_by_class":         _json(ghg_by_building_class(conn)),
        }
        stats = stats_summary(conn)
    except Exception as e:
        chart_data = {}
        stats = {}
        flash(f"Chart data error: {e}", "danger")
    finally:
        conn.close()

    return render_template("charts.html", charts=chart_data, stats=stats, active_tab=tab)


@app.route("/methodology")
def methodology():
    conn = _conn()
    try:
        stats = stats_summary(conn)
    except Exception:
        stats = {}
    finally:
        conn.close()
    return render_template("methodology.html", stats=stats)


@app.route("/map")
def map_view():
    """Map page — Flask shell + MapLibre React island."""
    filters = _filter_args()
    q = request.args.get("q", "").strip()
    map_init = {
        "q": q,
        "zip": filters["zip_code"],
        "class": filters["building_class"],
        "year_min": filters["year_min"],
        "year_max": filters["year_max"],
        "risk": filters["risk_label"],
        "asbestos": filters["has_asbestos"],
        "limit": _int_or_none(request.args.get("limit")) or MAP_GEOJSON_DEFAULT_LIMIT,
        "demo_bin": DEMO_BIN,
    }
    conn = _conn()
    try:
        confidence = carbon_source_counts(conn)
    finally:
        conn.close()
    return render_template(
        "map.html",
        q=q,
        filters=filters,
        map_init=map_init,
        map_bundle=_load_map_bundle(),
        confidence=confidence,
    )


# ── API ───────────────────────────────────────────────────────────────────────

@app.route("/api/health")
def api_health():
    try:
        conn = get_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
    except Exception as e:
        return jsonify({
            "ok": False,
            "service": "carbonshift-api",
            "database": "unavailable",
            "error": str(e),
        }), 503

    return jsonify({
        "ok": True,
        "service": "carbonshift-api",
        "database": "ok",
    })


@app.route("/api/stats")
@app.route("/api/stats/summary")
def api_stats_summary():
    conn = _conn()
    try:
        stats = stats_summary(conn)
        carbon_sources = carbon_source_counts(conn)
    finally:
        conn.close()

    return jsonify({
        "stats": stats,
        "carbon_sources": carbon_sources,
    })


@app.route("/api/data-health")
def api_data_health():
    conn = _conn()
    try:
        health = data_health_summary(conn)
    finally:
        conn.close()

    return jsonify(health)


@app.route("/api/buildings/search")
def api_buildings_search():
    q = request.args.get("q", "").strip()
    filters = _filter_args()
    limit = _limit_arg(default=25, maximum=100)

    conn = _conn()
    try:
        results = search_buildings(conn, q, limit=limit, **filters)
    finally:
        conn.close()

    return jsonify({
        "query": q,
        "filters": {k: v for k, v in filters.items() if v},
        "count": len(results),
        "limit": limit,
        "results": results,
    })


def _risk_drivers(risk_detail: str | None) -> list[str]:
    if not risk_detail:
        return []
    normalized = str(risk_detail).replace(" · ", ";").replace("|", ";")
    return [part.strip() for part in normalized.split(";") if part.strip()]


def _building_detail_payload(conn, bin_val: str, record_limit: int) -> dict | None:
    building_row = get_building(conn, bin_val)
    if not building_row:
        return None

    violations = get_violations(conn, bin_val, limit=record_limit)
    energy = get_energy(conn, bin_val)
    asbestos = get_asbestos(conn, bin_val, limit=record_limit)
    asbestos_violation_count = sum(1 for v in violations if v.get("is_asbestos_related"))

    return {
        "building": building_row,
        "signals": {
            "risk": {
                "score": building_row.get("risk_score"),
                "label": building_row.get("risk_label") or "Unscored",
                "confidence": building_row.get("confidence_label"),
                "drivers": _risk_drivers(building_row.get("risk_detail")),
            },
            "carbon": {
                "estimated_ghg_metric_tons": building_row.get("estimated_ghg_metric_tons"),
                "eui_source": building_row.get("eui_source"),
                "site_eui": building_row.get("site_eui"),
                "peer_building_count": building_row.get("peer_building_count"),
            },
            "compliance": {
                "violation_count_returned": len(violations),
                "asbestos_related_violation_count_returned": asbestos_violation_count,
            },
            "asbestos": {
                "project_count_returned": len(asbestos),
                "has_asbestos_signal": asbestos_violation_count > 0 or len(asbestos) > 0,
            },
            "data_completeness": {
                "has_location": bool(building_row.get("latitude") and building_row.get("longitude")),
                "has_profile": bool(building_row.get("building_class") or building_row.get("building_area")),
                "has_risk_score": building_row.get("risk_score") is not None,
                "has_carbon_estimate": building_row.get("estimated_ghg_metric_tons") is not None,
            },
        },
        "records": {
            "violations": violations,
            "energy": energy,
            "asbestos": asbestos,
        },
        "record_limit": record_limit,
    }


@app.route("/api/buildings/<bin_val>")
def api_building_detail(bin_val):
    record_limit = _limit_arg(default=50, maximum=200)

    conn = _conn()
    try:
        payload = _building_detail_payload(conn, bin_val, record_limit)
    finally:
        conn.close()

    if not payload:
        return jsonify({"ok": False, "error": f"No building found with BIN {bin_val}"}), 404

    return jsonify(payload)


@app.route("/api/buildings.geojson")
def api_buildings_geojson():
    q = request.args.get("q", "").strip()
    limit = _limit_arg(default=MAP_GEOJSON_DEFAULT_LIMIT, maximum=10000)
    zip_code       = request.args.get("zip", "").strip()
    building_class = request.args.get("class", "").strip()
    year_min       = _int_or_none(request.args.get("year_min"))
    year_max       = _int_or_none(request.args.get("year_max"))
    risk_label     = request.args.get("risk", "").strip()
    has_asbestos   = request.args.get("asbestos") == "1"

    conn = _conn()
    try:
        gj = buildings_geojson(
            conn, q=q, limit=limit,
            zip_code=zip_code, building_class=building_class,
            year_min=year_min, year_max=year_max,
            risk_label=risk_label, has_asbestos=has_asbestos,
        )
    finally:
        conn.close()

    return Response(
        json.dumps(gj, default=str),
        mimetype="application/json",
        headers={"Cache-Control": "no-store"},
    )


@app.route("/api/score", methods=["POST"])
def api_score():
    """Trigger scoring pipeline (carbon + risk) from the web UI."""
    if os.getenv("FLASK_ENV") != "development":
        return jsonify({"ok": False, "error": "Scoring endpoint is disabled outside development"}), 403
    try:
        init_db()
        conn = _conn()
        from src.scoring import carbon as carbon_mod, risk as risk_mod
        measured, modelled = carbon_mod.run(conn)
        scored = risk_mod.run(conn)
        conn.close()
        return jsonify({
            "ok": True,
            "carbon_measured": measured,
            "carbon_modelled": modelled,
            "risk_scored": scored,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── exports ───────────────────────────────────────────────────────────────────

@app.route("/export/<name>.csv")
def export_csv(name):
    if name not in EXPORT_QUERIES:
        flash(f"Unknown export '{name}'", "danger")
        return redirect(url_for("index"))
    conn = _conn()
    try:
        content = export_to_csv_string(conn, name)
    finally:
        conn.close()
    return Response(
        content,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={name}.csv"},
    )


@app.route("/export/custom.csv", methods=["POST"])
def export_custom_csv():
    sql = request.form.get("sql", "").strip()
    if not sql:
        flash("No SQL provided", "warning")
        return redirect(url_for("query"))
    conn = _conn()
    try:
        content = export_to_csv_string(conn, "", custom_sql=sql)
    except ValueError as e:
        flash(str(e), "danger")
        conn.close()
        return redirect(url_for("query"))
    finally:
        conn.close()
    return Response(
        content,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=query_results.csv"},
    )


@app.route("/building/<bin_val>/export.csv")
def export_building_csv(bin_val):
    conn = _conn()
    try:
        cursor = conn.execute(
            """
            SELECT b.bin, b.bbl, b.full_address, b.zip_code,
                   bp.year_built, bp.building_class, bp.land_use,
                   bp.residential_units, bp.total_units,
                   bp.number_of_floors, bp.building_area,
                   rs.risk_score, rs.risk_label,
                   ce.estimated_ghg_metric_tons, ce.eui_source,
                   (SELECT COUNT(*) FROM building_violations v WHERE v.building_id = b.bin) AS violations,
                   (SELECT ghg_emissions_metric_tons_co2e FROM energy_emissions e
                    WHERE e.building_id = b.bin ORDER BY reporting_year DESC LIMIT 1) AS latest_measured_ghg
            FROM buildings b
            LEFT JOIN building_profiles bp ON bp.building_id = b.bin
            LEFT JOIN building_risk_scores rs ON rs.building_id = b.bin
            LEFT JOIN carbon_estimates ce ON ce.building_id = b.bin
            WHERE b.bin = ?
            """,
            (bin_val,),
        )
        rows = [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        flash(str(e), "danger")
        conn.close()
        return redirect(url_for("building", bin_val=bin_val))
    finally:
        conn.close()

    buf = io.StringIO()
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=building_{bin_val}.csv"},
    )
