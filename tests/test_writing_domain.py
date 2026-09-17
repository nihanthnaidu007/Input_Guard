"""First-party writing domain tests.

Five layers, matching the acceptance criteria:

- per-rule behavior: each of the six writing rules fires on a gap-bearing
  writing prompt and stays silent when that gap is satisfied (or when the
  prompt is not a writing task at all);
- the writing-domain completeness invariant: every registered writing gap
  has a four-key recommendation entry and one or two curated follow-up
  questions, and the intent the rules bind to ("compose") is globally
  unique — no coding intent reuses it;
- analyze() integration end to end: an underspecified writing prompt comes
  back needs_clarification with the right gaps, severities, score, and
  follow-ups; a fully specified one comes back ready;
- no leakage in either direction, at the registry level and through the
  public analyze() path: writing codes never appear in coding analyses and
  coding codes never appear in writing ones;
- the labeled English writing rows in eval/cases.csv match their labels —
  the domain's calibration net. (The FP/FN measurement harness stays the
  source of truth for rates; this pins the rows the gap_vocabulary sheet
  defines.)

All existing tests are untouched — this file only adds.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from inputguard import InputGuard
from inputguard.followups import _FOLLOW_UP_QUESTIONS
from inputguard.recommender import _RECOMMENDATIONS
from inputguard.registry import REGISTRY
from inputguard.rules.writing import (
    WRITING_GAPS,
    WRITING_RULES,
    check_missing_audience,
    check_missing_completeness,
    check_missing_purpose,
    check_missing_source_material,
    check_missing_structure_format,
    check_missing_writing_context,
    run_writing_rules,
)

EVAL_CASES = Path(__file__).resolve().parent.parent / "eval" / "cases.csv"


# --- per-rule behavior: fires on the gap, silent when satisfied --------------


@pytest.mark.parametrize(
    "check, fires_on, silent_on",
    [
        (
            check_missing_audience,
            "Write a blog post about remote work",
            "Write a blog post about remote work for the engineering team",
        ),
        (
            check_missing_purpose,
            "Write a blog post about remote work",
            "Write a blog post announcing our new remote-work policy",
        ),
        (
            check_missing_structure_format,
            "Write a blog post about remote work",
            "Write a short blog post about remote work",
        ),
        # Fires only when existing material is referenced but not provided;
        # a rewrite-with-text (gap satisfied) and a bare drafting prompt
        # (no trigger) are both silent.
        (
            check_missing_source_material,
            "Rewrite my resume summary",
            "Rewrite the resume summary I pasted below",
        ),
        (
            check_missing_writing_context,
            "Write something short for tomorrow",
            "Write a blog post about remote work",
        ),
        (
            check_missing_completeness,
            "Write a blog post about remote work",
            "Write a blog post about remote work and include the headline stat",
        ),
    ],
)
def test_rule_fires_on_gap_and_stays_silent_when_satisfied(check, fires_on, silent_on):
    finding = check(fires_on)
    assert finding is not None, f"{check.__name__} must fire on {fires_on!r}"

    assert check(silent_on) is None, f"{check.__name__} must stay silent on {silent_on!r}"


def test_not_a_writing_task_produces_no_findings():
    # Coding prompts analyzed in the writing domain (a user error) must not
    # produce misleading writing findings — the writing-task gate blocks
    # every rule.
    for text in (
        "fix the login crash",
        "my endpoint returns 500 instead of 200",
        "explain async",
    ):
        assert run_writing_rules(text) == [], f"expected no findings for {text!r}"


def test_every_writing_rule_binds_to_the_compose_intent_with_vocab_severity():
    # The gap_vocabulary sheet pins the severities; the intent must be
    # "compose" for every rule (the single fallback intent).
    expected = {
        "missing_audience": "high",
        "missing_purpose": "high",
        "missing_structure_format": "medium",
        "missing_source_material": "high",
        "missing_writing_context": "medium",
        "missing_completeness": "low",
    }
    for rule in WRITING_RULES:
        assert rule.domain == "compose"
        assert rule.severity == expected[rule.id]
        assert rule.gap is not None


# --- the writing-domain completeness invariant ------------------------------


def _writing_registry_rules():
    writing_ids = {rule.id for rule in WRITING_RULES}
    return [r for r in REGISTRY.rules() if r.id in writing_ids]


def test_every_registered_writing_rule_has_a_recommendation_and_follow_ups():
    # Mirrors the global invariant in test_followups.py, scoped to the
    # writing domain: a writing rule can ship only with complete advice.
    for rule in _writing_registry_rules():
        assert rule.gap in _RECOMMENDATIONS, f"gap {rule.gap!r} has no recommendation entry"
        assert rule.gap in _FOLLOW_UP_QUESTIONS, f"gap {rule.gap!r} has no follow-up question"
        assert 1 <= len(_FOLLOW_UP_QUESTIONS[rule.gap]) <= 2


def test_writing_gap_set_matches_the_domain_vocabulary():
    # The six gaps the eval set's gap_vocabulary sheet defines for writing
    # are exactly what the rules declare — no more, no fewer.
    declared = {rule.gap for rule in _writing_registry_rules()}
    assert declared == set(WRITING_GAPS)


def test_compose_intent_is_globally_unique():
    # PR #8 contract: intent names are globally unique across domains. No
    # coding intent may collide with the writing domain's single intent.
    for intent in ("build", "debug", "optimization", "explanation", "feature"):
        ids = [r.id for r in REGISTRY.rules_for_intent(intent)]
        assert not writing_ids_in(ids), f"writing rules leaked into intent {intent!r}"


def writing_ids_in(ids):
    writing_ids = {rule.id for rule in WRITING_RULES}
    return [i for i in ids if i in writing_ids]


def test_rules_for_compose_are_exactly_the_writing_rules():
    assert {r.id for r in REGISTRY.rules_for_intent("compose")} == {
        rule.id for rule in WRITING_RULES
    }


# --- analyze() integration, end to end ---------------------------------------


def test_underspecified_writing_prompt_end_to_end():
    result = InputGuard().analyze("Write a blog post about remote work", domain="writing")

    assert result.status == "needs_clarification"
    assert result.detected_intent == "compose"
    assert set(result.gaps) == {"audience", "purpose", "structure/format", "completeness"}
    # 100 - 25 (audience, high) - 25 (purpose, high) - 15 (structure,
    # medium) - 5 (completeness, low) = 30.
    assert result.clarity_score == 30
    severity_by_gap = {f.gap: f.severity for f in result.findings}
    assert severity_by_gap == {
        "audience": "high",
        "purpose": "high",
        "structure/format": "medium",
        "completeness": "low",
    }
    # Advice and follow-ups are complete: one four-key recommendation and
    # at least one question per gap, in gap order.
    assert [r["gap"] for r in result.recommendations] == result.gaps
    for rec in result.recommendations:
        assert set(rec) == {"gap", "what_is_missing", "what_to_provide", "why_it_matters"}
    assert len(result.follow_ups) >= len(result.gaps)
    assert all(q.endswith("?") for q in result.follow_ups)
    # English input: no degradation, honest full coverage.
    assert result.detected_language == "en"
    assert result.heuristic_coverage == "full"
    assert result.degradation_note is None


def test_fully_specified_writing_prompt_is_ready():
    text = (
        "Turn my bullet outline into a full proposal for the steering "
        "committee; goal is to win headcount for Q1; include budget, risks, "
        "and milestones; the outline is at the bottom"
    )
    result = InputGuard().analyze(text, domain="writing")

    assert result.status == "ready"
    assert result.clarity_score == 100
    assert result.gaps == []
    assert result.findings == []
    assert result.follow_ups == []


def test_partially_specified_writing_prompt_lands_in_warning_band():
    # Audience, purpose, and context are present; length/organization and
    # required content are not. 100 - 15 (structure, medium) - 5
    # (completeness, low) = 80 -> usable_with_warnings in warning mode.
    result = InputGuard().analyze(
        "Write an email to the engineering team announcing the Q3 roadmap",
        domain="writing",
    )

    assert result.status == "usable_with_warnings"
    assert result.clarity_score == 80
    assert set(result.gaps) == {"structure/format", "completeness"}


# --- no leakage, either direction --------------------------------------------


def test_coding_analyses_never_emit_writing_codes():
    guard = InputGuard()
    for text in (
        "Write a blog post about remote work",
        "Rewrite my resume summary",
        "Write a short email to my team explaining why the deadline moved",
    ):
        result = guard.analyze(text)  # default domain: coding
        assert writing_ids_in(f.code for f in result.findings) == [], (
            f"writing codes leaked into a coding analysis of {text!r}"
        )


def test_writing_analyses_never_emit_coding_codes():
    coding_codes = {rule.id for rule in REGISTRY.rules_for_intent("build",)} | {
        rule.id
        for intent in ("build", "debug", "optimization", "explanation", "feature")
        for rule in REGISTRY.rules_for_intent(intent)
    }
    guard = InputGuard()
    for text in (
        "fix the login crash",
        "make this faster",
        "add auth to my app",
        "explain async",
    ):
        result = guard.analyze(text, domain="writing")
        leaked = [f.code for f in result.findings if f.code in coding_codes]
        assert leaked == [], f"coding codes leaked into a writing analysis of {text!r}"


# --- the labeled eval rows (calibration net) ---------------------------------


def _writing_eval_rows():
    with open(EVAL_CASES, newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row["domain"] == "writing"]
    assert rows, "eval/cases.csv must contain writing rows"
    return rows


def _parse_multi_value(raw: str):
    """Split a ``;``-separated eval field; ``none``/``n/a`` mean no entries."""
    value = (raw or "").strip()
    if value.lower() in {"none", "n/a", ""}:
        return []
    return [part.strip() for part in value.split(";") if part.strip()]


@pytest.mark.parametrize("row", _writing_eval_rows(), ids=lambda row: row["id"])
def test_labeled_writing_rows_match_their_labels(row):
    guard = InputGuard()
    result = guard.analyze(row["text"], domain="writing")

    expected_gaps = _parse_multi_value(row["expected_gaps"])
    expected_severities = _parse_multi_value(row["expected_severities"])

    assert set(result.gaps) == set(expected_gaps), (
        f"{row['id']}: gap set mismatch on {row['text']!r}"
    )
    assert result.status == row["expected_status"], (
        f"{row['id']}: status mismatch on {row['text']!r}"
    )
    severity_by_gap = {f.gap: f.severity for f in result.findings}
    for gap, severity in zip(expected_gaps, expected_severities):
        assert severity_by_gap.get(gap) == severity, (
            f"{row['id']}: severity mismatch for gap {gap!r} on {row['text']!r}"
        )
