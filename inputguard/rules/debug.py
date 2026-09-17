from __future__ import annotations

import re
from typing import Iterable, List, Optional

from inputguard.detector import DEBUG_SIGNALS
from inputguard.matching import contains_any
from inputguard.registry import register_rule
from inputguard.types import RuleFinding


ERROR_DESCRIPTION_SIGNALS = {
    "error message", "error:", "exception:", "traceback", "stack trace",
    "stacktrace", "says", "shows", "outputs", "prints", "returns",
    "it says", "it shows", "message is", "message:", "log says",
    "getting:", "throwing:", "raises:", "failed with",
    "typeerror", "valueerror", "keyerror", "attributeerror",
    "importerror", "nameerror", "indexerror", "syntaxerror",
    "runtimeerror", "nullpointerexception", "segfault",
}

BEHAVIOR_SIGNALS = {
    "should", "expected", "supposed to", "meant to", "instead",
    "but it", "however", "actually", "in reality", "what i want",
    "what i expect", "what i need", "correct behavior", "correct output",
    "right output", "instead of", "rather than", "not what",
    "wrong result", "wrong value", "incorrect",
}

CODE_CONTEXT_SIGNALS = {
    "function", "method", "class", "file", "module", "script",
    "line", "snippet", "code block", "the function", "my function",
    "this function", "this method", "this class", "the class",
    "this line", "on line", "at line", "this code", "the code",
    "python", "javascript", "typescript", "java", "react", "node",
    "django", "flask", "fastapi", "express", "ruby", "go", "rust",
    "def ", "function ", "class ", "const ", "let ", "var ",
    "import ", "from ", "async ", "await ",
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    # v0.3: word-boundary matching via the shared matcher (probe P1 fix).
    return contains_any(text, terms)


def check_missing_error_message(text: str) -> Optional[RuleFinding]:
    text = _normalize(text)
    if _contains_any(text, DEBUG_SIGNALS) and not _contains_any(text, ERROR_DESCRIPTION_SIGNALS):
        return RuleFinding(
            code="missing_error_message",
            message="Debug request detected but no error message or exception described.",
            severity="high",
            gap="error description",
        )
    return None


def check_missing_expected_vs_actual(text: str) -> Optional[RuleFinding]:
    text = _normalize(text)
    if _contains_any(text, DEBUG_SIGNALS) and not _contains_any(text, BEHAVIOR_SIGNALS):
        return RuleFinding(
            code="missing_expected_vs_actual",
            message="No description of expected vs actual behavior provided.",
            severity="high",
            gap="expected vs actual behavior",
        )
    return None


def check_missing_debug_code_context(text: str) -> Optional[RuleFinding]:
    text = _normalize(text)
    if _contains_any(text, DEBUG_SIGNALS) and not _contains_any(text, CODE_CONTEXT_SIGNALS):
        return RuleFinding(
            code="missing_debug_code_context",
            message="No code context provided — no language, function name, or snippet referenced.",
            severity="medium",
            gap="code context",
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


def run_debug_rules(text: str) -> List[RuleFinding]:
    normalized = _normalize(text)
    findings = []
    for check in [
        check_missing_error_message,
        check_missing_expected_vs_actual,
        check_missing_debug_code_context,
    ]:
        result = check(normalized)
        if result:
            findings.append(result)
    return _dedupe(findings)


# Registry adapters: the v0.2 check functions above stay the single home of
# the rule logic; these classes expose it through the v0.3 Rule protocol and
# register it through the same path a user rule takes.


@register_rule
class MissingErrorMessageRule:
    """Registry adapter for check_missing_error_message."""

    id = "missing_error_message"
    domain = "debug"
    severity = "high"
    gap = "error description"

    def check(self, text: str) -> Optional[RuleFinding]:
        return check_missing_error_message(text)


@register_rule
class MissingExpectedVsActualRule:
    """Registry adapter for check_missing_expected_vs_actual."""

    id = "missing_expected_vs_actual"
    domain = "debug"
    severity = "high"
    gap = "expected vs actual behavior"

    def check(self, text: str) -> Optional[RuleFinding]:
        return check_missing_expected_vs_actual(text)


@register_rule
class MissingDebugCodeContextRule:
    """Registry adapter for check_missing_debug_code_context."""

    id = "missing_debug_code_context"
    domain = "debug"
    severity = "medium"
    gap = "code context"

    def check(self, text: str) -> Optional[RuleFinding]:
        return check_missing_debug_code_context(text)


DEBUG_RULES = (
    MissingErrorMessageRule,
    MissingExpectedVsActualRule,
    MissingDebugCodeContextRule,
)
