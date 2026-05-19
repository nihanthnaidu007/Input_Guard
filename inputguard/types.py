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
    gaps: List[str] = field(default_factory=list)
    recommendations: List[dict] = field(default_factory=list)
    findings: List[RuleFinding] = field(default_factory=list)
    interpretation_note: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "clarity_score": self.clarity_score,
            "gaps": list(self.gaps),
            "recommendations": [dict(r) for r in self.recommendations],
            "findings": [asdict(f) for f in self.findings],
            "interpretation_note": self.interpretation_note,
        }

    def is_clear(self) -> bool:
        return self.status == "ready"
