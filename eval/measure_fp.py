#!/usr/bin/env python3
"""Measure InputGuard against the labeled clarity-evaluation set.

Loads ``eval/cases.csv``, runs every row through ``inputguard``'s analyzer,
and prints per-case_type and overall false-positive / false-negative rates.

This is a data-measurement tool, not a CI assertion: labels may legitimately
disagree with current analyzer behavior — that disagreement IS the
measurement. The script exits 0 after printing its summary regardless of the
rates. Only a broken run (missing file, malformed CSV, missing columns)
exits 2.

Stdlib-only, Python 3.9+. Run from anywhere:

    python3 eval/measure_fp.py
    python3 eval/measure_fp.py --limit 10   # quick smoke run
    python3 eval/measure_fp.py --json       # machine-readable summary
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, NoReturn, Optional, Sequence, Tuple

# Make the repo checkout importable (and preferred over any site-packages
# install) so the tool measures the code in this tree without pip install.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

REQUIRED_COLUMNS: Tuple[str, ...] = (
    "id",
    "text",
    "domain",
    "expected_intent",
    "expected_gaps",
    "expected_status",
    "expected_severities",
    "case_type",
    "labeler_note",
)

CASE_TYPE_ORDER: Tuple[str, ...] = (
    "true_positive",
    "true_negative",
    "boundary",
    "degradation",
    "performance",
)

SEVERITY_RANK: Dict[str, int] = {"low": 0, "medium": 1, "high": 2}
RANK_TO_SEVERITY: Dict[int, str] = {rank: name for name, rank in SEVERITY_RANK.items()}

NONE_SENTINELS = ("", "none", "n/a")


def fail(message: str) -> NoReturn:
    print(f"measure_fp: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_multi_value(raw: str) -> List[str]:
    """Split a ``;``-separated field; ``none``/``n/a``/empty mean no entries."""
    value = (raw or "").strip()
    if value.lower() in NONE_SENTINELS:
        return []
    return [part.strip() for part in value.split(";") if part.strip()]


def load_cases(path: Path) -> List[Dict[str, str]]:
    if not path.is_file():
        fail(f"cases file not found: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
        if missing:
            fail(f"{path} is missing required columns: {', '.join(missing)}")
        rows = [dict(row) for row in reader]
    if not rows:
        fail(f"{path} contains no data rows")
    return rows


def actual_gap_severities(findings: Sequence[Any]) -> Dict[str, int]:
    """Map gap key -> max severity rank across that gap's findings."""
    best: Dict[str, int] = {}
    for finding in findings:
        key = finding.gap if finding.gap is not None else finding.code
        rank = SEVERITY_RANK.get(finding.severity, -1)
        if rank > best.get(key, -1):
            best[key] = rank
    return best


def classify_case(row: Dict[str, str], guard: Any) -> Dict[str, Any]:
    """Run one labeled row through the analyzer and classify it.

    A row matches when: status equals expected, intent equals expected (when
    the label asserts one), the actual gap set equals the expected set
    (order-insensitive), and each shared gap's max severity equals the
    expected severity. Any deviation is recorded as the row's reasons.
    """
    expected_gaps = parse_multi_value(row["expected_gaps"])
    expected_severities = parse_multi_value(row["expected_severities"])
    expected_gap_set = set(expected_gaps)
    intent_asserted = row["expected_intent"].strip().lower() not in NONE_SENTINELS

    record: Dict[str, Any] = {
        "id": row["id"],
        "case_type": row["case_type"],
        "evaluated": True,
        "match": False,
        "status_match": False,
        "intent_match": False,
        "spurious_gaps": [],  # analyzer flagged, label did not list -> false positive
        "missed_gaps": [],  # label listed, analyzer did not flag -> false negative
        "severity_mismatches": [],
        "actual_status": None,
        "actual_intent": None,
        "actual_gaps": [],
        "wall_ms": None,
        "notes": [],
        "reasons": [],
    }

    start = time.perf_counter()
    try:
        result = guard.analyze(row["text"], domain=row["domain"])
    except Exception as exc:  # unevaluable row (e.g. domain not yet implemented)
        record["evaluated"] = False
        record["wall_ms"] = (time.perf_counter() - start) * 1000.0
        record["missed_gaps"] = list(expected_gaps)
        message = f"analyzer raised {type(exc).__name__}: {exc}"
        record["notes"].append(message)
        record["reasons"].append(f"{message} — row counted as unmatched")
        return record

    record["wall_ms"] = (time.perf_counter() - start) * 1000.0
    record["actual_status"] = result.status
    record["actual_intent"] = result.detected_intent
    record["actual_gaps"] = list(result.gaps)

    actual_gap_set = set(result.gaps)
    record["spurious_gaps"] = sorted(actual_gap_set - expected_gap_set)
    record["missed_gaps"] = [gap for gap in expected_gaps if gap not in actual_gap_set]

    actual_severities = actual_gap_severities(result.findings)
    for gap, expected_severity in zip(expected_gaps, expected_severities):
        if gap not in actual_gap_set:
            continue
        actual_rank = actual_severities.get(gap, -1)
        expected_rank = SEVERITY_RANK.get(expected_severity.strip(), -1)
        if actual_rank != expected_rank:
            record["severity_mismatches"].append(
                f"{gap}: expected {expected_severity}, got "
                f"{RANK_TO_SEVERITY.get(actual_rank, 'unknown')}"
            )

    record["status_match"] = result.status == row["expected_status"]
    record["intent_match"] = (not intent_asserted) or (
        result.detected_intent == row["expected_intent"]
    )

    if row["case_type"] == "degradation":
        # Degradation rubric (labeling guide): the analyzer must report an
        # explicit degradation note and never a silent `ready`. The note is
        # additive on any underlying status; until that path ships the
        # attribute is simply absent and the row stays unmatched.
        note = getattr(result, "degradation_note", None)
        record["notes"].append(
            "degradation_note present" if note else "degradation_note absent"
        )

    reasons: List[str] = []
    if not record["status_match"]:
        reasons.append(f"status {row['expected_status']} -> {result.status}")
    if intent_asserted and not record["intent_match"]:
        reasons.append(f"intent {row['expected_intent']} -> {result.detected_intent}")
    if record["spurious_gaps"]:
        reasons.append("spurious gaps: " + ", ".join(record["spurious_gaps"]))
    if record["missed_gaps"]:
        reasons.append("missed gaps: " + ", ".join(record["missed_gaps"]))
    reasons.extend(f"severity {item}" for item in record["severity_mismatches"])

    record["match"] = not reasons
    record["reasons"] = reasons
    return record


