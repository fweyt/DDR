import json
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "config.json"

_DEFAULTS = {
    "llm": {"api_url": "http://localhost:11434", "api_key": "", "model": "llama3.2", "mock": True},
    "signal": {"api_url": "http://localhost:8080", "number": "+32XXXXXXXXX"},
}


def load_config(p=None):
    p = Path(p) if p else _PATH
    cfg = json.loads(p.read_text()) if p.exists() else {}
    return {**_DEFAULTS, **cfg}
