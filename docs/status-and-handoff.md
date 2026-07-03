# Status & Handoff — DATABASE_URL fallback fix (July 3, 2026)

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

**Caveat carried over from `handoff.md`:** Supabase is known to be
stale relative to the local `carbonshift_queens` Postgres database (old
Queens-only data, missing the `asbestos_projects` dedup fix). This fix
makes the server *start reliably* against whichever DSN is available —
it does not change which database is the source of truth. See
`handoff.md` section 1 and 3 for the Supabase/local divergence, which is
still unresolved.

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
