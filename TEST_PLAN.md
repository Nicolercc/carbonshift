# CarbonShift — Test Plan
**Last updated:** June 26, 2026
**Purpose:** Diagnose, troubleshoot, and confirm every layer of the CarbonShift stack is working correctly. Run sections in order after a fresh install or after any significant change.

---

## Prerequisites

```bash
cd carbonshift
source venv/bin/activate
cp .env.example .env          # fill in SOCRATA_APP_TOKEN if not already set
```

All commands below assume the venv is active and you are in the project root.

---

## Section 1 — Environment

### 1.1 Python version

```bash
python --version
```

**Pass:** `Python 3.10.x` or higher.
**Fail:** Any 3.9 or lower — upgrade Python.

### 1.2 Dependencies installed

```bash
pip show flask requests python-dotenv pandas | grep -E "^Name|^Version"
```

**Pass:** All four packages listed with a version.
**Fail:** `WARNING: Package(s) not found` — run `pip install -r requirements.txt`.

### 1.3 Environment variables loaded

```bash
python3 -c "
from dotenv import load_dotenv; load_dotenv()
import os
token = os.getenv('SOCRATA_APP_TOKEN','')
db    = os.getenv('DB_PATH','')
bc    = os.getenv('BOROUGH_CODE','')
print('SOCRATA_APP_TOKEN:', 'SET' if token else 'MISSING')
print('DB_PATH:', db or 'MISSING')
print('BOROUGH_CODE:', bc or 'MISSING')
"
```

**Pass:** All three show values, `SOCRATA_APP_TOKEN` is `SET`.
**Fail:** Any `MISSING` — check `.env` exists and is correctly filled in. Without the token, Socrata throttles after a few hundred rows per dataset and ingestion will produce partial data.

---

## Section 2 — Database

### 2.1 Schema initialises cleanly

```bash
python3 -c "from src.db.init_db import init_db; init_db()"
```

**Pass:** Prints `Database initialised at data/carbonshift.db` with no traceback.
**Fail:** Any exception — check `src/db/schema.sql` syntax and that `data/` is writable.

### 2.2 All tables exist

```bash
python3 -c "
from dotenv import load_dotenv; load_dotenv()
from src.db.init_db import get_connection
conn = get_connection()
tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table' ORDER BY name\")]
print('Tables:', tables)
"
```

**Pass:** Output includes all nine: `asbestos_projects`, `building_crosswalk`, `building_profiles`, `building_record_sources`, `building_risk_scores`, `building_violations`, `buildings`, `carbon_estimates`, `energy_emissions`.
**Fail:** Any table missing — re-run `init_db()` or check `schema.sql`.

### 2.3 All performance indexes exist

```bash
python3 -c "
from dotenv import load_dotenv; load_dotenv()
from src.db.init_db import get_connection
conn = get_connection()
idx = {r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='index'\")}
required = {'idx_bv_building_id','idx_bv_building_asbestos','idx_bp_building_id','idx_ap_building_id','idx_ee_building_id'}
missing = required - idx
print('Missing indexes:', missing if missing else 'none — all present')
"
```

**Pass:** `Missing indexes: none — all present`.
**Fail:** Any index listed as missing — run `python web.py` once (it calls `init_db()` which creates missing indexes) or run `python3 -c "from src.db.init_db import init_db; init_db()"`.

### 2.4 Row counts are in a sane range

```bash
python3 -c "
from dotenv import load_dotenv; load_dotenv()
from src.db.init_db import get_connection
conn = get_connection()
for t in ['building_crosswalk','buildings','building_profiles','building_violations',
          'asbestos_projects','energy_emissions','carbon_estimates','building_risk_scores']:
    n = conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
    print(f'  {t}: {n:,}')
"
```

**Expected after a complete Queens ingest + score run:**

| Table | Expected range |
|---|---|
| `building_crosswalk` | ~350,000–370,000 |
| `buildings` | ~270,000–280,000 |
| `building_profiles` | ~270,000–280,000 |
| `building_violations` | ~1,500,000–1,800,000 |
| `asbestos_projects` | ~30,000–40,000 |
| `energy_emissions` | ~15,000–22,000 |
| `carbon_estimates` | ~270,000–280,000 |
| `building_risk_scores` | ~350,000–370,000 |

**Fail:** Any table at 0 after ingestion — that step either failed or filtered nothing (check the ingestion step order; `crosswalk` must run before `pluto`; `pluto` must run before `dob`/`acp7`/`ll84`).

