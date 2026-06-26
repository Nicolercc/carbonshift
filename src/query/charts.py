"""
Functions that return Chart.js-ready data dicts.
All return plain Python dicts/lists — JSON-serialised by the caller.
"""

import sqlite3


def _rows(conn, sql, *params):
    return conn.execute(sql, params).fetchall()


# ── dataset-level charts ──────────────────────────────────────────────────────

def violations_by_source(conn: sqlite3.Connection) -> dict:
    rows = _rows(conn, """
        SELECT source_dataset, COUNT(*) AS n
        FROM building_violations
        GROUP BY source_dataset
        ORDER BY n DESC
    """)
    labels = [r[0] for r in rows]
    data   = [r[1] for r in rows]
    return {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Violations",
                "data": data,
                "backgroundColor": ["#198754","#ffc107","#dc3545","#0d6efd","#6c757d"],
            }],
        },
        "options": {
            "indexAxis": "y",
            "plugins": {"legend": {"display": False},
                        "title": {"display": True, "text": "Violations by Source Dataset"}},
            "responsive": True,
        },
    }


def buildings_by_decade(conn: sqlite3.Connection) -> dict:
    rows = _rows(conn, """
        SELECT (year_built / 10) * 10 AS decade, COUNT(*) AS n
        FROM building_profiles
        WHERE year_built IS NOT NULL AND year_built > 1800 AND year_built <= 2030
        GROUP BY decade
        ORDER BY decade
    """)
    labels = [f"{r[0]}s" for r in rows]
    data   = [r[1] for r in rows]
    return {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Buildings",
                "data": data,
                "backgroundColor": "#2d6a4f",
                "borderRadius": 4,
            }],
        },
        "options": {
            "plugins": {"legend": {"display": False},
                        "title": {"display": True, "text": "Buildings by Decade Built"}},
            "responsive": True,
        },
    }


def building_class_distribution(conn: sqlite3.Connection) -> dict:
    rows = _rows(conn, """
        SELECT building_class, COUNT(*) AS n
        FROM building_profiles
        WHERE building_class IS NOT NULL AND building_class != ''
        GROUP BY building_class
        ORDER BY n DESC
        LIMIT 15
    """)
    labels = [r[0] for r in rows]
    data   = [r[1] for r in rows]
    colors = [
        "#2d6a4f","#40916c","#52b788","#74c69d","#95d5b2",
        "#b7e4c7","#d8f3dc","#1b4332","#081c15","#6c757d",
        "#adb5bd","#dee2e6","#f8f9fa","#198754","#20c997",
    ]
    return {
        "type": "doughnut",
        "data": {
            "labels": labels,
            "datasets": [{"data": data, "backgroundColor": colors[:len(data)]}],
        },
        "options": {
            "plugins": {"title": {"display": True, "text": "Top 15 Building Classes"},
                        "legend": {"position": "right"}},
            "responsive": True,
        },
    }


def top_ghg_emitters(conn: sqlite3.Connection, limit: int = 20) -> dict:
    rows = _rows(conn, """
        SELECT b.full_address, e.ghg_emissions_metric_tons_co2e, e.reporting_year
        FROM energy_emissions e
        JOIN buildings b ON b.bin = e.building_id
        WHERE e.ghg_emissions_metric_tons_co2e IS NOT NULL
        ORDER BY e.reporting_year DESC, e.ghg_emissions_metric_tons_co2e DESC
        LIMIT ?
    """, limit)
    labels = [r[0][:40] if r[0] else r[0] for r in rows]
    data   = [round(float(r[1]), 1) for r in rows]
    years  = sorted({r[2] for r in rows if r[2]})
    year_note = f" ({min(years)}–{max(years)})" if years else ""
    return {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "GHG (mt CO₂e)",
                "data": data,
                "backgroundColor": "#dc3545",
                "borderRadius": 4,
            }],
        },
        "options": {
            "indexAxis": "y",
            "plugins": {"legend": {"display": False},
                        "title": {"display": True,
                                  "text": f"Top {limit} GHG Emitters{year_note}"}},
            "responsive": True,
        },
    }


