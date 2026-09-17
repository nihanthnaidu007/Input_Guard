from __future__ import annotations

from typing import List, Set

import inputguard.rules  # noqa: F401 — importing registers the coding domain and the 19 built-in rules
from inputguard.detector import detect_intent, normalize
from inputguard.recommender import get_recommendations
from inputguard.registry import REGISTRY
from inputguard.scorer import calculate_score, get_status
from inputguard.types import AnalysisResult, RuleFinding


_VALID_MODES = {"warning", "strict"}
_INTERPRETATION_NOTE = (
    "This input is ambiguous in multiple ways. Addressing each gap below "
    "before sending will prevent the AI from making assumptions that lead "
    "to the wrong output."
)


class InputGuard:
    def __init__(self, mode: str = "warning") -> None:
        if mode not in _VALID_MODES:
            raise ValueError(
                f"Invalid mode: {mode!r}. Expected one of: 'warning', 'strict'."
            )
        self.mode = mode

    def analyze(self, user_input: str, domain: str = "coding") -> AnalysisResult:
        if not isinstance(user_input, str):
            raise TypeError(
                f"user_input must be a string, got {type(user_input).__name__}."
            )
        if not user_input.strip():
            raise ValueError("user_input must be a non-empty, non-whitespace string.")

        domain_signals = REGISTRY.get_domain_signals(domain)

        detected_intent = detect_intent(user_input, domain_signals)
        normalized = normalize(user_input)

        findings: List[RuleFinding] = []
        seen_codes: Set[str] = set()
        for rule in REGISTRY.rules_for_intent(detected_intent):
            finding = rule.check(normalized, detected_intent)
            if finding is None or finding.code in seen_codes:
                continue
            seen_codes.add(finding.code)
            findings.append(finding)

        score = calculate_score(findings)
        status = get_status(score, self.mode)

        gaps: List[str] = []
        seen: Set[str] = set()
        for f in findings:
            if f.gap is not None and f.gap not in seen:
                gaps.append(f.gap)
                seen.add(f.gap)

        recommendations = get_recommendations(gaps)

        high_count = sum(1 for f in findings if f.severity == "high")
        interpretation_note = None
        if score < 50 or high_count >= 2:
            interpretation_note = _INTERPRETATION_NOTE

        return AnalysisResult(
            status=status,
            clarity_score=score,
            detected_intent=detected_intent,
            gaps=gaps,
            recommendations=recommendations,
            findings=findings,
            interpretation_note=interpretation_note,
        )
