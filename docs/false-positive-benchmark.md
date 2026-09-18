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
rows. Performance wall time (single pass): PF-001 19 ms, PF-002 20 ms —
PF-002 exercises the 10,000-character cap with the `truncated` flag set.

Zero false positives on true negatives and zero on degradation rows is the
load-bearing number: it says the English keyword rules fire only on English
input, and that non-English input degrades instead of producing invented
gaps.

## Fixture-style boundary target: 4 of 6, against v0.2's 6 of 6

The labeling guide (`art_XPvHhPeZ`) sets the release target: the six
fixture-style boundary rows (BD-002, BD-003, BD-004, BD-006, BD-013,
BD-014) must come back clean, with BD-012 — the genuine-debug-request
no-regression guard — still passing. The v0.2 baseline flagged all six
(substring matching read "fixture" as "fix").

Measured at this release: **2 of 6 pass cleanly (BD-003, BD-013), and
BD-012 passes**, but 4 of 6 still flag (BD-002, BD-004, BD-006, BD-014).
The 0/6 target is therefore **not met** — the honest read is "improved from
6/6 to 4/6 flagged, short of the 0/6 target."

The mechanism is deliberate, verified in `inputguard/matching.py`: the
shared matcher kills the embedded-word false positives ("fixture" is no
longer "fix"), but it still absorbs common inflectional endings
(`-s`, `-ed`, `-ing`, `-er`, `-ly`, ...) so natural word forms keep firing
— "debugged" still matches "debug", "slowly" still matches "slow". The
class-of-hit the v0.2 coding matcher preserved was read as recall on
real inputs; these four labels were written against strict
boundary-only semantics and sit exactly on that trade-off. Closing them
means re-deciding that recall trade-off on the labeled set — an
eval-driven change for a future release, never a label edit.

For the spec verification row "False positive eliminated", this run
records: v0.2 baseline 6/6 flagged; v0.3 measured 4/6 flagged with
BD-012 (no-regression guard) passing and zero false positives on all 37
true negatives.

## Residual mismatches (5)

The 5 unmatched rows, per the measured run at the top of this document:

- `TP-FEA-02` — false negative: the `feature scope` gap is not flagged; the
  row lands one status above expected (`usable_with_warnings` vs `ready`).
- `BD-002`, `BD-004`, `BD-006`, `BD-014` — fixture-style boundary rows
  still flagging through the matcher's deliberate inflection tolerance
  (see the target section above): the detected intent flips
  (build → optimization / debug) and the other intent's coding rules fire,
  adding spurious gaps.

These are candidate re-evaluations of the inflection-recall trade-off, or
intent-detector work, for a future release; per `eval/README.md`, labels
are never edited to make a measurement look better.

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
