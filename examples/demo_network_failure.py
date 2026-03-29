from __future__ import annotations

import numpy as np
import networkx as nx

from demo_real_graph import build_trace_from_affinity, plot_trace
from haos_genesis.api import predict_collapse


def main():
    graph = nx.watts_strogatz_graph(36, 4, 0.08, seed=19)
    layout = nx.spring_layout(graph, seed=19)
    positions = np.asarray([layout[node] for node in sorted(graph.nodes())], dtype=float)
    positions = (positions - positions.min(axis=0)) / np.maximum(np.ptp(positions, axis=0), 1.0e-12)
    adjacency = nx.to_numpy_array(graph, nodelist=sorted(graph.nodes()), dtype=float)
    distances = np.linalg.norm(positions[:, None, :] - positions[None, :, :], axis=-1)
    weights = np.exp(-(distances ** 2) / (2.0 * 0.18 ** 2))
    results = []
    selected_trace = None
    for quantile in (0.0, 0.4, 0.6, 0.65):
        degraded = adjacency.copy()
        if quantile > 0.0:
            cutoff = float(np.quantile(distances[adjacency > 0], 1.0 - quantile))
            degraded[(adjacency > 0) & (distances >= cutoff)] = 0.0
            degraded = np.maximum(degraded, degraded.T)
        trace = build_trace_from_affinity(positions, degraded * weights, seed=19, refinement_levels=5)
        analysis = predict_collapse(trace)
        selected_trace = trace
        results.append(
            {
                "removed_edge_quantile": quantile,
                "remaining_edges": int(np.sum(degraded) / 2.0),
                **{key: analysis[key] for key in ("k_star", "predicted_break", "safety_margin")},
            }
        )
    plot_trace(selected_trace, predict_collapse(selected_trace), "Network Failure Trace", "demo_network_failure.png")
    print(results)


if __name__ == "__main__":
    main()
