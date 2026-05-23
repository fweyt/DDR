import asyncio
import json
import sqlite3
from contextlib import asynccontextmanager

import websockets
from fastapi import FastAPI, Request, WebSocket

from .config import load_config
from .conversation import get_or_create
from .init_db import DB_PATH, init_db
from .nurse import LLMAdapter, RuleBasedNurse
from .router import Router
from .signal_sender import SignalSender


class _AllowAllOrigins:
    """ASGI middleware: accept WebSocket connections regardless of Origin header."""
    def __init__(self, app):
        self.app = app
    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            headers = [
                (k, v) for k, v in scope.get("headers", [])
                if k.lower() != b"origin"
            ]
            scope["headers"] = headers
        await self.app(scope, receive, send)


config = load_config()
init_db()

_router: Router
_router = Router(config)

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

    reply = _router.handle(sender, message)

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


async def _signal_receiver() -> None:
    signal_url = config.get("signal", {}).get("api_url", "http://localhost:8080")
    ws_url = signal_url.replace("http://", "ws://").replace("https://", "wss://")
    number = config.get("signal", {}).get("number", "")

    while True:
        try:
            async with websockets.connect(
                f"{ws_url}/v1/receive/{number}",
                ping_interval=30,
            ) as ws:
                async for raw in ws:
                    data = json.loads(raw)
                    envelope = data.get("envelope", {})
                    source = envelope.get("source")
                    msg = envelope.get("dataMessage", {}).get("message")
                    if source and msg:
                        _queue_message(source, msg)
        except Exception:
            pass
        await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    tasks = [
        asyncio.create_task(_dispatch_loop()),
        asyncio.create_task(_signal_receiver()),
    ]
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def chat_page():
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AI Service</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: system-ui, sans-serif; background:#f5f5f5; height:100vh; display:flex; flex-direction:column; max-width:640px; margin:0 auto; }
#status { text-align:center; font-size:12px; padding:4px; color:#999; }
#messages { flex:1; overflow-y:auto; padding:16px; display:flex; flex-direction:column; gap:8px; }
.msg { padding:10px 14px; border-radius:16px; max-width:80%; white-space:pre-wrap; word-break:break-word; }
.user { background:#007aff; color:#fff; align-self:flex-end; border-bottom-right-radius:4px; }
.nurse { background:#e5e5ea; color:#000; align-self:flex-start; border-bottom-left-radius:4px; }
.typing { background:#e5e5ea; color:#999; align-self:flex-start; font-size:14px; display:flex; align-items:center; gap:8px; }
.typing .dots { display:inline-flex; gap:3px; }
.typing .dots span { width:6px; height:6px; background:#999; border-radius:50%; animation:bounce 1.4s infinite ease-in-out both; }
.typing .dots span:nth-child(1) { animation-delay:-0.32s; }
.typing .dots span:nth-child(2) { animation-delay:-0.16s; }
.typing .txt { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
@keyframes bounce { 0%,80%,100% { transform:scale(0); } 40% { transform:scale(1); } }
.error { background:#ffd6d6; color:#c00; align-self:center; font-size:13px; }
form { display:flex; gap:8px; padding:12px; background:#fff; border-top:1px solid #ddd; }
input { flex:1; padding:10px 14px; border:1px solid #ddd; border-radius:20px; font-size:16px; outline:none; }
input:disabled { background:#eee; }
button { padding:10px 20px; background:#007aff; color:#fff; border:none; border-radius:20px; font-size:16px; cursor:pointer; }
button:disabled { opacity:.5; }
</style>
</head>
<body>
<div id="status">Connecting...</div>
<div id="messages"></div>
<form id="form">
<input id="input" placeholder="Ask your question..." autofocus>
<button id="send" type="submit">Send</button>
</form>
<script>
const $ = s => document.querySelector(s);
const addMsg = (text, role, sender) => {
    const d = document.createElement('div');
    d.className = 'msg ' + role;
    if (sender && role !== 'user') {
        const lbl = document.createElement('div');
        lbl.style.cssText = 'font-size:11px;font-weight:600;margin-bottom:4px;opacity:.7;';
        lbl.textContent = sender;
        d.appendChild(lbl);
    }
    const t = document.createElement('div');
    t.textContent = text;
    d.appendChild(t);
    $('#messages').appendChild(d);
    d.scrollIntoView();
};
const typingEl = () => document.getElementById('typing');
const typingDots = '<span class="dots"><span></span><span></span><span></span></span>';
const showTyping = (msg) => {
    const el = typingEl();
    if (el) {
        el.innerHTML = typingDots + '<span class="txt">' + (msg || 'Typing') + '</span>';
        return;
    }
    const d = document.createElement('div');
    d.id = 'typing';
    d.className = 'msg typing';
    d.innerHTML = typingDots + '<span class="txt">' + (msg || 'Typing') + '</span>';
    $('#messages').appendChild(d);
    d.scrollIntoView();
};
const hideTyping = () => {
    const el = typingEl();
    if (el) el.remove();
};
let ws;
function connect() {
    ws = new WebSocket(`ws://${location.host}/chat`);
    ws.onopen = () => { $('#status').textContent = 'Connected'; };
    ws.onclose = () => {
        $('#status').textContent = 'Disconnected, retrying...';
        $('#input').disabled = true;
        $('#send').disabled = true;
        setTimeout(connect, 3000);
    };
    ws.onerror = () => { $('#status').textContent = 'Connection error'; };
    ws.onmessage = e => {
        try {
            const d = JSON.parse(e.data);
            if (d.error) {
                hideTyping();
                addMsg('⚠ ' + d.error, 'error');
                $('#send').disabled = false;
                $('#input').disabled = false;
            } else if (d.status) {
                showTyping(d.status);
            } else if (d.text) {
                hideTyping();
                addMsg(d.text, 'nurse', d.sender);
                $('#send').disabled = false;
                $('#input').disabled = false;
            }
        } catch {
            hideTyping();
            addMsg('⚠ Invalid response', 'error');
        }
        $('#input').focus();
    };
}
connect();
$('#form').onsubmit = e => {
    e.preventDefault();
    const text = $('#input').value.trim();
    if (!text) return;
    addMsg(text, 'user');
    $('#input').value = '';
    $('#send').disabled = true;
    $('#input').disabled = true;
    showTyping();
    try { ws.send(JSON.stringify({text})); }
    catch { hideTyping(); addMsg('⚠ Could not send message', 'error'); }
};
</script>
</body>
</html>"""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(html)


@app.websocket("/chat")
async def chat_websocket(websocket: WebSocket):
    await websocket.accept()
    loop = asyncio.get_running_loop()
    try:
        while True:
            data = await websocket.receive_json()
            user_msg = data.get("text", "")
            try:
                sender = "web:" + websocket.client.host

                def progress(msg: str) -> None:
                    asyncio.run_coroutine_threadsafe(
                        websocket.send_json({"status": msg}), loop
                    )

                conv = get_or_create(sender)
                old_state = conv["state"]
                reply = await asyncio.to_thread(
                    _router.handle, sender, user_msg, progress
                )
                conv = get_or_create(sender)
                svc_cfg = config.get("services", {})
                new_state = conv["state"]
                if new_state.startswith("active:"):
                    persona = svc_cfg.get(new_state.split(":", 1)[1], {}).get("name", "Assistent")
                else:
                    persona = "Receptionist"
                await websocket.send_json({"text": reply, "sender": persona})
            except Exception as exc:
                await websocket.send_json({"error": str(exc)})
    except Exception:
        pass


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


# Wrap in middleware to allow all WebSocket origins (must be last)
app = _AllowAllOrigins(app)
