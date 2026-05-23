from src.nurse import RuleBasedNurse


def _nurse() -> RuleBasedNurse:
    return RuleBasedNurse()


def test_spoed_triggers_emergency():
    n = _nurse()
    reply = n.generate("Ik heb pijn op de borst en ben benauwd.")
    assert "112" in reply
    assert "spoed" in reply.lower()


def test_dringend_triggers_urgent():
    n = _nurse()
    reply = n.generate("Ik heb al dagen hoge koorts.")
    assert "huisarts" in reply or "wachtpost" in reply


def test_headache_advice():
    n = _nurse()
    reply = n.generate("Ik heb hoofdpijn, wat kan ik doen?")
    assert "Paracetamol" in reply
    assert "hoofdpijn" in reply.lower()


def test_fever_advice():
    n = _nurse()
    reply = n.generate("Mijn kind heeft koorts.")
    assert "Koorts" in reply


def test_wound_advice():
    n = _nurse()
    reply = n.generate("Ik heb een snijwond aan mijn vinger.")
    assert "Wondverzorging" in reply or "Ontsmet" in reply


def test_fallback_for_unknown():
    n = _nurse()
    reply = n.generate("Vertel eens een mop.")
    assert "digitale verpleger" in reply


def test_fever_with_dringend_keyword_bubbles_up():
    n = _nurse()
    reply = n.generate("Ik heb hoge koorts en ben suf.")
    assert "huisarts" in reply or "wachtpost" in reply


def test_spoed_keyword_embedded_in_sentence():
    n = _nurse()
    reply = n.generate("Mijn moeder heeft een beroerte gehad.")
    assert "112" in reply
