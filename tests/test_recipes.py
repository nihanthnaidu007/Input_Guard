"""docs/recipes example gate: the recipe code blocks execute.

Each recipe is split into a framework-free block (pure inputguard, runs
verbatim) and a wiring block whose only framework usage is the runnable/
completion idiom. The tests run every block in order inside a fresh
subprocess, with minimal stubs for the framework imports — proving the
inputguard-side contract the recipe relies on, without adding framework
dependencies to this repository.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

RECIPES_DIR = Path(__file__).resolve().parent.parent / "docs" / "recipes"
_FENCE = re.compile(r"```python\n(.*?)```", re.DOTALL)

# Minimal langchain-core runnable protocol: RunnableLambda wraps a callable,
# `|` composes pipelines left-to-right, .invoke() runs the chain.
_LANGCHAIN_STUB = """
import types as _types

class _Pipeline:
    def __init__(self, steps): self._steps = steps
    def __or__(self, other): return _Pipeline(self._steps + [other])
    def invoke(self, value):
        for step in self._steps:
            value = step.invoke(value)
        return value

class RunnableLambda:
    def __init__(self, fn): self._fn = fn
    def invoke(self, value): return self._fn(value)
    def __or__(self, other): return _Pipeline([self, other])

_langchain_core = _types.ModuleType("langchain_core")
_runnables = _types.ModuleType("langchain_core.runnables")
_runnables.RunnableLambda = RunnableLambda
_langchain_core.runnables = _runnables
sys.modules["langchain_core"] = _langchain_core
sys.modules["langchain_core.runnables"] = _runnables
"""

# The clarify path must return before the completion call — the stub raises
# if the recipe wiring ever reaches the model on the demo input.
_LITELLM_STUB = """
import types as _types

def _completion(*args, **kwargs):
    raise AssertionError("litellm.completion called on the clarify path")

litellm = _types.ModuleType("litellm")
litellm.completion = _completion
sys.modules["litellm"] = litellm
"""

_RUNNERS = {
    "langchain.md": _LANGCHAIN_STUB,
    "litellm.md": _LITELLM_STUB,
}


def test_both_recipe_pages_exist_and_use_to_dict() -> None:
    for name in _RUNNERS:
        page = RECIPES_DIR / name
        assert page.is_file(), f"missing recipe page docs/recipes/{name}"
        assert "to_dict()" in page.read_text(encoding="utf-8")


def test_recipe_blocks_execute_in_document_order() -> None:
    for name, stub_setup in _RUNNERS.items():
        page = RECIPES_DIR / name
        blocks = _FENCE.findall(page.read_text(encoding="utf-8"))
        assert len(blocks) >= 2, f"{name}: expected preflight + wiring blocks"
        script = "import sys\n" + stub_setup + "\n" + "\n\n".join(blocks)
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert proc.returncode == 0, (
            f"A docs/recipes/{name} example failed.\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )
