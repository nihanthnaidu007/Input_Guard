"""The ``inputguard`` command-line interface (spec art_bTvdPdJS §5).

A zero-dependency argparse front end over the same ``InputGuard.analyze``
pipeline the library exposes. JSON output is the result's own ``to_dict()``
contract — the CLI adds no fields and renames none.

Exit codes (the CI/commit-hook contract):

- ``0`` — analysis completed; with ``--min-score N``, the score is at or
  above the floor.
- ``1`` — analysis completed but the clarity score is below the
  ``--min-score`` floor. Use with ``--min-score`` to gate commits/PRs.
- ``2`` — usage error: unknown flags, missing text, or an invalid value
  (unknown domain, empty input) reported by the pipeline.

Examples::

    inputguard analyze "make this faster"
    inputguard analyze "make this faster" --mode strict
    inputguard analyze "$(cat prompt.txt)" --format json --min-score 85
    cat prompt.txt | inputguard analyze --stdin --min-score 85
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional, Sequence

from inputguard import AnalysisResult, InputGuard

EXIT_OK = 0
EXIT_BELOW_FLOOR = 1
EXIT_USAGE = 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="inputguard",
        description="Pre-flight LLM inputs for clarity before inference.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser(
        "analyze",
        help="Analyze input text and report its clarity verdict.",
    )
    analyze.add_argument(
        "text",
        nargs="?",
        help="The input text to analyze; omit when --stdin is given.",
    )
    analyze.add_argument(
        "--stdin",
        action="store_true",
        help="Read the input text from stdin instead of the TEXT argument.",
    )
    analyze.add_argument(
        "--domain",
        default="coding",
        help="Registered domain to analyze against (default: coding).",
    )
    analyze.add_argument(
        "--mode",
        choices=("warning", "strict"),
        default="warning",
        help="Status banding mode (default: warning).",
    )
    analyze.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text). json emits the to_dict() contract.",
    )
    analyze.add_argument(
        "--min-score",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Exit 1 when the clarity score is below N — a ready-made "
            "commit-hook / CI gate."
        ),
    )
    return parser


def _render_text(result: AnalysisResult, domain: str) -> str:
    """Human-readable verdict, one fact per line (spec §5 example shape)."""
    lines = [
        f"status: {result.status}",
        f"clarity: {result.clarity_score}/100",
        f"intent: {result.detected_intent}",
        f"domain: {domain}",
    ]
    if result.gaps:
        lines.append(f"missing: {', '.join(result.gaps)}")
    for question in result.follow_ups:
        lines.append(f"ask: {question}")
    if result.degradation_note is not None:
        lines.append(f"note: {result.degradation_note}")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run one analysis; returns the process exit code (see module docstring)."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    text = sys.stdin.read() if args.stdin else args.text
    if not text:
        parser.error("provide the text to analyze as TEXT, or pass --stdin")

    guard = InputGuard(mode=args.mode)
    try:
        result = guard.analyze(text, domain=args.domain)
    except ValueError as exc:
        # Invalid domain / empty-after-normalization input: a usage error,
        # not a crash — the same ValueError contract the library documents.
        print(f"inputguard: {exc}", file=sys.stderr)
        return EXIT_USAGE

    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(_render_text(result, args.domain))

    if args.min_score is not None and result.clarity_score < args.min_score:
        return EXIT_BELOW_FLOOR
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover — manual invocation convenience
    sys.exit(main())
