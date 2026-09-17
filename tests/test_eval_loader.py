"""Smoke tests for the versioned clarity-evaluation set (``eval/``).

These tests verify the dataset's mechanics only: the CSV parses, the
required columns exist, row ids are unique, and the measurement script runs
end to end on a small sample. They deliberately do NOT assert that labels
agree with analyzer output — label disagreement is the measurement
(``eval/measure_fp.py``), and freezing behavior against labels here would
defeat its purpose.
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parent.parent
CASES_CSV = REPO_ROOT / "eval" / "cases.csv"
MEASURE_FP = REPO_ROOT / "eval" / "measure_fp.py"

REQUIRED_COLUMNS = (
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


def _load_rows() -> List[dict]:
    with CASES_CSV.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_cases_csv_parses_with_required_columns() -> None:
    with CASES_CSV.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
    missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    assert not missing, f"cases.csv missing columns: {missing}"
    rows = _load_rows()
    assert len(rows) > 0, "cases.csv contains no data rows"
    assert all(row["text"].strip() for row in rows), "every case must carry prompt text"


def test_case_ids_are_unique() -> None:
    rows = _load_rows()
    ids = [row["id"] for row in rows]
    duplicates = {row_id for row_id in ids if ids.count(row_id) > 1}
    assert not duplicates, f"duplicate case ids: {sorted(duplicates)}"


def test_measure_fp_runs_end_to_end_on_sample() -> None:
    # Smoke run on a 10-case sample: the tool must complete, exit 0, and
    # print its summary table. Exit code and rates are not asserted against
    # the labels — that is the measurement, not a gate.
    result = subprocess.run(
        [sys.executable, str(MEASURE_FP), "--limit", "10"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"measure_fp.py failed:\n{result.stderr}"
    assert "=== Summary (case-level rates) ===" in result.stdout
    assert "overall" in result.stdout
