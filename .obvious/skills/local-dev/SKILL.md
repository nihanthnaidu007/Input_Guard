---
name: local-dev
description: How to set up, run, and verify local development for the InputGuard library
---

# local-dev — InputGuard

## Context

Pure-Python library, zero runtime deps, zero external services. Recorded during Autobuild
onboarding on 2026-09-17 (`main` @ `1dc9521`, Python 3.13.14). Everything below was
executed and passed; nothing here is inferred.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

- No env vars, no lockfile, no infra to start. A fresh checkout has no `.venv` — create it
  before any pytest/build step.
- No leftover lock/egg-info files existed at onboarding time.

## Verify

```bash
.venv/bin/python -m pytest tests/ -v     # canonical check: 89 tests, ~0.1s
.venv/bin/python -m compileall -q inputguard tests
.venv/bin/python -m build && .venv/bin/python -m twine check dist/*
```

Primary-flow smoke (the library's end-to-end path):

```python
from inputguard import InputGuard

warn, strict = InputGuard(), InputGuard(mode="strict")
r = warn.analyze("fix my code")
assert r.detected_intent == "debug"
assert r.status == "needs_clarification" and r.clarity_score == 35
assert not r.is_clear() and r.recommendations
assert strict.analyze("build a REST API").status == "blocked"
well = warn.analyze(
    "Fix this Python function get_users() - it should return a list of user dicts "
    "but instead returns None. The error says: TypeError: NoneType is not iterable on line 45."
)
assert well.status == "ready" and well.clarity_score == 100
```

## Gotchas

- There is no server, port, or health endpoint — "healthy" means tests pass and the smoke
  flow runs. Do not invent a start command.
- No lint/typecheck tooling is configured; pytest is the repo's canonical verification.
- `dist/`, `.venv/`, egg-info are gitignored — builds never dirty the worktree.
- Intent tie-break: debug always wins (deliberate, covered by tests).
