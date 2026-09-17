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

Latin script alone is not sufficient coverage, though: the heuristics are
English-only, and French, Spanish, or Portuguese text is 100% Latin script
yet just as unreadable to them as Chinese. Two refinements close that gap,
still with zero dependencies (eval rows DG-011..014):

- **Function-word layer** — when the dominant script is Latin, the sample's
  tokens are matched against small stop-word lexicons for French, Spanish,
  and Portuguese. A language is "detected" only when it has at least
  ``_MIN_DISTINCT_HITS`` distinct stop-word hits AND those beats the
  input's English function-word evidence by ``_MIN_ENGLISH_MARGIN`` — so
  genuinely English prompts (rich in English function words) can never
  trip it over scattered collisions ("Pour the DES dump into LA storage").
  The lexicon languages are a documented subset: German, Italian, Dutch,
  and other Latin-script languages still pass as before.
- **Uncovered-run layer** — a run of at least ``_UNCOVERED_BLOCK_DEGRADES_AT``
  consecutive letters in an uncovered script (e.g. a Han clause inside an
  English sentence) downgrades nominal full coverage to the degraded path.
  A two-character borrow like "这个" rides along (rules still run on the
  English majority); a whole clause the rules cannot read cannot.

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

# ---------------------------------------------------------------------------
# Latin-script language layer (eval rows DG-011, DG-012, DG-014)
#
# The script histogram alone cannot see French, Spanish, or Portuguese: their
# letters are Latin, so a purely script-level probe reports 100% coverage and
# the English-only heuristics run on text they cannot read — the same silent
# ready the probe exists to prevent. The labeling guide's rubric for these
# rows prescribes the fix: a stop-word probe that refuses to let "Latin
# script alone silently pass".
#
# The lexicons are deliberately tiny and conservative — function words
# (articles, pronouns, prepositions, conjunctions, question words) only:
# - every entry is >= 2 letters and is not a standalone English word, so
#   scattered collisions (French "pour" = English "pour", "est" = the EST
#   timezone) cannot manufacture a detection on their own;
# - matching runs on accent-stripped tokens ("qué" -> "que") and on tokens
#   trimmed of edge punctuation ("¿Por" -> "por"), never on interior
#   punctuation ("example.com" or "de-serialization" stay single tokens and
#   cannot match "com" / "de");
# - detection additionally requires the margin rule in ``_latin_language_of``
#   (distinct non-English hits must beat English function-word evidence by
#   ``_MIN_ENGLISH_MARGIN``), so genuinely English prompts — which are dense
#   in English function words — cannot trip the layer at all.
#
# This is an honest documented subset: German, Italian, Dutch, and other
# Latin-script languages still pass as before, because a word list for every
# language is neither shippable nor zero-dependency-honest. The probe reports
# a *guess* ("guessed language"), never a certainty.
# ---------------------------------------------------------------------------
_MIN_DISTINCT_HITS = 3
_MIN_ENGLISH_MARGIN = 3
# When the input shows zero English function-word evidence, two distinct
# foreign function words already fire: "Oui merci beaucoup pour ton aide"
# carries no English function words at all, and demanding three would miss
# it. A collision-only English prompt always has English evidence (the/a/
# and/...), so the relaxed floor cannot trip it.
_MIN_SOLO_HITS = 2

# Run length (in consecutive letters) of an uncovered script inside an
# otherwise-covered input that forces the degraded path (eval row DG-013).
# A 1-2 letter borrow ("这个") rides along under the English majority; a run
# of 3+ letters is a word or clause the English heuristics cannot read.
_UNCOVERED_BLOCK_DEGRADES_AT = 3

_LATIN_FUNCTION_WORDS: Dict[str, frozenset] = {
    "en": frozenset({
        "a", "an", "the", "and", "or", "but", "if", "then", "of", "to", "in",
        "on", "at", "by", "for", "with", "from", "into", "over", "under",
        "up", "down", "out", "off", "about", "after", "before", "between",
        "during", "through", "without", "within", "is", "are", "was", "were",
        "be", "been", "being", "am", "do", "does", "did", "have", "has",
        "had", "will", "would", "can", "could", "should", "shall", "may",
        "might", "must", "i", "you", "he", "she", "it", "we", "they", "me",
        "him", "us", "them", "my", "your", "his", "its", "our", "their",
        "this", "that", "these", "those", "there", "here", "who", "whom",
        "whose", "which", "what", "when", "where", "why", "how", "all",
        "any", "some", "each", "every", "both", "few", "many", "much",
        "more", "most", "very", "too", "also", "just", "only", "again",
        "once", "now", "not", "no", "yes", "so", "such", "than", "as",
        "because", "while", "per", "via", "please",
    }),
    "es": frozenset({
        "el", "los", "las", "una", "unos", "unas", "mi", "mis", "tu", "tus",
        "su", "sus", "pero", "para", "por", "que", "como", "donde",
        "cuando", "cual", "cuanto", "esto", "esta", "este", "eso", "ese",
        "esa", "esos", "esas", "con", "sin", "se", "es", "muy", "mas",
        "soy", "eres", "puedo", "puedes", "quiero", "necesito", "gracias",
        "hola", "porque", "tambien", "de",
    }),
    "fr": frozenset({
        "le", "la", "les", "des", "un", "une", "du", "au", "aux", "et",
        "est", "dans", "pour", "avec", "sur", "ce", "cet", "cette", "ces",
        "je", "tu", "il", "elle", "nous", "vous", "ils", "elles", "mon",
        "ton", "son", "mes", "tes", "ses", "leur", "leurs", "qui", "que",
        "quoi", "dont", "ou", "mais", "donc", "chez", "tres", "aussi",
        "pourquoi", "etre", "avoir", "sans", "entre", "de",
    }),
    "pt": frozenset({
        "um", "uma", "uns", "umas", "de", "da", "dos", "das", "na", "nas",
        "nos", "com", "para", "por", "que", "como", "muito", "mas", "meu",
        "minha", "meus", "minhas", "isso", "isto", "estou", "preciso",
        "obrigado", "obrigada", "quero", "posso", "onde", "porque",
        "tambem", "seu", "sua", "sem",
    }),
}

