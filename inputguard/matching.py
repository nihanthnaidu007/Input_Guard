"""Shared word-boundary matching for every signal and rule wordlist.

Before v0.3 the detector and four rule modules matched terms with raw
substring containment (``term in text``), so the debug signal ``"fix"`` read
``"fixture"`` as a debug request and innocent inputs were flagged (probe P1:
``"I love this fixture in the test suite..."`` scored 35 as debug). All term
lookups now go through this module, which matches terms as standalone words
under three guarantees:

- **Boundaries:** a term matches only at a word boundary on each side, so
  ``"fix"`` matches ``"fix this"`` but not ``"fixture"``, ``"refix"``, or
  ``"praised"`` (from ``"raised"``). The boundary class is the one the v0.2
  coding matcher already used (``(?<![a-z0-9])...(?![a-z0-9])`` on
  lowercased text), so identifier mentions like ``my_error`` still count.
- **Inflections stay genuine:** common endings (plural, ``-ed``, ``-ing``,
  ``-er``, ``-ly``, ``-e``) still match — ``"bugs"``, ``"errors"``,
  ``"debugged"``, ``"refactoring"``, ``"stack traces"``, ``"profiling"``
  all keep firing, so tightening the boundaries introduces no new false
  negatives. Formally: every v0.2 substring hit whose embedding was
  suffix-shaped at a word boundary still matches; the killed hits are
  exactly the embedded-inside-a-longer-word class that produced probe P1.
- **Multiword terms:** a phrase matches when each of its words does (each
  word accepting inflections, so ``"error messages"`` matches the term
  ``"error message"``). With ``token_fallback=True`` a phrase also matches
  when its words are all present but not adjacent — the v0.2 coding-rule
  behavior, kept for the coding rules only so their verdicts are unchanged.

Terms with no alphanumeric characters (``/``, ``=>``, ``->``, ``::``) have
no word to bound and keep plain substring semantics.

Text is expected pipeline-normalized (lowercased, whitespace-collapsed);
case is folded defensively so ad-hoc callers get identical verdicts.

Matching is deterministic and thread-safe: finders are compiled once per
term-set through ``functools.lru_cache`` (compiled finders are immutable and
the cached values are idempotent, so concurrent first calls are safe).
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Callable, FrozenSet, Iterable, List, Tuple

__all__ = ["contains_any", "contains_term"]

# The v0.2 coding matcher's boundary class: a neighboring identifier
# character ("my_error") still counts as a mention; a longer word does not.
_LEFT_BOUND = r"(?<![a-z0-9])"
_RIGHT_BOUND = r"(?![a-z0-9])"

# Inflectional endings a term may absorb while still counting as a hit.
# Deliberately suffix-only — a wildcard right side would make "fix" match
# "fixture" again.
_ENDINGS = r"(?:s|es|ed|d|ing|ers|er|ly|e)?"

# Final consonants that double before -ed/-ing ("debug" -> "debugged").
_DOUBLABLE = frozenset("bgmnpt")


def _fold(text: str) -> str:
    # Internal callers pass normalized text; fold defensively for ad-hoc calls.
    return text if text.islower() else text.lower()


def _stem_variants(term: str) -> Tuple[str, ...]:
    """Stems whose suffixed forms belong to ``term`` ("debug" -> "debugged")."""
    variants = {term}
    if term.endswith("e"):
        variants.add(term[:-1])  # "store" -> "storing"
    if term[-1] in _DOUBLABLE:
        variants.add(term + term[-1])  # "debug" -> "debugged"
    return tuple(sorted(variants))


def _single_word_body(term: str) -> str:
    return "|".join(re.escape(stem) + _ENDINGS for stem in _stem_variants(term))


def _single_word_pattern(term: str) -> str:
    return _LEFT_BOUND + "(?:" + _single_word_body(term) + ")" + _RIGHT_BOUND


def _phrase_body(tokens: Tuple[str, ...]) -> str:
    # Adjacent words (v0.2 substring parity); the final word carries the
    # inflections so plural phrases ("stack traces") still match the term.
    head = " ".join(re.escape(token) for token in tokens[:-1])
    tail = re.escape(tokens[-1]) + _ENDINGS
    return head + " " + tail if head else tail


def _phrase_pattern(tokens: Tuple[str, ...]) -> str:
    return _LEFT_BOUND + "(?:" + _phrase_body(tokens) + ")" + _RIGHT_BOUND


def _exact_word_pattern(term: str) -> str:
    return _LEFT_BOUND + re.escape(term) + _RIGHT_BOUND


def contains_term(text: str, term: str) -> bool:
    """Whether ``term`` occurs in ``text`` as a standalone word or phrase."""
    return _term_in(_fold(text), term.strip())


def _term_in(text: str, term: str) -> bool:
    if not term:
        return False
    if not any(ch.isalnum() for ch in term):
        # "/", "=>", "->", "::" — no word to bound; v0.2 substring semantics.
        return term in text
    if " " in term:
        return re.search(_phrase_pattern(tuple(term.split())), text) is not None
    return re.search(_single_word_pattern(term), text) is not None


@lru_cache(maxsize=None)
def _build_finder(
    terms: FrozenSet[str], token_fallback: bool
) -> Callable[[str], bool]:
    singles: List[str] = []
    phrases: List[Tuple[str, ...]] = []
    plain: List[str] = []
    for term in terms:
        stripped = term.strip()
        if not stripped:
            continue
        if not any(ch.isalnum() for ch in stripped):
            plain.append(stripped)
        elif " " in stripped:
            phrases.append(tuple(stripped.split()))
        else:
            singles.append(stripped)

    # One alternation scan covers every single-word term in the set.
    single_re = (
        re.compile(
            _LEFT_BOUND
            + "(?:"
            + "|".join(sorted(_single_word_body(s) for s in singles))
            + ")"
            + _RIGHT_BOUND
        )
        if singles
        else None
    )
    phrase_re = (
        re.compile(
            _LEFT_BOUND
            + "(?:"
            + "|".join(sorted(_phrase_body(tokens) for tokens in phrases))
            + ")"
            + _RIGHT_BOUND
        )
        if phrases
        else None
    )
    # v0.2 coding parity: fallback tokens match exactly, without inflections.
    fallback_res = (
        [
            tuple(re.compile(_exact_word_pattern(token)) for token in tokens)
            for tokens in phrases
        ]
        if token_fallback
        else []
    )
    plain_tuple = tuple(plain)

    def find(text: str) -> bool:
        if single_re is not None and single_re.search(text):
            return True
        if any(term in text for term in plain_tuple):
            return True
        if phrase_re is not None and phrase_re.search(text):
            return True
        if token_fallback:
            for tokens_re in fallback_res:
                if all(token_re.search(text) for token_re in tokens_re):
                    return True
        return False

    return find


def contains_any(
    text: str, terms: Iterable[str], token_fallback: bool = False
) -> bool:
    """Whether any of ``terms`` occurs in ``text`` as a standalone word or phrase.

    ``token_fallback=True`` restores the v0.2 coding-rule behavior of matching
    a multiword term whose words are all present but not adjacent.
    """
    if isinstance(terms, str):
        raise TypeError(
            "contains_any expects an iterable of terms, not a single string — "
            f"got {terms!r}."
        )
    return _build_finder(frozenset(terms), token_fallback)(_fold(text))
