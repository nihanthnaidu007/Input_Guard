# Changelog

## [Unreleased]
### Added
- Multilingual degradation: a zero-dependency script probe
  (`unicodedata`-based histogram, `inputguard/language.py`) classifies
  each input's script before rules run. Scripts without English
  heuristic coverage take an explicit degraded path — rules are skipped,
  a 20-point confidence penalty applies, and the result carries
  `detected_language`, `heuristic_coverage`, and `degradation_note`
  instead of silently scoring 100/ready.
- Additive `AnalysisResult` fields: `detected_language`,
  `heuristic_coverage`, `degradation_note` (included in `to_dict()`).
- Mixed-script input: rules run whenever the covered share of letters is
  at least 50%, with a `partial` note between 50–70% coverage.
- Accented-Latin honesty (eval DG-011..014): French, Spanish, and
  Portuguese input no longer passes as silently covered — a function-word
  layer degrades them like any other uncovered language, and a run of 3+
  consecutive uncovered-script letters (mixed English+Han) degrades even
  majority-English input. English prompts (loanwords, URLs, name and
  timezone collisions) are pinned unchanged by tests.

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