import json
from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock

from .init_db import db_conn

_sender_locks: dict[str, Lock] = defaultdict(Lock)


def get_or_create(sender: str) -> dict:
    now_iso = datetime.now(timezone.utc).isoformat()
    with db_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO conversations (sender, state, history, created_at, updated_at) "
            "VALUES (?, 'new', '[]', ?, ?)",
            (sender, now_iso, now_iso),
        )
        row = conn.execute(
            "SELECT state, history, created_at, updated_at FROM conversations WHERE sender=?",
            (sender,),
        ).fetchone()
    return {
        "sender": sender,
        "state": row[0],
        "history": json.loads(row[1]),
        "created_at": row[2],
        "updated_at": row[3],
    }


def set_state(sender: str, state: str) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    with db_conn() as conn:
        conn.execute(
            "UPDATE conversations SET state=?, updated_at=? WHERE sender=?",
            (state, now_iso, sender),
        )


def add_to_history(sender: str, role: str, content: str) -> list:
    now_iso = datetime.now(timezone.utc).isoformat()
    with _sender_locks[sender]:
        with db_conn() as conn:
            row = conn.execute("SELECT history FROM conversations WHERE sender=?", (sender,)).fetchone()
            if not row:
                return []
            history = json.loads(row[0])
            history.append({"role": role, "content": content})
            history = history[-20:]
            conn.execute(
                "UPDATE conversations SET history=?, updated_at=? WHERE sender=?",
                (json.dumps(history), now_iso, sender),
            )
    return history


def get_history(sender: str) -> list:
    with db_conn() as conn:
        row = conn.execute("SELECT history FROM conversations WHERE sender=?", (sender,)).fetchone()
        return json.loads(row[0]) if row else []


def delete(sender: str) -> None:
    with db_conn() as conn:
        conn.execute("DELETE FROM conversations WHERE sender=?", (sender,))
