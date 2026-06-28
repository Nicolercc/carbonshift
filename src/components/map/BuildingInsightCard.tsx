import type { CSSProperties } from "react";
import type { BuildingProperties } from "./mapTypes";
import type { BackendRiskLabel } from "./mapConfig";
import { RISK_COLORS } from "./mapConfig";
import {
  formatBuildingArea,
  formatGhg,
  ghgConfidenceLabel,
  riskHeadline,
} from "./buildingInsights";

interface BuildingInsightCardProps {
  building: BuildingProperties;
  onClose: () => void;
}

export function BuildingInsightCard({
  building,
  onClose,
}: BuildingInsightCardProps) {
  const accent = RISK_COLORS[building.risk_label as BackendRiskLabel];

  return (
    <div style={styles.card} role="dialog" aria-label="Building insight">
      <button
        type="button"
        onClick={onClose}
        style={styles.closeButton}
        aria-label="Close"
      >
        ×
      </button>

      <div style={{ ...styles.accentBar, backgroundColor: accent }} />

      <p style={styles.eyebrow}>Building intelligence</p>
      <h2 style={styles.headline}>{riskHeadline(building.risk_label)}</h2>

      <p style={styles.address}>{building.address}</p>
      <p style={styles.meta}>
        {building.zip ? `ZIP ${building.zip}` : "Queens, NYC"}
        {building.building_class ? ` · Class ${building.building_class}` : ""}
      </p>

      <div style={styles.metricsGrid}>
        <Metric
          label="Risk score"
          value={building.risk_score != null ? String(building.risk_score) : "—"}
        />
        <Metric label="Est. emissions" value={formatGhg(building.ghg)} />
        <Metric
          label="Year built"
          value={building.year_built != null ? String(building.year_built) : "—"}
        />
        <Metric
          label="Floor area"
          value={formatBuildingArea(building.building_area)}
        />
        <Metric
          label="Violations"
          value={String(building.violations)}
        />
        <Metric
          label="Emissions confidence"
          value={ghgConfidenceLabel(building.ghg_source)}
        />
      </div>

      {building.asbestos > 0 && (
        <div style={styles.alert}>
          {building.asbestos} asbestos-related flag
          {building.asbestos === 1 ? "" : "s"} on record
        </div>
      )}

      <section style={styles.section}>
        <h3 style={styles.sectionTitle}>Primary driver</h3>
        <p style={styles.bodyText}>{building.primary_driver}</p>
      </section>

      <section style={styles.section}>
        <h3 style={styles.sectionTitle}>Suggested action</h3>
        <p style={styles.bodyText}>{building.suggested_action}</p>
      </section>

      <p style={styles.bin}>BIN {building.bin}</p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div style={styles.metric}>
      <span style={styles.metricLabel}>{label}</span>
      <span style={styles.metricValue}>{value}</span>
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  card: {
    position: "absolute",
    top: 72,
    right: 24,
    width: 360,
    maxWidth: "calc(100vw - 48px)",
    maxHeight: "calc(100vh - 96px)",
    overflowY: "auto",
    background: "rgba(14, 17, 22, 0.94)",
    backdropFilter: "blur(16px)",
    borderRadius: 14,
    border: "1px solid rgba(255, 255, 255, 0.07)",
    boxShadow: "0 24px 60px rgba(0, 0, 0, 0.5)",
    color: "#E8ECF0",
    padding: "20px 22px 18px",
    zIndex: 10,
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },
  accentBar: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: 3,
    borderRadius: "14px 14px 0 0",
  },
  closeButton: {
    position: "absolute",
    top: 10,
    right: 12,
    background: "transparent",
    border: "none",
    color: "#8B949E",
    fontSize: 22,
    lineHeight: 1,
    cursor: "pointer",
    padding: "4px 8px",
  },
  eyebrow: {
    margin: "0 0 4px",
    fontSize: 11,
    letterSpacing: "0.07em",
    textTransform: "uppercase" as const,
    color: "#7D8794",
  },
  headline: {
    margin: "0 0 12px",
    fontSize: 20,
    fontWeight: 600,
    lineHeight: 1.25,
    color: "#F2F5F8",
  },
  address: {
    margin: "0 0 2px",
    fontSize: 15,
    fontWeight: 500,
    color: "#DDE3EA",
  },
  meta: {
    margin: "0 0 16px",
    fontSize: 13,
    color: "#8B949E",
  },
  metricsGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 12,
    marginBottom: 14,
  },
  metric: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 2,
  },
  metricLabel: {
    fontSize: 10,
    color: "#7D8794",
    textTransform: "uppercase" as const,
    letterSpacing: "0.05em",
  },
  metricValue: {
    fontSize: 13,
    fontWeight: 500,
    color: "#E8ECF0",
    lineHeight: 1.35,
  },
  alert: {
    marginBottom: 14,
    padding: "8px 10px",
    borderRadius: 8,
    background: "rgba(158, 74, 74, 0.18)",
    border: "1px solid rgba(158, 74, 74, 0.35)",
    fontSize: 12,
    color: "#E8B4B4",
  },
  section: {
    marginBottom: 12,
  },
  sectionTitle: {
    margin: "0 0 4px",
    fontSize: 10,
    fontWeight: 600,
    letterSpacing: "0.06em",
    textTransform: "uppercase" as const,
    color: "#7D8794",
  },
  bodyText: {
    margin: 0,
    fontSize: 13,
    lineHeight: 1.55,
    color: "#B8C2CC",
  },
  bin: {
    margin: "8px 0 0",
    fontSize: 11,
    color: "#5C6670",
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
  },
};
