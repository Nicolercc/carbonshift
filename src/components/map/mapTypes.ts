import type { Feature, FeatureCollection, MultiPolygon, Polygon } from "geojson";
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

export type ApiBuildingFeature = Feature<Polygon | MultiPolygon, ApiBuildingProperties>;

export type ApiBuildingFeatureCollection = FeatureCollection<
  Polygon | MultiPolygon,
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

export type MapDataSource = "loading" | "live" | "demo" | "error";

export interface BuildingDetailSignals {
  risk: {
    score: number | null;
    label: string;
    confidence: string | null;
    drivers: string[];
  };
  carbon: {
    estimated_ghg_metric_tons: number | null;
    eui_source: string | null;
    site_eui: number | null;
    peer_building_count: number | null;
  };
  compliance: {
    violation_count_returned: number;
    asbestos_related_violation_count_returned: number;
  };
  asbestos: {
    project_count_returned: number;
    has_asbestos_signal: boolean;
  };
  data_completeness: {
    has_location: boolean;
    has_profile: boolean;
    has_risk_score: boolean;
    has_carbon_estimate: boolean;
  };
}

export interface ViolationRecord {
  source_dataset?: string;
  violation_class?: string;
  issue_date?: string;
  current_status?: string;
  violation_description?: string;
  is_asbestos_related?: number;
  penalty_imposed?: number | null;
  balance_due?: number | null;
}

export interface BuildingDetailPayload {
  building: Record<string, unknown>;
  signals: BuildingDetailSignals;
  records: {
    violations: ViolationRecord[];
    energy: Record<string, unknown>[];
    asbestos: Record<string, unknown>[];
  };
  record_limit: number;
}

export interface BuildingsLoadResult {
  collection: BuildingFeatureCollection;
  source: MapDataSource;
  count: number;
  error?: string;
}

/** Initial filter state injected by Flask `map.html`. */
export interface MapInitConfig {
  q?: string;
  zip?: string;
  class?: string;
  year_min?: number | null;
  year_max?: number | null;
  risk?: string;
  asbestos?: boolean;
  limit?: number;
  demo_bin?: string;
}
