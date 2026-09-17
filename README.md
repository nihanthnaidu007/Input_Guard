# InputGuard
[![PyPI version](https://img.shields.io/pypi/v/inputguard.svg)](https://pypi.org/project/inputguard/)

Catch unclear inputs before they become bad AI outputs.

InputGuard is a pre-flight input clarity layer. It sits between a user's input and an LLM call. It detects vague, incomplete, or unspecific inputs before they reach the AI — saving the correction cycle that wastes time and tokens when the AI guesses wrong.

Zero LLM calls. Zero external dependencies. Pure local Python.

---

## The problem it solves

**Without InputGuard**

```
vague input → AI guesses → wrong output → correction loop → more tokens → repeat
```

**With InputGuard**

```
vague input → InputGuard flags what's missing → user clarifies → AI gets it right first time
```

A non-technical user asks to "fix my code." The AI guesses at the problem, picks the wrong function, and produces a fix for something that was not broken. InputGuard catches the gaps locally, in milliseconds, before any tokens are spent.

---

## Install

```bash
pip install inputguard
```

Python 3.9+. No external dependencies.

---

## Quick start

```python
from inputguard import InputGuard

guard = InputGuard()
result = guard.analyze("fix my code")

print(result.detected_intent)   # 'debug'
print(result.status)            # 'needs_clarification'
print(result.clarity_score)     # 35
print(result.gaps)              # ['error description', 'expected vs actual behavior', 'code context']
print(result.is_clear())        # False

for rec in result.recommendations:
    print(rec["gap"])
    print(rec["what_is_missing"])
    print(rec["what_to_provide"])
    print(rec["why_it_matters"])
    print()
```

`analyze()` takes an optional `domain` argument, which defaults to `"coding"`. Phase 1 supports `"coding"` only. Intent detection is automatic — no extra parameters needed.

---

## Modes

```python
from inputguard import InputGuard

# Warning mode (default) — flags gaps but allows the input through
warn_guard = InputGuard(mode="warning")

# Strict mode — blocks inputs that fall below the clarity threshold
strict_guard = InputGuard(mode="strict")

result_warn   = warn_guard.analyze("build a REST API")
result_strict = strict_guard.analyze("build a REST API")

print(result_warn.status)    # 'needs_clarification'
print(result_strict.status)  # 'blocked'
print(result_warn.clarity_score == result_strict.clarity_score)  # True
```

The clarity score is mode-independent. Only the status threshold changes.

| Status | Warning mode | Strict mode |
|---|---|---|
| `ready` | score ≥ 85 | score ≥ 85 |
| `usable_with_warnings` | score 60–84 | never |
| `needs_clarification` | score < 60 | score 65–84 |
| `blocked` | never | score < 65 |

Use `warning` when you want to surface gaps to the user without blocking. Use `strict` when you want to refuse to forward vague input to the LLM.

---

## Non-English input

InputGuard's rules are English-language heuristics. Before any rule runs, a zero-dependency script probe (stdlib `unicodedata` only) classifies the input's script. When the script has no heuristic coverage, InputGuard says so instead of pretending:

```python
result = guard.analyze("建造一个用户登录应用")

result.status              # 'usable_with_warnings' — never 'ready'
result.clarity_score       # 80 (100 minus the degradation penalty)
result.detected_intent     # 'undetermined'
result.detected_language   # 'zh' (coarse, script-derived guess)
result.heuristic_coverage  # 'none'
result.degradation_note    # explains that rules were skipped and why
```

The rules are **skipped explicitly** on uncovered scripts — running English keyword rules on text they cannot read would produce a silent, unearned verdict. A degraded result is never `ready` in either mode (strict mode returns `needs_clarification`). In v0.2 this input silently scored 100/ready; v0.3 refuses to assert a confidence it does not have.

Three additive fields on the result carry the probe's verdict:

| Field | Values |
|---|---|
| `detected_language` | coarse script-derived guess (`'en'`, `'zh'`, `'ja'`, `'ko'`, `'ru'`, `'ar'`, ...; `'und'` when unclassifiable) |
| `heuristic_coverage` | `'full'` (≥ 70% of letters covered — rules run exactly as before), `'partial'` (50–70% — rules run, note flags the uncovered remainder), `'none'` (degraded path), `'unknown'` (no letters to classify) |
| `degradation_note` | `None`, or an explanation of what was skipped and why |

Mixed input is handled by share, not by exclusion: `"make it faster 这个"` is still fully analyzed (English dominates and the rules run); input whose letters fall 50–70% inside coverage gets a `partial` note without a penalty.

---

## How intent detection works

InputGuard automatically detects what kind of coding input it is receiving. No extra parameters needed. The same `.analyze()` call handles all five intent types.

| Intent | What it covers | Example input |
|---|---|---|
| `build` | New app or system from scratch | "build a REST API" |
| `debug` | Fixing errors, bugs, broken code | "fix my code, getting a TypeError" |
| `optimization` | Performance, speed, refactoring | "make this function faster" |
| `explanation` | Understanding code or concepts | "explain what this decorator does" |
| `feature` | Adding to existing code | "add search to my existing React app" |

```python
guard = InputGuard()

guard.analyze("build a REST API").detected_intent           # 'build'
guard.analyze("fix my code").detected_intent               # 'debug'
guard.analyze("make this faster").detected_intent          # 'optimization'
guard.analyze("explain how async works").detected_intent   # 'explanation'
guard.analyze("add search to my existing app").detected_intent  # 'feature'
```

When an input is ambiguous, debug always wins. "Fix this slow function" is a debug request, not optimization. Priority order is: debug → optimization → explanation → feature → build.

---

## What gets checked

### Build inputs

Requests like "build me an X", "integrate with Y", "create a Z". Eight rules run against the normalized input.

| Rule code | What it catches | Severity |
|---|---|---|
| `missing_language` | A build/action verb is present but no programming language or framework is named. | high |
| `missing_api_structure` | API terms appear (REST, GraphQL, endpoint…) but no routes, HTTP methods, or request/response shape are described. | high |
| `missing_data_model` | Storage terms appear (database, CRUD, schema…) but no fields, entities, or model are described. | high |
| `missing_integration_specifics` | A third-party service is named (Stripe, Twilio, AWS…) but no specific action or feature is described. | medium |
| `missing_auth_type` | Authentication is mentioned but no concrete type (JWT, OAuth, magic link…) is named. | high |
| `missing_output_format` | A top-level build verb is present but no output format (web app, CLI, REST API, script…) is named. Does not fire on connector verbs like "integrate" or "add". | medium |
| `intent_without_language` | Build intent is expressed without a creation verb ("I need…", "I want…", "looking for…") and no language is named. | high |
| `insufficient_context` | Catch-all. Fires when nothing else fires, the input is at least 3 words, and is not a question. | high |

### Debug inputs

Requests like "fix my code", "it's not working", "getting a TypeError".

| Rule code | What it catches | Severity |
|---|---|---|
| `missing_error_message` | Debug intent detected but no error message, exception name, or stack trace described. | high |
| `missing_expected_vs_actual` | No description of what should happen vs what actually happens. | high |
| `missing_debug_code_context` | No language, function name, file, or snippet referenced. | medium |

### Optimization inputs

Requests like "make this faster", "optimize my code", "refactor this function".

| Rule code | What it catches | Severity |
|---|---|---|
| `missing_optimization_target` | Optimization requested but no specific function, component, or area identified. | high |
| `missing_performance_baseline` | No current measurement or observed problem described. | medium |
| `missing_optimization_constraint` | No constraints or acceptable tradeoffs mentioned. | low |

### Explanation inputs

Requests like "explain this code", "what does this do", "how does this work".

| Rule code | What it catches | Severity |
|---|---|---|
| `missing_code_reference` | Explanation requested but no specific code, function, or concept referenced. | high |
| `missing_explanation_depth` | No indication of depth or detail level requested. | low |

### Feature inputs

Requests like "add search to my existing app", "extend my current API with pagination".

| Rule code | What it catches | Severity |
|---|---|---|
| `missing_existing_stack` | Feature addition requested but no existing language, framework, or tech stack mentioned. | high |
| `missing_feature_scope` | Feature requested but no definition of what it should specifically do. | high |
| `missing_completion_criteria` | No definition of what done looks like for this feature. | low |

---

## The result object

`analyze()` returns an immutable `AnalysisResult` with these fields:

| Field | Type | Description |
|---|---|---|
| `status` | `str` | One of `"ready"`, `"usable_with_warnings"`, `"needs_clarification"`, `"blocked"` |
| `clarity_score` | `int` | 0 to 100 |
| `detected_intent` | `str` | Which intent was detected: `build`, `debug`, `optimization`, `explanation`, or `feature` |
| `gaps` | `List[str]` | Gap names, in the order rules fired |
| `recommendations` | `List[dict]` | One dict per gap (see next section) |
| `findings` | `List[RuleFinding]` | Raw rule findings (code, message, severity, gap) |
| `interpretation_note` | `Optional[str]` | Set when the input is highly ambiguous (score < 50 or two or more high-severity findings) |

Helpers:

- `result.is_clear()` — `True` only when status is `"ready"`
- `result.to_dict()` — full result as a plain JSON-serializable dict

Example `result.to_dict()` for `guard.analyze("fix my code")`:

```json
{
  "status": "needs_clarification",
  "clarity_score": 35,
  "detected_intent": "debug",
  "gaps": [
    "error description",
    "expected vs actual behavior",
    "code context"
  ],
  "recommendations": [
    {
      "gap": "error description",
      "what_is_missing": "You haven't included the actual error message or exception.",
      "what_to_provide": "Copy and paste the exact error message. For example: 'I'm getting TypeError: cannot read property of undefined on line 23'.",
      "why_it_matters": "The exact wording tells the AI exactly what went wrong. Without it, the AI guesses and often fixes the wrong thing."
    },
    {
      "gap": "expected vs actual behavior",
      "what_is_missing": "You haven't described what should happen vs what actually happens.",
      "what_to_provide": "Describe both. For example: 'it should return a list of users but instead returns None every time'.",
      "why_it_matters": "Without this, the AI is guessing what the problem is. It may fix something that was not broken."
    },
    {
      "gap": "code context",
      "what_is_missing": "You haven't pointed to the specific part of your code with the problem.",
      "what_to_provide": "Name the language and the function. For example: 'this is a Python function called get_users()'.",
      "why_it_matters": "The more specific you are, the more targeted the fix will be."
    }
  ],
  "findings": [
    {"code": "missing_error_message",      "message": "Debug request detected but no error message or exception described.", "severity": "high",   "gap": "error description"},
    {"code": "missing_expected_vs_actual", "message": "No description of expected vs actual behavior provided.",            "severity": "high",   "gap": "expected vs actual behavior"},
    {"code": "missing_debug_code_context", "message": "No code context provided.",                                          "severity": "medium", "gap": "code context"}
  ],
  "interpretation_note": "This input is ambiguous in multiple ways. Addressing each gap below before sending will prevent the AI from making assumptions that lead to the wrong output."
}
```

---

## Recommendations

Every entry in `result.recommendations` is a plain dict with four keys, all written for non-technical users:

```python
for rec in result.recommendations:
    print(rec["gap"])             # which gap this addresses
    print(rec["what_is_missing"]) # plain English — what the user forgot
    print(rec["what_to_provide"]) # concrete example they can copy
    print(rec["why_it_matters"])  # what goes wrong if they skip it
```

Gap names by intent type:

- **Build:** `programming language`, `api structure`, `data model`, `integration specifics`, `authentication type`, `output format`, `task context`
- **Debug:** `error description`, `expected vs actual behavior`, `code context`
- **Optimization:** `optimization target`, `performance baseline`, `optimization constraint`
- **Explanation:** `code reference`, `explanation depth`
- **Feature:** `existing stack`, `feature scope`, `completion criteria`

---

## Real-world examples

```python
from inputguard import InputGuard
guard = InputGuard()

# Build — vague
guard.analyze("build me an app")
#   detected_intent: 'build'
#   score:  60
#   status: usable_with_warnings
#   gaps:   ['programming language', 'output format']

# Debug — vague
guard.analyze("fix my code")
#   detected_intent: 'debug'
#   score:  35
#   status: needs_clarification
#   gaps:   ['error description', 'expected vs actual behavior', 'code context']

# Optimization — vague
guard.analyze("make this faster")
#   detected_intent: 'optimization'
#   score:  55
#   status: needs_clarification
#   gaps:   ['optimization target', 'performance baseline', 'optimization constraint']

# Build — fully specified
guard.analyze(
    "Build a REST API using FastAPI. "
    "Store users in PostgreSQL with fields: id, name, email. "
    "Expose GET /users and POST /users endpoints. "
    "Add JWT authentication."
)
#   detected_intent: 'build'
#   score:  100
#   status: ready
#   gaps:   []

# Debug — fully specified
guard.analyze(
    "Fix this Python function get_users() — it should return a list "
    "of user dicts but instead returns None. "
    "The error says: TypeError: NoneType is not iterable on line 45."
)
#   detected_intent: 'debug'
#   score:  100
#   status: ready
#   gaps:   []
```

---

## Integration pattern

Drop it in front of your existing LLM call. Two minimal patterns:

```python
from inputguard import InputGuard

guard = InputGuard(mode="warning")

def handle_user_input(user_input: str):
    result = guard.analyze(user_input)

    if result.status in ("needs_clarification", "blocked"):
        # Return feedback to the user before calling the LLM
        return {
            "status": result.status,
            "detected_intent": result.detected_intent,
            "gaps": result.gaps,
            "recommendations": result.recommendations,
        }

    # Input is clear enough — proceed to LLM
    return call_your_llm(user_input)
```

For a hard gate, use `mode="strict"` and check `result.is_clear()`:

```python
guard = InputGuard(mode="strict")

def handle_user_input(user_input: str):
    result = guard.analyze(user_input)
    if not result.is_clear():
        return {
            "status": result.status,
            "detected_intent": result.detected_intent,
            "gaps": result.gaps,
            "recommendations": result.recommendations,
        }
    return call_your_llm(user_input)
```

---

## Package layout

```
inputguard/
├── inputguard/
│   ├── __init__.py
│   ├── analyzer.py
│   ├── detector.py
│   ├── recommender.py
│   ├── scorer.py
│   ├── types.py
│   ├── py.typed
│   └── rules/
│       ├── __init__.py
│       ├── coding.py
│       ├── debug.py
│       ├── optimization.py
│       ├── explanation.py
│       └── feature.py
├── tests/
│   ├── test_coding.py
│   ├── test_detector.py
│   ├── test_debug.py
│   ├── test_optimization.py
│   ├── test_explanation.py
│   └── test_feature.py
├── pyproject.toml
└── README.md
```

---

## Development

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

---

## Publishing

```bash
python -m build
python -m twine check dist/*
python -m twine upload dist/*
```

---

## License

MIT — see [LICENSE](LICENSE) for the full text.

Copyright © 2026 Nihanth Kalisetti.