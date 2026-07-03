# CarbonShift — Data Ingestion Context File
**Last updated:** June 26, 2026 (rev 2)
**Purpose:** Project context file for CarbonShift. Originally written to hand off the data ingestion work; updated to reflect the current completed state of the pipeline, scoring, and web UI.

## Start Here For Current Product Direction

This file contains important backend/data context, but it is no longer the only project entrypoint.

Before planning frontend or product work, read:

- `docs/README.md`
- `docs/product-direction.md`
- `docs/frontend-implementation-plan.md`
- `docs/api-contracts.md`
- `docs/backend-context.md`

Current product direction:

> CarbonShift should become a visual-first civic climate intelligence tool. Bigger map. Less text. More visual explanation.

Architecture direction:

```txt
Next.js frontend
  -> Flask JSON API
    -> Postgres/PostGIS/Supabase
```

Do not replace Flask for the MVP. Flask should remain the data API while the frontend becomes a modern map-first product surface.

---

## SECTION A — Project Brief

CarbonShift is a climate-tech / built-environment transparency app. It turns fragmented NYC public building records (property data, housing and building violations, asbestos filings, energy/emissions disclosures) into a plain-language building profile, plus a carbon estimate.

**Current state (as of June 26, 2026):** Ingestion pipeline, scoring pipeline, and browser-based web UI are all complete and validated for Queens. See Section I for what remains out of scope.

**Tech stack:** Python 3.10+, SQLite (standard SQL only, no SQLite-specific syntax — clean migration path to Postgres later), `requests`, `python-dotenv`, `pandas`.

**Geographic scope:** Queens, NYC borough code **4**. Borough code is the first digit of both BBL (10-digit) and BIN (7-digit) citywide — this is a reliable, universal NYC convention and the recommended filter mechanism (see Section F).

---

## SECTION B — Environment & Setup

```bash
mkdir carbonshift && cd carbonshift
python -m venv venv && source venv/bin/activate
pip install requests python-dotenv pandas
git init
```

`.env.example`:
```
DB_PATH=data/carbonshift.db
SOCRATA_APP_TOKEN=your_token_here   # REQUIRED — sign up free at https://data.cityofnewyork.us/profile/app_tokens. Without this, requests throttle quickly across five datasets.
BOROUGH_CODE=4                      # Queens
```

`.gitignore`: exclude `.env`, `data/`, `venv/`, `__pycache__/`

Folder structure (mirrors the existing project pattern):
```
carbonshift/
├── run.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
└── src/
    ├── db/
    │   ├── schema.sql
    │   └── init_db.py
    ├── ingestion/
    │   ├── fetch_crosswalk.py
    │   ├── fetch_pluto.py
    │   ├── fetch_hpd.py
    │   ├── fetch_dob.py
    │   ├── fetch_acp7.py
    │   └── fetch_ll84_97.py
    └── validate/
        └── check_coverage.py
```

---

## SECTION C — Datasets to Ingest (Queens MVP scope)

All datasets are on the NYC Open Data Socrata platform. Base API pattern:
```
GET https://data.cityofnewyork.us/resource/{dataset_id}.json?$limit=50000&$offset=0
```
Add header `X-App-Token: {SOCRATA_APP_TOKEN}` or query param `$$app_token=`.

