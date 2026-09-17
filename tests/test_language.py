"""Tests for the language probe and the multilingual degradation path.

Probe units cover script classification and coverage bands
(``inputguard.language``). The integration section covers the degraded
``analyze()`` path end to end: the probe-P2 regression (Chinese input
must never silently return ready/100), mode behavior, additive result
fields, English parity, systematic Unicode no-crash samples, and
thread-safe parallel analysis.
"""

from __future__ import annotations

import json
import unicodedata
from concurrent.futures import ThreadPoolExecutor

import pytest

from inputguard import InputGuard
from inputguard.language import (
    COVERAGE_FULL,
    COVERAGE_NONE,
    COVERAGE_PARTIAL,
    COVERAGE_UNKNOWN,
    DEGRADATION_PENALTY,
    DEGRADED_INTENT,
    _sample,
    degradation_note_for,
    partial_coverage_note,
    probe_script,
)

# Well-known probe-P2 input: pure Chinese, zero English heuristic coverage.
CHINESE = "建造一个用户登录应用"


def test_pure_english_is_full_coverage_en():
    probe = probe_script("build a rest api with users in postgresql")
    assert probe.dominant_script == "latin"
    assert probe.detected_language == "en"
    assert probe.heuristic_coverage == COVERAGE_FULL
    assert probe.covered_share == 1.0


def test_pure_chinese_is_uncovered_han():
    probe = probe_script(CHINESE)
    assert probe.dominant_script == "han"
    assert probe.detected_language == "zh"
    assert probe.heuristic_coverage == COVERAGE_NONE
    assert probe.covered_share == 0.0


def test_cyrillic_is_uncovered():
    probe = probe_script("почему моя программа не работает")
    assert probe.dominant_script == "cyrillic"
    assert probe.detected_language == "ru"
    assert probe.heuristic_coverage == COVERAGE_NONE


def test_arabic_is_uncovered():
    probe = probe_script("لماذا لا يعمل هذا الكود")
    assert probe.dominant_script == "arabic"
    assert probe.detected_language == "ar"
    assert probe.heuristic_coverage == COVERAGE_NONE


def test_hebrew_is_uncovered():
    probe = probe_script("למה הקוד הזה לא עובד")
    assert probe.dominant_script == "hebrew"
    assert probe.detected_language == "he"
    assert probe.heuristic_coverage == COVERAGE_NONE


def test_greek_is_uncovered():
    probe = probe_script("γιατί δεν λειτουργεί")
    assert probe.dominant_script == "greek"
    assert probe.detected_language == "el"
    assert probe.heuristic_coverage == COVERAGE_NONE


def test_korean_is_uncovered():
    probe = probe_script("이 코드가 왜 작동하지 않는 건가요")
    assert probe.dominant_script == "hangul"
    assert probe.detected_language == "ko"
    assert probe.heuristic_coverage == COVERAGE_NONE


def test_japanese_kana_reads_as_ja():
    probe = probe_script("このコードが動作しないのはなぜですか")
    assert probe.dominant_script in ("hiragana", "katakana", "han")
    assert probe.detected_language == "ja"
    assert probe.heuristic_coverage == COVERAGE_NONE


def test_fullwidth_latin_reads_as_latin():
    # Fullwidth Latin: the Unicode name's first token ("FULLWIDTH") is not
    # the script; the token scan must find "latin".
    probe = probe_script("ＡＰＩ")
    assert probe.dominant_script == "latin"
    assert probe.heuristic_coverage == COVERAGE_FULL


def test_fullwidth_latin_mixed_with_japanese_is_partial():
    # 3 fullwidth latin letters vs 2 japanese letters -> exactly 0.5 share,
    # the partial band boundary: rules still run, a note flags the rest.
    probe = probe_script("ＡＰＩを作る")
    assert probe.dominant_script == "latin"
    assert probe.heuristic_coverage == COVERAGE_PARTIAL


