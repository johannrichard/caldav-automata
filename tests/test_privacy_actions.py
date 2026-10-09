import pytest
from icalendar import Event

from caldav_automata import actions as a


@pytest.fixture(autouse=True)
def reset_llm_config():
    a.set_llm_config(None)
    yield
    a.set_llm_config(None)


def _ev(summary="Dentist appointment", desc=""):
    e = Event()
    e.add("UID", "u1")
    e.add("SUMMARY", summary)
    if desc:
        e.add("DESCRIPTION", desc)
    return e


@pytest.mark.parametrize("value", ["PUBLIC", "PRIVATE", "CONFIDENTIAL"])
def test_set_class_idempotent(value, caplog):
    caplog.set_level("INFO")
    e = _ev()
    assert a.apply_action(e, ["set-class", value.lower()])
    assert str(e["CLASS"]) == value
    assert f"Set CLASS:{value}" in caplog.text
    caplog.clear()
    assert not a.apply_action(e, ["set-class", value])
    assert f"CLASS already {value}" in caplog.text
    assert not a.apply_action(e, ["set-class", "bogus"])


def test_redact_whole_words():
    e = _ev("Dentist appointment", "see dentistry notes")
    assert a.apply_action(e, ["redact-words", "Private", "dentist"])
    assert str(e["SUMMARY"]) == "Private appointment"
    assert str(e["DESCRIPTION"]) == "see dentistry notes"
    assert not a.apply_action(e, ["redact-words", "Private", "dentist"])


def test_redact_replacement_is_literal():
    e = _ev()
    replacement = r"Private \1"
    assert a.apply_action(e, ["redact-words", replacement, "dentist"])
    assert str(e["SUMMARY"]) == "Private \\1 appointment"


def test_redact_preserves_property_parameters():
    e = _ev()
    e["SUMMARY"].params["LANGUAGE"] = "en"
    assert a.apply_action(e, ["redact-words", "Private", "dentist"])
    assert str(e["SUMMARY"]) == "Private appointment"
    assert e["SUMMARY"].params["LANGUAGE"] == "en"


def test_redact_preserves_repeated_text_properties():
    e = _ev()
    e.add("DESCRIPTION", "Dentist details", parameters={"LANGUAGE": "en"})
    e.add("DESCRIPTION", "Dentist notes", parameters={"LANGUAGE": "fr"})

    assert a.apply_action(e, ["redact-words", "Private", "dentist"])
    descriptions = e["DESCRIPTION"]
    assert [str(value) for value in descriptions] == [
        "Private details",
        "Private notes",
    ]
    assert [value.params["LANGUAGE"] for value in descriptions] == ["en", "fr"]


def test_redact_fields_option_narrows_properties():
    e = _ev("Dentist appointment", "Dentist details")
    assert a.apply_action(
        e, ["redact-words", "Private", "dentist", ["fields", "DESCRIPTION"]]
    )
    assert str(e["SUMMARY"]) == "Dentist appointment"
    assert str(e["DESCRIPTION"]) == "Private details"


def test_redact_outgoing_scope_skipped():
    e = _ev()
    assert not a.apply_action(
        e, ["redact-words", "P", "dentist", ["scope", "outgoing"]]
    )
    assert str(e["SUMMARY"]) == "Dentist appointment"


def test_redact_rejects_invalid_options_without_mutating_event():
    invalid_forms = [
        ["redact-words", "Private", "dentist", ["scpoe", "outgoing"]],
        ["redact-words", "Private", "dentist", ["scope", "outgoing", "stored"]],
        ["redact-words", "Private", "dentist", ["scope", "elsewhere"]],
        ["redact-words", "Private", "dentist", ["fields", "DTSTART"]],
        ["redact-words", "Private", "dentist", ["fields"]],
        ["redact-words", "Private", "dentist", []],
    ]
    for form in invalid_forms:
        e = _ev()
        assert not a.apply_action(e, form)
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


def test_llm_decision():
    ok = {"answers": {"is_private": {"type": "noul", "noul": 0.93}}}
    assert a.parse_decision_response(ok) == 0.93
    assert a.parse_decision_response({"answers": {}}) is None
    a.set_llm_config({"enabled": True, "model": "respan/span-01-lite"})
    e = _ev()
    assert a.classify_with_llm(e, request=lambda c, s, i: ok)
    assert str(e["CLASS"]) == "PRIVATE"
    low = {"answers": {"is_private": {"type": "noul", "noul": 0.1}}}
    e2 = _ev()
    e2["UID"] = "u2"
    assert not a.classify_with_llm(e2, request=lambda c, s, i: low)
    e3 = _ev()
    e3["UID"] = "u3"
    assert not a.classify_with_llm(e3, request=lambda c, s, i: {})
    a.set_llm_config(None)


def test_llm_cache_key_includes_classification_state():
    a.set_llm_config({"enabled": True, "model": "respan/span-01-lite"})
    calls = []
    response = {"answers": {"is_private": {"type": "noul", "noul": 0.93}}}

    def request(config, state, instructions):
        calls.append(state)
        return response

    e = _ev()
    assert a.classify_with_llm(e, request=request)
    e["SUMMARY"] = "Updated appointment"
    del e["CLASS"]
    assert a.classify_with_llm(e, request=request)
    assert len(calls) == 2
    a.set_llm_config(None)


def test_llm_cache_key_includes_model():
    a.set_llm_config({"enabled": True, "model": "model-one"})
    calls = []
    response = {"answers": {"is_private": {"type": "noul", "noul": 0.93}}}

    def request(config, state, instructions):
        calls.append(config["model"])
        return response

    e = _ev()
    assert a.classify_with_llm(e, request=request)
    del e["CLASS"]
    a.set_llm_config({"enabled": True, "model": "model-two"})
    assert a.classify_with_llm(e, request=request)
    assert calls == ["model-one", "model-two"]


def test_llm_cache_is_bounded(monkeypatch):
    a.set_llm_config({"enabled": True, "model": "respan/span-01-lite"})
    monkeypatch.setattr(a, "_LLM_CACHE_MAXSIZE", 2)
    calls = []
    response = {"answers": {"is_private": {"type": "noul", "noul": 0.1}}}

    def request(config, state, instructions):
        calls.append(state)
        return response

    for uid in ("u1", "u2"):
        e = _ev()
        e["UID"] = uid
        assert not a.classify_with_llm(e, request=request)

    e = _ev()
    assert not a.classify_with_llm(e, request=request)
    assert [key[0] for key in a._LLM_CACHE] == ["u2", "u1"]
    e = _ev()
    e["UID"] = "u3"
    assert not a.classify_with_llm(e, request=request)
    assert [key[0] for key in a._LLM_CACHE] == ["u1", "u3"]
    assert len(a._LLM_CACHE) == 2

    e = _ev()
    assert not a.classify_with_llm(e, request=request)
    e["UID"] = "u2"
    assert not a.classify_with_llm(e, request=request)
    assert len(calls) == 4
    assert len(a._LLM_CACHE) == 2
    a.set_llm_config(None)


def test_llm_rejects_invalid_thresholds(caplog):
    a.set_llm_config({"enabled": True, "model": "respan/span-01-lite"})
    for threshold in (-0.1, 1.1, float("nan"), "abc", None, True, False):
        caplog.clear()
        assert not a.classify_with_llm(
            _ev(),
            threshold=threshold,
            request=lambda *_: {
                "answers": {"is_private": {"type": "noul", "noul": 0.9}}
            },
        )
        assert len(caplog.records) == 1
        assert "invalid threshold" in caplog.records[0].message
    a.set_llm_config(None)
