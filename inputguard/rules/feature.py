from __future__ import annotations

import re
from typing import List, Optional

from inputguard.detector import FEATURE_SIGNALS
from inputguard.registry import register_rule
from inputguard.types import RuleFinding


EXISTING_STACK_SIGNALS = {
    "python", "javascript", "typescript", "java", "react", "node",
    "nodejs", "vue", "angular", "next", "nextjs", "django", "flask",
    "fastapi", "express", "rails", "laravel", "spring", "dotnet",
    "using", "built with", "written in", "in python", "in javascript",
    "with react", "with node", "postgres", "postgresql", "mysql",
    "mongodb", "sqlite", "redis", "rest api", "graphql",
}

FEATURE_SCOPE_SIGNALS = {
    "specifically", "in particular", "meaning", "which means",
    "that is", "that means", "so that", "in order to",
    "full text", "fuzzy", "exact match", "filter by", "sort by",
    "paginated", "pagination", "real-time", "real time", "live",
    "email notification", "push notification", "sms notification",
    "oauth", "jwt", "session", "api key", "role-based", "rbac",
    "upload", "download", "preview", "thumbnail",
    "dashboard", "chart", "graph", "table", "export",
    "search by", "filter by", "sort by", "group by",
}

COMPLETION_CRITERIA_SIGNALS = {
    "until", "when", "once", "after", "working means",
    "done means", "complete means", "finished means",
    "success looks like", "should be able to", "user can",
    "users can", "it should", "the feature should",
    "acceptance criteria", "definition of done",
    "tested", "test coverage", "end to end", "e2e",
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _contains_any(text: str, terms) -> bool:
    return any(term in text for term in terms)


def check_missing_existing_stack(text: str) -> Optional[RuleFinding]:
    text = _normalize(text)
    if _contains_any(text, FEATURE_SIGNALS) and not _contains_any(text, EXISTING_STACK_SIGNALS):
        return RuleFinding(
            code="missing_existing_stack",
            message="Feature addition requested but no existing language, framework, or tech stack mentioned.",
            severity="high",
            gap="existing stack",
        )
    return None


def check_missing_feature_scope(text: str) -> Optional[RuleFinding]:
    text = _normalize(text)
    if _contains_any(text, FEATURE_SIGNALS) and not _contains_any(text, FEATURE_SCOPE_SIGNALS):
        return RuleFinding(
            code="missing_feature_scope",
            message="Feature requested but no definition of what it should specifically do.",
            severity="high",
            gap="feature scope",
        )
    return None


def check_missing_completion_criteria(text: str) -> Optional[RuleFinding]:
    text = _normalize(text)
    if _contains_any(text, FEATURE_SIGNALS) and not _contains_any(text, COMPLETION_CRITERIA_SIGNALS):
        return RuleFinding(
            code="missing_completion_criteria",
            message="No definition of what done looks like for this feature.",
            severity="low",
            gap="completion criteria",
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


def run_feature_rules(text: str) -> List[RuleFinding]:
    normalized = _normalize(text)
    findings = []
    for check in [
        check_missing_existing_stack,
        check_missing_feature_scope,
        check_missing_completion_criteria,
    ]:
        result = check(normalized)
        if result:
            findings.append(result)
    return _dedupe(findings)


# Registry adapters: the v0.2 check functions above stay the single home of
# the rule logic; these classes expose it through the v0.3 Rule protocol and
# register it through the same path a user rule takes.


@register_rule
class MissingExistingStackRule:
    """Registry adapter for check_missing_existing_stack."""

    id = "missing_existing_stack"
    domain = "feature"
    severity = "high"
    gap = "existing stack"

    def check(self, text: str) -> Optional[RuleFinding]:
        return check_missing_existing_stack(text)


@register_rule
class MissingFeatureScopeRule:
    """Registry adapter for check_missing_feature_scope."""

    id = "missing_feature_scope"
    domain = "feature"
    severity = "high"
    gap = "feature scope"

    def check(self, text: str) -> Optional[RuleFinding]:
        return check_missing_feature_scope(text)


@register_rule
class MissingCompletionCriteriaRule:
    """Registry adapter for check_missing_completion_criteria."""

    id = "missing_completion_criteria"
    domain = "feature"
    severity = "low"
    gap = "completion criteria"

    def check(self, text: str) -> Optional[RuleFinding]:
        return check_missing_completion_criteria(text)


FEATURE_RULES = (
    MissingExistingStackRule,
    MissingFeatureScopeRule,
    MissingCompletionCriteriaRule,
)
