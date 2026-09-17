from __future__ import annotations

import re
from typing import Iterable, List, Optional, Set

from inputguard.matching import contains_any
from inputguard.registry import register_rule
from inputguard.types import RuleFinding


# Verbs that create a new top-level artifact from scratch.
# Rule 1 (missing_language) AND Rule 6 (missing_output_format) fire on these.
BUILD_VERBS = {
    "build", "create", "make", "develop", "implement",
    "write", "generate", "code", "program", "set up",
    "setup", "spin up", "scaffold", "bootstrap",
}

# Verbs that add or connect something to an existing codebase.
# Rule 1 (missing_language) fires on these. Rule 6 does NOT.
ACTION_VERBS = {
    "integrate", "connect", "add", "wire up",
    "hook up", "link", "use",
}

# Combined set used by rules that apply to all coding actions.
CREATION_VERBS = BUILD_VERBS | ACTION_VERBS

LANGUAGES = {
    "python", "javascript", "typescript", "java", "c++", "c#", "go",
    "golang", "rust", "ruby", "php", "swift", "kotlin", "node", "nodejs",
    "react", "vue", "angular", "next", "nextjs", "nuxt", "svelte",
    "django", "flask", "fastapi", "express", "spring", "rails", "laravel",
    "dotnet", ".net", "dart", "flutter",
}

API_TERMS = {
    "api", "rest", "restful", "graphql", "grpc", "endpoint", "endpoints",
    "backend", "server", "microservice", "webhook",
}

API_STRUCTURE_INDICATORS = {
    "get", "post", "put", "delete", "patch", "route", "routes",
    "request", "response", "payload", "params", "query param",
    "status code", "json body", "/",
}

DATA_TERMS = {
    "database", "db", "store", "storage", "crud", "model", "schema",
    "table", "collection", "save", "persist", "record", "records",
    "data model", "entity", "entities",
}

DATA_FIELD_INDICATORS = {
    "field", "column", "attribute", "property", "id", "name", "email",
    "password", "title", "price", "date", "user", "users", "schema",
    "columns", "fields",
}

INTEGRATION_SERVICES = {
    "stripe", "paypal", "braintree", "twilio", "sendgrid", "mailgun",
    "aws", "s3", "lambda", "ec2", "firebase", "supabase", "mongodb",
    "redis", "openai", "anthropic", "slack", "discord", "github",
    "google", "oauth", "zapier", "webhook", "plaid", "shopify",
    "hubspot", "salesforce",
}

INTEGRATION_SPECIFICS = {
    "payment", "charge", "subscribe", "subscription", "invoice",
    "sms", "email notification", "upload", "download", "bucket",
    "stream", "event", "trigger", "message", "notify", "login with",
    "sign in with", "completion", "embedding",
}

AUTH_TERMS = {
    "auth", "authentication", "login", "sign in", "signin", "log in",
    "register", "signup", "sign up", "secure", "protected", "user account",
    "accounts", "password",
}

AUTH_TYPES = {
    "jwt", "oauth", "oauth2", "session", "cookie", "api key", "apikey",
    "token", "magic link", "otp", "2fa", "mfa", "basic auth", "bearer",
    "saml", "google login", "github login", "email and password",
    "username and password",
}

OUTPUT_FORMATS = {
    "web app", "website", "cli", "command line", "command-line", "terminal",
    "mobile app", "desktop app", "desktop application", "script",
    "library", "package", "plugin", "extension", "microservice",
    "lambda", "function", "bot", "chrome extension", "rest api",
    "graphql api", "dashboard", "admin panel",
}


