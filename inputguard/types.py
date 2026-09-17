from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class RuleFinding:
    code: str
    message: str
    severity: str
    gap: Optional[str] = None


def _copy_breakdown(breakdown: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Copy the breakdown so a result and its to_dict never share mutable state."""
    if breakdown is None:
        return None
    copied = dict(breakdown)
    copied["penalties"] = [dict(p) for p in breakdown["penalties"]]
    return copied


@dataclass(frozen=True)
class AnalysisResult:
    status: str
    clarity_score: int
    detected_intent: str
    gaps: List[str] = field(default_factory=list)
    recommendations: List[dict] = field(default_factory=list)
    findings: List[RuleFinding] = field(default_factory=list)
    interpretation_note: Optional[str] = None
    # v0.3, additive: templated clarifying questions, one or two per gap,
    # deduped and ordered with `gaps`. Appended after the v0.2 fields so any
    # positional construction keeps its meaning.
    follow_ups: List[str] = field(default_factory=list)
    # v0.3 multilingual degradation (additive, see inputguard/language.py):
    # the script probe's verdict. ``heuristic_coverage`` is "full", "partial",
    # "none", or "unknown"; a non-None ``degradation_note`` marks results the
    # rules could not fully assess.
    detected_language: str = "en"
    heuristic_coverage: str = "full"
    degradation_note: Optional[str] = None
    # v0.3 policy calibration (additive): near-miss signal — True when the
    # score lands in [policy.borderline_at, policy.ready_at), the "worth one
    # more pass" band just below ready.
    borderline: bool = False
    truncated: bool = False
    score_breakdown: Optional[Dict[str, Any]] = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "clarity_score": self.clarity_score,
            "detected_intent": self.detected_intent,
            "gaps": list(self.gaps),
            "recommendations": [dict(r) for r in self.recommendations],
            "follow_ups": list(self.follow_ups),
            "findings": [asdict(f) for f in self.findings],
            "interpretation_note": self.interpretation_note,
            "detected_language": self.detected_language,
            "heuristic_coverage": self.heuristic_coverage,
            "degradation_note": self.degradation_note,
            "borderline": self.borderline,
            "truncated": self.truncated,
            "score_breakdown": _copy_breakdown(self.score_breakdown),
        }

    def is_clear(self) -> bool:
        return self.status == "ready"