def energy_star_distribution(conn: sqlite3.Connection) -> dict:
    rows = _rows(conn, """
        SELECT (energy_star_score / 10) * 10 AS bucket, COUNT(*) AS n
        FROM energy_emissions
        WHERE energy_star_score IS NOT NULL
          AND energy_star_score >= 0 AND energy_star_score <= 100
        GROUP BY bucket
        ORDER BY bucket
    """)
    labels = [f"{r[0]}–{r[0]+9}" for r in rows]
    data   = [r[1] for r in rows]

    def _color(bucket):
        if bucket >= 75: return "#198754"
        if bucket >= 50: return "#ffc107"
        return "#dc3545"

    colors = [_color(r[0]) for r in rows]
    return {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Buildings",
                "data": data,
                "backgroundColor": colors,
                "borderRadius": 4,
            }],
        },
        "options": {
            "plugins": {"legend": {"display": False},
                        "title": {"display": True, "text": "Energy Star Score Distribution"}},
            "responsive": True,
        },
    }


def violations_over_time(conn: sqlite3.Connection) -> dict:
    rows = _rows(conn, """
        SELECT SUBSTR(issue_date, 1, 4) AS yr, source_dataset, COUNT(*) AS n
        FROM building_violations
        WHERE issue_date IS NOT NULL AND LENGTH(issue_date) >= 4
          AND SUBSTR(issue_date,1,4) GLOB '[0-9][0-9][0-9][0-9]'
          AND CAST(SUBSTR(issue_date,1,4) AS INTEGER) BETWEEN 1970 AND 2030
        GROUP BY yr, source_dataset
        ORDER BY yr
    """)
    sources = sorted({r[1] for r in rows})
    years   = sorted({r[0] for r in rows})
    data_map = {(r[0], r[1]): r[2] for r in rows}

    src_colors = {
        "HPD":        "#0d6efd",
        "DOB_SAFETY": "#198754",
        "DOB_LEGACY": "#ffc107",
        "DOB_ECB":    "#dc3545",
    }
    datasets = []
    for src in sources:
        datasets.append({
            "label": src,
            "data": [data_map.get((yr, src), 0) for yr in years],
            "borderColor": src_colors.get(src, "#6c757d"),
            "backgroundColor": src_colors.get(src, "#6c757d") + "33",
            "fill": False,
            "tension": 0.3,
            "pointRadius": 2,
        })
    return {
        "type": "line",
        "data": {"labels": years, "datasets": datasets},
        "options": {
            "plugins": {"title": {"display": True, "text": "Violations Filed Per Year by Agency"}},
            "scales": {"y": {"beginAtZero": True}},
            "responsive": True,
        },
    }


def asbestos_by_status(conn: sqlite3.Connection) -> dict:
    rows = _rows(conn, """
        SELECT project_status, COUNT(*) AS n
        FROM asbestos_projects
        WHERE project_status IS NOT NULL AND project_status != ''
        GROUP BY project_status
        ORDER BY n DESC
    """)
    labels = [r[0] for r in rows]
    data   = [r[1] for r in rows]
    colors = ["#dc3545","#fd7e14","#ffc107","#198754","#0d6efd","#6c757d"]
    return {
        "type": "doughnut",
        "data": {
            "labels": labels,
            "datasets": [{"data": data, "backgroundColor": colors[:len(data)]}],
        },
        "options": {
            "plugins": {"title": {"display": True, "text": "Asbestos Projects by Status"},
                        "legend": {"position": "right"}},
            "responsive": True,
        },
    }


def ghg_by_building_class(conn: sqlite3.Connection) -> dict:
    rows = _rows(conn, """
        SELECT p.building_class,
               ROUND(AVG(e.ghg_emissions_metric_tons_co2e), 1) AS avg_ghg,
               COUNT(*) AS n
        FROM energy_emissions e
        JOIN building_profiles p ON p.building_id = e.building_id
        WHERE e.ghg_emissions_metric_tons_co2e IS NOT NULL
          AND p.building_class IS NOT NULL AND p.building_class != ''
        GROUP BY p.building_class
        HAVING n >= 3
        ORDER BY avg_ghg DESC
        LIMIT 15
    """)
    labels = [f"{r[0]} (n={r[2]})" for r in rows]
    data   = [r[1] for r in rows]
    return {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Avg GHG (mt CO₂e)",
                "data": data,
                "backgroundColor": "#6610f2",
                "borderRadius": 4,
            }],
        },
        "options": {
            "indexAxis": "y",
            "plugins": {"legend": {"display": False},
                        "title": {"display": True, "text": "Avg GHG by Building Class"}},
            "responsive": True,
        },
    }


