from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "haos_genesis" / "output" / ".mpl"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np

from haos_genesis.api import apply_intervention, suggest_recovery
from haos_genesis.api.skill import _build_graph_from_edges, _build_trace_from_graph, haos_stability_skill


def _payload_to_trace(payload):
    graph_data = _build_graph_from_edges(
        payload["nodes"],
        payload["edges"],
        seed=int(payload.get("seed", 42)),
        positions=payload.get("positions"),
    )
    return _build_trace_from_graph(
        graph_data,
        seed=int(payload.get("seed", 42)),
        refinement_levels=int(payload.get("refinement_levels", 5)),
        schedule_shift=float(payload.get("schedule_shift", 0.0)),
    )


def _plot_recovery(baseline_trace, repaired_trace, baseline_result, repaired_result, filename: str):
    output = ROOT / "haos_genesis" / "output" / filename
    output.parent.mkdir(parents=True, exist_ok=True)
    levels = [int(entry["level"]) for entry in baseline_trace]
    baseline_scores = [float(entry["metrics"]["persistence_score"]) for entry in baseline_trace]
    repaired_scores = [float(entry["metrics"]["persistence_score"]) for entry in repaired_trace]
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    ax.plot(levels, baseline_scores, marker="o", color="#dc2626", label="baseline")
    ax.plot(levels, repaired_scores, marker="o", color="#0f766e", label="repaired")
    ax.axvline(int(baseline_result["k_star"]) + 1, color="#dc2626", linestyle="--", alpha=0.5, label="baseline k_star")
    ax.axvline(int(repaired_result["k_star"]) + 1, color="#0f766e", linestyle="--", alpha=0.5, label="repaired k_star")
    ax.set_xlabel("level")
    ax.set_ylabel("persistence_score")
    ax.set_title("Recovery Design: Minimal Stabilizing Intervention")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return output


def main():
    graph = nx.watts_strogatz_graph(36, 4, 0.08, seed=19)
    layout = nx.spring_layout(graph, seed=19)
    positions = np.asarray([layout[node] for node in sorted(graph.nodes())], dtype=float)
    positions = (positions - positions.min(axis=0)) / np.maximum(np.ptp(positions, axis=0), 1.0e-12)
    adjacency = nx.to_numpy_array(graph, nodelist=sorted(graph.nodes()), dtype=float)
    distances = np.linalg.norm(positions[:, None, :] - positions[None, :, :], axis=-1)
    weights = np.exp(-(distances ** 2) / (2.0 * 0.18 ** 2))
    degraded = adjacency.copy()
    cutoff = float(np.quantile(distances[adjacency > 0], 1.0 - 0.65))
    degraded[(adjacency > 0) & (distances >= cutoff)] = 0.0
    degraded = np.maximum(degraded, degraded.T)
    affinity = degraded * weights
    edges = [
        (int(left), int(right), float(affinity[left, right]))
        for left in range(affinity.shape[0])
        for right in range(left + 1, affinity.shape[1])
        if affinity[left, right] > 0.0
    ]
    payload = {
        "nodes": list(range(affinity.shape[0])),
        "edges": edges,
        "positions": positions.tolist(),
        "seed": 19,
        "refinement_levels": 5,
    }
    suggestion = suggest_recovery(payload)
    intervention = suggestion["best_intervention"]
    if intervention is None:
        print(suggestion)
        return
    repaired_payload = apply_intervention(payload, intervention)
    baseline_trace = _payload_to_trace(payload)
    repaired_trace = _payload_to_trace(repaired_payload)
    baseline_result = haos_stability_skill(payload)
    repaired_result = haos_stability_skill(repaired_payload)
    _plot_recovery(baseline_trace, repaired_trace, baseline_result, repaired_result, "demo_recovery_design.png")
    print(suggestion)


if __name__ == "__main__":
    main()
