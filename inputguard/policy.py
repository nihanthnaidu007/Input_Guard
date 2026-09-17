"""Policy: InputGuard calibration as data, not constants.

A :class:`Policy` bundles every tunable the ``analyze()`` pipeline consumes —
status bands, severity penalties, the input cap, rule filters, and the
borderline near-miss band — in one frozen, validated object. Every default is
the v0.2 constant, pinned byte-exactly by ``tests/test_policy_defaults.py`` so
existing behavior cannot drift.

Two layers stay separate: per-rule severity decides *what fires*; the policy's
bands decide *what happens* to the score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import FrozenSet, Optional, Tuple

__all__ = ["Policy"]


SEVERITIES: Tuple[str, ...] = ("low", "medium", "high")
"""The one severity vocabulary, owned here and shared by both validation sites
(review concern C5, art_hC18m78C): registration validates a rule's *declared*
severity against it (``registry.KNOWN_SEVERITIES``, cross-pinned by
``tests/test_policy.py``), and scoring validates every *emitted* finding's
severity against it (``scorer.require_known_severity``) — so the two checks
cannot drift apart. Deliberately not a ``Policy`` field: a per-instance
vocabulary would be silently ignored by the penalty lookup. Extend only
additively, with a matching ``penalty_*`` field."""


@dataclass(frozen=True)
class Policy:
    """Calibration for one :class:`~inputguard.InputGuard`.

    Every default is the v0.2 constant (pinned by ``tests/test_policy_defaults.py``).
    Instances are frozen, validated at construction, and safe to share across
    threads and guards.

    Fields
    ------
    ready_at:
        A score at or above this is ``ready`` in both modes.
    usable_at:
        Warning-mode floor for ``usable_with_warnings``.
    strict_clarify_at:
        Strict-mode floor for ``needs_clarification``; below it, strict blocks.
    penalty_low / penalty_medium / penalty_high:
        Points deducted per distinct gap, by the highest-severity finding in
        that gap. Must satisfy ``penalty_low <= penalty_medium <= penalty_high``.
    min_words:
        Inputs with fewer words are never flagged as vague by the built-in
        ``insufficient_context`` rule — short input is valid-but-short, not
        vague. That rule keeps a structural minimum of 3 words, so values
        below 3 cannot force shorter input to be flagged.
    max_chars:
        Input cap. ``analyze()`` inspects at most this many characters;
        truncation is reported on the result (``AnalysisResult.truncated``),
        never silent.
    borderline_at:
        Near-miss band: a score in ``[borderline_at, ready_at)`` sets the
        result's ``borderline`` signal — distinct "worth one more pass"
        messaging just below the ready floor. Set ``borderline_at`` equal to
        ``ready_at`` to disable the signal.
    disabled_rules:
        Rule ids to skip entirely during ``analyze()``. Every id must be a
        registered rule id (validated at construction).
    allow_patterns:
        Regex patterns; analyzed input matching any of them is never flagged —
        rules are skipped and the result is ``ready``. Patterns are matched
        against the analyzed (length-capped) input via ``re.search``.
    """

    ready_at: int = 85
    usable_at: int = 60
    strict_clarify_at: int = 65
    penalty_low: int = 5
    penalty_medium: int = 15
    penalty_high: int = 25
    min_words: int = 3
    max_chars: int = 10_000
    borderline_at: int = 74
    disabled_rules: FrozenSet[str] = frozenset()
    allow_patterns: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # A bare string would silently explode into characters under
        # frozenset()/tuple() — reject it before coercion.
        if isinstance(self.disabled_rules, str):
            raise ValueError(
                "Policy.disabled_rules must be a collection of rule ids, e.g. "
                f"frozenset({{'missing_language'}}), got the string {self.disabled_rules!r}."
            )
        if isinstance(self.allow_patterns, str):
            raise ValueError(
                "Policy.allow_patterns must be a collection of regex strings, "
                f"e.g. ('^re:',), got the string {self.allow_patterns!r}."
            )
        # Coerce to immutable containers so a later mutation of the caller's
        # set or list cannot change a "frozen" policy mid-flight.
        object.__setattr__(self, "disabled_rules", frozenset(self.disabled_rules))
        object.__setattr__(self, "allow_patterns", tuple(self.allow_patterns))
        _validate(self)


def _check_int(policy: Policy, name: str, *, minimum: int, maximum: Optional[int]) -> None:
    value = getattr(policy, name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Policy.{name} must be an int, got {value!r}.")
    if maximum is None:
        if value < minimum:
            raise ValueError(f"Policy.{name} must be >= {minimum}, got {value}.")
    elif not minimum <= value <= maximum:
        raise ValueError(f"Policy.{name} must be in [{minimum}, {maximum}], got {value}.")


def _validate(policy: Policy) -> None:
    for name in ("ready_at", "usable_at", "strict_clarify_at", "borderline_at"):
        _check_int(policy, name, minimum=0, maximum=100)
    if not policy.usable_at <= policy.strict_clarify_at < policy.ready_at:
        raise ValueError(
            "Policy bands are mis-ordered: they must satisfy "
            "usable_at <= strict_clarify_at < ready_at, got "
            f"usable_at={policy.usable_at}, strict_clarify_at={policy.strict_clarify_at}, "
            f"ready_at={policy.ready_at}."
        )
    if not policy.usable_at <= policy.borderline_at <= policy.ready_at:
        raise ValueError(
            "Policy.borderline_at must satisfy usable_at <= borderline_at <= ready_at, got "
            f"usable_at={policy.usable_at}, borderline_at={policy.borderline_at}, "
            f"ready_at={policy.ready_at}. Set borderline_at equal to ready_at to "
            "disable the borderline signal."
        )

    for name in ("penalty_low", "penalty_medium", "penalty_high"):
        _check_int(policy, name, minimum=0, maximum=None)
    if not policy.penalty_low <= policy.penalty_medium <= policy.penalty_high:
        raise ValueError(
            "Policy penalties are mis-ordered: they must satisfy "
            "penalty_low <= penalty_medium <= penalty_high, got "
            f"penalty_low={policy.penalty_low}, penalty_medium={policy.penalty_medium}, "
            f"penalty_high={policy.penalty_high}."
        )

    _check_int(policy, "min_words", minimum=0, maximum=None)
    _check_int(policy, "max_chars", minimum=1, maximum=None)

    for pattern in policy.allow_patterns:
        if not isinstance(pattern, str):
            raise ValueError(
                f"Policy.allow_patterns entries must be regex strings, got {pattern!r}."
            )
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(
                f"Policy.allow_patterns entry {pattern!r} is not a valid regex: {exc}"
            ) from exc

    for rule_id in policy.disabled_rules:
        if not isinstance(rule_id, str):
            raise ValueError(
                f"Policy.disabled_rules entries must be rule id strings, got {rule_id!r}."
            )

    if policy.disabled_rules:
        # Local import: the registry is populated as a side effect of importing
        # inputguard.rules, so the known-id check must run at construction time,
        # not module-import time (and registry imports nothing from this module).
        from inputguard.registry import REGISTRY

        registered = REGISTRY.rule_ids()
        unknown = sorted(set(policy.disabled_rules) - set(registered))
        if unknown:
            raise ValueError(
                "Policy.disabled_rules references unknown rule ids: "
                f"{', '.join(repr(r) for r in unknown)}. Registered rule ids: "
                f"{', '.join(repr(r) for r in registered)}."
            )
