import type { Feature, FeatureCollection, Point, Polygon } from "geojson";
import type { BackendRiskLabel } from "./mapConfig";

/** Raw properties returned by `/api/buildings.geojson`. */
export interface ApiBuildingProperties {
  bin: string;
  address: string;
  zip: string;
  year_built: number | null;
  building_class: string;
  building_area: number | null;
  risk_score: number | null;
  risk_label: string;
  ghg: number | null;
  ghg_source: string;
  violations: number;
  asbestos: number;
}

export type ApiBuildingFeature = Feature<Point, ApiBuildingProperties>;

export type ApiBuildingFeatureCollection = FeatureCollection<
  Point,
  ApiBuildingProperties
>;

/** Normalized properties used by map layers and the insight card. */
export interface BuildingProperties {
  id: string;
  bin: string;
  address: string;
  zip: string;
  year_built: number | null;
  building_class: string;
  building_area: number | null;
  risk_score: number | null;
  risk_label: BackendRiskLabel;
  ghg: number | null;
  ghg_source: string;
  violations: number;
  asbestos: number;
  height_m: number;
  primary_driver: string;
  suggested_action: string;
}

export interface SelectedBuilding {
  id: string;
  properties: BuildingProperties;
  lngLat: [number, number];
}

export type BuildingFeature = Feature<Polygon, BuildingProperties>;

export type BuildingFeatureCollection = FeatureCollection<
  Polygon,
  BuildingProperties
>;

export type MapDataSource = "loading" | "live" | "demo";

export interface BuildingsLoadResult {
  collection: BuildingFeatureCollection;
  source: MapDataSource;
  count: number;
}
