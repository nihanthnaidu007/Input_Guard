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


def calculate_score(findings: List[RuleFinding]) -> int:
    highest_by_gap: Dict[str, str] = {}
    for f in findings:
        key = f.gap if f.gap is not None else f.code
        current = highest_by_gap.get(key)
        if current is None or _SEVERITY_RANK.get(f.severity, 0) > _SEVERITY_RANK.get(current, 0):
            highest_by_gap[key] = f.severity

    score = 100
    for severity in highest_by_gap.values():
        score -= SEVERITY_PENALTIES.get(severity, 0)

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