| # | Dataset | Dataset ID | Role | URL |
|---|---|---|---|---|
| 1 | **Building Footprints** (crosswalk) | `5zhs-2jue` | Master BIN ↔ BBL ↔ BASE_BBL crosswalk — ingest this **first** | https://data.cityofnewyork.us/City-Government/BUILDING/5zhs-2jue |
| 2 | PLUTO | `64uk-42ks` | Building profile: year built, sq ft, building class, units, floors | https://data.cityofnewyork.us/City-Government/Primary-Land-Use-Tax-Lot-Output-PLUTO-/64uk-42ks |
| 3 | HPD Housing Maintenance Code Violations | `wvxf-dwi5` | Housing violations, Class A/B/C/I | https://data.cityofnewyork.us/Housing-Development/Housing-Maintenance-Code-Violations/wvxf-dwi5 |
| 4 | DOB Safety Violations | `855j-jady` | Building safety violations (current system) | https://data.cityofnewyork.us/Housing-Development/DOB-Safety-Violations/855j-jady |
| 5 | DOB Violations (legacy) | `3h2n-5cm9` | Building safety violations (legacy BIS system — pull both, dedupe later) | https://data.cityofnewyork.us/Housing-Development/DOB-Violations/3h2n-5cm9 |
| 6 | DOB ECB Violations | `6bgk-3dad` | Enforcement/hearings; also the surface to keyword-match for asbestos-adjacent enforcement | https://data.cityofnewyork.us/Housing-Development/DOB-ECB-Violations/6bgk-3dad |
| 7 | Asbestos Control Program (ACP-7) | `vq35-j9qm` | Asbestos abatement project notifications | https://data.cityofnewyork.us/Environment/Asbestos-Control-Program-ACP7-/vq35-j9qm |
| 8 | NYC Building Energy & Water Data Disclosure (LL84/LL97) | `5zyy-y8am` | **The carbon dataset.** Measured GHG emissions for buildings ≥25,000 sq ft. Current rolling dataset (2023–present, CY2022 onward) | https://data.cityofnewyork.us/Environment/NYC-Building-Energy-and-Water-Data-Disclosure-for-/5zyy-y8am |

**Do not use dataset ID `4t62-jm4m` for LL84/97** — that's the 2018 vintage (reports calendar year 2017), nine years stale. Use `5zyy-y8am`.

**ACP-5 (asbestos assessment reports) has no bulk dataset** — confirmed by searching NYC Open Data's asbestos-tagged catalog (only ACP-7 and "Certified Asbestos Investigators" exist in bulk). ACP-5 is portal-only (`https://a826-web01.nyc.gov/acpsearchportal/acp5`) — do not attempt to bulk-ingest it. Skip for this phase.

---

## SECTION D — The Crosswalk Strategy (read before writing any ingestion code)

Neither street addresses nor BBLs are reliable, persistent building identifiers — a tax lot can hold more than one building, lots merge/subdivide, and BBL/BIN field names and formats are **not consistent across datasets**:

- HPD violations key on BBL.
- DOB datasets typically expose BIN, or separate BORO/BLOCK/LOT fields, not a clean BBL.
- LL84/97 allows a single reported property to span **multiple** BBLs and BINs in one row (list-valued fields) — do not assume 1 row = 1 building.

**Fix:** Building Footprints (`5zhs-2jue`) carries both BIN and BBL on every record, plus `BASE_BBL` distinct from the billing BBL (correctly handles condos/multi-building lots). Ingest it first, build `building_crosswalk`, and join every other dataset through it — never construct a BBL by concatenating Boro+Block+Lot by hand (zero-padding mistakes silently drop or misjoin rows).

**Before writing filter logic for any dataset:** pull 5 sample rows and print the field names. Do not assume field names match across datasets — confirm the actual BBL/BIN/borough field name and exact format (string vs. integer, zero-padded vs. not) for each of the 8 datasets above before coding the ingestion filter. This is a concrete first task, not a formality.

**Recommended Queens filter:** once you've confirmed each dataset's BBL or BIN field, filter using the first-digit borough-code convention (`4` = Queens) rather than relying on a free-text "Borough" field, which is spelled inconsistently across datasets (`"QUEENS"`, `"QN"`, `"Q"`, integer `4`, etc.). The numeric BBL/BIN prefix is universal and verified; the text borough field is not.

---

## SECTION E — Database Schema

Standard SQL — works on SQLite now, Postgres later with no changes.

