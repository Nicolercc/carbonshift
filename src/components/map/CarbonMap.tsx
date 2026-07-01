import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import maplibregl, { type GeoJSONSource } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import { loadBuildings } from "./buildingDataAdapter";
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
  SelectedBuilding,
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

  const [selectedBuilding, setSelectedBuilding] =
    useState<SelectedBuilding | null>(null);
  const [hoveredBuilding, setHoveredBuilding] = useState<{
    properties: BuildingProperties;
    x: number;
    y: number;
  } | null>(null);
  const [dataSource, setDataSource] = useState<MapDataSource>("loading");
  const [buildings, setBuildings] =
    useState<BuildingFeatureCollection>(sampleBuildings);
  const [buildingCount, setBuildingCount] = useState(
    sampleBuildings.features.length,
  );

  const handleClose = useCallback(() => setSelectedBuilding(null), []);
  const handleSelectFeature = useCallback((feature: BuildingFeature) => {
    const map = mapRef.current;
    const lngLat = getFeatureCenter(feature);

    if (map) {
      applySelectionFilter(map, feature.properties.id);
      flyToBuilding(map, lngLat);
    }

    setSelectedBuilding({
      id: feature.properties.id,
      properties: feature.properties,
      lngLat,
    });
  }, []);

  useEffect(() => {
    let cancelled = false;

    loadBuildings().then((result) => {
      if (cancelled) return;
      buildingsRef.current = result.collection;
      setBuildings(result.collection);
      setDataSource(result.source);
      setBuildingCount(result.count);

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
  }, []);

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
      const lngLat: [number, number] = [event.lngLat.lng, event.lngLat.lat];

      applySelectionFilter(map, props.id);
      flyToBuilding(map, lngLat);
      setSelectedBuilding({
        id: props.id,
        properties: props,
        lngLat,
      });
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
    applySelectionFilter(map, selectedBuilding?.id ?? null);
  }, [selectedBuilding]);

  return (
    <div style={styles.wrapper}>
      <div ref={containerRef} style={styles.map} />
      <div style={styles.vignette} aria-hidden />
      <MapChrome dataSource={dataSource} buildingCount={buildingCount} />
      <MapSearch buildings={buildings} onSelect={handleSelectFeature} />
      <MapLegend />
      {dataSource === "loading" && (
        <div style={styles.loadingOverlay}>
          <p style={styles.loadingText}>Loading building intelligence…</p>
        </div>
      )}
      {selectedBuilding && (
        <BuildingInsightCard
          building={selectedBuilding.properties}
          onClose={handleClose}
        />
      )}
      {hoveredBuilding && (
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
    bottom: 24,
    right: 24,
    zIndex: 10,
    padding: "10px 14px",
    borderRadius: 10,
    background: "rgba(14, 17, 22, 0.88)",
    border: "1px solid rgba(255, 255, 255, 0.06)",
    backdropFilter: "blur(10px)",
  },
  loadingText: {
    margin: 0,
    fontSize: 12,
    color: "#9AA5B1",
    letterSpacing: "0.02em",
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
