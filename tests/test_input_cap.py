"""Input-cap tests: enforced max_chars truncation, visible in the result.

Covers the input-length slice of the v0.3 spec (art_bTvdPdJS §2): analyzed
input is bounded, always, and truncation is reported on the result — never
silent. The v0.2 code had no cap at all (a 1.6 MB input took ~3.8 s).
"""

from __future__ import annotations

import time

from inputguard import InputGuard, Policy

CLEAN_INPUT = (
    "Build a web app using React and FastAPI. "
    "It needs user authentication with JWT. "
    "Store tasks in a PostgreSQL database with title, description, and due date fields. "
    "Expose REST API endpoints: GET /tasks, POST /tasks, DELETE /tasks/{id}."
)


def test_input_at_cap_is_not_truncated():
    guard = InputGuard()
    assert guard.analyze("a" * 10_000).truncated is False


def test_input_one_char_over_cap_is_truncated():
    guard = InputGuard()
    assert guard.analyze("a" * 10_001).truncated is True


def test_truncation_visible_in_to_dict():
    assert InputGuard().analyze("x" * 10_001).to_dict()["truncated"] is True


def test_default_cap_is_the_v02_compatible_10k():
    assert Policy().max_chars == 10_000


def test_custom_cap_truncates_at_its_boundary():
    guard = InputGuard(policy=Policy(max_chars=50))
    assert guard.analyze("x" * 51).truncated is True
    assert guard.analyze("x" * 50).truncated is False


def test_truncated_analysis_equals_analyzing_the_kept_prefix():
    # Only the truncation flag may differ — the cap is a pure prefix slice.
    prefix = "fix the bug in my app"
    huge = prefix + " and some filler that would change nothing " * 400
    guard = InputGuard()
    full = guard.analyze(huge).to_dict()
    head = guard.analyze(huge[:10_000]).to_dict()
    assert full["truncated"] is True
    assert head["truncated"] is False
    full.pop("truncated")
    head.pop("truncated")
    assert full == head


def test_findings_come_from_the_kept_prefix():
    # Flag-worthy content inside the cap still fires after truncation.
    guard = InputGuard(policy=Policy(max_chars=100))
    result = guard.analyze("fix the bug in my app" + " z" * 200)
    assert result.truncated is True
    assert result.findings[0].code == "missing_error_message"


def test_allowlist_evaluated_against_the_capped_input():
    # The allow pattern must match within the analyzed (capped) region.
    guard = InputGuard(policy=Policy(max_chars=10, allow_patterns=("^fix",)))
    result = guard.analyze("fix the bug in my app" + "z" * 500)
    assert result.truncated is True
    assert result.findings == []
    assert result.status == "ready"


def test_clean_short_input_reports_no_truncation():
    result = InputGuard().analyze(CLEAN_INPUT)
    assert result.truncated is False
    assert result.status == "ready"


def test_huge_input_analysis_is_bounded_by_the_cap():
    # v0.2 took ~3.8 s on a 1.6 MB input; the cap must bound the scan.
    huge = ("make my database query faster " * 55_000)[:1_600_000]
    start = time.perf_counter()
    result = InputGuard().analyze(huge)
    elapsed = time.perf_counter() - start
    assert result.truncated is True
    assert elapsed < 1.0
