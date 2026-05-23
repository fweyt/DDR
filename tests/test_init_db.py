import sqlite3
import tempfile

from src.init_db import init_db


def test_init_db_creates_table():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        init_db(f.name)
        conn = sqlite3.connect(f.name)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        conn.close()
    assert ("message_queue",) in tables


def test_init_db_is_idempotent(tmp_path):
    db = tmp_path / "test.db"
    init_db(str(db))
    init_db(str(db))
    conn = sqlite3.connect(str(db))
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='message_queue'"
    ).fetchall()
    conn.close()
    assert len(tables) == 1