---

## Section 3 — Socrata API connectivity

### 3.1 Sample all datasets

```bash
python run.py --sample
```

**Pass:** Eight blocks of output, each showing field names from 5 sample rows. No HTTP errors.
**Fail:** `HTTPError: 401` → token invalid or not set. `HTTPError: 429` → throttled (set token). `ConnectionError` → no internet.

### 3.2 Confirm field names (spot-check)

After `--sample`, verify these specific fields are present in the output:

| Dataset | Field to confirm |
|---|---|
| Building Footprints | `bin`, `mappluto_bbl`, `base_bbl` |
| PLUTO | `bbl`, `yearbuilt`, `bldgarea`, `bldgclass` |
| HPD | `boroid`, `block`, `lot`, `class` |
| DOB Safety | `bin`, `violation_number`, `violation_remarks` |
| DOB Legacy | `boro`, `block`, `lot`, `description` |
| DOB ECB | `bin`, `ecb_violation_number`, `penality_imposed` (typo is in the dataset) |
| ACP-7 | `bin`, `tru`, `status_description` |
| LL84/97 | `nyc_borough_block_and_lot`, `nyc_building_identification`, `total_location_based_ghg` |

**Fail:** Any field missing → Socrata may have renamed a column. Update the relevant fetcher's docstring and field references before re-running ingestion.

---

## Section 4 — Ingestion pipeline

Run steps individually to isolate failures. Each step prints running totals.

### 4.1 Crosswalk

```bash
python run.py --step crosswalk
```

**Pass:** Completes with `357,000+` rows inserted into `building_crosswalk`. No HTTP or database errors.
**Fail:** `400 Bad Request` from Socrata → check the SoQL filter; `starts_with()` is not supported, use `bin >= '4000000' AND bin < '5000000'`. `0 rows inserted` → filter is wrong.

### 4.2 PLUTO

```bash
python run.py --step pluto
```

**Pass:** `270,000+` rows in `buildings` and `building_profiles`.
**Fail:** `0 rows` → crosswalk must run first. `KeyError` on field name → PLUTO renamed a column; check `--sample` output.

### 4.3 HPD

```bash
python run.py --step hpd
```

**Pass:** `1,000,000+` violations in `building_violations` with `source_dataset = 'HPD'`.
**Fail:** `FOREIGN KEY constraint failed` → PLUTO step did not complete successfully; `buildings` table is missing rows that HPD is referencing.

### 4.4 DOB

```bash
python run.py --step dob
```

**Pass:** `400,000+` combined violations across DOB Safety, Legacy, and ECB.
**Fail:** `FOREIGN KEY constraint failed` → `pluto` must run before `dob`. The DOB fetchers load their BIN allowlist from `buildings`, not `building_crosswalk`.

### 4.5 ACP-7

```bash
python run.py --step acp7
```

**Pass:** `30,000+` rows in `asbestos_projects`.
**Fail:** `FOREIGN KEY constraint failed` → same as DOB; `pluto` must precede `acp7`.

### 4.6 LL84/97

```bash
python run.py --step ll84
```

**Pass:** `15,000+` rows in `energy_emissions`; output notes multi-BIN expansions.
**Fail:** `0 rows` → check the borough filter `upper(borough)='QUEENS'` and that `buildings` is populated.

### 4.7 Full validation report

```bash
python run.py --validate-only
```

Run this after all six steps complete. Review:
- Join coverage: crosswalk BINs with a resolved BBL should be >90%
- Measured split: `energy_emissions` rows / `buildings` rows — expect ~1–2%
- Violations per source: HPD should be the largest share (~70%), DOB ECB second
- Asbestos flag count: should be several hundred to a few thousand

---

## Section 5 — Scoring pipeline

### 5.1 Carbon estimates

```bash
python score.py --carbon-only
```

**Pass:** Prints class-median count, measured vs. modelled vs. skipped totals. `carbon_estimates` row count matches `buildings` minus skipped.
**Fail:** `no such table: energy_emissions` → LL84 step did not run. `0 measured` → energy data is empty; check LL84 step.

### 5.2 Risk scoring

```bash
python score.py --risk-only
```

**Pass:** Prints distribution across Low / Moderate / High / Critical. All four buckets should have non-zero counts.
**Fail:** `no such table: carbon_estimates` → run `--carbon-only` first. All buildings in one bucket → scoring weights may be misconfigured.

