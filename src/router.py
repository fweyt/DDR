import json
import re
from pathlib import Path

from .conversation import (
    STATE_NEW,
    STATE_TRIAGE,
    STATE_OFFERED,
    STATE_ACTIVE,
    add_to_history,
    delete,
    get_history,
    get_or_create,
    set_state,
)
from .nurse import LLMAdapter, RuleBasedNurse

_ROUTE_RE = re.compile(r"\s*\[ROUTE:([\w-]+)(?::([^]]+))?\]")
_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class Router:
    def __init__(self, config: dict) -> None:
        self.llm_config = config.get("llm", {})
        self.services = config.get("services", {})
        self._prompt_cache: dict[str, str] = {}
        mock = self.llm_config.get("mock", False)

        if mock:
            self._receptionist = RuleBasedNurse()
            self._specialists: dict = {}
            for name in self.services:
                self._specialists[name] = RuleBasedNurse()
        else:
            self._receptionist = LLMAdapter(self.llm_config, "receptionist")
            self._specialists: dict = {}
            for name, svc in self.services.items():
                prompt = svc.get("prompt", name)
                self._specialists[name] = LLMAdapter(self.llm_config, prompt)

    _RESET_WORDS = [
        "new conversation", "other service", "something else", "another question",
        "back to start", "reset", "again", "different topic",
    ]
    _SERVICE_NAMES = [
        "nurse", "medical",
        "tech", "technical", "computer",
        "investing", "investment advisor", "investment",
        "programmer", "coding", "software",
        "fluidyne", "stirling", "engine",
    ]

    def _ensure_specialist(self, name: str, description: str | None = None) -> bool:
        if name in self._specialists:
            return True
        if self.llm_config.get("mock", False):
            self._specialists[name] = RuleBasedNurse()
            return True

        topic = description or name
        import requests
        headers = {
            "Authorization": f"Bearer {self.llm_config.get('api_key', '')}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.llm_config.get("model", "llama-3.3-70b-versatile"),
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"Write a short system prompt (max 5 sentences, "
                        f"in English) for an AI assistant that is an expert "
                        f"in: {topic}. Describe their expertise, their style "
                        f"of answering, and that they should be concise "
                        f"(max 3-4 sentences). Only the prompt, no explanation."
                    ),
                }
            ],
        }
        resp = requests.post(
            f"{self.llm_config.get('api_url', 'https://api.groq.com/openai/v1')}/chat/completions",
            json=payload,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        prompt_text = resp.json()["choices"][0]["message"]["content"]

        path = _PROMPTS_DIR / f"{name}.md"
        path.write_text(prompt_text.strip())

        adapter = LLMAdapter(self.llm_config, name)
        self._specialists[name] = adapter

        config_path = _PROMPTS_DIR.parent / "config.json"
        if config_path.exists():
            try:
                cfg = json.loads(config_path.read_text())
                if "services" not in cfg:
                    cfg["services"] = {}
                if name not in cfg["services"]:
                    cfg["services"][name] = {
                        "name": name.replace("-", " ").title(),
                        "prompt": name,
                        "description": topic,
                    }
                    config_path.write_text(json.dumps(cfg, indent=4))
            except Exception:
                pass

        return True

    def handle(self, sender: str, message: str, status_callback=None) -> str:
        conv = get_or_create(sender)
        state = conv["state"]
        msg_lower = message.lower().strip()

        add_to_history(sender, "user", message)

        if state not in (STATE_NEW, STATE_TRIAGE):
            if any(w in msg_lower for w in self._RESET_WORDS):
                delete(sender)
                conv = get_or_create(sender)
                state = STATE_NEW

        if state == STATE_NEW:
            set_state(sender, STATE_TRIAGE)
            return self._triage(sender, message, status_callback)

        if state == STATE_TRIAGE:
            return self._triage(sender, message, status_callback)

        if state.startswith(STATE_OFFERED):
            return self._handle_offer(sender, state, message)

        if state.startswith(STATE_ACTIVE):
            service = state.split(":", 1)[1]
            return self._active(sender, service, message)

        return self._triage(sender, message, status_callback)

    def _triage(self, sender: str, message: str, status_callback=None) -> str:
        history = get_history(sender)
        context = "\n".join(
            f"{'User' if h['role'] == 'user' else 'You'}: {h['content']}"
            for h in history
        )
        reply = self._receptionist.generate(f"Conversation so far:\n{context}")
        m = _ROUTE_RE.search(reply)
        if m:
            service = m.group(1)
            description = m.group(2)
            if service not in self._specialists and status_callback:
                status_callback(
                    f"Please wait, creating the {service} specialist..."
                )
            self._ensure_specialist(service, description)
            set_state(sender, f"{STATE_ACTIVE}{service}")
            specialist = self._specialists.get(service)
            if specialist:
                intro = specialist.generate(
                    f"(The receptionist has connected me to {service}. "
                    f"Introduce yourself and ask how you can help. "
                    f"Mention that the user can say 'new conversation' to "
                    f"go back to the receptionist for a different service.)"
                )
                add_to_history(sender, "assistant", intro)
                return intro
            clean = _ROUTE_RE.sub("", reply).strip()
            set_state(sender, f"{STATE_OFFERED}{service}")
            add_to_history(sender, "assistant", clean)
            return clean
        add_to_history(sender, "assistant", reply)
        return reply

    def _handle_offer(self, sender: str, state: str, message: str) -> str:
        service = state.split(":", 1)[1]
        msg_lower = message.lower().strip()
        confirmed = any(
            w in msg_lower
            for w in [
                "yes", "ok", "okay", "please", "connect",
                "go ahead", "fine", "do it", "sure",
            ]
        )
        denied = any(
            w in msg_lower
            for w in ["no", "not", "none", "rather not", "other", "different"]
        )

        if confirmed:
            set_state(sender, f"{STATE_ACTIVE}{service}")
            specialist = self._specialists.get(service)
            if not specialist:
                self._ensure_specialist(service)
                specialist = self._specialists.get(service)
            if not specialist:
                set_state(sender, STATE_TRIAGE)
                return "Sorry, something went wrong while creating this service."
            intro = specialist.generate(
                f"(The receptionist has connected me to {service}. "
                f"This user has indicated they want help. "
                f"Introduce yourself and ask how you can help. "
                f"Mention that the user can say 'new conversation' to "
                f"go back to the receptionist for a different service.)"
            )
            add_to_history(sender, "assistant", intro)
            return intro

        set_state(sender, STATE_TRIAGE)
        return self._triage(sender, message)

    def _active(self, sender: str, service: str, message: str) -> str:
        specialist = self._specialists.get(service)
        if not specialist:
            self._ensure_specialist(service)
            specialist = self._specialists.get(service)
        if not specialist:
            set_state(sender, STATE_TRIAGE)
            return self._triage(sender, message)
        history = get_history(sender)
        context = "\n".join(
            f"{'User' if h['role'] == 'user' else 'You'}: {h['content']}"
            for h in history
        )
        reply = specialist.generate(
            f"Context (conversation with {service}):\n{context}"
        )
        add_to_history(sender, "assistant", reply)
        return reply
