"""Per-gap templated clarifying questions — the v0.3 differentiator.

InputGuard already knows exactly what is missing from a prompt; this module
turns each gap finding into one or two clarifying questions the user can
answer verbatim. That converts "your input is vague" into "here is the
sentence to send next" — no adjacent tool generates structured follow-up
questions from gap findings (domain brief art_bzqrA3c7 §2).

Design, mirroring the recommender:

- ``_FOLLOW_UP_QUESTIONS`` is the gap -> questions table, one or two
  templates per built-in gap, in stable order.
- A template may reference a slot (``{function}``, ``{dataset}``); the slot
  is filled from the original input when something recognizable is there and
  the template is skipped otherwise. Every gap keeps at least one slot-free
  template, so a gap never yields zero questions.
- A gap with no table entry gets the documented fallback question — never
  silence (the same contract the recommendations fallback keeps).

The module is pure (table lookups plus regex over the input, no shared
mutation), so it preserves the thread-safe pipeline ``analyze()`` runs.
"""

from __future__ import annotations

import re
from typing import Dict, List, Mapping, Optional, Set, Tuple

__all__ = ["get_follow_ups"]


# One or two question templates per built-in gap, in stable order. Templates
# are phrased for the person typing the prompt; {function} / {dataset} slots
# are filled from the input when extractable. The spec-pinned examples
# ("Which function or module should get faster?", "How slow is it today, and
# what latency would be acceptable?") are kept byte-exact for the gaps the
# spec's example result shows them for.
_FOLLOW_UP_QUESTIONS: Dict[str, Tuple[str, ...]] = {
    "programming language": (
        "Which programming language or framework should this use?",
        "Where does it need to run — a web browser, a server, your terminal, or a phone?",
    ),
    "api structure": (
        "What actions should the API support — for example, list, create, or delete a resource?",
    ),
    "data model": (
        "Which fields does {dataset} contain, and which of them matter for this task?",
        "What data needs to be stored, and which fields matter for each item?",
    ),
    "integration specifics": (
        "Which specific feature of the integration do you need — for example, one-time payments, monthly subscriptions, or SMS notifications?",
    ),
    "authentication type": (
        "Which login method should it use — email and password, Google or GitHub sign-in, an API key, or a magic link?",
    ),
    "output format": (
        "What should this be when it's done — a web app, a command-line tool, a REST API, a script, or a mobile app?",
    ),
    "task context": (
        "What are you trying to build or accomplish, in a sentence or two?",
    ),
    "error description": (
        "What is the exact error message or exception you're seeing (copy it verbatim if you can)?",
    ),
    "expected vs actual behavior": (
        "What did you expect to happen, and what actually happens instead?",
    ),
    "code context": (
        "Where is {function} defined, and what does it currently do?",
        "Which file, function, or part of your code does the problem live in?",
    ),
    "optimization target": (
        "Which function or module should get faster?",
        "What makes {function} slow today, and how fast should it be?",
    ),
    "performance baseline": (
        "How slow is it today, and what latency would be acceptable?",
    ),
    "optimization constraint": (
        "What must not change while it gets faster — an interface, readability, behavior others depend on?",
    ),
    "code reference": (
        "Which function, class, or concept should the explanation focus on?",
    ),
    "explanation depth": (
        "How deep should the explanation go — a quick overview, step by step, or all the way down to internals?",
    ),
    "existing stack": (
        "What is your existing app built with — languages, frameworks, and database?",
    ),
    "feature scope": (
        "What exactly should the new feature do, from the user's point of view?",
    ),
    "completion criteria": (
        "What does 'done' look like — what should you be able to do when the feature works?",
    ),
    "audience": (
        "Who is going to read this — a manager, your team, clients, or the public?",
        "How familiar will readers be with the topic?",
    ),
    "purpose": (
        "What should this piece accomplish — inform, persuade, announce, or request something?",
    ),
    "structure/format": (
        "How long should it be, and how should it be organized — bullets, sections, or flowing prose?",
    ),
    "source material": (
        "Where is the text to work from — can you paste it or attach the file?",
        "Should I preserve its structure, or can I reorganize it freely?",
    ),
    "context": (
        "What is the topic or situation this piece should cover?",
    ),
    "completeness": (
        "Is there anything it must include — specific points, names, or numbers?",
        "Any hard limits, like a word count or a required section?",
    ),
}

