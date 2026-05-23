import json
import sqlite3
from datetime import datetime

from .init_db import DB_PATH


STATE_NEW = "new"
STATE_TRIAGE = "triage"
STATE_OFFERED = "offered:"  # + service_name
STATE_ACTIVE = "active:"  # + service_name


def get_or_create(sender: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT state, history, created_at, updated_at FROM conversations WHERE sender=?",
        (sender,),
    ).fetchone()
    if row:
        result = {
            "sender": sender,
            "state": row[0],
            "history": json.loads(row[1]),
            "created_at": row[2],
            "updated_at": row[3],
        }
    else:
        conn.execute(
            "INSERT INTO conversations (sender, state, history) VALUES (?, 'new', '[]')",
            (sender,),
        )
        conn.commit()
        result = {"sender": sender, "state": "new", "history": [], "created_at": None, "updated_at": None}
    conn.close()
    return result


def set_state(sender: str, state: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE conversations SET state=?, updated_at=? WHERE sender=?",
        (state, datetime.utcnow().isoformat(), sender),
    )
    conn.commit()
    conn.close()


def add_to_history(sender: str, role: str, content: str) -> list:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT history FROM conversations WHERE sender=?", (sender,)
    ).fetchone()
    if not row:
        conn.close()
        return []
    history = json.loads(row[0])
    history.append({"role": role, "content": content})
    MAX = 20
    history = history[-MAX:]
    conn.execute(
        "UPDATE conversations SET history=?, updated_at=? WHERE sender=?",
        (json.dumps(history), datetime.utcnow().isoformat(), sender),
    )
    conn.commit()
    conn.close()
    return history


def get_history(sender: str) -> list:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT history FROM conversations WHERE sender=?", (sender,)
    ).fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return []


def delete(sender: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM conversations WHERE sender=?", (sender,))
    conn.commit()
    conn.close()
