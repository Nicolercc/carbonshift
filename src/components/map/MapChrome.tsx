import type { CSSProperties } from "react";
import { DEMO_BIN } from "./mapConfig";
import type { MapDataSource } from "./mapTypes";
import { dataSourceLabel } from "./buildingDataAdapter";

interface MapChromeProps {
  dataSource: MapDataSource;
  buildingCount: number;
  onDemoSelect?: () => void;
}

/** Map-local status strip — Flask navbar owns global navigation. */
export function MapChrome({
  dataSource,
  buildingCount,
  onDemoSelect,
}: MapChromeProps) {
  const isLive = dataSource === "live";
  const isLoading = dataSource === "loading";
  const isError = dataSource === "error";

  return (
    <div style={styles.bar}>
      {onDemoSelect && !isLoading && (
        <button type="button" style={styles.demoButton} onClick={onDemoSelect}>
          Demo BIN
        </button>
      )}
      {!isLoading && !isError && (
        <span style={styles.countBadge}>
          {buildingCount.toLocaleString()} buildings
        </span>
      )}
      <span
        style={{
          ...styles.sourceBadge,
          ...(isLive ? styles.sourceLive : {}),
          ...(isError ? styles.sourceError : {}),
          ...(!isLive && !isError && !isLoading ? styles.sourceDemo : {}),
          ...(isLoading ? styles.sourceLoading : {}),
        }}
        title={isLive ? `Demo BIN ${DEMO_BIN} auto-loads on start` : undefined}
      >
        {isLive && <span style={styles.liveDot} aria-hidden />}
        {dataSourceLabel(dataSource)}
      </span>
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  bar: {
    position: "absolute",
    top: 12,
    right: 12,
    zIndex: 10,
    display: "flex",
    alignItems: "center",
    gap: 8,
    pointerEvents: "auto",
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },
  demoButton: {
    fontSize: 12,
    fontWeight: 600,
    letterSpacing: "0.02em",
    padding: "7px 11px",
    borderRadius: 8,
    border: "1px solid rgba(110, 207, 196, 0.3)",
    background: "rgba(110, 207, 196, 0.1)",
    color: "#6ECFC4",
    cursor: "pointer",
  },
  countBadge: {
    fontSize: 13,
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
  sourceError: {
    background: "rgba(158, 74, 74, 0.14)",
    color: "#E8B4B4",
    borderColor: "rgba(158, 74, 74, 0.28)",
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
