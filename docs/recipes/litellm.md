# Recipe: InputGuard as a LiteLLM gate

LiteLLM routes one OpenAI-shaped call to a hundred providers. InputGuard sits in front of that call: analyze the prompt first, and only forward to `litellm.completion(...)` when the payload says the input is worth the tokens. There is no adapter package and no shared dependency — `inputguard` stays zero-dependency and imports nothing from `litellm`.

> **Prerequisites:** `pip install inputguard` (and your own LiteLLM setup — inputguard installs none of it).

## 1 · The gate decision (pure inputguard)

This step is framework-free — a strict-mode guard turns vague input into a refusal without a model call. It is executed by CI (`tests/test_recipes.py`), including its assertions:

```python
from inputguard import InputGuard

guard = InputGuard(mode="strict")  # hard gate: refuse to forward vague input

def guard_prompt(question: str) -> dict:
    """Return {"ok": False, ...} to refuse, or {"ok": True, "prompt": ...} to forward."""
    payload = guard.analyze(question).to_dict()

    if payload["status"] != "ready":
        return {
            "ok": False,
            "status": payload["status"],
            "gaps": payload["gaps"],
            "follow_ups": payload["follow_ups"],
        }
    return {"ok": True, "prompt": question}


blocked = guard_prompt("make this faster")
assert blocked["ok"] is False
assert blocked["status"] == "blocked"
assert blocked["gaps"] == [
    "optimization target",
    "performance baseline",
    "optimization constraint",
]
assert blocked["follow_ups"][0] == "Which function or module should get faster?"

specified = guard_prompt(
    "Fix this Python function get_users() — it should return a list "
    "of user dicts but instead returns None. "
    "The error says: TypeError: NoneType is not iterable on line 45."
)
assert specified["ok"] is True
```

A `degraded` payload also fails the gate (`"ready"` is required): non-English input gets an honest note back instead of a silent pass.

## 2 · Wire it in front of the completion call

The clarify path returns before `litellm.completion` is ever reached — in the CI run the stub raises if it is:

```python
import litellm

def answer(question: str) -> str:
    decision = guard_prompt(question)

    if not decision["ok"]:
        return (
            "I need more detail before I can help.\n"
            "Missing: " + ", ".join(decision["gaps"]) + "\n"
            "Could you answer: " + " ".join(decision["follow_ups"])
        )

    response = litellm.completion(
        model="gpt-4o-mini",  # LiteLLM routes to 100+ providers behind this one call
        messages=[{"role": "user", "content": decision["prompt"]}],
    )
    return response.choices[0].message.content


reply = answer("make this faster")
assert reply.startswith("I need more detail")
```

## Notes

- **Proxy deployments:** run the same check at the proxy edge — `guard_prompt` is a pure function, so a LiteLLM pre-call hook or a tiny FastAPI route in front of the proxy can reuse it verbatim.
- **Audit trail:** `payload["score_breakdown"]` gives you the per-gap arithmetic for logs; `payload["detected_intent"]` and `payload["detected_language"]` are useful routing metadata.
- **Softer rollout:** start with `InputGuard()` in warning mode and log `"ok": False` cases without refusing; flip to `mode="strict"` once you trust the measured false-positive rate (see [docs/false-positive-benchmark.md](../false-positive-benchmark.md)).
- **Cost math:** every refused call is a completion you never paid for; the gate costs one local, dependency-free `analyze()` pass.

---

🔗 [Obvious Project](https://app.obvious.ai/p/inputguard-package-upgrade-plan-ZWAga4Fk) · 🧵 [Obvious Thread](https://app.obvious.ai/p/inputguard-package-upgrade-plan-ZWAga4Fk?thread=th_2ZBoxRug)