```sql
CREATE TABLE building_crosswalk (
  bin TEXT PRIMARY KEY,
  bbl TEXT,
  base_bbl TEXT,
  borough_code TEXT,
  source_updated_at TEXT
);

CREATE TABLE buildings (
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

CREATE TABLE building_profiles (
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

CREATE TABLE building_violations (
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

CREATE TABLE asbestos_projects (
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

CREATE TABLE energy_emissions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  building_id TEXT,
  reporting_year INTEGER,
  site_eui REAL,
  energy_star_score INTEGER,
  ghg_emissions_metric_tons_co2e REAL,
  source_property_id TEXT,
  FOREIGN KEY (building_id) REFERENCES buildings(bin)
);

CREATE TABLE building_risk_scores (
  building_id TEXT PRIMARY KEY,
  risk_score INTEGER,
  risk_label TEXT,
  confidence_label TEXT,
  generated_at TEXT,
  FOREIGN KEY (building_id) REFERENCES buildings(bin)
);

CREATE TABLE building_record_sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  building_id TEXT,
  source_name TEXT,
  source_agency TEXT,
  source_dataset_id TEXT,
  source_record_url TEXT,
  last_checked_at TEXT,
  FOREIGN KEY (building_id) REFERENCES buildings(bin)
);
```

`building_violations` is intentionally one unified, source-tagged table (not separate HPD/DOB/ECB tables) — simplifies "all violations for this building" queries and supports keyword-classifying asbestos-adjacent records regardless of which agency filed them.

---

## SECTION F — Ingestion Steps, In Order

1. **Sample every dataset first.** For each of the 8 dataset IDs in Section C, pull 5 rows (`$limit=5`) and print field names/types. Do this before writing any filter logic.
2. **Ingest Building Footprints**, filtered to BIN/BBL prefix `4` (Queens). Populate `building_crosswalk`. Spot-check: pick 3 known Queens addresses and confirm their BBL→BIN resolves correctly.
3. **Ingest PLUTO**, filtered to BBLs present in `building_crosswalk`. Populate `buildings` + `building_profiles`.
4. **Ingest HPD violations**, filtered to BBLs in the crosswalk. Insert into `building_violations` with `source_dataset = 'HPD'`.
5. **Ingest DOB Safety Violations + DOB Violations (legacy) + DOB ECB Violations**, BIN-range-filtered via SoQL then post-filtered against BINs in `buildings` (not `building_crosswalk` — see Section H). Insert into `building_violations` with the appropriate `source_dataset` value each. Run the asbestos keyword match (`asbestos`, `ACM`, `abatement`, `ACP-5`, `ACP-7`) against violation descriptions and set `is_asbestos_related = 1` where matched.
6. **Ingest ACP-7**, BIN-range-filtered via SoQL then post-filtered against BINs in `buildings`. Populate `asbestos_projects`.
7. **Ingest LL84/97**, filtered to `upper(borough)='QUEENS'` then post-filtered against BINs in `buildings`. **Watch for list-valued BBL/BIN fields on this dataset specifically** (Section D) — a single row may need to expand into multiple `energy_emissions` rows, one per BBL/BIN, all pointing at the same source_property_id.
8. **Paginate everything.** Socrata defaults to a row limit per request — use `$limit`/`$offset` loops, don't assume one request returns the full filtered set.
9. Populate `building_record_sources` as you go (source dataset ID + URL + timestamp), so every record is traceable later.

---

## SECTION G — Validation Checkpoints (run before calling ingestion done)

- **Crosswalk join coverage rate:** % of ingested Queens BINs that successfully matched a BBL, with no inflation (duplicate rows from the LL84/97 list-field expansion) or silent drops.
- **Row counts per dataset** are within a sane order of magnitude — if any dataset returns 0 or returns the full citywide set unfiltered, the borough filter from Section D didn't apply correctly.
- **Measured vs. modeled split:** % of buildings in `buildings` that have a matching row in `energy_emissions` (measured) vs. not (will need the modeled estimate downstream).
- Spot-check a handful of real Queens addresses end-to-end: PLUTO profile present, violations present if expected, crosswalk resolved correctly.

---

## SECTION H — Known Gotchas (read before debugging blind)

