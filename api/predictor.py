from __future__ import annotations

from .stability_monitor import StabilityMonitor


def predict_collapse(trace, threshold: float = -0.1176):
    return StabilityMonitor(threshold).analyze_trace(trace)
