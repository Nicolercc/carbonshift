import { useMemo, useState, type CSSProperties } from "react";
import {
  ghgConfidenceLabel,
  riskHeadline,
} from "./buildingInsights";
import type { BuildingFeature, BuildingFeatureCollection } from "./mapTypes";

interface MapSearchProps {
  buildings: BuildingFeatureCollection;
  onSelect: (building: BuildingFeature) => void;
}

export function MapSearch({ buildings, onSelect }: MapSearchProps) {
  const [query, setQuery] = useState("");
  const trimmedQuery = query.trim().toLowerCase();

  const results = useMemo(() => {
    if (!trimmedQuery) return [];

    return buildings.features
      .filter((feature) => {
        const props = feature.properties;
        const haystack = [
          props.address,
          props.bin,
          props.zip,
          props.building_class,
          props.risk_label,
        ]
          .join(" ")
          .toLowerCase();

        return haystack.includes(trimmedQuery);
      })
      .slice(0, 6);
  }, [buildings.features, trimmedQuery]);

  return (
    <div style={styles.shell}>
      <div style={styles.searchBox}>
        <span style={styles.searchIcon} aria-hidden>
          /
        </span>
        <input
          aria-label="Search buildings"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search address, BIN, ZIP, class"
          style={styles.input}
        />
        {query && (
          <button
            type="button"
            aria-label="Clear search"
            onClick={() => setQuery("")}
            style={styles.clearButton}
          >
            ×
          </button>
        )}
      </div>

      {trimmedQuery && (
        <div style={styles.resultsPanel}>
          {results.length > 0 ? (
            results.map((feature) => (
              <button
                key={feature.properties.id}
                type="button"
                style={styles.result}
                onClick={() => {
                  onSelect(feature);
                  setQuery(feature.properties.address);
                }}
              >
                <span style={styles.resultAddress}>
                  {feature.properties.address}
                </span>
                <span style={styles.resultMeta}>
                  {riskHeadline(feature.properties.risk_label)} ·{" "}
                  {ghgConfidenceLabel(feature.properties.ghg_source)}
                </span>
              </button>
            ))
          ) : (
            <p style={styles.emptyState}>No matching buildings in loaded data.</p>
          )}
        </div>
      )}
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  shell: {
    position: "absolute",
    top: 12,
    left: 12,
    zIndex: 11,
    width: 420,
    maxWidth: "calc(100vw - 48px)",
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    pointerEvents: "auto",
  },
  searchBox: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    minHeight: 44,
    padding: "0 12px",
    borderRadius: 12,
    background: "rgba(14, 17, 22, 0.9)",
    border: "1px solid rgba(255, 255, 255, 0.09)",
    boxShadow: "0 16px 40px rgba(0, 0, 0, 0.38)",
    backdropFilter: "blur(14px)",
  },
  searchIcon: {
    display: "grid",
    placeItems: "center",
    width: 20,
    height: 20,
    borderRadius: 6,
    background: "rgba(255, 255, 255, 0.07)",
    color: "#9AA5B1",
    fontSize: 14,
    fontWeight: 600,
    flexShrink: 0,
  },
  input: {
    flex: 1,
    minWidth: 0,
    height: 42,
    background: "transparent",
    border: "none",
    outline: "none",
    color: "#F2F5F8",
    fontSize: 14,
  },
  clearButton: {
    width: 26,
    height: 26,
    borderRadius: 8,
    border: "1px solid rgba(255, 255, 255, 0.08)",
    background: "rgba(255, 255, 255, 0.05)",
    color: "#9AA5B1",
    cursor: "pointer",
    fontSize: 18,
    lineHeight: 1,
  },
  resultsPanel: {
    marginTop: 8,
    overflow: "hidden",
    borderRadius: 12,
    background: "rgba(14, 17, 22, 0.94)",
    border: "1px solid rgba(255, 255, 255, 0.08)",
    boxShadow: "0 18px 48px rgba(0, 0, 0, 0.45)",
    backdropFilter: "blur(14px)",
  },
  result: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
    width: "100%",
    padding: "12px 14px",
    border: "none",
    borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
    background: "transparent",
    color: "#DDE3EA",
    textAlign: "left",
    cursor: "pointer",
  },
  resultAddress: {
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    fontSize: 13,
    fontWeight: 600,
  },
  resultMeta: {
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    fontSize: 11,
    color: "#8B949E",
  },
  emptyState: {
    margin: 0,
    padding: "12px 14px",
    color: "#8B949E",
    fontSize: 13,
  },
};
