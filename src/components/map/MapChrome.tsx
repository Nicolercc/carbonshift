import type { CSSProperties } from "react";
import type { MapDataSource } from "./mapTypes";
import { dataSourceLabel } from "./buildingDataAdapter";

interface MapChromeProps {
  dataSource: MapDataSource;
  buildingCount: number;
}

export function MapChrome({ dataSource, buildingCount }: MapChromeProps) {
  const isLive = dataSource === "live";
  const isLoading = dataSource === "loading";

  return (
    <header style={styles.header}>
      <div style={styles.brand}>
        <span style={styles.logoMark} aria-hidden />
        <div>
          <p style={styles.productName}>CarbonShift</p>
          <p style={styles.tagline}>Queens building intelligence</p>
        </div>
      </div>

      <div style={styles.statusGroup}>
        {!isLoading && (
          <span style={styles.countBadge}>
            {buildingCount.toLocaleString()} buildings
          </span>
        )}
        <span
          style={{
            ...styles.sourceBadge,
            ...(isLive ? styles.sourceLive : styles.sourceDemo),
            ...(isLoading ? styles.sourceLoading : {}),
          }}
        >
          {isLive && <span style={styles.liveDot} aria-hidden />}
          {dataSourceLabel(dataSource)}
        </span>
      </div>
    </header>
  );
}

const styles: Record<string, CSSProperties> = {
  header: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    zIndex: 10,
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "14px 20px",
    background:
      "linear-gradient(180deg, rgba(8, 10, 14, 0.82) 0%, rgba(8, 10, 14, 0.45) 70%, transparent 100%)",
    pointerEvents: "none",
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },
  brand: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    pointerEvents: "auto",
  },
  logoMark: {
    width: 10,
    height: 10,
    borderRadius: "50%",
    background: "linear-gradient(135deg, #3DAA9E 0%, #2A7A72 100%)",
    boxShadow: "0 0 12px rgba(61, 170, 158, 0.45)",
    flexShrink: 0,
  },
  productName: {
    margin: 0,
    fontSize: 15,
    fontWeight: 600,
    letterSpacing: "-0.01em",
    color: "#F2F5F8",
  },
  tagline: {
    margin: 0,
    fontSize: 11,
    color: "#8B949E",
    letterSpacing: "0.02em",
  },
  statusGroup: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    pointerEvents: "auto",
  },
  countBadge: {
    fontSize: 12,
    color: "#A8B2BD",
    padding: "5px 10px",
    borderRadius: 8,
    background: "rgba(14, 17, 22, 0.75)",
    border: "1px solid rgba(255, 255, 255, 0.06)",
  },
  sourceBadge: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    fontSize: 11,
    fontWeight: 500,
    letterSpacing: "0.03em",
    textTransform: "uppercase" as const,
    padding: "5px 10px",
    borderRadius: 8,
    border: "1px solid rgba(255, 255, 255, 0.08)",
  },
  sourceLive: {
    background: "rgba(61, 170, 158, 0.12)",
    color: "#6ECFC4",
    borderColor: "rgba(61, 170, 158, 0.25)",
  },
  sourceDemo: {
    background: "rgba(196, 160, 53, 0.1)",
    color: "#D4B85A",
    borderColor: "rgba(196, 160, 53, 0.22)",
  },
  sourceLoading: {
    background: "rgba(107, 117, 128, 0.12)",
    color: "#9AA5B1",
  },
  liveDot: {
    width: 6,
    height: 6,
    borderRadius: "50%",
    background: "#3DAA9E",
    boxShadow: "0 0 6px rgba(61, 170, 158, 0.8)",
  },
};
