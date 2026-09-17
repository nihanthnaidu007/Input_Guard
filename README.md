# InputGuard
[![PyPI version](https://img.shields.io/pypi/v/inputguard.svg)](https://pypi.org/project/inputguard/)

Catch unclear inputs before they become bad AI outputs.

InputGuard is a pre-flight input clarity layer. It sits between a user's input and an LLM call. It detects vague, incomplete, or unspecific inputs before they reach the AI — saving the correction cycle that wastes time and tokens when the AI guesses wrong. When it finds gaps, it returns the questions that close them, ready to send back to the user.

Zero LLM calls. Zero external dependencies. Pure local Python.

- **Deterministic rules you can extend** — register your own rules and analysis domains through the same typed API the built-ins use.
- **Calibration as data** — status bands, severity penalties, rule filters, and the input cap live in one frozen `Policy` object.
- **Honest by construction** — non-English input is reported as a limitation of the tool, never silently scored `ready`.

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

Python 3.9+. No external dependencies — `pip install inputguard` imports nothing outside the standard library.

---

## Quick start

```python
from inputguard import InputGuard

guard = InputGuard()
result = guard.analyze("fix my code")

assert result.detected_intent == "debug"
assert result.status == "needs_clarification"
assert result.clarity_score == 35
assert result.gaps == ["error description", "expected vs actual behavior", "code context"]
assert result.is_clear() is False
```

Every gap comes with plain-English advice and the questions that close it:

```python
for question in result.follow_ups:
    print("-", question)

assert len(result.follow_ups) == 3
assert result.follow_ups[0].startswith("What is the exact error message")
```

`analyze()` takes an optional `domain` argument, which defaults to `"coding"`. Three domains ship built in — `coding`, `writing`, and `data-analysis` — and you can register your own (see [Custom domains](#custom-domains)).

---

## The public API

Nine names; everything else is internal:

```python
from inputguard import (
    AnalysisResult,
    InputGuard,
    Policy,
    REGISTRY,
    Rule,
    RuleFinding,
    __version__,
    register_domain,
    register_rule,
)
```

| Name | What it is |
|---|---|
| `InputGuard` | The engine: `InputGuard(mode="warning", policy=None)` |
| `AnalysisResult` | The frozen result of `analyze()` |
| `RuleFinding` | One rule's raw verdict: `code`, `message`, `severity`, `gap` |
| `Policy` | Frozen calibration: bands, penalties, filters, input cap |
| `Rule` | The protocol a custom rule implements |
| `register_rule` | Register one rule (decorator or call) |
| `register_domain` | Register an analysis domain: intent signals + rules |
| `REGISTRY` | The process-global registry (read during `analyze()`) |
| `__version__` | The installed version string |

---

## Modes

```python
from inputguard import InputGuard

# Warning mode (default) — flags gaps but allows the input through
warn_guard = InputGuard(mode="warning")

# Strict mode — blocks inputs that fall below the clarity threshold
strict_guard = InputGuard(mode="strict")

result_warn = warn_guard.analyze("build a REST API")
result_strict = strict_guard.analyze("build a REST API")

assert result_warn.status == "needs_clarification"
assert result_strict.status == "blocked"
assert result_warn.clarity_score == result_strict.clarity_score
```

The clarity score is mode-independent. Only the status threshold changes.

| Status | Warning mode | Strict mode |
|---|---|---|
| `ready` | score ≥ 85 | score ≥ 85 |
| `usable_with_warnings` | score 60–84 | never |
| `needs_clarification` | score < 60 | score 65–84 |
| `blocked` | never | score < 65 |
| `degraded` | never (language limitation — see Non-English input) | never (language limitation) |

Use `warning` when you want to surface gaps to the user without blocking. Use `strict` when you want to refuse to forward vague input to the LLM.

---

## Follow-up questions

Every gap maps to one or two templated clarifying questions — the sentence the user can answer verbatim. Questions dedupe and order with the gaps:

```python
result = guard.analyze("make this faster")

assert result.gaps == [
    "optimization target",
    "performance baseline",
    "optimization constraint",
]
assert result.follow_ups[0] == "Which function or module should get faster?"
```

A gap with no built-in question table entry — including gaps from your own custom rules — gets a documented fallback question, never silence. The same contract holds for recommendations.

---

## Non-English input

InputGuard's rules are English-language heuristics. Before any rule runs, a zero-dependency script probe (stdlib `unicodedata` only) classifies the input's script and language. Inputs the rules cannot assess take the explicit degraded path — an uncovered dominant script, Latin-script text recognized as French/Spanish/Portuguese by its function words, or a Latin-dominant input carrying a run of 3+ consecutive uncovered-script letters. In every case InputGuard says so instead of pretending:

```python
result = guard.analyze("建造一个用户登录应用")

assert result.status == "degraded"
assert result.clarity_score == 80  # 100 minus the degradation penalty
assert result.detected_intent == "undetermined"
assert result.detected_language == "zh"
assert result.heuristic_coverage == "none"
assert result.degradation_note is not None
```

The rules are **skipped explicitly** — running English keyword rules on text they cannot assess would produce a silent, unearned verdict or spurious gaps invented out of the silence. A degraded result reports the literal `degraded` status in both modes: it is the tool reporting a language limitation of itself, not a judgment of the input's clarity (strict mode's banding would otherwise read as an ordinary critique). In v0.2 this input silently scored 100/ready; v0.3 refuses to assert a confidence it does not have.

Four additive fields on the result carry the probe's verdict:

| Field | Values |
|---|---|
| `detected_language` | coarse script-derived guess (`'en'`, `'zh'`, `'ja'`, `'ko'`, `'ru'`, `'ar'`, `'fr'`, `'es'`, `'pt'`, ...; `'und'` when unclassifiable) |
| `heuristic_coverage` | `'full'` (≥ 70% of letters covered — rules run exactly as before), `'partial'` (50–70% — rules run, note flags the uncovered remainder), `'none'` (degraded path), `'unknown'` (no letters to classify) |
| `degradation_note` | `None`, or an explanation of what was skipped and why |
| `truncated` | `True` when the input was capped to the 10,000-character limit (preserved even on the degraded path) |

The degraded path covers three shapes of input the English rules cannot assess:

- **Uncovered script** — the dominant script (Cyrillic, Arabic, Han, ...) has no heuristic coverage.
- **Non-English Latin** — French, Spanish, and Portuguese text is 100% Latin script yet just as unreadable to English-only rules, which would find nothing and invent gaps out of the silence. A function-word layer recognizes those three languages — enough distinct stop-word hits with a margin over the input's English function-word evidence — and degrades them like any other uncovered language. German, Italian, Dutch, and other Latin-script languages are a documented blind spot and still pass as before. Accented English (`café`) and short telegraphic prompts (`build todo api`) still run the rules.
- **Mixed scripts** — a run of 3+ consecutive letters in an uncovered script degrades even a majority-English input ("Fix this bug 修复这个错误 in the payment flow"): that clause is content the rules cannot audit. A short borrow like `"make it faster 这个"` still rides along, and input at 50–70% coverage keeps the `partial` path with its note.

```python
result = guard.analyze("Preciso de um aplicativo web com login de usuário e relatórios")

assert result.detected_language == "pt"
assert result.heuristic_coverage == "none"
assert result.status == "degraded"
assert "Portuguese" in result.degradation_note
```

---

## Custom rules

The extension contract is four members and one method. Built-in rules register through the exact same path — the API is exercised by all 31 built-in rules before anyone writes their own.

```python
from typing import Optional

from inputguard import RuleFinding, register_domain

class CheckRollbackPlan:
    id = "missing_rollback_plan"   # unique across the registry
    domain = "deploy"              # the INTENT name this rule runs for
    severity = "high"              # "low" | "medium" | "high" — validated
    gap = "rollback plan"          # groups findings for scoring dedup

    def check(self, text: str) -> Optional[RuleFinding]:
        # text arrives normalized: lowercased, whitespace-collapsed.
        if "rollback" not in text and "roll back" not in text:
            return RuleFinding(
                code=self.id,
                message="No rollback plan described.",
                severity=self.severity,
                gap=self.gap,
            )
        return None
```

The rule above ships with the custom domain in the next section — `register_domain` registers rules through the same path `register_rule` uses, once the intents they name exist. The contracts a rule author accepts:

- **`check` receives normalized text** (lowercased, whitespace-collapsed) and returns at most one `RuleFinding`, or `None` when the rule does not fire.
- **A `check` exception is never swallowed** — it aborts the `analyze()` call in flight, naming the rule and where it was registered.
- **Registration is permanent** for the process lifetime (there is no unregister), and `REGISTRY` is a process-global singleton shared by everything that imports inputguard.
- **Duplicate rule ids raise `ValueError`** at registration, as do unknown severities and rules naming an intent no registered domain declares.
- **Every gap deserves advice**: a gap with no recommendation or follow-up table entry gets a documented generic fallback — never an empty list and never silence.

---

## Custom domains

A domain is a named analysis scope: intent signals in priority order, plus its rules. The single intent with empty terms is the fallback for inputs no other intent matches.

```python
register_domain(
    "devops",
    {
        "deploy": ("deploy", "deployment", "release", "rollout", "ship", "shipping"),
        "general": (),  # fallback intent — inputs no deploy signal matches
    },
    [CheckRollbackPlan],
)

result = guard.analyze("deploy the new checkout service to production", domain="devops")

assert result.detected_intent == "deploy"
assert result.gaps == ["rollback plan"]
assert result.clarity_score == 75
assert result.status == "usable_with_warnings"
assert result.follow_ups == ["Can you add the rollback plan this request is missing?"]
```

Intent names are globally unique across domains — registering a domain whose intent another domain already declares raises `ValueError`, because rules dispatch on intent name alone. The same guard rejects duplicate domain names, so re-registering `devops` above raises too.

---

## Policy: calibrate the guard

Every scoring constant is data on a frozen, validated `Policy` — with the v0.2 values pinned as defaults, so existing behavior cannot drift. Two layers stay separate: per-rule severity decides *what fires*; the policy's bands decide *what happens*.

| Field | Default | Controls |
|---|---|---|
| `ready_at` | `85` | score ≥ `ready_at` is `ready`, both modes |
| `usable_at` | `60` | warning-mode floor for `usable_with_warnings` |
| `strict_clarify_at` | `65` | strict-mode floor for `needs_clarification`; below it, strict blocks |
| `penalty_low` / `penalty_medium` / `penalty_high` | `5` / `15` / `25` | points per distinct gap, by highest severity |
| `min_words` | `3` | shorter input is never flagged as vague |
| `max_chars` | `10_000` | input cap — truncation is reported, never silent |
| `borderline_at` | `74` | near-miss band just below `ready_at` — the "worth one more pass" signal |
| `disabled_rules` | `frozenset()` | rule ids to skip entirely |
| `allow_patterns` | `()` | regex patterns; matching input is never flagged |

```python
from inputguard import Policy

# Disable a rule whose advice your product handles elsewhere —
# the disabled low-severity penalty comes back (55 -> 60) and the
# status flips out of needs_clarification.
tuned = InputGuard(
    mode="warning",
    policy=Policy(disabled_rules=frozenset({"missing_optimization_constraint"})),
)
result = tuned.analyze("make this faster")
assert result.clarity_score == 60
assert result.status == "usable_with_warnings"

# Allowlist internal input shapes — matching input is never flagged.
allowlisted = InputGuard(policy=Policy(allow_patterns=("^re:",)))
result = allowlisted.analyze("re: invoice numbering scheme question")
assert result.status == "ready"
assert result.gaps == []
```

The cap bounds every analysis; a longer input is truncated and the result says so:

```python
result = InputGuard().analyze("word " * 3000)
assert result.truncated is True
```

Policy is validated at construction — mis-ordered bands raise `ValueError` instead of silently distorting statuses — and a per-call `policy=` argument overrides the guard's for one `analyze()` call:

```python
strict = InputGuard(mode="strict")

default_bands = strict.analyze("make this faster")
assert default_bands.status == "blocked"  # 55 < 65

loosened = strict.analyze("make this faster", policy=Policy(usable_at=50, strict_clarify_at=50))
assert loosened.status == "needs_clarification"  # 55 >= 50
```

---

## CLI

A zero-dependency `argparse` front end over the same pipeline, installed as a console script:

```bash
pip install inputguard
inputguard analyze "make this faster" --mode strict
```

```text
status: blocked
clarity: 55/100
intent: optimization
domain: coding
missing: optimization target, performance baseline, optimization constraint
ask: Which function or module should get faster?
ask: How slow is it today, and what latency would be acceptable?
ask: What must not change while it gets faster — an interface, readability, behavior others depend on?
```

`--format json` emits the same `to_dict()` contract the library documents, and `--min-score` turns the CLI into a commit-hook / CI gate:

```bash
inputguard analyze "$(cat prompt.txt)" --format json --min-score 85
cat prompt.txt | inputguard analyze --stdin --min-score 85
```

Exit codes: `0` analysis completed (score at or above `--min-score` when given), `1` score below the `--min-score` floor, `2` usage error (unknown flags, missing text, invalid domain or input).

---

## How intent detection works

Each domain detects intent over its own registered signals — insertion order is the priority chain, and the fallback intent catches what no signal matches. The coding domain detects five intents automatically; no extra parameters needed.

| Intent | What it covers | Example input |
|---|---|---|
| `build` | New app or system from scratch | "build a REST API" |
| `debug` | Fixing errors, bugs, broken code | "fix my code, getting a TypeError" |
| `optimization` | Performance, speed, refactoring | "make this function faster" |
| `explanation` | Understanding code or concepts | "explain what this decorator does" |
| `feature` | Adding to existing code | "add search to my existing React app" |
| `compose` *(writing)* | Essays, emails, documents, posts | "write a blog post" |
| `analysis` *(data analysis)* | Analyzing datasets, building reports | "analyze my sales data" |

```python
assert guard.analyze("build a REST API").detected_intent == "build"
assert guard.analyze("fix my code").detected_intent == "debug"
assert guard.analyze("make this faster").detected_intent == "optimization"
assert guard.analyze("explain how async works").detected_intent == "explanation"
assert guard.analyze("add search to my existing app").detected_intent == "feature"
assert guard.analyze("write a blog post", domain="writing").detected_intent == "compose"
assert guard.analyze("analyze my sales data", domain="data-analysis").detected_intent == "analysis"
```

When a coding input is ambiguous, debug always wins. "Fix this slow function" is a debug request, not optimization. Priority order is: debug → optimization → explanation → feature → build.

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

### Writing inputs

Requests like "write a blog post", "draft an email", "proofread my essay" — analyzed with `domain="writing"`. Every gap carries its own follow-up questions, and each gap names one thing at a time — same one-gap-one-question discipline as the coding domains.

| Rule code | What it catches | Severity |
|---|---|---|
| `missing_audience` | Writing task detected but no audience or reader is specified. | high |
| `missing_purpose` | The goal — what the piece should accomplish — is not stated. | high |
| `missing_structure_format` | No length or organization guidance is provided. | medium |
| `missing_source_material` | Existing material is referenced but not provided — paste or attach the text to work from. | high |
| `missing_writing_context` | The subject or situation is not named. | medium |
| `missing_completeness` | No required content or constraints are specified. | low |

### Data-analysis inputs

Requests like "analyze my sales data", "build a dashboard", "report on this spreadsheet" — analyzed with `domain="data-analysis"`.

| Rule code | What it catches | Severity |
|---|---|---|
| `missing_dataset_source` | Analysis requested but no dataset, file, or source is named. | high |
| `missing_question_goal` | Data present but no question or goal for the analysis is stated. | high |
| `missing_deliverable_format` | No chart, table, summary, or report named as the output. | medium |
| `missing_tooling` | No tool or stack (pandas, SQL, Excel...) specified. | medium |
| `missing_volume` | No sense of data size or scope given. | low |
| `missing_reproducibility` | No refresh/reproducibility expectation stated. | low |

---

## The result object

`analyze()` returns an immutable `AnalysisResult` with these fields:

| Field | Type | Description |
|---|---|---|
| `status` | `str` | One of `"ready"`, `"usable_with_warnings"`, `"needs_clarification"`, `"blocked"`, `"degraded"` (language limitation — see Non-English input) |
| `clarity_score` | `int` | 0 to 100 |
| `detected_intent` | `str` | The detected intent: `build`, `debug`, `optimization`, `explanation`, `feature`, `compose`, `analysis`, or `undetermined` (degraded inputs) |
| `gaps` | `List[str]` | Gap names, in the order rules fired |
| `recommendations` | `List[dict]` | One dict per gap (see The gap vocabulary) |
| `follow_ups` | `List[str]` | One or two clarifying questions per gap, ready to send back to the user |
| `findings` | `List[RuleFinding]` | Raw rule findings (code, message, severity, gap) |
| `interpretation_note` | `Optional[str]` | Set when the input is highly ambiguous (score < 50 or two or more high-severity findings) |
| `detected_language` | `str` | Coarse script-derived language guess (`'en'`, `'zh'`, ...; `'und'` when unclassifiable) |
| `heuristic_coverage` | `str` | `'full'`, `'partial'`, `'none'`, or `'unknown'` — how much of the input the English rules could see |
| `degradation_note` | `Optional[str]` | Set when rule analysis was skipped or limited by language coverage |
| `borderline` | `bool` | `True` when the score sits in the near-miss band just below ready — worth one more pass |
| `truncated` | `bool` | `True` when the input was capped at 10,000 characters (only the prefix was analyzed) |
| `score_breakdown` | `Optional[dict]` | Per-contribution score arithmetic (base, per-gap penalties, final) |

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
      "what_is_missing": "You haven't shared the actual error message, exception, or output you're seeing.",
      "what_to_provide": "Include the exact error message or exception you are seeing. Copy and paste it exactly as it appears. For example: 'I'm getting TypeError: cannot read property of undefined on line 23' or 'it throws a 500 Internal Server Error with message: connection refused'. The exact wording tells the AI exactly what went wrong.",
      "why_it_matters": "Without the exact error, the AI has to guess what failure mode you're hitting. The wrong guess sends you down a fix path that doesn't apply to your actual problem."
    },
    {
      "gap": "expected vs actual behavior",
      "what_is_missing": "You haven't described what you expected to happen and what is actually happening.",
      "what_to_provide": "Describe two things: what you expected to happen, and what actually happened. For example: 'I expected the function to return a list of users, but it returns an empty list every time' or 'the button should submit the form but nothing happens when I click it'. Without this, the AI is guessing what the problem is.",
      "why_it_matters": "A bug is the gap between what you wanted and what happened. Without both sides, the AI cannot tell what counts as a fix."
    },
    {
      "gap": "code context",
      "what_is_missing": "You haven't pointed to a language, file, function, or snippet for the AI to look at.",
      "what_to_provide": "Tell it which language you are using and point to the specific part of your code that has the problem. For example: 'this is a Python function called get_users()' or 'this is in my React component UserList.jsx on line 45'. The more specific you are, the more targeted the fix will be.",
      "why_it_matters": "Without a code reference, the AI suggests generic fixes that may not apply to your actual code. Pointing to the exact location lets it propose a precise change."
    }
  ],
  "follow_ups": [
    "What is the exact error message or exception you're seeing (copy it verbatim if you can)?",
    "What did you expect to happen, and what actually happens instead?",
    "Which file, function, or part of your code does the problem live in?"
  ],
  "findings": [
    {
      "code": "missing_error_message",
      "message": "Debug request detected but no error message or exception described.",
      "severity": "high",
      "gap": "error description"
    },
    {
      "code": "missing_expected_vs_actual",
      "message": "No description of expected vs actual behavior provided.",
      "severity": "high",
      "gap": "expected vs actual behavior"
    },
    {
      "code": "missing_debug_code_context",
      "message": "No code context provided — no language, function name, or snippet referenced.",
      "severity": "medium",
      "gap": "code context"
    }
  ],
  "interpretation_note": "This input is ambiguous in multiple ways. Addressing each gap below before sending will prevent the AI from making assumptions that lead to the wrong output.",
  "detected_language": "en",
  "heuristic_coverage": "full",
  "degradation_note": null,
  "borderline": false,
  "truncated": false,
  "score_breakdown": {
    "base": 100,
    "penalties": [
      {
        "code": "missing_error_message",
        "severity": "high",
        "points": -25
      },
      {
        "code": "missing_expected_vs_actual",
        "severity": "high",
        "points": -25
      },
      {
        "code": "missing_debug_code_context",
        "severity": "medium",
        "points": -15
      }
    ],
    "final": 35
  }
}
```

---

## The gap vocabulary

Every built-in gap string, by intent. These strings are de-facto API — consumers switch on them — and every one has a recommendation and at least one follow-up question.

- **Build:** `programming language`, `api structure`, `data model`, `integration specifics`, `authentication type`, `output format`, `task context`
- **Debug:** `error description`, `expected vs actual behavior`, `code context`
- **Optimization:** `optimization target`, `performance baseline`, `optimization constraint`
- **Explanation:** `code reference`, `explanation depth`
- **Feature:** `existing stack`, `feature scope`, `completion criteria`
- **Compose:** `audience`, `purpose`, `structure/format`, `source material`, `context`, `completeness`
- **Analysis:** `dataset/source`, `question/goal`, `output format`, `tooling`, `volume`, `reproducibility`

Every entry in `result.recommendations` is a plain dict with four keys, all written for non-technical users:

```python
result = guard.analyze("fix my code")
for rec in result.recommendations:
    assert set(rec) == {"gap", "what_is_missing", "what_to_provide", "why_it_matters"}
    print(rec["gap"])             # which gap this addresses
    print(rec["what_is_missing"]) # plain English — what the user forgot
    print(rec["what_to_provide"]) # concrete example they can copy
    print(rec["why_it_matters"])  # what goes wrong if they skip it
