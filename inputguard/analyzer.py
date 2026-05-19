from __future__ import annotations

from typing import List

from inputguard.recommender import get_recommendations
from inputguard.rules.coding import run_coding_rules
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
        if domain != "coding":
            raise ValueError(
                f"Unsupported domain: {domain!r}. Phase 1 only supports 'coding'."
            )

        findings: List[RuleFinding] = run_coding_rules(user_input)
        score = calculate_score(findings)
        status = get_status(score, self.mode)

        gaps: List[str] = []
        seen = set()
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
            gaps=gaps,
            recommendations=recommendations,
            findings=findings,
            interpretation_note=interpretation_note,
        )
