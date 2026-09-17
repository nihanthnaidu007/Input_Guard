"""Language probe: stdlib-only script detection for honest degradation.

Every clarity rule in InputGuard is an English-keyword heuristic. On input in
another script (Chinese, Cyrillic, Arabic, ...) none of those keywords match,
so v0.2 silently returned ``ready`` at score 100 for input it had not assessed
at all — the tool asserted a confidence it did not have.

This module is the v0.3 fix (spec: "Honest degradation for non-English
input"): a pure script histogram built exclusively on :mod:`unicodedata` —
no langdetect, no fastText, no network, honoring the zero-dependency
constraint. Each letter's Unicode *name* mentions its script (``"CJK
UNIFIED IDEOGRAPH-..."``, ``"CYRILLIC SMALL LETTER BE"``, ...), so scanning
name tokens classifies scripts with no hardcoded range tables to rot.

When the dominant script has no heuristic coverage, ``analyze()`` takes the
explicit degraded path: English-only rules are skipped, a confidence penalty
is applied, and the result carries a ``degradation_note`` — never a silent
``ready``. Scripts with coverage (Latin) behave exactly as they did before
the probe existed.

The probe is pure and thread-safe: no module-level mutation, only stdlib
lookups, matching the ``analyze()`` thread-safety contract.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, Optional

__all__ = [
    "COVERAGE_FULL",
    "COVERAGE_NONE",
    "COVERAGE_PARTIAL",
    "COVERAGE_UNKNOWN",
    "COVERED_SCRIPTS",
    "DEGRADATION_PENALTY",
    "DEGRADED_INTENT",
    "ScriptProbe",
    "degradation_note_for",
    "partial_coverage_note",
    "probe_script",
]

# Scripts the English keyword heuristics can actually assess. Every rule fires
# on English terms, so Latin script is the only fully covered script today.
COVERED_SCRIPTS = frozenset({"latin"})

# Coverage vocabulary for ``AnalysisResult.heuristic_coverage``:
# - "full":    >= 70% of classified letters are in covered scripts; rules run
#              exactly as before, no note.
# - "partial": 50-70% covered; rules run (the covered majority still drives
#              detection), a note flags the uncovered remainder, no penalty.
# - "none":    < 50% covered; degraded path — rules skipped, penalty, note.
# - "unknown": no letters at all (digits, punctuation, emoji) — nothing to
#              classify; rules run as-is, no note.
COVERAGE_FULL = "full"
COVERAGE_PARTIAL = "partial"
COVERAGE_NONE = "none"
COVERAGE_UNKNOWN = "unknown"

_FULL_COVERAGE_AT = 0.7
_NONE_COVERAGE_BELOW = 0.5

# Confidence penalty applied on the degraded path (rules skipped). 20 points
# puts a degraded result at score 80: never ``ready`` (85) in either mode —
# ``usable_with_warnings`` in warning mode, ``needs_clarification`` in strict
# mode — so a degraded result can never masquerade as a clean bill of health.
# Policy-tunable in a later release; this constant is the default.
DEGRADATION_PENALTY = 20

# Intent reported for degraded results. Intent detection is English-keyword
# based, so on uncovered scripts it has no evidence; "undetermined" is an
# additive intent value that says so instead of guessing the "build" fallback.
DEGRADED_INTENT = "undetermined"

# The probe examines a deterministic stride sample of at most this many
# characters, bounding probe cost on arbitrarily long input.
_SAMPLE_LIMIT = 4096

# Unicode name token -> script label. Name tokens are matched left-to-right,
# so the first script mention in the name wins ("FULLWIDTH LATIN CAPITAL
# LETTER A" -> "latin"; "KATAKANA-HIRAGANA PROLONGED SOUND MARK" ->
# "katakana").
_SCRIPT_KEYWORDS = {
    "latin": "latin",
    "cjk": "han",
    "ideograph": "han",
    "han": "han",
    "hiragana": "hiragana",
    "katakana": "katakana",
    "hangul": "hangul",
    "cyrillic": "cyrillic",
    "greek": "greek",
    "arabic": "arabic",
    "hebrew": "hebrew",
    "syriac": "syriac",
    "thaana": "thaana",
    "devanagari": "devanagari",
    "bengali": "bengali",
    "gurmukhi": "gurmukhi",
    "gujarati": "gujarati",
    "oriya": "oriya",
    "tamil": "tamil",
    "telugu": "telugu",
    "kannada": "kannada",
    "malayalam": "malayalam",
    "sinhala": "sinhala",
    "thai": "thai",
    "lao": "lao",
    "tibetan": "tibetan",
    "myanmar": "myanmar",
    "georgian": "georgian",
    "armenian": "armenian",
    "ethiopic": "ethiopic",
    "cherokee": "cherokee",
    "mongolian": "mongolian",
    "khmer": "khmer",
}

# Script label -> coarse language guess. Script-level detection cannot pick
# between languages sharing a script (Han is written as Chinese *and* Japanese
# kanji); the ``ja`` refinement below handles the kana case, and the guess is
# documented as script-derived, never certain.
_SCRIPT_LANGUAGE = {
    "latin": "en",
    "han": "zh",
    "hiragana": "ja",
    "katakana": "ja",
    "hangul": "ko",
    "cyrillic": "ru",
    "greek": "el",
    "arabic": "ar",
    "hebrew": "he",
    "syriac": "syc",
    "thaana": "dv",
    "devanagari": "hi",
    "bengali": "bn",
    "gurmukhi": "pa",
    "gujarati": "gu",
    "oriya": "or",
    "tamil": "ta",
    "telugu": "te",
    "kannada": "kn",
    "malayalam": "ml",
    "sinhala": "si",
    "thai": "th",
    "lao": "lo",
    "tibetan": "bo",
    "myanmar": "my",
    "georgian": "ka",
    "armenian": "hy",
    "ethiopic": "am",
    "cherokee": "chr",
    "mongolian": "mn",
    "khmer": "km",
}


@dataclass(frozen=True)
class ScriptProbe:
    """Result of the script histogram over one input.

    ``heuristic_coverage`` is the field ``analyze()`` branches on; the other
    fields feed the degradation note and the result's ``detected_language``.
    """

    detected_language: str
    dominant_script: Optional[str]
    covered_share: float
    heuristic_coverage: str


def _sample(text: str, limit: int) -> str:
    """Deterministic stride sample of at most ``limit`` characters.

    Striding (not truncating) keeps the histogram representative of the whole
    input — a script buried at the end of a long paste is still seen.
    """
    if len(text) <= limit:
        return text
    step = (len(text) + limit - 1) // limit  # ceil division
    return text[::step]


def _script_of(char: str) -> Optional[str]:
    """Best-effort script label for one character, or ``None``.

    Non-letters (digits, punctuation, emoji, marks) and unnamed code points
    carry no script evidence and return ``None``.
    """
    if not unicodedata.category(char).startswith("L"):
        return None
    try:
        name = unicodedata.name(char)
    except ValueError:  # unassigned / unnamed code point
        return None
    for token in re.findall(r"[a-z]+", name.lower()):
        script = _SCRIPT_KEYWORDS.get(token)
        if script is not None:
            return script
    return None


def probe_script(text: str) -> ScriptProbe:
    """Classify an input's script coverage with a :mod:`unicodedata` histogram.

    Pure function: same input, same probe, no shared state — safe to call
    from parallel ``analyze()`` threads. The classified population is the
    letters whose script the probe recognizes; scripts outside
    :data:`_SCRIPT_KEYWORDS` (Runic, Deseret, ...) leave the covered-share
    denominator, which is the honest signal that heuristics do not apply.
    """
    letter_count = 0
    script_counts: Dict[str, int] = {}
    for char in _sample(text, _SAMPLE_LIMIT):
        if not unicodedata.category(char).startswith("L"):
            continue
        letter_count += 1
        script = _script_of(char)
        if script is not None:
            script_counts[script] = script_counts.get(script, 0) + 1

    classified = sum(script_counts.values())
    if classified == 0:
        # Letters with no recognizable script, or no letters at all.
        coverage = COVERAGE_NONE if letter_count > 0 else COVERAGE_UNKNOWN
        return ScriptProbe(
            detected_language="und",
            dominant_script=None,
            covered_share=0.0,
            heuristic_coverage=coverage,
        )

    covered_share = script_counts.get("latin", 0) / classified
    if covered_share >= _FULL_COVERAGE_AT:
        coverage = COVERAGE_FULL
    elif covered_share >= _NONE_COVERAGE_BELOW:
        coverage = COVERAGE_PARTIAL
    else:
        coverage = COVERAGE_NONE

    # Deterministic dominant script: highest count, alphabetical tie-break.
    dominant = min(script_counts, key=lambda s: (-script_counts[s], s))
    detected_language = _detected_language(dominant, script_counts)

    return ScriptProbe(
        detected_language=detected_language,
        dominant_script=dominant,
        covered_share=covered_share,
        heuristic_coverage=coverage,
    )


def _detected_language(dominant: str, script_counts: Dict[str, int]) -> str:
    """Coarse script-derived language guess; "und" when nothing maps."""
    kana_present = script_counts.get("hiragana", 0) + script_counts.get("katakana", 0)
    if dominant in ("han", "hiragana", "katakana") and kana_present:
        return "ja"  # kana alongside han (or alone) reads as Japanese
    return _SCRIPT_LANGUAGE.get(dominant, "und")


def degradation_note_for(probe: ScriptProbe) -> str:
    """The note carried by results on the degraded (uncovered) path."""
    if probe.dominant_script is None:
        script_desc = "a script outside the probe's coverage"
    else:
        script_desc = f"the {probe.dominant_script} script"
    return (
        f"InputGuard's clarity rules are English-language heuristics; this "
        f"input appears to use {script_desc} (guessed language: "
        f"{probe.detected_language}), which they do not cover. Rule analysis "
        "was skipped rather than run with false confidence — this result "
        "reports a language limitation of the tool, not a judgment of the "
        "input's clarity. Rephrasing the key details in English enables a "
        "full analysis."
    )


def partial_coverage_note(probe: ScriptProbe) -> str:
    """The note carried when rules ran but a minority script is uncovered."""
    covered_pct = round(probe.covered_share * 100)
    return (
        f"Input mixes scripts — about {covered_pct}% of its letters fall "
        "within the English-heuristic coverage. Rules ran on the input as a "
        "whole, so findings may miss content in the uncovered script(s)."
    )
