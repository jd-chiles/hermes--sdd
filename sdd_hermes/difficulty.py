"""Explainable per-task difficulty; independent from workflow and model routing."""

from __future__ import annotations

from typing import Any, Mapping

from .core import SDDError

POLICY_VERSION = 1
DIMENSIONS = ('scope', 'uncertainty', 'coupling', 'consequence', 'verification')
LEVELS = {'low': 0, 'med': 1, 'high': 2}


def tier(value: str) -> str:
    value = 'med' if value == 'medium' else value
    if value not in LEVELS:
        raise SDDError(f'invalid difficulty tier: {value!r}')
    return value


def assess(dimensions: Mapping[str, str] | None = None, rationale: str = '', override: str | None = None) -> dict[str, Any]:
    dimensions = dict(dimensions or {})
    if set(dimensions) - set(DIMENSIONS):
        raise SDDError('unknown difficulty dimension')
    unknown = [name for name in DIMENSIONS if name not in dimensions]
    values = {name: tier(dimensions[name]) if name in dimensions else 'med' for name in DIMENSIONS}
    calculated = max(values.values(), key=LEVELS.get)
    if (dimensions or override is not None) and not rationale.strip():
        raise SDDError('difficulty assessment or override requires a rationale')
    selected = tier(override) if override is not None else calculated
    if LEVELS[selected] < LEVELS[calculated]:
        raise SDDError('override cannot hide higher-risk or unassessed dimensions; reassess the dimensions')
    return {'tier': selected, 'calculated_tier': calculated, 'dimensions': values,
            'unassessed': unknown, 'rationale': rationale.strip() or 'Repository dimensions unassessed; defaulting to med pending inspection.',
            'override': override, 'policy_version': POLICY_VERSION}
