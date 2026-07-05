import type { LngLatBoundsLike } from "maplibre-gl";

/**
 * Basemap style URL.
 *
 * Production swap-in options (set MAP_STYLE_URL env or replace here):
 *   MapTiler:  `https://api.maptiler.com/maps/streets-v2-dark/style.json?key=YOUR_KEY`
 *   Protomaps: custom PMTiles + style JSON hosted on your CDN
 *
 * Current: CARTO Dark Matter — keyless, reliable, presentation-ready dark basemap.
 * Fallback: MapLibre demo tiles (see MAP_STYLE_FALLBACK_URL).
 */
export const MAP_STYLE_URL =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

export const MAP_STYLE_FALLBACK_URL =
  "https://demotiles.maplibre.org/style.json";

/** Presentation demo building — strongest four-signal API payload. */
export const DEMO_BIN = "1063355";

/** Default GeoJSON payload size for /map (URL ?limit= overrides). */
export const MAP_GEOJSON_LIMIT = 2000;

/** Max violation rows shown in map building panel. */
export const VIOLATION_DISPLAY_CAP = 5;

/** Max risk driver chips shown in building panel. */
export const RISK_DRIVER_DISPLAY_CAP = 5;

export const BUILDING_SOURCE_ID = "carbon-buildings";
export const BUILDING_EXTRUSION_LAYER_ID = "building-extrusion";
export const BUILDING_OUTLINE_LAYER_ID = "building-outline";
export const SELECTED_BUILDING_LAYER_ID = "building-selected";

export const initialMapView = {
  center: [-73.986, 40.754] as [number, number],
  zoom: 11.5,
  pitch: 58,
  bearing: -18,
};

/** Approximate Manhattan bounding box — default presentation viewport. */
export const manhattanBounds: LngLatBoundsLike = [
  [-74.02, 40.70],
  [-73.93, 40.80],
];

/** Approximate NYC core bounds (Queens + Manhattan) — presentation viewport reference. */
export const nycBounds: LngLatBoundsLike = [
  [-74.02, 40.54],
  [-73.7, 40.80],
];

/** Approximate Queens bounding box — data coverage reference. */
export const queensBounds: LngLatBoundsLike = [
  [-73.962, 40.543],
  [-73.7, 40.802],
];

/** Matches Flask `risk_label` values from building_risk_scores. */
export type BackendRiskLabel =
  | "Low"
  | "Moderate"
  | "High"
  | "Critical"
  | "Unscored";

export const RISK_COLORS: Record<BackendRiskLabel, string> = {
  Low: "#3DAA9E",
  Moderate: "#C4A035",
  High: "#C96B52",
  Critical: "#9E4A4A",
  Unscored: "#6B7580",
};

export const RISK_LABELS: Record<BackendRiskLabel, string> = {
  Low: "Low risk",
  Moderate: "Moderate risk",
  High: "High risk",
  Critical: "Critical risk",
  Unscored: "Unscored",
};

export const RISK_LEGEND_ORDER: BackendRiskLabel[] = [
  "Low",
  "Moderate",
  "High",
  "Critical",
  "Unscored",
];
