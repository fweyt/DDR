import asyncio
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from .config import load_config
from .init_db import DB_PATH, init_db
from .nurse import LLMAdapter, RuleBasedNurse
from .signal_sender import SignalSender

config = load_config()
init_db()

_nurse: LLMAdapter | RuleBasedNurse
if config.get("llm", {}).get("mock", False):
    _nurse = RuleBasedNurse()
else:
    _nurse = LLMAdapter(config.get("llm", {}))

_signal = SignalSender(config.get("signal", {}))


def _queue_message(sender: str, message: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO message_queue (sender, message, channel) VALUES (?, ?, 'signal')",
        (sender, message),
    )
    conn.commit()
    conn.close()


def _process_one() -> bool:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id, sender, message FROM message_queue "
        "WHERE status='pending' ORDER BY id ASC LIMIT 1"
    ).fetchone()
    if not row:
        conn.close()
        return False

    msg_id, sender, message = row
    conn.execute("UPDATE message_queue SET status='processing' WHERE id=?", (msg_id,))
    conn.commit()

    reply = _nurse.generate(message)

    if _signal.send(sender, reply):
        conn.execute(
            "UPDATE message_queue SET status='completed', reply=? WHERE id=?",
            (reply, msg_id),
        )
    else:
        conn.execute("UPDATE message_queue SET status='pending' WHERE id=?", (msg_id,))
    conn.commit()
    conn.close()
    return True


async def _dispatch_loop() -> None:
    while True:
        try:
            _process_one()
        except Exception:
            pass
        await asyncio.sleep(1)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(_dispatch_loop())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)


@app.post("/signal-webhook")
async def signal_webhook(request: Request):
    data = await request.json()
    envelope = data.get("envelope", {})
    source = envelope.get("source")
    data_message = envelope.get("dataMessage", {})
    message = data_message.get("message") if isinstance(data_message, dict) else None
    if source and message:
        _queue_message(source, message)
    return {"status": "queued"}
