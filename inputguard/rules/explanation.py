from __future__ import annotations

import re
from typing import Iterable, List, Optional

from inputguard.detector import EXPLANATION_SIGNALS
from inputguard.matching import contains_any
from inputguard.registry import register_rule
from inputguard.types import RuleFinding


CODE_REFERENCE_SIGNALS = {
    "this function", "this method", "this class",
    "this line", "this snippet", "this block", "this pattern",
    "this decorator", "this expression", "this syntax",
    "the function", "the method", "the class",
    "the following", "the above", "the below",
    "def ", "class ", "function ", "const ", "let ", "var ",
    "import ", "from ", "async ", "=>", "->", "::",
    "recursion", "closure", "decorator", "generator", "iterator",
    "async await", "promise", "callback", "middleware",
    "inheritance", "polymorphism", "abstraction", "encapsulation",
}

EXPLANATION_DEPTH_SIGNALS = {
    "briefly", "quickly", "overview", "high level", "high-level",
    "in simple terms", "simply", "basically", "eli5",
    "in detail", "in depth", "in-depth", "thoroughly", "deeply",
    "step by step", "step-by-step", "line by line", "line-by-line",
    "beginner", "beginner-friendly", "for a beginner", "advanced",
    "technical", "non-technical", "like i'm five", "like i am five",
    "example", "with an example", "with examples",
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    # v0.3: word-boundary matching via the shared matcher (probe P1 fix).
    return contains_any(text, terms)


def check_missing_code_reference(text: str) -> Optional[RuleFinding]:
    text = _normalize(text)
    if _contains_any(text, EXPLANATION_SIGNALS) and not _contains_any(text, CODE_REFERENCE_SIGNALS):
        return RuleFinding(
            code="missing_code_reference",
            message="Explanation requested but no specific code, function, or concept referenced.",
            severity="high",
            gap="code reference",
        )
    return None


def check_missing_explanation_depth(text: str) -> Optional[RuleFinding]:
    text = _normalize(text)
    if _contains_any(text, EXPLANATION_SIGNALS) and not _contains_any(text, EXPLANATION_DEPTH_SIGNALS):
        return RuleFinding(
            code="missing_explanation_depth",
            message="No indication of depth or detail level requested.",
            severity="low",
            gap="explanation depth",
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


def run_explanation_rules(text: str) -> List[RuleFinding]:
    normalized = _normalize(text)
    findings = []
    for check in [
        check_missing_code_reference,
        check_missing_explanation_depth,
    ]:
        result = check(normalized)
        if result:
            findings.append(result)
    return _dedupe(findings)


# Registry adapters: the v0.2 check functions above stay the single home of
# the rule logic; these classes expose it through the v0.3 Rule protocol and
# register it through the same path a user rule takes.


@register_rule
class MissingCodeReferenceRule:
    """Registry adapter for check_missing_code_reference."""

    id = "missing_code_reference"
    domain = "explanation"
    severity = "high"
    gap = "code reference"

    def check(self, text: str) -> Optional[RuleFinding]:
        return check_missing_code_reference(text)


@register_rule
class MissingExplanationDepthRule:
    """Registry adapter for check_missing_explanation_depth."""

    id = "missing_explanation_depth"
    domain = "explanation"
    severity = "low"
    gap = "explanation depth"

    def check(self, text: str) -> Optional[RuleFinding]:
        return check_missing_explanation_depth(text)


EXPLANATION_RULES = (
    MissingCodeReferenceRule,
    MissingExplanationDepthRule,
)
