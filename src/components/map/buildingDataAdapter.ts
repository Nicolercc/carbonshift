import type { MultiPolygon, Polygon } from "geojson";
import {
  derivePrimaryDriver,
  deriveSuggestedAction,
  normalizeRiskLabel,
} from "./buildingInsights";
import { DEMO_BIN, MAP_GEOJSON_LIMIT } from "./mapConfig";
import type {
  ApiBuildingFeature,
  ApiBuildingFeatureCollection,
  BuildingFeature,
  BuildingFeatureCollection,
  BuildingProperties,
  BuildingsLoadResult,
  MapDataSource,
  MapInitConfig,
} from "./mapTypes";

/** Normalize API Polygon / MultiPolygon to a single Polygon for extrusion. */
function apiGeometryToPolygon(
  geometry: Polygon | MultiPolygon,
): Polygon | null {
  if (geometry.type === "Polygon") {
    return geometry.coordinates[0]?.length ? geometry : null;
  }
  const ring = geometry.coordinates[0]?.[0];
  return ring?.length
    ? { type: "Polygon", coordinates: geometry.coordinates[0] }
    : null;
}

/** Estimate extrusion height from building area (API has no floor count). */
export function estimateHeightM(buildingAreaSqFt: number | null): number {
  if (!buildingAreaSqFt || buildingAreaSqFt <= 0) return 12;
  const floors = Math.max(buildingAreaSqFt / 850, 1);
  return Math.min(Math.max(floors * 3.1, 8), 140);
}

function normalizeApiFeature(feature: ApiBuildingFeature): BuildingFeature | null {
  const raw = feature.properties;
  const footprint = apiGeometryToPolygon(feature.geometry);
  if (!raw?.bin || !footprint) return null;

  const risk_label = normalizeRiskLabel(raw.risk_label);
  const buildingProps: BuildingProperties = {
    id: raw.bin,
    bin: raw.bin,
    address: raw.address || `BIN ${raw.bin}`,
    zip: raw.zip || "",
    year_built: raw.year_built ?? null,
    building_class: raw.building_class || "",
    building_area: raw.building_area ?? null,
    risk_score: raw.risk_score ?? null,
    risk_label,
    ghg: raw.ghg ?? null,
    ghg_source: raw.ghg_source || "",
    violations: raw.violations ?? 0,
    asbestos: raw.asbestos ?? 0,
    height_m: estimateHeightM(raw.building_area),
    primary_driver: "",
    suggested_action: "",
  };

  buildingProps.primary_driver = derivePrimaryDriver(buildingProps);
  buildingProps.suggested_action = deriveSuggestedAction(buildingProps);

  return {
    type: "Feature",
    geometry: footprint,
    properties: buildingProps,
  };
}

export function transformApiCollection(
  api: ApiBuildingFeatureCollection,
): BuildingFeatureCollection {
  const features = api.features
    .map(normalizeApiFeature)
    .filter((f): f is BuildingFeature => f != null);

  return { type: "FeatureCollection", features };
}

function readInitConfig(): MapInitConfig {
  const init = window.__MAP_INIT__ ?? {};
  const params = new URLSearchParams(window.location.search);

  const pick = (key: keyof MapInitConfig, param: string): string | undefined => {
    const fromInit = init[key];
    if (typeof fromInit === "string" && fromInit.trim()) return fromInit.trim();
    const fromUrl = params.get(param);
    return fromUrl?.trim() || undefined;
  };

  const yearMin = init.year_min ?? (params.get("year_min") ? Number(params.get("year_min")) : null);
  const yearMax = init.year_max ?? (params.get("year_max") ? Number(params.get("year_max")) : null);

  return {
    q: pick("q", "q"),
    zip: pick("zip", "zip"),
    class: pick("class", "class"),
    year_min: Number.isFinite(yearMin) ? yearMin : null,
    year_max: Number.isFinite(yearMax) ? yearMax : null,
    risk: pick("risk", "risk"),
    asbestos: init.asbestos ?? params.get("asbestos") === "1",
    limit: init.limit ?? (params.get("limit") ? Number(params.get("limit")) : MAP_GEOJSON_LIMIT),
  };
}

/** Resolve which BIN to auto-select: URL ?bin= wins, then Flask demo_bin, then default. */
export function resolveTargetBin(): string {
  const init = window.__MAP_INIT__ ?? {};
  const urlBin = new URLSearchParams(window.location.search).get("bin")?.trim();
  if (urlBin) return urlBin;
  const initBin = init.demo_bin?.trim();
  if (initBin) return initBin;
  return DEMO_BIN;
}

/** Build `/api/buildings.geojson` URL from Flask-injected init + page query string. */
export function buildBuildingsApiUrl(): string {
  const cfg = readInitConfig();
  const params = new URLSearchParams();

  if (cfg.q) params.set("q", cfg.q);
  if (cfg.zip) params.set("zip", cfg.zip);
  if (cfg.class) params.set("class", cfg.class);
  if (cfg.year_min != null) params.set("year_min", String(cfg.year_min));
  if (cfg.year_max != null) params.set("year_max", String(cfg.year_max));
  if (cfg.risk) params.set("risk", cfg.risk);
  if (cfg.asbestos) params.set("asbestos", "1");
  params.set("limit", String(cfg.limit ?? MAP_GEOJSON_LIMIT));

  return `/api/buildings.geojson?${params.toString()}`;
}

function userFacingMapError(status: number): string {
  if (status === 503) {
    return "The map data service is temporarily unavailable.";
  }
  if (status >= 500) {
    return "The building layer could not be loaded right now.";
  }
  return "The building layer could not be loaded. Check your connection and retry.";
}

async function fetchApiBuildings(): Promise<BuildingFeatureCollection | null> {
  let response: Response;
  try {
    response = await fetch(buildBuildingsApiUrl(), {
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new Error("The building layer could not be loaded. Check your connection and retry.");
  }

  if (!response.ok) {
    throw new Error(userFacingMapError(response.status));
  }

  const api = (await response.json()) as ApiBuildingFeatureCollection;
  if (!api.features?.length) return null;

  return transformApiCollection(api);
}

export async function loadBuildings(): Promise<BuildingsLoadResult> {
  try {
    const live = await fetchApiBuildings();
    if (live && live.features.length > 0) {
      return {
        collection: live,
        source: "live",
        count: live.features.length,
      };
    }
    return {
      collection: { type: "FeatureCollection", features: [] },
      source: "error",
      count: 0,
      error: "No buildings returned from the API",
    };
  } catch (err) {
    return {
      collection: { type: "FeatureCollection", features: [] },
      source: "error",
      count: 0,
      error: err instanceof Error ? err.message : "The building layer could not be loaded.",
    };
  }
}

export function dataSourceLabel(source: MapDataSource): string {
  switch (source) {
    case "live":
      return "Live NYC data";
    case "demo":
      return "Demo sample data";
    case "error":
      return "Data unavailable";
    default:
      return "Loading…";
  }
}

declare global {
  interface Window {
    __MAP_INIT__?: MapInitConfig;
  }
}
