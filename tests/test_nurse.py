from src.nurse import MockLLM


def test_mock_llm_returns_string():
    llm = MockLLM()
    reply = llm.generate("Hallo, ik voel me niet goed.")
    assert isinstance(reply, str)
    assert len(reply) > 0
    assert "mock-antwoord" in reply
