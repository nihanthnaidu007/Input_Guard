"""Tests for optimization rule set."""
from inputguard import InputGuard


def test_optimization_intent_detected():
    guard = InputGuard()
    r = guard.analyze("make this function faster")
    assert r.detected_intent == "optimization"


def test_missing_optimization_target_fires():
    guard = InputGuard()
    r = guard.analyze("make my code faster")
    codes = [f.code for f in r.findings]
    assert "missing_optimization_target" in codes


def test_missing_optimization_target_suppressed():
    guard = InputGuard()
    r = guard.analyze("optimize the get_users() function it is too slow")
    codes = [f.code for f in r.findings]
    assert "missing_optimization_target" not in codes


def test_missing_performance_baseline_fires():
    guard = InputGuard()
    r = guard.analyze("make my app faster")
    codes = [f.code for f in r.findings]
    assert "missing_performance_baseline" in codes


def test_missing_performance_baseline_suppressed():
    guard = InputGuard()
    r = guard.analyze(
        "optimize my API it currently takes 8 seconds to respond"
    )
    codes = [f.code for f in r.findings]
    assert "missing_performance_baseline" not in codes


def test_missing_optimization_constraint_fires():
    guard = InputGuard()
    r = guard.analyze("speed up my Python script")
    codes = [f.code for f in r.findings]
    assert "missing_optimization_constraint" in codes


def test_missing_optimization_constraint_suppressed():
    guard = InputGuard()
    r = guard.analyze(
        "optimize the query but keep it readable and maintainable"
    )
    codes = [f.code for f in r.findings]
    assert "missing_optimization_constraint" not in codes


def test_well_specified_optimization_scores_high():
    guard = InputGuard()
    r = guard.analyze(
        "Optimize the get_users() function in users.py — it currently takes "
        "8 seconds to run. Keep it readable and backward compatible."
    )
    assert r.clarity_score >= 85


def test_optimization_detected_intent_in_result():
    guard = InputGuard()
    r = guard.analyze("refactor this module")
    assert r.detected_intent == "optimization"
