"""Registry contract-guard tests (adversarial review art_hC18m78C).

The three tests the review found missing, as a dedicated CI-enforced suite:

1. Duplicate rule ids within one ``register_domain`` call raise ``ValueError``
   (review C3/probe P2 — the high-severity second rule used to vanish
   silently) and nothing mutates on rejection.
2. A rule whose ``check`` signature cannot be called as ``check(self, text)``
   is rejected *at registration* with an actionable message (review B1/N3/
   probe P1 — a mismatched rule used to pass registration and detonate mid-
   ``analyze()`` with a ``TypeError`` on arbitrary user input).
3. A rule that raises inside ``check()`` surfaces as a ``RuntimeError``
   carrying the rule's id and registration origin, with the original
   exception chained (review C2/P4 — exceptions used to escape raw, with no
   attribution and no recovery path).

These complement the remediation tests in ``test_registry.py`` (which covers
the ``register_rule`` path); this module is the contract-guards gate the CI
matrix runs on every push, and also pins the ``register_domain`` road.
"""

from __future__ import annotations

import pytest

from inputguard import InputGuard, RuleFinding
from inputguard.registry import REGISTRY, register_domain, register_rule


# --- 1 · same-call duplicate rule ids raise, nothing mutates ----------------


class _ProbeRule:
    """Probe rule with a configurable id, firing on the word ``widget``."""

    domain = "probe thing"
    severity = "high"
    gap = "probe gap"

    def __init__(self, rule_id: str) -> None:
        self.id = rule_id

    def check(self, text: str):
        if "widget" in text:
            return RuleFinding(
                code=self.id,
                message="probe rule fired",
                severity=self.severity,
                gap=self.gap,
            )
        return None


_PROBE_SIGNALS = {"probe thing": ("widget",), "probe review": ()}


def test_same_call_duplicate_rule_ids_raise_and_mutate_nothing(registry_isolation):
    """Review C3: duplicate ids inside one register_domain call must raise.

    The original hole: the pre-check compared only against *already
    registered* rules, so a same-call duplicate was silently skipped in the
    mutation loop — the second rule disappeared without an error. The error
    must name the duplicated id, and a rejected batch must leave the registry
    untouched ("nothing mutates unless every check passes").
    """
    with pytest.raises(ValueError, match="register_domain call.*'dup_x'") as exc_info:
        register_domain(
            "probe_dup",
            _PROBE_SIGNALS,
            rules=[_ProbeRule("dup_x"), _ProbeRule("dup_x")],
        )

    # The message names the offending id so the author can fix it in one look.
    assert "dup_x" in str(exc_info.value)

    # No partial mutation: neither the domain nor either rule registered.
    assert "probe_dup" not in REGISTRY.domain_names()
    assert "dup_x" not in REGISTRY.rule_ids()

    # A corrected call through the same path works — the guard blocks
    # duplicates, not the batch API itself.
    register_domain("probe_dup_fixed", _PROBE_SIGNALS, rules=[_ProbeRule("solo_rule")])
    result = InputGuard().analyze("widget please", domain="probe_dup_fixed")
    assert "solo_rule" in [f.code for f in result.findings]


def test_duplicate_hidden_among_distinct_ids_raises(registry_isolation):
    """A duplicate buried in a batch of otherwise-distinct ids still raises,
    and the message names exactly the duplicated id."""
    with pytest.raises(ValueError, match="'twin_b'") as exc_info:
        register_domain(
            "probe_dup_mixed",
            _PROBE_SIGNALS,
            rules=[
                _ProbeRule("unique_a"),
                _ProbeRule("twin_b"),
                _ProbeRule("twin_b"),
                _ProbeRule("unique_c"),
            ],
        )
    # The distinct ids are not blamed.
    assert "unique_a" not in str(exc_info.value)
    assert "unique_c" not in str(exc_info.value)
    assert "probe_dup_mixed" not in REGISTRY.domain_names()
    assert "unique_a" not in REGISTRY.rule_ids()
    assert "twin_b" not in REGISTRY.rule_ids()


# --- 2 · wrong check() signature is a registration error --------------------


