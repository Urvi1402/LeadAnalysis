import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS emails (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  gmail_message_id TEXT NOT NULL UNIQUE,
  thread_id TEXT,
  internal_date INTEGER,
  from_name TEXT,
  from_email TEXT,
  subject TEXT,
  snippet TEXT,
  body_text TEXT,
  received_at TEXT,
  processed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS companies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  normalized_name TEXT NOT NULL UNIQUE,
  first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
  last_seen_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS email_companies (
  email_id INTEGER NOT NULL,
  company_id INTEGER NOT NULL,
  confidence REAL,
  source TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (email_id, company_id),
  FOREIGN KEY (email_id) REFERENCES emails(id),
  FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS company_profiles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  company_id INTEGER NOT NULL,
  source TEXT NOT NULL,              -- wikipedia, wikidata, website, etc.
  source_url TEXT,
  founded_year INTEGER,
  employees INTEGER,
  hq_location TEXT,
  industry TEXT,
  revenue TEXT,
  rating REAL,
  confidence REAL DEFAULT 0.0,
  raw_json TEXT,
  fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(company_id, source),
  FOREIGN KEY(company_id) REFERENCES companies(id)
);

CREATE INDEX IF NOT EXISTS idx_company_profiles_company_id
ON company_profiles(company_id);

CREATE INDEX IF NOT EXISTS idx_companies_last_seen
ON companies(last_seen_at);
"""

def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

def get_conn(db_path: Path) -> sqlite3.Connection:
    ensure_parent(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn

def init_db(conn: sqlite3.Connection) -> None:
    # executescript runs PRAGMA + multiple CREATE statements safely
    conn.executescript(SCHEMA)
    conn.commit()

def is_profile_fresh(conn: sqlite3.Connection, company_id: int, ttl_days: int = 7) -> bool:
    row = conn.execute(
        """
        SELECT fetched_at
        FROM company_profiles
        WHERE company_id = ?
        ORDER BY fetched_at DESC
        LIMIT 1
        """,
        (company_id,),
    ).fetchone()

    if not row:
        return False

    # Is fetched_at within last ttl_days?
    chk = conn.execute(
        "SELECT datetime(?) >= datetime('now', ?) AS fresh",
        (row["fetched_at"], f"-{ttl_days} days"),
    ).fetchone()

    return bool(chk["fresh"])