def test_digits_and_punctuation_have_no_coverage_signal():
    probe = probe_script("12345 !!! ??? ...")
    assert probe.dominant_script is None
    assert probe.detected_language == "und"
    assert probe.heuristic_coverage == COVERAGE_UNKNOWN


def test_majority_english_with_minority_han_is_full():
    # 12 latin letters vs 2 han letters -> covered share well above 0.7.
    probe = probe_script("make it faster 这个")
    assert probe.dominant_script == "latin"
    assert probe.heuristic_coverage == COVERAGE_FULL


def test_partial_band_input_is_between_full_and_none():
    # 5 latin letters vs 4 han letters -> covered share 5/9 (~0.56), inside
    # the partial band (>= 0.5, < 0.7).
    probe = probe_script("abcde 这是测试")
    assert probe.heuristic_coverage == COVERAGE_PARTIAL


def test_unknown_script_letters_take_none_path():
    # Runic letters: real letters whose Unicode names the keyword table does
    # not map — the honest classification is "no coverage", not a silent pass.
    probe = probe_script("ᚠᚢᚦᚨᚱᚲ")
    assert probe.dominant_script is None
    assert probe.heuristic_coverage == COVERAGE_NONE


def test_probe_is_deterministic():
    text = "mixed 混合 input テキスト with 数字 123 and émojis 🏳️‍🌈"
    assert probe_script(text) == probe_script(text)


def test_sample_bounds_length_and_is_deterministic():
    text = "a" * 100_000
    sample = _sample(text, 4096)
    assert len(sample) <= 4096
    assert sample == _sample(text, 4096)
    assert _sample("short", 4096) == "short"


def test_sample_lets_tail_scripts_surface():
    # A buried script at the very end of a huge paste must still be seen by
    # the stride sample (stride 3 over 10 000 chars hits index 9999).
    text = "a" * 9999 + "中"
    probe = probe_script(text)
    assert probe.dominant_script == "latin"
    assert probe.covered_share < 1.0


def test_degradation_penalty_never_allows_ready():
    # 100 - penalty must stay below the 85 ready floor in both modes.
    assert 100 - DEGRADATION_PENALTY < 85


def test_degraded_intent_value_is_undetermined():
    assert DEGRADED_INTENT == "undetermined"


def test_note_for_dominant_script_mentions_script_and_language():
    probe = probe_script(CHINESE)
    note = degradation_note_for(probe)
    assert "han" in note
    assert "zh" in note
    assert "English" in note


def test_note_for_unrecognized_script_names_the_limitation():
    probe = probe_script("ᚠᚢᚦᚨᚱᚲ")
    note = degradation_note_for(probe)
    assert "outside the probe's coverage" in note


def test_partial_note_reports_coverage_percentage():
    probe = probe_script("abcde 这是测试")
    note = partial_coverage_note(probe)
    assert "uncovered" in note


def test_script_probe_is_frozen():
    probe = probe_script(CHINESE)
    try:
        probe.detected_language = "en"
        raised = False
    except Exception:
        raised = True
    assert raised


def test_non_letters_are_skipped_by_category():
    # Digits, punctuation, emoji, combining marks, and control characters
    # contribute nothing to the histogram — only letters classify.
    for ch in "0九!！。🏳️‍🌈́\u0000":
        assert unicodedata.category(ch)  # sanity: all real code points
    probe = probe_script("... 123 🏳️‍🌈")
    assert probe.heuristic_coverage == COVERAGE_UNKNOWN


# ---------------------------------------------------------------------------
# Integration: the degraded analyze() path (non-English honesty)
# ---------------------------------------------------------------------------

# Probe P2's exact input: v0.2 returned intent=build, score 100, ready,
# zero findings — a silent pass on input the rules cannot read.
PROBE_P2_INPUT = "建造一个用户登录应用"


