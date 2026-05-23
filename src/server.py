import asyncio
import json

import websockets
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import FileResponse

from .config import load_config
from .conversation import get_or_create
from .init_db import db_conn, init_db
from .router import Router
from .signal_sender import SignalSender


config = load_config()
init_db()

_router = Router(config)
_signal = SignalSender(config.get("signal", {}))
_queue_ready = asyncio.Event()


def _queue_message(sender: str, message: str) -> None:
    with db_conn() as conn:
        conn.execute("INSERT INTO message_queue (sender, message, channel) VALUES (?, ?, 'signal')", (sender, message))
    _queue_ready.set()


def _handle_message(msg_id: int, sender: str, message: str) -> None:
    try:
        reply = _router.handle(sender, message)
        ok = _signal.send(sender, reply)
        with db_conn() as conn:
            if ok:
                conn.execute("UPDATE message_queue SET status='completed', reply=? WHERE id=?", (reply, msg_id))
            else:
                conn.execute("UPDATE message_queue SET status='pending' WHERE id=?", (msg_id,))
    except:
        with db_conn() as conn:
            conn.execute("UPDATE message_queue SET status='pending' WHERE id=?", (msg_id,))


async def _dispatch_loop() -> None:
    while True:
        try:
            _queue_ready.clear()
            with db_conn() as conn:
                rows = conn.execute("SELECT id, sender, message FROM message_queue WHERE status='pending' ORDER BY id ASC").fetchall()
            if not rows:
                await _queue_ready.wait()
                continue
            for msg_id, sender, message in rows:
                with db_conn() as conn:
                    conn.execute("UPDATE message_queue SET status='processing' WHERE id=?", (msg_id,))
                await asyncio.to_thread(_handle_message, msg_id, sender, message)
        except:
            await asyncio.sleep(1)


async def _signal_receiver() -> None:
    number = config.get("signal", {}).get("number", "")
    ws_url = config.get("signal", {}).get("api_url", "http://localhost:8080").replace("http://", "ws://").replace("https://", "wss://")
    while True:
        try:
            async with websockets.connect(f"{ws_url}/v1/receive/{number}", ping_interval=30) as ws:
                async for raw in ws:
                    d = json.loads(raw).get("envelope", {})
                    if (s := d.get("source")) and (m := (d.get("dataMessage") or {}).get("message")):
                        _queue_message(s, m)
        except: pass
        await asyncio.sleep(5)


from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(_app: FastAPI):
    tasks = [asyncio.create_task(_dispatch_loop()), asyncio.create_task(_signal_receiver())]
    yield
    for t in tasks: t.cancel()


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def chat_page():
    return FileResponse("static/index.html")


@app.websocket("/chat")
async def chat_websocket(websocket: WebSocket):
    await websocket.accept()
    loop = asyncio.get_running_loop()
    try:
        while True:
            data = await websocket.receive_json()
            sender = "web:" + websocket.client.host
            try:
                def progress(msg):
                    asyncio.run_coroutine_threadsafe(websocket.send_json({"status": msg}), loop)
                reply = await asyncio.to_thread(_router.handle, sender, data.get("text", ""), progress)
                state = get_or_create(sender)["state"]
                persona = "Receptionist"
                if state.startswith("active:") and ":" in state:
                    persona = _router.get_specialist_name(state.split(":", 1)[1])
                await websocket.send_json({"text": reply, "sender": persona})
            except Exception as e:
                await websocket.send_json({"error": str(e)})
    except Exception:
        pass


@app.post("/signal-webhook")
async def signal_webhook(request: Request):
    d = (await request.json()).get("envelope", {})
    if (s := d.get("source")) and (m := (d.get("dataMessage") or {}).get("message")):
        _queue_message(s, m)
    return {"status": "queued"}


def _allow_all_origins(app):
    async def mw(scope, receive, send):
        if scope["type"] == "websocket":
            scope["headers"] = [(k, v) for k, v in scope.get("headers", []) if k.lower() != b"origin"]
        await app(scope, receive, send)
    return mw


app = _allow_all_origins(app)
