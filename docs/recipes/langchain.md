# Recipe: InputGuard as a LangChain pre-flight gate

InputGuard is framework-agnostic: it takes a string and returns a plain `to_dict()` payload, so wiring it into a LangChain chain is one `RunnableLambda` in front of your model call. There is no adapter package and no shared dependency — `inputguard` stays zero-dependency and imports nothing from `langchain-core`.

> **Prerequisites:** `pip install inputguard` (and your own LangChain setup — inputguard installs none of it). This recipe targets langchain-core's runnable protocol; the same shape works for LCEL chains, agents, and LangGraph nodes.

## 1 · The pre-flight payload (pure inputguard)

This step is framework-free — a plain function returning the `to_dict()` contract your chain branches on. It is executed by CI (`tests/test_recipes.py`), including its assertions:

```python
from inputguard import InputGuard

guard = InputGuard()  # warning mode: measure and flag, do not block

def preflight(question: str) -> dict:
    """Analyze input and return the to_dict() contract the chain routes on."""
    payload = guard.analyze(question).to_dict()

    if payload["status"] in ("needs_clarification", "blocked", "degraded"):
        return {
            "route": "clarify",
            "question": question,
            "gaps": payload["gaps"],
            "follow_ups": payload["follow_ups"],
        }
    return {"route": "model", "question": question}


routed = preflight("fix my code")
assert routed["route"] == "clarify"
assert routed["gaps"] == ["error description", "expected vs actual behavior", "code context"]
assert routed["follow_ups"][0].startswith("What is the exact error message")

specified = preflight(
    "Fix this Python function get_users() — it should return a list "
    "of user dicts but instead returns None. "
    "The error says: TypeError: NoneType is not iterable on line 45."
)
assert specified["route"] == "model"
```

`degraded` rides the clarify route too: it is InputGuard reporting its own language limitation, not a judgment of the input — but the safest behavior is still to ask the user rather than run English-only analysis downstream.

## 2 · Slot it into a chain

The clarify path never touches the model — in the demo below, `call_your_model` is a `RuntimeError` to prove it:

```python
from langchain_core.runnables import RunnableLambda

def clarify_message(payload: dict) -> dict:
    return {
        **payload,
        "message": "Before I can help, could you answer: " + " ".join(payload["follow_ups"]),
    }

def call_your_model(question: str) -> str:
    # Replace with your real model invocation, e.g. ChatOpenAI(...).invoke(...)
    raise RuntimeError("the clarify path must never reach the model")

chain = RunnableLambda(preflight) | RunnableLambda(
    lambda payload: clarify_message(payload)
    if payload["route"] == "clarify"
    else call_your_model(payload["question"])
)

result = chain.invoke("fix my code")
assert result["route"] == "clarify"
assert result["message"].startswith("Before I can help")
```

## Notes

- **Warning vs strict:** in warning mode only `needs_clarification` and `degraded` arrive at the clarify branch. In strict mode `blocked` joins them — same route, more refusal. Pick via `InputGuard(mode=...)`; the payload contract does not change.
- **Where the score lives:** `payload["clarity_score"]` and `payload["score_breakdown"]` are on every result if you want to log the arithmetic or threshold on your side.
- **Follow-ups are ready to send:** `follow_ups` are plain sentences, deduped and gap-ordered — drop them into your clarification message verbatim.
- **Streaming/agents:** call `preflight()` before entering the agent loop; the payload is a plain dict, safe to attach to any run state.

---

🔗 [Obvious Project](https://app.obvious.ai/p/inputguard-package-upgrade-plan-ZWAga4Fk) · 🧵 [Obvious Thread](https://app.obvious.ai/p/inputguard-package-upgrade-plan-ZWAga4Fk?thread=th_2ZBoxRug)
