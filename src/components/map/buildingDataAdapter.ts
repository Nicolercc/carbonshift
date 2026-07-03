import type { MultiPolygon, Polygon } from "geojson";
import {
  derivePrimaryDriver,
  deriveSuggestedAction,
  normalizeRiskLabel,
} from "./buildingInsights";
import { sampleBuildings } from "./sampleBuildings";
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
    limit: init.limit ?? (params.get("limit") ? Number(params.get("limit")) : 8000),
  };
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
  params.set("limit", String(cfg.limit ?? 8000));

  return `/api/buildings.geojson?${params.toString()}`;
}

async function fetchApiBuildings(): Promise<BuildingFeatureCollection | null> {
  const response = await fetch(buildBuildingsApiUrl(), {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`API responded with ${response.status}`);
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
  } catch {
    // Fall through to demo data.
  }

  return {
    collection: sampleBuildings,
    source: "demo",
    count: sampleBuildings.features.length,
  };
}

export function dataSourceLabel(source: MapDataSource): string {
  switch (source) {
    case "live":
      return "Live Queens data";
    case "demo":
      return "Demo sample data";
    default:
      return "Loading…";
  }
}

declare global {
  interface Window {
    __MAP_INIT__?: MapInitConfig;
  }
}
