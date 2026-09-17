"""Registry contract tests for the v0.3 foundation.

Covers the acceptance points of the rule-registry PR: registration
validation (duplicate id, unknown severity, unknown domain), the
unknown-gap fallback, a custom rule changing a result end to end, a
registered custom domain, the registry-walking completeness invariant,
dispatch parity with the v0.2 runners, and thread-safe parallel
analyze() consistency.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from inputguard import InputGuard, RuleFinding
from inputguard.recommender import _RECOMMENDATIONS, get_recommendations
from inputguard.registry import REGISTRY, Rule, register_domain, register_rule
from inputguard.rules.coding import run_coding_rules
from inputguard.rules.debug import run_debug_rules
from inputguard.rules.explanation import run_explanation_rules
from inputguard.rules.feature import run_feature_rules
from inputguard.rules.optimization import run_optimization_rules
from inputguard.scorer import calculate_score

# The 31 built-in rule ids: the 19 coding rules documented in the README
# table plus the six first-party writing rules and the six first-party
# data-analysis rules (spec §7).
EXPECTED_BUILTIN_IDS = {
    "missing_language",
    "missing_api_structure",
    "missing_data_model",
    "missing_integration_specifics",
    "missing_auth_type",
    "missing_output_format",
    "intent_without_language",
    "insufficient_context",
    "missing_error_message",
    "missing_expected_vs_actual",
    "missing_debug_code_context",
    "missing_optimization_target",
    "missing_performance_baseline",
    "missing_optimization_constraint",
    "missing_code_reference",
    "missing_explanation_depth",
    "missing_existing_stack",
    "missing_feature_scope",
    "missing_completion_criteria",
    # First-party writing domain (6 rules).
    "missing_audience",
    "missing_purpose",
    "missing_structure_format",
    "missing_source_material",
    "missing_writing_context",
    "missing_completeness",
    # First-party data-analysis domain (6 rules, spec §7).
    "missing_dataset_source",
    "missing_question_goal",
    "missing_deliverable_format",
    "missing_tooling",
    "missing_volume",
    "missing_reproducibility",
}

_V02_INTENT_RUNNERS = {
    "build": run_coding_rules,
    "debug": run_debug_rules,
    "optimization": run_optimization_rules,
    "explanation": run_explanation_rules,
    "feature": run_feature_rules,
}


def _test_rule(rule_id="test_rule", domain="debug", severity="low", gap=None, finding=None):
    """Build an instance of a minimal rule class with configurable members."""

    class TestRule:
        pass

    TestRule.id = rule_id
    TestRule.domain = domain
    TestRule.severity = severity
    TestRule.gap = gap
    TestRule.check = lambda self, text: finding
    return TestRule()


@pytest.fixture
def registry_isolation():
    """Snapshot the registry around tests that mutate it."""
    rules_before = dict(REGISTRY._rules)
    domains_before = dict(REGISTRY._domains)
    origins_before = dict(REGISTRY._origins)
    yield REGISTRY
    REGISTRY._rules.clear()
    REGISTRY._rules.update(rules_before)
    REGISTRY._domains.clear()
    REGISTRY._domains.update(domains_before)
    REGISTRY._origins.clear()
    REGISTRY._origins.update(origins_before)


# --- the 31 built-ins dogfood the registry path ---------------------------


def test_all_builtin_rules_registered_through_registry():
    # 19 coding + 6 writing + 6 data-analysis built-ins. The exact-set guard
    # is the point: a rule that stops registering (or an unregistered stray)
    # fails here.
    assert len(REGISTRY.rule_ids()) == 31
    assert set(REGISTRY.rule_ids()) == EXPECTED_BUILTIN_IDS
    for rule in REGISTRY.rules():
        assert isinstance(rule, Rule)
        assert rule.severity in ("low", "medium", "high")


def test_coding_domain_registered_with_priority_signals():
    assert "coding" in REGISTRY.domain_names()
    chain = REGISTRY.get_domain_signals("coding")
    assert [intent for intent, _ in chain] == [
        "debug",
        "optimization",
        "explanation",
        "feature",
        "build",
    ]
    # The single fallback intent carries no terms.
    assert [terms for _, terms in chain if not terms] == [()]


def test_build_intent_rule_order_is_deterministic():
    ids = [r.id for r in REGISTRY.rules_for_intent("build")]
    assert ids == [
        "missing_language",
        "missing_api_structure",
        "missing_data_model",
        "missing_integration_specifics",
        "missing_auth_type",
        "missing_output_format",
        "intent_without_language",
        "insufficient_context",
    ]


# --- registration validation ----------------------------------------------


def test_duplicate_rule_id_raises_value_error(registry_isolation):
    with pytest.raises(ValueError, match="Duplicate rule id"):
        register_rule(_test_rule(rule_id="missing_error_message"))


def test_unknown_severity_raises_value_error_at_registration(registry_isolation):
    with pytest.raises(ValueError, match="unknown severity"):
        register_rule(_test_rule(severity="critical"))


def test_unknown_domain_raises_value_error_at_registration(registry_isolation):
    with pytest.raises(ValueError, match="domain"):
        register_rule(_test_rule(domain="nosuchintent"))


def test_register_rule_decorator_form(registry_isolation):
    @register_rule
    class AlwaysAskForDeadlineRule:
        id = "test_always_ask_deadline"
        domain = "debug"
        severity = "medium"
        gap = "deadline"

        def check(self, text):
            return RuleFinding(
                code=self.id,
                message="Test rule fired.",
                severity=self.severity,
                gap=self.gap,
            )

    registered = REGISTRY.get_rule("test_always_ask_deadline")
    assert registered is not None
    assert isinstance(registered, AlwaysAskForDeadlineRule)
    assert isinstance(registered, Rule)


# --- scorer / recommender loud failures ------------------------------------


def test_scorer_unknown_severity_raises_value_error():
    finding = RuleFinding(code="x", message="m", severity="catastrophic")
    with pytest.raises(ValueError, match="Unknown severity"):
        calculate_score([finding])


def test_scorer_unknown_severity_raises_even_alongside_known_severities():
    known = RuleFinding(code="y", message="m", severity="high")
    unknown = RuleFinding(code="x", message="m", severity="typo")
    with pytest.raises(ValueError, match="Unknown severity"):
        calculate_score([known, unknown])


def test_unknown_gap_gets_documented_fallback():
    recs = get_recommendations(["totally new gap"])
    assert len(recs) == 1
    entry = recs[0]
    assert set(entry) == {"gap", "what_is_missing", "what_to_provide", "why_it_matters"}
    assert entry["gap"] == "totally new gap"
    assert all(isinstance(v, str) and v for v in entry.values())


def test_unknown_gap_fallback_preserves_order_and_known_entries():
    recs = get_recommendations(["programming language", "totally new gap"])
    assert [r["gap"] for r in recs] == ["programming language", "totally new gap"]
    # The known gap still gets its curated entry (copied, not shared).
    assert recs[0]["why_it_matters"] == _RECOMMENDATIONS["programming language"]["why_it_matters"]


# --- custom rules and domains end to end -----------------------------------


def test_custom_rule_changes_result(registry_isolation):
    text = "fix the bug in my app"
    before = InputGuard().analyze(text)
    assert not any(f.code == "test_always_ask_deadline" for f in before.findings)

    finding = RuleFinding(
        code="test_always_ask_deadline",
        message="Test rule fired.",
        severity="medium",
        gap="deadline",
    )
    register_rule(_test_rule("test_always_ask_deadline", finding=finding))

    result = InputGuard().analyze(text)
    codes = [f.code for f in result.findings]
    assert "test_always_ask_deadline" in codes
    assert "deadline" in result.gaps
    assert result.clarity_score == before.clarity_score - 15
    deadline_rec = next(r for r in result.recommendations if r["gap"] == "deadline")
    assert all(str(v) for v in deadline_rec.values())


def test_custom_domain_analyzes_end_to_end(registry_isolation):
    register_domain(
        "testdom",
        {"thing": ("widget",), "fallback": ()},
        rules=[],
    )
    result = InputGuard().analyze("widget please", domain="testdom")
    assert result.detected_intent == "thing"
    assert result.findings == []
    assert result.clarity_score == 100
    assert result.status == "ready"


def test_duplicate_domain_registration_raises(registry_isolation):
    with pytest.raises(ValueError, match="Duplicate domain"):
        register_domain("coding", {"x": ("term",), "fallback": ()})


# --- completeness invariant -------------------------------------------------


def test_every_builtin_gap_has_recommendation_and_complete_entry():
    gaps = {rule.gap for rule in REGISTRY.rules() if rule.gap is not None}
    assert gaps, "built-in rules must declare gaps"
    for gap in gaps:
        assert gap in _RECOMMENDATIONS, f"gap {gap!r} has no recommendation entry"
        entry = _RECOMMENDATIONS[gap]
        assert set(entry) == {"gap", "what_is_missing", "what_to_provide", "why_it_matters"}
        assert all(isinstance(v, str) and v for v in entry.values())


# --- dispatch parity with the v0.2 runners ----------------------------------


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
        "Build a REST API using FastAPI. Store users in PostgreSQL with fields for name and email. Add email and password login.",
        "make me something good",
        "I need a mobile app",
        "fix the bug in my app",
        "the deploy fails with a TypeError: cannot read property of undefined, it should return the cached value instead",
        "make my database query faster",
        "explain recursion in this function",
        "add search to my app",
        "what does this code do",
    ],
)
def test_registry_dispatch_matches_v02_runner_output(text):
    result = InputGuard().analyze(text)
    legacy = _V02_INTENT_RUNNERS[result.detected_intent](text)
    assert [f.code for f in result.findings] == [f.code for f in legacy]
    assert result.gaps == _ordered_unique_gaps(legacy)
    assert result.clarity_score == calculate_score(legacy)


# --- thread safety -----------------------------------------------------------


def test_parallel_analyze_stays_consistent():
    guard = InputGuard()
    texts = [
        "fix the bug in my app",
        "make my database query faster",
        "what does this code do",
        "add search to my app",
        "Build a REST API using FastAPI. Store users in PostgreSQL. Add login.",
    ]
    sequential = [guard.analyze(t).to_dict() for t in texts]

    with ThreadPoolExecutor(max_workers=8) as pool:
        parallel = list(pool.map(lambda t: guard.analyze(t).to_dict(), texts * 13))

    assert len(parallel) == 65
    for offset in range(0, len(parallel), len(texts)):
        assert parallel[offset : offset + len(texts)] == sequential


# --- registry contract remediations (adversarial review art_hC18m78C) ------


def test_spec_compliant_check_text_rule_registers_and_fires(registry_isolation):
    """Review P1: a rule written per the pinned spec used to crash analyze()."""

    class SpecRule:
        id = "test_spec_signature_rule"
        domain = "debug"
        severity = "medium"
        gap = "deadline"

        def check(self, text):
            if "fix the bug" in text:
                return RuleFinding(
                    code=self.id,
                    message="Spec-signature rule fired.",
                    severity=self.severity,
                    gap=self.gap,
                )
            return None

    register_rule(SpecRule())
    result = InputGuard().analyze("fix the bug in my app")
    assert "test_spec_signature_rule" in [f.code for f in result.findings]


def test_wrong_arity_check_rejected_at_registration(registry_isolation):
    """Review N3: a wrong-signature rule is a registration error, not a
    mid-analyze TypeError. The retired foundation signature is the case."""

    class OldSignatureRule:
        id = "test_old_signature"
        domain = "debug"
        severity = "low"
        gap = None

        def check(self, text, intent):
            return None

    with pytest.raises(TypeError, match="test_old_signature"):
        register_rule(OldSignatureRule())
    assert "test_old_signature" not in REGISTRY.rule_ids()


def test_zero_argument_check_rejected_at_registration(registry_isolation):

    class NoArgRule:
        id = "test_noarg_check"
        domain = "debug"
        severity = "low"
        gap = None

        def check(self):
            return None

    with pytest.raises(TypeError, match="test_noarg_check"):
        register_rule(NoArgRule())
    assert "test_noarg_check" not in REGISTRY.rule_ids()


def test_intent_collision_across_domains_raises(registry_isolation):
    """Review B2/P6b: 'legal' reusing coding's 'debug' intent used to register
    silently and leak rules across domains. The error names both domains."""
    legal_signals = {"debug": ("lawsuit", "court filing"), "plead": ()}
    with pytest.raises(ValueError, match="globally unique") as exc_info:
        register_domain("legal", legal_signals)
    assert "legal" in str(exc_info.value)
    assert "coding" in str(exc_info.value)


def test_cross_domain_rule_leakage_is_now_impossible(registry_isolation):
    """Review P6b: a legal rule firing inside a coding analysis must not recur."""
    legal_signals = {"debug": ("lawsuit", "court filing"), "plead": ()}
    with pytest.raises(ValueError, match="globally unique"):
        register_domain("legal", legal_signals)

    result = InputGuard().analyze("fix the bug in my app")
    assert "legal_fires" not in [f.code for f in result.findings]
    assert "legal" not in REGISTRY.domain_names()


def test_duplicate_intent_within_one_domain_raises(registry_isolation):
    """Review N1 (registry half): one call cannot declare an intent twice."""
    duplicated = [("build", ("make",)), ("build", ()), ("review", ("check",))]
    with pytest.raises(ValueError, match="duplicate intent"):
        register_domain("testdupint", duplicated)


def test_same_call_duplicate_rule_ids_raise(registry_isolation):
    """Review C3/P2: duplicate ids in one register_domain call used to be
    silently dropped (the high-severity second rule vanished)."""

    class HighSeverity:
        severity = "high"
        gap = "probe gap"
        domain = "probe thing"

        def __init__(self, rule_id):
            self.id = rule_id

        def check(self, text):
            return None

    with pytest.raises(ValueError, match="register_domain call.*'dup_x'"):
        register_domain(
            "testdupdom",
            {"probe thing": ("widget",), "probe review": ()},
            rules=[HighSeverity("dup_x"), HighSeverity("dup_x")],
        )
    assert "testdupdom" not in REGISTRY.domain_names()


def test_rule_exception_gets_loud_attribution(registry_isolation):
    """Review C2-lite/P4: a rule exception aborts analyze() naming the rule
    and its registration origin, with the original exception chained."""
    register_domain("testboom", {"boom thing": ("widget",), "boom review": ()})

    class ExplodingRule:
        id = "test_exploding_rule"
        domain = "boom thing"
        severity = "low"
        gap = None

        def check(self, text):
            raise RuntimeError("boom from user rule")

    register_rule(ExplodingRule())
    with pytest.raises(RuntimeError, match="test_exploding_rule.*registered at") as exc_info:
        InputGuard().analyze("widget please", domain="testboom")
    assert "boom from user rule" in str(exc_info.value.__cause__)


def test_extension_api_exported_at_top_level():
    """Review C6: the extension API is importable from the package root."""
    import inputguard

    for name in ("register_rule", "register_domain", "REGISTRY", "Rule"):
        assert hasattr(inputguard, name)
        assert name in inputguard.__all__
    # the v0.2 compat surface is untouched and leads __all__
    assert inputguard.__all__[:4] == [
        "InputGuard",
        "AnalysisResult",
        "RuleFinding",
        "__version__",
    ]
