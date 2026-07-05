import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import maplibregl, { type GeoJSONSource } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import { fetchBuildingDetail } from "./buildingDetail";
import { loadBuildings, resolveTargetBin } from "./buildingDataAdapter";
import { BuildingInsightCard } from "./BuildingInsightCard";
import { MapChrome } from "./MapChrome";
import { MapLegend } from "./MapLegend";
import { MapSearch } from "./MapSearch";
import {
  ghgConfidenceLabel,
  riskHeadline,
} from "./buildingInsights";
import {
  BUILDING_EXTRUSION_LAYER_ID,
  BUILDING_SOURCE_ID,
  DEMO_BIN,
  initialMapView,
  MAP_STYLE_FALLBACK_URL,
  MAP_STYLE_URL,
  SELECTED_BUILDING_LAYER_ID,
} from "./mapConfig";
import {
  createBuildingExtrusionLayer,
  createBuildingOutlineLayer,
  createSelectedBuildingLayer,
} from "./mapLayers";
import { sampleBuildings } from "./sampleBuildings";
import type {
  BuildingFeature,
  BuildingFeatureCollection,
  BuildingProperties,
  MapDataSource,
} from "./mapTypes";

const INTERACTIVE_LAYERS = [
  BUILDING_EXTRUSION_LAYER_ID,
  SELECTED_BUILDING_LAYER_ID,
];

function parseBuildingProperties(
  raw: GeoJSON.GeoJsonProperties,
): BuildingProperties | null {
  if (!raw || typeof raw.id !== "string") return null;
  return raw as BuildingProperties;
}

function applySelectionFilter(
  map: maplibregl.Map,
  buildingId: string | null,
) {
  if (!map.getLayer(SELECTED_BUILDING_LAYER_ID)) return;
  map.setFilter(
    SELECTED_BUILDING_LAYER_ID,
    buildingId ? ["==", ["get", "id"], buildingId] : ["==", ["get", "id"], ""],
  );
}

function applyBuildingsToMap(
  map: maplibregl.Map,
  data: BuildingFeatureCollection,
) {
  const source = map.getSource(BUILDING_SOURCE_ID) as GeoJSONSource | undefined;
  if (!source) return false;
  source.setData(data);
  return true;
}

function getFeatureCenter(feature: BuildingFeature): [number, number] {
  const ring = feature.geometry.coordinates[0];
  const points = ring.slice(0, -1);
  const sum = points.reduce(
    (acc, coord) => {
      acc.lng += coord[0];
      acc.lat += coord[1];
      return acc;
    },
    { lng: 0, lat: 0 },
  );

  return [sum.lng / points.length, sum.lat / points.length];
}

function flyToBuilding(map: maplibregl.Map, lngLat: [number, number]) {
  map.easeTo({
    center: lngLat,
    zoom: Math.max(map.getZoom(), 15.4),
    pitch: 62,
    bearing: map.getBearing(),
    duration: 900,
  });
}

