import type { Polygon } from "geojson";
import { BUILDINGS_API_URL } from "./mapConfig";
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
} from "./mapTypes";

/** Convert a point + building area into a square footprint polygon. */
export function pointToFootprint(
  lng: number,
  lat: number,
  buildingAreaSqFt: number | null,
): Polygon {
  const sqFt = buildingAreaSqFt && buildingAreaSqFt > 0 ? buildingAreaSqFt : 8000;
  const sideM = Math.sqrt(sqFt * 0.092903);
  const clampedSideM = Math.min(Math.max(sideM, 14), 75);

  const latRad = (lat * Math.PI) / 180;
  const metersPerDegLat = 111_320;
  const metersPerDegLng = 111_320 * Math.cos(latRad);

  const halfLat = Math.max(clampedSideM / 2 / metersPerDegLat, 0.000022);
  const halfLng = Math.max(clampedSideM / 2 / metersPerDegLng, 0.000018);

  return {
    type: "Polygon",
    coordinates: [
      [
        [lng - halfLng, lat - halfLat],
        [lng + halfLng, lat - halfLat],
        [lng + halfLng, lat + halfLat],
        [lng - halfLng, lat + halfLat],
        [lng - halfLng, lat - halfLat],
      ],
    ],
  };
}

/** Estimate extrusion height from building area (API has no floor count). */
export function estimateHeightM(buildingAreaSqFt: number | null): number {
  if (!buildingAreaSqFt || buildingAreaSqFt <= 0) return 12;
  const floors = Math.max(buildingAreaSqFt / 850, 1);
  return Math.min(Math.max(floors * 3.1, 8), 140);
}

function normalizeApiFeature(feature: ApiBuildingFeature): BuildingFeature | null {
  const [lng, lat] = feature.geometry.coordinates;
  const raw = feature.properties;
  if (!raw?.bin || lng == null || lat == null) return null;

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
    geometry: pointToFootprint(lng, lat, raw.building_area),
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

async function fetchApiBuildings(): Promise<BuildingFeatureCollection | null> {
  const response = await fetch(BUILDINGS_API_URL, {
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
