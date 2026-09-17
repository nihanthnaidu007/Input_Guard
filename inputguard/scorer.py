from __future__ import annotations

from typing import Dict, List

from inputguard.types import RuleFinding


SEVERITY_PENALTIES = {"low": 5, "medium": 15, "high": 25}

_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2}

# Warning mode thresholds
_WARN_READY = 85
_WARN_USABLE = 60

# Strict mode thresholds
_STRICT_READY = 85
_STRICT_NEEDS = 65


def _severity_rank(severity: str) -> int:
    """Rank lookup that fails loudly: an unknown severity must never silently score zero."""
    try:
        return _SEVERITY_RANK[severity]
    except KeyError:
        raise ValueError(
            f"Unknown severity: {severity!r}. Expected one of: 'low', 'medium', 'high'."
        ) from None


def calculate_score(findings: List[RuleFinding]) -> int:
    """100 minus one penalty per distinct gap (or code, when gap is None), clamped to [0, 100].

    Unknown severities raise ``ValueError`` — a typo'd severity would
    otherwise distort every score silently (the v0.2 ``.get(severity, 0)``
    behavior).
    """
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
        score -= SEVERITY_PENALTIES[severity]

    return max(0, min(100, score))


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
