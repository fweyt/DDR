from pathlib import Path
import re


class RuleBasedNurse:
    """
    Deterministic triage engine.
    Reads prompts/*.md and uses keyword matching to route and respond.
    No external API needed — works offline, fully testable.
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
        self.spoed_keywords = [
            "bewustzijnsverlies", "verward", "insult", "benauwd", "ademhalings",
            "pijn op de borst", "drukkend gevoel", "ernstige bloeding", "groot trauma",
            "brandwonden", "beroerte", "scheve mond", "verlamde arm", "onduidelijke spraak",
            "allergische reactie", "zwelling van mond", "zwelling van keel",
            "112", "spoed", "hartaanval", "niet meer wakker",
        ]
        self.dringend_keywords = [
            "hoge koorts", "baby", "hoge bloeddruk",
            "onverklaarbaar gewichtsverlies", "zelfmoord", "suïcidaal",
            "wazig zien", "dubbelzien", "stijve nek",
            "huisarts", "dokter", "wachtpost",
        ]
        self.condition_map = {
            "hoofdpijn": self._advice_headache,
            "koorts": self._advice_fever,
            "wond": self._advice_wound,
            "snijwond": self._advice_wound,
            "schaafwond": self._advice_wound,
            "diarree": self._advice_diarrhea,
            "misselijk": self._advice_nausea,
            "braken": self._advice_nausea,
            "overgeven": self._advice_nausea,
            "uitslag": self._advice_rash,
            "eczeem": self._advice_rash,
        }

    def generate(self, message: str) -> str:
        msg_lower = message.lower()

        if any(kw in msg_lower for kw in self.spoed_keywords):
            return (
                "⚠️ **Dit klinkt alsof je onmiddellijk medische hulp nodig hebt.**\n\n"
                "Bel **112** of ga naar de spoedafdeling. Ik kan geen spoedhulp verlenen, "
                "maar blijf gerust aan de lijn tot de hulpverleners er zijn."
            )

        if any(kw in msg_lower for kw in self.dringend_keywords):
            return (
                "🕐 **Dit is niet acuut levensbedreigend, maar je moet er wel "
                "binnen 24 uur een arts naar laten kijken.**\n\n"
                "Bel je **huisarts** of de **huisartsenwachtpost**. "
                "Als de klachten verergeren, aarzel dan niet om alsnog 112 te bellen."
            )

        for keyword, handler in self.condition_map.items():
            if keyword in msg_lower:
                return handler()

        return (
            "Bedankt voor je bericht. Ik ben een digitale verpleger en kan je gericht advies "
            "geven over gezondheidsklachten.\n\n"
            "Kun je kort omschrijven wat je klacht is? Bijvoorbeeld: hoofdpijn, koorts, "
            "een wond, of iets anders?\n\n"
            "*(Bij ernstige klachten: aarzel niet om 112 te bellen.)*"
        )

    def _advice_headache(self) -> str:
        return (
            "**Hoofdpijn** — meestal onschuldig, maar soms een signaal.\n\n"
            "- Rust, voldoende water drinken\n"
            "- Paracetamol 500-1000mg (max 4g/dag)\n"
            "- Donkere kamer, weinig prikkels\n\n"
            "**Raadpleeg een arts als:**\n"
            "- De pijn plotseling héél hevig is ('knal')\n"
            "- Je een stijve nek hebt of koorts\n"
            "- Het langer dan 7 dagen aanhoudt"
        )

    def _advice_fever(self) -> str:
        return (
            "**Koorts** — het lichaam vecht tegen een infectie.\n\n"
            "- Veel drinken (water, thee)\n"
            "- Paracetamol bij hoge koorts of pijn\n"
            "- Rust houden\n\n"
            "**Raadpleeg een arts als:**\n"
            "- Koorts > 39°C en niet daalt met paracetamol\n"
            "- Koorts langer dan 3 dagen\n"
            "- Je benauwd bent, verward, of suf wordt\n"
            "- Baby < 3 maanden met koorts > 38°C"
        )

    def _advice_wound(self) -> str:
        return (
            "**Wondverzorging:**\n\n"
            "- Reinig met zuiver water\n"
            "- Ontsmet met jodium of chloorhexidine\n"
            "- Dek af met steriel verband of pleister\n"
            "- Check tetanusvaccinatie (om de 10 jaar)\n\n"
            "**Raadpleeg een arts als:**\n"
            "- De wond rood wordt, warm aanvoelt of pus geeft\n"
            "- Je tetanus niet op orde is\n"
            "- De wond diep is of blijft bloeden"
        )

    def _advice_diarrhea(self) -> str:
        return (
            "**Diarree** — meestal viraal of door voeding.\n\n"
            "- ORS (oral rehydration salts) of water met een snuf zout en suiker\n"
            "- Kleine slokjes, frequent\n"
            "- Eet licht: beschuit, banaan, witbrood\n\n"
            "**Raadpleeg een arts als:**\n"
            "- Het langer dan 3 dagen duurt\n"
            "- Je bloed bij de ontlasting ziet\n"
            "- Je suf of verward wordt (uitdroging)"
        )

    def _advice_nausea(self) -> str:
        return (
            "**Misselijkheid/braken** — veel oorzaken mogelijk.\n\n"
            "- Kleine slokjes water, gemberthee\n"
            "- Kolazuur (7-Up, cola) kan helpen\n"
            "- Eet pas als de misselijkheid over is\n\n"
            "**Raadpleeg een arts als:**\n"
            "- Je geen vocht binnen kunt houden\n"
            "- Het langer dan 48 uur duurt\n"
            "- Je hevige buikpijn hebt"
        )

    def _advice_rash(self) -> str:
        return (
            "**Huiduitslag** — kan vele oorzaken hebben.\n\n"
            "- Koel houden, niet krabben\n"
            "- Vochtinbrengende crème (zonder parfum)\n"
            "- Bij jeuk: antihistaminicum (bv. cetirizine)\n\n"
            "**Raadpleeg een arts als:**\n"
            "- De uitslag gepaard gaat met koorts\n"
            "- Het eczeem ondanks verzorging verergert\n"
            "- Je bijkomende klachten hebt (benauwdheid, zwelling)"
        )


class LLMAdapter:
    """
    Pluggable LLM adapter for OpenAI-compatible chat completion APIs.
    Only used when llm.mock == false in config.
    """

    def __init__(self, config: dict) -> None:
        self.api_url = config["api_url"].rstrip("/")
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "gpt-4o")

    def generate(self, user_message: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Je bent een digitale verpleger."},
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
