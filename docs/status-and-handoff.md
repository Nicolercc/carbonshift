# Status & Handoff — Phase 1 API hardening (July 4, 2026)

## Latest Phase 1 hardening

The Flask API is now hardened for pre-merge review without starting Phase 2
or scaffolding Next.js.

Changes made:

- `/building/<bin>/export.csv` now uses a parameterized query for the BIN
  filter instead of interpolating the route parameter into SQL.
- `/api/*` routes now return JSON for 404, 503, and unexpected 500 errors.
  Non-API Flask/Jinja pages retain HTML behavior.
- Environment-driven CORS remains in place. Local dev origins are allowed by
  default outside production, and `CORS_ALLOWED_ORIGINS` is the explicit
  production configuration path. Wildcard CORS is not honored in production.
- `scripts/smoke_api.py` adds lightweight in-process API smoke checks for
  health JSON, JSON 404s, DB-backed search/detail payloads, the five signal
  groups, and the building CSV SQL-injection regression.

Recommended verification:

```bash
npm run typecheck
python -m py_compile src/web/app.py scripts/smoke_api.py
python scripts/smoke_api.py
CORS_ALLOWED_ORIGINS=http://localhost:3000 python -c "from src.web.app import app; c=app.test_client(); r=c.get('/api/health', headers={'Origin':'http://localhost:3000'}); print(r.status_code); print(r.headers.get('Access-Control-Allow-Origin')); print(r.content_type)"
git diff --check
```

## Previous DATABASE_URL fallback fix

## What was broken

`python web.py` failed immediately in any fresh terminal session with
`RuntimeError: DATABASE_URL is not set`, even though `.env` contains a
working Postgres connection string and both `web.py` and
`src/web/app.py` already call `load_dotenv()` at import time.

Root cause: `.env` only defines `SUPABASE_DATABASE_URL`, not
`DATABASE_URL`. `load_dotenv()` loads whatever keys exist in `.env` —
it can't invent a `DATABASE_URL` key that isn't there. `get_connection()`
in `src/db/init_db.py` read `os.getenv("DATABASE_URL")` with no
fallback, so every session required a manual
`export DATABASE_URL=$SUPABASE_DATABASE_URL` before starting the server.

This was previously called out as a known open item in `handoff.md`
(section 3, "`.env` in this repo defines `SUPABASE_DATABASE_URL` but not
`DATABASE_URL`") — that item is now resolved by this fix.

## Fix applied

`src/db/init_db.py`:

```diff
+def _resolve_database_dsn() -> str | None:
+    """DATABASE_URL is canonical; fall back to SUPABASE_DATABASE_URL from .env."""
+    return os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DATABASE_URL")
+
+
 def get_connection():
-    dsn = os.getenv("DATABASE_URL")
+    dsn = _resolve_database_dsn()
     if dsn:
         return get_pg_connection(dsn)
     raise RuntimeError(
         "DATABASE_URL is not set. SQLite is no longer supported — "
         "building footprints require PostGIS (Postgres). "
-        "Set DATABASE_URL=postgresql://... before starting the server."
+        "Set DATABASE_URL or SUPABASE_DATABASE_URL in .env before starting the server."
     )


 def init_db() -> None:
-    if os.getenv("DATABASE_URL"):
+    if _resolve_database_dsn():
         print("Postgres mode: schema applied via migrate_to_pg.py — skipping SQLite init.")
         return
```

`DATABASE_URL` remains canonical and wins if explicitly set (CI, prod,
or a manual override pointing at local Postgres instead of Supabase).
`SUPABASE_DATABASE_URL` is only used as a fallback when `DATABASE_URL`
is absent from the environment.

**Database freshness note:** older handoff notes described Supabase as stale
relative to local Postgres. Recent API smoke checks through the configured
fallback DSN returned the two-borough counts documented in `README.md`, so do
not assume the old Queens-only Supabase warning is still current. Before
deploying or merging ingestion changes, verify the target database with direct
row-count queries instead of trusting either this document or `handoff.md`.

## Verification

Server started in a clean shell with no manual `export DATABASE_URL`,
confirmed running via `Running on http://127.0.0.1:5050` with no
traceback.

```
curl http://127.0.0.1:5050/api/health
curl "http://127.0.0.1:5050/api/buildings/search?q=Murray&limit=5"
```

Output recorded in this session's conversation log at the time of the
fix.
