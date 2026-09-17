"""Byte-exact pinning of every Policy default against the v0.2 constants.

The v0.2 constants are load-bearing for existing users (spec art_bTvdPdJS,
"Calibration drift" risk): these tests fail if any default drifts. Sources:
SEVERITY_PENALTIES and the four threshold constants in the v0.2 scorer, and
the three-word structural floor of the insufficient_context rule.
"""

from __future__ import annotations

import dataclasses
import inspect
import re

import pytest

from inputguard import InputGuard, Policy

V02_THRESHOLD_CONSTANTS = {
    "ready_at": 85,  # warning and strict ready floor
    "usable_at": 60,  # warning-mode band floor
    "strict_clarify_at": 65,  # strict-mode needs_clarification floor
    "penalty_low": 5,
    "penalty_medium": 15,
    "penalty_high": 25,
    "min_words": 3,  # insufficient_context structural floor
    "max_chars": 10_000,  # v0.3 default cap (v0.2 had none)
    "borderline_at": 74,  # near-miss band just below ready
}


def test_every_policy_default_is_pinned():
    fields = {f.name: f.default for f in dataclasses.fields(Policy)}
    for name, value in V02_THRESHOLD_CONSTANTS.items():
        assert fields[name] == value, f"Policy.{name} drifted from v0.2 ({value})"


def test_no_unpinned_numeric_fields():
    # Every int field must appear in the pin table so future fields cannot
    # ship uncalibrated.
    int_fields = {
        f.name
        for f in dataclasses.fields(Policy)
        if f.type in ("int",) or getattr(f.type, "__name__", "") == "int"
    }
    assert int_fields == set(V02_THRESHOLD_CONSTANTS)


def test_dataclass_defaults_are_the_source_of_truth():
    # Constructing with zero arguments must equal the pinned table — no
    # hidden overrides inside __post_init__.
    policy = Policy()
    for name, value in V02_THRESHOLD_CONSTANTS.items():
        assert getattr(policy, name) == value


def test_defaults_are_frozen():
    policy = Policy()
    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.ready_at = 90  # type: ignore[misc]


def test_source_defaults_match_the_pinned_table():
    # Guard against the dataclass defaults themselves drifting (the pinning
    # tests above read instantiated values; this reads the source). Underscore
    # digit separators are normalized before comparison.
    source = inspect.getsource(Policy)
    for name, value in V02_THRESHOLD_CONSTANTS.items():
        match = re.search(rf"^\s*{name}: int = ([0-9_]+),?\s*$", source, re.MULTILINE)
        assert match is not None, f"source default for {name} missing or reformatted"
        assert int(match.group(1).replace("_", "")) == value


# --- behavioral pins: v0.2 reference outputs under default policy --------------


def _result(text, **kwargs):
    return InputGuard(**kwargs).analyze(text).to_dict()


def test_reference_outputs_unchanged_warning_mode():
    # Scores observed via runtime probes on the release branch.
    assert _result("do something now")["clarity_score"] == 75
    assert _result("do something now")["status"] == "usable_with_warnings"
    assert _result("fix the bug in my app")["clarity_score"] == 35
    assert _result("fix the bug in my app")["status"] == "needs_clarification"
    assert _result("build a REST API")["clarity_score"] == 50


def test_reference_outputs_unchanged_strict_mode():
    # 50 < 65 strict floor -> blocked; 75 in [65, 85) -> needs_clarification.
    assert _result("build a REST API", mode="strict")["status"] == "blocked"
    assert _result("do something now", mode="strict")["status"] == "needs_clarification"


def test_default_result_keys_are_a_superset_of_v02():
    result = _result("build a REST API")
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


def test_v02_recommendation_keys_unchanged():
    recs = _result("build a REST API")["recommendations"]
    assert recs, "expected at least one recommendation"
    for rec in recs:
        assert set(rec) == {
            "gap",
            "what_is_missing",
            "what_to_provide",
            "why_it_matters",
        }
