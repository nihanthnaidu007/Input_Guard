"""Built-in rule modules and the registry wiring for the coding and
writing domains.

Importing this package registers both first-party domains — their intent
signals and all built-in rules — through the exact same registry path a
user rule takes. The v0.2 ``run_*_rules`` functions stay exported for
backward compatibility, but the analyzer dispatches through the registry
now.
"""

from inputguard.detector import (
    DEBUG_SIGNALS,
    EXPLANATION_SIGNALS,
    FEATURE_SIGNALS,
    INTENT_SIGNALS,
    OPTIMIZATION_SIGNALS,
)
from inputguard.registry import REGISTRY
from inputguard.rules.coding import CODING_RULES, run_coding_rules
from inputguard.rules.debug import DEBUG_RULES, run_debug_rules
from inputguard.rules.explanation import EXPLANATION_RULES, run_explanation_rules
from inputguard.rules.feature import FEATURE_RULES, run_feature_rules
from inputguard.rules.optimization import (
    OPTIMIZATION_RULES,
    run_optimization_rules,
)
from inputguard.rules.writing import WRITING_RULES, WRITING_SIGNALS

__all__ = [
    "run_coding_rules",
    "run_debug_rules",
    "run_optimization_rules",
    "run_explanation_rules",
    "run_feature_rules",
]

# The coding domain: intent signals in strict priority order (the single
# empty-terms entry, "build", is the fallback) and all 19 built-in rules,
# registered through the same register_domain path a user domain takes.
REGISTRY.register_domain(
    "coding",
    INTENT_SIGNALS,
    rules=(
        *CODING_RULES,
        *DEBUG_RULES,
        *OPTIMIZATION_RULES,
        *EXPLANATION_RULES,
        *FEATURE_RULES,
    ),
)

# The writing domain: a single fallback intent ("compose" — globally unique;
# no coding intent name is reused, so no cross-domain rule leakage) and the
# six first-party writing rules, registered through the same path.
REGISTRY.register_domain(
    "writing",
    WRITING_SIGNALS,
    rules=WRITING_RULES,
)
