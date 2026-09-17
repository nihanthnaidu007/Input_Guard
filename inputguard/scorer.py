from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from inputguard.policy import Policy, SEVERITIES
from inputguard.types import RuleFinding


SEVERITY_PENALTIES = {"low": 5, "medium": 15, "high": 25}
"""The v0.2 default penalty table — now mirrored by :class:`~inputguard.Policy`'s
penalty defaults (cross-pinned by ``tests/test_policy_defaults.py``). Kept for
backward compatibility of the module surface."""

_SEVERITY_RANK = {name: rank for rank, name in enumerate(SEVERITIES)}


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
    score, _ = calculate_score_with_breakdown(findings, policy)
    return score


def calculate_score_with_breakdown(
    findings: List[RuleFinding], policy: Optional[Policy] = None
) -> Tuple[int, Dict[str, Any]]:
    """Score the findings and also return the additive audit breakdown.

    The breakdown is ``{"base": 100, "penalties": [...], "final": score}``
    where each penalty records ``{"code", "severity", "points"}`` (negative) —
    one entry per distinct gap (or code, when gap is None), in first-occurrence
    order. Ops teams use it to audit exactly which finding cost which points.
    Unknown severities raise ``ValueError`` before any scoring happens.
    """
    p = Policy() if policy is None else policy
    # Validate every severity before scoring so a bad finding fails loudly
    # even when a later finding would otherwise mask it in the dedup loop.
    for f in findings:
        _severity_rank(f.severity)

    highest_by_gap: Dict[str, RuleFinding] = {}
    for f in findings:
        key = f.gap if f.gap is not None else f.code
        current = highest_by_gap.get(key)
        if current is None or _severity_rank(f.severity) > _severity_rank(
            current.severity
        ):
            highest_by_gap[key] = f

    score = 100
    penalties: List[Dict[str, Any]] = []
    for f in highest_by_gap.values():
        points = _penalty_for(f.severity, p)
        penalties.append({"code": f.code, "severity": f.severity, "points": -points})
        score -= points

    final = max(0, min(100, score))
    return final, {"base": 100, "penalties": penalties, "final": final}


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


def get_status(score: int, mode: str, policy: Optional[Policy] = None) -> str:
    """Map a score to a status using the mode's policy bands.

    Bands come from ``policy`` (defaults reproduce the v0.2 constants
    byte-exactly): warning mode — ``ready`` at ``ready_at`` (85), then
    ``usable_with_warnings`` at ``usable_at`` (60); strict mode — ``ready``
    at ``ready_at`` (85), then ``needs_clarification`` at ``strict_clarify_at``
    (65), else ``blocked``. Two layers stay separate: severity decided what
    fired; these bands decide what happens.
    """
    p = Policy() if policy is None else policy
    if mode == "warning":
        if score >= p.ready_at:
            return "ready"
        if score >= p.usable_at:
            return "usable_with_warnings"
        return "needs_clarification"
    if mode == "strict":
        if score >= p.ready_at:
            return "ready"
        if score >= p.strict_clarify_at:
            return "needs_clarification"
        return "blocked"
    raise ValueError(f"Unknown mode: {mode!r}. Expected 'warning' or 'strict'.")
