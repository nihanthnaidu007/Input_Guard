"""README anti-drift gate: every example in README.md is executed.

The v0.2 README shipped ``to_dict()`` examples that drifted from the code
within two releases (survey art_CnghyDxp §5.6) — the first docs a new user
read were wrong. This module makes that failure mode a test failure:

1. Every ```python fenced block in README.md runs, in document order, in
   one fresh subprocess. The README's code blocks carry real ``assert``
   statements for their documented values, so a stale value fails here.
   The subprocess also isolates the extension examples' process-global
   registry registrations from the modules this suite runs afterwards.
2. The embedded ```json block must equal the analyzer's live ``to_dict()``
   output for the same input — regenerated docs, never hand-copied.
3. The rule tables, gap-name lists, export list, and CLI output block must
   match the live package: rule ids, severities, and gap strings per
   intent, straight from the registry.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import List

import inputguard
from inputguard import REGISTRY

README_PATH = Path(__file__).resolve().parent.parent / "README.md"

_FENCE = re.compile(r"```([a-z]*)\n(.*?)```", re.DOTALL)

# "What gets checked" section header -> the intent whose rules it documents.
_SECTION_INTENTS = [
    ("### Build inputs", "build"),
    ("### Debug inputs", "debug"),
    ("### Optimization inputs", "optimization"),
    ("### Explanation inputs", "explanation"),
    ("### Feature inputs", "feature"),
    ("### Writing inputs", "compose"),
    ("### Data-analysis inputs", "analysis"),
]

# Bold label in the gap-vocabulary bullets -> intent id.
_GAP_LABELS = {
    "Build": "build",
    "Debug": "debug",
    "Optimization": "optimization",
    "Explanation": "explanation",
    "Feature": "feature",
    "Compose": "compose",
    "Analysis": "analysis",
}


def _blocks(lang: str) -> List[str]:
    """The README's fenced blocks in one language, in document order."""
    text = README_PATH.read_text(encoding="utf-8")
    found = [match.group(2) for match in _FENCE.finditer(text) if match.group(1) == lang]
    assert found, f"no {lang!r} blocks found in README.md — extraction rotted"
    return found


def test_python_blocks_run_in_document_order() -> None:
    blocks = _blocks("python")
    # If this count drops, block extraction rotted — fix the extraction, not the docs.
    assert len(blocks) >= 10
    script = "\n\n".join(blocks)
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, (
        "A README example failed — README and code have drifted.\n"
        f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
    )


def test_to_dict_json_block_matches_live_output() -> None:
    blocks = _blocks("json")
    assert len(blocks) == 1, "README should embed exactly one to_dict() JSON example"
    documented = json.loads(blocks[0])
    live = inputguard.InputGuard().analyze("fix my code").to_dict()
    assert documented == live


def test_public_exports_block_matches_package() -> None:
    import_blocks = [b for b in _blocks("python") if "from inputguard import (" in b]
    assert len(import_blocks) == 1, "README should show the public exports exactly once"
    names = re.findall(r"^\s{4}(\w+),?$", import_blocks[0], re.MULTILINE)
    assert set(names) == set(inputguard.__all__)
    for name in names:
        assert hasattr(inputguard, name), f"README export {name!r} does not exist"


def test_rule_tables_match_registry() -> None:
    text = README_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    for header, intent in _SECTION_INTENTS:
        at = lines.index(header)  # a vanished section raises — that is the failure
        documented = {}
        for line in lines[at + 1 :]:
            if line.startswith("#"):
                break
            if line.startswith("| `"):
                cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
                documented[cells[0].strip("`")] = cells[-1]
        expected = {r.id: r.severity for r in REGISTRY.rules() if r.domain == intent}
        assert documented == expected, (
            f"README rule table for {intent!r} drifted from the registry"
        )
    registry_intents = {r.domain for r in REGISTRY.rules()}
    assert registry_intents == {intent for _, intent in _SECTION_INTENTS}, (
        "a registry intent has no README rule-table section"
    )


def test_gap_name_lists_match_registry() -> None:
    text = README_PATH.read_text(encoding="utf-8")
    section = text.split("## The gap vocabulary", 1)[1].split("\n## ", 1)[0]
    documented = {}
    for line in section.splitlines():
        match = re.match(r"- \*\*(\w+):?\*\*\s*(.*)", line)
        if not match:
            continue
        intent = _GAP_LABELS[match.group(1)]
        documented[intent] = sorted(re.findall(r"`([^`]+)`", match.group(2)))
    assert set(documented) == set(_GAP_LABELS.values()), "a gap list is missing from README"
    for intent, gaps in documented.items():
        expected = sorted(
            {r.gap for r in REGISTRY.rules() if r.domain == intent and r.gap is not None}
        )
        assert gaps == expected, f"README gap list for {intent!r} drifted from the registry"


def test_cli_examples_behave_as_documented() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "inputguard.cli", "analyze", "make this faster", "--mode", "strict"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0
    text_blocks = _blocks("text")
    assert len(text_blocks) == 1, "README should embed exactly one CLI output block"
    assert proc.stdout.strip() == text_blocks[0].strip(), (
        "README CLI output drifted from the real CLI"
    )

    gated = subprocess.run(
        [sys.executable, "-m", "inputguard.cli", "analyze", "build a REST API", "--min-score", "85"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert gated.returncode == 1, "--min-score below the floor must exit 1"

    bash_blocks = _blocks("bash")
    assert any("pip install inputguard" in block for block in bash_blocks)
    assert any("inputguard analyze" in block for block in bash_blocks)
