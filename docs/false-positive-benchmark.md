# False-positive benchmark

Measured results of the clarity-evaluation set (`eval/`, 121 labeled rows)
against the shipped analyzer, produced by `eval/measure_fp.py`. This is the
document `eval/README.md` references as the release-wave record; re-run the
script and update the tables when the analyzer or the labels change.

Last run: v0.3.0 release branch, 2026-09-17.

## Headline numbers

| Case type      | Rows | Match | FP | FN | FP rate | FN rate |
| -------------- | ---- | ----- | -- | -- | ------- | ------- |
| true_positive  | 43   | 42    | 0  | 1  | 0.0%    | 2.3%    |
| true_negative  | 37   | 37    | 0  | 0  | 0.0%    | 0.0%    |
| boundary       | 25   | 21    | 4  | 0  | 16.0%   | 0.0%    |
| degradation    | 14   | 14    | 0  | 0  | 0.0%    | 0.0%    |
| performance    | 2    | 2     | 0  | 0  | 0.0%    | 0.0%    |
| **overall**    | **121** | **116** | **4** | **1** | **3.3%** | **0.8%** |

Degradation honesty: a degradation note is present on 14 of 14 degradation
rows. Performance wall time (single pass): PF-001 22 ms, PF-002 22 ms —
PF-002 exercises the 10,000-character cap with the `truncated` flag set.

Zero false positives on true negatives and zero on degradation rows is the
load-bearing number: it says the English keyword rules fire only on English
input, and that non-English input degrades instead of producing invented
gaps.

## Residual mismatches (5)

The 5 unmatched rows are all pre-existing behavior on the coding domain,
known at label time and outside the v0.3 feature work:

- `TP-FEA-02` — false negative: `feature scope` gap not flagged; the row
  comes back one status above expected (`usable_with_warnings` vs `ready`).
- `BD-002`, `BD-004`, `BD-006` — boundary rows: the detected intent
  switches (build → optimization / debug) and the coding rules of the other
  intent fire, adding spurious gaps.
- `BD-014` — boundary row with the same intent-adjacency shape.

These are candidate labels to re-examine or intent-detector work for a
future release; per `eval/README.md`, labels are never edited to make a
measurement look better.

## History within the release wave

Measured with the same script, no label edits in between:

| State                                         | Match  | Note                                            |
| --------------------------------------------- | ------ | ----------------------------------------------- |
| Early v0.3 branch, before writing/analysis rules | 87/121 | 15 data-analysis rows unevaluated (rules absent) |
| After data-analysis rules landed (PR #11)     | 102/121 | 14 degradation rows still mismatching            |
| Degradation contract completed (this release) | 116/121 | all 14 degradation rows match, notes on 14/14    |

## Performance: dataset-filename extraction

The `{dataset}` follow-up slot and the data-analysis dataset rule both
extract filename-like runs. The original single regex backtracked its
greedy span against every dot in a run — quadratic. Measured on dotted
filler (the adversarial shape):

| Input length | Old regex | Current extractor |
| ------------ | --------- | ----------------- |
| 1,000 chars  | 13 ms     | < 1 ms            |
| 10,000 chars | 1,306 ms  | 0.7 ms (plain) / 21 ms (all dots) |
| 100,000 chars | unbounded growth | 130 ms |

Timing tests at 1 K and 10 K (`tests/test_followups.py`) pin the linear
growth rate.

## How to reproduce

```bash
python3 eval/measure_fp.py        # full 121-row table
python3 eval/measure_fp.py --json # machine-readable
python3 -m pytest tests/          # full suite including timing guards
```
