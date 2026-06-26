import csv
import io
import json
import os
import pathlib

from flask import Flask, render_template, request, redirect, url_for, Response, flash, jsonify
from dotenv import load_dotenv

load_dotenv()

from src.db.init_db import get_connection, init_db
from src.query.lookup import (
    search_buildings, get_building, get_violations,
    get_energy, get_asbestos, run_sql, stats_summary,
    buildings_geojson,
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
app = Flask(__name__, template_folder=TEMPLATE_DIR)
app.secret_key = os.getenv("FLASK_SECRET", "carbonshift-dev")


def _conn():
    return get_connection()


def _json(obj) -> str:
    return json.dumps(obj, default=str)


def _int_or_none(val) -> int | None:
    try:
        return int(val) if val else None
    except (ValueError, TypeError):
        return None


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
def charts():
    conn = _conn()
    try:
        tab = request.args.get("tab", "overview")
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


@app.route("/map")
def map_view():
    """Standalone full-map page."""
    filters = _filter_args()
    q = request.args.get("q", "").strip()
    return render_template("map.html", q=q, filters=filters)


# ── API ───────────────────────────────────────────────────────────────────────

@app.route("/api/buildings.geojson")
def api_buildings_geojson():
    q = request.args.get("q", "").strip()
    limit = min(_int_or_none(request.args.get("limit")) or 5000, 10000)
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
        _, rows = run_sql(conn, f"""
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
            WHERE b.bin = '{bin_val}'
        """)
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
