"""Follow-up question engine tests.

Three layers, matching the acceptance criteria:

- the registry-walking completeness invariant extended to follow-ups:
  every built-in gap has one or two curated questions, and the question
  table covers exactly the built-in gaps (drift in either direction fails);
- behavior on results: follow_ups present and non-empty wherever findings
  fire, deduped, ordered with gaps, empty when the input is clean;
- slot fills (function name, dataset name), the unknown-gap fallback,
  English score parity with v0.2, and thread-safe parallel consistency.

All existing tests are untouched — this file only adds.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from inputguard import AnalysisResult, InputGuard
from inputguard.followups import (
    _FOLLOW_UP_QUESTIONS,
    _extract_slots,
    _render,
    get_follow_ups,
)
from inputguard.recommender import _RECOMMENDATIONS
from inputguard.registry import REGISTRY, register_rule
from inputguard.rules.coding import run_coding_rules
from inputguard.rules.debug import run_debug_rules
from inputguard.rules.explanation import run_explanation_rules
from inputguard.rules.feature import run_feature_rules
from inputguard.rules.optimization import run_optimization_rules
from inputguard.scorer import calculate_score
from inputguard.types import RuleFinding


# --- the extended registry-walking completeness invariant --------------------


def _builtin_gaps():
    gaps = {rule.gap for rule in REGISTRY.rules() if rule.gap is not None}
    assert gaps, "built-in rules must declare gaps"
    return gaps


def test_every_builtin_gap_has_at_least_one_follow_up_question():
    # The extended invariant: a rule can ship a recommendation entry and
    # still leave the user with nothing to answer — every built-in gap must
    # also carry one or two curated clarifying questions.
    for gap in _builtin_gaps():
        assert gap in _FOLLOW_UP_QUESTIONS, f"gap {gap!r} has no follow-up question"
        questions = _FOLLOW_UP_QUESTIONS[gap]
        assert 1 <= len(questions) <= 2, f"gap {gap!r} must have one or two questions"
        for question in questions:
            assert isinstance(question, str) and question.endswith("?"), (
                f"gap {gap!r} has a malformed follow-up question: {question!r}"
            )


def test_follow_up_table_covers_exactly_the_builtin_gaps():
    # Two-way check: a question entry for a gap no rule declares is dead
    # config, so the table keys must equal the built-in gaps exactly.
    assert set(_FOLLOW_UP_QUESTIONS) == _builtin_gaps()


def test_every_template_renders_with_unknown_slot_failing_loudly():
    # Rendering every template against empty slots exercises the render path:
    # a typo'd slot name raises (loud table bug); a known-but-unfilled slot
    # skips the template (documented behavior); plain templates pass through.
    for gap, questions in _FOLLOW_UP_QUESTIONS.items():
        for question in questions:
            rendered = _render(question, slots={})
            if "{" in question:
                assert rendered is None
            else:
                assert rendered == question


def test_every_builtin_gap_has_recommendation_and_follow_up_pair():
    # The completeness invariant read whole: advice AND a question per gap.
    for gap in _builtin_gaps():
        assert gap in _RECOMMENDATIONS, f"gap {gap!r} has no recommendation entry"
        assert gap in _FOLLOW_UP_QUESTIONS, f"gap {gap!r} has no follow-up question"


# --- follow_ups on results ----------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "build a REST API",  # build
        "fix the login crash",  # debug
        "make this faster",  # optimization
        "explain async",  # explanation
        "add auth to my app",  # feature
    ],
)
def test_follow_ups_present_and_non_empty_on_findings_bearing_results(text):
    result = InputGuard().analyze(text)
    assert result.findings, "test input must be findings-bearing"
    assert result.gaps
    assert isinstance(result.follow_ups, list)
    assert result.follow_ups, "findings-bearing results must ask at least one question"
    assert all(
        isinstance(q, str) and q for q in result.follow_ups
    ), "follow-ups must be non-empty strings"
    # One or two per gap, deduped.
    assert len(result.gaps) <= len(result.follow_ups) <= 2 * len(result.gaps)
    assert len(result.follow_ups) == len(set(result.follow_ups)), "follow-ups must be deduped"


def test_ready_results_have_empty_follow_ups():
    text = (
        "Write a Python function using FastAPI and PostgreSQL that returns "
        "a JSON list of users"
    )
    result = InputGuard().analyze(text)
    assert result.clarity_score == 100
    assert result.follow_ups == []


def test_follow_ups_order_matches_gap_order_and_spec_examples():
    # "make this faster" is the spec's example input: its first two
    # follow-ups are pinned byte-exact to the spec's example output, which
    # also pins follow-up order to gap order.
    result = InputGuard().analyze("make this faster")
    assert result.gaps == [
        "optimization target",
        "performance baseline",
        "optimization constraint",
    ]
    assert result.follow_ups[0] == "Which function or module should get faster?"
    assert result.follow_ups[1] == "How slow is it today, and what latency would be acceptable?"
    assert result.follow_ups[2] in {
        "What must not change while it gets faster — an interface, readability, "
        "behavior others depend on?",
    }


# --- dedup, ordering, and the unknown-gap fallback ----------------------------


def test_follow_ups_are_deduped_across_gaps():
    questions = get_follow_ups(
        ["task context", "task context", "error description"],
        "fix the login crash",
    )
    assert len(questions) == len(set(questions))


def test_follow_ups_order_follows_the_gap_list():
    error_first = get_follow_ups(["error description", "task context"], "text")
    task_first = get_follow_ups(["task context", "error description"], "text")
    assert error_first[0].startswith("What is the exact error")
    assert task_first[0].startswith("What are you trying to build")


def test_unknown_gap_gets_the_documented_fallback_question():
    assert get_follow_ups(["deadline"], "ship the report by Friday") == [
        "Can you add the deadline this request is missing?"
    ]


def test_user_rule_with_unknown_gap_still_gets_a_follow_up():
    finding = RuleFinding(
        code="missing_deadline",
        message="No deadline given.",
        severity="medium",
        gap="deadline",
    )

    class DeadlineRule:
        id = "test_followups_missing_deadline"
        domain = "build"
        severity = "medium"
        gap = "deadline"

        def check(self, text: str):
            return finding

    rules_before = {rule.id: rule for rule in REGISTRY.rules()}
    try:
        register_rule(DeadlineRule())
        result = InputGuard().analyze("build a REST API")
        assert result.findings
        # "build a REST API" also fires the built-in missing-language rule;
        # the point here is the unknown gap: it joins the result and its
        # fallback question lands in follow_ups, in gap order.
        assert result.gaps[-1] == "deadline"
        assert result.follow_ups[-1] == "Can you add the deadline this request is missing?"
        assert result.follow_ups[-1] in result.to_dict()["follow_ups"]
    finally:
        REGISTRY._rules.clear()
        REGISTRY._rules.update(rules_before)


# --- slot fills ---------------------------------------------------------------


def test_function_slot_fill_from_call_site():
    result = InputGuard().analyze(
        "speed up my code — the render loop calls update_positions() on every frame"
    )
    assert "optimization target" in result.gaps
    assert (
        "What makes update_positions slow today, and how fast should it be?"
        in result.follow_ups
    )


def test_dataset_slot_fill_from_named_file():
    result = InputGuard().analyze(
        "analyze the sales_data.csv table and find the top customers"
    )
    assert "data model" in result.gaps
    assert (
        "Which fields does sales_data.csv contain, and which of them matter for this task?"
        in result.follow_ups
    )


def test_prose_parentheticals_never_fill_the_function_slot():
    # Natural-language parentheses and control-flow keywords are not call
    # sites; without a fillable slot the slotted template is skipped and no
    # unfilled "{...}" ever leaks into a question.
    assert "function" not in _extract_slots("fix this (urgently) broken build")
    assert "function" not in _extract_slots("if(x > 3) the loop is wrong")
    for question in get_follow_ups(["code context"], "the build is broken"):
        assert "{" not in question


def test_slot_extraction_preserves_the_original_case():
    slots = _extract_slots("speed up ProcessOrders(")
    assert slots["function"] == "ProcessOrders"


# --- English score parity with v0.2 -------------------------------------------

_V02_INTENT_RUNNERS = {
    "build": run_coding_rules,
    "debug": run_debug_rules,
    "optimization": run_optimization_rules,
    "explanation": run_explanation_rules,
    "feature": run_feature_rules,
}

_V02_TO_DICT_KEYS = {
    "status",
    "clarity_score",
    "detected_intent",
    "gaps",
    "recommendations",
    "findings",
    "interpretation_note",
}


def _ordered_unique_gaps(findings):
    seen = set()
    out = []
    for f in findings:
        if f.gap is not None and f.gap not in seen:
            out.append(f.gap)
            seen.add(f.gap)
    return out


@pytest.mark.parametrize(
    "text",
    [
        "build a REST API",
        "fix the login crash",
        "make this faster",
        "explain async",
        "add auth to my app",
    ],
)
def test_english_score_parity_with_v02(text):
    # follow_ups are derived from gaps after scoring; the v0.2 numbers must
    # not move: same findings, same gap order, same score as the legacy
    # runners, and to_dict() gains exactly the merged additive keys
    # (follow_ups from the questions engine; the language-probe fields from
    # the multilingual degradation work).
    result = InputGuard().analyze(text)
    legacy = _V02_INTENT_RUNNERS[result.detected_intent](text)

    assert [f.code for f in result.findings] == [f.code for f in legacy]
    assert result.gaps == _ordered_unique_gaps(legacy)
    assert result.clarity_score == calculate_score(legacy)

    d = result.to_dict()
    assert set(d) == _V02_TO_DICT_KEYS | {
        "follow_ups",
        "detected_language",
        "heuristic_coverage",
        "degradation_note",
    }
    v02_shaped = AnalysisResult(
        status=result.status,
        clarity_score=result.clarity_score,
        detected_intent=result.detected_intent,
        gaps=result.gaps,
        recommendations=result.recommendations,
        findings=result.findings,
        interpretation_note=result.interpretation_note,
    )
    assert {k: d[k] for k in _V02_TO_DICT_KEYS} == {
        k: v02_shaped.to_dict()[k] for k in _V02_TO_DICT_KEYS
    }


# --- thread safety -------------------------------------------------------------


def test_parallel_analyze_follow_ups_stay_consistent():
    texts = [
        "build a REST API",
        "fix the login crash",
        "make this faster",
        "explain async",
        "add auth to my app",
    ]
    guard = InputGuard()
    sequential = [guard.analyze(t).to_dict() for t in texts]
    with ThreadPoolExecutor(max_workers=13) as pool:
        parallel = list(pool.map(lambda t: guard.analyze(t).to_dict(), texts * 13))
    for i in range(len(sequential)):
        expected = sequential[i]
        for j in range(i, len(parallel), len(sequential)):
            assert parallel[j] == expected