export function CarbonMap() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const buildingsRef = useRef<BuildingFeatureCollection>(sampleBuildings);
  const pendingBuildingsRef = useRef<BuildingFeatureCollection | null>(null);
  const demoOpenedRef = useRef(false);

  const [selectedBin, setSelectedBin] = useState<string | null>(null);
  const [selectedFallback, setSelectedFallback] =
    useState<BuildingProperties | undefined>(undefined);
  const [hoveredBuilding, setHoveredBuilding] = useState<{
    properties: BuildingProperties;
    x: number;
    y: number;
  } | null>(null);
  const [dataSource, setDataSource] = useState<MapDataSource>("loading");
  const [buildings, setBuildings] =
    useState<BuildingFeatureCollection>(sampleBuildings);
  const [buildingCount, setBuildingCount] = useState(0);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const handleClose = useCallback(() => {
    setSelectedBin(null);
    setSelectedFallback(undefined);
    const map = mapRef.current;
    if (map) applySelectionFilter(map, null);
  }, []);

  const handleSelectFeature = useCallback((feature: BuildingFeature) => {
    const map = mapRef.current;
    const lngLat = getFeatureCenter(feature);

    if (map) {
      applySelectionFilter(map, feature.properties.id);
      flyToBuilding(map, lngLat);
    }

    setSelectedBin(feature.properties.bin);
    setSelectedFallback(feature.properties);
  }, []);

  const openBuildingByBin = useCallback(
    async (bin: string) => {
      const feature = buildingsRef.current.features.find(
        (f) => f.properties.bin === bin,
      );
      if (feature) {
        handleSelectFeature(feature);
        return;
      }

      try {
        const detail = await fetchBuildingDetail(bin, 1);
        const lat = Number(detail.building.latitude);
        const lng = Number(detail.building.longitude);
        const map = mapRef.current;
        if (map && Number.isFinite(lat) && Number.isFinite(lng)) {
          applySelectionFilter(map, bin);
          flyToBuilding(map, [lng, lat]);
        }
        setSelectedBin(bin);
        setSelectedFallback(undefined);
      } catch {
        setSelectedBin(bin);
        setSelectedFallback(undefined);
      }
    },
    [handleSelectFeature],
  );

  const handleDemoSelect = useCallback(() => {
    void openBuildingByBin(DEMO_BIN);
  }, [openBuildingByBin]);

  const handleRetry = useCallback(() => {
    setDataSource("loading");
    setLoadError(null);
    setReloadKey((key) => key + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;

    loadBuildings().then((result) => {
      if (cancelled) return;
      buildingsRef.current = result.collection;
      setBuildings(result.collection);
      setDataSource(result.source);
      setBuildingCount(result.count);
      setLoadError(result.error ?? null);

      const map = mapRef.current;
      if (!map) {
        pendingBuildingsRef.current = result.collection;
        return;
      }
      if (!applyBuildingsToMap(map, result.collection)) {
        pendingBuildingsRef.current = result.collection;
      }
    });

    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  useEffect(() => {
    if (dataSource !== "live" || demoOpenedRef.current) return;
    demoOpenedRef.current = true;
    void openBuildingByBin(resolveTargetBin());
  }, [dataSource, openBuildingByBin]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || mapRef.current) return;

    const map = new maplibregl.Map({
      container,
      style: MAP_STYLE_URL,
      center: initialMapView.center,
      zoom: initialMapView.zoom,
      pitch: initialMapView.pitch,
      bearing: initialMapView.bearing,
    });

    mapRef.current = map;

    map.addControl(
      new maplibregl.NavigationControl({ showCompass: true }),
      "bottom-right",
    );

    map.on("error", (event) => {
      if (event.error?.message?.includes("style")) {
        map.setStyle(MAP_STYLE_FALLBACK_URL);
      }
    });

    map.on("load", () => {
      map.addSource(BUILDING_SOURCE_ID, {
        type: "geojson",
        data: pendingBuildingsRef.current ?? buildingsRef.current,
      });

      map.addLayer(createBuildingExtrusionLayer());
      map.addLayer(createBuildingOutlineLayer());
      map.addLayer(createSelectedBuildingLayer());

      pendingBuildingsRef.current = null;
    });

    map.on("click", INTERACTIVE_LAYERS, (event) => {
      const feature = event.features?.[0];
      const props = parseBuildingProperties(feature?.properties ?? null);
      if (!props) return;

      applySelectionFilter(map, props.id);
      flyToBuilding(map, [event.lngLat.lng, event.lngLat.lat]);
      setSelectedBin(props.bin);
      setSelectedFallback(props);
    });

    map.on("mousemove", INTERACTIVE_LAYERS, (event) => {
      const feature = event.features?.[0];
      const props = parseBuildingProperties(feature?.properties ?? null);
      if (!props) return;

      setHoveredBuilding({
        properties: props,
        x: event.point.x,
        y: event.point.y,
      });
    });

    map.on("mouseenter", INTERACTIVE_LAYERS, () => {
      map.getCanvas().style.cursor = "pointer";
    });

    map.on("mouseleave", INTERACTIVE_LAYERS, () => {
      map.getCanvas().style.cursor = "";
      setHoveredBuilding(null);
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    applySelectionFilter(map, selectedBin);
  }, [selectedBin]);

  const isLoading = dataSource === "loading";
  const hasError = dataSource === "error";

  return (
    <div style={styles.wrapper}>
      <div ref={containerRef} style={styles.map} />
      <div style={styles.vignette} aria-hidden />
      <MapChrome
        dataSource={dataSource}
        buildingCount={buildingCount}
        onDemoSelect={handleDemoSelect}
      />
      <MapSearch buildings={buildings} onSelect={handleSelectFeature} />
      <MapLegend />

      {isLoading && (
        <div style={styles.loadingOverlay} aria-live="polite" aria-busy="true">
          <div style={styles.loadingGrid} aria-hidden>
            {Array.from({ length: 12 }, (_, i) => (
              <div key={i} style={styles.loadingGridCell} />
            ))}
          </div>
          <p style={styles.loadingTitle}>Loading NYC building risk layer…</p>
          <p style={styles.loadingText}>
            Pulling scored footprints from the API — the map stays interactive underneath.
          </p>
          <div style={styles.loadingBar} aria-hidden />
        </div>
      )}

      {hasError && (
        <div style={styles.errorOverlay} role="alert">
          <p style={styles.errorTitle}>Map data unavailable</p>
          <p style={styles.errorText}>
            {loadError || "The building layer could not be loaded."}
          </p>
          <p style={styles.errorHint}>
            Start Flask with <code style={styles.inlineCode}>python web.py</code>, confirm
            Supabase credentials in <code style={styles.inlineCode}>.env</code>, then retry.
          </p>
          <button type="button" style={styles.retryButton} onClick={handleRetry}>
            Retry load
          </button>
        </div>
      )}

      {selectedBin && (
        <BuildingInsightCard
          bin={selectedBin}
          fallback={selectedFallback}
          onClose={handleClose}
        />
      )}

      {hoveredBuilding && !selectedBin && (
        <div
          style={{
            ...styles.tooltip,
            left: hoveredBuilding.x + 14,
            top: hoveredBuilding.y + 14,
          }}
        >
          <p style={styles.tooltipAddress}>
            {hoveredBuilding.properties.address}
          </p>
          <p style={styles.tooltipMeta}>
            {riskHeadline(hoveredBuilding.properties.risk_label)} ·{" "}
            {ghgConfidenceLabel(hoveredBuilding.properties.ghg_source)}
          </p>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  wrapper: {
    position: "relative",
    width: "100%",
    height: "100%",
    overflow: "hidden",
    background: "#0a0c10",
  },
  map: {
    width: "100%",
    height: "100%",
  },
  vignette: {
    position: "absolute",
    inset: 0,
    pointerEvents: "none",
    background:
      "radial-gradient(ellipse at center, transparent 40%, rgba(8, 10, 14, 0.55) 100%)",
    zIndex: 1,
  },
  loadingOverlay: {
    position: "absolute",
    inset: 0,
    zIndex: 9,
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    background: "rgba(8, 10, 14, 0.78)",
    backdropFilter: "blur(8px)",
    pointerEvents: "none",
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },
  loadingGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(4, 44px)",
    gap: 6,
    marginBottom: 8,
    opacity: 0.55,
  },
  loadingGridCell: {
    width: 44,
    height: 44,
    borderRadius: 8,
    border: "1px solid rgba(255, 255, 255, 0.04)",
    background:
      "linear-gradient(135deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0.07) 50%, rgba(255,255,255,0.03) 100%)",
    backgroundSize: "200% 200%",
    animation: "cs-skeleton 1.6s ease infinite",
  },
  loadingBar: {
    width: 160,
    height: 3,
    borderRadius: 999,
    marginTop: 4,
    background:
      "linear-gradient(90deg, rgba(110,207,196,0.15) 25%, rgba(110,207,196,0.55) 50%, rgba(110,207,196,0.15) 75%)",
    backgroundSize: "200% 100%",
    animation: "cs-skeleton 1.2s ease infinite",
  },
  loadingTitle: {
    margin: 0,
    fontSize: 14,
    fontWeight: 600,
    color: "#DDE3EA",
    letterSpacing: "0.01em",
  },
  loadingText: {
    margin: 0,
    fontSize: 12,
    color: "#8B949E",
  },
  errorOverlay: {
    position: "absolute",
    inset: 0,
    zIndex: 11,
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    padding: 24,
    textAlign: "center" as const,
    background: "rgba(8, 10, 14, 0.88)",
    backdropFilter: "blur(8px)",
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },
  errorTitle: {
    margin: 0,
    fontSize: 16,
    fontWeight: 600,
    color: "#F2F5F8",
  },
  errorText: {
    margin: 0,
    fontSize: 13,
    color: "#B8C2CC",
    maxWidth: 360,
    lineHeight: 1.5,
  },
  errorHint: {
    margin: 0,
    fontSize: 11,
    color: "#7D8794",
    maxWidth: 380,
    lineHeight: 1.45,
  },
  inlineCode: {
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
    fontSize: "0.95em",
    color: "#9AA5B1",
  },
  retryButton: {
    marginTop: 8,
    padding: "8px 14px",
    borderRadius: 8,
    border: "1px solid rgba(110, 207, 196, 0.35)",
    background: "rgba(110, 207, 196, 0.12)",
    color: "#6ECFC4",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  },
  tooltip: {
    position: "absolute",
    zIndex: 12,
    maxWidth: 280,
    padding: "9px 11px",
    borderRadius: 10,
    background: "rgba(14, 17, 22, 0.94)",
    border: "1px solid rgba(255, 255, 255, 0.09)",
    boxShadow: "0 14px 36px rgba(0, 0, 0, 0.42)",
    color: "#DDE3EA",
    pointerEvents: "none",
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },
  tooltipAddress: {
    margin: "0 0 3px",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    fontSize: 12,
    fontWeight: 600,
  },
  tooltipMeta: {
    margin: 0,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    fontSize: 11,
    color: "#8B949E",
  },
};