# Note-facing language names for lexicon-detected Latin-script inputs.
_LATIN_LANGUAGE_NAMES = {"fr": "French", "es": "Spanish", "pt": "Portuguese"}

# Punctuation that French/Spanish/Portuguese elides into the next word
# ("l'homme", "n'est") — split it so the pieces can match their lexicons.
_APOSTROPHES = str.maketrans({"'": " ", "\u2019": " ", "`": " "})

# Trim edge punctuation ("¿Por" -> "Por", "bord." -> "bord") while keeping
# interior punctuation intact ("example.com" stays one token, so a URL can
# never contribute a stray "com" hit).
_EDGE_TRIM = re.compile(r"^[^\w]+|[^\w]+$")


@dataclass(frozen=True)
class ScriptProbe:
    """Result of the script histogram over one input.

    ``heuristic_coverage`` is the field ``analyze()`` branches on; the other
    fields feed the degradation note and the result's ``detected_language``.

    ``uncovered_block_script`` / ``uncovered_block_length`` record the longest
    run of consecutive uncovered-script letters in the sample (0 when every
    classified letter is Latin). They explain *why* a Latin-dominant input
    was degraded — the mixed English+Han case — and feed the note's wording.
    """

    detected_language: str
    dominant_script: Optional[str]
    covered_share: float
    heuristic_coverage: str
    uncovered_block_script: Optional[str] = None
    uncovered_block_length: int = 0


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


def _strip_diacritics(token: str) -> str:
    """Accent-fold one token for lexicon matching: "qué" -> "que".

    NFD decomposition splits accented letters into base letter + combining
    mark; the marks (category Mn) drop out. Purely lexical — the histogram
    itself keeps every letter, accented or not.
    """
    decomposed = unicodedata.normalize("NFD", token)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _latin_language_of(sample: str) -> Optional[str]:
    """Guess a non-English Latin-script language from function words, or ``None``.

    A language "fires" only when its distinct stop-word hits reach
    :data:`_MIN_DISTINCT_HITS` AND beat the input's distinct English
    function-word hits by :data:`_MIN_ENGLISH_MARGIN` — English prompts are
    dense in English function words, so scattered collisions with French or
    Spanish tokens ("pour", "est", "la") can never fire the layer alone.
    Ties between firing languages resolve alphabetically, like the script
    histogram's dominant-script tie-break.
    """
    distinct: Dict[str, set] = {}
    for raw in sample.translate(_APOSTROPHES).lower().split():
        token = _EDGE_TRIM.sub("", raw)
        if not token:
            continue
        stripped = _strip_diacritics(token)
        for lang, words in _LATIN_FUNCTION_WORDS.items():
            if stripped in words:
                distinct.setdefault(lang, set()).add(stripped)
    english = len(distinct.get("en", set()))
    # English-dense inputs need the full margin; zero-English inputs fire on
    # the relaxed floor (see _MIN_SOLO_HITS).
    floor = _MIN_DISTINCT_HITS if english else _MIN_SOLO_HITS
    firing = [
        (len(words), lang)
        for lang, words in distinct.items()
        if lang != "en"
        and len(words) >= floor
        and (english == 0 or len(words) >= english + _MIN_ENGLISH_MARGIN)
    ]
    if not firing:
        return None
    firing.sort(key=lambda item: (-item[0], item[1]))
    return firing[0][1]


