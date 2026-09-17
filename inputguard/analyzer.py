from __future__ import annotations

import re
from typing import List, Optional, Set

import inputguard.rules  # noqa: F401 — importing registers the coding domain and the 19 built-in rules
from inputguard.detector import detect_intent, normalize
from inputguard.followups import get_follow_ups
from inputguard.language import (
    COVERAGE_NONE,
    COVERAGE_PARTIAL,
    DEGRADATION_PENALTY,
    DEGRADED_INTENT,
    DEGRADED_STATUS,
    degradation_note_for,
    partial_coverage_note,
    probe_script,
)
from inputguard.policy import Policy
from inputguard.recommender import get_recommendations
from inputguard.registry import REGISTRY
from inputguard.scorer import (
    calculate_score_with_breakdown,
    get_status,
    require_known_severity,
)
from inputguard.types import AnalysisResult, RuleFinding


_VALID_MODES = {"warning", "strict"}
# The one built-in rule that flags input as vague. Policy.min_words gates it:
# below the floor, input is valid-but-short — never "vague" (spec art_bTvdPdJS §2).
_VAGUE_RULE_ID = "insufficient_context"
_INTERPRETATION_NOTE = (
    "This input is ambiguous in multiple ways. Addressing each gap below "
    "before sending will prevent the AI from making assumptions that lead "
    "to the wrong output."
)


class InputGuard:
    """The clarity engine: ``analyze(user_input, domain=...) -> AnalysisResult``.

    ``mode`` selects the status banding (warning never blocks, strict does).
    ``policy`` is optional :class:`~inputguard.Policy` calibration — status
    bands, severity penalties, rule filters, and the input cap. It defaults to
    the v0.2 constants; every guard and every ``analyze()`` call may carry its
    own (a per-call ``policy`` overrides the guard's).
    """

    def __init__(self, mode: str = "warning", policy: Optional[Policy] = None) -> None:
        if mode not in _VALID_MODES:
            raise ValueError(
                f"Invalid mode: {mode!r}. Expected one of: 'warning', 'strict'."
            )
        if policy is not None and not isinstance(policy, Policy):
            raise TypeError(
                f"policy must be a Policy instance, got {type(policy).__name__}."
            )
        self.mode = mode
        self.policy: Policy = Policy() if policy is None else policy

    def analyze(
        self,
        user_input: str,
        domain: str = "coding",
        policy: Optional[Policy] = None,
    ) -> AnalysisResult:
        if not isinstance(user_input, str):
            raise TypeError(
                f"user_input must be a string, got {type(user_input).__name__}."
            )
        if not user_input.strip():
            raise ValueError("user_input must be a non-empty, non-whitespace string.")
        if policy is not None and not isinstance(policy, Policy):
            raise TypeError(
                f"policy must be a Policy instance, got {type(policy).__name__}."
            )

        effective_policy = self.policy if policy is None else policy

        # Enforce the input cap: analysis is bounded, always. Truncation is
        # visible on the result (AnalysisResult.truncated), never silent.
        max_chars = effective_policy.max_chars
        truncated = len(user_input) > max_chars
        if truncated:
            user_input = user_input[:max_chars]

        domain_signals = REGISTRY.get_domain_signals(domain)
        normalized = normalize(user_input)

        # Language probe (pipeline step 2): classify the input's script before
        # any rule runs, so scripts outside heuristic coverage take the
        # explicit degradation path instead of silently passing as ready.
        probe = probe_script(normalized)
        if probe.heuristic_coverage == COVERAGE_NONE:
            # English-only rules are skipped outright — running them on input
            # they cannot assess (another script, mixed scripts, or non-
            # English Latin wording) would produce a silent, unearned ready
            # or spurious gaps invented out of the silence. The status is the
            # literal "degraded" in both modes: the result reports a language
            # limitation of the tool, not an ordinary vagueness verdict. The
            # truncation flag is preserved so a capped input degraded by the
            # probe still says so.
            score = max(0, 100 - DEGRADATION_PENALTY)
            return AnalysisResult(
                status=DEGRADED_STATUS,
                clarity_score=score,
                detected_intent=DEGRADED_INTENT,
                gaps=[],
                recommendations=[],
                findings=[],
                interpretation_note=None,
                detected_language=probe.detected_language,
                heuristic_coverage=probe.heuristic_coverage,
                degradation_note=degradation_note_for(probe),
                truncated=truncated,
            )

        detected_intent = detect_intent(user_input, domain_signals)

        findings: List[RuleFinding] = []
        seen_codes: Set[str] = set()
        if not _matches_allow_pattern(user_input, effective_policy):
            word_count = len(normalized.split())
            for rule in REGISTRY.rules_for_intent(detected_intent):
                if rule.id in effective_policy.disabled_rules:
                    continue
                if rule.id == _VAGUE_RULE_ID and word_count < effective_policy.min_words:
                    continue
                try:
                    finding = rule.check(normalized)
                except Exception as exc:
                    # Loud failure with attribution (review C2-lite): a rule
                    # exception is never swallowed or silently degraded around —
                    # it aborts analyze(), naming the rule and where it was
                    # registered, with the original traceback chained.
                    raise RuntimeError(
                        f"inputguard rule {rule.id!r} "
                        f"(registered {REGISTRY.rule_origin(rule.id)}) raised "
                        f"{type(exc).__name__}: {exc}. A rule exception aborts "
                        f"analyze() by design — rules are the author's "
                        f"responsibility after registration; fix or remove the rule."
                    ) from exc
                if finding is None:
                    continue
                # C5 choke point: every emitted finding's severity must be in
                # the same Policy-owned vocabulary registration validated.
                require_known_severity(finding.severity)
                if finding.code in seen_codes:
                    continue
                seen_codes.add(finding.code)
                findings.append(finding)

        score, breakdown = calculate_score_with_breakdown(findings, effective_policy)
        status = get_status(score, self.mode, effective_policy)
        # Two layers: severity decided what fired; the policy's bands decide
        # what happens. The borderline band is the near-miss signal just below
        # ready — distinct "worth one more pass" messaging (spec art_bTvdPdJS).
        borderline = effective_policy.borderline_at <= score < effective_policy.ready_at

        gaps: List[str] = []
        seen: Set[str] = set()
        for f in findings:
            if f.gap is not None and f.gap not in seen:
                gaps.append(f.gap)
                seen.add(f.gap)

        recommendations = get_recommendations(gaps)
        # Slot fills read the original input (case preserved); rules ran on
        # the normalized text, question extraction does not need to.
        follow_ups = get_follow_ups(gaps, user_input)

        high_count = sum(1 for f in findings if f.severity == "high")
        interpretation_note = None
        if score < 50 or high_count >= 2:
            interpretation_note = _INTERPRETATION_NOTE

        return AnalysisResult(
            status=status,
            clarity_score=score,
            detected_intent=detected_intent,
            gaps=gaps,
            recommendations=recommendations,
            findings=findings,
            interpretation_note=interpretation_note,
            follow_ups=follow_ups,
            detected_language=probe.detected_language,
            heuristic_coverage=probe.heuristic_coverage,
            degradation_note=(
                partial_coverage_note(probe)
                if probe.heuristic_coverage == COVERAGE_PARTIAL
                else None
            ),
            borderline=borderline,
            truncated=truncated,
            score_breakdown=breakdown,
        )


def _matches_allow_pattern(text: str, policy: Policy) -> bool:
    """True when the analyzed input matches any allowlist pattern — such input is never flagged."""
    return any(re.search(pattern, text) for pattern in policy.allow_patterns)
