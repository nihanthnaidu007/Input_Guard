from inputguard.analyzer import InputGuard
from inputguard.registry import REGISTRY, Rule, register_domain, register_rule
from inputguard.types import AnalysisResult, RuleFinding

__version__ = "0.2.0"

__all__ = [
    # v0.2 public API — unchanged compat contract.
    "InputGuard",
    "AnalysisResult",
    "RuleFinding",
    "__version__",
    # v0.3 extension API (additive): register custom rules and domains
    # through the same path the built-ins take.
    "REGISTRY",
    "Rule",
    "register_rule",
    "register_domain",
]