# Slot names a template may reference. A template naming anything else is a
# table bug and raises at render time instead of silently never firing (the
# same loud-failure contract the scorer applies to unknown severities).
_KNOWN_SLOTS: Tuple[str, ...] = ("function", "dataset")

_SLOT_RE = re.compile(r"\{([a-z_]+)\}")

# A code call site: an identifier immediately followed by "(" — no space, so
# natural-language parentheticals ("fix this (urgently)") never match, while
# process_orders() and def process_orders( both do. Control-flow keywords are
# excluded; the first match in the input wins (deterministic).
_FUNCTION_RE = re.compile(r"(?<![\w])([A-Za-z_][A-Za-z0-9_]*)\(")
_FUNCTION_KEYWORDS = frozenset(
    {"if", "for", "while", "switch", "catch", "return", "elif", "else", "do", "try"}
)

# A named data file, or a dataset/table introduced with "called"/"named".
_DATASET_FILE_RE = re.compile(
    r"(?<![\w])([A-Za-z0-9_][A-Za-z0-9_.\-]*\.(?:csv|tsv|xls|xlsx|json|jsonl|parquet|sql|db|sqlite|dat))\b",
    re.IGNORECASE,
)
_DATASET_NAMED_RE = re.compile(
    r"\b(?:dataset|table)\s+(?:called|named)\s+([A-Za-z0-9_][A-Za-z0-9_.\-]*)",
    re.IGNORECASE,
)


def _extract_function(text: str) -> Optional[str]:
    for match in _FUNCTION_RE.finditer(text):
        name = match.group(1)
        if name not in _FUNCTION_KEYWORDS:
            return name
    return None


def _extract_dataset(text: str) -> Optional[str]:
    file_match = _DATASET_FILE_RE.search(text)
    if file_match is not None:
        return file_match.group(1)
    named_match = _DATASET_NAMED_RE.search(text)
    if named_match is not None:
        return named_match.group(1)
    return None


def _extract_slots(text: str) -> Dict[str, str]:
    """Pull fillable slots from the original input (case preserved)."""
    slots: Dict[str, str] = {}
    function_name = _extract_function(text)
    if function_name is not None:
        slots["function"] = function_name
    dataset_name = _extract_dataset(text)
    if dataset_name is not None:
        slots["dataset"] = dataset_name
    return slots


def _render(template: str, slots: Mapping[str, str]) -> Optional[str]:
    """Fill a template's slots, or return None when one is not fillable.

    A slot name outside ``_KNOWN_SLOTS`` is a table bug and raises instead of
    quietly producing a template that can never fire.
    """
    names = _SLOT_RE.findall(template)
    unknown = [name for name in names if name not in _KNOWN_SLOTS]
    if unknown:
        raise ValueError(
            f"Unknown follow-up slot(s) {unknown} in template {template!r}. "
            f"Known slots: {', '.join(_KNOWN_SLOTS)}."
        )
    if any(name not in slots for name in names):
        return None
    return template.format(**slots)


def _fallback_question(gap: str) -> str:
    """Generic question for a gap with no curated entry.

    The follow-up mirror of the recommendations fallback: a user-registered
    rule may declare a gap this table has never seen, and its findings still
    earn a question instead of silently empty advice.
    """
    return f"Can you add the {gap} this request is missing?"


def get_follow_ups(gaps: List[str], text: str) -> List[str]:
    """Build deduped clarifying questions for ``gaps``, in gap order.

    Each gap contributes its one or two templates, rendered against the
    slots extractable from ``text``; a question already produced by an
    earlier gap is dropped. A gap without a curated entry gets the
    documented fallback question.
    """
    slots = _extract_slots(text)
    out: List[str] = []
    seen: Set[str] = set()
    for gap in gaps:
        templates = _FOLLOW_UP_QUESTIONS.get(gap, (_fallback_question(gap),))
        for template in templates:
            rendered = _render(template, slots)
            if rendered is None or rendered in seen:
                continue
            seen.add(rendered)
            out.append(rendered)
    return out
