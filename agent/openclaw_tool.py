from __future__ import annotations

from haos_genesis.api.skill import haos_stability_skill


def tool_haos_stability(**kwargs):
    return haos_stability_skill(kwargs)