### 5.3 Single-building score (smoke test)

```bash
python score.py --building 4059918
```

**Pass:** Prints score, label, confidence, and detail breakdown for BIN `4059918`.
**Fail:** `Building not found` → that BIN did not make it into `buildings`; try a different BIN from `SELECT bin FROM buildings LIMIT 5`.

---

## Section 6 — Query CLI

### 6.1 Address search

```bash
python query.py search "Jamaica"
```

**Pass:** Table of results with address, BIN, year, class, violations, GHG.
**Fail:** `no results` after a completed ingest → check the address is in Queens; try `python query.py search "11432"` (Jamaica zip).

### 6.2 Building detail

```bash
python query.py building 4059918
```

**Pass:** Full detail block: identifiers, profile, energy table, violations, asbestos projects.
**Fail:** `Building not found` → BIN not in `buildings`.

### 6.3 Custom SQL

```bash
python query.py sql "SELECT source_dataset, COUNT(*) AS n FROM building_violations GROUP BY source_dataset ORDER BY n DESC"
```

**Pass:** Table with four rows: HPD, DOB_ECB, DOB_SAFETY, DOB_LEGACY, each with non-zero counts.
**Fail:** Empty result → `building_violations` is empty; re-run ingestion.

### 6.4 CSV export

```bash
python query.py export buildings --out /tmp/cs_test.csv && wc -l /tmp/cs_test.csv
```

**Pass:** Line count matches `buildings` row count + 1 (header).
**Fail:** `0 lines` or `1 line` (header only) → table is empty.

---

## Section 7 — Web server

### 7.1 Server starts on port 5050

```bash
python web.py &
sleep 2
curl -s -o /dev/null -w "HTTP %{http_code}" http://localhost:5050/
```

**Pass:** `HTTP 200`.
**Fail:** `HTTP 403` → wrong port; AirPlay Receiver is answering (this happens on port 5000 on macOS). Confirm the server printed `Running on http://127.0.0.1:5050`. `Connection refused` → server did not start; check for a Python error in the terminal.

### 7.2 Home page stats load

```bash
curl -s http://localhost:5050/ | grep -o 'display-6">[^<]*' | head -6
```

**Pass:** Four numbers visible (buildings, violations, energy coverage, asbestos flags). All non-zero.
**Fail:** All zeros → `init_db()` ran but tables are empty; run the ingestion pipeline.

### 7.3 Map API endpoint — timing and correctness

This is the endpoint that caused the "Failed to fetch" bug. Test it directly:

```bash
time curl -s -o /dev/null -w "HTTP %{http_code}  size=%{size_download}B  time=%{time_total}s\n" \
  "http://localhost:5050/api/buildings.geojson?limit=8000"
```

**Pass:** `HTTP 200`, size `>1MB`, time `<5s`.
**Fail:**
- `HTTP 403` with `Server: AirTunes` → wrong port; see 7.1.
- Time `>30s` or connection dropped → indexes are missing; run `python3 -c "from src.db.init_db import init_db; init_db()"` then retest.
- `HTTP 500` → check Flask terminal output for a Python traceback.

### 7.4 Map API — response structure

```bash
curl -s "http://localhost:5050/api/buildings.geojson?limit=5" | python3 -c "
import json, sys
gj = json.load(sys.stdin)
print('type:', gj.get('type'))
print('features:', len(gj.get('features', [])))
f = gj['features'][0]
print('geometry type:', f['geometry']['type'])
print('coords:', f['geometry']['coordinates'])
print('props keys:', list(f['properties'].keys()))
"
```

**Pass:** `type: FeatureCollection`, 5 features, geometry `Point`, coordinates are two floats, properties include `bin`, `address`, `risk_label`, `ghg`, `violations`.
**Fail:** `features: 0` → no buildings with lat/lon in `buildings`; check PLUTO ingestion. `KeyError` on a property → `buildings_geojson()` in `src/query/lookup.py` is missing a column.

### 7.5 Map API — filter params

```bash
curl -s "http://localhost:5050/api/buildings.geojson?limit=10&risk=Critical" | \
  python3 -c "import json,sys; gj=json.load(sys.stdin); [print(f['properties']['risk_label']) for f in gj['features']]"
```

**Pass:** All printed labels are `Critical`.
**Fail:** Other labels present → risk filter in `buildings_geojson()` is broken.

