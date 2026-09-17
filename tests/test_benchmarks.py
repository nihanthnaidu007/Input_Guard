"""Latency budgets for the documented analysis path (spec art_bTvdPdJS §8).

Every budget below is derived from measured numbers on this codebase, not
guesses. The measured baselines (Python 3.13, 10,000-character inputs, 60
samples after warmup, ``time.perf_counter``):

    build-intent (vague, C1 path):  p50 21.94 ms / p95 26.09 / p99 27.30
    debug-intent (with findings):   p50  6.59 ms / p95  8.06 / p99  8.07
    ready path (score 100):         p50  5.62 ms / p95  5.88 / p99  6.03
    1.6 MB input under the cap:     17.1 ms (truncated=True)

What the measured path includes — deliberately:

- **C1 double-run (adversarial review art_hC18m78C):** the build path runs
  ``InsufficientContextRule.check``, which re-executes the six built-in build
  checks plus the intent-detail check inside itself because the Rule protocol
  is stateless — a ~2x multiplier on the busiest path. The build input below
  is intentionally vague so this rule is always part of the measured cost;
  any latency budget for build-intent inputs must account for it.
- **Word-boundary matching (PR #6):** ``contains_any`` matches at word
  boundaries instead of raw substring scans; its measured delta is part of
  every number above (it replaced the v0.2 substring matcher everywhere).

Budget policy: the hard gate is the **p50** (a stable statistic under CI
noise) at ~2.2x the measured p50, with a p95 sustained-regression guard at
2.5x the p50 budget. Single-sample maxima are NOT asserted — CI runners are
noisy and a one-off slow sample must not fail a merge. p50/p99 are printed
so the CI benchmark job records them per spec ("p50/p99 recorded in CI").
"""

from __future__ import annotations

import time

from inputguard import InputGuard

# 10k characters: the default Policy.max_chars cap — the documented worst
# case for a single analyze() call.
_CAP = 10_000
_SAMPLES = 60
_WARMUP = 5

# Measured p50 21.94 ms on this codebase (including the C1 double-run).
# Budget: ~1.8x -> 40 ms; p95 guard 2.5x -> 100 ms.
BUILD_P50_BUDGET_MS = 40.0

# Measured p50 6.59 ms. Budget: ~2.6x -> 17 ms; p95 guard 2.5x -> 42 ms.
DEBUG_P50_BUDGET_MS = 17.0

# Measured p50 5.62 ms. Budget: ~3.4x -> 19 ms; p95 guard 2.5x -> 47 ms.
READY_P50_BUDGET_MS = 19.0


def _pad(text: str, filler: str, n: int = _CAP) -> str:
    """Extend ``text`` to exactly ``n`` characters with neutral filler prose.

    The filler carries no rule triggers (no error/build/feature vocabulary);
    only the seed text decides which intent and findings fire.
    """
    reps = (n - len(text)) // len(filler) + 1
    return (text + " " + (filler * reps))[:n]


# Build-intent, deliberately vague: InsufficientContextRule is in the build
# ruleset, so this path pays the C1 re-run of seven checks inside check().
_BUILD_VAGUE = _pad(
    "build me an app",
    "please and then the thing should be there somehow ",
)

# Debug-intent with findings: a trigger with unresolved satisfies.
_DEBUG_GAPS = _pad(
    "my python code is throwing an error when the users log in, "
    "the app is just wrong",
    "the function receives the arguments and the error happens again "
    "when running it ",
)

# Ready path: a fully-specified debug request (eval corpus TN-DBG-01 shape)
# padded to the cap — every trigger-and-satisfy pair resolves, score 100.
_READY = _pad(
    "getting a TypeError in my Python function, expected a list but got None, "
    "the function should return an empty list instead of crashing, "
    "stack trace shows the failure happens on the iteration step",
    "the function receives the arguments described above and returns the "
    "value it should return; the behavior matches the description given ",
)


def _measure(input_text: str) -> tuple[float, float, float]:
    """Return (p50, p95, p99) in milliseconds over _SAMPLES analyzed calls."""
    guard = InputGuard()
    for _ in range(_WARMUP):
        guard.analyze(input_text)
    samples: list[float] = []
    for _ in range(_SAMPLES):
        start = time.perf_counter()
        guard.analyze(input_text)
        samples.append((time.perf_counter() - start) * 1000.0)
    samples.sort()
    p50 = samples[len(samples) // 2]
    p95 = samples[int(len(samples) * 0.95)]
    p99 = samples[min(len(samples) - 1, int(len(samples) * 0.99))]
    return p50, p95, p99


def test_build_intent_p50_within_budget() -> None:
    """C1 path: vague 10k build input, InsufficientContextRule re-running the
    build checks inside check() — the documented worst-case busy path."""
    p50, p95, p99 = _measure(_BUILD_VAGUE)
    print(
        f"\n[benchmark] build-intent 10k: p50={p50:.2f}ms p95={p95:.2f}ms "
        f"p99={p99:.2f}ms (budget p50<={BUILD_P50_BUDGET_MS}ms)"
    )
    assert p50 <= BUILD_P50_BUDGET_MS, f"build p50 {p50:.2f}ms > {BUILD_P50_BUDGET_MS}ms"
    assert p95 <= BUILD_P50_BUDGET_MS * 2.5, f"build p95 {p95:.2f}ms > sustained guard"


def test_debug_intent_p50_within_budget() -> None:
    p50, p95, p99 = _measure(_DEBUG_GAPS)
    print(
        f"\n[benchmark] debug-intent 10k: p50={p50:.2f}ms p95={p95:.2f}ms "
        f"p99={p99:.2f}ms (budget p50<={DEBUG_P50_BUDGET_MS}ms)"
    )
    assert p50 <= DEBUG_P50_BUDGET_MS, f"debug p50 {p50:.2f}ms > {DEBUG_P50_BUDGET_MS}ms"
    assert p95 <= DEBUG_P50_BUDGET_MS * 2.5, f"debug p95 {p95:.2f}ms > sustained guard"


def test_ready_path_p50_within_budget() -> None:
    p50, p95, p99 = _measure(_READY)
    print(
        f"\n[benchmark] ready-path 10k: p50={p50:.2f}ms p95={p95:.2f}ms "
        f"p99={p99:.2f}ms (budget p50<={READY_P50_BUDGET_MS}ms)"
    )
    assert p50 <= READY_P50_BUDGET_MS, f"ready p50 {p50:.2f}ms > {READY_P50_BUDGET_MS}ms"
    assert p95 <= READY_P50_BUDGET_MS * 2.5, f"ready p95 {p95:.2f}ms > sustained guard"


def test_unbounded_input_is_bounded_by_cap() -> None:
    """The v0.2 failure mode (1.6 MB input taking ~3.8 s of linear scans) must
    stay dead: the Policy cap bounds the scan and the result says so."""
    big = _pad(_BUILD_VAGUE, "more of the same neutral prose ", n=1_600_000)
    assert len(big) == 1_600_000
    guard = InputGuard()
    start = time.perf_counter()
    result = guard.analyze(big)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    print(f"\n[benchmark] 1.6MB input with cap: {elapsed_ms:.1f}ms, truncated={result.truncated}")
    assert result.truncated is True
    # 1s ceiling: 100x headroom over the measured capped path (~10 ms) while
    # still catching any regression to the v0.2 unbounded 3.8 s behavior.
    assert elapsed_ms < 1000.0, f"1.6MB input took {elapsed_ms:.1f}ms — the cap is not bounding the scan"
