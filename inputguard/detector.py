from __future__ import annotations

import re

from typing import Iterable, Mapping, Optional, Tuple

from inputguard.matching import contains_any

DEBUG_SIGNALS = {
    "error", "exception", "traceback", "not working", "isn't working",
    "doesn't work", "won't work", "broken", "failing", "fails", "failed",
    "bug", "crash", "crashes", "crashing", "wrong output", "unexpected",
    "keeps throwing", "getting a", "throwing a", "raises", "raised",
    "stack trace", "it breaks", "breaks when", "fix", "debug",
    "why is this", "why does this", "what's wrong", "what is wrong",
    "can't get", "cannot get", "no longer works", "stopped working",
    "undefined", "null pointer", "type error", "attribute error",
    "import error", "syntax error", "runtime error", "value error",
    "key error", "index error",
}

OPTIMIZATION_SIGNALS = {
    "faster", "slower", "slow", "too slow", "performance", "optimize",
    "optimise", "optimizing", "optimising", "refactor", "refactoring",
    "clean up", "cleanup", "speed up", "speeding up", "bottleneck",
    "efficient", "efficiency", "memory", "memory usage", "cpu usage",
    "taking too long", "latency", "throughput", "benchmark", "profil",
    "reduce", "improve performance", "response time", "load time",
    "heavy", "bloated", "overly complex", "simplify", "restructure",
}

EXPLANATION_SIGNALS = {
    "explain", "explaining", "explanation", "understand", "understanding",
    "what does", "what do", "how does", "how do", "what is", "what are",
    "walk me through", "walk through", "help me understand", "clarify",
    "what's the difference", "difference between", "why does", "why do",
    "what's happening", "what is happening", "how it works", "how this works",
    "what this does", "what does this", "break down", "breakdown",
    "describe", "tell me about", "i don't understand", "confused about",
    "makes no sense", "doesn't make sense",
}

FEATURE_SIGNALS = {
    "add to my", "add to the", "add to our", "add it to",
    "extend my", "extend the", "extend our",
    "implement in my", "implement in the",
    "my existing", "my current", "existing app", "existing project",
    "existing codebase", "current codebase", "current app",
    "current project", "plug into", "hook into", "integrate into my",
    "on top of my", "on top of the", "into my existing",
    "to my app", "to my project", "to my codebase",
    "to the existing", "to our existing",
}


# The coding intent chain: priority-ordered (intent, terms) pairs. The single
# intent with empty terms ("build") is the fallback. This is the single source
# of truth for detection — the rule modules key their gates off the same sets,
# and the coding domain registers this chain in the rule registry.
INTENT_SIGNALS = (
    ("debug", DEBUG_SIGNALS),
    ("optimization", OPTIMIZATION_SIGNALS),
    ("explanation", EXPLANATION_SIGNALS),
    ("feature", FEATURE_SIGNALS),
    ("build", ()),
)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    # v0.3: word-boundary matching shared with the rule modules — "fixture"
    # is no longer read as the debug signal "fix" (probe P1).
    return contains_any(text, terms)


def detect_intent(
    text: str,
    signals: Optional[Iterable[Tuple[str, Iterable[str]]]] = None,
) -> str:
    """
    Detect the intent type of a coding input.

    Returns one of: "debug", "optimization", "explanation",
    "feature", "build".

    Priority order is strict: debug beats all, optimization beats
    explanation/feature/build, explanation beats feature/build,
    feature beats build. Build is the fallback.

    Ambiguous inputs always resolve to the highest-priority match.

    Pass ``signals`` to run the same chain over a domain's own
    priority-ordered ``(intent, terms)`` pairs — the single intent with
    empty terms is the fallback. Defaults to :data:`INTENT_SIGNALS`, the
    built-in coding chain.
    """
    normalized = normalize(text)

    chain = INTENT_SIGNALS if signals is None else tuple(
        signals.items() if isinstance(signals, Mapping) else signals
    )

    fallback: Optional[str] = None
    for intent, terms in chain:
        if not terms:
            fallback = intent
        elif _contains_any(normalized, terms):
            return intent

    if fallback is not None:
        return fallback
    raise ValueError(
        "detect_intent requires exactly one fallback intent (an entry with "
        "empty signal terms); none was provided."
    )
