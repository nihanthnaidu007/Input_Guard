# InputGuard
[![PyPI version](https://badge.fury.io/py/inputguard.svg)](https://pypi.org/project/inputguard/)

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

A non-technical user asks for "an app". The AI invents a stack, a schema, an auth scheme. Five rounds of correction later, you're closer to what they actually wanted. InputGuard catches the gaps locally, in milliseconds, before any tokens are spent.

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
result = guard.analyze("build a REST API")

print(result.status)         # 'needs_clarification'
print(result.clarity_score)  # 50
print(result.gaps)           # ['programming language', 'api structure']
print(result.is_clear())     # False

for rec in result.recommendations:
    print(rec["gap"])
    print(rec["what_is_missing"])
    print(rec["what_to_provide"])
    print(rec["why_it_matters"])
    print()
```

Actual output of the recommendations loop:

```
programming language
You haven't told it which programming language or technology to use.
Add something like 'using Python', 'in JavaScript with React', or 'with Node.js'. If you're not sure which to use, say what device or platform you want it to run on, like 'runs in a web browser' or 'runs on my Mac'.
Without this, the AI picks a language on its own. You might get something built in a language you don't have installed or can't run on your machine.

api structure
You mentioned an API but didn't describe what it should do or how it should work.
Describe the actions it needs to support. For example: 'it needs to get a list of users, create a new user, and delete a user by their ID'. You don't need to use technical terms, just describe what it does.
Without this, the AI invents its own structure. You will spend hours correcting routes, field names, and data shapes you never asked for.
```

`analyze()` takes an optional `domain` argument, which defaults to `"coding"`. Phase 1 supports `"coding"` only.

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

## What gets checked

Phase 1 covers coding build inputs: requests like "build me an X", "integrate with Y", "add Z". Eight rules run against the normalized input. Six look for specific missing pieces. Two are safety nets that catch inputs the term sets would otherwise miss.

| Rule code | What it catches | Severity |
|---|---|---|
| `missing_language` | A build/action verb is present but no programming language or framework is named. | high |
| `missing_api_structure` | API terms appear (REST, GraphQL, endpoint…) but no routes, HTTP methods, or request/response shape are described. | high |
| `missing_data_model` | Storage terms appear (database, CRUD, schema…) but no fields, entities, or model are described. | high |
| `missing_integration_specifics` | A third-party service is named (Stripe, Twilio, AWS…) but no specific action or feature is described. | medium |
| `missing_auth_type` | Authentication is mentioned but no concrete type (JWT, OAuth, magic link…) is named. | high |
| `missing_output_format` | A top-level build verb is present but no output format (web app, CLI, REST API, script…) is named. Does not fire on connector verbs like "integrate" or "add". | medium |
| `intent_without_language` | Build intent is expressed without a creation verb ("I need…", "I want…", "looking for…", "put together…") and no language is named. | high |
| `insufficient_context` | Catch-all. Fires when nothing else fires, the input is at least 5 words, is not a question, and contains no specificity signal at all. | high |

---

## The result object

`analyze()` returns an immutable `AnalysisResult` with these fields:

| Field | Type | Description |
|---|---|---|
| `status` | `str` | One of `"ready"`, `"usable_with_warnings"`, `"needs_clarification"`, `"blocked"` |
| `clarity_score` | `int` | 0 to 100 |
| `gaps` | `List[str]` | Gap names, in the order rules fired |
| `recommendations` | `List[dict]` | One dict per gap (see next section) |
| `findings` | `List[RuleFinding]` | Raw rule findings (code, message, severity, gap) |
| `interpretation_note` | `Optional[str]` | Set when the input is highly ambiguous (score < 50 or two or more high-severity findings) |

Helpers:

- `result.is_clear()` — `True` only when status is `"ready"`
- `result.to_dict()` — full result as a plain JSON-serializable dict

Example `result.to_dict()` for `guard.analyze("build a CRUD app with a database")`:

```json
{
  "status": "needs_clarification",
  "clarity_score": 35,
  "gaps": [
    "programming language",
    "data model",
    "output format"
  ],
  "recommendations": [
    {
      "gap": "programming language",
      "what_is_missing": "You haven't told it which programming language or technology to use.",
      "what_to_provide": "Add something like 'using Python', 'in JavaScript with React', or 'with Node.js'. If you're not sure which to use, say what device or platform you want it to run on, like 'runs in a web browser' or 'runs on my Mac'.",
      "why_it_matters": "Without this, the AI picks a language on its own. You might get something built in a language you don't have installed or can't run on your machine."
    },
    {
      "gap": "data model",
      "what_is_missing": "You mentioned storing data but didn't say what data or what details need to be saved.",
      "what_to_provide": "List the main things you need to store and what information matters for each. For example: 'store users with their name, email address, and password' or 'products with a title, price, and how many are in stock'.",
      "why_it_matters": "Without this, the AI guesses your entire database structure. The names, fields, and data types will be wrong and you will have to rebuild them from scratch."
    },
    {
      "gap": "output format",
      "what_is_missing": "You didn't say what kind of thing you're building or how it will be used.",
      "what_to_provide": "Add something like: 'as a web app I can open in a browser', 'as a command-line tool I run in my terminal', 'as a REST API', 'as a Python script', or 'as a mobile app'. Pick whichever matches how you plan to use it.",
      "why_it_matters": "A web app, a script, and an API that do the same job look completely different in code. Without this, the AI picks one and you might get the wrong one entirely."
    }
  ],
  "findings": [
    {"code": "missing_language",      "message": "No programming language or framework detected.",                          "severity": "high",   "gap": "programming language"},
    {"code": "missing_data_model",    "message": "Storage or database mentioned but no fields, entities, or model described.","severity": "high",   "gap": "data model"},
    {"code": "missing_output_format", "message": "Build request detected but no output or delivery format specified.",      "severity": "medium", "gap": "output format"}
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

The seven gap names that can appear are:
`programming language`, `api structure`, `data model`, `integration specifics`, `authentication type`, `output format`, `task context`.

---

## Real-world examples

```python
from inputguard import InputGuard
guard = InputGuard()

guard.analyze("build me an app")
#   score:  60
#   status: usable_with_warnings
#   gaps:   ['programming language', 'output format']

guard.analyze("integrate with Stripe")
#   score:  60
#   status: usable_with_warnings
#   gaps:   ['programming language', 'integration specifics']

guard.analyze(
    "Build a REST API using FastAPI. "
    "Store users in PostgreSQL with fields: id, name, email. "
    "Expose GET /users and POST /users endpoints. "
    "Add JWT authentication."
)
#   score:  100
#   status: ready
#   gaps:   []
```

The vague input is flagged in two places. The partial input is flagged on the missing language and on the unspecified Stripe action. The specific input passes cleanly.

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
│   ├── recommender.py
│   ├── scorer.py
│   ├── types.py
│   ├── py.typed
│   └── rules/
│       ├── __init__.py
│       └── coding.py
├── tests/
│   └── test_coding.py
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