def summarize(results: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate per-case results into per-case_type and overall rates."""
    groups: Dict[str, List[Dict[str, Any]]] = {name: [] for name in CASE_TYPE_ORDER}
    for record in results:
        groups.setdefault(record["case_type"], []).append(record)

    def group_summary(records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        total = len(records)
        matches = sum(1 for r in records if r["match"])
        status_matches = sum(1 for r in records if r["status_match"])
        fp_cases = sum(1 for r in records if r["spurious_gaps"])
        fn_cases = sum(1 for r in records if r["missed_gaps"])
        unevaluated = sum(1 for r in records if not r["evaluated"])
        return {
            "total": total,
            "matches": matches,
            "status_matches": status_matches,
            "false_positive_cases": fp_cases,
            "false_negative_cases": fn_cases,
            "unevaluated": unevaluated,
            "false_positive_rate": fp_cases / total if total else 0.0,
            "false_negative_rate": fn_cases / total if total else 0.0,
            "match_rate": matches / total if total else 0.0,
        }

    summary = {name: group_summary(records) for name, records in groups.items() if records}
    summary["overall"] = group_summary(list(results))
    return summary


def print_table(summary: Dict[str, Any], results: Sequence[Dict[str, Any]]) -> None:
    header = (
        f"{'case_type':<15} {'total':>5} {'match':>6} {'status_ok':>9} "
        f"{'fp_cases':>8} {'fn_cases':>8} {'fp_rate':>8} {'fn_rate':>8}"
    )
    print("=== Summary (case-level rates) ===")
    print(header)
    print("-" * len(header))
    for name, stats in summary.items():
        print(
            f"{name:<15} {stats['total']:>5} {stats['matches']:>6} "
            f"{stats['status_matches']:>9} {stats['false_positive_cases']:>8} "
            f"{stats['false_negative_cases']:>8} "
            f"{stats['false_positive_rate']:>7.1%} {stats['false_negative_rate']:>7.1%}"
        )
    print(
        "\nfp: rows where the analyzer flagged a gap the label does not list "
        "(false positives)\n"
        "fn: rows where a labeled gap was not flagged (false negatives)"
    )

    degradation = summary.get("degradation")
    if degradation:
        noted = sum(
            1
            for r in results
            if r["case_type"] == "degradation"
            and any("degradation_note present" in n for n in r["notes"])
        )
        print(
            f"\ndegradation honesty: degradation_note present on {noted}/"
            f"{degradation['total']} degradation rows"
        )

    perf = [r for r in results if r["case_type"] == "performance"]
    if perf:
        timings = ", ".join(f"{r['id']} {r['wall_ms']:.0f} ms" for r in perf)
        print(f"performance wall time (single pass): {timings}")

    mismatched = [r for r in results if not r["match"]]
    if mismatched:
        print(f"\n=== Mismatched rows ({len(mismatched)}) ===")
        for record in mismatched:
            detail_source = record.get("reasons") or record.get("notes") or []
            detail = "; ".join(detail_source)
            print(f"{record['id']} [{record['case_type']}] {detail}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure inputguard against the labeled clarity-evaluation set.",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).resolve().parent / "cases.csv",
        help="path to the labeled cases CSV (default: eval/cases.csv)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="evaluate only the first N rows (smoke runs)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the summary and per-case results as JSON",
    )
    args = parser.parse_args(argv)

    import inputguard  # noqa: E402  (after sys.path setup above)

    rows = load_cases(args.cases)
    if args.limit is not None:
        if args.limit < 1:
            fail("--limit must be >= 1")
        rows = rows[: args.limit]

    guard = inputguard.InputGuard()
    results = [classify_case(row, guard) for row in rows]
    summary = summarize(results)

    if args.json:
        print(json.dumps({"summary": summary, "results": results}, indent=2))
    else:
        print(
            f"InputGuard clarity evaluation — {len(rows)} rows from "
            f"{args.cases} · analyzer {inputguard.__version__} · default policy"
        )
        print_table(summary, results)

    # A measurement tool reports, it does not gate: labels disagreeing with
    # current behavior is the measurement, so always exit 0 on a clean run.
    return 0


if __name__ == "__main__":
    sys.exit(main())
