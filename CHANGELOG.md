# Changelog

## [0.1.2] — 2026-05-28
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