- **BIN is the only permanent 1:1 building identifier.** BBLs and addresses are not reliable on their own — this is why the crosswalk exists at all.
- **LL84/97 rows can represent multiple buildings.** Don't assume 1 row = 1 BBL = 1 BIN.
- **Socrata throttles unauthenticated requests fast** across 8 dataset pulls. Confirm `SOCRATA_APP_TOKEN` is set before starting ingestion, not after hitting a wall.
- **Borough field names are not consistent across datasets.** Use the BBL/BIN numeric prefix, not a free-text borough field, per Section D.
- **Default web port is 5050.** `python web.py` binds to `http://localhost:5050`. Port 5000 conflicts with macOS AirPlay Receiver (Monterey+), which binds to `*:5000` including IPv6 — `localhost` resolves to `::1` first so `localhost:5000` hits AirPlay, not Flask. Port 5050 is reserved for this project.
- **`building_violations` must be indexed for the map to load.** The `/api/buildings.geojson` endpoint uses two correlated `COUNT(*)` subqueries against `building_violations` (1.6M rows). Without `idx_bv_building_id`, each query is a full table scan — the endpoint hangs indefinitely and the browser reports "TypeError: Failed to fetch". The index is created by `init_db()` / `schema.sql`; running `python web.py` on startup applies it automatically to existing databases.
- **Socrata SoQL does not support `starts_with()` on all datasets.** Building Footprints, DOB Safety, DOB ECB, and ACP-7 return a 400 error for `starts_with(bin, '4')`. Use the equivalent range filter: `bin >= '4000000' AND bin < '5000000'`.
- **Foreign key constraint: run PLUTO before DOB/ACP-7/LL84.** `building_violations` and `asbestos_projects` have FK constraints on `buildings(bin)`. DOB, ACP-7, and LL84/97 fetchers resolve their BIN allowlists from the `buildings` table (populated by PLUTO) — not from `building_crosswalk` — to avoid FK failures. Buildings in the crosswalk but not in PLUTO (parking structures, parks, undeveloped lots) will be silently skipped. HPD uses crosswalk BBLs directly, which is safe because HPD-violated buildings are universally covered by PLUTO.
- **There is no standalone "asbestos violations" dataset.** Asbestos-adjacent enforcement only surfaces via keyword-matching DOB/ECB violation text (Step 5 above) — don't go looking for a dedicated dataset that doesn't exist.
- **ACP-5 cannot be bulk-ingested.** Don't spend time looking for an API — there isn't one.

---

## SECTION I — Out of Scope

- Personal carbon tracking (signup/login, activity logging, emission factors)
- Citywide search (Queens only at present)
- ACP-5 portal lookups — no bulk API; portal-only at `a826-web01.nyc.gov`
- Con Edison utility data, "concern type" filtering, "Learn" screen — backlog
- Any UI beyond the existing Flask web interface

**Completed as of June 26, 2026 (previously out of scope):**
- Ingestion pipeline (`run.py`) — all 8 datasets, paginated, Queens-filtered, FK-safe
- Carbon estimate scoring (`score.py`) — class-median and borough-median modelled EUI; 359,408 buildings scored
- Risk scoring (`score.py`) — point-weighted model; Low / Moderate / High / Critical labels
- Browser-based web UI (`web.py`) — search, building detail, charts, map, SQL editor, CSV export, dark mode

---

## SECTION J — Scoring Logic Summary

`score.py` runs two passes after ingestion:

**Carbon estimates** — for buildings with measured LL84/97 data, records actual GHG directly. For the rest (~95%), computes median GHG intensity (mt CO₂e per ft²) per `building_class` from measured peers and multiplies by building area. Falls back to a Queens-wide median if fewer than 3 class peers exist. Writes to `carbon_estimates`; `eui_source` = `measured` / `class_median` / `borough_median`.

**Risk scoring** — point-weighted score written to `building_risk_scores`. Do not rename columns in `building_violations`, `asbestos_projects`, or `building_profiles` without checking `src/scoring/risk.py`.
