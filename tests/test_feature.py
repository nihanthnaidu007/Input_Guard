"""Tests for feature addition rule set."""
from inputguard import InputGuard


def test_feature_intent_detected():
    guard = InputGuard()
    r = guard.analyze("add search to my existing React app")
    assert r.detected_intent == "feature"


def test_missing_existing_stack_fires():
    guard = InputGuard()
    r = guard.analyze("add a search feature to my existing app")
    codes = [f.code for f in r.findings]
    assert "missing_existing_stack" in codes


def test_missing_existing_stack_suppressed():
    guard = InputGuard()
    r = guard.analyze(
        "add search to my existing React and FastAPI app"
    )
    codes = [f.code for f in r.findings]
    assert "missing_existing_stack" not in codes


def test_missing_feature_scope_fires():
    guard = InputGuard()
    r = guard.analyze("add search to my current project")
    codes = [f.code for f in r.findings]
    assert "missing_feature_scope" in codes


def test_missing_feature_scope_suppressed():
    guard = InputGuard()
    r = guard.analyze(
        "add full text search by product name to my existing app "
        "so that results appear as the user types"
    )
    codes = [f.code for f in r.findings]
    assert "missing_feature_scope" not in codes


def test_missing_completion_criteria_fires():
    guard = InputGuard()
    r = guard.analyze("add authentication to my existing Node.js app")
    codes = [f.code for f in r.findings]
    assert "missing_completion_criteria" in codes


def test_missing_completion_criteria_suppressed():
    guard = InputGuard()
    r = guard.analyze(
        "add JWT auth to my existing FastAPI app. "
        "Done means users can register, log in, and access protected routes."
    )
    codes = [f.code for f in r.findings]
    assert "missing_completion_criteria" not in codes


def test_well_specified_feature_scores_high():
    guard = InputGuard()
    r = guard.analyze(
        "Add full-text search to my existing FastAPI and React app. "
        "Search by product name and description, case-insensitive. "
        "Done means users can type in a search box and see results "
        "appear within 300ms."
    )
    assert r.clarity_score >= 85


def test_feature_detected_intent_in_result():
    guard = InputGuard()
    r = guard.analyze("extend my current codebase with caching")
    assert r.detected_intent == "feature"
