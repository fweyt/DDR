from pathlib import Path

import requests

_DIR = Path(__file__).resolve().parent.parent / "prompts"


class LLMAdapter:
    _ZEN_URL = "https://opencode.ai/zen/v1"
    _ZEN_AUTH = Path.home() / ".local/share/opencode/auth.json"

    def __init__(self, config: dict, prompt_name: str = "system_prompt") -> None:
        c = config
        self.api_url = c.get("api_url", self._ZEN_URL).rstrip("/")
        self.api_key = c.get("api_key", "") or self._load_zen_key()
        self.model = c.get("model", "big-pickle")

        def r(n): p = _DIR / n; return p.read_text().strip() if p.exists() else ""
        self.system_prompt = r(f"{prompt_name}.md")
        self.triage_protocol = r("triage_protocol.md") if prompt_name == "system_prompt" else ""
        self.knowledge_base = r("knowledge_base.md") if prompt_name == "system_prompt" else ""

    def _load_zen_key(self) -> str:
        try:
            if self._ZEN_AUTH.exists():
                import json
                return json.loads(self._ZEN_AUTH.read_text()).get("opencode", {}).get("key", "")
        except: pass
        return ""

    def _system_prompt(self) -> str:
        parts = [p for p in (self.system_prompt, self.triage_protocol, self.knowledge_base) if p]
        return "\n\n".join(parts) + "\n\nBe concise. Maximum 3-4 sentences per response."

    def generate(self, msg: str) -> str:
        try:
            r = requests.post(
                f"{self.api_url}/chat/completions",
                json={"model": self.model, "messages": [{"role": "system", "content": self._system_prompt()}, {"role": "user", "content": msg}]},
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                timeout=60,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"⚠️ Nurse system error: {e}"


_EMERGENCY = ["unconsciousness", "confused", "seizure", "shortness of breath", "breathing",
    "chest pain", "tightness", "severe bleeding", "major trauma", "burns", "stroke",
    "crooked mouth", "paralyzed arm", "slurred speech", "allergic reaction",
    "swelling of mouth", "swelling of throat", "911", "emergency", "heart attack",
    "unresponsive", "112"]

_URGENT = ["high fever", "baby", "high blood pressure", "unexplained weight loss",
    "suicide", "suicidal", "blurred vision", "double vision", "stiff neck",
    "GP", "doctor", "urgent care"]

_ADVICE = {
    "headache": ("Headache — usually harmless, but sometimes a signal.",
        "- Rest, drink plenty of water\n- Paracetamol 500-1000mg (max 4g/day)\n- Dark room, minimal stimulation",
        "**Consult a doctor if:**\n- The pain is suddenly very severe ('thunderclap')\n- You have a stiff neck or fever\n- It lasts longer than 7 days"),
    "fever": ("Fever — the body is fighting an infection.",
        "- Drink plenty (water, tea)\n- Paracetamol for high fever or pain\n- Get rest",
        "**Consult a doctor if:**\n- Fever > 39°C and does not drop with paracetamol\n- Fever lasts longer than 3 days\n- You are short of breath, confused, or drowsy\n- Infant < 3 months with fever > 38°C"),
    "wound": ("Wound care:",
        "- Clean with clean water\n- Disinfect with iodine or chlorhexidine\n- Cover with sterile bandage or plaster\n- Check tetanus vaccination (every 10 years)",
        "**Consult a doctor if:**\n- The wound becomes red, feels warm, or produces pus\n- Your tetanus is not up to date\n- The wound is deep or keeps bleeding"),
    "diarrhea": ("Diarrhea — usually viral or from food.",
        "- ORS (oral rehydration salts) or water with a pinch of salt and sugar\n- Small sips, frequently\n- Eat light: crackers, banana, white bread",
        "**Consult a doctor if:**\n- It lasts longer than 3 days\n- You see blood in your stool\n- You feel drowsy or confused (dehydration)"),
    "nausea": ("Nausea/vomiting — many possible causes.",
        "- Small sips of water, ginger tea\n- Flat soda (7-Up, cola) can help\n- Eat only after the nausea subsides",
        "**Consult a doctor if:**\n- You cannot keep fluids down\n- It lasts longer than 48 hours\n- You have severe abdominal pain"),
    "rash": ("Skin rash — can have many causes.",
        "- Keep cool, do not scratch\n- Moisturizing cream (unscented)\n- For itching: antihistamine (e.g. cetirizine)",
        "**Consult a doctor if:**\n- The rash is accompanied by fever\n- The eczema worsens despite care\n- You have additional symptoms (shortness of breath, swelling)"),
}

_ADVICE.update({k: _ADVICE["wound"] for k in ("cut", "abrasion")})
_ADVICE.update({k: _ADVICE["nausea"] for k in ("vomiting",)})
_ADVICE.update({k: _ADVICE["rash"] for k in ("eczema",)})


def _fmt(title: str, bullets: str, danger: str) -> str:
    return f"**{title}**\n\n{bullets}\n\n{danger}"


class RuleBasedNurse:
    def generate(self, message: str) -> str:
        m = message.lower()
        if any(k in m for k in _EMERGENCY):
            return ("⚠️ **This sounds like you need immediate medical help.**\n\n"
                    "Call **911** or go to the emergency room. I cannot provide emergency care, "
                    "but feel free to stay on the line until help arrives.")
        if any(k in m for k in _URGENT):
            return ("🕐 **This is not acutely life-threatening, but you should "
                    "have a doctor look at it within 24 hours.**\n\n"
                    "Call your **GP** or the **out-of-hours GP service**. "
                    "If symptoms worsen, do not hesitate to call 911.")
        for kw, (t, b, d) in _ADVICE.items():
            if kw in m:
                return _fmt(t, b, d)
        return ("Thank you for your message. I am a digital nurse and can provide targeted advice "
                "about health complaints.\n\n"
                "Can you briefly describe what your complaint is? For example: headache, fever, "
                "a wound, or something else?\n\n"
                "*(For serious complaints: do not hesitate to call 911.)*")
