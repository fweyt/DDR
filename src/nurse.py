from pathlib import Path

import requests


class LLMAdapter:
    def __init__(self, config: dict) -> None:
        self.api_url = config["api_url"].rstrip("/")
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "gpt-4o")
        self.system_prompt = self._read("system_prompt.md")
        self.triage_protocol = self._read("triage_protocol.md")
        self.knowledge_base = self._read("knowledge_base.md")

    def _read(self, name: str) -> str:
        path = Path(__file__).resolve().parent.parent / "prompts" / name
        if path.exists():
            return path.read_text().strip()
        return ""

    def _build_system_prompt(self) -> str:
        parts = [p for p in (self.system_prompt, self.triage_protocol, self.knowledge_base) if p]
        return "\n\n".join(parts)

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
                f"{self.api_url}/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            return f"⚠️ Nurse-systeemfout: {exc}"


class MockLLM:
    def generate(self, user_message: str) -> str:
        return (
            f"Dit is een mock-antwoord van de AI-verpleger. "
            f"Je bericht was: \"{user_message[:100]}\"."
        )
