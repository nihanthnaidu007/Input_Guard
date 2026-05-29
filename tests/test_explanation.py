"""Tests for explanation rule set."""
from inputguard import InputGuard


def test_explanation_intent_detected():
    guard = InputGuard()
    r = guard.analyze("explain what this decorator does")
    assert r.detected_intent == "explanation"


def test_missing_code_reference_fires():
    guard = InputGuard()
    r = guard.analyze("explain this code to me")
    codes = [f.code for f in r.findings]
    assert "missing_code_reference" in codes


def test_missing_code_reference_suppressed():
    guard = InputGuard()
    r = guard.analyze(
        "explain what the @property decorator does in Python"
    )
    codes = [f.code for f in r.findings]
    assert "missing_code_reference" not in codes


def test_missing_explanation_depth_fires():
    guard = InputGuard()
    r = guard.analyze("explain how async await works")
    codes = [f.code for f in r.findings]
    assert "missing_explanation_depth" in codes


def test_missing_explanation_depth_suppressed():
    guard = InputGuard()
    r = guard.analyze(
        "explain how async await works in Python with simple examples "
        "for a beginner"
    )
    codes = [f.code for f in r.findings]
    assert "missing_explanation_depth" not in codes


def test_well_specified_explanation_scores_high():
    guard = InputGuard()
    r = guard.analyze(
        "Explain what the @property decorator does in Python. "
        "Give me a step by step breakdown with simple examples."
    )
    assert r.clarity_score >= 85


def test_explanation_detected_intent_in_result():
    guard = InputGuard()
    r = guard.analyze("what does this function do")
    assert r.detected_intent == "explanation"