### 7.6 Search endpoint

```bash
curl -s "http://localhost:5050/search?q=Jamaica" | grep -c "building-link"
```

**Pass:** Count `> 0`.
**Fail:** `0` → no results returned; check `search_buildings()` in `src/query/lookup.py`.

### 7.7 Building detail page

```bash
curl -s "http://localhost:5050/building/4059918" | grep -o "<title>[^<]*</title>"
```

**Pass:** Title contains the building address or BIN.
**Fail:** `404` → BIN not in database. `500` → traceback in Flask terminal.

### 7.8 SQL query endpoint

```bash
curl -s -X POST "http://localhost:5050/query" \
  -d "sql=SELECT+COUNT(*)+AS+n+FROM+building_violations" | grep -o '"n":[0-9]*'
```

**Pass:** Returns a non-zero count.
**Fail:** `403` or `400` → non-SELECT was blocked (expected). `500` → check Flask terminal.

### 7.9 CSV export endpoints

```bash
for path in buildings violations energy asbestos; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:5050/export/${path}.csv")
  size=$(curl -s "http://localhost:5050/export/${path}.csv" | wc -l)
  echo "$path: HTTP $code, $size lines"
done
```

**Pass:** All four return `HTTP 200` with `> 1` line.
**Fail:** `0` or `1` lines (header only) → that table is empty.

### 7.10 Charts page

```bash
curl -s "http://localhost:5050/charts" | grep -c "canvas id="
```

**Pass:** Count `>= 2` (charts are rendered as `<canvas>` elements).
**Fail:** `0` → chart data not generated; run `python score.py` then reload.

---

## Section 8 — Dark mode

These checks require a browser. Open `http://localhost:5050` manually.

| Check | Expected |
|---|---|
| Click moon icon in navbar | Page switches to dark background, icon changes to sun |
| Reload the page | Dark mode is preserved (localStorage `cs-theme = dark`) |
| Click sun icon | Page switches back to light mode |
| Navigate to Charts, Map, Building detail | Dark mode persists across all pages |
| Open Charts tab with dark mode on | Chart axes/labels are light-coloured, not black-on-dark |
| Open Map tab | Map tiles render in standard (light) style; markers retain their risk colours |

---

## Section 9 — Known failure modes and quick fixes

| Symptom | Likely cause | Fix |
|---|---|---|
| `HTTP 403 Server: AirTunes` on port 5000 | macOS AirPlay Receiver owns port 5000 | Use `python web.py` (defaults to 5050) or `python web.py --port 5050` |
| Map tab "TypeError: Failed to fetch" | Missing `idx_bv_building_id` index | Run `python3 -c "from src.db.init_db import init_db; init_db()"` |
| Map tab shows "Failed to load buildings" with no buildings on the map | `buildings` table has no lat/lon | PLUTO ingestion incomplete; re-run `--step pluto` |
| `FOREIGN KEY constraint failed` on DOB/ACP-7/LL84 step | `pluto` step not run first | Run steps in order: crosswalk → pluto → hpd → dob → acp7 → ll84 |
| `starts_with()` 400 error from Socrata | SoQL function unsupported on that dataset | Use range filter: `bin >= '4000000' AND bin < '5000000'` |
| `database is locked` during ingestion | Flask web server holding an open connection | Kill `python web.py` before running `python run.py` |
| All chart tabs show "No data yet" | `score.py` not run | Run `python score.py` after ingestion completes |
| `0 rows inserted` on any step | Wrong step order or filter returning nothing | Check that prerequisite steps completed; re-run `--step crosswalk` then retry |
| Socrata returns only a few hundred rows | Missing or invalid `SOCRATA_APP_TOKEN` | Add token to `.env`; see Configuration section in README |
| `404` on a building detail page | BIN not in `buildings` table | Verify BIN via `python query.py sql "SELECT bin FROM buildings WHERE bin='<BIN>'"` |
| Jinja2 template changes not reflected | Flask caches templates in non-debug mode | Restart the server; or run with `--debug` during development |

---

## Section 10 — End-to-end smoke test (single command sequence)

Run this in one session to confirm the whole stack is healthy:

```bash
# 1. Environment
python --version && python3 -c "from dotenv import load_dotenv; load_dotenv(); import os; print('Token:', 'OK' if os.getenv('SOCRATA_APP_TOKEN') else 'MISSING')"

# 2. DB integrity
python3 -c "
from dotenv import load_dotenv; load_dotenv()
from src.db.init_db import get_connection, init_db
init_db()
conn = get_connection()
for t in ['buildings','building_violations','building_risk_scores','carbon_estimates']:
    n = conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
    print(f'{t}: {n:,}')
"

# 3. API sample (5 rows from crosswalk dataset only)
python3 -c "
from dotenv import load_dotenv; load_dotenv()
from src.ingestion.socrata import sample
rows = sample('5zhs-2jue')
print('Crosswalk sample OK:', len(rows), 'rows, fields:', list(rows[0].keys())[:5])
"

# 4. Query CLI
python query.py sql "SELECT COUNT(*) AS violations FROM building_violations"

# 5. Web server — start, probe, stop
python web.py &
sleep 3
curl -s -o /dev/null -w "Home: HTTP %{http_code}\n" http://localhost:5050/
curl -s -o /dev/null -w "GeoJSON: HTTP %{http_code} time=%{time_total}s\n" "http://localhost:5050/api/buildings.geojson?limit=100"
kill %1
```

**All-pass output looks like:**
```
Python 3.x.x
Token: OK
Database initialised at data/carbonshift.db
buildings: 275,526
building_violations: 1,663,986
building_risk_scores: 275,526
carbon_estimates: 273,917
Crosswalk sample OK: 5 rows, fields: ['bin', ...]
violations | 1663986
Home: HTTP 200
GeoJSON: HTTP 200 time=0.xxxs
```

---

## Section 11 — MapLibre island & Data Confidence page

The `/map` route serves a Vite-built React bundle inside the Flask template.
Flask remains the only runtime server — do not use `npm run dev` for production
verification.

### 11.1 Build the map bundle

Run from the project root (Node 18+ required):

```bash
npm install
npm run build
```

**Pass:** Command exits 0 and prints `✓ built`. Files exist under
`src/web/static/map/assets/` (hashed `map-*.js` and `map-*.css`) and
`src/web/static/map/.vite/manifest.json`.

**Fail:** `tsc` errors or missing `node_modules` — run `npm install` first.
No `map-*.js` in `src/web/static/map/assets/` — the map page will render an
empty island or a "Map bundle not found" warning.

Re-run `npm run build` after any change to `src/components/map/` or
`src/map-entry.tsx`.

### 11.2 Verify `/map` serves the built bundle

With `python web.py` running on port 5050:

```bash
curl -s http://localhost:5050/map | grep -E 'carbon-map-root|/static/map/assets/map-.*\.js'
```

**Pass:** Both patterns match in the HTML:
- `id="carbon-map-root"` — React mount point inside the Flask sidebar layout
- `<script type="module" src="/static/map/assets/map-….js">` — hashed bundle
  loaded from Flask static files (not from a Vite dev server)

Also confirm in page source:
- `window.__MAP_INIT__` is present (filter/limit config injected by Flask)
- `<link rel="stylesheet" href="/static/map/assets/map-….css">` is present
- No `leaflet` references (MapLibre replaced the old Leaflet map on `/map`)

**Fail:**
- `carbon-map-root` missing → check `src/web/templates/map.html`
- No `/static/map/assets/map-*.js` → run `npm run build`; restart Flask
- Script returns 404 → bundle path mismatch; rebuild and confirm manifest

Optional browser check: open `http://localhost:5050/map`, confirm the Flask
navbar is visible, the emissions-confidence sidebar panel loads, and the map
island shows **"Live Queens data"** (not "Demo sample data") when the API is
healthy.

### 11.3 Verify `/methodology` route

```bash
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:5050/methodology
curl -s http://localhost:5050/methodology | grep -c "Data confidence"
```

**Pass:** `HTTP 200`. Page body includes `Data confidence` heading and explains
the three emissions confidence levels:
- Measured LL84/97 (high confidence)
- Class median / similar buildings (medium confidence)
- Borough median / borough fallback (lower confidence)

When `score.py` has been run, the page also shows non-zero stat cards for
measured and modeled building counts.

**Fail:** `HTTP 404` → route not registered in `app.py`. Empty stats with
no explanatory copy → template error. All stat cards zero after a completed
`score.py` run → check `stats_summary()` in `src/query/lookup.py`.

Legacy alias: `/insights` and `/charts` both serve the borough insights page;
`/charts?tab=map` redirects to `/map`.
