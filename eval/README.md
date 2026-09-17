# eval/ — clarity evaluation set

A versioned checkpoint of the InputGuard v0.3 labeled clarity-evaluation set:
121 prompts with expected intent, gap set, status, and per-gap severities,
plus the labeling criteria and a stdlib-only measurement script.

Source of record: the "InputGuard v0.3 clarity-evaluation set" workbook
(sheets `cases`, `gap_vocabulary`) and its labeling guide in the Obvious
project. This directory is the git checkpoint of that dataset — it is what
the release-wave `docs/false-positive-benchmark.md` procedure consumes, and
what keeps the labels reviewable alongside the code they calibrate.

## Files

| File            | What it is                                                |
| --------------- | --------------------------------------------------------- |
| `cases.csv`     | All 121 labeled rows (schema below).                      |
| `measure_fp.py` | Runs the analyzer over every row, reports FP/FN rates.    |
| `README.md`     | This document: labeling criteria, rubric, how to measure. |

## `cases.csv` schema

Nine columns, UTF-8, all fields double-quoted, CRLF line endings:

| Column                | Meaning                                                                                                                                                                             |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`                  | Stable row id: `TP-…`, `TN-…`, `BD-…`, `DG-…`, `PF-…`. Unique across the file.                                                                                                       |
| `text`                | The prompt as a user would send it.                                                                                                                                                  |
| `domain`              | `coding`, `writing`, or `data-analysis` (the v0.3 first-party domains).                                                                                                              |
| `expected_intent`     | Intent the analyzer must detect; `n/a` when the label asserts no intent (all degradation/performance rows, plus writing/data-analysis rows, which carry no intent machinery yet).     |
| `expected_gaps`       | `;`-separated gap strings from the vocabulary below; `none` when no gap may fire.                                                                                                    |
| `expected_status`     | `ready`, `usable_with_warnings`, `needs_clarification`, or `degraded`.                                                                                                               |
| `expected_severities` | `;`-separated, positionally aligned with `expected_gaps`; `none` when there are no gaps.                                                                                             |
| `case_type`           | `true_positive`, `true_negative`, `boundary`, `degradation`, `performance`.                                                                                                          |
| `labeler_note`        | Why the row is labeled the way it is. Read it before re-labeling or "fixing" a row.                                                                                                  |

Row counts: 43 true positives, 37 true negatives, 25 boundary, 14
degradation, 2 performance. Domains: 92 coding, 14 writing, 15
data-analysis.

## How rows were labeled

- **Coding rows** (`true_positive`, `true_negative`, `boundary`):
  `expected_gaps` is the set of registry rules whose satisfaction signals
  the text genuinely lacks, using the 19 built-in rules plus the catch-all
  (`task context`). A true negative has zero such gaps by construction.
  Gap strings use the coding vocabulary verbatim (see table below).
- **Writing rows** use the spec's first-party vocabulary verbatim:
  `audience`, `purpose`, `structure/format`, `source material`, `context`,
  `completeness`. **Data-analysis rows** use `dataset/source`,
  `question/goal`, `output format`, `tooling`, `volume`, `reproducibility`.
- **Degradation rows** (`DG-001`…`DG-014`) cover Chinese, Japanese, Arabic,
  Hindi, Cyrillic, accented Latin, and one mixed English+Han prompt. They
  assert a non-null degradation note and a non-ready outcome — not an
  ordinary status band. `expected_status` is `degraded`,
  `expected_intent` is `n/a`.
- **Performance rows**: `PF-001` is 9,741 characters (under the 10,000-char
  cap), `PF-002` is 10,533 (over it). Both are filler with no rule signals,
  so the expected outcome isolates size handling from clarity scoring.

## Pass rubric per case_type

A row **passes** when the analyzer returns exactly: the expected intent
(when asserted), the expected status, and the expected gap set
(order-insensitive; no extra gaps, none missing).

- **true_positive** — must flag: status below `ready`, correct intent,
  expected gaps. The maximum severity per gap must match
  `expected_severities`.
- **true_negative** — must return `ready` with zero gaps and correct
  intent. Any flag on these rows is a false positive.
- **boundary** — read `labeler_note` first; it states which side the row
  guards. Fixture-style rows (BD-002/003/004/006/013/014) must return
  `ready` under word-boundary matching; under v0.2 substring matching all
  six flag — that is the regression being killed. BD-012 is the
  no-regression guard: a genuine debug request containing "fixture" must
  stay `intent=debug` with one medium `code context` gap at `ready`.
  BD-010 probes the catch-all: v0.2 misses it; v0.3 must report one high
  `task context` gap.
- **degradation** — the analyzer must return an explicit degradation note
  and NOT a `ready` status. Rule checks must not fire on Latin-only
  vocabulary assumptions.
- **performance** — `PF-001` must complete normally within the latency
  budget; `PF-002` must exercise the over-cap path (truncate-with-flag or
  reject) with no crash and bounded time. Wall time is recorded per row.

## Measuring

```bash
python3 eval/measure_fp.py              # full 121-row run, human-readable table
python3 eval/measure_fp.py --limit 10   # smoke run (used by tests/test_eval_loader.py)
python3 eval/measure_fp.py --json       # machine-readable summary + per-case detail
```

Requires Python 3.9+ and nothing else — the script imports only the stdlib
and `inputguard` itself, resolved from the repo checkout (no install
needed). It always exits 0 after printing its summary: it is a
data-measurement tool, not a CI assertion. Only a broken run (missing or
malformed cases file) exits 2.

Definitions used by `measure_fp.py`:

- A row **matches** when actual status equals `expected_status`, actual
  intent equals `expected_intent` (rows labeled `n/a` skip the intent
  check), the actual gap set equals the expected set order-insensitively,
  and every shared gap's maximum severity matches.
- **False positive (row-level)** — the analyzer flagged a gap the label
  does not list. Includes every flagged true negative.
- **False negative (row-level)** — a labeled gap the analyzer failed to
  flag. A row the analyzer cannot evaluate at all (for example a domain
  whose rules are not registered yet, so `analyze()` raises) counts every
  expected gap as missed and is reported as unevaluated.
- Rates are reported per `case_type` and overall as
  `false-positive rows ÷ rows in group` (and likewise for false
  negatives). Degradation-note presence is reported separately from the
  gap-based rates, and performance rows print their wall time.

Interpreting results: **labels may legitimately disagree with current
analyzer behavior — that disagreement is the measurement.** A rising match
rate over the release wave is the signal that the registry, word-boundary
matching, and degradation work are landing. Never edit a label to make a
measurement look better; if a row is genuinely mislabeled, fix it in a PR
with the `labeler_note` updated to say why.

## Gap vocabulary (calibration contract)

Per-gap default severities and the satisfied-condition examples a text must
contain to avoid the flag. The `gap_vocabulary` sheet in the source workbook
is the normative version; this table is its checkpoint. For the new-domain
gaps the examples double as the implementation contract: a text containing
any listed example must not flag that gap; a text containing none must.

| Domain        | Gap                         | Severity | Rule code                                 | Satisfied when the text contains…                                                                                            |
| ------------- | --------------------------- | -------- | ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| coding        | programming language        | high     | missing_language, intent_without_language | v0.2 gap string (compat-pinned)                                                                                              |
| coding        | api structure               | high     | missing_api_structure                     | v0.2 gap string (compat-pinned)                                                                                              |
| coding        | data model                  | high     | missing_data_model                        | v0.2 gap string (compat-pinned)                                                                                              |
| coding        | integration specifics       | medium   | missing_integration_specifics             | v0.2 gap string (compat-pinned)                                                                                              |
| coding        | authentication type         | high     | missing_auth_type                         | v0.2 gap string (compat-pinned)                                                                                              |
| coding        | output format               | medium   | missing_output_format                     | v0.2 gap string (compat-pinned); build verbs only                                                                            |
| coding        | task context                | high     | insufficient_context                      | v0.2 gap string (compat-pinned); catch-all safety net                                                                        |
| coding        | error description           | high     | missing_error_message                     | v0.2 gap string (compat-pinned)                                                                                              |
| coding        | expected vs actual behavior | high     | missing_expected_vs_actual                | v0.2 gap string (compat-pinned)                                                                                              |
| coding        | code context                | medium   | missing_debug_code_context                | v0.2 gap string (compat-pinned)                                                                                              |
| coding        | optimization target         | high     | missing_optimization_target               | v0.2 gap string (compat-pinned)                                                                                              |
| coding        | performance baseline        | medium   | missing_performance_baseline              | v0.2 gap string (compat-pinned)                                                                                              |
| coding        | optimization constraint     | low      | missing_optimization_constraint           | v0.2 gap string (compat-pinned)                                                                                              |
| coding        | code reference              | high     | missing_code_reference                    | v0.2 gap string (compat-pinned)                                                                                              |
| coding        | explanation depth           | low      | missing_explanation_depth                 | v0.2 gap string (compat-pinned)                                                                                              |
| coding        | existing stack              | high     | missing_existing_stack                    | v0.2 gap string (compat-pinned)                                                                                              |
| coding        | feature scope               | high     | missing_feature_scope                     | v0.2 gap string (compat-pinned)                                                                                              |
| coding        | completion criteria         | low      | missing_completion_criteria               | v0.2 gap string (compat-pinned)                                                                                              |
| writing       | audience                    | high     | (new v0.3 rule)                           | readership named: 'for beginners', 'my manager', 'the board', 'engineers', 'admissions officers', 'stakeholders'              |
| writing       | purpose                     | high     | (new v0.3 rule)                           | goal stated: 'to convince', 'announcing', 'requesting', 'asking for', 'goal is to', 'so that', 'recap', 'lead with'           |
| writing       | structure/format            | medium   | (new v0.3 rule)                           | length or organization: '300 words', 'one page', 'bullets', 'sections', 'short', 'concise'; bare artifact type does NOT satisfy |
| writing       | source material             | high     | (new v0.3 rule)                           | fires only when the task references existing material; satisfied when the material is actually provided                      |
| writing       | context                     | medium   | (new v0.3 rule)                           | subject or situation named: 'remote work', 'the migration', 'Q3 roadmap', 'context:', 'background:', 'the vendor'             |
| writing       | completeness                | low      | (new v0.3 rule)                           | required content enumerated: 'include', 'must cover', 'mention', 'must stay under 650 words', 'owners and deadlines'          |
| data-analysis | dataset/source              | high     | (new v0.3 rule)                           | concrete data named: 'sales.csv', 'the attached export', 'postgres subscriptions table'; 'this dataset' alone does NOT satisfy |
| data-analysis | question/goal               | high     | (new v0.3 rule)                           | explicit question or objective: 'whether refunds spiked', 'which tier cancels most', 'I want to know', or a trailing '?'      |
| data-analysis | output format               | medium   | (new v0.3 rule)                           | deliverable shape: 'bar chart', 'heatmap', 'two-slide summary', 'trend table', 'SQL to reproduce', 'themes table'             |
| data-analysis | tooling                     | medium   | (new v0.3 rule)                           | tool constraint: 'using pandas only', 'in python', 'dbt', 'BigQuery only', 'no external libraries'                            |
| data-analysis | volume                      | low      | (new v0.3 rule)                           | scale stated: '80,000 rows', '400M rows', '5,000 responses', '90 days of data', '18 months of daily data'                     |
| data-analysis | reproducibility             | low      | (new v0.3 rule)                           | rerun/reuse concern: 'rerun weekly', 'reusable', 'rerunnable', 'reproduce it', 'monthly'                                      |

## Maintenance

- Add rows via PR. Keep the id prefix and uniqueness, gap strings verbatim
  from the vocabulary, and always fill `labeler_note`.
- Regenerate `cases.csv` only from the source workbook (scripted export,
  QUOTE_ALL + CRLF), never by hand-editing quoted text.
- `tests/test_eval_loader.py` guards the file's mechanics (it parses,
  columns exist, ids unique, the measurement runs end to end on a sample).
  It deliberately does NOT assert that labels match analyzer output — that
  agreement is what `measure_fp.py` measures over time.