```

---

## Real-world examples

```python
from inputguard import InputGuard

guard = InputGuard()

# Build — vague
result = guard.analyze("build me an app")
assert result.detected_intent == "build"
assert result.clarity_score == 60
assert result.status == "usable_with_warnings"
assert result.gaps == ["programming language", "output format"]

# Debug — vague
result = guard.analyze("fix my code")
assert result.clarity_score == 35
assert result.status == "needs_clarification"
assert result.gaps == ["error description", "expected vs actual behavior", "code context"]

# Optimization — vague
result = guard.analyze("make this faster")
assert result.clarity_score == 55
assert result.status == "needs_clarification"
assert result.gaps == ["optimization target", "performance baseline", "optimization constraint"]

# Build — fully specified
result = guard.analyze(
    "Build a REST API using FastAPI. "
    "Store users in PostgreSQL with fields: id, name, email. "
    "Expose GET /users and POST /users endpoints. "
    "Add JWT authentication."
)
assert result.detected_intent == "build"
assert result.clarity_score == 100
assert result.status == "ready"
assert result.gaps == []

# Debug — fully specified
result = guard.analyze(
    "Fix this Python function get_users() — it should return a list "
    "of user dicts but instead returns None. "
    "The error says: TypeError: NoneType is not iterable on line 45."
)
assert result.detected_intent == "debug"
assert result.clarity_score == 100
assert result.status == "ready"
assert result.gaps == []
```

---

## Integration pattern

Drop it in front of your existing LLM call:

```python
from inputguard import InputGuard

