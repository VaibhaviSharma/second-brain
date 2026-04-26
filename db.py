"""
db.py — Database layer for the Second Brain app.

Handles all SQLite access, FTS5 search, schema setup, and shared helpers.
No UI dependencies (no click, no rich) — imported by both brain.py and server.py.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────
BRAIN_DIR      = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "brain"
DB_PATH        = BRAIN_DIR / "brain.db"
VALID_STATUSES = ("active", "archived", "done")
DEFAULT_TYPES  = ("note", "link", "skill", "job", "idea", "resource")

# ── Connection ──────────────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_db() -> sqlite3.Connection:
    """Return an open DB connection. Raises RuntimeError if the DB doesn't exist."""
    if not DB_PATH.exists():
        raise RuntimeError(
            f"Database not found at {DB_PATH}. Run 'brain init' first."
        )
    return _connect()


# ── Schema ──────────────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create the DB file, tables, FTS index, and triggers (idempotent)."""
    BRAIN_DIR.mkdir(parents=True, exist_ok=True)
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS entries (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT    NOT NULL,
            content     TEXT    NOT NULL DEFAULT '',
            url         TEXT    NOT NULL DEFAULT '',
            type        TEXT    NOT NULL DEFAULT 'note',
            tags        TEXT    NOT NULL DEFAULT '',
            priority    INTEGER NOT NULL DEFAULT 3
                            CHECK(priority BETWEEN 1 AND 5),
            status      TEXT    NOT NULL DEFAULT 'active'
                            CHECK(status IN ('active', 'archived', 'done')),
            created_at  TEXT    NOT NULL,
            updated_at  TEXT    NOT NULL
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
            title,
            content,
            tags,
            content='entries',
            content_rowid='id',
            tokenize='porter unicode61'
        );

        CREATE TRIGGER IF NOT EXISTS entries_ai
        AFTER INSERT ON entries BEGIN
            INSERT INTO entries_fts(rowid, title, content, tags)
            VALUES (new.id, new.title, new.content, new.tags);
        END;

        CREATE TRIGGER IF NOT EXISTS entries_au
        AFTER UPDATE ON entries BEGIN
            INSERT INTO entries_fts(entries_fts, rowid, title, content, tags)
            VALUES ('delete', old.id, old.title, old.content, old.tags);
            INSERT INTO entries_fts(rowid, title, content, tags)
            VALUES (new.id, new.title, new.content, new.tags);
        END;

        CREATE TRIGGER IF NOT EXISTS entries_ad
        AFTER DELETE ON entries BEGIN
            INSERT INTO entries_fts(entries_fts, rowid, title, content, tags)
            VALUES ('delete', old.id, old.title, old.content, old.tags);
        END;
    """)
    conn.commit()
    conn.close()


# ── Helpers ─────────────────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def normalise_tags(raw: str) -> str:
    """Lowercase, strip whitespace, deduplicate, and sort comma-separated tags."""
    if not raw:
        return ""
    parts = sorted({t.strip().lower() for t in raw.split(",") if t.strip()})
    return ",".join(parts)


def fts_search(db: sqlite3.Connection, query: str):
    """
    Run an FTS5 prefix search. Returns a list of matching rowids ordered by rank.
    Falls back to None on malformed query (caller should use LIKE fallback).
    """
    words    = [w for w in query.split() if w]
    fts_expr = " OR ".join(f"{w}*" for w in words) if words else query
    try:
        return [
            r[0] for r in db.execute(
                "SELECT rowid FROM entries_fts WHERE entries_fts MATCH ? ORDER BY rank",
                (fts_expr,),
            ).fetchall()
        ]
    except sqlite3.OperationalError:
        return None
