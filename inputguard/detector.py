from __future__ import annotations

import re


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


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _contains_any(text: str, terms) -> bool:
    return any(term in text for term in terms)


def detect_intent(text: str) -> str:
    """
    Detect the intent type of a coding input.

    Returns one of: "debug", "optimization", "explanation",
    "feature", "build".

    Priority order is strict: debug beats all, optimization beats
    explanation/feature/build, explanation beats feature/build,
    feature beats build. Build is the fallback.

    Ambiguous inputs always resolve to the highest-priority match.
    """
    normalized = _normalize(text)

    if _contains_any(normalized, DEBUG_SIGNALS):
        return "debug"
    if _contains_any(normalized, OPTIMIZATION_SIGNALS):
        return "optimization"
    if _contains_any(normalized, EXPLANATION_SIGNALS):
        return "explanation"
    if _contains_any(normalized, FEATURE_SIGNALS):
        return "feature"
    return "build"
