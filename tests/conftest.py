"""Shared test fixtures.

The registry-isolation fixture lives here so every module that mutates the
module-level ``REGISTRY`` (the contract-guard suite, the policy suite) uses
one canonical snapshot/restore implementation instead of reaching into
private registry state ad hoc.
"""

from __future__ import annotations

import pytest

from inputguard.registry import REGISTRY


@pytest.fixture
def registry_isolation():
    """Snapshot the registry around tests that mutate it.

    Registration is permanent by design (there is no unregister), so tests
    that register probe rules/domains restore the snapshot afterwards to keep
    the process-global registry unpolluted for the rest of the suite.
    """
    rules_before = dict(REGISTRY._rules)
    domains_before = dict(REGISTRY._domains)
    origins_before = dict(REGISTRY._origins)
    yield REGISTRY
    REGISTRY._rules.clear()
    REGISTRY._rules.update(rules_before)
    REGISTRY._domains.clear()
    REGISTRY._domains.update(domains_before)
    REGISTRY._origins.clear()
    REGISTRY._origins.update(origins_before)
