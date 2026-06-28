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

export function CarbonMap() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const buildingsRef = useRef<BuildingFeatureCollection>(sampleBuildings);
  const pendingBuildingsRef = useRef<BuildingFeatureCollection | null>(null);

  const [selectedBuilding, setSelectedBuilding] =
    useState<SelectedBuilding | null>(null);
  const [dataSource, setDataSource] = useState<MapDataSource>("loading");
  const [buildingCount, setBuildingCount] = useState(
    sampleBuildings.features.length,
  );

  const handleClose = useCallback(() => setSelectedBuilding(null), []);

  useEffect(() => {
    let cancelled = false;

    loadBuildings().then((result) => {
      if (cancelled) return;
      buildingsRef.current = result.collection;
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

      applySelectionFilter(map, props.id);
      setSelectedBuilding({
        id: props.id,
        properties: props,
        lngLat: [event.lngLat.lng, event.lngLat.lat],
      });
    });

    map.on("mouseenter", INTERACTIVE_LAYERS, () => {
      map.getCanvas().style.cursor = "pointer";
    });

    map.on("mouseleave", INTERACTIVE_LAYERS, () => {
      map.getCanvas().style.cursor = "";
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
};
