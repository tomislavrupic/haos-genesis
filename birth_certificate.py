from __future__ import annotations
from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class BirthCertificate:
    stable_identity_count: int
    persistence_score: float
    connectivity_diameter: float
    transport_efficiency: float
    failure_events: int
    recovery_score: float
    @classmethod
    def from_trace(cls, trace: list[dict]) -> "BirthCertificate":
        masks = [np.asarray(entry["metrics"]["largest_component_mask"], dtype=bool) for entry in trace]
        core = masks[0].copy() if masks else np.zeros(0, dtype=bool)
        for mask in masks[1:]:
            core &= mask
        metrics = [entry["metrics"] for entry in trace]
        return cls(
            stable_identity_count=int(np.sum(core)),
            persistence_score=float(np.mean([float(item["persistence_score"]) for item in metrics])) if metrics else 0.0,
            connectivity_diameter=float(np.max([float(item["connectivity_diameter"]) for item in metrics])) if metrics else 0.0,
            transport_efficiency=float(np.mean([float(item["transport_efficiency"]) for item in metrics])) if metrics else 0.0,
            failure_events=int(sum(1 for item in metrics if str(item["label"]) == "unstable")),
            recovery_score=float(np.mean([float(item["recovery_score"]) for item in metrics])) if metrics else 0.0,
        )
    def to_dict(self) -> dict[str, float | int]:
        return {
            "stable_identity_count": self.stable_identity_count,
            "persistence_score": self.persistence_score,
            "connectivity_diameter": self.connectivity_diameter,
            "transport_efficiency": self.transport_efficiency,
            "failure_events": self.failure_events,
            "recovery_score": self.recovery_score,
        }
    def to_markdown(self) -> str:
        return "\n".join(["## Birth Certificate", "", f"- stable_identity_count: `{self.stable_identity_count}`", f"- persistence_score: `{self.persistence_score:.4f}`", f"- connectivity_diameter: `{self.connectivity_diameter:.2f}`", f"- transport_efficiency: `{self.transport_efficiency:.4f}`", f"- failure_events: `{self.failure_events}`", f"- recovery_score: `{self.recovery_score:.4f}`"])
