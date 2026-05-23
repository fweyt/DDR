from pathlib import Path

import requests


class LLMAdapter:
    """
    Nurse backend using an external LLM via OpenAI-compatible API.
    Reads prompts/*.md as the system prompt harness.

    Defaults to OpenCode Zen (free for Big Pickle).
    API key is auto-detected from ~/.local/share/opencode/auth.json
    if not provided in config.
    """

    _ZEN_URL = "https://opencode.ai/zen/v1"
    _ZEN_AUTH = Path.home() / ".local/share/opencode/auth.json"

    def __init__(self, config: dict, prompt_name: str = "system_prompt") -> None:
        self.api_url = config.get("api_url", self._ZEN_URL).rstrip("/")
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "big-pickle")
        if not self.api_key:
            self._zen_key()
        self.system_prompt = self._read(f"{prompt_name}.md")
        if prompt_name == "system_prompt":
            self.triage_protocol = self._read("triage_protocol.md")
            self.knowledge_base = self._read("knowledge_base.md")
        else:
            self.triage_protocol = ""
            self.knowledge_base = ""

    def _zen_key(self) -> None:
        try:
            if self._ZEN_AUTH.exists():
                import json
                data = json.loads(self._ZEN_AUTH.read_text())
                key = data.get("opencode", {}).get("key", "")
                if key:
                    self.api_key = key
        except Exception:
            pass

    def _read(self, name: str) -> str:
        path = Path(__file__).resolve().parent.parent / "prompts" / name
        if path.exists():
            return path.read_text().strip()
        return ""

    def _build_system_prompt(self) -> str:
        parts = [p for p in (self.system_prompt, self.triage_protocol, self.knowledge_base) if p]
        prompt = "\n\n".join(parts)
        prompt += "\n\nBe concise. Maximum 3-4 sentences per response."
        return prompt

    def generate(self, user_message: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._build_system_prompt()},
                {"role": "user", "content": user_message},
            ],
        }
        try:
            resp = requests.post(
                f"{self.api_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            return f"⚠️ Nurse system error: {exc}"


class RuleBasedNurse:
    """
    Deterministic triage fallback — used when mock: true.
    Keyword matching on prompts/*.md rules. No external API needed.
    """

    def __init__(self) -> None:
        self.system_prompt = self._read("system_prompt.md")
        self.triage_protocol = self._read("triage_protocol.md")
        self.knowledge_base = self._read("knowledge_base.md")
        self._compile_rules()

    def _read(self, name: str) -> str:
        path = Path(__file__).resolve().parent.parent / "prompts" / name
        if path.exists():
            return path.read_text().strip()
        return ""

    def _compile_rules(self) -> None:
        self.emergency_keywords = [
            "unconsciousness", "confused", "seizure", "shortness of breath", "breathing",
            "chest pain", "tightness", "severe bleeding", "major trauma",
            "burns", "stroke", "crooked mouth", "paralyzed arm", "slurred speech",
            "allergic reaction", "swelling of mouth", "swelling of throat",
            "911", "emergency", "heart attack", "unresponsive", "112",
        ]
        self.urgent_keywords = [
            "high fever", "baby", "high blood pressure",
            "unexplained weight loss", "suicide", "suicidal",
            "blurred vision", "double vision", "stiff neck",
            "GP", "doctor", "urgent care",
        ]
        self.condition_map = {
            "headache": self._advice_headache,
            "fever": self._advice_fever,
            "wound": self._advice_wound,
            "cut": self._advice_wound,
            "abrasion": self._advice_wound,
            "diarrhea": self._advice_diarrhea,
            "nausea": self._advice_nausea,
            "vomiting": self._advice_nausea,
            "rash": self._advice_rash,
            "eczema": self._advice_rash,
        }

    def handle(self, sender: str, message: str) -> str:
        return self.generate(message)

    def generate(self, message: str) -> str:
        msg_lower = message.lower()

        if any(kw in msg_lower for kw in self.emergency_keywords):
            return (
                "⚠️ **This sounds like you need immediate medical help.**\n\n"
                "Call **911** or go to the emergency room. I cannot provide emergency care, "
                "but feel free to stay on the line until help arrives."
            )

        if any(kw in msg_lower for kw in self.urgent_keywords):
            return (
                "🕐 **This is not acutely life-threatening, but you should "
                "have a doctor look at it within 24 hours.**\n\n"
                "Call your **GP** or the **out-of-hours GP service**. "
                "If symptoms worsen, do not hesitate to call 911."
            )

        for keyword, handler in self.condition_map.items():
            if keyword in msg_lower:
                return handler()

        return (
            "Thank you for your message. I am a digital nurse and can provide targeted advice "
            "about health complaints.\n\n"
            "Can you briefly describe what your complaint is? For example: headache, fever, "
            "a wound, or something else?\n\n"
            "*(For serious complaints: do not hesitate to call 911.)*"
        )

    def _advice_headache(self) -> str:
        return (
            "**Headache** — usually harmless, but sometimes a signal.\n\n"
            "- Rest, drink plenty of water\n"
            "- Paracetamol 500-1000mg (max 4g/day)\n"
            "- Dark room, minimal stimulation\n\n"
            "**Consult a doctor if:**\n"
            "- The pain is suddenly very severe ('thunderclap')\n"
            "- You have a stiff neck or fever\n"
            "- It lasts longer than 7 days"
        )

    def _advice_fever(self) -> str:
        return (
            "**Fever** — the body is fighting an infection.\n\n"
            "- Drink plenty (water, tea)\n"
            "- Paracetamol for high fever or pain\n"
            "- Get rest\n\n"
            "**Consult a doctor if:**\n"
            "- Fever > 39°C and does not drop with paracetamol\n"
            "- Fever lasts longer than 3 days\n"
            "- You are short of breath, confused, or drowsy\n"
            "- Infant < 3 months with fever > 38°C"
        )

    def _advice_wound(self) -> str:
        return (
            "**Wound care:**\n\n"
            "- Clean with clean water\n"
            "- Disinfect with iodine or chlorhexidine\n"
            "- Cover with sterile bandage or plaster\n"
            "- Check tetanus vaccination (every 10 years)\n\n"
            "**Consult a doctor if:**\n"
            "- The wound becomes red, feels warm, or produces pus\n"
            "- Your tetanus is not up to date\n"
            "- The wound is deep or keeps bleeding"
        )

    def _advice_diarrhea(self) -> str:
        return (
            "**Diarrhea** — usually viral or from food.\n\n"
            "- ORS (oral rehydration salts) or water with a pinch of salt and sugar\n"
            "- Small sips, frequently\n"
            "- Eat light: crackers, banana, white bread\n\n"
            "**Consult a doctor if:**\n"
            "- It lasts longer than 3 days\n"
            "- You see blood in your stool\n"
            "- You feel drowsy or confused (dehydration)"
        )

    def _advice_nausea(self) -> str:
        return (
            "**Nausea/vomiting** — many possible causes.\n\n"
            "- Small sips of water, ginger tea\n"
            "- Flat soda (7-Up, cola) can help\n"
            "- Eat only after the nausea subsides\n\n"
            "**Consult a doctor if:**\n"
            "- You cannot keep fluids down\n"
            "- It lasts longer than 48 hours\n"
            "- You have severe abdominal pain"
        )

    def _advice_rash(self) -> str:
        return (
            "**Skin rash** — can have many causes.\n\n"
            "- Keep cool, do not scratch\n"
            "- Moisturizing cream (unscented)\n"
            "- For itching: antihistamine (e.g. cetirizine)\n\n"
            "**Consult a doctor if:**\n"
            "- The rash is accompanied by fever\n"
            "- The eczema worsens despite care\n"
            "- You have additional symptoms (shortness of breath, swelling)"
        )
