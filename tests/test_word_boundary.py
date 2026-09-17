"""Word-boundary matching regressions (the probe P1 false-positive class).

The v0.2 matcher read ``"fixture"`` as the debug signal ``"fix"`` (probe P1:
``"I love this fixture in the test suite, what does it do"`` scored 35 as a
debug request). These tests pin the shared matcher's contract
(``inputguard.matching``): terms match as standalone words, inflected and
suffixed forms still match (no new false negatives at term boundaries), and
unrelated embeddings (``"fixture"``, ``"refix"``, ``"prefix"``) do not.
"""

from __future__ import annotations

import pytest

from inputguard import InputGuard
from inputguard.detector import DEBUG_SIGNALS
from inputguard.matching import contains_any, contains_term


P1_INPUT = "I love this fixture in the test suite, what does it do"
DEBUG_CODES = {"missing_error_message", "missing_expected_vs_actual", "missing_debug_code_context"}


class TestProbeP1Regression:
    """The false positive that motivated the matcher: fixture reads as fix."""

    def test_p1_input_no_longer_reads_as_debug(self):
        result = InputGuard().analyze(P1_INPUT)
        assert result.detected_intent != "debug"
        assert not any(f.code in DEBUG_CODES for f in result.findings)

    def test_p1_input_not_hard_flagged(self):
        # The input is honestly an (underspecified) explanation request, so
        # advisory findings are correct — but it must not land in a hard
        # flag state in the default warning mode (v0.2: score 35,
        # needs_clarification).
        result = InputGuard().analyze(P1_INPUT)
        assert result.clarity_score >= 60
        assert result.status in ("ready", "usable_with_warnings")

    def test_p1_input_does_not_match_any_debug_signal(self):
        assert contains_any(P1_INPUT.lower(), DEBUG_SIGNALS) is False


class TestBoundaryPolarity:
    """Embeddings that must stop matching (the killed false-positive class)."""

    @pytest.mark.parametrize(
        "text",
        [
            "the fixture loads slowly",
            "my fixtures are missing",
            "refix the layout",
            "prefix the variable",
        ],
    )
    def test_embedded_words_do_not_match(self, text):
        assert contains_term(text, "fix") is False

    def test_left_embedding_does_not_match(self):
        # "raised" embedded in "praised" (the survey's second substring FP).
        assert contains_term("praised the release", "raised") is False

    def test_fixture_does_not_match_fix(self):
        assert contains_term("the fixture loads slowly", "fix") is False

    def test_suffix_embeddings_are_required(self):
        # "fixture" is not a suffix of "fix" — only inflectional endings count.
        assert contains_term("fixture", "fix") is False
        assert contains_term("fixtures", "fix") is False


class TestGenuineHitsStillMatch:
    """No new false negatives: real term occurrences keep firing."""

    @pytest.mark.parametrize(
        ("text", "term"),
        [
            ("fix the login bug", "fix"),
            ("fix, this breaks", "fix"),
            ("(fix) applied", "fix"),
            ("FIX THIS NOW", "fix"),
            ("my_error is misleading", "error"),
            ("route /users", "/"),
            ("x=>y mapping", "=>"),
            ("a->b pointer", "->"),
        ],
    )
    def test_genuine_hits(self, text, term):
        assert contains_term(text, term) is True


class TestInflectionsStillMatch:
    """Inflectional forms the substring matcher caught must keep matching."""

    @pytest.mark.parametrize(
        ("text", "term"),
        [
            ("my code has bugs", "bug"),
            ("it raises errors", "error"),
            ("i debugged the loop", "debug"),
            ("still debugging it", "debug"),
            ("the bugfix was debugged twice", "debug"),
            ("it crashed twice", "crash"),
            ("refactoring the hot loop", "refactor"),
            ("we refactored it", "refactor"),
            ("profile this code", "profil"),
            ("profiling shows the bottleneck", "profil"),
            ("the profiler output", "profil"),
            ("stack traces attached", "stack trace"),
            ("error messages below", "error message"),
        ],
    )
    def test_inflected_forms(self, text, term):
        assert contains_term(text, term) is True


class TestMultiwordPhrases:
    """Phrases match adjacently (with final-word inflections); the coding
    rules' v0.2 token fallback stays opt-in."""

    def test_adjacent_phrase_matches(self):
        assert contains_any("it is not working today", {"not working"}) is True

    def test_non_adjacent_words_do_not_match_by_default(self):
        # v0.2 substring never matched these either — adjacency is required
        # unless the caller opts into the coding token fallback.
        assert contains_any("add authentication to the app", {"add to the"}) is False

    def test_token_fallback_is_opt_in(self):
        terms = {"error message"}
        text = "the error and the message"
        assert contains_any(text, terms) is False
        assert contains_any(text, terms, token_fallback=True) is True

    def test_token_fallback_matches_v02_coding_rules(self):
        # The v0.2 coding matcher's fallback: multiword term words may appear
        # non-adjacent (e.g. "def " token prefixes).
        assert contains_any("in def process_order we loop", {"def "}) is True


class TestAnalyzeSpotChecks:
    """End-to-end: intents and findings survive the matcher change."""

    @pytest.mark.parametrize(
        ("text", "expected_intent"),
        [
            ("fix the login bug, it crashes with an error", "debug"),
            ("my code has bugs that raise errors", "debug"),
            ("the parser failed after I debugged it, stack traces show typeerror", "debug"),
            ("we are refactoring the hot loop", "optimization"),
            ("profiling shows the bottleneck", "optimization"),
            ("Build a REST API using FastAPI. Store users in PostgreSQL with JWT auth and Stripe integration.", "build"),
        ],
    )
    def test_intent_preserved(self, text, expected_intent):
        assert InputGuard().analyze(text).detected_intent == expected_intent

    def test_feature_phrase_does_not_shadow_build(self):
        # "add to the" must not fire on non-adjacent words and steal the
        # intent from build (regression: coding auth rule stopped running).
        result = InputGuard().analyze("add authentication to the app")
        assert result.detected_intent == "build"
        assert "missing_auth_type" in [f.code for f in result.findings]


class TestMatcherContract:
    def test_string_terms_rejected(self):
        with pytest.raises(TypeError):
            contains_any("text", "fix")

    def test_empty_term_never_matches(self):
        assert contains_term("anything", "") is False

    def test_case_folded_for_ad_hoc_callers(self):
        assert contains_any("FIX the bug", {"fix"}) is True
