import type { CSSProperties } from "react";
import {
  RISK_COLORS,
  RISK_LEGEND_ORDER,
  type BackendRiskLabel,
} from "./mapConfig";

const SHORT_LABELS: Record<BackendRiskLabel, string> = {
  Low: "Low",
  Moderate: "Mod.",
  High: "High",
  Critical: "Crit.",
  Unscored: "—",
};

export function MapLegend() {
  return (
    <div style={styles.legend} aria-label="Risk legend">
      <span style={styles.title}>Risk</span>
      <ul style={styles.list}>
        {RISK_LEGEND_ORDER.map((key: BackendRiskLabel) => (
          <li key={key} style={styles.item}>
            <span
              style={{ ...styles.swatch, backgroundColor: RISK_COLORS[key] }}
              aria-hidden
            />
            <span style={styles.label}>{SHORT_LABELS[key]}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  legend: {
    position: "absolute",
    bottom: 14,
    left: 12,
    zIndex: 10,
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "7px 12px",
    borderRadius: 10,
    background: "rgba(14, 17, 22, 0.88)",
    backdropFilter: "blur(12px)",
    border: "1px solid rgba(255, 255, 255, 0.07)",
    boxShadow: "0 6px 24px rgba(0, 0, 0, 0.32)",
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    color: "#E8ECF0",
    pointerEvents: "none",
  },
  title: {
    fontSize: 10,
    fontWeight: 600,
    letterSpacing: "0.07em",
    textTransform: "uppercase" as const,
    color: "#7D8794",
    flexShrink: 0,
  },
  list: {
    listStyle: "none",
    margin: 0,
    padding: 0,
    display: "flex",
    flexWrap: "wrap" as const,
    alignItems: "center",
    gap: "6px 10px",
  },
  item: {
    display: "flex",
    alignItems: "center",
    gap: 5,
  },
  swatch: {
    width: 10,
    height: 10,
    borderRadius: 2,
    flexShrink: 0,
    boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.12)",
  },
  label: {
    fontSize: 11,
    fontWeight: 500,
    color: "#B8C2CC",
  },
};
