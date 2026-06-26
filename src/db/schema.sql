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
  latitude REAL,
  longitude REAL,
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
  lot_area REAL,
  building_area REAL,
  source_name TEXT,
  source_updated_at TEXT,
  FOREIGN KEY (building_id) REFERENCES buildings(bin)
);

CREATE TABLE IF NOT EXISTS building_violations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  building_id TEXT,
  source_dataset TEXT,
  issuing_agency TEXT,
  violation_number TEXT,
  violation_class TEXT,
  severity TEXT,
  issue_date TEXT,
  current_status TEXT,
  violation_description TEXT,
  penalty_imposed REAL,
  balance_due REAL,
  is_asbestos_related INTEGER DEFAULT 0,
  raw_record_id TEXT,
  FOREIGN KEY (building_id) REFERENCES buildings(bin)
);

CREATE TABLE IF NOT EXISTS asbestos_projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
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
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  building_id TEXT,
  reporting_year INTEGER,
  site_eui REAL,
  energy_star_score INTEGER,
  ghg_emissions_metric_tons_co2e REAL,
  source_property_id TEXT,
  FOREIGN KEY (building_id) REFERENCES buildings(bin)
);

CREATE TABLE IF NOT EXISTS building_risk_scores (
  building_id TEXT PRIMARY KEY,
  risk_score INTEGER,
  risk_label TEXT,
  confidence_label TEXT,
  generated_at TEXT,
  FOREIGN KEY (building_id) REFERENCES buildings(bin)
);

CREATE TABLE IF NOT EXISTS carbon_estimates (
  building_id TEXT PRIMARY KEY,
  building_class TEXT,
  building_area REAL,
  eui_source TEXT,               -- 'measured' | 'class_median' | 'borough_median'
  site_eui REAL,
  ghg_intensity REAL,            -- metric tons CO2e per sq ft
  estimated_ghg_metric_tons REAL,
  peer_building_count INTEGER,
  generated_at TEXT,
  FOREIGN KEY (building_id) REFERENCES buildings(bin)
);

CREATE TABLE IF NOT EXISTS building_record_sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  building_id TEXT,
  source_name TEXT,
  source_agency TEXT,
  source_dataset_id TEXT,
  source_record_url TEXT,
  last_checked_at TEXT,
  FOREIGN KEY (building_id) REFERENCES buildings(bin)
);
