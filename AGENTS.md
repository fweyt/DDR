# DDR — Autonome AI-Hulpservice (Service Frank)

## Architectuur
- `src/server.py` — FastAPI + event-driven async dispatch + Web UI op `/`
- `src/router.py` — **Data-Driven Router**: alle transities uit `routing_rules` in SQLite
- `src/conversation.py` — SQLite-backed state machine (`new → triage → active`)
- `src/nurse.py` — LLMAdapter (OpenAI-compat) + RuleBasedNurse (mock/fallback)
- `src/signal_sender.py` — Signal REST API uitgaand (`POST /v2/send`)
- `src/init_db.py` — SQLite schema + `db_conn()` contextmanager + pragma optimalisaties
- `src/config.py` — JSON-config loader
- `static/index.html` — Web UI (geserveerd via `FileResponse`)

## Routing
- Alle transities staan in `routing_rules` tabel (niet hardcoded in Python)
- `Router._load_rules()` cached regels in geheugen bij eerste gebruik
- `match_type`: `auto`, `llm_route`, `keyword`, `confirm`, `deny`, `fallback`
- Receptionist detecteert `[ROUTE:dienst:beschrijving]` in LLM output
- Nieuwe specialisten dynamisch aangemaakt via `_ensure_specialist()` → LLM genereert prompt → opslag in `prompts/{naam}.md` + `config.json`

## Signaal-nummer
- Service: `+233594051553` (router-SIM, profielnaam "Service Frank")
- Signal REST API container in json-rpc mode, --net=host
- Ontvangst via WebSocket `ws://localhost:8080/v1/receive/+233594051553`

## LLM
- `config.json` — Groq, `llama-3.3-70b-versatile` (gratis tier)
- Fallback: OpenCode Zen Big Pickle (auto-detect key uit `~/.local/share/opencode/auth.json`)

## Performance
- Routing rules gecached (0 DB queries per bericht)
- Parallelle dispatch via `asyncio.create_task(asyncio.to_thread(...))`
- Event-driven (`asyncio.Event`) — geen polling, directe trigger bij `_queue_message`
- SQLite pragma's: `WAL`, `synchronous=NORMAL`, `busy_timeout=5000`, `cache_size=-20000`

## Testen
```bash
pip install -r requirements.txt
pytest -v
```

## Server starten
```bash
uvicorn src.server:app --host 0.0.0.0 --port 5000
```

## Docker
```bash
docker compose -f container/docker-compose.yml up --build
```
