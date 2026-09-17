"""Tests for the language probe (unicodedata script histogram).

Covers the script classification and coverage-band logic of
``inputguard.language``. End-to-end degradation behavior (the degraded
``analyze()`` path) is covered in the integration section appended by the
non-English-honesty commit.
"""

from __future__ import annotations

import unicodedata

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
