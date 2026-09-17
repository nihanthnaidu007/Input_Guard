"""First-party writing domain rules.

The writing domain covers essays, emails, documents, and social posts.
Its gap vocabulary (pinned by the eval set's ``gap_vocabulary`` sheet) is
six gaps, one rule each:

============  ==========  ==========================
Gap           Severity    Rule
============  ==========  ==========================
audience      high        missing_audience
purpose       high        missing_purpose
structure/    medium      missing_structure_format
format
source        high        missing_source_material
material
context       medium      missing_writing_context
completeness  low         missing_completeness
============  ==========  ==========================

Rules follow the established trigger-and-satisfy shape: each fires only on
writing tasks and only when the gap's satisfier is absent from the prompt.

Design note — one intent, not many. The six gaps apply to any writing task
(drafting, rewriting, feedback), so the domain declares a single fallback
intent (``compose``) instead of fragmenting into sub-intents whose inputs
would silently skip the rules. The compose-vs-revise discrimination the
coding domains put in intent signals lives here inside the rules that need
it (``missing_source_material`` fires only when the task references
existing material).

All term matching goes through the shared word-boundary matcher
(``inputguard.matching``): ``"write"`` matches ``"writing"`` but not
``"written in Go"``, and ``"board"`` matches ``"the board"`` but not
``"keyboard"``. Phrase terms match adjacent words; the non-adjacent token
fallback is deliberately left off — these are new rules, so there is no
v0.2 verdict to preserve.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from inputguard.matching import contains_any
from inputguard.registry import register_rule
from inputguard.types import RuleFinding


# A writing task is present when the prompt names a writing artifact or a
# writing action. Every rule gates on this before looking at its own gap —
# it keeps coding prompts analyzed under domain="writing" (a user error)
# from producing misleading findings.
WRITING_TASK_TERMS = {
    "write", "draft", "compose",
    "blog", "post", "email", "memo", "letter", "essay", "resume",
    "proposal", "paragraph", "article", "recap", "summary", "summaries",
    "announcement", "press release", "cover letter", "outline",
    "linkedin", "newsletter", "bio", "story", "tweet", "thread",
    "note", "notes", "report", "document", "review",
    "rewrite", "revise", "reword", "rephrase", "proofread", "polish",
    "condense", "shorten", "tighten", "edit",
}

# The named readership that satisfies the audience gap. Reader nouns are
# matched anywhere in the text ("admissions officers are the readers" has
# no "for" prefix, and it must satisfy).
AUDIENCE_TERMS = {
    "audience", "readers", "reader", "readership",
    "beginners", "beginner", "newcomers",
    "manager", "managers", "my manager", "your manager", "my boss",
    "supervisor", "supervisors",
    "executives", "executive team", "leadership", "leadership team",
    "board", "board members", "steering committee", "committee",
    "stakeholders", "stakeholder",
    "clients", "client", "customers", "customer",
    "team", "my team", "engineering team", "engineers", "engineer",
    "developers", "developer",
    "journalists", "journalist", "press", "media",
    "recruiters", "recruiter", "hiring manager", "hiring managers",
    "admissions officers", "admissions", "officers",
    "students", "student", "teachers", "teacher", "professors",
    "professor", "instructors", "instructor",
    "investors", "investor", "shareholders", "shareholder",
    "subscribers", "subscriber", "followers", "follower",
    "colleagues", "colleague", "coworkers", "teammates", "peers",
    "donors", "donor", "members", "community",
    "applicants", "applicant", "candidates", "candidate",
    "reviewers", "reviewer", "editor", "editors",
    "users", "user base", "general public",
}

# A stated goal that satisfies the purpose gap ("announcing the Q3
# roadmap", "asking for budget", "so that nobody reruns the old pipeline").
PURPOSE_TERMS = {
    "to convince", "convince", "convincing", "persuade", "persuading",
    "persuasive",
    "announce", "announcing", "announced", "announcement",
    "request", "requesting", "requested",
    "ask for", "asking for", "asks for",
    "goal is", "goal of", "aim is", "aimed at", "purpose is",
    "objective is",
    "so that", "in order to",
    "recap",
    "lead with", "leads with",
    "explain", "explaining", "explains",
    "apologize", "apologizing", "apology",
    "thank", "thanking", "thanks",
    "celebrate", "celebrating", "celebration",
    "invite", "inviting", "invitation",
    "pitch", "pitching", "propose", "proposing",
    "inform", "informing", "update", "updating",
    "introduce", "introducing",
    "complain", "complaining", "complaint",
    "seeking", "seek", "justify", "justifying",
    "follow up", "follow-up", "following up",
    "respond", "responding", "reply",
    "remind", "reminding", "reminder",
    "promote", "promoting", "marketing",
}

# Length or organization guidance that satisfies the structure/format gap.
# Bare artifact types ("blog post") do not satisfy — the vocabulary is
# explicit about that — so "page" and "word" only match in count forms.
STRUCTURE_TERMS = {
    "bullet", "bullets", "bullet point", "bullet points",
    "sections", "section", "headings", "heading", "subheadings",
    "subheading", "numbered", "numbered list",
    "concise", "short", "shorter", "brief", "condensed",
    "length", "word count", "word limit", "page limit",
    "table format", "as a table", "in a table",
    "paragraph", "paragraphs",
}
# Count forms: "300 words", "one page", "two pages", "under 150 words",
# "3 bullets", "2 sections" — including hyphenated modifiers ("300-word").
_STRUCTURE_COUNT_PATTERNS = (
    r"\b\d+\s*[-\s]?\s*words?\b",
    r"\b(?:one|two|three|four|five|six|ten|single|half|\d+)\s*[-\s]?\s*pages?\b",
    r"\b\d+\s*[-\s]?\s*(?:paragraphs?|bullets?|sections?|slides?)\b",
)

# The task references existing material it wants worked on. Fires the
# source-material rule; the gap is then satisfied only if the material is
# actually provided.
MATERIAL_REFERENCE_TERMS = {
    "rewrite", "revise", "reword", "rephrase", "proofread", "polish",
    "improve", "condense", "shorten", "tighten", "trim", "expand",
    "fix up", "clean up", "restructure", "reorganize",
    "summarize", "summarise", "edit", "edited", "editing", "edits",
    "turn the", "turn my", "turn this",
    "my resume", "my essay", "my draft", "my outline", "my paragraph",
    "my summary", "my cover letter", "my letter", "my email", "my post",
    "my blog", "my notes", "my bio", "my article", "my proposal",
    "my story", "my memo", "my document", "my report",
    "this paragraph", "this essay", "this draft", "this outline",
    "this email", "this document", "this summary", "this post",
    "this blog", "this letter", "this resume", "this memo", "this note",
    "this report", "this article",
    "the essay", "the draft", "the outline", "the paragraph",
    "the notes", "the meeting notes", "the resume", "the cover letter",
    "the summary", "the document", "the manuscript",
    "the survey responses", "the bullet outline",
}
# The material is actually provided: pasted into the prompt, attached, or
# pointed at concretely.
MATERIAL_PROVIDED_TERMS = {
    "pasted", "attached", "below", "above", "at the bottom", "at the end",
    "copied", "the following", "as follows", "included", "quoted",
    "in the attachment", "in the document", "in the file", "the transcript",
}

# A named subject or situation that satisfies the context gap: explicit
# context markers, topic introducers, the artifact itself, or a concrete
# situation noun ("the migration", "the Q3 roadmap", "the vendor").
CONTEXT_TERMS = {
    "context", "background", "regarding", "about", "on the topic of",
    "subject:", "topic:", "re:",
    "blog", "post", "email", "memo", "letter", "essay", "resume",
    "proposal", "paragraph", "article", "recap", "summary",
    "announcement", "press release", "cover letter", "outline",
    "linkedin", "newsletter", "bio", "story", "tweet",
    "note", "notes", "report", "document", "draft", "review",
    "migration", "launch", "release", "deadline", "roadmap", "project",
    "initiative", "campaign", "rollout", "transition", "incident",
    "outage", "meeting", "event", "acquisition", "merger", "reorg",
    "vendor", "offsite", "layoff", "hiring", "product", "issue",
    "delay", "expansion", "funding", "series a", "restructure",
}

# Enumerated required content or constraints that satisfy the
# completeness gap ("must cover current costs", "mention the new ship
# date", "include the headline", "max 300 words"). Bare "cover" is
# deliberately absent — "cover letter" must not satisfy.
COMPLETENESS_TERMS = {
    "include", "including", "included", "includes",
    "must cover", "should cover", "needs to cover", "covering",
    "mention", "mentions", "mentioning", "mentioned",
    "highlight", "highlighting", "highlights",
    "emphasize", "emphasizing", "emphasise", "emphasising",
    "such as", "specifically", "namely", "in particular",
    "at least", "at minimum",
    "make sure", "be sure to", "don't forget", "do not forget",
    "required", "require", "requires", "requirements",
    "must have", "must-have", "needs to have", "needs to include",
    "max", "maximum", "at most", "no more than", "stay under",
    "within", "limit", "up to",
}


def _normalize(text: str) -> str:
    """Defensive re-normalization for direct callers of the check functions."""
    return re.sub(r"\s+", " ", text.strip().lower())


def check_missing_audience(text: str) -> Optional[RuleFinding]:
    text = _normalize(text)
    if not contains_any(text, WRITING_TASK_TERMS):
        return None
    if contains_any(text, AUDIENCE_TERMS):
        return None
    return RuleFinding(
        code="missing_audience",
        message="Writing task detected but no audience or reader is specified.",
        severity="high",
        gap="audience",
    )


def check_missing_purpose(text: str) -> Optional[RuleFinding]:
    text = _normalize(text)
    if not contains_any(text, WRITING_TASK_TERMS):
        return None
    if contains_any(text, PURPOSE_TERMS):
        return None
    return RuleFinding(
        code="missing_purpose",
        message="Writing task detected but the goal — what the piece should accomplish — is not stated.",
        severity="high",
        gap="purpose",
    )


def _has_structure_signal(text: str) -> bool:
    if contains_any(text, STRUCTURE_TERMS):
        return True
    return any(re.search(pattern, text) for pattern in _STRUCTURE_COUNT_PATTERNS)


def check_missing_structure_format(text: str) -> Optional[RuleFinding]:
    text = _normalize(text)
    if not contains_any(text, WRITING_TASK_TERMS):
        return None
    if _has_structure_signal(text):
        return None
    return RuleFinding(
        code="missing_structure_format",
        message="Writing task detected but no length or organization guidance is provided.",
        severity="medium",
        gap="structure/format",
    )


def check_missing_source_material(text: str) -> Optional[RuleFinding]:
    text = _normalize(text)
    if not contains_any(text, WRITING_TASK_TERMS):
        return None
    if not contains_any(text, MATERIAL_REFERENCE_TERMS):
        return None
    if contains_any(text, MATERIAL_PROVIDED_TERMS):
        return None
    return RuleFinding(
        code="missing_source_material",
        message="Existing material is referenced but not provided — paste or attach the text to work from.",
        severity="high",
        gap="source material",
    )


def check_missing_writing_context(text: str) -> Optional[RuleFinding]:
    text = _normalize(text)
    if not contains_any(text, WRITING_TASK_TERMS):
        return None
    if contains_any(text, CONTEXT_TERMS):
        return None
    return RuleFinding(
        code="missing_writing_context",
        message="Writing task detected but the subject or situation is not named.",
        severity="medium",
        gap="context",
    )


def check_missing_completeness(text: str) -> Optional[RuleFinding]:
    text = _normalize(text)
    if not contains_any(text, WRITING_TASK_TERMS):
        return None
    if contains_any(text, COMPLETENESS_TERMS):
        return None
    return RuleFinding(
        code="missing_completeness",
        message="Writing task detected but no required content or constraints are specified.",
        severity="low",
        gap="completeness",
    )


# Registry adapters: the check functions above stay the single home of the
# rule logic; these classes expose it through the v0.3 Rule protocol and
# register it through the same path a user rule takes.


@register_rule
class MissingAudienceRule:
    """Registry adapter for check_missing_audience."""

    id = "missing_audience"
    domain = "compose"
    severity = "high"
    gap = "audience"

    def check(self, text: str) -> Optional[RuleFinding]:
        return check_missing_audience(text)


@register_rule
class MissingPurposeRule:
    """Registry adapter for check_missing_purpose."""

    id = "missing_purpose"
    domain = "compose"
    severity = "high"
    gap = "purpose"

    def check(self, text: str) -> Optional[RuleFinding]:
        return check_missing_purpose(text)


@register_rule
class MissingStructureFormatRule:
    """Registry adapter for check_missing_structure_format."""

    id = "missing_structure_format"
    domain = "compose"
    severity = "medium"
    gap = "structure/format"

    def check(self, text: str) -> Optional[RuleFinding]:
        return check_missing_structure_format(text)


@register_rule
class MissingSourceMaterialRule:
    """Registry adapter for check_missing_source_material."""

    id = "missing_source_material"
    domain = "compose"
    severity = "high"
    gap = "source material"

    def check(self, text: str) -> Optional[RuleFinding]:
        return check_missing_source_material(text)


@register_rule
class MissingWritingContextRule:
    """Registry adapter for check_missing_writing_context."""

    id = "missing_writing_context"
    domain = "compose"
    severity = "medium"
    gap = "context"

    def check(self, text: str) -> Optional[RuleFinding]:
        return check_missing_writing_context(text)


@register_rule
class MissingCompletenessRule:
    """Registry adapter for check_missing_completeness."""

    id = "missing_completeness"
    domain = "compose"
    severity = "low"
    gap = "completeness"

    def check(self, text: str) -> Optional[RuleFinding]:
        return check_missing_completeness(text)


WRITING_RULES: Tuple[type, ...] = (
    MissingAudienceRule,
    MissingPurposeRule,
    MissingStructureFormatRule,
    MissingSourceMaterialRule,
    MissingWritingContextRule,
    MissingCompletenessRule,
)

# The single fallback intent: every writing-domain input is a composition
# task. Exactly one empty-terms intent is what the registry requires.
WRITING_SIGNALS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("compose", ()),
)

# Findings this domain can emit, for the completeness invariant.
WRITING_GAPS: Tuple[str, ...] = (
    "audience",
    "purpose",
    "structure/format",
    "source material",
    "context",
    "completeness",
)


def run_writing_rules(text: str) -> List[RuleFinding]:
    """Run every writing rule directly (mirror of the coding run_* helpers)."""
    findings: List[RuleFinding] = []
    seen = set()
    for check in (
        check_missing_audience,
        check_missing_purpose,
        check_missing_structure_format,
        check_missing_source_material,
        check_missing_writing_context,
        check_missing_completeness,
    ):
        result = check(text)
        if result and result.code not in seen:
            findings.append(result)
            seen.add(result.code)
    return findings
