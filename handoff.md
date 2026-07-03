# Handoff — Manhattan expansion + Postgres migration (July 3, 2026)

## 1. Current state

Branch `nr/map-integration` has 20 commits ahead of `main` (`6d95381`…`829d21d`), all committed and clean (`git status` shows no uncommitted changes to tracked files as of this writing, aside from in-progress doc edits). The branch does three things on top of the earlier MapLibre-island work: migrates the schema from SQLite to PostgreSQL+PostGIS, adds real building-footprint polygons (Queens via Socrata, Manhattan via ArcGIS), and adds a full second borough (Manhattan) — buildings, violations, ACP-7 asbestos projects, footprints — to the ingestion and scoring pipeline. **Where the data actually lives matters here and the two databases have diverged:** the local Postgres database `carbonshift_queens` (`DATABASE_URL`, unset by default — see Known Open Items) has the complete, correct, two-borough dataset with the ACP-7 dedup fix applied. Supabase (`SUPABASE_DATABASE_URL`, currently the only DB var set in `.env`) still has the **old, pre-Manhattan, pre-fix** Queens-only data, duplicate `asbestos_projects` rows included. `migrate_to_supabase.py` — the script that copies local → Supabase — exists but has not been re-run since any of this landed.

## 2. What changed

| | Before (`main`) | After (this branch) |
|---|---|---|
| **Geographic scope** | Queens only | Queens + Manhattan (buildings, violations, footprints, asbestos — **not** energy/emissions, see below) |
| **Database** | SQLite (`sqlite3` stdlib), zero-install | PostgreSQL 16+ with PostGIS. SQLite is not a fallback — `get_connection()` raises `RuntimeError` immediately if `DATABASE_URL` is unset |
| **Building shapes on the map** | Synthetic squares, drawn from a single lat/lng centroid | Real NYC-surveyed polygon outlines (`building_footprints` table, PostGIS `geometry(MultiPolygon,4326)`) — Queens 86,677 footprints via Socrata `5zhs-2jue`, Manhattan 44,607 via ArcGIS `BUILDING_view` FeatureServer (Socrata only covers ~17.8% of Manhattan, confirmed by direct query — that's why Manhattan needed a different source entirely) |
| **`asbestos_projects` data integrity** | No unique constraint; not a known issue at the time | Found and fixed a real bug: ACP-7 ingestion paginated Socrata without `$order`, so re-fetches/page overlaps produced massive duplicate `(building_id, control_number)` rows — one pair on Supabase's still-broken copy repeats 252 times. Fix: `$order=:id` added to both ACP-7 fetchers' pagination calls (confirmed at the call sites, not just as an unused default) + `ALTER TABLE asbestos_projects ADD CONSTRAINT uq_acp7_building_cn UNIQUE (building_id, control_number)` + `ON CONFLICT (building_id, control_number) DO NOTHING` on insert |
| **Scoring pipeline Postgres compatibility** | `score.py` never ran against anything but SQLite | Three SQLite-only patterns removed: `conn.executemany()` → `psycopg2.extras.execute_values()`; `INSERT OR REPLACE` → `INSERT ... ON CONFLICT ... DO UPDATE`; the `sqlite_master`-based `_migrate()` step in `init_db.py` no longer executes at all under Postgres (short-circuits before it) |

## 3. Known open items — stated honestly

- **Manhattan LL84/97 (energy & emissions) ingestion does not exist.** There is no `fetch_manhattan_ll84_97.py`. `energy_emissions` has zero Manhattan rows. Every Manhattan `carbon_estimates` row is therefore `class_median` or `borough_median` — never `measured`. This is the single biggest data gap, not a documentation gap.
- **Frontend is still Queens-only in viewport and copy.** `src/components/map/mapConfig.ts` exports `queensBounds`, which drives the map's default `fitBounds` — Manhattan buildings exist in the data and the API, but the map won't show them until a user manually pans there. Hardcoded "Queens" strings remain in `base.html`, `index.html`, `map.html`, `charts.html`, `buildingInsights.ts`, `buildingDataAdapter.ts`, and `BuildingInsightCard.tsx`. None of this has been touched for Manhattan.
- **Supabase is stale and does not reflect any of this branch's work.** Confirmed by direct query just now: Supabase has 79,171 buildings (Queens only, matches pre-Manhattan state exactly), and `asbestos_projects` still has 13,009 total rows behind only 4,237 distinct pairs — the `uq_acp7_building_cn` constraint does not exist there. Whoever is running the deployed app against Supabase is seeing old, duplicate-laden, single-borough data.
- **`.env` in this repo defines `SUPABASE_DATABASE_URL` but not `DATABASE_URL`.** As configured, `python web.py` will fail immediately with `DATABASE_URL is not set` — you must export `DATABASE_URL` pointing at either the local Postgres instance or Supabase before starting the server. `.env.example` has also not been updated off the SQLite-era `DB_PATH` template — don't use it as a reference until it's fixed.
- **Two redundant indexes exist on `asbestos_projects` in the local DB**: both `idx_ap_building_control_number` (a plain unique index) and `uq_acp7_building_cn` (the constraint) enforce the same `(building_id, control_number)` uniqueness. Harmless but worth cleaning up — the constraint should probably be the only one kept.

## 4. Exact commands to resume

**Verify local Postgres state** (source of truth — run this first, don't trust this document's numbers to still be current):

```bash
psql -d carbonshift_queens -c "SELECT left(bin,1) boro, count(*) FROM buildings GROUP BY 1;"
psql -d carbonshift_queens -c "SELECT left(building_id,1) boro, count(*) FROM building_violations GROUP BY 1;"
psql -d carbonshift_queens -c "SELECT left(building_id,1) boro, count(*) total, count(DISTINCT (building_id, control_number)) distinct_pairs FROM asbestos_projects GROUP BY 1;"
psql -d carbonshift_queens -c "\d asbestos_projects"   # confirm uq_acp7_building_cn is still present
```

**Verify Supabase state** (must `source .env` first — `SUPABASE_DATABASE_URL` is only in `.env`, not the ambient shell environment):

```bash
set -a; source .env; set +a
psql "$SUPABASE_DATABASE_URL" -c "\dt"
psql "$SUPABASE_DATABASE_URL" -c "SELECT left(bin,1) boro, count(*) FROM buildings GROUP BY 1;"
psql "$SUPABASE_DATABASE_URL" -c "\d asbestos_projects"   # check whether uq_acp7_building_cn has been added yet
```

**Bring Supabase up to date** (only after confirming local state is what you want to ship):

```bash
set -a; source .env; set +a
export DATABASE_URL="postgresql://nicolerodriguez@localhost:5432/carbonshift_queens"
python migrate_to_supabase.py
python verify_pg.py   # or equivalent row-count check against SUPABASE_DATABASE_URL
```

**Run the missing Manhattan LL84/97 ingestion** (does not exist yet — this is new work, not a re-run):
1. Sample dataset `5zyy-y8am` filtered for Manhattan (`upper(borough)='MANHATTAN'` — confirm the exact string against a live sample first, per the pattern in `fetch_ll84_97.py`).
2. Write `src/ingestion/fetch_manhattan_ll84_97.py` following the shape of `fetch_manhattan_violations.py` (BIN post-filtered against `buildings`, not `building_crosswalk`) and `fetch_ll84_97.py` (multi-BBL/BIN list-field expansion — Section D/H of `CLAUDE.md`).
3. Re-run `python score.py --carbon-only` afterward so Manhattan buildings with real LL84/97 data get `eui_source='measured'` instead of a modelled estimate.

**Update the frontend for two boroughs** (not started):
1. Replace or generalize `queensBounds` in `src/components/map/mapConfig.ts` to a combined Queens+Manhattan bounding box, or compute bounds dynamically from loaded features.
2. Sweep the hardcoded "Queens" copy listed in Section 3 above and either genericize it or make it borough-aware.
