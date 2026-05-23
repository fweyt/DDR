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
        "choices": [{"message": {"content": "Raadpleeg je huisarts."}}]
    }

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = fake_response

        reply = adapter.generate("Ik heb al dagen hoofdpijn.")

    assert reply == "Raadpleeg je huisarts."

    call_args = mock_post.call_args
    assert call_args[0][0] == "http://test-llm.local/chat/completions"
    payload = call_args[1]["json"]
    assert payload["model"] == "test-model"
    assert payload["messages"][1]["content"] == "Ik heb al dagen hoofdpijn."
    assert "system" in payload["messages"][0]["role"]


def test_llm_adapter_handles_api_error():
    config = {"api_url": "http://test-llm.local", "api_key": "", "model": "m"}
    adapter = LLMAdapter(config)

    with patch("requests.post") as mock_post:
        mock_post.side_effect = Exception("connection refused")
        reply = adapter.generate("Hallo")

    assert "Nurse-systeemfout" in reply


# ── RuleBasedNurse ─────────────────────────────────────────────────

def _nurse() -> RuleBasedNurse:
    return RuleBasedNurse()


def test_spoed_triggers_emergency():
    reply = _nurse().generate("Ik heb pijn op de borst en ben benauwd.")
    assert "112" in reply
    assert "spoed" in reply.lower()


def test_dringend_triggers_urgent():
    reply = _nurse().generate("Ik heb al dagen hoge koorts.")
    assert "huisarts" in reply or "wachtpost" in reply


def test_headache_advice():
    reply = _nurse().generate("Ik heb hoofdpijn, wat kan ik doen?")
    assert "Paracetamol" in reply
    assert "hoofdpijn" in reply.lower()


def test_fever_advice():
    reply = _nurse().generate("Mijn kind heeft koorts.")
    assert "Koorts" in reply


def test_wound_advice():
    reply = _nurse().generate("Ik heb een snijwond aan mijn vinger.")
    assert "Wondverzorging" in reply or "Ontsmet" in reply


def test_fallback_for_unknown():
    reply = _nurse().generate("Vertel eens een mop.")
    assert "digitale verpleger" in reply


def test_fever_with_dringend_keyword_bubbles_up():
    reply = _nurse().generate("Ik heb hoge koorts en ben suf.")
    assert "huisarts" in reply or "wachtpost" in reply


def test_spoed_keyword_embedded_in_sentence():
    reply = _nurse().generate("Mijn moeder heeft een beroerte gehad.")
    assert "112" in reply
