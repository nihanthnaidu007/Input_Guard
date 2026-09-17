from __future__ import annotations

from typing import Dict, List, Optional

from inputguard.policy import Policy, SEVERITIES
from inputguard.types import RuleFinding


SEVERITY_PENALTIES = {"low": 5, "medium": 15, "high": 25}
"""The v0.2 default penalty table — now mirrored by :class:`~inputguard.Policy`'s
penalty defaults (cross-pinned by ``tests/test_policy_defaults.py``). Kept for
backward compatibility of the module surface."""

_SEVERITY_RANK = {name: rank for rank, name in enumerate(SEVERITIES)}

# Warning mode thresholds
_WARN_READY = 85
_WARN_USABLE = 60

# Strict mode thresholds
_STRICT_READY = 85
_STRICT_NEEDS = 65


def require_known_severity(severity: str) -> None:
    """The single choke point validating a severity against ``Policy.SEVERITIES``.

    Two validations share this one vocabulary (review concern C5,
    art_hC18m78C): registration validates a rule's *declared* severity
    (``registry.KNOWN_SEVERITIES``, cross-pinned by ``tests/test_policy.py``),
    and the analyzer/scorer validate every *emitted* finding's severity here —
    so the two checks cannot drift apart.
    """
    if severity not in _SEVERITY_RANK:
        raise ValueError(
            f"Unknown severity: {severity!r}. Expected one of: "
            f"{', '.join(repr(s) for s in SEVERITIES)}."
        )


def _severity_rank(severity: str) -> int:
    """Rank lookup that fails loudly: an unknown severity must never silently score zero."""
    require_known_severity(severity)
    return _SEVERITY_RANK[severity]


def calculate_score(findings: List[RuleFinding], policy: Optional[Policy] = None) -> int:
    """100 minus one penalty per distinct gap (or code, when gap is None), clamped to [0, 100].

    Penalties come from ``policy`` (defaults reproduce the v0.2 constants
    byte-exactly). Unknown severities raise ``ValueError`` — a typo'd severity
    would otherwise distort every score silently (the v0.2 ``.get(severity, 0)``
    behavior).
    """
    p = Policy() if policy is None else policy
    # Validate every severity before scoring so a bad finding fails loudly
    # even when a later finding would otherwise mask it in the dedup loop.
    for f in findings:
        _severity_rank(f.severity)

    highest_by_gap: Dict[str, str] = {}
    for f in findings:
        key = f.gap if f.gap is not None else f.code
        current = highest_by_gap.get(key)
        if current is None or _severity_rank(f.severity) > _severity_rank(current):
            highest_by_gap[key] = f.severity

    score = 100
    for severity in highest_by_gap.values():
        score -= _penalty_for(severity, p)

    return max(0, min(100, score))


def _penalty_for(severity: str, policy: Policy) -> int:
    """Per-distinct-gap penalty for a severity already validated by ``_severity_rank``."""
    if severity == "low":
        return policy.penalty_low
    if severity == "medium":
        return policy.penalty_medium
    if severity == "high":
        return policy.penalty_high
    raise ValueError(
        f"Unknown severity: {severity!r}. Expected one of: 'low', 'medium', 'high'."
    )


def get_status(score: int, mode: str) -> str:
    if mode == "warning":
        if score >= _WARN_READY:
            return "ready"
        if score >= _WARN_USABLE:
            return "usable_with_warnings"
        return "needs_clarification"
    if mode == "strict":
        if score >= _STRICT_READY:
            return "ready"
        if score >= _STRICT_NEEDS:
            return "needs_clarification"
        return "blocked"
    raise ValueError(f"Unknown mode: {mode!r}. Expected 'warning' or 'strict'.")
