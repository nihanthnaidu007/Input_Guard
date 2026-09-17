"""Typed Rule protocol and the in-process registries that open the engine.

v0.3 turns InputGuard's closed, coding-only checker into a pluggable clarity
engine: rules and domains are registered data, not code paths.

- A rule is any object with the four members (``id``, ``domain``,
  ``severity``, ``gap``) and a ``check(text)`` method — the
  :class:`Rule` protocol.
- A domain is a named analysis scope (``"coding"`` ships built in) that
  declares its intent signals in priority order via
  :meth:`RuleRegistry.register_domain`.

Registration happens at import/startup time; ``analyze()`` only reads the
registry, preserving the thread-safe, dependency-free pipeline v0.2
established.
"""

from __future__ import annotations

from typing import (
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Protocol,
    Set,
    Tuple,
    Union,
    runtime_checkable,
)

from inputguard.types import RuleFinding

__all__ = [
    "KNOWN_SEVERITIES",
    "REGISTRY",
    "Rule",
    "RuleRegistry",
    "register_domain",
    "register_rule",
]

KNOWN_SEVERITIES: Tuple[str, ...] = ("low", "medium", "high")

# Normalized domain signals: priority-ordered (intent, terms) pairs. The one
# intent with empty terms is the fallback for inputs no other intent matches.
SignalSpec = Tuple[Tuple[str, Tuple[str, ...]], ...]

_REQUIRED_MEMBERS = ("id", "domain", "severity", "gap", "check")


@runtime_checkable
class Rule(Protocol):
    """The v0.3 extension contract: four members and one method.

    ``id`` must be unique across the registry, ``severity`` must be one of
    ``'low' | 'medium' | 'high'`` (validated at registration), and ``gap``
    groups the rule's findings for scoring dedup (``None`` dedupes by code
    instead). ``check`` receives lowercased, whitespace-collapsed text, and
    returns at most one
    :class:`~inputguard.types.RuleFinding` — ``None`` when the rule does not
    fire.
    """

    id: str
    domain: str
    severity: str
    gap: Optional[str]

    def check(self, text: str) -> Optional[RuleFinding]:
        ...  # pragma: no cover — protocol body


def _instantiate(rule_cls: type) -> Rule:
    try:
        return rule_cls()
    except TypeError as exc:
        raise TypeError(
            f"Cannot register rule class {rule_cls.__name__!r}: it must be "
            f"constructible with no arguments. Register an instance instead: "
            f"register_rule({rule_cls.__name__}())."
        ) from exc


def _normalize_signals(
    name: str,
    signals: Union[Mapping[str, Iterable[str]], Iterable[Tuple[str, Iterable[str]]]],
) -> SignalSpec:
    items = tuple(signals.items() if isinstance(signals, Mapping) else signals)
    if not items:
        raise ValueError(f"Domain {name!r}: signals must declare at least one intent.")

    normalized: List[Tuple[str, Tuple[str, ...]]] = []
    fallbacks = 0
    for intent, terms in items:
        if not isinstance(intent, str) or not intent:
            raise ValueError(
                f"Domain {name!r}: intent names must be non-empty strings, got {intent!r}."
            )
        if isinstance(terms, str) or not isinstance(terms, Iterable):
            raise TypeError(
                f"Domain {name!r}: terms for intent {intent!r} must be an iterable "
                f"of strings, got {terms!r}."
            )
        term_tuple = tuple(terms)
        for term in term_tuple:
            if not isinstance(term, str) or not term:
                raise ValueError(
                    f"Domain {name!r}: terms for intent {intent!r} must be "
                    f"non-empty strings, got {term!r}."
                )
        if not term_tuple:
            fallbacks += 1
        normalized.append((intent, term_tuple))

    if fallbacks != 1:
        raise ValueError(
            f"Domain {name!r}: exactly one intent must have empty signal terms "
            f"(the fallback intent); found {fallbacks}."
        )
    return tuple(normalized)