def test_probe_p2_regression_chinese_never_silent_ready():
    guard = InputGuard()
    r = guard.analyze(PROBE_P2_INPUT)
    assert r.heuristic_coverage == COVERAGE_NONE
    assert r.degradation_note is not None
    assert r.status != "ready"
    assert r.clarity_score != 100
    assert not r.is_clear()


def test_degraded_result_shape():
    r = InputGuard().analyze(PROBE_P2_INPUT)
    assert r.clarity_score == 100 - DEGRADATION_PENALTY
    assert r.detected_intent == DEGRADED_INTENT
    assert r.detected_language == "zh"
    assert r.gaps == []
    assert r.findings == []
    assert r.recommendations == []
    assert r.interpretation_note is None


def test_degraded_strict_mode_returns_needs_clarification_not_blocked():
    r = InputGuard(mode="strict").analyze(PROBE_P2_INPUT)
    # Score 80 lands in the strict clarify band (65-84), below the ready
    # floor in both modes.
    assert r.status == "needs_clarification"


def test_degraded_warning_mode_returns_usable_with_warnings():
    r = InputGuard().analyze(PROBE_P2_INPUT)
    assert r.status == "usable_with_warnings"


def test_degradation_note_is_actionable():
    r = InputGuard().analyze(PROBE_P2_INPUT)
    assert "English" in r.degradation_note
    assert "han" in r.degradation_note


def test_degraded_applies_to_every_uncovered_script():
    for text in (
        "почему моя программа не работает",
        "لماذا لا يعمل هذا الكود",
        "이 코드가 왜 작동하지 않나요",
        "このコードが動作しないのはなぜですか",
        "γιατί δεν λειτουργεί",
        "ᚠᚢᚦᚨᚱᚲ",
    ):
        r = InputGuard().analyze(text)
        assert r.heuristic_coverage == COVERAGE_NONE, text
        assert r.degradation_note is not None, text
        assert r.status != "ready", text


def test_english_parity_probe_fields():
    # Covered input carries the probe's verdict but no degradation. The
    # clarity verdict itself is unchanged v0.2 behavior: one distinct gap
    # (api structure) -> 100 - 25 = 75.
    r = InputGuard().analyze("Build a REST API using FastAPI. Store users in PostgreSQL.")
    assert r.detected_language == "en"
    assert r.heuristic_coverage == COVERAGE_FULL
    assert r.degradation_note is None
    assert r.status == "usable_with_warnings"
    assert r.clarity_score == 75


def test_english_parity_score_unchanged():
    # Byte-parity with the pre-probe pipeline on a vague English input:
    # debug intent, three distinct gaps -> 100 - 25 - 25 - 15 = 35 (the
    # score the v0.2 README documents for this input).
    r = InputGuard().analyze("fix my code")
    assert r.detected_intent == "debug"
    assert r.clarity_score == 35
    assert r.status == "needs_clarification"
    assert r.heuristic_coverage == COVERAGE_FULL
    assert r.degradation_note is None


def test_partial_coverage_runs_rules_with_note_no_penalty():
    # ~56% covered share: rules run (findings computed as usual), the note
    # flags the uncovered remainder, and no degradation penalty applies.
    r = InputGuard().analyze("abcde 这是测试")
    assert r.heuristic_coverage == COVERAGE_PARTIAL
    assert r.degradation_note is not None
    assert r.clarity_score == 100  # 5-letter input fires no rules


def test_validation_contracts_precede_the_probe():
    guard = InputGuard()
    with pytest.raises(TypeError):
        guard.analyze(12345)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        guard.analyze("   ")
    # Unknown domain raises even for input the probe would degrade.
    with pytest.raises(ValueError):
        guard.analyze(PROBE_P2_INPUT, domain="legal")


