"""Tests for debug rule set."""
from inputguard import InputGuard


def test_debug_intent_detected():
    guard = InputGuard()
    r = guard.analyze("fix my code")
    assert r.detected_intent == "debug"


def test_missing_error_message_fires():
    guard = InputGuard()
    r = guard.analyze("fix my code it is not working")
    codes = [f.code for f in r.findings]
    assert "missing_error_message" in codes


def test_missing_error_message_suppressed_with_error():
    guard = InputGuard()
    r = guard.analyze(
        "fix my code I am getting a TypeError: "
        "cannot read property of undefined"
    )
    codes = [f.code for f in r.findings]
    assert "missing_error_message" not in codes


def test_missing_expected_vs_actual_fires():
    guard = InputGuard()
    r = guard.analyze("my code is broken please fix it")
    codes = [f.code for f in r.findings]
    assert "missing_expected_vs_actual" in codes


def test_missing_expected_vs_actual_suppressed():
    guard = InputGuard()
    r = guard.analyze(
        "fix this function — it should return a list but instead returns None"
    )
    codes = [f.code for f in r.findings]
    assert "missing_expected_vs_actual" not in codes


def test_missing_debug_code_context_fires():
    guard = InputGuard()
    r = guard.analyze("it is not working at all")
    codes = [f.code for f in r.findings]
    assert "missing_debug_code_context" in codes


def test_missing_debug_code_context_suppressed():
    guard = InputGuard()
    r = guard.analyze(
        "fix this Python function get_users() it is not working"
    )
    codes = [f.code for f in r.findings]
    assert "missing_debug_code_context" not in codes


def test_well_specified_debug_scores_high():
    guard = InputGuard()
    r = guard.analyze(
        "Fix this Python function get_users() — it should return a list "
        "of user dicts but instead returns None. The error says: "
        "TypeError: NoneType is not iterable on line 45."
    )
    assert r.clarity_score >= 85
    assert r.status == "ready"


def test_debug_recommendations_have_four_keys():
    guard = InputGuard()
    r = guard.analyze("fix my code")
    for rec in r.recommendations:
        assert "gap" in rec
        assert "what_is_missing" in rec
        assert "what_to_provide" in rec
        assert "why_it_matters" in rec
