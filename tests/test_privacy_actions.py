from icalendar import Event

from caldav_automata import actions as a


def _ev(summary="Dentist appointment", desc=""):
    e = Event()
    e.add("UID", "u1")
    e.add("SUMMARY", summary)
    if desc:
        e.add("DESCRIPTION", desc)
    return e


def test_set_class_idempotent():
    e = _ev()
    assert a.apply_action(e, ["set-class", "confidential"])
    assert str(e["CLASS"]) == "CONFIDENTIAL"
    assert not a.apply_action(e, ["set-class", "CONFIDENTIAL"])
    assert not a.apply_action(e, ["set-class", "bogus"])


def test_redact_whole_words():
    e = _ev("Dentist appointment", "see dentistry notes")
    assert a.apply_action(e, ["redact-words", "Private", "dentist"])
    assert str(e["SUMMARY"]) == "Private appointment"
    assert str(e["DESCRIPTION"]) == "see dentistry notes"
    assert not a.apply_action(e, ["redact-words", "Private", "dentist"])


def test_redact_outgoing_scope_skipped():
    e = _ev()
    assert not a.apply_action(
        e, ["redact-words", "P", "dentist", ["scope", "outgoing"]]
    )
    assert str(e["SUMMARY"]) == "Dentist appointment"


def test_class_by_keyword_and_category():
    e = _ev()
    form = [
        "set-class-by-keyword",
        "PRIVATE",
        ["keywords", "dentist"],
        ["category", "Health"],
    ]
    assert a.apply_action(e, form)
    assert str(e["CLASS"]) == "PRIVATE"
    assert not a.apply_action(e, form)
    assert not a.apply_action(_ev("Standup"), form)


def test_llm_parse_and_classify():
    assert a.parse_llm_response('x {"private": true, "confidence": 0.9} y')["private"]
    assert a.parse_llm_response("nope") is None
    a.set_llm_config({"enabled": True, "model": "m"})
    e = _ev()
    assert a.classify_with_llm(
        e, request=lambda c, p: '{"private": true, "confidence": 0.9}'
    )
    assert str(e["CLASS"]) == "PRIVATE"
    e2 = _ev()
    e2["UID"] = "u2"
    assert not a.classify_with_llm(e2, request=lambda c, p: "garbage")
    a.set_llm_config(None)
