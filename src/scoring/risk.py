"""
Risk scoring logic — populates building_risk_scores.

Point-weighted algorithm:

  AGE (max 3)
    year_built < 1940              +3   (high asbestos-era construction)
    1940 ≤ year_built < 1978       +2   (pre-EPA asbestos regulations)
    1978 ≤ year_built < 2000       +1

  VIOLATIONS
    Open / Active violations        +1 each, capped at 8
    Asbestos-related violations     +2 each, capped at 6
    HPD Class C violations          +1 each, capped at 4
    Balance due > $0               +1, capped at 3

  ASBESTOS PROJECTS
    ACP-7 confirmed projects        +3 each, capped at 9

  ENERGY / EMISSIONS
    Modelled only (no LL84 data)   +1   (less certainty, often older stock)
    GHG > 2× class median          +2
    GHG > class median             +1

  LABELS
    0–3   → Low
    4–9   → Moderate
    10–18 → High
    19+   → Critical

  CONFIDENCE
    High:   has PLUTO profile + (violations OR energy data)
    Medium: has PLUTO profile, no other data
    Low:    missing PLUTO profile
"""

import sqlite3
from datetime import datetime, timezone

from psycopg2.extras import execute_values


def _label(score: int) -> str:
    if score <= 3:   return "Low"
    if score <= 9:   return "Moderate"
    if score <= 18:  return "High"
    return "Critical"


def _confidence(has_profile: bool, has_violations: bool, has_energy: bool) -> str:
    if not has_profile:
        return "Low"
    if has_violations or has_energy:
        return "High"
    return "Medium"


def _cap(value: int, limit: int) -> int:
    return min(value, limit)


