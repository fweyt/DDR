import requests


class SignalSender:
    def __init__(self, config: dict) -> None:
        self.api_url = config.get("api_url", "http://localhost:8080").rstrip("/")
        self.number = config.get("number", "+32XXXXXXXXX")

    def send(self, recipient: str, text: str) -> bool:
        payload = {
            "message": text,
            "number": self.number,
            "recipients": [recipient],
        }
        try:
            resp = requests.post(
                f"{self.api_url}/v2/send",
                json=payload,
                timeout=15,
            )
            if resp.status_code not in (200, 201):
                return False
            data = resp.json()
            if isinstance(data, dict):
                if recipient in data.get("unregisteredRecipients", []) or recipient in data.get("failedRecipients", []):
                    return False
            return True
        except requests.RequestException:
            return False
