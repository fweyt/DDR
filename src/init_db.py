import json
from contextlib import contextmanager
from pathlib import Path

import sqlite3

DB_PATH = "messages.db"
_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@contextmanager
def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA cache_size=-20000;")
    try:
        yield conn
        conn.commit()
    except:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: str | None = None) -> None:
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS message_queue (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            sender      TEXT    NOT NULL,
            message     TEXT    NOT NULL,
            channel     TEXT    NOT NULL DEFAULT 'signal',
            status      TEXT    DEFAULT 'pending',
            reply       TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS conversations (
            sender      TEXT PRIMARY KEY,
            state       TEXT NOT NULL DEFAULT 'new',
            history     TEXT NOT NULL DEFAULT '[]',
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS routing_rules (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            state_base      TEXT    NOT NULL,
            match_type      TEXT    NOT NULL DEFAULT 'keyword',
            match_value     TEXT    DEFAULT '',
            target_state    TEXT    NOT NULL DEFAULT '',
            specialist_name TEXT    DEFAULT '',
            prompt_file     TEXT    DEFAULT '',
            priority        INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_routing_rules_state
            ON routing_rules (state_base, priority);
    """)
    conn.commit()
    conn.close()
