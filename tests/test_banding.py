"""Two-layer banding tests: policy-driven status bands and the borderline signal.

Covers the banding slice of the v0.3 spec (art_bTvdPdJS §2 and Result states):
severity decides what fires, Policy bands decide what happens. Byte-exact
default pinning lives in tests/test_policy_defaults.py.
"""

from __future__ import annotations

import dataclasses

import pytest

from inputguard import InputGuard, Policy
from inputguard.scorer import get_status

# Observed via runtime probe: "do something now" scores 75 (one high finding).
SINGLE_HIGH_INPUT = "do something now"


# --- default bands reproduce v0.2 warning mode -------------------------------


def test_default_warning_bands_byte_exact():
    assert get_status(100, "warning") == "ready"
    assert get_status(85, "warning") == "ready"
    assert get_status(84, "warning") == "usable_with_warnings"
    assert get_status(60, "warning") == "usable_with_warnings"
    assert get_status(59, "warning") == "needs_clarification"
    assert get_status(0, "warning") == "needs_clarification"


def test_default_strict_bands_byte_exact():
    assert get_status(100, "strict") == "ready"
    assert get_status(85, "strict") == "ready"
    assert get_status(84, "strict") == "needs_clarification"
    assert get_status(65, "strict") == "needs_clarification"
    assert get_status(64, "strict") == "blocked"
    assert get_status(0, "strict") == "blocked"


def test_default_policy_get_status_matches_no_policy():
    for mode in ("warning", "strict"):
        for score in (0, 59, 60, 64, 65, 74, 84, 85, 100):
            assert get_status(score, mode) == get_status(score, mode, Policy())


# --- bands are tunable data ---------------------------------------------------


def test_custom_bands_change_warning_mode():
    policy = Policy(ready_at=90, usable_at=40)
    assert get_status(85, "warning", policy) == "usable_with_warnings"
    assert get_status(90, "warning", policy) == "ready"
    assert get_status(39, "warning", policy) == "needs_clarification"


def test_custom_bands_change_strict_mode():
    policy = Policy(ready_at=95, strict_clarify_at=75)
    assert get_status(80, "strict", policy) == "needs_clarification"
    assert get_status(95, "strict", policy) == "ready"
    assert get_status(74, "strict", policy) == "blocked"


def test_relaxed_bands_never_block_in_warning_mode():
    # Warning mode never returns blocked for any score, whatever the bands.
    policy = Policy(usable_at=0, strict_clarify_at=0)
    for score in range(0, 101):
        assert get_status(score, "warning", policy) != "blocked"


# --- the borderline near-miss signal ------------------------------------------


def test_default_borderline_band_is_74_to_84():
    guard = InputGuard()
    result = guard.analyze(SINGLE_HIGH_INPUT)
    assert result.clarity_score == 75
    assert result.borderline is True
    assert result.status == "usable_with_warnings"


def test_scores_outside_the_band_are_not_borderline():
    guard = InputGuard()
    below = guard.analyze("fix the bug in my app")  # 35
    assert below.clarity_score == 35
    assert below.borderline is False
    clean = guard.analyze(
        "Build a web app using React and FastAPI. "
        "It needs user authentication with JWT. "
        "Store tasks in a PostgreSQL database with title, description, and due date fields. "
        "Expose REST API endpoints: GET /tasks, POST /tasks, DELETE /tasks/{id}."
    )  # 100
    assert clean.clarity_score == 100
    assert clean.borderline is False


def test_borderline_at_bounds():
    # Band floor inclusive: borderline_at == score -> borderline.
    assert (
        InputGuard(policy=Policy(borderline_at=75))
        .analyze(SINGLE_HIGH_INPUT)
        .borderline
        is True
    )
    # Disabled: borderline_at == ready_at means no score can be borderline.
    disabled = InputGuard(policy=Policy(borderline_at=85))
    result = disabled.analyze(SINGLE_HIGH_INPUT)
    assert result.borderline is False


def test_borderline_works_in_strict_mode_too():
    # Score 75 in strict mode is needs_clarification (65-84) and inside [74, 85).
    result = InputGuard(mode="strict").analyze(SINGLE_HIGH_INPUT)
    assert result.status == "needs_clarification"
    assert result.borderline is True


def test_borderline_field_is_additive_on_to_dict():
    result = InputGuard().analyze(SINGLE_HIGH_INPUT).to_dict()
    assert result["borderline"] is True
    # Every v0.2 key is still present.
    assert set(result).issuperset(
        {
            "status",
            "clarity_score",
            "detected_intent",
            "gaps",
            "recommendations",
            "findings",
            "interpretation_note",
        }
    )


def test_frozen_result_rejects_mutation():
    result = InputGuard().analyze(SINGLE_HIGH_INPUT)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.borderline = False  # type: ignore[misc]
