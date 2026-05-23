import sqlite3

DB_PATH = "messages.db"


def init_db(db_path: str | None = None) -> None:
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS message_queue (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            sender      TEXT    NOT NULL,
            message     TEXT    NOT NULL,
            channel     TEXT    NOT NULL DEFAULT 'signal',
            status      TEXT    DEFAULT 'pending',
            reply       TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
