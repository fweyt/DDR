import re
import threading
from pathlib import Path

from .conversation import add_to_history, delete, get_history, get_or_create, set_state
from .init_db import db_conn
from .nurse import LLMAdapter, RuleBasedNurse

_ROUTE_RE = re.compile(r"\s*\[ROUTE:([\w-]+)(?::([^]]+))?\]")
_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

_DEFAULT_RULES = [
    ("any", "keyword", "new conversation,other service,something else,another question,back to start,reset,again,different topic", "triage", "", "", 10),
    ("new", "auto", "", "triage", "", "", 0),
    ("triage", "llm_route", "", "", "", "", 0),
    ("offered", "confirm", "yes,ok,okay,please,connect,go ahead,fine,do it,sure", "active:same", "", "", 20),
    ("offered", "deny", "no,not,none,rather not,other,different", "triage", "", "", 20),
    ("active", "fallback", "", "", "", "", 99),
]

_DISPATCH = {
    "auto": "_exec_triage",
    "llm_route": "_exec_triage",
    "confirm": "_exec_confirm",
    "deny": "_exec_deny",
    "fallback": "_exec_fallback",
    "keyword": "_exec_keyword",
}


class Router:
    def __init__(self, config: dict) -> None:
        self.llm_config = config.get("llm", {})
        self._rules_cache: tuple | None = None
        self._cache_lock = threading.Lock()
        self._persona_cache: dict[str, str] = {}
        mock = self.llm_config.get("mock", False)
        self._receptionist = RuleBasedNurse() if mock else LLMAdapter(self.llm_config, "receptionist")
        self._specialists: dict = {}
        self._ensure_default_rules()
        if not mock:
            with db_conn() as conn:
                for row in conn.execute("SELECT DISTINCT target_state, specialist_name, prompt_file FROM routing_rules WHERE target_state LIKE 'active:%'"):
                    if not row[0] or ":" not in row[0]:
                        continue
                    svc = row[0].split(":", 1)[1]
                    if svc not in self._specialists:
                        self._specialists[svc] = LLMAdapter(self.llm_config, row[2] or svc)
                        if row[1]:
                            self._persona_cache[svc] = row[1]

    def _ensure_default_rules(self) -> None:
        with db_conn() as conn:
            if conn.execute("SELECT COUNT(*) FROM routing_rules").fetchone()[0] == 0:
                conn.executemany(
                    "INSERT INTO routing_rules (state_base,match_type,match_value,target_state,specialist_name,prompt_file,priority) VALUES (?,?,?,?,?,?,?)",
                    _DEFAULT_RULES,
                )

    def _register_specialist_in_db(self, name: str, topic: str, prompt_file: str | None = None) -> None:
        keywords = name.lower().replace("-", " ").replace("_", " ")
        with db_conn() as conn:
            exists = conn.execute("SELECT 1 FROM routing_rules WHERE state_base='triage' AND match_type='keyword' AND match_value=?", (keywords,)).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO routing_rules (state_base,match_type,match_value,target_state,specialist_name,prompt_file,priority) VALUES ('triage','keyword',?,?,?,?,5)",
                    (keywords, f"active:{name}", name.replace("-", " ").title(), prompt_file or name),
                )
        with self._cache_lock:
            self._rules_cache = None
        self._persona_cache[name] = name.replace("-", " ").title()

    def _load_rules(self) -> tuple:
        with self._cache_lock:
            if self._rules_cache is not None:
                return self._rules_cache
        with db_conn() as conn:
            conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
            any_rules = list(conn.execute("SELECT * FROM routing_rules WHERE state_base='any' AND match_type='keyword' ORDER BY priority"))
            state_rules = {}
            for sb in {r["state_base"] for r in conn.execute("SELECT state_base FROM routing_rules WHERE state_base!='any'")}:
                state_rules[sb] = list(conn.execute("SELECT * FROM routing_rules WHERE state_base=? ORDER BY priority", (sb,)))
        with self._cache_lock:
            self._rules_cache = (any_rules, state_rules)
            return self._rules_cache

    def _find_rule(self, state_base: str, msg_lower: str) -> dict | None:
        any_rules, state_rules = self._load_rules()
        for row in any_rules:
            for kw in row["match_value"].split(","):
                if kw.strip() and kw.strip() in msg_lower:
                    return row
        rules = state_rules.get(state_base, [])
        for row in rules:
            if row["match_type"] == "keyword" and row["match_value"]:
                for kw in row["match_value"].split(","):
                    if kw.strip() and kw.strip() in msg_lower:
                        return row
        for row in rules:
            if row["match_type"] in ("auto", "llm_route", "fallback"):
                return row
        return None

    def _context(self, sender: str) -> str:
        return "\n".join(f"{'User' if h['role'] == 'user' else 'You'}: {h['content']}" for h in get_history(sender))

    def handle(self, sender: str, message: str, status_callback=None) -> str:
        conv = get_or_create(sender)
        state = conv["state"]
        msg_lower = message.lower().strip()
        add_to_history(sender, "user", message)
        rule = self._find_rule(state.split(":")[0] if ":" in state else state, msg_lower)
        if rule:
            return self._execute_rule(rule, sender, state, message, status_callback)
        if state.startswith("active:") and ":" in state:
            return self._active(sender, state.split(":", 1)[1], message)
        set_state(sender, "triage")
        return self._triage(sender, message, status_callback)

    def _execute_rule(self, rule: dict, sender: str, state: str, message: str, status_callback=None) -> str:
        if rule["match_type"] == "keyword" and rule["state_base"] == "any":
            delete(sender); get_or_create(sender)
            return self._triage(sender, message, status_callback)
        handler = getattr(self, _DISPATCH.get(rule["match_type"], "_exec_triage"))
        return handler(rule, sender, state, message, status_callback)

    def _exec_triage(self, r, sender, state, message, status_callback):
        if r["target_state"]:
            set_state(sender, r["target_state"])
        return self._triage(sender, message, status_callback)

    def _exec_confirm(self, r, sender, state, message, status_callback):
        if ":" not in state:
            set_state(sender, "triage")
            return self._triage(sender, message, status_callback)
        service = state.split(":", 1)[1]
        set_state(sender, f"active:{service}")
        return self._active(sender, service, message, intro=True)

    def _exec_deny(self, r, sender, state, message, status_callback):
        set_state(sender, "triage")
        return self._triage(sender, message, status_callback)

    def _exec_fallback(self, r, sender, state, message, status_callback):
        if state.startswith("active:") and ":" in state:
            return self._active(sender, state.split(":", 1)[1], message)
        return self._triage(sender, message, status_callback)

    def _exec_keyword(self, r, sender, state, message, status_callback):
        target = r["target_state"]
        set_state(sender, target)
        if target.startswith("active:") and ":" in target:
            return self._active(sender, target.split(":", 1)[1], message, intro=True)
        return self._triage(sender, message, status_callback)

    def _triage(self, sender: str, message: str, status_callback=None) -> str:
        reply = self._receptionist.generate(f"Conversation so far:\n{self._context(sender)}")
        m = _ROUTE_RE.search(reply)
        if m:
            service, description = m.group(1), m.group(2)
            if service not in self._specialists and status_callback:
                status_callback(f"Please wait, creating the {service} specialist...")
            self._ensure_specialist(service, description)
            set_state(sender, f"active:{service}")
            specialist = self._specialists.get(service)
            if specialist:
                intro = specialist.generate(f"(The receptionist has connected me to {service}. Introduce yourself and ask how you can help. Mention that the user can say 'new conversation' to go back to the receptionist for a different service.)")
                add_to_history(sender, "assistant", intro)
                return intro
        add_to_history(sender, "assistant", reply)
        return reply

    def _active(self, sender: str, service: str, message: str, intro: bool = False) -> str:
        if service not in self._specialists:
            self._ensure_specialist(service)
        specialist = self._specialists.get(service)
        if not specialist:
            set_state(sender, "triage")
            return self._triage(sender, message)
        text = (f"(The receptionist has connected me to {service}. This user has indicated they want help. Introduce yourself and ask how you can help. Mention that the user can say 'new conversation' to go back to the receptionist for a different service.)" if intro
                else f"Context (conversation with {service}):\n{self._context(sender)}")
        reply = specialist.generate(text)
        add_to_history(sender, "assistant", reply)
        return reply

    def _ensure_specialist(self, name: str, description: str | None = None) -> bool:
        if name in self._specialists:
            return True
        if self.llm_config.get("mock", False):
            self._specialists[name] = RuleBasedNurse()
            return True
        topic = description or name
        try:
            import requests
            r = requests.post(
                f"{self.llm_config.get('api_url', 'https://api.groq.com/openai/v1')}/chat/completions",
                json={"model": self.llm_config.get("model", "llama-3.3-70b-versatile"), "messages": [{"role": "user", "content": f"Write a short system prompt (max 5 sentences, in English) for an AI assistant that is an expert in: {topic}. Describe their expertise, their style of answering, and that they should be concise (max 3-4 sentences). Only the prompt, no explanation."}]},
                headers={"Authorization": f"Bearer {self.llm_config.get('api_key', '')}", "Content-Type": "application/json"},
                timeout=30,
            )
            r.raise_for_status()
            (_PROMPTS_DIR / f"{name}.md").write_text(r.json()["choices"][0]["message"]["content"].strip())
            self._specialists[name] = LLMAdapter(self.llm_config, name)
        except:
            return False
        self._register_specialist_in_db(name, topic)
        return True

    def get_specialist_name(self, service: str) -> str:
        return self._persona_cache.get(service) or service.replace("-", " ").title()
