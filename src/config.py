import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

DEFAULT_CONFIG = {
    "llm": {
        "api_url": "http://localhost:11434",
        "api_key": "",
        "model": "llama3.2",
        "mock": True
    },
    "signal": {
        "api_url": "http://localhost:8080",
        "number": "+32XXXXXXXXX"
    }
}


def load_config(path: str | Path | None = None) -> dict:
    p = Path(path) if path else _CONFIG_PATH
    if p.exists():
        with open(p) as f:
            cfg = json.load(f)
    else:
        cfg = {}
    merged = DEFAULT_CONFIG.copy()
    merged.update(cfg)
    return merged