def test_extra_parameter_check_rejected_at_registration(registry_isolation):
    """Review B1: the retired check(self, text, intent) shape must be a
    registration error, not a mid-analyze TypeError. The message is
    actionable: it names the rule, the one-positional-argument dispatch, and
    the expected check(self, text) signature."""
    probe_signals = {"probe sig": ("gadget",), "probe sig review": ()}

    class ExtraArgRule:
        id = "probe_extra_arg"
        domain = "probe sig"
        severity = "low"
        gap = None

        def check(self, text, intent):  # noqa: ARG001 — the retired shape
            return None

    with pytest.raises(TypeError) as exc_info:
        register_domain("probe_sig", probe_signals, rules=[ExtraArgRule()])

    message = str(exc_info.value)
    assert "probe_extra_arg" in message
    assert "check(self, text)" in message
    assert "probe_extra_arg" not in REGISTRY.rule_ids()
    assert "probe_sig" not in REGISTRY.domain_names()


def test_zero_parameter_check_rejected_at_registration(registry_isolation):
    """check() with no parameters cannot bind the normalized text — reject at
    registration."""

    class NoArgRule:
        id = "probe_noarg"
        domain = "debug"
        severity = "low"
        gap = None

        def check(self):
            return None

    with pytest.raises(TypeError, match="probe_noarg") as exc_info:
        register_rule(NoArgRule())
    assert "check(self, text)" in str(exc_info.value)
    assert "probe_noarg" not in REGISTRY.rule_ids()


def test_keyword_only_check_rejected_at_registration(registry_isolation):
    """check(self, *, text) cannot be called positionally — the analyzer
    dispatches rule.check(normalized), so keyword-only rejects too."""

    class KeywordOnlyRule:
        id = "probe_kwonly"
        domain = "debug"
        severity = "low"
        gap = None

        def check(self, *, text):
            return None

    with pytest.raises(TypeError, match="probe_kwonly"):
        register_rule(KeywordOnlyRule())
    assert "probe_kwonly" not in REGISTRY.rule_ids()


def test_defaulted_check_is_accepted_and_fires(registry_isolation):
    """check(self, text="...") binds one positional argument, so it satisfies
    the dispatch contract — the gate rejects what cannot be called, not
    signatures it merely dislikes."""

    class DefaultedRule:
        id = "probe_defaulted"
        domain = "debug"
        severity = "low"
        gap = None

        def check(self, text=""):
            if "fix the bug" in text:
                return RuleFinding(
                    code=self.id,
                    message="Defaulted-signature rule fired.",
                    severity=self.severity,
                    gap=self.gap,
                )
            return None

    register_rule(DefaultedRule())
    result = InputGuard().analyze("fix the bug in my app")
    assert "probe_defaulted" in [f.code for f in result.findings]


def test_spec_signature_rule_is_accepted_and_fires(registry_isolation):
    """Positive control for the arity gate: check(self, text) — the pinned
    spec's signature (art_bTvdPdJS §1) — registers cleanly and the analyzer
    dispatches it. The gate rejects deviations, never the documented shape."""

    class SpecRule:
        id = "probe_spec_signature"
        domain = "debug"
        severity = "medium"
        gap = "error description"

        def check(self, text: str):
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
    assert "probe_spec_signature" in [f.code for f in result.findings]


# --- 3 · dispatch exceptions carry rule attribution --------------------------


def test_raising_rule_surfaces_id_origin_and_cause_via_register_domain(
    registry_isolation,
):
    """Review C2/P4: an exception inside check() aborts analyze() with the
    rule's id, its registration origin, and the original traceback chained.
    Tested through the register_domain path — test_registry.py covers the
    register_rule path — so both registration roads get the same loud
    attribution."""

    class ExplodingRule:
        id = "probe_boom_domain_rule"
        domain = "probe boom thing"
        severity = "high"
        gap = None

        def check(self, text: str):
            raise ZeroDivisionError("division by zero in probe rule")

    register_domain(
        "probe_boom",
        {"probe boom thing": ("widget",), "probe boom review": ()},
        rules=[ExplodingRule()],
    )

    with pytest.raises(RuntimeError) as exc_info:
        InputGuard().analyze("widget please", domain="probe_boom")

    message = str(exc_info.value)
    # Rule id, exception type, and registration origin all named.
    assert "probe_boom_domain_rule" in message
    assert "ZeroDivisionError" in message
    assert "registered at" in message
    # The original exception is chained, not swallowed.
    assert isinstance(exc_info.value.__cause__, ZeroDivisionError)
    assert "division by zero in probe rule" in str(exc_info.value.__cause__)
    # The origin names the file that registered the rule — this test module,
    # not inputguard internals (registration happened via register_domain
    # above, so the recorded call site is the register_domain line here).
    assert __file__ in message