def test_to_dict_includes_additive_fields():
    d = InputGuard().analyze(PROBE_P2_INPUT).to_dict()
    assert d["detected_language"] == "zh"
    assert d["heuristic_coverage"] == "none"
    assert isinstance(d["degradation_note"], str)
    # Merged additive contract: v0.2 keys keep their names and relative
    # order, follow_ups slots in after recommendations (questions engine),
    # the three probe keys trail, and the policy-calibration keys append
    # after those (borderline band, input cap, score breakdown).
    assert list(d) == [
        "status",
        "clarity_score",
        "detected_intent",
        "gaps",
        "recommendations",
        "follow_ups",
        "findings",
        "interpretation_note",
        "detected_language",
        "heuristic_coverage",
        "degradation_note",
        "borderline",
        "truncated",
        "score_breakdown",
    ]
    json.dumps(d, ensure_ascii=False)  # JSON-serializable as before


# ---------------------------------------------------------------------------
# Property-style no-crash on arbitrary Unicode (systematic samples —
# hypothesis is not a dev dependency; zero-dep constraint honored)
# ---------------------------------------------------------------------------

_VALID_STATUSES = {"ready", "usable_with_warnings", "needs_clarification", "blocked"}

_UNICODE_SAMPLES = [
    "emoji only 🚀🔥🏳️‍🌈",
    "mixed 混合 text وبالعربية معا",
    "zero width zero​width joiner",
    "rtl override ‮reverse‭",
    "combining marks é̈ 👨‍👩‍👧‍👦",
    "unassigned \u0378 codepoint",
    "cjk mixed with ascii: build api 用户",
    "ｆｕｌｌｗｉｄｔｈ　ｌｅｔｔｅｒｓ １２３",
    "tab\tand\nnewline\r\nmixes",
    "ʼn concatenations ʻʼʽ",
    "íàéä ççñň ņņň — diacritic soup",
    "文字化け mojibake",
    "سيب ذلك mixed rtl ltr",
    "҈ all the combining things ✈ ✈ ✈",
]


@pytest.mark.parametrize("text", _UNICODE_SAMPLES)
def test_no_crash_valid_result_on_arbitrary_unicode(text):
    r = InputGuard().analyze(text)
    assert r.status in _VALID_STATUSES
    assert 0 <= r.clarity_score <= 100
    # A note exists exactly when the probe could not fully cover the input.
    if r.heuristic_coverage in (COVERAGE_FULL, COVERAGE_UNKNOWN):
        assert r.degradation_note is None
    else:
        assert r.degradation_note is not None
    if r.heuristic_coverage == COVERAGE_NONE:
        # Degraded path contract: rules skipped, honest intent, never ready.
        assert r.findings == []
        assert r.detected_intent == DEGRADED_INTENT
        assert r.status != "ready"


def test_long_input_bounded_probe_still_classifies():
    # ~100k chars: the stride sample keeps the probe bounded while still
    # classifying correctly. The clarity verdict is unchanged v0.2
    # behavior for the repeated build request (missing language + api
    # structure -> 100 - 25 - 25 = 50).
    r = InputGuard().analyze("build a rest api " * 6000)
    assert r.status == "needs_clarification"
    assert r.clarity_score == 50
    assert r.heuristic_coverage == COVERAGE_FULL
    assert r.degradation_note is None


def test_parallel_analyze_thread_safety_64_workers():
    # 64 workers over mixed English/Chinese inputs must agree with the
    # single-threaded results (the v0.2 thread-safety contract, rerun with
    # the probe in the pipeline).
    guard = InputGuard()
    strict = InputGuard(mode="strict")
    inputs = [
        "fix my code",
        PROBE_P2_INPUT,
        "Build a REST API using FastAPI. Store users in PostgreSQL.",
        "почему моя программа не работает",
        "make it faster 这个",
    ]
    expected = {text: guard.analyze(text).to_dict() for text in inputs}
    expected_strict = {PROBE_P2_INPUT: strict.analyze(PROBE_P2_INPUT).to_dict()}

    def run(pair):
        text, mode = pair
        target = strict if mode == "strict" else guard
        return text, mode, target.analyze(text).to_dict()

    jobs = [(text, "warning") for text in inputs for _ in range(12)] + [
        (PROBE_P2_INPUT, "strict") for _ in range(4)
    ]
    assert len(jobs) == 64
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(run, jobs))

    for text, mode, result in results:
        baseline = expected_strict if mode == "strict" else expected
        assert result == baseline[text]