def run(conn: sqlite3.Connection) -> int:
    """Score all buildings and populate building_risk_scores. Returns count scored."""

    print("Computing class-median GHG intensities for relative scoring …")
    # Map: building_class → median GHG intensity (mt CO2e / ft²)
    class_medians: dict[str, float] = {}
    rows = conn.execute("""
        SELECT building_class, ghg_intensity
        FROM carbon_estimates
        WHERE eui_source = 'measured' AND ghg_intensity IS NOT NULL
          AND building_class IS NOT NULL AND building_class != ''
    """).fetchall()
    by_class: dict[str, list[float]] = {}
    for r in rows:
        by_class.setdefault(r[0], []).append(r[1])

    import statistics
    for bclass, vals in by_class.items():
        if len(vals) >= 3:
            class_medians[bclass] = statistics.median(vals)

    print(f"  Class medians available for {len(class_medians)} classes")

    # Load all buildings
    buildings = conn.execute("""
        SELECT b.bin,
               p.year_built, p.building_class, p.building_area,
               ce.estimated_ghg_metric_tons, ce.eui_source
        FROM buildings b
        LEFT JOIN building_profiles p ON p.building_id = b.bin
        LEFT JOIN carbon_estimates ce ON ce.building_id = b.bin
    """).fetchall()

    # Violations per building
    viol_map: dict[str, list] = {}
    for r in conn.execute("""
        SELECT building_id, current_status, is_asbestos_related,
               violation_class, source_dataset, balance_due
        FROM building_violations
    """).fetchall():
        viol_map.setdefault(r[0], []).append(dict(r))

    # Asbestos projects per building
    acp_counts: dict[str, int] = {}
    for r in conn.execute("SELECT building_id, COUNT(*) FROM asbestos_projects GROUP BY building_id").fetchall():
        acp_counts[r[0]] = r[1]

    now = datetime.now(timezone.utc).isoformat()
    batch = []
    scored = 0

    for b in buildings:
        bin_val = b[0]
        year_built, bclass, area = b[1], b[2], b[3]
        est_ghg, eui_source = b[4], b[5]

        violations = viol_map.get(bin_val, [])
        acp_count  = acp_counts.get(bin_val, 0)
        has_profile = year_built is not None or bclass is not None

        score = 0
        detail_parts = []

        # ── Age ──────────────────────────────────────────────────────────────
        if year_built:
            if year_built < 1940:
                score += 3; detail_parts.append("pre-1940 (+3)")
            elif year_built < 1978:
                score += 2; detail_parts.append("pre-1978 (+2)")
            elif year_built < 2000:
                score += 1; detail_parts.append("pre-2000 (+1)")

        # ── Violations ───────────────────────────────────────────────────────
        open_v = sum(
            1 for v in violations
            if any(kw in (v["current_status"] or "").upper()
                   for kw in ("OPEN", "ACTIVE"))
        )
        asb_v = sum(1 for v in violations if v["is_asbestos_related"])
        hpd_c = sum(
            1 for v in violations
            if v["source_dataset"] == "HPD" and (v["violation_class"] or "") == "C"
        )
        bal_v = sum(
            1 for v in violations
            if v["balance_due"] and float(v["balance_due"]) > 0
        )

        pts_open = _cap(open_v, 8)
        pts_asb  = _cap(asb_v * 2, 6)
        pts_hpd  = _cap(hpd_c, 4)
        pts_bal  = _cap(bal_v, 3)
        score += pts_open + pts_asb + pts_hpd + pts_bal

        if open_v:   detail_parts.append(f"{open_v} open violations (+{pts_open})")
        if asb_v:    detail_parts.append(f"{asb_v} asbestos violations (+{pts_asb})")
        if hpd_c:    detail_parts.append(f"{hpd_c} HPD Class C (+{pts_hpd})")
        if bal_v:    detail_parts.append(f"balance due (+{pts_bal})")

        # ── Asbestos projects ─────────────────────────────────────────────────
        pts_acp = _cap(acp_count * 3, 9)
        score  += pts_acp
        if acp_count:
            detail_parts.append(f"{acp_count} ACP-7 projects (+{pts_acp})")

        # ── Energy / GHG ──────────────────────────────────────────────────────
        if eui_source == "modelled" or eui_source == "class_median" or eui_source == "borough_median":
            score += 1
            detail_parts.append("no measured LL84 data (+1)")
        elif est_ghg and bclass and bclass in class_medians and area and area > 0:
            measured_intensity = float(est_ghg) / float(area)
            median_intensity   = class_medians[bclass]
            if measured_intensity > 2 * median_intensity:
                score += 2; detail_parts.append("GHG >2× class median (+2)")
            elif measured_intensity > median_intensity:
                score += 1; detail_parts.append("GHG >class median (+1)")

        label      = _label(score)
        confidence = _confidence(
            has_profile,
            bool(violations),
            eui_source == "measured",
        )
        detail = "; ".join(detail_parts) if detail_parts else "no risk factors identified"

        batch.append((bin_val, score, label, confidence, detail, now))
        scored += 1

    raw_conn = conn._conn if hasattr(conn, "_conn") else conn
    cur = raw_conn.cursor()
    execute_values(
        cur,
        """
        INSERT INTO building_risk_scores
          (building_id, risk_score, risk_label, confidence_label, risk_detail, generated_at)
        VALUES %s
        ON CONFLICT (building_id) DO UPDATE SET
          risk_score = EXCLUDED.risk_score,
          risk_label = EXCLUDED.risk_label,
          confidence_label = EXCLUDED.confidence_label,
          risk_detail = EXCLUDED.risk_detail,
          generated_at = EXCLUDED.generated_at
        """,
        batch,
        page_size=2000,
    )
    cur.close()
    conn.commit()

    # Print distribution
    dist: dict[str, int] = {}
    for _, _, label, *_ in batch:
        dist[label] = dist.get(label, 0) + 1
    print(f"Risk scoring done: {scored:,} buildings scored")
    for lbl in ("Low", "Moderate", "High", "Critical"):
        print(f"  {lbl:<10} {dist.get(lbl, 0):>8,}")

    return scored
