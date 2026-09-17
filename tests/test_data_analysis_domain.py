"""First-party data-analysis domain: rule behavior, vocabulary completeness,
eval-set alignment, and cross-domain leakage guards.

The six rules follow the pinned eval vocabulary (eval/cases.csv,
gap_vocabulary): dataset/source, question/goal, output format, tooling,
volume, reproducibility. The eval-alignment tests read the versioned CSV
labels directly, so any future label edit keeps these tests honest.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, FrozenSet, List

import pytest

from inputguard import InputGuard
from inputguard.followups import _FOLLOW_UP_QUESTIONS
from inputguard.recommender import _RECOMMENDATIONS
from inputguard.registry import REGISTRY
from inputguard.rules.data_analysis import (
    DATA_ANALYSIS_RULES,
    DATA_ANALYSIS_SIGNALS,
    MissingDatasetSourceRule,
    MissingDeliverableFormatRule,
    MissingQuestionGoalRule,
    MissingReproducibilityRule,
    MissingToolingRule,
    MissingVolumeRule,
)

# The registry name follows the eval corpus: cases.csv names the domain
# "data-analysis" and the harness passes it verbatim to analyze().
DOMAIN = "data-analysis"

# The six built-in data-analysis rule ids, by gap.
_GAP_TO_RULE = {
    "dataset/source": MissingDatasetSourceRule,
    "question/goal": MissingQuestionGoalRule,
    "output format": MissingDeliverableFormatRule,
    "tooling": MissingToolingRule,
    "volume": MissingVolumeRule,
    "reproducibility": MissingReproducibilityRule,
}

DA_RULE_IDS: FrozenSet[str] = frozenset(rule.id for rule in DATA_ANALYSIS_RULES)
DA_GAPS: FrozenSet[str] = frozenset(_GAP_TO_RULE)


def _eval_da_cases() -> List[Dict[str, str]]:
    """The versioned data-analysis rows of the eval corpus."""
    path = Path(__file__).resolve().parent.parent / "eval" / "cases.csv"
    with open(path, newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row["domain"] == DOMAIN]
    assert len(rows) == 15, "the eval corpus should carry 15 data-analysis cases"
    return rows


_NONE_SENTINELS = {"none", "n/a", ""}


def _split_multi(value: str) -> List[str]:
    """Parse a semicolon-joined multi-value column, as the harness does.

    ``none``/``n/a``/empty mean no entries (eval/measure_fp.py).
    """
    stripped = value.strip()
    if stripped.lower() in _NONE_SENTINELS:
        return []
    return [part.strip() for part in stripped.split(";") if part.strip()]


# --- registration -------------------------------------------------------------


def test_data_analysis_domain_registered():
    assert "data-analysis" in REGISTRY.domain_names()
    assert DA_RULE_IDS <= set(REGISTRY.rule_ids())


def test_domain_signals_have_two_intents_with_reference_fallback():
    chain = REGISTRY.get_domain_signals(DOMAIN)
    assert [intent for intent, _ in chain] == ["analysis", "reference"]
    assert [terms for _, terms in chain if not terms] == [()]


def test_data_analysis_signals_shape():
    intents = [intent for intent, _ in DATA_ANALYSIS_SIGNALS]
    assert intents[0] == "analysis"
    assert len(DATA_ANALYSIS_SIGNALS) == 2
    assert DATA_ANALYSIS_SIGNALS[-1] == ("reference", ())


def test_every_data_analysis_rule_scopes_to_the_analysis_intent():
    for rule in DATA_ANALYSIS_RULES:
        assert rule.domain == "analysis"


# --- per-rule fire / silence ----------------------------------------------------


@pytest.mark.parametrize(
    ("rule_id", "prompt", "gap", "severity"),
    [
        # Each prompt satisfies the other five gaps so exactly one rule fires.
        (
            "missing_dataset_source",
            "Analyze the churn patterns for the board, deliver a summary "
            "slide, using pandas in python, about 80,000 rows, and we rerun "
            "it weekly.",
            "dataset/source",
            "high",
        ),
        (
            "missing_question_goal",
            "Analyze the attached export and deliver a summary chart, using "
            "pandas, about 80,000 rows, rerun weekly.",
            "question/goal",
            "high",
        ),
        (
            "missing_deliverable_format",
            "Analyze the attached export to see whether churn improved, "
            "using pandas, about 80,000 rows, rerun weekly.",
            "output format",
            "medium",
        ),
        (
            "missing_tooling",
            "Analyze the attached export to see whether churn improved and "
            "deliver a summary chart, about 80,000 rows, rerun weekly.",
            "tooling",
            "medium",
        ),
        (
            "missing_volume",
            "Analyze the attached export to see whether churn improved, "
            "deliver a summary chart, using pandas, rerun weekly.",
            "volume",
            "low",
        ),
        (
            "missing_reproducibility",
            "Analyze the attached export to see whether churn improved, "
            "deliver a summary chart, using pandas, about 80,000 rows.",
            "reproducibility",
            "low",
        ),
    ],
)
def test_each_rule_fires_isolated(prompt, rule_id, gap, severity):
    result = InputGuard().analyze(prompt, domain=DOMAIN)
    assert result.gaps == [gap]
    finding = next(f for f in result.findings if f.code == rule_id)
    assert finding.severity == severity
    assert finding.gap == gap


@pytest.mark.parametrize(
    ("rule_cls", "satisfying_suffix"),
    [
        (MissingDatasetSourceRule, "in the attached postgres export"),
        (MissingQuestionGoalRule, "to find why CSAT dropped"),
        (MissingDeliverableFormatRule, "and deliver a summary chart"),
        (MissingToolingRule, "using pandas in python"),
        (MissingVolumeRule, "on about 80,000 rows"),
        (MissingReproducibilityRule, "and we rerun it weekly"),
    ],
)
def test_each_rule_stays_silent_when_gap_satisfied(rule_cls, satisfying_suffix):
    rule = rule_cls()
    finding = rule.check("analyze my sales data " + satisfying_suffix)
    assert finding is None


def test_boundary_safe_matching_on_satisfy_side():
    # "exporter" is not "export": the word-boundary matcher must not read it
    # as a named data source. Rule-level check keeps the assertion precise.
    assert MissingDatasetSourceRule().check("analyze the exporter metrics") is not None
    # The plain word still satisfies.
    assert MissingDatasetSourceRule().check("analyze the export metrics") is None


def test_volume_regexes_cover_labeled_scale_forms():
    rule = MissingVolumeRule()
    for text in (
        "analyze the attached export, about 80,000 rows, rerun weekly",
        "analyze 400m rows of clickstream",
        "analyze 90 days of data in the warehouse",
        "analyze two weeks of beacons from the warehouse",
    ):
        assert rule.check(text) is None, text


# --- eval-set alignment -----------------------------------------------------------


@pytest.mark.parametrize("row", _eval_da_cases(), ids=lambda row: row["id"])
def test_eval_alignment(row):
    result = InputGuard().analyze(row["text"], domain=DOMAIN)
    expected_gaps = set(_split_multi(row["expected_gaps"]))
    expected_status = row["expected_status"]
    assert set(result.gaps) == expected_gaps, row["id"]
    assert result.status == expected_status, row["id"]


def test_eval_severities_match_pinned_vocabulary():
    for row in _eval_da_cases():
        if not _split_multi(row["expected_severities"]):
            continue
        result = InputGuard().analyze(row["text"], domain=DOMAIN)
        actual = {f.severity for f in result.findings}
        assert actual == set(_split_multi(row["expected_severities"])), row["id"]


# --- registry completeness invariant (domain-specific) -----------------------------


def test_every_data_analysis_gap_has_a_recommendation():
    for rule in DATA_ANALYSIS_RULES:
        assert rule.gap in _RECOMMENDATIONS, rule.id
        entry = _RECOMMENDATIONS[rule.gap]
        assert set(entry) == {"gap", "what_is_missing", "what_to_provide", "why_it_matters"}
        assert entry["gap"] == rule.gap


def test_every_data_analysis_gap_has_follow_up_questions():
    for rule in DATA_ANALYSIS_RULES:
        questions = _FOLLOW_UP_QUESTIONS[rule.gap]
        assert 1 <= len(questions) <= 2, rule.id
        for question in questions:
            assert question.endswith("?"), (rule.id, question)
        # At least one slot-free template: it renders on any input.
        assert any("{" not in q for q in questions), rule.id


def test_rule_severities_match_pinned_vocabulary():
    path = Path(__file__).resolve().parent.parent / "eval" / "cases.csv"
    # The gap vocabulary's default severities are pinned by the workbook; the
    # eval corpus rows carry the same per-gap severities.
    with open(path, newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row["domain"] == DOMAIN]
    for row in rows:
        gaps = _split_multi(row["expected_gaps"])
        severities = _split_multi(row["expected_severities"])
        for gap, severity in zip(gaps, severities):
            rule = _GAP_TO_RULE[gap]
            assert rule.severity == severity, (row["id"], gap)


# --- analyze() integration -----------------------------------------------------------


def test_underspecified_analysis_prompt_end_to_end():
    result = InputGuard().analyze("Analyze my sales data", domain=DOMAIN)
    assert result.detected_intent == "analysis"
    assert set(result.gaps) == DA_GAPS
    assert result.status == "needs_clarification"
    assert result.clarity_score == 10  # 100 - (25 + 25 + 15 + 15 + 5 + 5)
    # Recommendations cover each gap, in order.
    assert [rec["gap"] for rec in result.recommendations] == result.gaps
    assert all(set(rec) == {"gap", "what_is_missing", "what_to_provide", "why_it_matters"} for rec in result.recommendations)
    # Follow-ups cover every gap.
    assert len(result.follow_ups) >= len(result.gaps)
    assert all(q.endswith("?") for q in result.follow_ups)


def test_to_dict_round_trips_as_json():
    result = InputGuard().analyze("Analyze my sales data", domain=DOMAIN)
    payload = json.dumps(result.to_dict())
    assert json.loads(payload)["clarity_score"] == result.clarity_score


def test_reference_intent_clears_without_findings():
    result = InputGuard().analyze("What is a p-value?", domain=DOMAIN)
    assert result.detected_intent == "reference"
    assert result.findings == []
    assert result.status == "ready"


# --- no-leakage guards ----------------------------------------------------------------


def test_data_analysis_rules_never_fire_in_coding_analyses():
    result = InputGuard().analyze(
        "Build a REST API using FastAPI. Store users in PostgreSQL with "
        "fields for name and email. Add email and password login.",
        domain="coding",
    )
    fired = {f.code for f in result.findings}
    assert fired & DA_RULE_IDS == set()


def test_coding_rules_never_fire_in_data_analysis_analyses():
    coding_ids = set(REGISTRY.rule_ids()) - DA_RULE_IDS
    result = InputGuard().analyze("Analyze my sales data", domain=DOMAIN)
    fired = {f.code for f in result.findings}
    assert fired <= DA_RULE_IDS
    assert fired & coding_ids == set()


def test_vague_coding_request_stays_a_coding_result():
    # A vague prompt sent to the coding domain must get coding behavior,
    # not data-analysis rules.
    result = InputGuard().analyze("Analyze my sales data", domain="coding")
    fired = {f.code for f in result.findings}
    assert fired & DA_RULE_IDS == set()
    assert fired  # the coding build rules still do their job