# ---------------------------------------------------------------------------
# Accented-Latin and mixed-script coverage (eval rows DG-011..014)
#
# The share histogram alone calls French/Spanish/Portuguese "fully covered"
# (their letters are Latin) and calls a mixed English+Han prompt covered
# whenever the Han minority is small. Both are silent mis-coverage: the
# English-only heuristics cannot read a word of them. These tests pin the
# two refinements that close the gap and the English prompts they must not
# disturb.
# ---------------------------------------------------------------------------

FRENCH = "Crée une application web avec connexion utilisateur et tableau de bord"
SPANISH = "¿Por qué mi código se ejecuta tan lento y cómo puedo optimizarlo?"
PORTUGUESE = "Preciso de um aplicativo web com login de usuário e relatórios"
MIXED_ENGLISH_HAN = "Fix this bug 修复这个错误 in the payment flow"


def test_french_is_not_english_coverage():
    probe = probe_script(FRENCH)
    assert probe.dominant_script == "latin"
    assert probe.detected_language == "fr"
    assert probe.heuristic_coverage == COVERAGE_NONE


def test_spanish_is_not_english_coverage():
    probe = probe_script(SPANISH)
    assert probe.dominant_script == "latin"
    assert probe.detected_language == "es"
    assert probe.heuristic_coverage == COVERAGE_NONE


def test_portuguese_is_not_english_coverage():
    probe = probe_script(PORTUGUESE)
    assert probe.dominant_script == "latin"
    assert probe.detected_language == "pt"
    assert probe.heuristic_coverage == COVERAGE_NONE


def test_french_degrades_even_with_only_two_stop_words():
    # Zero English function-word evidence: two distinct French function
    # words already fire (_MIN_SOLO_HITS) — "Oui merci beaucoup pour ton
    # aide" must not pass as English just because it is stop-word light.
    probe = probe_script("Oui merci beaucoup pour ton aide")
    assert probe.detected_language == "fr"
    assert probe.heuristic_coverage == COVERAGE_NONE


def test_mixed_english_han_clause_is_degraded_by_run_length():
    probe = probe_script(MIXED_ENGLISH_HAN)
    assert probe.dominant_script == "latin"
    assert probe.detected_language == "en"  # majority English, honestly kept
    assert probe.heuristic_coverage == COVERAGE_NONE
    assert probe.uncovered_block_script == "han"
    assert probe.uncovered_block_length == 6


def test_two_letter_han_borrow_stays_full():
    # Boundary guard for the run rule: a 2-letter borrow rides along under
    # the English majority (the pinned "make it faster 这个" contract).
    probe = probe_script("optimize the query 支持")
    assert probe.detected_language == "en"
    assert probe.heuristic_coverage == COVERAGE_FULL


def test_three_letter_han_block_degrades():
    # A 3-letter uncovered run is a word the English heuristics cannot read.
    probe = probe_script("optimize the query 数据库")
    assert probe.heuristic_coverage == COVERAGE_NONE
    assert probe.uncovered_block_length == 3


def test_accented_english_loanwords_stay_full():
    probe = probe_script("Add a café section for José résumé page")
    assert probe.detected_language == "en"
    assert probe.heuristic_coverage == COVERAGE_FULL


def test_urls_and_hyphenated_words_stay_full():
    # Interior punctuation keeps "example.com" and "de-duplicate" whole —
    # neither may contribute a stray "com"/"de" lexicon hit.
    probe = probe_script("De-duplicate records from api.example.com and deploy")
    assert probe.detected_language == "en"
    assert probe.heuristic_coverage == COVERAGE_FULL


