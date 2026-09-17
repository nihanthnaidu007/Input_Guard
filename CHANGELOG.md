# Changelog

## [0.3.0] — 2026-09-17
The extension release: register your own rules and domains, get follow-up
questions for every gap, calibrated policy control, and honest behavior on
non-English input. Evaluated at **116 of 121** cases on the versioned
clarity-evaluation set in `eval/`; the 5 residual mismatches are documented
in `docs/false-positive-benchmark.md`.

### Added
- Typed `Rule` protocol and in-process registry (`#3`): first-party and
  third-party rules enter through the same path; unknown severities fail
  loudly at score time instead of being swallowed.
- Registry contract enforcement (`#8`): rules must expose a `check(text)`
  signature, unique `(intent, id)` pairs, and pass registration guards —
  a mis-registered rule aborts instead of silently never firing.
- Per-gap follow-up questions engine (`#4`): every built-in gap carries one
  or two templated clarifying questions, surfaced on the result as the
  additive `follow_ups` field. `{function}` / `{dataset}` slots fill from
  the original input; a gap with no table entry still gets the documented
  fallback question — never silence.
- Policy calibration (`#9`): a frozen, validated `Policy` with the v0.2
  constants as defaults — status bands, severity penalties, rule filters,
  `min_words`, allowlist patterns, and the 10,000-character input cap with
  a visible `truncated` flag — plus a per-result `score_breakdown`.
- First-party writing domain (`#10`): six rules, the `compose` intent,
  recommendations, and follow-ups for essay/report/email prompts.
- First-party data-analysis domain (`#11`): six rules (dataset/source,
  question/goal, deliverable format, tooling, volume, reproducibility),
  the `analysis` intent, recommendations, and follow-ups.
- The 121-case clarity-evaluation set, versioned as `eval/` (`#7`), with a
  measured false-positive benchmark in `docs/false-positive-benchmark.md`.
- Multilingual degradation (`#5`, `#12`): a zero-dependency script probe
  (unicodedata histogram, `inputguard/language.py`) classifies each input
  before rules run. Inputs the English heuristics cannot assess take an
  explicit degraded path — rules skipped, a 20-point confidence penalty,
  `detected_language`, `heuristic_coverage`, `degradation_note`, and
  `detected_intent: undetermined` instead of spurious gaps or a silent
  100/ready. Four inputs degrade: uncovered dominant scripts, and — from
  `#12` — Latin-script text recognized as French/Spanish/Portuguese by a
  function-word layer with an English margin, and Latin-dominant text
  carrying a run of 3+ consecutive uncovered-script letters (mixed
  English+Han). English prompts with loanwords, URLs, or name collisions
  are pinned unchanged by tests.

### Changed
- All term matching now happens at word boundaries (`#6`) — detector and
  every rule module share one matcher, so "my_error" matches but "error"
  inside "terrorist" no longer counts as a mention.
- Degraded results report the literal `degraded` status in both modes.
  Mapping the degradation penalty through the ordinary banding returned
  `usable_with_warnings` / `needs_clarification`, reading as an ordinary
  vagueness verdict about the input; degradation is a language limitation
  of the tool and now says so.

### Fixed
- The dataset-filename regex behind the `{dataset}` follow-up slot (and the
  data-analysis dataset rule) backtracked its greedy span against every dot
  in a filename-like run — quadratic, measured at 13 ms per 1 K chars and
  1.3 s per 10 K. Both sites now scan maximal filename runs linearly with
  the extension checked in Python; 10 K now takes under a millisecond, and
  timing tests at 1 K and 10 K pin the growth rate.
- Degraded-path results preserve the `truncated` flag, so a capped input
  that also degrades reports both honestly.

## [0.2.0] — 2026-05-29
### Added
- Auto intent detection. `.analyze()` now detects whether the input
  is a build, debug, optimization, explanation, or feature request.
- `detected_intent` field on `AnalysisResult`.
- Debug rules: missing_error_message, missing_expected_vs_actual,
  missing_debug_code_context.
- Optimization rules: missing_optimization_target,
  missing_performance_baseline, missing_optimization_constraint.
- Explanation rules: missing_code_reference, missing_explanation_depth.
- Feature rules: missing_existing_stack, missing_feature_scope,
  missing_completion_criteria.
- 11 new plain English recommendations for all new gap types.
- 51 new tests across 5 new test files.
## [0.1.2] — 2026-05-27
### Fixed
- Short inputs of 3+ words with no recognizable patterns now correctly
  flagged instead of returning ready. "do something now" no longer
  returns score=100.
- Removed "do" from question_starters in catch-all so imperative
  sentences starting with "do" are no longer silently passed through.

## [0.1.1] — 2026-05-24
### Fixed
- Short inputs (3+ words) with no recognizable patterns now flagged
  by catch-all instead of returning ready.
- Added "use" to ACTION_VERBS. "use Stripe", "use Redis" now correctly
  flags missing language.
- Added "that lets" and "lets users" to intent pattern. "something that
  lets people upload photos" no longer returns ready.

## [0.1.0] — 2026-05-19
### Released
- Initial release. Phase 1 coding build input validation.
- Six core rules: missing_language, missing_api_structure,
  missing_data_model, missing_integration_specifics,
  missing_auth_type, missing_output_format.
- Two safety net rules: intent_without_language, insufficient_context.
- Warning and strict modes.
- Plain English recommendations for non-technical users.