def probe_script(text: str) -> ScriptProbe:
    """Classify an input's script coverage with a :mod:`unicodedata` histogram.

    Pure function: same input, same probe, no shared state — safe to call
    from parallel ``analyze()`` threads. The classified population is the
    letters whose script the probe recognizes; scripts outside
    :data:`_SCRIPT_KEYWORDS` (Runic, Deseret, ...) leave the covered-share
    denominator, which is the honest signal that heuristics do not apply.

    On top of the share histogram, two refinements route inputs the share
    alone would wrongly call fully covered to the degraded path: Latin-script
    text recognized as French/Spanish/Portuguese by function words
    (:func:`_latin_language_of`), and Latin-dominant text carrying a run of
    uncovered-script letters too long to ride along (``_UNCOVERED_BLOCK_DEGRADES_AT``).
    """
    letter_count = 0
    script_counts: Dict[str, int] = {}
    uncovered_run = 0
    max_uncovered_run = 0
    max_uncovered_script: Optional[str] = None
    sample = _sample(text, _SAMPLE_LIMIT)
    for char in sample:
        if not unicodedata.category(char).startswith("L"):
            uncovered_run = 0  # any non-letter breaks a run
            continue
        letter_count += 1
        script = _script_of(char)
        if script is not None:
            script_counts[script] = script_counts.get(script, 0) + 1
        if script == "latin":
            uncovered_run = 0
        else:
            uncovered_run += 1
            if uncovered_run > max_uncovered_run:
                max_uncovered_run = uncovered_run
                max_uncovered_script = script

    classified = sum(script_counts.values())
    if classified == 0:
        # Letters with no recognizable script, or no letters at all.
        coverage = COVERAGE_NONE if letter_count > 0 else COVERAGE_UNKNOWN
        return ScriptProbe(
            detected_language="und",
            dominant_script=None,
            covered_share=0.0,
            heuristic_coverage=coverage,
            uncovered_block_script=max_uncovered_script if letter_count > 0 else None,
            uncovered_block_length=max_uncovered_run if letter_count > 0 else 0,
        )

    covered_share = script_counts.get("latin", 0) / classified
    # Deterministic dominant script: highest count, alphabetical tie-break.
    dominant = min(script_counts, key=lambda s: (-script_counts[s], s))

    latin_language = _latin_language_of(sample) if dominant == "latin" else None
    if latin_language is not None:
        # French/Spanish/Portuguese: 100% Latin script, yet the English-only
        # heuristics cannot read a word of it — degraded like any other
        # uncovered language, never a silent pass on nominal coverage.
        coverage = COVERAGE_NONE
        detected_language = latin_language
    else:
        detected_language = _detected_language(dominant, script_counts)
        if covered_share >= _FULL_COVERAGE_AT:
            if max_uncovered_run >= _UNCOVERED_BLOCK_DEGRADES_AT:
                # Latin-dominant but carrying a substantive uncovered-script
                # clause (mixed English+Han, DG-013): the rules cannot read
                # that content, so full coverage is a false claim.
                coverage = COVERAGE_NONE
            else:
                coverage = COVERAGE_FULL
        elif covered_share >= _NONE_COVERAGE_BELOW:
            coverage = COVERAGE_PARTIAL
        else:
            coverage = COVERAGE_NONE

    return ScriptProbe(
        detected_language=detected_language,
        dominant_script=dominant,
        covered_share=covered_share,
        heuristic_coverage=coverage,
        uncovered_block_script=max_uncovered_script,
        uncovered_block_length=max_uncovered_run,
    )


def _detected_language(dominant: str, script_counts: Dict[str, int]) -> str:
    """Coarse script-derived language guess; "und" when nothing maps."""
    kana_present = script_counts.get("hiragana", 0) + script_counts.get("katakana", 0)
    if dominant in ("han", "hiragana", "katakana") and kana_present:
        return "ja"  # kana alongside han (or alone) reads as Japanese
    return _SCRIPT_LANGUAGE.get(dominant, "und")


def degradation_note_for(probe: ScriptProbe) -> str:
    """The note carried by results on the degraded (uncovered) path."""
    if probe.detected_language in _LATIN_LANGUAGE_NAMES:
        script_desc = (
            f"the {probe.dominant_script} script, but function words read as "
            f"{_LATIN_LANGUAGE_NAMES[probe.detected_language]}"
        )
    elif probe.dominant_script is None:
        script_desc = "a script outside the probe's coverage"
    else:
        script_desc = f"the {probe.dominant_script} script"
    note = (
        f"InputGuard's clarity rules are English-language heuristics; this "
        f"input appears to use {script_desc} (guessed language: "
        f"{probe.detected_language}), which they do not cover. Rule analysis "
        "was skipped rather than run with false confidence — this result "
        "reports a language limitation of the tool, not a judgment of the "
        "input's clarity. Rephrasing the key details in English enables a "
        "full analysis."
    )
    if probe.uncovered_block_length >= _UNCOVERED_BLOCK_DEGRADES_AT:
        note += (
            " The input also mixes scripts: a run of "
            f"{probe.uncovered_block_length} letters in "
            f"{probe.uncovered_block_script or 'an uncovered'} script sits "
            "outside the heuristics' coverage."
        )
    return note


def partial_coverage_note(probe: ScriptProbe) -> str:
    """The note carried when rules ran but a minority script is uncovered."""
    covered_pct = round(probe.covered_share * 100)
    return (
        f"Input mixes scripts — about {covered_pct}% of its letters fall "
        "within the English-heuristic coverage. Rules ran on the input as a "
        "whole, so findings may miss content in the uncovered script(s)."
    )
