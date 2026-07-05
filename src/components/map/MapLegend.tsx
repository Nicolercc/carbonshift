import type { CSSProperties } from "react";
import {
  RISK_COLORS,
  RISK_LEGEND_ORDER,
  RISK_LABELS,
  type BackendRiskLabel,
} from "./mapConfig";

export function MapLegend() {
  return (
    <div style={styles.legend}>
      <p style={styles.title}>Risk layer</p>
      <ul style={styles.list}>
        {RISK_LEGEND_ORDER.map((key: BackendRiskLabel) => (
          <li key={key} style={styles.item}>
            <span
              style={{ ...styles.swatch, backgroundColor: RISK_COLORS[key] }}
            />
            <span style={styles.label}>{RISK_LABELS[key]}</span>
          </li>
        ))}
      </ul>
      <p style={styles.note}>Height ≈ emissions · color = risk score</p>
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  legend: {
    position: "absolute",
    bottom: 20,
    left: 16,
    background: "rgba(14, 17, 22, 0.92)",
    backdropFilter: "blur(14px)",
    borderRadius: 12,
    border: "1px solid rgba(255, 255, 255, 0.07)",
    padding: "12px 14px",
    zIndex: 10,
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    color: "#E8ECF0",
    minWidth: 196,
    boxShadow: "0 8px 32px rgba(0, 0, 0, 0.35)",
  },
  title: {
    margin: "0 0 10px",
    fontSize: 11,
    fontWeight: 600,
    letterSpacing: "0.06em",
    textTransform: "uppercase" as const,
    color: "#7D8794",
  },
  list: {
    listStyle: "none",
    margin: 0,
    padding: 0,
    display: "flex",
    flexDirection: "column" as const,
    gap: 7,
  },
  item: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  swatch: {
    width: 12,
    height: 12,
    borderRadius: 3,
    flexShrink: 0,
    boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.12)",
  },
  label: {
    fontSize: 13,
    fontWeight: 500,
    color: "#CDD5DE",
  },
  note: {
    margin: "12px 0 0",
    fontSize: 11,
    lineHeight: 1.45,
    color: "#7D8794",
    maxWidth: 220,
  },
};
