# DDR — Autonome AI-Hulpservice (Service Frank)

## Architectuur
- `src/server.py` — FastAPI + async background dispatcher + Web UI op `/`
- `src/router.py` — **Router**: receptionist (LLM) bepaalt welke dienst, biedt aan, schakelt over
- `src/conversation.py` — State machine per afzender: `new → triage → offered → active`
- `src/nurse.py` — LLMAdapter (OpenAI-compat) + RuleBasedNurse (deterministische mock-fallback)
- `src/signal_sender.py` — Signal REST API uitgaand (`POST /v2/send`)
- `src/init_db.py` — SQLite schema: `message_queue` + `conversations`
- `src/config.py` — JSON-config loader

## Dynamische specialisten
- Receptionist output `[ROUTE:dienst:beschrijving]`
- Als dienst niet bestaat → LLM genereert systeemprompt → `prompts/{dienst}.md` → nieuwe LLMAdapter
- Nieuwe dienst wordt permanent opgeslagen in `config.json` (overleeft herstart)
- Bestaande specialisten staan in `config.json` onder `services`
- `nieuw gesprek` reset naar receptionist

## Prompts
- `prompts/receptionist.md` — receptionist (alleen routeren, geen advies)
- `prompts/system_prompt.md` — AI-nurse (medisch)
- `prompts/tech_support.md` — AI-tech
- `prompts/beleggingsadviseur.md` — beleggingsadviseur
- `prompts/programmeur.md` — programmeur/software
- `prompts/fluidyne.md` — Fluidyne Stirling specialist
- Alle andere `prompts/{naam}.md` worden dynamisch gegenereerd

## Signaal-nummer
- Service: `+233594051553` (router-SIM, profielnaam "Service Frank")
- Signal REST API container in json-rpc mode, --net=host
- Ontvangst via WebSocket `ws://localhost:8080/v1/receive/+233594051553`

## LLM
- `config.json` — Groq, `llama-3.3-70b-versatile` (gratis tier)
- Fallback: OpenCode Zen Big Pickle (auto-detect key uit `~/.local/share/opencode/auth.json`)

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
