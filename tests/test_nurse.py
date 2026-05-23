from unittest.mock import patch

from src.nurse import LLMAdapter, RuleBasedNurse


# ── LLMAdapter ─────────────────────────────────────────────────────

def test_llm_adapter_sends_correct_payload():
    config = {
        "api_url": "http://test-llm.local",
        "api_key": "test-key-123",
        "model": "test-model",
    }
    adapter = LLMAdapter(config)

    fake_response = {
        "choices": [{"message": {"content": "Consult your GP."}}]
    }

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = fake_response

        reply = adapter.generate("I have had a headache for days.")

    assert reply == "Consult your GP."

    call_args = mock_post.call_args
    assert call_args[0][0] == "http://test-llm.local/chat/completions"
    payload = call_args[1]["json"]
    assert payload["model"] == "test-model"
    assert payload["messages"][1]["content"] == "I have had a headache for days."
    assert "system" in payload["messages"][0]["role"]


def test_llm_adapter_handles_api_error():
    config = {"api_url": "http://test-llm.local", "api_key": "", "model": "m"}
    adapter = LLMAdapter(config)

    with patch("requests.post") as mock_post:
        mock_post.side_effect = Exception("connection refused")
        reply = adapter.generate("Hallo")

    assert "Nurse system error" in reply


# ── RuleBasedNurse ─────────────────────────────────────────────────

def _nurse() -> RuleBasedNurse:
    return RuleBasedNurse()


def test_emergency_triggers_emergency():
    reply = _nurse().generate("I have chest pain and shortness of breath.")
    assert "911" in reply
    assert "emergency" in reply.lower()


def test_urgent_triggers_urgent():
    reply = _nurse().generate("I have had a high fever for days.")
    assert "GP" in reply or "out-of-hours" in reply


def test_headache_advice():
    reply = _nurse().generate("I have a headache, what can I do?")
    assert "Paracetamol" in reply
    assert "headache" in reply.lower()


def test_fever_advice():
    reply = _nurse().generate("My child has a fever.")
    assert "Fever" in reply


def test_wound_advice():
    reply = _nurse().generate("I have a cut on my finger.")
    assert "Wound care" in reply or "Disinfect" in reply


def test_fallback_for_unknown():
    reply = _nurse().generate("Tell me a joke.")
    assert "digital nurse" in reply


def test_fever_with_urgent_keyword_bubbles_up():
    reply = _nurse().generate("I have a high fever and feel drowsy.")
    assert "GP" in reply or "out-of-hours" in reply


def test_emergency_keyword_embedded_in_sentence():
    reply = _nurse().generate("My mother had a stroke.")
    assert "911" in reply
