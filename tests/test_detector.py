"""Tests for intent detection in detector.py"""
from inputguard.detector import detect_intent


def test_debug_intent_on_fix():
    assert detect_intent("fix my code") == "debug"

def test_debug_intent_on_error():
    assert detect_intent("I'm getting a TypeError in my function") == "debug"

def test_debug_intent_on_not_working():
    assert detect_intent("it's not working and I don't know why") == "debug"

def test_debug_intent_on_broken():
    assert detect_intent("this function is broken") == "debug"

def test_optimization_intent():
    assert detect_intent("make this function faster") == "optimization"

def test_optimization_intent_refactor():
    assert detect_intent("refactor this code") == "optimization"

def test_optimization_intent_performance():
    assert detect_intent("improve the performance of my API") == "optimization"

def test_explanation_intent():
    assert detect_intent("explain what this decorator does") == "explanation"

def test_explanation_intent_how():
    assert detect_intent("how does async await work in Python") == "explanation"

def test_explanation_intent_what():
    assert detect_intent("what does this function do") == "explanation"

def test_feature_intent():
    assert detect_intent("add search to my existing React app") == "feature"

def test_feature_intent_extend():
    assert detect_intent("extend my current API with pagination") == "feature"

def test_build_intent_fallback():
    assert detect_intent("build a REST API using FastAPI") == "build"

def test_build_intent_fallback_create():
    assert detect_intent("create a web app with React") == "build"

def test_debug_beats_optimization():
    # "fix" is debug signal, "faster" is optimization — debug wins
    assert detect_intent("fix this slow function") == "debug"

def test_debug_beats_explanation():
    # "explain why" has both — debug signal wins
    assert detect_intent("explain why this is throwing an error") == "debug"

def test_case_insensitive():
    assert detect_intent("Fix My Code") == "debug"
    assert detect_intent("EXPLAIN HOW THIS WORKS") == "explanation"