# ── per-building charts ───────────────────────────────────────────────────────

def building_ghg_trend(conn: sqlite3.Connection, bin_val: str) -> dict | None:
    rows = _rows(conn, """
        SELECT reporting_year, ghg_emissions_metric_tons_co2e, site_eui, energy_star_score
        FROM energy_emissions
        WHERE building_id = ? AND reporting_year IS NOT NULL
        ORDER BY reporting_year
    """, bin_val)
    if not rows:
        return None
    years  = [r[0] for r in rows]
    ghg    = [round(float(r[1]), 2) if r[1] is not None else None for r in rows]
    eui    = [round(float(r[2]), 2) if r[2] is not None else None for r in rows]
    return {
        "type": "line",
        "data": {
            "labels": years,
            "datasets": [
                {
                    "label": "GHG Emissions (mt CO₂e)",
                    "data": ghg,
                    "borderColor": "#dc3545",
                    "backgroundColor": "#dc354533",
                    "yAxisID": "y",
                    "tension": 0.3,
                    "fill": True,
                },
                {
                    "label": "Site EUI (kBtu/ft²)",
                    "data": eui,
                    "borderColor": "#0d6efd",
                    "backgroundColor": "transparent",
                    "yAxisID": "y1",
                    "tension": 0.3,
                    "borderDash": [5, 3],
                },
            ],
        },
        "options": {
            "responsive": True,
            "interaction": {"mode": "index", "intersect": False},
            "plugins": {"title": {"display": True, "text": "GHG Emissions & EUI Over Time"}},
            "scales": {
                "y":  {"type": "linear", "position": "left",  "title": {"display": True, "text": "GHG (mt CO₂e)"}},
                "y1": {"type": "linear", "position": "right", "title": {"display": True, "text": "EUI (kBtu/ft²)"},
                       "grid": {"drawOnChartArea": False}},
            },
        },
    }


def building_violations_breakdown(conn: sqlite3.Connection, bin_val: str) -> dict | None:
    rows = _rows(conn, """
        SELECT source_dataset, COUNT(*) AS n
        FROM building_violations
        WHERE building_id = ?
        GROUP BY source_dataset
        ORDER BY n DESC
    """, bin_val)
    if not rows:
        return None
    labels = [r[0] for r in rows]
    data   = [r[1] for r in rows]
    colors = ["#0d6efd","#198754","#ffc107","#dc3545","#6c757d"]
    return {
        "type": "doughnut",
        "data": {
            "labels": labels,
            "datasets": [{"data": data, "backgroundColor": colors[:len(data)]}],
        },
        "options": {
            "plugins": {"title": {"display": True, "text": "Violations by Source"},
                        "legend": {"position": "bottom"}},
            "responsive": True,
        },
    }


def auto_chart_from_rows(cols: list[str], rows: list[dict]) -> dict | None:
    """
    Best-effort chart from arbitrary SQL results.
    Picks the first text column as labels, all numeric columns as datasets.
    Returns None if no chartable structure is detected.
    """
    if not rows or len(cols) < 2:
        return None

    def _is_numeric(col):
        vals = [r[col] for r in rows if r[col] is not None]
        if not vals:
            return False
        try:
            [float(v) for v in vals]
            return True
        except (ValueError, TypeError):
            return False

    label_col = cols[0]
    num_cols   = [c for c in cols[1:] if _is_numeric(c)]
    if not num_cols:
        return None

    labels = [str(r[label_col] or "") for r in rows]
    palette = ["#198754","#0d6efd","#dc3545","#ffc107","#6610f2","#fd7e14","#6c757d"]
    datasets = []
    for i, nc in enumerate(num_cols):
        data = [float(r[nc]) if r[nc] is not None else 0 for r in rows]
        datasets.append({
            "label": nc,
            "data": data,
            "backgroundColor": palette[i % len(palette)],
            "borderRadius": 4,
        })

    chart_type = "bar" if len(rows) <= 30 else "line"
    return {
        "type": chart_type,
        "data": {"labels": labels, "datasets": datasets},
        "options": {
            "responsive": True,
            "indexAxis": "y" if len(rows) > 10 and len(num_cols) == 1 else "x",
            "plugins": {"title": {"display": False}},
            "scales": {"y": {"beginAtZero": True}},
        },
    }
