"""
Carbon estimate logic.

For buildings WITH measured LL84/97 data: record the actual GHG and EUI.
For buildings WITHOUT: derive a class-level GHG intensity (mt CO2e / ft²) from
peer buildings in the same building_class, then multiply by area.

Fallback chain:
  1. class median intensity (same building_class, ≥3 peers)
  2. borough-wide median intensity (all Queens buildings with measured data)
  3. None (insufficient data)
"""

import sqlite3
import statistics
from datetime import datetime, timezone

from psycopg2.extras import execute_values


def _median(values: list[float]) -> float | None:
    clean = [v for v in values if v is not None and v > 0]
    return statistics.median(clean) if len(clean) >= 1 else None


def _build_intensity_map(conn: sqlite3.Connection) -> tuple[dict, float | None]:
    """
    Return (class_intensity_map, borough_median_intensity).
    class_intensity_map: {building_class: median_ghg_per_sqft}
    """
    rows = conn.execute("""
        SELECT p.building_class,
               e.ghg_emissions_metric_tons_co2e,
               p.building_area,
               e.site_eui
        FROM energy_emissions e
        JOIN building_profiles p ON p.building_id = e.building_id
        WHERE e.ghg_emissions_metric_tons_co2e IS NOT NULL
          AND p.building_area IS NOT NULL AND p.building_area > 0
          AND p.building_class IS NOT NULL AND p.building_class != ''
        ORDER BY e.reporting_year DESC
    """).fetchall()

    # Keep only the most recent row per building (reporting_year DESC order helps)
    seen: set[str] = set()
    by_class: dict[str, list] = {}
    all_intensities: list[float] = []

    for r in rows:
        bclass, ghg, area, eui = r[0], r[1], r[2], r[3]
        intensity = float(ghg) / float(area)
        # Sanity-check: skip extreme outliers (> 1 mt CO2e / ft² is unrealistic)
        if intensity <= 0 or intensity > 1:
            continue
        all_intensities.append(intensity)
        by_class.setdefault(bclass, []).append((intensity, eui))

    class_map: dict[str, dict] = {}
    for bclass, items in by_class.items():
        intensities = [i for i, _ in items]
        euis = [e for _, e in items if e is not None]
        if len(intensities) >= 3:
            class_map[bclass] = {
                "intensity": _median(intensities),
                "eui": _median(euis),
                "count": len(intensities),
            }

    borough_median = _median(all_intensities)
    return class_map, borough_median


def run(conn: sqlite3.Connection) -> tuple[int, int]:
    """
    Populate carbon_estimates for all buildings.
    Returns (measured_count, modelled_count).
    """
    print("Building GHG intensity map from measured data …")
    class_map, borough_median = _build_intensity_map(conn)
    print(f"  Class-level medians computed for {len(class_map)} building classes")
    if borough_median:
        print(f"  Borough-wide fallback intensity: {borough_median:.6f} mt CO2e/ft²")

    now = datetime.now(timezone.utc).isoformat()
    measured = 0
    modelled = 0
    skipped = 0

    buildings = conn.execute("""
        SELECT b.bin, p.building_class, p.building_area
        FROM buildings b
        LEFT JOIN building_profiles p ON p.building_id = b.bin
    """).fetchall()

    # Latest measured GHG per building
    measured_ghg = {
        r[0]: {"ghg": r[1], "eui": r[2]}
        for r in conn.execute("""
            SELECT building_id, ghg_emissions_metric_tons_co2e, site_eui
            FROM energy_emissions
            WHERE ghg_emissions_metric_tons_co2e IS NOT NULL
            ORDER BY reporting_year DESC
        """).fetchall()
    }

    batch = []
    for b in buildings:
        bin_val, bclass, area = b[0], b[1], b[2]

        if bin_val in measured_ghg:
            m = measured_ghg[bin_val]
            ghg = m["ghg"]
            eui = m["eui"]
            intensity = float(ghg) / float(area) if area and area > 0 else None
            batch.append((
                bin_val, bclass, area, "measured",
                eui, intensity, ghg, None, now,
            ))
            measured += 1
            continue

        if not area or area <= 0:
            skipped += 1
            continue

        # Modelled: class median → borough median
        if bclass and bclass in class_map:
            peer = class_map[bclass]
            intensity = peer["intensity"]
            eui = peer["eui"]
            peer_count = peer["count"]
            source = "class_median"
        elif borough_median:
            intensity = borough_median
            eui = None
            peer_count = None
            source = "borough_median"
        else:
            skipped += 1
            continue

        estimated_ghg = intensity * float(area)
        batch.append((
            bin_val, bclass, area, source,
            eui, intensity, estimated_ghg, peer_count, now,
        ))
        modelled += 1

    raw_conn = conn._conn if hasattr(conn, "_conn") else conn
    cur = raw_conn.cursor()
    execute_values(
        cur,
        """
        INSERT INTO carbon_estimates
          (building_id, building_class, building_area, eui_source,
           site_eui, ghg_intensity, estimated_ghg_metric_tons,
           peer_building_count, generated_at)
        VALUES %s
        ON CONFLICT (building_id) DO UPDATE SET
          building_class = EXCLUDED.building_class,
          building_area = EXCLUDED.building_area,
          eui_source = EXCLUDED.eui_source,
          site_eui = EXCLUDED.site_eui,
          ghg_intensity = EXCLUDED.ghg_intensity,
          estimated_ghg_metric_tons = EXCLUDED.estimated_ghg_metric_tons,
          peer_building_count = EXCLUDED.peer_building_count,
          generated_at = EXCLUDED.generated_at
        """,
        batch,
        page_size=2000,
    )
    cur.close()
    conn.commit()

    print(f"Carbon estimates done: {measured:,} measured, {modelled:,} modelled, {skipped:,} skipped (no area)")
    return measured, modelled