# Detects build intent expressed without standard creation verbs.
# Catches phrases like "I need", "I want", "put together", "looking for".
_INTENT_PATTERN = re.compile(
    r"\b("
    r"i\s+(want|need|would like|am trying|'m trying|am looking|am building|'m building)|"
    r"looking for|trying to|hoping to|planning to|put together|"
    r"need\s+(a|an|to)|want\s+(a|an|to)|"
    r"lets\s+(users?|people|them|you|me)|that\s+lets\s+(users?|people|them|you|me)"
    r")\b",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    # v0.3: word-boundary matching via the shared matcher. token_fallback
    # keeps the v0.2 coding-rule behavior for multiword terms ("def ",
    # "sign in with"): their words may appear non-adjacent.
    return contains_any(text, terms, token_fallback=True)


def check_missing_language(text: str) -> Optional[RuleFinding]:
    text = _normalize(text)
    if _contains_any(text, CREATION_VERBS) and not _contains_any(text, LANGUAGES):
        return RuleFinding(
            code="missing_language",
            message="No programming language or framework detected.",
            severity="high",
            gap="programming language",
        )
    return None


def check_missing_api_structure(text: str) -> Optional[RuleFinding]:
    text = _normalize(text)
    if _contains_any(text, API_TERMS) and not _contains_any(text, API_STRUCTURE_INDICATORS):
        return RuleFinding(
            code="missing_api_structure",
            message="API mentioned but no structure, routes, or request/response shape defined.",
            severity="high",
            gap="api structure",
        )
    return None


def check_missing_data_model(text: str) -> Optional[RuleFinding]:
    text = _normalize(text)
    if _contains_any(text, DATA_TERMS) and not _contains_any(text, DATA_FIELD_INDICATORS):
        return RuleFinding(
            code="missing_data_model",
            message="Storage or database mentioned but no fields, entities, or model described.",
            severity="high",
            gap="data model",
        )
    return None


def check_missing_integration_specifics(text: str) -> Optional[RuleFinding]:
    text = _normalize(text)
    if _contains_any(text, INTEGRATION_SERVICES) and not _contains_any(text, INTEGRATION_SPECIFICS):
        return RuleFinding(
            code="missing_integration_specifics",
            message="Third-party service mentioned but no specific feature or action defined.",
            severity="medium",
            gap="integration specifics",
        )
    return None


def check_missing_auth_type(text: str) -> Optional[RuleFinding]:
    text = _normalize(text)
    if _contains_any(text, AUTH_TERMS) and not _contains_any(text, AUTH_TYPES):
        return RuleFinding(
            code="missing_auth_type",
            message="Authentication mentioned but no type specified.",
            severity="high",
            gap="authentication type",
        )
    return None


def check_missing_output_format(text: str) -> Optional[RuleFinding]:
    text = _normalize(text)
    if _contains_any(text, BUILD_VERBS) and not _contains_any(text, OUTPUT_FORMATS):
        return RuleFinding(
            code="missing_output_format",
            message="Build request detected but no output or delivery format specified.",
            severity="medium",
            gap="output format",
        )
    return None


def _check_intent_without_detail(text: str) -> Optional[RuleFinding]:
    """
    Detects build intent expressed through non-verb phrasing.
    Fires when the input matches the intent pattern but has no
    language specified. This catches inputs like:
      "I need a mobile app"
      "I want a login system"
      "put together a user dashboard"
    that bypass CREATION_VERBS entirely.
    """
    normalized = _normalize(text)
    if not _INTENT_PATTERN.search(normalized):
        return None
    if _contains_any(normalized, LANGUAGES):
        return None
    return RuleFinding(
        code="intent_without_language",
        message="Build intent detected but no programming language or technology specified.",
        severity="high",
        gap="programming language",
    )


def _check_insufficient_context(text: str, findings: List[RuleFinding]) -> Optional[RuleFinding]:
    """
    Safety net that fires when:
      - No other rules triggered (findings is empty)
      - The input is not a question
      - The input is at least 3 words long
      - The input has no specificity signal (a language, output format, route,
        field, auth type, or integration specific). Without that guard, the
        catch-all would also fire on fully specified inputs where every rule
        was correctly suppressed.
    """
    if findings:
        return None

    normalized = _normalize(text)
    words = normalized.split()

    if len(words) < 3:
        return None

    question_starters = {
        "what", "how", "why", "when", "where", "who", "which",
        "is", "are", "can", "does", "will", "would",
        "should", "could", "has", "have", "did", "was", "were",
    }
    if words[0] in question_starters or normalized.strip().endswith("?"):
        return None

    if (_contains_any(normalized, LANGUAGES)
            or _contains_any(normalized, OUTPUT_FORMATS)
            or _contains_any(normalized, API_STRUCTURE_INDICATORS)
            or _contains_any(normalized, DATA_FIELD_INDICATORS)
            or _contains_any(normalized, INTEGRATION_SPECIFICS)
            or _contains_any(normalized, AUTH_TYPES)):
        return None

    return RuleFinding(
        code="insufficient_context",
        message="Input does not contain enough detail to determine what needs to be built.",
        severity="high",
        gap="task context",
    )


_CHECKS = (
    check_missing_language,
    check_missing_api_structure,
    check_missing_data_model,
    check_missing_integration_specifics,
    check_missing_auth_type,
    check_missing_output_format,
)


def run_coding_rules(text: str) -> List[RuleFinding]:
    normalized = _normalize(text)
    findings: List[RuleFinding] = []
    seen_codes: Set[str] = set()

    for check in _CHECKS:
        result = check(normalized)
        if result is not None and result.code not in seen_codes:
            findings.append(result)
            seen_codes.add(result.code)

    intent_finding = _check_intent_without_detail(normalized)
    if intent_finding is not None and intent_finding.code not in seen_codes:
        findings.append(intent_finding)
        seen_codes.add(intent_finding.code)

    catchall = _check_insufficient_context(normalized, findings)
    if catchall is not None and catchall.code not in seen_codes:
        findings.append(catchall)
        seen_codes.add(catchall.code)

    return findings


# Registry adapters: the v0.2 check functions above stay the single home of
# the rule logic; these classes expose it through the v0.3 Rule protocol and
# register it through the same path a user rule takes.


@register_rule
class MissingLanguageRule:
    """Registry adapter for check_missing_language."""

    id = "missing_language"
    domain = "build"
    severity = "high"
    gap = "programming language"

    def check(self, text: str) -> Optional[RuleFinding]:
        return check_missing_language(text)


@register_rule
class MissingApiStructureRule:
    """Registry adapter for check_missing_api_structure."""

    id = "missing_api_structure"
    domain = "build"
    severity = "high"
    gap = "api structure"

    def check(self, text: str) -> Optional[RuleFinding]:
        return check_missing_api_structure(text)


@register_rule
class MissingDataModelRule:
    """Registry adapter for check_missing_data_model."""

    id = "missing_data_model"
    domain = "build"
    severity = "high"
    gap = "data model"

    def check(self, text: str) -> Optional[RuleFinding]:
        return check_missing_data_model(text)


@register_rule
class MissingIntegrationSpecificsRule:
    """Registry adapter for check_missing_integration_specifics."""

    id = "missing_integration_specifics"
    domain = "build"
    severity = "medium"
    gap = "integration specifics"

    def check(self, text: str) -> Optional[RuleFinding]:
        return check_missing_integration_specifics(text)


@register_rule
class MissingAuthTypeRule:
    """Registry adapter for check_missing_auth_type."""

    id = "missing_auth_type"
    domain = "build"
    severity = "high"
    gap = "authentication type"

    def check(self, text: str) -> Optional[RuleFinding]:
        return check_missing_auth_type(text)


@register_rule
class MissingOutputFormatRule:
    """Registry adapter for check_missing_output_format."""

    id = "missing_output_format"
    domain = "build"
    severity = "medium"
    gap = "output format"

    def check(self, text: str) -> Optional[RuleFinding]:
        return check_missing_output_format(text)


@register_rule
class IntentWithoutDetailRule:
    """Registry adapter for _check_intent_without_detail."""

    id = "intent_without_language"
    domain = "build"
    severity = "high"
    gap = "programming language"

    def check(self, text: str) -> Optional[RuleFinding]:
        return _check_intent_without_detail(text)


@register_rule
class InsufficientContextRule:
    """Catch-all safety net for build-intent input (registry adapter).

    v0.2's run_coding_rules passed this rule the findings collected so far and
    it fired only when that list was empty. A Rule sees only the normalized
    text, so the adapter re-runs the other built-in build rules — they are
    pure functions, so the verdict is identical. Findings from
    user-registered rules are not visible here: the catch-all suppresses on
    the built-in build rules only.
    """

    id = "insufficient_context"
    domain = "build"
    severity = "high"
    gap = "task context"

    def check(self, text: str) -> Optional[RuleFinding]:
        normalized = _normalize(text)
        seen_codes: Set[str] = set()
        prior: List[RuleFinding] = []
        for check_fn in _CHECKS:
            result = check_fn(normalized)
            if result is not None and result.code not in seen_codes:
                prior.append(result)
                seen_codes.add(result.code)
        intent_finding = _check_intent_without_detail(normalized)
        if intent_finding is not None and intent_finding.code not in seen_codes:
            prior.append(intent_finding)
            seen_codes.add(intent_finding.code)
        return _check_insufficient_context(normalized, prior)


CODING_RULES = (
    MissingLanguageRule,
    MissingApiStructureRule,
    MissingDataModelRule,
    MissingIntegrationSpecificsRule,
    MissingAuthTypeRule,
    MissingOutputFormatRule,
    IntentWithoutDetailRule,
    InsufficientContextRule,
)
