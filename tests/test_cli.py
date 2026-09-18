"""Tests for the ``inputguard`` CLI (spec art_bTvdPdJS §5).

Covers the documented exit-code contract (0 = ok / 1 = below the
``--min-score`` floor / 2 = usage error), the text rendering shape, and that
``--format json`` emits exactly the result's ``to_dict()`` contract — the
CLI adds no fields and renames none.
"""

from __future__ import annotations

import io
import json

import pytest

from inputguard import InputGuard
from inputguard.cli import EXIT_BELOW_FLOOR, EXIT_OK, EXIT_USAGE, main

VAGUE = "make this faster"  # optimization intent, needs clarification
READY = (
    "getting a TypeError in my Python function, expected a list but got None"
)  # eval corpus TN-DBG-01 shape: score 100


def test_text_output_contains_verdict_lines(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["analyze", VAGUE]) == EXIT_OK
    out = capsys.readouterr().out
    assert "status: needs_clarification" in out
    assert "clarity: " in out
    assert "intent: optimization" in out
    assert "domain: coding" in out
    assert "missing: " in out
    assert "ask: " in out  # the follow-up questions surface on the CLI too


def test_json_output_is_exactly_to_dict(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["analyze", VAGUE, "--format", "json"]) == EXIT_OK
    parsed = json.loads(capsys.readouterr().out)
    expected = InputGuard().analyze(VAGUE).to_dict()
    assert parsed == expected


def test_min_score_below_floor_exits_one() -> None:
    assert main(["analyze", VAGUE, "--min-score", "85"]) == EXIT_BELOW_FLOOR


def test_min_score_at_or_above_floor_exits_zero() -> None:
    assert main(["analyze", READY, "--min-score", "85"]) == EXIT_OK


def test_missing_text_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["analyze"])
    assert exc_info.value.code == EXIT_USAGE


def test_unknown_domain_is_a_usage_error_not_a_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["analyze", VAGUE, "--domain", "legal"]) == EXIT_USAGE
    err = capsys.readouterr().err
    assert "inputguard:" in err
    assert "legal" in err


def test_stdin_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(VAGUE))
    assert main(["analyze", "--stdin"]) == EXIT_OK


def test_strict_mode_flag_is_accepted() -> None:
    assert main(["analyze", READY, "--mode", "strict", "--min-score", "85"]) == EXIT_OK


def test_degraded_note_appears_in_text_output(capsys: pytest.CaptureFixture[str]) -> None:
    # A Chinese build request (spec probe P2): the language probe must mark
    # the result degraded, and the CLI must show that note instead of a
    # silent ready.
    degraded_input = "建造一个用户登录应用"
    assert main(["analyze", degraded_input]) == EXIT_OK
    out = capsys.readouterr().out
    assert "note: " in out
    assert "status: ready" not in out
