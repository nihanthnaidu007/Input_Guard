from __future__ import annotations

import re
from typing import List, Optional

from inputguard.detector import EXPLANATION_SIGNALS
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


def _contains_any(text: str, terms) -> bool:
    return any(term in text for term in terms)


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