def test_english_function_words_block_lexicon_fire():
    # Collision-heavy but genuinely English: pour/DES/LA/Mon are scattered
    # collisions, and the dense English function-word evidence (the, into,
    # before) keeps the margin rule from firing.
    probe = probe_script("Pour the DES dump into LA storage before Mon")
    assert probe.detected_language == "en"
    assert probe.heuristic_coverage == COVERAGE_FULL


def test_unlisted_latin_language_stays_full():
    # Documented subset boundary: German is Latin script and not in the
    # lexicons — it passes as before rather than pretending to degrade.
    probe = probe_script("Ich möchte eine Webanwendung mit Benutzeranmeldung")
    assert probe.detected_language == "en"
    assert probe.heuristic_coverage == COVERAGE_FULL


def test_latin_language_probe_is_deterministic():
    assert probe_script(FRENCH) == probe_script(FRENCH)
    assert probe_script(MIXED_ENGLISH_HAN) == probe_script(MIXED_ENGLISH_HAN)


def test_latin_language_degrades_end_to_end_like_other_uncovered_languages():
    # The DG-001..010 contract, now for the accented-Latin rows: explicit
    # note, no silent ready, rules skipped, undetermined intent, no gaps.
    for text, language in ((FRENCH, "fr"), (SPANISH, "es"), (PORTUGUESE, "pt")):
        r = InputGuard().analyze(text)
        assert r.heuristic_coverage == COVERAGE_NONE, text
        assert r.detected_language == language, text
        assert r.degradation_note is not None, text
        assert r.status == "usable_with_warnings", text
        assert r.detected_intent == DEGRADED_INTENT, text
        assert r.gaps == [], text
        assert r.clarity_score == 100 - DEGRADATION_PENALTY, text


def test_spanish_no_longer_returns_silent_ready():
    # DG-012's specific regression: v0.3-before-this-fix answered ready/100
    # with zero findings on Spanish input.
    r = InputGuard().analyze(SPANISH)
    assert r.status != "ready"
    assert r.clarity_score != 100
    assert not r.is_clear()


def test_french_degrades_in_strict_mode_too():
    r = InputGuard(mode="strict").analyze(FRENCH)
    assert r.status == "needs_clarification"
    assert r.degradation_note is not None


def test_mixed_english_han_degrades_end_to_end():
    r = InputGuard().analyze(MIXED_ENGLISH_HAN)
    assert r.heuristic_coverage == COVERAGE_NONE
    assert r.degradation_note is not None
    assert r.status == "usable_with_warnings"
    assert r.detected_intent == DEGRADED_INTENT
    assert r.gaps == []


def test_french_note_names_the_language():
    note = InputGuard().analyze(FRENCH).degradation_note
    assert "French" in note
    assert "fr" in note
    assert "English" in note


def test_mixed_note_names_the_uncovered_run():
    note = InputGuard().analyze(MIXED_ENGLISH_HAN).degradation_note
    assert "han" in note
    assert "6" in note
    assert "English" in note


def test_all_fourteen_degradation_rows_meet_the_dg_rubric():
    # The acceptance sweep for DG-001..014 (labeling guide rubric: explicit
    # degradation note, never a silent ready, no rule firing on vocabulary
    # the heuristics cannot read). Labels come straight from eval/cases.csv.
    import csv
    from pathlib import Path

    cases = Path(__file__).resolve().parent.parent / "eval" / "cases.csv"
    with cases.open(newline="", encoding="utf-8") as handle:
        dg_rows = [row for row in csv.DictReader(handle) if row["id"].startswith("DG-")]
    assert len(dg_rows) == 14

    guard = InputGuard()
    for row in dg_rows:
        result = guard.analyze(row["text"], domain=row["domain"])
        assert result.degradation_note, row["id"]
        assert result.status != "ready", row["id"]
        assert result.heuristic_coverage != COVERAGE_FULL, row["id"]
        assert result.gaps == [], row["id"]
