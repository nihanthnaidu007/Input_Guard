"""Policy object tests: validation, filtering, severity vocabulary, and plumbing.

Covers the policy-object slice of the v0.3 spec (art_bTvdPdJS §2) plus the C5
closure from the adversarial API review (art_hC18m78C): one Policy-owned
severity vocabulary shared by registration and scoring. Byte-exact default
pinning lives in tests/test_policy_defaults.py.
"""

from __future__ import annotations

import dataclasses
from concurrent.futures import ThreadPoolExecutor

import pytest

from inputguard import InputGuard, Policy, RuleFinding
from inputguard.policy import SEVERITIES
from inputguard.registry import KNOWN_SEVERITIES, register_rule
from inputguard.scorer import require_known_severity
from test_registry import _test_rule  # noqa: F401 — shared rule builder
# registry_isolation resolves as a pytest fixture from tests/conftest.py.

# Observed v0.2 / release-branch behavior (runtime probes), reused as fixtures.
VAGUE_INPUT = "do something now"  # build intent, one high finding: insufficient_context
SINGLE_HIGH_INPUT = "build a REST API using Python"  # build intent, one high finding


# --- construction, coercion, and validation --------------------------------


def test_policy_is_frozen():
    policy = Policy()
    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.ready_at = 90  # type: ignore[misc]


def test_disabled_rules_coerced_to_frozenset_and_isolated():
    source = {"missing_language"}
    policy = Policy(disabled_rules=source)  # type: ignore[arg-type]
    assert isinstance(policy.disabled_rules, frozenset)
    source.add("missing_api_structure")  # mutating the source must not leak in
    assert policy.disabled_rules == frozenset({"missing_language"})


def test_allow_patterns_coerced_to_tuple_and_isolated():
    source = ["^re:"]
    policy = Policy(allow_patterns=source)  # type: ignore[arg-type]
    assert isinstance(policy.allow_patterns, tuple)
    source.append("x")
    assert policy.allow_patterns == ("^re:",)


def test_string_disabled_rules_rejected():
    # A bare string would silently become a set of characters.
    with pytest.raises(ValueError, match="collection of rule ids"):
        Policy(disabled_rules="missing_language")  # type: ignore[arg-type]


def test_string_allow_patterns_rejected():
    with pytest.raises(ValueError, match="collection of regex"):
        Policy(allow_patterns="^re:")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"usable_at": 70, "strict_clarify_at": 65}, "mis-ordered"),
        ({"strict_clarify_at": 90}, "mis-ordered"),
        ({"usable_at": 90}, "mis-ordered"),
        ({"ready_at": 101}, "ready_at"),
        ({"usable_at": -1}, "usable_at"),
        ({"borderline_at": 90, "ready_at": 85}, "borderline_at"),
        ({"borderline_at": 50}, "borderline_at"),
        ({"penalty_high": -1}, "penalty_high"),
        ({"penalty_low": 30}, "penalties are mis-ordered"),
        ({"penalty_medium": 30, "penalty_high": 25}, "penalties are mis-ordered"),
        ({"min_words": -1}, "min_words"),
        ({"max_chars": 0}, "max_chars"),
        ({"ready_at": "85"}, "must be an int"),
        ({"disabled_rules": {"no_such_rule_id"}}, "unknown rule ids"),
        ({"allow_patterns": ("(",)}, "not a valid regex"),
        ({"allow_patterns": (5,)}, "must be regex strings"),
        ({"disabled_rules": {5}}, "must be rule id strings"),
    ],
)
def test_invalid_policy_rejected_with_value_error(kwargs, match):
    with pytest.raises(ValueError, match=match):
        Policy(**kwargs)


def test_band_edges_are_valid():
    policy = Policy(usable_at=0, strict_clarify_at=0, ready_at=100, borderline_at=0)
    assert policy.ready_at == 100


def test_borderline_disabled_by_setting_equal_to_ready_at():
    policy = Policy(borderline_at=85)
    assert policy.borderline_at == policy.ready_at


def test_known_rule_ids_accepted_in_disabled_rules():
    policy = Policy(
        disabled_rules=frozenset({"missing_error_message", "missing_language"})
    )
    assert policy.disabled_rules == frozenset(
        {"missing_error_message", "missing_language"}
    )


# --- C5: one severity vocabulary, shared by registration and scoring --------


def test_registry_severity_vocabulary_cross_pins_to_policy():
    # The registration check (registry.KNOWN_SEVERITIES) and the scoring choke
    # point (policy.SEVERITIES) must never drift apart.
    assert KNOWN_SEVERITIES == SEVERITIES
    assert SEVERITIES == ("low", "medium", "high")


def test_require_known_severity_rejects_unknown():
    with pytest.raises(ValueError, match="Unknown severity: 'typo'"):
        require_known_severity("typo")


