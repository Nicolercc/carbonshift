# CarbonShift — Queens Building Data Pipeline

CarbonShift ingests eight NYC Open Data datasets for Queens, scores every building for carbon emissions and risk, and provides four ways to access the results: an ingestion pipeline, a scoring pipeline, a command-line query tool, and a browser-based web interface with interactive charts, a Leaflet map, advanced filters, and CSV export.

---

## Table of Contents

1. [Tech Stack](#tech-stack)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Quick Start](#quick-start)
6. [Pipeline — `run.py`](#pipeline----runpy)
7. [Scoring — `score.py`](#scoring----scorepy)
8. [Query CLI — `query.py`](#query-cli----querypy)
9. [Web Interface — `web.py`](#web-interface----webpy)
10. [Project Structure](#project-structure)
11. [Datasets Ingested](#datasets-ingested)
12. [Database Schema](#database-schema)
13. [Known Gotchas](#known-gotchas)

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Language** | Python 3.10+ | Type hints, broad ecosystem, walrus operator |
| **Database** | SQLite (`sqlite3` stdlib) | Zero-install; schema is standard SQL — migrates to Postgres with no changes |
| **HTTP** | `requests` | Stable session handling, retries, header management |
| **Config** | `python-dotenv` | Keeps secrets out of code and version control |
| **Web framework** | `flask` 3.x | Lightweight; Jinja2 templates bundled; no build step |
| **Charts** | Chart.js 4 (CDN) | Loaded from CDN — no npm/bundler required |
| **Maps** | Leaflet.js + MarkerCluster (CDN) | Interactive map with clustering; no npm required |
| **Data manipulation** | `pandas` | Available for future transform work |
| **Data source** | NYC Open Data — Socrata REST API | Uniform `$limit`/`$offset` pagination and auth across all 8 datasets |

### Key architectural decisions

**BIN as the universal building key.** BBLs change when lots merge or subdivide; street addresses are ambiguous. Building Footprints carries both BIN and BBL on every record, so every other dataset is joined through it — no hand-constructed BBL strings.

**One `building_violations` table.** HPD, DOB Safety, DOB Legacy, and DOB ECB violations all go into a single source-tagged table. This keeps "all violations for building X" queries simple and lets the asbestos keyword scan run once across all agencies.

**Shared query module.** `src/query/` is used by both `query.py` (CLI) and the Flask web app, so changes to lookup or export logic apply everywhere.

**WAL journal mode.** `PRAGMA journal_mode=WAL` lets reads proceed during long write loops.

**Standard SQL only.** No SQLite-specific syntax — the schema runs on Postgres with `SERIAL` in place of `INTEGER PRIMARY KEY AUTOINCREMENT`.

---

## Prerequisites

- Python 3.10 or newer
- A free NYC Open Data (Socrata) API token — without it requests throttle after a few hundred rows per dataset

---

## Installation

```bash
# 1. Clone / enter the project directory
cd carbonshift

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows

# 3. Install all dependencies
pip install -r requirements.txt
```

**Dependencies installed** (`requirements.txt`):

| Package | Version | Used for |
|---|---|---|
| `requests` | ≥ 2.31 | Socrata API calls |
| `python-dotenv` | ≥ 1.0 | Loading `.env` config |
| `pandas` | ≥ 2.0 | Data manipulation |
| `flask` | ≥ 3.0 | Web interface + Jinja2 templates |

---

## Configuration

```bash
cp .env.example .env
```

Edit `.env`:

```
DB_PATH=data/carbonshift.db       # SQLite file — created automatically on first run
SOCRATA_APP_TOKEN=xxxxxxxxxxxx    # Required for full dataset pulls (see below)
BOROUGH_CODE=4                    # Queens — do not change for this phase
```

**Getting a free Socrata API token (~2 minutes):**
1. Visit `https://data.cityofnewyork.us/profile/app_tokens`
2. Click **Add New App Token**, give it any name
3. Copy the **App Token** value into `.env`

Without a token the pipeline still runs but Socrata throttles heavily — most datasets will return partial data.

---

## Quick Start

```bash
# 1. Verify API connectivity and inspect field names
python run.py --sample

# 2. Run the full ingestion pipeline (30–90 min depending on network)
python run.py

# 3. Run the scoring pipeline (carbon estimates + risk scores)
python score.py

# 4. Search for a building on the command line
python query.py search "Jamaica"

# 5. Launch the web interface
python web.py
# → open http://localhost:5000
```

---

## Pipeline — `run.py`

The pipeline fetches all eight datasets from NYC Open Data and loads them into SQLite. Run this before using the query tool or web interface.

### Commands

```bash
# Inspect raw field names from all 8 datasets (do this first)
python run.py --sample

# Full pipeline — all 6 steps in order, then validation report
python run.py

# Run a single step
python run.py --step crosswalk
python run.py --step pluto
python run.py --step hpd
python run.py --step dob
python run.py --step acp7
python run.py --step ll84

# Validation report only (no ingestion)
python run.py --validate-only
```

### Pipeline steps (must run in this order)

| Step | Flag | Source dataset | Destination table(s) |
|---|---|---|---|
| 1 | `crosswalk` | Building Footprints (`5zhs-2jue`) | `building_crosswalk` |
| 2 | `pluto` | PLUTO (`64uk-42ks`) | `buildings`, `building_profiles` |
| 3 | `hpd` | HPD Violations (`wvxf-dwi5`) | `building_violations` |
| 4 | `dob` | DOB Safety + Legacy + ECB | `building_violations` |
| 5 | `acp7` | ACP-7 Asbestos (`vq35-j9qm`) | `asbestos_projects` |
| 6 | `ll84` | LL84/97 Energy (`5zyy-y8am`) | `energy_emissions` |

`crosswalk` must run first — every subsequent step filters against BINs in `building_crosswalk`. `pluto` must run before `dob`, `acp7`, and `ll84` — those three steps resolve their BIN allowlists from the `buildings` table (populated by PLUTO) to satisfy foreign key constraints. Running them before PLUTO will insert nothing and produce no error.

### Validation report (`--validate-only`)

Printed automatically after a full run, or on demand:

```bash
python run.py --validate-only
```

Checks:
- Row counts per table
- % of Queens BINs with a resolved BBL
- Measured vs. modelled split (how many buildings have LL84/97 data)
- Violations breakdown by source agency
- Asbestos flag counts
- Duplicate-row warnings for LL84 multi-BIN expansion

---

## Scoring — `score.py`

Run after ingestion is complete. Populates `carbon_estimates` and `building_risk_scores` for every building.

### Commands

```bash
# Run both carbon estimates and risk scoring (recommended)
python score.py

# Carbon estimates only
python score.py --carbon-only

# Risk scoring only (requires carbon estimates already computed)
python score.py --risk-only

# Score a single building by BIN and print its score to the terminal
python score.py --building 4059918
```

### Carbon estimate algorithm

For buildings **with** measured LL84/97 data: records actual GHG and EUI directly.

For buildings **without** LL84/97 data (the majority):
1. Computes median GHG intensity (mt CO₂e per ft²) for each `building_class` from all measured peers
2. Applies that intensity × building area to estimate annual GHG
3. Falls back to a borough-wide median if fewer than 3 peers exist for the class
4. Records `eui_source` = `class_median` or `borough_median` so estimates are clearly labelled

### Risk scoring algorithm

Point-weighted score written to `building_risk_scores`:

| Factor | Points |
|---|---|
| Year built < 1940 | +3 |
| Year built 1940–1977 | +2 |
| Year built 1978–1999 | +1 |
| Open / Active violations | +1 each (capped at 8) |
| Asbestos-related violations | +2 each (capped at 6) |
| HPD Class C violations | +1 each (capped at 4) |
| Balance due on violations | +1 each (capped at 3) |
| ACP-7 asbestos projects | +3 each (capped at 9) |
| No measured LL84 data | +1 |
| GHG > class median | +1 |
| GHG > 2× class median | +2 |

| Score | Label |
|---|---|
| 0–3 | Low |
| 4–9 | Moderate |
| 10–18 | High |
| 19+ | Critical |

Confidence labels — **High** (PLUTO profile + violations or energy data), **Medium** (PLUTO only), **Low** (no PLUTO profile).

---

## Query CLI — `query.py`

Command-line access to the database. No web server needed.

### Subcommands

#### `search` — find buildings

```bash
# Search by partial address
python query.py search "Jamaica"
python query.py search "Grand Avenue"

# Search by zip code
python query.py search 11101

# Search by BIN (exact)
python query.py search 4059918

# Search by BBL (exact)
python query.py search 4026780001

# Limit results (default: 50)
python query.py search "Flushing" --limit 100
```

Output columns: address, zip, BIN, year built, building class, area, violation count, asbestos count, latest GHG.

#### `building` — full detail for one building

```bash
python query.py building 4059918
```

Prints:
- Identifiers (BIN, BBL, base BBL, block/lot, lat/lon)
- Building profile (year, class, land use, floors, units, area)
- Energy & emissions table (GHG, EUI, Energy Star by year)
- All violations (source, date, class, status, description)
- Asbestos abatement projects

#### `sql` — run any SELECT query

```bash
python query.py sql "SELECT COUNT(*) FROM building_violations WHERE is_asbestos_related=1"

python query.py sql "SELECT full_address, year_built FROM buildings WHERE zip_code='11101' LIMIT 10"

python query.py sql "SELECT source_dataset, COUNT(*) as n FROM building_violations GROUP BY source_dataset"
```

Only SELECT statements are accepted. Results print as an aligned table.

#### `export` — download to CSV

```bash
# Named exports (full tables)
python query.py export buildings
python query.py export violations
python query.py export energy
python query.py export asbestos

# Custom output path
python query.py export violations --out queens_violations.csv

# Export results of a custom SQL query
python query.py export sql --sql "SELECT * FROM buildings WHERE zip_code='11101'" --out flushing.csv
```

Default output filename is `<name>.csv` in the current directory.

---

## Web Interface — `web.py`

A browser-based interface for search, building detail, interactive charts, SQL queries, and CSV export.

### Starting the server

```bash
# Default: http://localhost:5000
python web.py

# Custom port
python web.py --port 8080

# Accessible on your local network (e.g. from another device)
python web.py --host 0.0.0.0 --port 8080

# Development mode — auto-reloads when code changes
python web.py --debug
```

### Dark Mode

CarbonShift ships with a built-in dark mode. A moon/sun toggle button sits in the top-right corner of the navigation bar on every page.

- **Toggle**: click the moon (🌙) icon to switch to dark mode; click the sun (☀) icon to switch back.
- **Persistence**: the choice is saved to `localStorage` under the key `cs-theme` and restored automatically on every page load — no flicker on revisit.
- **Scope**: Bootstrap 5.3's `data-bs-theme` attribute drives the colour switch for all Bootstrap components (cards, forms, tables, badges, dropdowns, buttons). Custom design tokens (`--cs-*` CSS variables defined in `base.html`) extend dark mode to the app's own styles: hover rows, asbestos-highlighted rows, building links, card shadows, and card header borders.
- **Charts**: Chart.js canvases read `data-bs-theme` at render time and apply dark axis labels and grid lines when dark mode is active. Chart colours are intentional and remain the same in both modes for consistency.
- **Map**: Leaflet marker colours are semantic (risk/GHG/age) and are unchanged by theme. Map tiles always render in their standard (light) style — this is standard for Leaflet + OpenStreetMap.

### Pages

#### Home — `/`

- Dataset stats dashboard: building count, violations, energy coverage, asbestos flags, buildings scored, high/critical risk count
- Address / BIN / BBL / zip search bar
- Bulk CSV export buttons for all four tables
- **Run Scoring** button triggers `score.py` logic in-browser

#### Search results — `/search?q=<term>`

**Advanced filter bar** — all filters can be combined:

| Filter | Input |
|---|---|
| Keyword / BIN / BBL / zip | Text (existing search bar) |
| Zip code | Text field |
| Building class | Text prefix (e.g. `D`, `R`, `A`) |
| Year built range | From / To year inputs |
| Risk level | Dropdown: Any / Low / Moderate / High / Critical |
| Has violations | Checkbox |
| Asbestos flags only | Checkbox |
| Has energy data | Checkbox |

**View toggle** — switch between **Table** and **Map** view without re-running the search:
- **Table**: sortable results with risk badge, GHG (measured or estimated*), violations, asbestos count
- **Map**: Leaflet map with clustered markers; popup shows address, risk, GHG, violations; click to open building detail

#### Building detail — `/building/<BIN>`

- **Risk score card** — score number, label (colour-coded), confidence level, and plain-English breakdown of what drove the score (e.g. "pre-1940 (+3); 12 open violations (+8); 2 ACP-7 projects (+6)")
- **Carbon estimate card** — annual GHG in metric tons CO₂e; badged as **measured** (LL84/97 data) or **modelled** (class-median estimate); shows peer building count for modelled estimates
- **Profile card** — year built, building class, land use, floors, units, building/lot area
- **Energy & Emissions card** — LL84/97 data by year; **Table / Chart toggle**
  - Chart: dual-axis line (GHG left axis, Site EUI right axis)
  - Energy Star badges colour-coded: green ≥ 75, yellow ≥ 50, red < 50
- **Violations donut chart** — split by agency, with explanatory card
- **Violations table** — all violations; asbestos-flagged rows highlighted; live filter input
- **Asbestos projects table** — ACP-7 records with contractor and air monitor

#### Charts & Map — `/charts`

Six tabs — the first five are Chart.js analytics; the sixth is the full interactive map:

| Tab | Contents |
|---|---|
| **Overview** | Violations by source (bar) · Building class distribution (donut) |
| **Age & Class** | Decade histogram · Class counts · Avg GHG by class |
| **Energy & Emissions** | Top 20 GHG emitters · Energy Star distribution · GHG by class |
| **Violations** | Filed per year by agency with **linear ↔ log** and **line ↔ bar** toggles |
| **Asbestos** | Projects by status (donut) · Data notes |
| **🗺 Map** | Full Queens map with all buildings, **Color by** toggle (Risk / GHG / Age), **Filter risk** buttons (Low / Moderate / High / Critical), MarkerCluster for performance |

#### Standalone Map — `/map`

Full-screen map with a filter sidebar:
- Filter by keyword, zip, building class, year range, risk level, asbestos-only
- **Color by**: Risk score · GHG · Year built
- Dynamic legend updates when color mode changes
- Loads buildings via `/api/buildings.geojson` (up to 8,000 at a time)
- Marker popups show address, BIN, class, year, risk, GHG, violations; link to building detail
- Press Enter in any filter field or click Apply to reload

#### GeoJSON API — `/api/buildings.geojson`

Returns a GeoJSON FeatureCollection for use by both map views. Accepts all filter params as query strings:

```
/api/buildings.geojson?limit=5000
/api/buildings.geojson?zip=11101&risk=High
/api/buildings.geojson?year_min=1900&year_max=1940&asbestos=1
/api/buildings.geojson?q=Jamaica&class=D
```

#### SQL Query — `/query`

- Write and run any `SELECT` statement against the database
- Results display in a scrollable table
- **Chart toggle** — any result with a text column plus numeric columns gets an automatic chart with controls:
  - Chart type: **Bar / Line / Donut**
  - Orientation: **Vertical / Horizontal**
- **Download CSV** button for any query result
- Schema sidebar listing all tables and key columns
- Six pre-built example queries (click to load):
  - Buildings with most violations
  - Highest GHG emitters
  - Asbestos violations by agency
  - Buildings with open violations
  - Pre-1940 buildings
  - Energy Star average by building class

#### CSV export endpoints

Direct download links — no form submission needed:

```
/export/buildings.csv
/export/violations.csv
/export/energy.csv
/export/asbestos.csv
```

Custom query export (POST from query page) → `query_results.csv`
Per-building export → `/building/<BIN>/export.csv`

---

## Project Structure

```
carbonshift/
├── run.py                          # Ingestion pipeline CLI
├── score.py                        # Scoring pipeline CLI (carbon + risk)
├── query.py                        # Command-line query & export tool
├── web.py                          # Web server entry point
├── requirements.txt                # Python dependencies
├── .env.example                    # Config template — copy to .env
├── .gitignore
├── README.md
└── src/
    ├── db/
    │   ├── schema.sql              # Full DDL (standard SQL)
    │   └── init_db.py              # DB init + connection helper + migration
    ├── ingestion/
    │   ├── socrata.py              # Pagination helper, sample(), retry logic
    │   ├── fetch_crosswalk.py      # Step 1: Building Footprints
    │   ├── fetch_pluto.py          # Step 2: PLUTO
    │   ├── fetch_hpd.py            # Step 3: HPD violations
    │   ├── fetch_dob.py            # Step 4: DOB Safety + Legacy + ECB
    │   ├── fetch_acp7.py           # Step 5: ACP-7 asbestos projects
    │   └── fetch_ll84_97.py        # Step 6: LL84/97 energy disclosures
    ├── scoring/
    │   ├── carbon.py               # Modelled EUI / GHG estimation → carbon_estimates
    │   └── risk.py                 # Point-weighted risk scoring → building_risk_scores
    ├── query/
    │   ├── lookup.py               # Search (with filters), get_building, buildings_geojson, run_sql
    │   ├── export.py               # CSV export (named tables + custom SQL)
    │   └── charts.py               # Chart.js data builders (dataset-level + per-building)
    ├── validate/
    │   └── check_coverage.py       # Post-ingestion validation report
    └── web/
        ├── app.py                  # Flask routes (pages + GeoJSON API + scoring API)
        └── templates/
            ├── base.html           # Navbar, Bootstrap 5 CDN, shared styles, dark mode tokens + toggle
            ├── index.html          # Home page with stats and search
            ├── results.html        # Search results — table view + map toggle + filter bar
            ├── building.html       # Building detail: risk card, carbon card, charts
            ├── charts.html         # Analytics dashboard (5 chart tabs + Map tab)
            ├── map.html            # Standalone full-screen map with filter sidebar
            └── query.html          # SQL editor with auto-chart toggle
```

---

## Datasets Ingested

| # | Name | Dataset ID | Queens filter | Destination |
|---|---|---|---|---|
| 1 | Building Footprints | `5zhs-2jue` | `bin >= '4000000' AND bin < '5000000'` | `building_crosswalk` |
| 2 | PLUTO | `64uk-42ks` | `borough='QN'` | `buildings`, `building_profiles` |
| 3 | HPD Housing Maintenance Code Violations | `wvxf-dwi5` | `boroid='4'` (BBL post-filtered against crosswalk) | `building_violations` |
| 4 | DOB Safety Violations | `855j-jady` | `bin >= '4000000' AND bin < '5000000'` (BIN post-filtered against `buildings`) | `building_violations` |
| 5 | DOB Violations (legacy BIS) | `3h2n-5cm9` | `boro='4'` (BBL post-filtered against `buildings`) | `building_violations` |
| 6 | DOB ECB Violations | `6bgk-3dad` | `bin >= '4000000' AND bin < '5000000'` (BIN post-filtered against `buildings`) | `building_violations` |
| 7 | Asbestos Control Program ACP-7 | `vq35-j9qm` | `bin >= '4000000' AND bin < '5000000'` (BIN post-filtered against `buildings`) | `asbestos_projects` |
| 8 | NYC Building Energy & Water Disclosure (LL84/97) | `5zyy-y8am` | `upper(borough)='QUEENS'` (BIN post-filtered against `buildings`) | `energy_emissions` |

**Not ingested (by design):**
- ACP-5 asbestos assessment reports — no public bulk API exists; portal-only at `a826-web01.nyc.gov`
- Dataset `4t62-jm4m` — 2018 vintage LL84, nine years stale; `5zyy-y8am` is the correct current dataset

### Field name notes (confirmed against live API)

These differ from what the field names might appear to be — the fetchers handle each explicitly:

| Dataset | Quirk |
|---|---|
| Building Footprints | No plain `bbl` field — uses `mappluto_bbl` as the billing BBL |
| PLUTO | BBL stored as float string (`2054800111.00000000`) — normalised via `int(float(raw))` |
| HPD | No `bbl` field — BBL constructed from `boroid` + `block` + `lot` (zero-padded to 10 digits) |
| DOB Safety | Field names have underscores: `violation_remarks`, `violation_issue_date`, `violation_status` |
| DOB Legacy | No `bin` field at all — BBL constructed from `boro` + `block` + `lot`, then BIN looked up from crosswalk |
| DOB ECB | `penality_imposed` is a typo in the dataset itself (not a code error) |
| ACP-7 | Control number field is `tru`; status is `status_description` |
| LL84/97 | BBL is `nyc_borough_block_and_lot`; BIN is `nyc_building_identification`; GHG is `total_location_based_ghg` |

---

## Database Schema

```
building_crosswalk      BIN ↔ BBL ↔ BASE_BBL — the join spine for all other tables
buildings               One row per building: address, lat/lng, zip, block, lot
building_profiles       PLUTO: year built, class, land use, sq ft, floors, units
building_violations     All HPD/DOB/ECB violations — source-tagged, with asbestos flag
asbestos_projects       ACP-7 abatement notifications
energy_emissions        LL84/97 GHG + EUI + Energy Star, one row per building per year
carbon_estimates        GHG estimate per building: measured or class/borough-median modelled
building_risk_scores    Point-weighted risk score, label, confidence, and detail text
building_record_sources Provenance trail: dataset ID, URL, timestamp per record
```

### `carbon_estimates` columns

| Column | Description |
|---|---|
| `building_id` | BIN (primary key) |
| `building_class` | PLUTO building class |
| `building_area` | Floor area in sq ft |
| `eui_source` | `measured` / `class_median` / `borough_median` |
| `site_eui` | Site energy use intensity (kBtu/ft²) |
| `ghg_intensity` | GHG per sq ft (mt CO₂e/ft²) |
| `estimated_ghg_metric_tons` | Annual GHG estimate (mt CO₂e) |
| `peer_building_count` | Number of measured peers used for the estimate |

### `building_risk_scores` columns

| Column | Description |
|---|---|
| `building_id` | BIN (primary key) |
| `risk_score` | Numeric score (0–40+) |
| `risk_label` | Low / Moderate / High / Critical |
| `confidence_label` | Low / Medium / High |
| `risk_detail` | Plain-English breakdown of contributing factors |
| `generated_at` | ISO timestamp of last scoring run |

Full DDL is in `src/db/schema.sql`.

### Useful queries to get started

```sql
-- All violations for one building
SELECT * FROM building_violations WHERE building_id = '4059918' ORDER BY issue_date DESC;

-- Top 20 GHG emitters (most recent year)
SELECT b.full_address, e.reporting_year, e.ghg_emissions_metric_tons_co2e
FROM energy_emissions e
JOIN buildings b ON b.bin = e.building_id
ORDER BY e.reporting_year DESC, e.ghg_emissions_metric_tons_co2e DESC
LIMIT 20;

-- Buildings with open violations
SELECT b.full_address, v.source_dataset, v.violation_class, v.issue_date
FROM building_violations v
JOIN buildings b ON b.bin = v.building_id
WHERE UPPER(v.current_status) LIKE '%OPEN%' OR UPPER(v.current_status) LIKE '%ACTIVE%'
LIMIT 50;

-- Asbestos exposure breakdown
SELECT source_dataset, COUNT(*) AS flagged
FROM building_violations
WHERE is_asbestos_related = 1
GROUP BY source_dataset;

-- Pre-1940 buildings with ACP-7 projects
SELECT b.full_address, p.year_built, COUNT(a.id) AS projects
FROM buildings b
JOIN building_profiles p ON p.building_id = b.bin
JOIN asbestos_projects a ON a.building_id = b.bin
WHERE p.year_built < 1940
GROUP BY b.bin
ORDER BY projects DESC;
```

---

## Known Gotchas

**Borough field names differ across datasets.** The pipeline filters using the numeric BBL/BIN prefix (`4` = Queens), not the free-text borough field, which appears as `"QUEENS"`, `"QN"`, `"Q"`, or integer `4` depending on the dataset.

**Socrata SoQL does not support `starts_with()` on all datasets.** Building Footprints, DOB Safety, DOB ECB, and ACP-7 reject `starts_with(bin, '4')` with a 400 error. All four use the equivalent range filter instead: `bin >= '4000000' AND bin < '5000000'`.

**LL84 rows can represent multiple buildings.** One disclosure row may list multiple BBLs and BINs in comma-delimited fields. `fetch_ll84_97.py` expands these into one `energy_emissions` row per resolved BIN — all sharing the same `source_property_id`.

**Asbestos violations are keyword-matched.** There is no standalone asbestos violations feed. `is_asbestos_related` is set by scanning violation description text for: `asbestos`, `ACM`, `abatement`, `ACP-5`, `ACP-7`.

**Run `crosswalk` then `pluto` before the remaining steps.** DOB, ACP-7, and LL84/97 post-filter their BINs against the `buildings` table (populated by the PLUTO step) to satisfy the `building_violations → buildings(bin)` and `asbestos_projects → buildings(bin)` foreign key constraints. Buildings present in the crosswalk but absent from PLUTO (e.g. parking structures, parks) will not receive violations or energy records. HPD filters by BBL against the crosswalk directly — the residential buildings HPD cites are universally covered by PLUTO.

**DOB Legacy dataset has no BIN field.** BIN is reconstructed from `boro` + `block` + `lot` and looked up in the `buildings` table. Buildings not present in `buildings` will be skipped.

**Web query tool is SELECT-only.** The `/query` route rejects any statement that does not start with `SELECT`. This is enforced in `src/query/lookup.py:run_sql`.

---

## What Comes Next

- Citywide search (currently Queens only)
- ACP-5 portal lookups (no bulk API exists — portal-only at `a826-web01.nyc.gov`)
- Con Edison utility data integration
- User accounts / saved searches
