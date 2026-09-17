"""Score-breakdown tests: the additive audit trail on AnalysisResult.

Covers the breakdown slice of the v0.3 spec (art_bTvdPdJS §2/§5): base,
per-distinct-gap penalties (negative points), final — owned by the
policy-calibration PR. All expected values below were observed via runtime
probes against the release branch.
"""

from __future__ import annotations

import json

import pytest

from inputguard import InputGuard, Policy, RuleFinding
from inputguard.scorer import calculate_score, calculate_score_with_breakdown


def test_breakdown_shape_end_to_end():
    result = InputGuard().analyze("fix the bug in my app")
    assert result.clarity_score == 35
    assert result.score_breakdown == {
        "base": 100,
        "penalties": [
            {"code": "missing_error_message", "severity": "high", "points": -25},
            {
                "code": "missing_expected_vs_actual",
                "severity": "high",
                "points": -25,
            },
            {
                "code": "missing_debug_code_context",
                "severity": "medium",
                "points": -15,
            },
        ],
        "final": 35,
    }


def test_breakdown_final_matches_clarity_score():
    for text in ("build a REST API", "do something now", "fix the bug in my app"):
        result = InputGuard().analyze(text)
        assert result.score_breakdown is not None
        assert result.score_breakdown["final"] == result.clarity_score


def test_breakdown_dedupes_shared_gap():
    # missing_language and intent_without_language share gap
    # "programming language" — one penalty entry for that gap, first wins.
    result = InputGuard().analyze("I need to build an app")
    assert result.clarity_score == 60
    assert result.score_breakdown == {
        "base": 100,
        "penalties": [
            {"code": "missing_language", "severity": "high", "points": -25},
            {"code": "missing_output_format", "severity": "medium", "points": -15},
        ],
        "final": 60,
    }


def test_breakdown_penalty_order_matches_findings_order():
    result = InputGuard().analyze("fix the bug in my app")
    assert result.score_breakdown is not None
    # Every finding here has a distinct gap, so penalty order == findings order.
    assert [p["code"] for p in result.score_breakdown["penalties"]] == [
        f.code for f in result.findings
    ]


def test_breakdown_penalties_follow_policy_penalties():
    guard = InputGuard(policy=Policy(penalty_low=1, penalty_medium=3, penalty_high=10))
    result = guard.analyze("build a REST API")  # two high findings
    assert result.score_breakdown == {
        "base": 100,
        "penalties": [
            {"code": "missing_language", "severity": "high", "points": -10},
            {"code": "missing_api_structure", "severity": "high", "points": -10},
        ],
        "final": 80,
    }
    assert result.clarity_score == 80


def test_breakdown_clean_input_has_no_penalties():
    result = InputGuard().analyze(
        "Build a web app using React and FastAPI. "
        "It needs user authentication with JWT. "
        "Store tasks in a PostgreSQL database with title, description, and due date fields. "
        "Expose REST API endpoints: GET /tasks, POST /tasks, DELETE /tasks/{id}."
    )
    assert result.score_breakdown == {"base": 100, "penalties": [], "final": 100}


def test_breakdown_present_in_to_dict_and_json_serializable():
    d = InputGuard().analyze("build a REST API").to_dict()
    assert d["score_breakdown"]["final"] == 50
    assert json.dumps(d)  # must not raise


def test_to_dict_breakdown_is_a_copy():
    # The dict to_dict() returns must be detached from the result's own
    # breakdown object: mutating the result afterwards cannot rewrite history.
    result = InputGuard().analyze("build a REST API")
    snapshot = result.to_dict()
    assert result.score_breakdown is not None
    result.score_breakdown["penalties"][0]["points"] = 0  # type: ignore[index]
    assert snapshot["score_breakdown"]["penalties"][0]["points"] == -25
    assert result.to_dict()["score_breakdown"]["penalties"][0]["points"] == 0


def test_breakdown_clamps_at_zero():
    findings = [
        RuleFinding(code=f"c{i}", message="m", severity="high") for i in range(5)
    ]
    score, breakdown = calculate_score_with_breakdown(findings)
    assert score == 0
    assert breakdown["final"] == 0
    assert len(breakdown["penalties"]) == 5
    assert sum(p["points"] for p in breakdown["penalties"]) == -125


def test_breakdown_gap_none_dedupes_by_code():
    findings = [
        RuleFinding(code="a", message="m", severity="low"),
        RuleFinding(code="a", message="m", severity="high"),
    ]
    score, breakdown = calculate_score_with_breakdown(findings)
    assert score == 75
    assert breakdown["penalties"] == [
        {"code": "a", "severity": "high", "points": -25}
    ]


def test_calculate_score_keeps_v02_signature_and_matches_breakdown():
    findings = [RuleFinding(code="a", message="m", severity="medium", gap="g")]
    assert calculate_score(findings) == 85
    score, breakdown = calculate_score_with_breakdown(findings)
    assert score == 85
    assert breakdown["final"] == 85


def test_breakdown_unknown_severity_raises_before_scoring():
    findings = [RuleFinding(code="a", message="m", severity="typo")]
    with pytest.raises(ValueError, match="Unknown severity: 'typo'"):
        calculate_score_with_breakdown(findings)
