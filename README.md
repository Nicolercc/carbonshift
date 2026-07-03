# CarbonShift — Queens + Manhattan Building Data Pipeline

CarbonShift ingests NYC Open Data building records for Queens and Manhattan, scores every building for carbon emissions and risk, and provides four ways to access the results: an ingestion pipeline, a scoring pipeline, a command-line query tool, and a browser-based web interface with interactive charts, a MapLibre map with real building footprints, advanced filters, and CSV export.

**Current product/frontend direction:** see [`docs/README.md`](docs/README.md). The next MVP direction is a map-first civic climate intelligence product with Flask as the JSON data API and a future Next.js frontend as the presentation layer.

**Scope note:** Manhattan ingestion for buildings, violations, footprints, and asbestos projects is complete and live in the local Postgres database. Manhattan energy/emissions (LL84/97) has **not** been ingested yet — see [Datasets Ingested](#datasets-ingested) and [What Comes Next](#what-comes-next). The frontend (map viewport, page copy) is still Queens-only in several places — see [What Comes Next](#what-comes-next).

---

## Table of Contents

1. [Tech Stack](#tech-stack)
2. [Prerequisites](#prerequisites)
3. [For Collaborators — Getting the Latest Work](#for-collaborators--getting-the-latest-work)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Quick Start](#quick-start)
7. [Pipeline — `run.py`](#pipeline----runpy)
8. [Scoring — `score.py`](#scoring----scorepy)
9. [Query CLI — `query.py`](#query-cli----querypy)
10. [Web Interface — `web.py`](#web-interface----webpy)
11. [Project Structure](#project-structure)
12. [Datasets Ingested](#datasets-ingested)
13. [Database Schema](#database-schema)
14. [Building Footprints](#building-footprints)
15. [Live Data State](#live-data-state)
16. [Known Gotchas](#known-gotchas)
17. [What Comes Next](#what-comes-next)

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Language** | Python 3.10+ | Type hints, broad ecosystem, walrus operator |
| **Database** | PostgreSQL 16+ with PostGIS | Building footprint geometry requires PostGIS; SQLite is no longer supported |
| **HTTP** | `requests` | Stable session handling, retries, header management |
| **Config** | `python-dotenv` | Keeps secrets out of code and version control |
| **Web framework** | `flask` 3.x | Lightweight; Jinja2 templates bundled; no build step |
| **Charts** | Chart.js 4 (CDN) | Loaded from CDN — no npm/bundler required |
| **Maps** | MapLibre GL + React (Vite) | `/map` embeds a Vite-built React island inside the Flask template; `npm run build` emits static assets to `src/web/static/map/` — single server on port 5050, not a separate Node app |
| **Data manipulation** | `pandas` | Available for future transform work |
| **Data source** | NYC Open Data (Socrata REST API) + NYC ArcGIS (FeatureServer) | Socrata for 7 of 8 datasets; ArcGIS specifically for Manhattan building footprints (see [Datasets Ingested](#datasets-ingested)) |

### From this to this: the SQLite → Postgres migration

The project was originally built and validated on SQLite (see [Live Data State](#live-data-state) for why that's now historical). It moved to PostgreSQL 16+ with PostGIS for one concrete reason: **building footprint polygons**. Real building outlines are stored as `geometry(MultiPolygon, 4326)` columns and served to the map via `ST_AsGeoJSON` — neither the PostGIS type nor that function exists in SQLite. Once footprints needed real geometry, SQLite was no longer an option for any part of the schema, not just the footprints table.

**SQLite is no longer supported at all — not as a fallback.** `get_connection()` in `src/db/init_db.py` raises immediately if `DATABASE_URL` is unset:

```
RuntimeError: DATABASE_URL is not set. SQLite is no longer supported —
building footprints require PostGIS (Postgres).
Set DATABASE_URL=postgresql://... before starting the server.
```

This is deliberate — a silent SQLite fallback would let the app boot against a schema that can't hold footprint geometry, and the map would fail confusingly downstream instead of failing loudly at startup.

### Key architectural decisions

**BIN as the universal building key.** BBLs change when lots merge or subdivide; street addresses are ambiguous. Building Footprints carries both BIN and BBL on every record, so every other dataset is joined through it — no hand-constructed BBL strings.

**One `building_violations` table.** HPD, DOB Safety, DOB Legacy, and DOB ECB violations all go into a single source-tagged table. This keeps "all violations for building X" queries simple and lets the asbestos keyword scan run once across all agencies.

**Shared query module.** `src/query/` is used by both `query.py` (CLI) and the Flask web app, so changes to lookup or export logic apply everywhere.

**Standard SQL only, with one caveat.** The original design goal — SQLite-compatible standard SQL that migrates cleanly to Postgres — held until PostGIS became a requirement. `schema_pg.sql` is now the source of truth for the schema; `src/db/schema.sql` (SQLite DDL) is retained for historical reference only and is not applied by any code path when `DATABASE_URL` is set.

---

## Prerequisites

- Python 3.10 or newer
- PostgreSQL 16+ with PostGIS 3.x — required to run the server. Postgres.app (macOS) includes PostGIS. Run `CREATE EXTENSION IF NOT EXISTS postgis;` once in the target database, or use `migrate_to_pg.py` which does this automatically.
- A free NYC Open Data (Socrata) API token — without it requests throttle after a few hundred rows per dataset

---

## For Collaborators — Getting the Latest Work

The active development branch is `nr/map-integration`, not `main`. `main` reflects the last stable, deployable state; ongoing Manhattan expansion and Postgres/Supabase migration work happens on `nr/map-integration` until it's fully verified and ready to merge.

To see the current work:

**If you don't have the repo yet:**

```bash
git clone https://github.com/Nicolercc/carbonshift.git
cd carbonshift
git checkout nr/map-integration
```

**If you already have it cloned:**

```bash
git fetch origin
git checkout nr/map-integration
git pull origin nr/map-integration
```

From there, follow the [Installation](#installation) and [Configuration](#configuration) sections below.

### Database Setup

This app requires PostgreSQL 16+ with the PostGIS extension — SQLite is not supported. You have two options:

**Option 1 — use the shared Supabase project (recommended for collaborators)**

Ask Nicole for the `DATABASE_URL` connection string. Add it to a `.env` file at the repo root (never commit this file — it's already gitignored):

```
DATABASE_URL=postgresql://postgres.xxxxxxxx:password@aws-0-us-east-1.pooler.supabase.com:6543/postgres
SOCRATA_APP_TOKEN=your_token_here
```

Then run the app normally (`python web.py`). The database already has Queens and Manhattan data loaded — no ingestion needed.

**Option 2 — run your own local Postgres**

Install Postgres 16+ with PostGIS (Postgres.app on macOS includes it), create a database, enable the extension, and run the full pipeline:

```bash
createdb carbonshift_queens
psql carbonshift_queens -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# Point the app at your local database
echo 'DATABASE_URL=postgresql://localhost:5432/carbonshift_queens' >> .env

# Run ingestion (30–90 min) then scoring
python run.py
python score.py
```

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
| `psycopg2` | ≥ 2.9 | Postgres driver (`execute_values`, connection handling) |

---

## Configuration

```bash
cp .env.example .env
```

Edit `.env`:

```
DATABASE_URL=postgresql://nicolerodriguez@localhost:5432/carbonshift_queens   # Required — Postgres with PostGIS
SOCRATA_APP_TOKEN=xxxxxxxxxxxx    # Required for full dataset pulls (see below)
BOROUGH_CODE=4                    # Queens — Manhattan uses code 1; see Datasets Ingested
```

**Known gap:** `.env.example` itself still shows the old `DB_PATH=data/carbonshift.db` / SQLite-era template, not `DATABASE_URL`. It has not been updated to match. Use the block above, not the template file, until `.env.example` is fixed.

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
# → open http://localhost:5050
```

---

## Pipeline — `run.py`

The pipeline fetches Queens datasets from NYC Open Data and loads them into Postgres. Run this before using the query tool or web interface. Manhattan ingestion is a separate set of scripts — see [Datasets Ingested](#datasets-ingested) — not yet wired into `run.py`'s step flags.

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

Manhattan equivalents (`fetch_manhattan_pluto.py`, `fetch_manhattan_violations.py`, `fetch_manhattan_acp7.py`, `fetch_manhattan_footprints.py`) are run directly as scripts, not via `run.py --step`. There is no `fetch_manhattan_ll84_97.py` — that ingestion has not been written.

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

For buildings **with** measured LL84/97 data: records actual GHG and EUI directly. Since Manhattan has no LL84/97 data ingested yet, every Manhattan building is currently scored via the modelled path below — there are no `measured` Manhattan rows.

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

**Postgres compatibility fixes applied to `score.py`** (see [Known Gotchas](#known-gotchas) for the full story):
- `conn.executemany(...)` (SQLite) → `psycopg2.extras.execute_values(...)` in both `src/scoring/carbon.py` and `src/scoring/risk.py`
- `INSERT OR REPLACE INTO ...` (SQLite) → `INSERT ... ON CONFLICT (building_id) DO UPDATE SET ...` in both scoring modules
- The `sqlite_master`-based `_migrate()` schema-migration step in `src/db/init_db.py` no longer runs at all under Postgres — `init_db()` short-circuits to a no-op print statement when `DATABASE_URL` is set, and schema changes are applied via `schema_pg.sql` / `migrate_to_pg.py` instead

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
# Default: http://localhost:5050
python web.py

# Custom port
python web.py --port 8080

# Accessible on your local network (e.g. from another device)
python web.py --host 0.0.0.0 --port 8080

# Development mode — auto-reloads when code changes
python web.py --debug
```

**Why port 5050?** macOS AirPlay Receiver (Monterey and later) binds to `*:5000` on all interfaces including IPv6. Because macOS resolves `localhost` to `::1` first, `http://localhost:5000` hits AirPlay (HTTP 403) rather than Flask. Port 5050 is unoccupied and reserved for this project to avoid collisions with other local dev servers.

### Dark Mode

CarbonShift ships with a built-in dark mode. A moon/sun toggle button sits in the top-right corner of the navigation bar on every page.

- **Toggle**: click the moon (🌙) icon to switch to dark mode; click the sun (☀) icon to switch back.
- **Persistence**: the choice is saved to `localStorage` under the key `cs-theme` and restored automatically on every page load — no flicker on revisit.
- **Scope**: Bootstrap 5.3's `data-bs-theme` attribute drives the colour switch for all Bootstrap components (cards, forms, tables, badges, dropdowns, buttons). Custom design tokens (`--cs-*` CSS variables defined in `base.html`) extend dark mode to the app's own styles: hover rows, asbestos-highlighted rows, building links, card shadows, and card header borders.
- **Charts**: Chart.js canvases read `data-bs-theme` at render time and apply dark axis labels and grid lines when dark mode is active. Chart colours are intentional and remain the same in both modes for consistency.
- **Map**: marker/footprint colours are semantic (risk/GHG/age) and are unchanged by theme.

### Pages

#### Home — `/`

- Dataset stats dashboard: building count, violations, energy coverage, asbestos flags, buildings scored, high/critical risk count
- Address / BIN / BBL / zip search bar
- Bulk CSV export buttons for all four tables
- **Run Scoring** button triggers `score.py` logic in-browser
- **Not yet updated for Manhattan**: page copy still reads "Queens Building Carbon Intelligence" / "Queens · NYC Open Data" (see [What Comes Next](#what-comes-next))

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

**View toggle** — switch between **Table** and **Map** view without re-running the search.

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

Six tabs — the first five are Chart.js analytics; the sixth is the full interactive map.

#### Standalone Map — `/map`

Full-screen map with a filter sidebar:
- Filter by keyword, zip, building class, year range, risk level, asbestos-only
- **Color by**: Risk score · GHG · Year built
- Dynamic legend updates when color mode changes
- Loads buildings via `/api/buildings.geojson` (up to 8,000 at a time); each building is drawn as its **real NYC footprint outline**, not a synthetic square
- Marker popups show address, BIN, class, year, risk, GHG, violations; link to building detail
- Press Enter in any filter field or click Apply to reload
- **Not yet updated for Manhattan**: the map's default viewport (`queensBounds` in `src/components/map/mapConfig.ts`) is hardcoded to a Queens bounding box, so Manhattan buildings only appear if a user pans/zooms there manually — see [What Comes Next](#what-comes-next)

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
- **Chart toggle**, **Download CSV**, schema sidebar, six pre-built example queries

#### CSV export endpoints

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
├── run.py                              # Queens ingestion pipeline CLI
├── score.py                            # Scoring pipeline CLI (carbon + risk)
├── query.py                            # Command-line query & export tool
├── web.py                              # Web server entry point
├── migrate_to_pg.py                    # One-time SQLite → local Postgres migration
├── migrate_to_supabase.py              # local Postgres (DATABASE_URL) → Supabase (SUPABASE_DATABASE_URL)
├── verify_pg.py                        # Row-count verification after a migration
├── schema_pg.sql                       # Postgres DDL — source of truth (PostGIS types, ON CONFLICT-safe constraints)
├── requirements.txt                    # Python dependencies
├── .env.example                        # Config template — copy to .env (currently stale, see Configuration)
├── .gitignore
├── README.md
└── src/
    ├── db/
    │   ├── schema.sql                  # SQLite DDL — historical reference only, not applied under Postgres
    │   └── init_db.py                  # Connection routing; SQLite path is dead code when DATABASE_URL is set
    ├── ingestion/
    │   ├── socrata.py                  # Pagination helper, sample(), retry logic, deterministic $order support
    │   ├── fetch_crosswalk.py          # Queens step 1: Building Footprints (Socrata)
    │   ├── fetch_pluto.py              # Queens step 2: PLUTO
    │   ├── fetch_hpd.py                # Queens step 3: HPD violations
    │   ├── fetch_dob.py                # Queens step 4: DOB Safety + Legacy + ECB
    │   ├── fetch_acp7.py               # Queens step 5: ACP-7 asbestos projects
    │   ├── fetch_ll84_97.py            # Queens step 6: LL84/97 energy disclosures (Queens only — no Manhattan equivalent exists)
    │   ├── fetch_footprints.py         # Queens building footprints (Socrata, PostGIS geometry)
    │   ├── fetch_manhattan_pluto.py    # Manhattan: crosswalk + PLUTO
    │   ├── fetch_manhattan_violations.py  # Manhattan: HPD + DOB Safety + Legacy + ECB
    │   ├── fetch_manhattan_acp7.py     # Manhattan: ACP-7 asbestos projects
    │   └── fetch_manhattan_footprints.py  # Manhattan building footprints (ArcGIS, not Socrata — see Datasets Ingested)
    ├── scoring/
    │   ├── carbon.py                   # Modelled EUI / GHG estimation → carbon_estimates
    │   └── risk.py                     # Point-weighted risk scoring → building_risk_scores
    ├── query/
    │   ├── lookup.py                   # Search (with filters), get_building, buildings_geojson, run_sql
    │   ├── export.py                   # CSV export (named tables + custom SQL)
    │   └── charts.py                   # Chart.js data builders (dataset-level + per-building)
    ├── validate/
    │   └── check_coverage.py           # Post-ingestion validation report
    ├── components/map/                 # MapLibre React island — footprint rendering, insight card, search, legend
    └── web/
        ├── app.py                      # Flask routes (pages + GeoJSON API + scoring API)
        └── templates/                  # Jinja2 templates (index, results, building, charts, map, query, methodology)
```

---

## Datasets Ingested

| # | Name | Dataset ID / Source | Queens filter | Manhattan filter | Destination |
|---|---|---|---|---|---|
| 1 | Building Footprints | Queens: Socrata `5zhs-2jue` · Manhattan: **ArcGIS `BUILDING_view` FeatureServer** (different source — see below) | `bin >= '4000000' AND bin < '5000000'` | `feature_code=2100`, Manhattan BIN range | `building_footprints` |
| 2 | PLUTO | `64uk-42ks` | `borough='QN'` | `borough='MN' AND bldgarea > 0` | `buildings`, `building_profiles` |
| 3 | HPD Housing Maintenance Code Violations | `wvxf-dwi5` | `boroid='4'` | `boroid='1'` | `building_violations` |
| 4 | DOB Safety Violations | `855j-jady` | `bin >= '4000000' AND bin < '5000000'` | `bin >= '1000000' AND bin < '2000000'` | `building_violations` |
| 5 | DOB Violations (legacy BIS) | `3h2n-5cm9` | `boro='4'` | `boro='1'` | `building_violations` |
| 6 | DOB ECB Violations | `6bgk-3dad` | `bin >= '4000000' AND bin < '5000000'` | `bin >= '1000000' AND bin < '2000000'` | `building_violations` |
| 7 | Asbestos Control Program ACP-7 | `vq35-j9qm` | `bin >= '4000000' AND bin < '5000000'`, `$order=:id` | `bin >= '1000000' AND bin < '2000000'`, `$order=:id` | `asbestos_projects` |
| 8 | NYC Building Energy & Water Disclosure (LL84/97) | `5zyy-y8am` | `upper(borough)='QUEENS'` | **Not ingested** — no `fetch_manhattan_ll84_97.py` exists yet | `energy_emissions` |

**Why Manhattan footprints use a different source entirely.** Queens footprints came from the Socrata Building Footprints export (`5zhs-2jue`) with full coverage: 86,677 Queens records, matching the borough's real building stock. Confirmed by direct query against the authoritative source, that same Socrata export covers only **~17.8% of Manhattan's real buildings** — 7,946 records against Manhattan's actual footprint count. Using Socrata for Manhattan would have silently left over 80% of buildings without a footprint on the map. `fetch_manhattan_footprints.py` pulls from the NYC ArcGIS `BUILDING_view` FeatureServer instead, which returns 44,607 Manhattan records — the complete set. This is a genuine source substitution, not a stylistic choice: the two fetchers parse different geometry formats (ArcGIS returns `Polygon`, wrapped to `MultiPolygon` before insert; BIN/DOITT_ID arrive as integers and are cast to string) and Manhattan needs no Socrata app token since the ArcGIS service is public.

**Not ingested (by design):**
- ACP-5 asbestos assessment reports — no public bulk API exists; portal-only at `a826-web01.nyc.gov`
- Dataset `4t62-jm4m` — 2018 vintage LL84, nine years stale; `5zyy-y8am` is the correct current dataset

**Not ingested (not by design — genuinely unfinished):**
- Manhattan LL84/97 energy & emissions data — see [What Comes Next](#what-comes-next)

### Field name notes (confirmed against live API)

| Dataset | Quirk |
|---|---|
| Building Footprints (Queens/Socrata) | No plain `bbl` field — uses `mappluto_bbl` as the billing BBL |
| Building Footprints (Manhattan/ArcGIS) | `bin` and `doitt_id` are integers in ArcGIS JSON, not strings — cast explicitly before insert |
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
energy_emissions        LL84/97 GHG + EUI + Energy Star, one row per building per year (Queens only)
carbon_estimates        GHG estimate per building: measured or class/borough-median modelled
building_risk_scores    Point-weighted risk score, label, confidence, and detail text
building_record_sources Provenance trail: dataset ID, URL, timestamp per record
building_footprints     PostGIS: real building polygon geometry, keyed by doitt_id (not bin — see below)
```

### `building_footprints` columns

| Column | Description |
|---|---|
| `doitt_id` | Primary key — the footprint dataset's own unique record ID (not `bin`; see rationale in [Building Footprints](#building-footprints)) |
| `bin` | Building identifier — indexed, joined to `buildings.bin`, not guaranteed unique within this table |
| `mappluto_bbl`, `base_bbl` | BBL fields carried through from the source dataset |
| `last_status_type`, `feature_code` | Source metadata (construction status, feature classification) |
| `geom` | `geometry(MultiPolygon, 4326)` — the actual footprint shape |

### The `asbestos_projects` unique constraint — a real bug, not a formality

`asbestos_projects` now has:

```sql
ALTER TABLE asbestos_projects
  ADD CONSTRAINT uq_acp7_building_cn UNIQUE (building_id, control_number);
```

**The bug this fixes:** ACP-7 ingestion paginates through Socrata with `$limit`/`$offset`. Without a `$order` clause, Socrata does not guarantee a stable row order between requests — as the underlying table changes (or simply due to how Socrata internally serves paginated results without an explicit sort), the same records could be returned across multiple offset pages, or re-fetched entirely on a re-run of the script, with no application-side de-duplication. The result: massive duplicate rows in **both** boroughs. On Supabase's still-unfixed copy of this table, one Queens `(building_id, control_number)` pair — `(4216655, TRU0930QN25)` — appears **252 times**; the table has 13,009 total rows behind only 4,237 distinct pairs.

**The fix, in two parts:**
1. `src/ingestion/socrata.py`'s `paginate()` now accepts an `order` parameter that sets `$order` on the Socrata request. Both `fetch_acp7.py` (Queens) and `fetch_manhattan_acp7.py` (Manhattan) call their pagination helper with a deterministic order (`:id`, Socrata's row-identity column) — confirmed at the call sites, not just declared as a default.
2. `INSERT ... ON CONFLICT (building_id, control_number) DO NOTHING` was added to both fetchers' insert statements. This clause is inert without a matching unique constraint or index — which is exactly why `uq_acp7_building_cn` had to be added before it could do anything.

With both pieces in place, the local Postgres database (`carbonshift_queens`) is clean: Manhattan 23,509/23,509 distinct pairs, Queens 4,237/4,237 distinct pairs — confirmed by direct query, not by re-running the buggy ingestion and hoping. See [Live Data State](#live-data-state) for the caveat that this fix has **not** yet been propagated to Supabase.

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

Full DDL is in `schema_pg.sql`.

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

## Building Footprints

Every building on the map used to appear as a small square. That square wasn't
real — the app took the building's single centre-point coordinate (latitude/
longitude from PLUTO) and drew a fixed-size box around it. It was enough to put
a dot in roughly the right place, but it said nothing about the actual shape,
size, or boundary of the building.

Queens and Manhattan buildings now show their **real outline** — the actual polygon recorded by
NYC's Department of City Planning when they photographed the city from the air.
An L-shaped apartment block, a building that wraps around a courtyard, a structure
that sits at an angle to the street — all of those are now drawn correctly. The
most complex footprints in Queens have over 200 vertices.

**Why a separate table?** The NYC Building Footprints dataset itself warns that
BIN values (the identifier shared with every other dataset) are not guaranteed to
be unique — some records have duplicate BINs, placeholder triangle shapes for
buildings that couldn't be measured precisely, or unassigned "million BINs" for
buildings never formally registered. If the footprint were stored as a single
column directly on the `buildings` table, a duplicate BIN would silently overwrite
the previous shape with no warning. Instead, footprints live in their own
`building_footprints` table keyed by `doitt_id` — the footprint dataset's own
unique record ID — so every shape is stored and none are silently dropped. When
the map loads, it picks the largest-area footprint for each BIN, so a real
building always wins over a placeholder triangle.

**PostGIS** is a Postgres extension that lets the database store geographic shapes
and answer spatial questions about them — in this app, that means holding each
building's polygon coordinates and converting them to GeoJSON in a single database
call rather than doing the conversion in Python.

**Coverage:** all 118,904 buildings in the local database (79,171 Queens + 39,733 Manhattan) have a real footprint match — no building on the map falls back to a synthetic square. Those figures are the PLUTO tax-lot universe: every parcel with recorded building area. That is the right scope for this app. LL84/97 energy reporting and carbon risk scoring are assessed at the tax-lot level — a multi-unit building and the parcel it sits on share one energy meter, one compliance obligation, and one risk score.

---

## Live Data State

**This section reports what's actually in each database, queried directly — not what commit messages say.**

### Local Postgres (`carbonshift_queens`) — current and authoritative

| Metric | Queens | Manhattan | Combined |
|---|---|---|---|
| Buildings | 79,171 | 39,733 | 118,904 |
| Violations | 460,927 | 2,783,287 | 3,244,214 |
| Asbestos projects (distinct pairs) | 4,237 | 23,509 | 27,746 |
| Risk scores | 79,171 | 39,733 | 118,904 |
| Carbon estimates | 78,793 | 39,733 | 118,526 |
| Building footprints | 86,677 | 44,607 | 131,284 |

The `uq_acp7_building_cn` unique constraint is present and enforced here. Manhattan risk and carbon scores show real, non-zero, non-uniform violation and asbestos signal — Manhattan's violation count (2.78M) is roughly 6x Queens's despite having about half the buildings, driven by a much larger HPD housing-violation history; this is a real reflection of the underlying data, not a scoring artifact.

### Supabase (`SUPABASE_DATABASE_URL`) — stale

Supabase currently reflects the **old, pre-Manhattan, pre-fix state**:

| Metric | Value on Supabase |
|---|---|
| Buildings | 79,171 (Queens only — no Manhattan rows) |
| Violations | 460,927 (Queens only) |
| Asbestos projects | 13,009 total rows, only 4,237 distinct pairs — **still duplicated, constraint not present** |
| Risk scores | 79,171 (Queens only) |
| Carbon estimates | 78,793 (Queens only) |
| Building footprints | 86,677 (Queens only) |

`migrate_to_supabase.py` (source: local `DATABASE_URL` → destination: `SUPABASE_DATABASE_URL`) exists in the repo but has not been re-run since Manhattan ingestion or the ACP-7 dedup fix landed locally. Anyone pointing the deployed app at Supabase today gets the old Queens-only, duplicate-asbestos dataset. Note also that `.env` in this repo currently defines `SUPABASE_DATABASE_URL` but not `DATABASE_URL` — the app as configured will refuse to start (`DATABASE_URL is not set`) until one is exported pointing at either the local Postgres instance or Supabase directly.

---

## Known Gotchas

**Borough field names differ across datasets.** The pipeline filters using the numeric BBL/BIN prefix (`4` = Queens, `1` = Manhattan), not the free-text borough field, which appears as `"QUEENS"`/`"QN"`/`"Q"` or `"MANHATTAN"`/`"MN"`/`"M"` depending on the dataset.

**Socrata SoQL does not support `starts_with()` on all datasets.** Building Footprints (Queens/Socrata), DOB Safety, DOB ECB, and ACP-7 reject `starts_with(bin, '4')` with a 400 error. All use the equivalent range filter instead: `bin >= '4000000' AND bin < '5000000'` (Queens) / `bin >= '1000000' AND bin < '2000000'` (Manhattan).

**ACP-7 pagination without deterministic ordering caused massive duplicate rows.** See [The `asbestos_projects` unique constraint](#the-asbestos_projects-unique-constraint--a-real-bug-not-a-formality) above for the full root cause and fix. Short version: no `$order` on paginated Socrata requests meant re-fetches and page overlaps produced the same `(building_id, control_number)` pair dozens to hundreds of times over. Fixed by adding `$order=:id` to both ACP-7 fetchers plus a `uq_acp7_building_cn` unique constraint with `ON CONFLICT DO NOTHING`.

**Three SQLite-isms had to be removed for Postgres, not just swapped 1:1:**
1. `conn.executemany(...)` → `psycopg2.extras.execute_values(...)` (`src/scoring/carbon.py`, `src/scoring/risk.py`, and both ACP-7 fetchers) — psycopg2 has no `executemany` equivalent with the same batch-insert performance characteristics.
2. `INSERT OR REPLACE INTO ...` (SQLite upsert syntax) → `INSERT ... ON CONFLICT (...) DO UPDATE SET ...` (Postgres upsert syntax) — these are not interchangeable; Postgres has no `OR REPLACE` clause at all.
3. `_migrate()` in `src/db/init_db.py`, which queried `sqlite_master` to detect existing tables/indexes, does not run under Postgres at all — `init_db()` short-circuits before reaching it when `DATABASE_URL` is set. Schema changes now go through `schema_pg.sql` and `migrate_to_pg.py` instead of an in-place migration function.

**Map tab "Failed to fetch" — two causes, both fixed.** The `/charts` Map tab and `/map` standalone page both call `GET /api/buildings.geojson?limit=8000`. Two bugs caused `TypeError: Failed to fetch` in the browser:
1. *Missing indexes on `building_violations`.* The two correlated `COUNT(*)` subqueries in `buildings_geojson()` ran as full table scans for every row returned. Fixed by adding `idx_bv_building_id` and `idx_bv_building_asbestos`.
2. *AirPlay port conflict on macOS*. Fixed by changing the default port to **5050**.

**LL84 rows can represent multiple buildings.** One disclosure row may list multiple BBLs and BINs in comma-delimited fields. `fetch_ll84_97.py` expands these into one `energy_emissions` row per resolved BIN — all sharing the same `source_property_id`. (Queens only — see [Datasets Ingested](#datasets-ingested).)

**Asbestos violations are keyword-matched.** There is no standalone asbestos violations feed. `is_asbestos_related` is set by scanning violation description text for: `asbestos`, `ACM`, `abatement`, `ACP-5`, `ACP-7`.

**Run `crosswalk` then `pluto` before the remaining steps.** DOB, ACP-7, and LL84/97 post-filter their BINs against the `buildings` table (populated by the PLUTO step) to satisfy the `building_violations → buildings(bin)` and `asbestos_projects → buildings(bin)` foreign key constraints.

**DOB Legacy dataset has no BIN field.** BIN is reconstructed from `boro` + `block` + `lot` and looked up in the `buildings` table. Buildings not present in `buildings` will be skipped.

**Web query tool is SELECT-only.** The `/query` route rejects any statement that does not start with `SELECT`. This is enforced in `src/query/lookup.py:run_sql`.

**Manhattan footprints use a different geometry pipeline than Queens.** ArcGIS returns plain `Polygon`, which is wrapped into `MultiPolygon` before insert to match the shared `geom` column type. If a future borough's footprint source also returns `Polygon`, the same wrapping step will be needed — it is not automatic across ingestion scripts.

---

## What Comes Next

- **Manhattan LL84/97 ingestion** — genuinely unfinished. No `fetch_manhattan_ll84_97.py` exists; `energy_emissions` has zero Manhattan rows; every Manhattan carbon estimate is currently `class_median`/`borough_median`, never `measured`.
- **Frontend still has hardcoded Queens-only viewport and copy** — genuinely unfinished, not a documentation gap:
  - `src/components/map/mapConfig.ts` exports `queensBounds`, used for the map's default `fitBounds` — Manhattan buildings are off-screen until a user manually pans/zooms there.
  - Page copy in `base.html`, `index.html`, `map.html`, `charts.html`, and map components (`buildingInsights.ts`, `buildingDataAdapter.ts`, `BuildingInsightCard.tsx`) still reads "Queens Building Carbon Intelligence," "Queens · NYC Open Data," "Queens-wide median," etc.
- **Supabase migration is stale** — `migrate_to_supabase.py` needs to be re-run against the current local Postgres state to bring Supabase's schema and data (Manhattan rows, the `uq_acp7_building_cn` constraint, deduplicated `asbestos_projects`) up to date. Until then, Supabase reflects the old Queens-only, duplicate-asbestos state described in [Live Data State](#live-data-state).
- **`.env.example` is stale** — still shows the SQLite-era `DB_PATH` template instead of the required `DATABASE_URL`.
- ACP-5 portal lookups (no bulk API exists — portal-only at `a826-web01.nyc.gov`)
- Con Edison utility data integration
- User accounts / saved searches
- Expansion beyond Queens + Manhattan to the remaining three boroughs
