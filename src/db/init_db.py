import collections.abc
import os
import re
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


# ── Postgres adapter ──────────────────────────────────────────────────────────

class _PgRow(collections.abc.Mapping):
    """Row wrapper that mimics sqlite3.Row: supports row[0], row["col"], dict(row)."""
    __slots__ = ("_cols", "_vals", "_d")

    def __init__(self, cols: list, values: tuple):
        self._cols = tuple(cols)
        self._vals = tuple(values)
        self._d = dict(zip(cols, values))

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._vals[key]
        return self._d[key]

    def __iter__(self):
        return iter(self._d)

    def __len__(self):
        return len(self._d)

    def keys(self):
        return self._cols


class _PgCursor:
    def __init__(self, pg_cursor):
        self._c = pg_cursor

    @property
    def description(self):
        return self._c.description

    def _col_names(self):
        return [d[0] for d in self._c.description] if self._c.description else []

    def fetchall(self):
        cols = self._col_names()
        return [_PgRow(cols, row) for row in self._c.fetchall()]

    def fetchone(self):
        cols = self._col_names()
        row = self._c.fetchone()
        return _PgRow(cols, row) if row else None


# MINIMAL TRANSLATION LAYER — handles only the specific SQLite constructs
# present in this codebase at the time of the Queens Postgres migration
# (GLOB year pattern, :name named params, ? positional params). This is NOT
# a general SQLite→Postgres compatibility shim. Manhattan-phase queries and
# PostGIS expressions must be written in valid Postgres SQL directly; do not
# rely on this function to adapt syntax it was never built for.
def _translate_sql(sql: str, params):
    """Translate SQLite-dialect SQL to Postgres-compatible SQL."""
    # charts.py violations_over_time() uses SQLite GLOB for 4-digit year match
    sql = sql.replace(
        "GLOB '[0-9][0-9][0-9][0-9]'",
        "~ '^[0-9]{4}$'",
    )
    if isinstance(params, dict):
        # Named params: :name → %(name)s
        sql = re.sub(r":(\w+)", r"%(\1)s", sql)
    elif params is not None:
        # Positional params: ? → %s
        sql = sql.replace("?", "%s")
    return sql, params


class PgConn:
    def __init__(self, pg_conn):
        self._conn = pg_conn

    def execute(self, sql: str, params=None):
        translated_sql, translated_params = _translate_sql(sql, params)
        cur = self._conn.cursor()
        try:
            cur.execute(translated_sql, translated_params)
        except Exception:
            self._conn.rollback()
            raise
        return _PgCursor(cur)

    def close(self):
        try:
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        finally:
            self._conn.close()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()


def get_pg_connection(dsn: str) -> "PgConn":
    import psycopg2
    try:
        conn = psycopg2.connect(dsn)
    except psycopg2.OperationalError as e:
        raise RuntimeError(f"Postgres connection failed: {e}") from e
    return PgConn(conn)


# ── SQLite / routing ──────────────────────────────────────────────────────────

def get_connection():
    dsn = os.getenv("DATABASE_URL")
    if dsn:
        return get_pg_connection(dsn)
    raise RuntimeError(
        "DATABASE_URL is not set. SQLite is no longer supported — "
        "building footprints require PostGIS (Postgres). "
        "Set DATABASE_URL=postgresql://... before starting the server."
    )


def init_db() -> None:
    if os.getenv("DATABASE_URL"):
        print("Postgres mode: schema applied via migrate_to_pg.py — skipping SQLite init.")
        return
    schema_path = Path(__file__).parent / "schema.sql"
    conn = get_connection()
    with open(schema_path) as f:
        conn.executescript(f.read())
    _migrate(conn)
    conn.commit()
    conn.close()
    print(f"Database initialised at {os.getenv('DB_PATH', 'data/carbonshift.db')}")


def _migrate(conn: sqlite3.Connection) -> None:
    """Apply additive migrations to existing databases without dropping data."""
    existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "carbon_estimates" not in existing:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS carbon_estimates (
              building_id TEXT PRIMARY KEY,
              building_class TEXT,
              building_area REAL,
              eui_source TEXT,
              site_eui REAL,
              ghg_intensity REAL,
              estimated_ghg_metric_tons REAL,
              peer_building_count INTEGER,
              generated_at TEXT,
              FOREIGN KEY (building_id) REFERENCES buildings(bin)
            )
        """)
    # Add risk_detail column to building_risk_scores if not present
    cols = {r[1] for r in conn.execute("PRAGMA table_info(building_risk_scores)")}
    if "risk_detail" not in cols:
        try:
            conn.execute("ALTER TABLE building_risk_scores ADD COLUMN risk_detail TEXT")
        except Exception:
            pass

    # Ensure performance indexes exist (safe to run on existing databases)
    existing_idx = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    needed = [
        ("idx_bv_building_id",
         "CREATE INDEX idx_bv_building_id ON building_violations(building_id)"),
        ("idx_bv_building_asbestos",
         "CREATE INDEX idx_bv_building_asbestos ON building_violations(building_id, is_asbestos_related)"),
        ("idx_bp_building_id",
         "CREATE INDEX idx_bp_building_id ON building_profiles(building_id)"),
        ("idx_ap_building_id",
         "CREATE INDEX idx_ap_building_id ON asbestos_projects(building_id)"),
        ("idx_ee_building_id",
         "CREATE INDEX idx_ee_building_id ON energy_emissions(building_id)"),
    ]
    for name, sql in needed:
        if name not in existing_idx:
            conn.execute(sql)


if __name__ == "__main__":
    init_db()
