# DDR — Autonome AI-Hulpservice

## Architectuur
- `src/server.py` — FastAPI + async background dispatcher (geen while-loop)
- `src/nurse.py` — Pluggable LLM-adapter (OpenAI-compatible API)
- `src/signal_sender.py` — Signal REST API uitgaand
- `src/init_db.py` — SQLite schema

## Testen
```bash
pip install -r requirements.txt
pytest -v
```

## Config
Kopieer `config.json.example` naar `config.json` en pas aan.
Zet `llm.mock: true` voor testen zonder LLM.

## Docker
```bash
docker compose -f container/docker-compose.yml up --build
```
