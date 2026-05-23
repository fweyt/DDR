# DDR — AI Service (Signal + Web)

Autonomous AI assistant with Signal and web interface. Routes messages to specialized LLM agents via a receptionist triage system.

## Quick start

```bash
cp config.json.example config.json
# edit config.json: add your LLM API key and Signal number
mkdir signals
docker compose -f container/docker-compose.yml up --build
```

- **Web:** open http://localhost:5000
- **Signal:** message your Signal number

## Configuration

Edit `config.json`:

| Key | Description |
|-----|-------------|
| `llm.api_key` | LLM API key (Groq, OpenAI, etc.) |
| `llm.model` | Model name (default: llama-3.3-70b-versatile) |
| `signal.number` | Your Signal number in international format |
| `services` | Pre-configured specialists |

When the receptionist routes to a specialist that doesn't exist yet, one is created dynamically.

## Architecture

- `src/server.py` — FastAPI + WebSocket + background dispatch
- `src/router.py` — Receptionist LLM routes messages, creates specialists on demand
- `src/nurse.py` — LLM adapter (OpenAI-compatible) + rule-based fallback
- `src/conversation.py` — SQLite-backed conversation state machine
- `src/signal_sender.py` — Signal REST API outbound messages
- `prompts/` — System prompts for receptionist and specialists

## Run without Docker

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.server:app --host 0.0.0.0 --port 5000
```

The Signal REST API still needs Docker: `docker compose -f container/docker-compose.yml up signal-api`

## Tests

```bash
pytest tests/ -v
```
