from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass(frozen=True)
class RuleFinding:
    code: str
    message: str
    severity: str
    gap: Optional[str] = None


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
        }

    def is_clear(self) -> bool:
        return self.status == "ready"
