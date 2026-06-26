import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def get_connection() -> sqlite3.Connection:
    db_path = os.getenv("DB_PATH", "data/carbonshift.db")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
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


if __name__ == "__main__":
    init_db()
