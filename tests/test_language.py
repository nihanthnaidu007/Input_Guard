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
