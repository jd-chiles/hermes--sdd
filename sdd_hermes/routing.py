"""Routing and failure-policy primitives for durable SDD recovery.

Routes are configuration, not credentials.  The ledger stores only the route
identity and policy version so a recovery can prove what it attempted without
persisting provider secrets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .core import SDDError


TIERS = {"low", "med", "high"}
FAILURE_CLASSES = {
    "provider_transient",
    "provider_configuration",
    "capability_mismatch",
    "task_defect",
    "environment_or_permission",
    "unknown_or_ambiguous",
}


@dataclass(frozen=True)
class Route:
    provider: str
    model: str
    endpoint: str = ""
    policy_version: str = "1"

    @property
    def identity(self) -> str:
        return f"{self.provider}/{self.model}@{self.endpoint or 'default'}"

    def public(self) -> dict[str, str]:
        return {"provider": self.provider, "model": self.model, "endpoint": self.endpoint, "policy_version": self.policy_version}


def route_from(value: Mapping[str, Any], policy_version: str = "1") -> Route:
    provider = str(value.get("provider", "")).strip()
    model = str(value.get("model", "")).strip()
    if not provider or not model:
        raise SDDError("a route requires provider and model")
    return Route(provider, model, str(value.get("endpoint", "")).strip(), str(value.get("policy_version", policy_version)))


def resolve_routes(config: Mapping[str, Any] | None) -> dict[str, Any]:
    """Resolve configured routes without claiming host effectiveness."""
    if not config:
        return {"state": "unconfigured", "escalation_available": False, "reason": "no authorized tier routes configured"}
    policy_version = str(config.get("policy_version", "1"))
    raw = config.get("tiers", {})
    routes: dict[str, Route] = {}
    for tier in TIERS:
        if tier in raw:
            routes[tier] = route_from(raw[tier], policy_version)
    missing = sorted(TIERS - routes.keys())
    if missing:
        return {"state": "routing_unavailable", "escalation_available": False, "missing_tiers": missing, "policy_version": policy_version}
    identities = {route.identity for route in routes.values()}
    return {
        "state": "configured",
        "escalation_available": len(identities) > 1,
        "shared_route": len(identities) == 1,
        "policy_version": policy_version,
        "routes": {tier: route.public() for tier, route in routes.items()},
    }


def classify_failure(code: str, phase: str = "") -> dict[str, str]:
    normalized = code.strip().lower()
    aliases = {
        "429": "provider_transient", "500": "provider_transient", "502": "provider_transient",
        "503": "provider_transient", "timeout": "unknown_or_ambiguous", "auth": "provider_configuration",
        "quota": "provider_configuration", "model_not_found": "provider_configuration",
        "unsupported": "capability_mismatch", "permission": "environment_or_permission",
        "check_failed": "task_defect",
    }
    failure_class = aliases.get(normalized, normalized if normalized in FAILURE_CLASSES else "unknown_or_ambiguous")
    return {"class": failure_class, "phase": phase or "dispatch", "code": code}


def recovery_decision(failure_class: str, current_route: str, alternate_route: str | None = None) -> dict[str, Any]:
    if failure_class not in FAILURE_CLASSES:
        raise SDDError(f"unknown failure class: {failure_class}")
    if failure_class == "provider_transient" and alternate_route and alternate_route != current_route:
        return {"state": "repair_ready", "actionable_change": "distinct_effective_route", "route": alternate_route}
    if failure_class == "task_defect":
        return {"state": "repair_ready", "actionable_change": "changed_repair_plan"}
    if failure_class == "unknown_or_ambiguous":
        return {"state": "reconcile_required", "actionable_change": "native_state_reconciliation"}
    if failure_class == "provider_configuration":
        return {"state": "blocked_configuration", "actionable_change": "corrected_provider_configuration"}
    if failure_class == "capability_mismatch":
        return {"state": "blocked_capability", "actionable_change": "compatible_route_or_decomposition"}
    if failure_class == "environment_or_permission":
        return {"state": "blocked", "actionable_change": "resolved_environment_prerequisite"}
    return {"state": "waiting_provider", "actionable_change": "fresh_health_signal"}