guard = InputGuard(mode="warning")

def call_your_llm(user_input: str) -> str:
    return "..."  # your real LLM call

def handle_user_input(user_input: str):
    result = guard.analyze(user_input)

    if result.status in ("needs_clarification", "blocked", "degraded"):
        # Surface the gaps and the questions that close them,
        # instead of calling the LLM. `degraded` inputs arrive here
        # in both modes; `blocked` only in strict mode.
        return {
            "status": result.status,
            "detected_intent": result.detected_intent,
            "gaps": result.gaps,
            "follow_ups": result.follow_ups,
            "recommendations": result.recommendations,
        }

    # Input is clear enough — proceed to LLM
    return call_your_llm(user_input)

payload = handle_user_input("fix my code")
assert payload["status"] == "needs_clarification"
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
            "follow_ups": result.follow_ups,
        }
    return call_your_llm(user_input)

payload = handle_user_input("make this faster")
assert payload["status"] == "blocked"
```

Framework-ready versions of this pattern — LangChain and LiteLLM, consuming `to_dict()` output — live in [docs/recipes/](docs/recipes/). The recipes are copy-paste patterns, not adapter packages: inputguard stays zero-dependency.

---

## Package layout

```
inputguard/
├── inputguard/
│   ├── __init__.py        # public exports
│   ├── analyzer.py        # the analyze() pipeline
│   ├── cli.py             # the inputguard console script
│   ├── detector.py        # intent detection (coding signal chain)
│   ├── followups.py       # per-gap clarifying questions
│   ├── language.py        # script probe / multilingual degradation
│   ├── matching.py        # shared word-boundary term matcher
│   ├── policy.py          # Policy — calibration as data
│   ├── recommender.py     # per-gap recommendations
│   ├── registry.py        # Rule protocol, register_rule, register_domain
│   ├── scorer.py          # scoring and status banding
│   ├── types.py           # AnalysisResult, RuleFinding
│   ├── py.typed
│   └── rules/             # the 31 built-in rules
│       ├── coding.py      # build, debug, optimization, explanation, feature
│       ├── writing.py     # compose
│       └── data_analysis.py  # analysis
├── eval/                  # versioned 121-case clarity-evaluation set
├── docs/                  # benchmark + framework recipes
├── tests/
└── pyproject.toml
```

---

## Development

```bash
pip install -e ".[dev]"
python -m pytest tests/
ruff check .
mypy            # strict — the shipped py.typed is checked
python -m pytest tests/ --cov=inputguard --cov-branch --cov-fail-under=90
python3 eval/measure_fp.py   # clarity-evaluation benchmark (see docs/)
```

CI runs the same gates on Python 3.9–3.13, plus a latency-benchmark job and a zero-dependency wheel check.

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
