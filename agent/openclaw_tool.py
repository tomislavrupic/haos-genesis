from __future__ import annotations

from haos_genesis.api import suggest_recovery
from haos_genesis.api.skill import haos_stability_skill


def tool_haos_stability(**kwargs):
    return haos_stability_skill(kwargs)


def tool_haos_recovery(**kwargs):
    return suggest_recovery(kwargs)
