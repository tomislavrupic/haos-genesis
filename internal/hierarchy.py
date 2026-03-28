from __future__ import annotations

import math


def frozen_hierarchy(size: int, refinement_levels: int, schedule_shift: float = 0.0) -> list[dict[str, float | int]]:
    n_side = max(2, int(round(math.sqrt(max(int(size), 4)))))
    h_value = 1.0 / float(n_side)
    levels: list[dict[str, float | int]] = []
    for level in range(max(int(refinement_levels), 0) + 1):
        multiplier = float(level + 1) + float(schedule_shift)
        if multiplier <= 0.0:
            raise ValueError("schedule_shift must keep all hierarchy multipliers positive.")
        kernel_width = multiplier * h_value
        levels.append(
            {
                "level": int(level),
                "multiplier": float(multiplier),
                "kernel_width": float(kernel_width),
                "locality_radius": float(min(3.0 * kernel_width, math.sqrt(2.0))),
            }
        )
    return levels