class RuleRegistry:
    """In-process registry of rules and analysis domains.

    Writes happen at import/startup; ``analyze()`` reads are plain dict
    lookups and iteration over registered rules, so parallel ``analyze()``
    calls stay consistent (the v0.2 thread-safety contract). Registering
    while another thread is mid-``analyze()`` is not supported.
    """

    def __init__(self) -> None:
        self._rules: Dict[str, Rule] = {}
        self._domains: Dict[str, SignalSpec] = {}

    # -- registration ----------------------------------------------------

    def register_rule(self, rule: Union[type, Rule]) -> Union[type, Rule]:
        """Register a rule — decorator or imperative form.

        ``@register_rule`` above a rule class registers a zero-argument
        instance and returns the class unchanged; ``register_rule(instance)``
        registers the instance and returns it.

        Raises ``ValueError`` on a duplicate rule id, an unknown severity, or
        — once any domain is registered — a domain no registered domain
        declares as an intent. Raises ``TypeError`` when the object is not
        shaped like a :class:`Rule` or the class cannot be constructed with
        no arguments.
        """
        if isinstance(rule, type):
            instance = _instantiate(rule)
            self._validate(instance)
            self._add(instance)
            return rule
        self._validate(rule)
        self._add(rule)
        return rule

    def register_domain(
        self,
        name: str,
        signals: Union[Mapping[str, Iterable[str]], Iterable[Tuple[str, Iterable[str]]]],
        rules: Iterable[Union[type, Rule]] = (),
    ) -> None:
        """Register an analysis domain: intent signals plus its rules.

        ``signals`` maps intent names to trigger terms; insertion order is the
        priority chain, and the single intent with empty terms is the fallback
        for inputs no other intent matches. Every rule passed in must declare
        one of those intents as its ``domain``; rules already registered (for
        example via the ``@register_rule`` decorator) are reused, and the rest
        are registered through the same path.

        Raises ``ValueError`` on a duplicate domain name, malformed signals
        (no fallback intent), or a rule whose domain the domain does not
        declare.
        """
        if not isinstance(name, str) or not name:
            raise ValueError(f"Domain name must be a non-empty string, got {name!r}.")
        if name in self._domains:
            raise ValueError(
                f"Duplicate domain: {name!r}. Domains must be registered once."
            )
        normalized_signals = _normalize_signals(name, signals)
        declared = {intent for intent, _ in normalized_signals}

        coerced = [self._coerce(entry) for entry in rules]
        for rule in coerced:
            self._validate(rule)
        for rule in coerced:
            if rule.domain not in declared:
                raise ValueError(
                    f"Rule {rule.id!r} declares domain {rule.domain!r}, which is not "
                    f"an intent of domain {name!r}. Declared intents: {sorted(declared)}."
                )
        for rule in coerced:
            existing = self._rules.get(rule.id)
            if existing is not None and existing is not rule:
                raise ValueError(
                    f"Duplicate rule id: {rule.id!r}. Rule ids must be unique."
                )

        # All checks passed — mutate. The domain is stored before its rules so
        # the known-domain check in _add sees the intents it declares.
        self._domains[name] = normalized_signals
        for rule in coerced:
            if rule.id not in self._rules:
                self._add(rule)

    # -- reads (thread-safe: no mutation happens during analyze) ----------

    def get_domain_signals(self, name: str) -> SignalSpec:
        """Return the domain's priority-ordered ``(intent, terms)`` pairs.

        Raises ``ValueError`` for an unregistered domain — the registry-owned
        replacement for v0.2's hardcoded domain whitelist.
        """
        try:
            return self._domains[name]
        except KeyError:
            registered = ", ".join(repr(d) for d in self._domains) or "none"
            raise ValueError(
                f"Unsupported domain: {name!r}. Registered domains: {registered}."
            ) from None

    def domain_names(self) -> Tuple[str, ...]:
        """Registered domain names, in registration order."""
        return tuple(self._domains)

    def rules_for_intent(self, intent: str) -> List[Rule]:
        """Rules whose domain is this intent scope, in registration order."""
        return [rule for rule in self._rules.values() if rule.domain == intent]

    def rule_ids(self) -> Tuple[str, ...]:
        """Registered rule ids, in registration order."""
        return tuple(self._rules)

    def rules(self) -> Tuple[Rule, ...]:
        """All registered rules, in registration order."""
        return tuple(self._rules.values())

    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """Return the rule registered under ``rule_id``, or ``None``."""
        return self._rules.get(rule_id)

    # -- internals ---------------------------------------------------------

    def _coerce(self, entry: Union[type, Rule]) -> Rule:
        """Accept a rule class or instance.

        A class already registered (via the decorator, which instantiates)
        resolves to its registered instance; a fresh class is instantiated.
        """
        if not isinstance(entry, type):
            return entry
        probe_id = getattr(entry, "id", None)
        existing = self._rules.get(probe_id) if isinstance(probe_id, str) else None
        return existing if existing is not None else _instantiate(entry)

    def _validate(self, rule: Rule) -> None:
        missing = [m for m in _REQUIRED_MEMBERS if not hasattr(rule, m)]
        if missing:
            raise TypeError(
                f"Rule {rule!r} is missing required member(s): "
                f"{', '.join(repr(m) for m in missing)}. A rule needs id, domain, "
                "severity, gap, and a check(text) method."
            )
        if not isinstance(rule.id, str) or not rule.id:
            raise ValueError(f"Rule id must be a non-empty string, got {rule.id!r}.")
        if not isinstance(rule.domain, str) or not rule.domain:
            raise ValueError(
                f"Rule {rule.id!r}: domain must be a non-empty string, got {rule.domain!r}."
            )
        if rule.severity not in KNOWN_SEVERITIES:
            raise ValueError(
                f"Rule {rule.id!r}: unknown severity {rule.severity!r}. "
                f"Expected one of: 'low', 'medium', 'high'."
            )
        if rule.gap is not None and (not isinstance(rule.gap, str) or not rule.gap):
            raise ValueError(
                f"Rule {rule.id!r}: gap must be None or a non-empty string, got {rule.gap!r}."
            )
        if not callable(rule.check):
            raise TypeError(
                f"Rule {rule.id!r}: check must be callable — "
                "check(text) -> Optional[RuleFinding]."
            )

    def _add(self, rule: Rule) -> None:
        if rule.id in self._rules:
            raise ValueError(f"Duplicate rule id: {rule.id!r}. Rule ids must be unique.")
        # Known-domain check: vacuous until the first domain registers (built-in
        # rules register during package import, before any domain exists), then
        # enforced for everything registered afterwards.
        if self._domains and rule.domain not in self._declared_intents():
            raise ValueError(
                f"Rule {rule.id!r} declares domain {rule.domain!r}, which no "
                f"registered domain declares as an intent. Registered domains: "
                f"{', '.join(repr(d) for d in self._domains)}."
            )
        self._rules[rule.id] = rule

    def _declared_intents(self) -> Set[str]:
        declared: Set[str] = set()
        for signal_spec in self._domains.values():
            declared.update(intent for intent, _ in signal_spec)
    
        return declared


REGISTRY = RuleRegistry()


def register_rule(rule: Union[type, Rule]) -> Union[type, Rule]:
    """Module-level form of :meth:`RuleRegistry.register_rule` — usable as a decorator."""
    return REGISTRY.register_rule(rule)


def register_domain(
    name: str,
    signals: Union[Mapping[str, Iterable[str]], Iterable[Tuple[str, Iterable[str]]]],
    rules: Iterable[Union[type, Rule]] = (),
) -> None:
    """Module-level form of :meth:`RuleRegistry.register_domain`."""
    REGISTRY.register_domain(name, signals, rules)
