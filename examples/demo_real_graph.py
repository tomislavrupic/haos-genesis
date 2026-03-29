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

from haos_genesis.api import predict_collapse
from haos_genesis.generator import _refine_graph
from haos_genesis.internal.graph_builder import InteractionGraph
from haos_genesis.internal.hierarchy import frozen_hierarchy
from haos_genesis.internal.metrics import graph_metrics
from haos_genesis.utils import safe_graph_copy


def build_trace_from_affinity(positions: np.ndarray, affinity: np.ndarray, seed: int = 7, refinement_levels: int = 5, schedule_shift: float = 0.0):
    levels = frozen_hierarchy(len(positions), refinement_levels, schedule_shift=schedule_shift)
    delta = np.asarray(positions, dtype=float)[:, None, :] - np.asarray(positions, dtype=float)[None, :, :]
    distances = np.linalg.norm(delta, axis=-1)
    affinity = np.asarray(affinity, dtype=float)
    affinity = 0.5 * (affinity + affinity.T)
    affinity = affinity / max(float(np.max(affinity)), 1.0)
    np.fill_diagonal(affinity, 0.0)
    graph = InteractionGraph(np.asarray(positions, dtype=float), affinity, distances, float(levels[0]["kernel_width"]), float(levels[0]["locality_radius"]), int(seed), 0)
    reference = safe_graph_copy(graph)
    trace = []
    prev_graph = None
    prev_metrics = None
    for step in levels:
        if int(step["level"]) > 0:
            graph = _refine_graph(graph, float(step["kernel_width"]), float(step["locality_radius"]))
        metrics = graph_metrics(graph, reference)
        metrics["local_overlap"] = graph_metrics(graph, prev_graph)["overlap"] if prev_graph is not None else 1.0
        metrics["delta_persistence"] = float(metrics["persistence_score"] - prev_metrics["persistence_score"]) if prev_metrics is not None else 0.0
        trace.append({"level": int(step["level"]), "graph": safe_graph_copy(graph), "metrics": metrics})
        prev_graph = safe_graph_copy(graph)
        prev_metrics = dict(metrics)
    return trace


def plot_trace(trace, analysis, title: str, filename: str):
    levels = [int(entry["level"]) for entry in trace]
    scores = [float(entry["metrics"]["persistence_score"]) for entry in trace]
    output = ROOT / "haos_genesis" / "output" / filename
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    ax.plot(levels, scores, marker="o", color="#0f766e", label="persistence_score")
    critical_level = min(int(analysis["k_star"]) + 1, len(levels) - 1)
    ax.scatter([levels[critical_level]], [scores[critical_level]], color="#dc2626", zorder=3, label="k_star")
    if analysis["predicted_break"] is not None:
        ax.axvline(int(analysis["predicted_break"]), color="#f59e0b", linestyle="--", label="predicted_break")
    ax.set_xlabel("level")
    ax.set_ylabel("persistence_score")
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return output


def main():
    graph = nx.karate_club_graph()
    nodes = sorted(graph.nodes())
    layout = nx.spring_layout(graph, seed=7)
    positions = np.asarray([layout[node] for node in nodes], dtype=float)
    positions = (positions - positions.min(axis=0)) / np.maximum(np.ptp(positions, axis=0), 1.0e-12)
    adjacency = nx.to_numpy_array(graph, nodelist=nodes, dtype=float)
    distances = np.linalg.norm(positions[:, None, :] - positions[None, :, :], axis=-1)
    sigma0 = float(frozen_hierarchy(len(nodes), 5)[0]["kernel_width"])
    affinity = adjacency * np.exp(-(distances ** 2) / max(2.0 * sigma0 ** 2, 1.0e-12))
    trace = build_trace_from_affinity(positions, affinity, seed=7, refinement_levels=5)
    analysis = predict_collapse(trace)
    plot_trace(trace, analysis, "Karate Club Stability Trace", "demo_real_graph.png")
    print({key: analysis[key] for key in ("k_star", "predicted_break", "safety_margin")})


if __name__ == "__main__":
    main()
