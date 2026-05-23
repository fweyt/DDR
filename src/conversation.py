import json
from datetime import datetime

from .init_db import db_conn


def get_or_create(sender: str) -> dict:
    with db_conn() as conn:
        row = conn.execute(
            "SELECT state, history, created_at, updated_at FROM conversations WHERE sender=?",
            (sender,),
        ).fetchone()
        if row:
            return {"sender": sender, "state": row[0], "history": json.loads(row[1]),
                    "created_at": row[2], "updated_at": row[3]}
        conn.execute(
            "INSERT INTO conversations (sender, state, history) VALUES (?, 'new', '[]')",
            (sender,),
        )
        return {"sender": sender, "state": "new", "history": [], "created_at": None, "updated_at": None}


def set_state(sender: str, state: str) -> None:
    with db_conn() as conn:
        conn.execute(
            "UPDATE conversations SET state=?, updated_at=? WHERE sender=?",
            (state, datetime.utcnow().isoformat(), sender),
        )


def add_to_history(sender: str, role: str, content: str) -> list:
    with db_conn() as conn:
        row = conn.execute("SELECT history FROM conversations WHERE sender=?", (sender,)).fetchone()
        if not row:
            return []
        history = json.loads(row[0])
        history.append({"role": role, "content": content})
        history = history[-20:]
        conn.execute(
            "UPDATE conversations SET history=?, updated_at=? WHERE sender=?",
            (json.dumps(history), datetime.utcnow().isoformat(), sender),
        )
        return history


def get_history(sender: str) -> list:
    with db_conn() as conn:
        row = conn.execute("SELECT history FROM conversations WHERE sender=?", (sender,)).fetchone()
        return json.loads(row[0]) if row else []


def delete(sender: str) -> None:
    with db_conn() as conn:
        conn.execute("DELETE FROM conversations WHERE sender=?", (sender,))
