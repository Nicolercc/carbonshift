CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS building_crosswalk (
  bin TEXT PRIMARY KEY,
  bbl TEXT,
  base_bbl TEXT,
  borough_code TEXT,
  source_updated_at TEXT
);

CREATE TABLE IF NOT EXISTS buildings (
  bin TEXT PRIMARY KEY,
  bbl TEXT,
  base_bbl TEXT,
  borough TEXT,
  block TEXT,
  lot TEXT,
  full_address TEXT,
  zip_code TEXT,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  created_at TEXT,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS building_profiles (
  building_id TEXT,
  year_built INTEGER,
  building_class TEXT,
  land_use TEXT,
  residential_units INTEGER,
  total_units INTEGER,
  number_of_floors INTEGER,
  lot_area DOUBLE PRECISION,
  building_area DOUBLE PRECISION,
  source_name TEXT,
  source_updated_at TEXT,
  FOREIGN KEY (building_id) REFERENCES buildings(bin)
);

CREATE TABLE IF NOT EXISTS building_violations (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  building_id TEXT,
  source_dataset TEXT,
  issuing_agency TEXT,
  violation_number TEXT,
  violation_class TEXT,
  severity TEXT,
  issue_date TEXT,
  current_status TEXT,
  violation_description TEXT,
  penalty_imposed DOUBLE PRECISION,
  balance_due DOUBLE PRECISION,
  is_asbestos_related INTEGER DEFAULT 0,
  raw_record_id TEXT,
  FOREIGN KEY (building_id) REFERENCES buildings(bin)
);

CREATE TABLE IF NOT EXISTS asbestos_projects (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  building_id TEXT,
  control_number TEXT,
  project_status TEXT,
  project_start_date TEXT,
  project_end_date TEXT,
  contractor_name TEXT,
  air_monitor_name TEXT,
  FOREIGN KEY (building_id) REFERENCES buildings(bin)
);

CREATE TABLE IF NOT EXISTS energy_emissions (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  building_id TEXT,
  reporting_year INTEGER,
  site_eui DOUBLE PRECISION,
  energy_star_score INTEGER,
  ghg_emissions_metric_tons_co2e DOUBLE PRECISION,
  source_property_id TEXT,
  FOREIGN KEY (building_id) REFERENCES buildings(bin)
);

CREATE TABLE IF NOT EXISTS building_risk_scores (
  building_id TEXT PRIMARY KEY,
  risk_score INTEGER,
  risk_label TEXT,
  confidence_label TEXT,
  risk_detail TEXT,
  generated_at TEXT,
  FOREIGN KEY (building_id) REFERENCES buildings(bin)
);

CREATE TABLE IF NOT EXISTS carbon_estimates (
  building_id TEXT PRIMARY KEY,
  building_class TEXT,
  building_area DOUBLE PRECISION,
  eui_source TEXT,
  site_eui DOUBLE PRECISION,
  ghg_intensity DOUBLE PRECISION,
  estimated_ghg_metric_tons DOUBLE PRECISION,
  peer_building_count INTEGER,
  generated_at TEXT,
  FOREIGN KEY (building_id) REFERENCES buildings(bin)
);

CREATE TABLE IF NOT EXISTS building_record_sources (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  building_id TEXT,
  source_name TEXT,
  source_agency TEXT,
  source_dataset_id TEXT,
  source_record_url TEXT,
  last_checked_at TEXT,
  FOREIGN KEY (building_id) REFERENCES buildings(bin)
);

CREATE INDEX IF NOT EXISTS idx_bv_building_id
  ON building_violations(building_id);
CREATE INDEX IF NOT EXISTS idx_bv_building_asbestos
  ON building_violations(building_id, is_asbestos_related);
CREATE INDEX IF NOT EXISTS idx_bp_building_id
  ON building_profiles(building_id);
CREATE INDEX IF NOT EXISTS idx_ap_building_id
  ON asbestos_projects(building_id);
CREATE INDEX IF NOT EXISTS idx_ee_building_id
  ON energy_emissions(building_id);

CREATE TABLE IF NOT EXISTS building_footprints (
    doitt_id         TEXT PRIMARY KEY,
    bin              TEXT,
    mappluto_bbl     TEXT,
    base_bbl         TEXT,
    last_status_type TEXT,
    feature_code     TEXT,
    geom             geometry(MultiPolygon, 4326)
);

CREATE INDEX IF NOT EXISTS idx_footprints_bin  ON building_footprints (bin);
CREATE INDEX IF NOT EXISTS idx_footprints_geom ON building_footprints USING GIST (geom);
