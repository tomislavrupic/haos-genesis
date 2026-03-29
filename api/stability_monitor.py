from __future__ import annotations

from typing import Any, Mapping


TraceEntry = Mapping[str, Any]


def compute_k_star(trace: list[TraceEntry]) -> dict[str, int | float | list[float]]:
    """
    Compute the critical transition index k_star from a trace.

    k_star = argmin Δpersistence(k -> k+1)
    """
    if len(trace) < 2:
        return {
            "k_star": 0,
            "delta_persistence": [],
            "min_delta": 0.0,
        }

    persistence = [float(entry["metrics"]["persistence_score"]) for entry in trace]
    delta = [float(persistence[index + 1] - persistence[index]) for index in range(len(persistence) - 1)]
    assert len(delta) == len(trace) - 1
    k_star = int(min(range(len(delta)), key=lambda index: delta[index]))
    min_delta = float(delta[k_star])
    return {
        "k_star": k_star,
        "delta_persistence": delta,
        "min_delta": min_delta,
    }


class StabilityMonitor:
    def __init__(self, threshold: float = -0.1176):
        self.threshold = float(threshold)

    def analyze_trace(self, trace: list[TraceEntry]) -> dict[str, int | float | list[float] | None]:
        k_data = compute_k_star(trace)
        delta = list(k_data["delta_persistence"])
        k_star = int(k_data["k_star"])

        predicted_break = None
        safety_margin = None
        if len(delta) > 1:
            d12 = float(delta[1])
            predicted_break = 2 if d12 <= self.threshold else 3
            # safety_margin > 0 -> stable, ~=0 -> boundary, < 0 -> predicted collapse
            safety_margin = float(self.threshold - d12)

        return {
            "k_star": k_star,
            "delta_persistence": delta,
            "min_delta": float(k_data["min_delta"]),
            "predicted_break": predicted_break,
            "safety_margin": safety_margin,
        }
