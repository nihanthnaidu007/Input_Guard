from __future__ import annotations

import re
from typing import List, Optional

from inputguard.detector import OPTIMIZATION_SIGNALS
from inputguard.types import RuleFinding


OPTIMIZATION_TARGET_SIGNALS = {
    "this function", "this method", "this loop", "this query",
    "this endpoint", "this route", "this component", "this module",
    "the function", "the method", "the loop", "the query",
    "the endpoint", "loading", "rendering", "processing",
    "the database query", "the api call", "the request",
    "specifically", "in particular", "especially",
    "def ", "function ", "class ", "select ", "query",
}

PERFORMANCE_BASELINE_SIGNALS = {
    "takes", "taking", "seconds", "minutes", "milliseconds", "ms",
    "too slow", "very slow", "extremely slow", "noticeable",
    "measured", "profiled", "benchmark", "currently", "right now",
    "at the moment", "as it stands", "currently takes",
    "high memory", "high cpu", "maxing out", "hitting limits",
    "users are complaining", "timing out", "timeout",
}

OPTIMIZATION_CONSTRAINT_SIGNALS = {
    "without breaking", "maintain", "keep", "preserve",
    "backward compatible", "backwards compatible",
    "readability", "readable", "maintainable", "maintainability",
    "tradeoff", "trade-off", "trade off", "memory vs",
    "speed vs", "at the cost of", "acceptable", "constraint",
    "limitation", "requirement", "must still", "should still",
    "cannot change", "can't change", "don't break",
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _contains_any(text: str, terms) -> bool:
    return any(term in text for term in terms)


def check_missing_optimization_target(text: str) -> Optional[RuleFinding]:
    text = _normalize(text)
    if _contains_any(text, OPTIMIZATION_SIGNALS) and not _contains_any(text, OPTIMIZATION_TARGET_SIGNALS):
        return RuleFinding(
            code="missing_optimization_target",
            message="Optimization requested but no specific function, component, or area identified.",
            severity="high",
            gap="optimization target",
        )
    return None


def check_missing_performance_baseline(text: str) -> Optional[RuleFinding]:
    text = _normalize(text)
    if _contains_any(text, OPTIMIZATION_SIGNALS) and not _contains_any(text, PERFORMANCE_BASELINE_SIGNALS):
        return RuleFinding(
            code="missing_performance_baseline",
            message="No current performance measurement or observed problem described.",
            severity="medium",
            gap="performance baseline",
        )
    return None


def check_missing_optimization_constraint(text: str) -> Optional[RuleFinding]:
    text = _normalize(text)
    if _contains_any(text, OPTIMIZATION_SIGNALS) and not _contains_any(text, OPTIMIZATION_CONSTRAINT_SIGNALS):
        return RuleFinding(
            code="missing_optimization_constraint",
            message="No constraints or acceptable tradeoffs mentioned.",
            severity="low",
            gap="optimization constraint",
        )
    return None


def _dedupe(findings: List[RuleFinding]) -> List[RuleFinding]:
    seen = set()
    out = []
    for f in findings:
        if f.code not in seen:
            out.append(f)
            seen.add(f.code)
    return out


def run_optimization_rules(text: str) -> List[RuleFinding]:
    normalized = _normalize(text)
    findings = []
    for check in [
        check_missing_optimization_target,
        check_missing_performance_baseline,
        check_missing_optimization_constraint,
    ]:
        result = check(normalized)
        if result:
            findings.append(result)
    return _dedupe(findings)