def test_rule_emitting_unknown_severity_fails_loudly_at_analyze(registry_isolation):
    # Declared severity is valid; the EMITTED finding's severity is not. The
    # analyzer choke point must reject it — the tie registration could not give us.
    bad = _test_rule(
        rule_id="bad_severity_rule",
        domain="debug",
        severity="high",
        gap="error description",
        finding=RuleFinding(code="bad_finding", message="m", severity="critical"),
    )
    register_rule(bad)
    with pytest.raises(ValueError, match="Unknown severity: 'critical'"):
        InputGuard().analyze("fix the bug in my app")


# --- disabled_rules filtering ------------------------------------------------


def test_disabled_rule_is_skipped_during_analyze():
    guard = InputGuard(
        policy=Policy(disabled_rules=frozenset({"missing_api_structure"}))
    )
    result = guard.analyze(SINGLE_HIGH_INPUT)
    assert result.findings == []  # the only finding this input produces
    assert result.clarity_score == 100
    assert result.status == "ready"


def test_disabled_rules_default_is_no_filtering():
    result = InputGuard().analyze(SINGLE_HIGH_INPUT)
    assert [f.code for f in result.findings] == ["missing_api_structure"]


def test_disabled_rules_apply_per_call_too():
    guard = InputGuard()
    result = guard.analyze(
        SINGLE_HIGH_INPUT,
        policy=Policy(disabled_rules=frozenset({"missing_api_structure"})),
    )
    assert result.findings == []


# --- allow_patterns filtering -------------------------------------------------


def test_allow_pattern_skips_flagging():
    guard = InputGuard(policy=Policy(allow_patterns=(r"\bfixture\b",)))
    result = guard.analyze("I love this fixture in the test suite, what does it do")
    assert result.status == "ready"
    assert result.clarity_score == 100
    assert result.findings == []
    assert result.gaps == []


def test_allow_pattern_no_match_leaves_analysis_unchanged():
    matched = InputGuard(policy=Policy(allow_patterns=("fix",))).analyze(
        "fix the bug in my app"
    )
    unmatched = InputGuard(policy=Policy(allow_patterns=("deploy",))).analyze(
        "fix the bug in my app"
    )
    assert matched.status == "ready"
    assert matched.findings == []
    assert unmatched.findings  # still analyzed
    assert unmatched.status != "ready"


# --- min_words: short input is valid-but-short, never "vague" -----------------


def test_min_words_below_floor_never_vague():
    result = InputGuard().analyze(VAGUE_INPUT)
    assert [f.code for f in result.findings] == ["insufficient_context"]
    assert result.clarity_score == 75

    raised = InputGuard(policy=Policy(min_words=10)).analyze(VAGUE_INPUT)
    assert raised.findings == []
    assert raised.clarity_score == 100
    assert raised.status == "ready"


def test_min_words_default_matches_explicit_default_policy():
    default_guard = InputGuard()
    pinned = InputGuard(policy=Policy())
    assert default_guard.analyze(VAGUE_INPUT).to_dict() == pinned.analyze(
        VAGUE_INPUT
    ).to_dict()


def test_min_words_above_floor_still_flags_long_vague_input():
    result = InputGuard(policy=Policy(min_words=4)).analyze("do something now please")
    assert [f.code for f in result.findings] == ["insufficient_context"]


# --- plumbing: guard attribute, per-call override, type errors ----------------


def test_guard_exposes_its_policy():
    policy = Policy(penalty_high=30)
    assert InputGuard(policy=policy).policy is policy
    assert InputGuard().policy == Policy()


def test_per_call_policy_overrides_guard_policy():
    guard = InputGuard(policy=Policy(min_words=10))
    assert guard.analyze(VAGUE_INPUT).findings == []  # guard policy applies
    allowed = guard.analyze(VAGUE_INPUT, policy=Policy())  # per-call override
    assert [f.code for f in allowed.findings] == ["insufficient_context"]


def test_constructor_rejects_non_policy():
    with pytest.raises(TypeError, match="Policy instance"):
        InputGuard(policy=Policy)  # class, not instance
    with pytest.raises(TypeError, match="Policy instance"):
        InputGuard(policy={"ready_at": 85})  # type: ignore[dict-item]


def test_analyze_rejects_non_policy():
    guard = InputGuard()
    with pytest.raises(TypeError, match="Policy instance"):
        guard.analyze(SINGLE_HIGH_INPUT, policy=85)  # type: ignore[arg-type]


# --- thread safety with a shared custom policy --------------------------------


def test_shared_policy_parallel_analyze_consistent():
    policy = Policy(disabled_rules=frozenset({"missing_debug_code_context"}))
    guard = InputGuard(policy=policy)
    text = "fix the bug in my app"
    expected = guard.analyze(text).to_dict()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: guard.analyze(text).to_dict(), range(64)))
    assert results == [expected] * 64
