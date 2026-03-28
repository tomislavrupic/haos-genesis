from __future__ import annotations

import numpy as np

from .graph_builder import EPSILON, InteractionGraph


def perturb_graph(graph: InteractionGraph, strength: float, seed: int) -> InteractionGraph:
    rng = np.random.default_rng(int(seed))
    affinity = np.asarray(graph.affinity, dtype=float).copy()
    edges = np.transpose(np.nonzero(np.triu(affinity > 0.0, k=1)))
    for u, v in edges.tolist():
        weight = float(affinity[u, v])
        jitter = rng.normal(loc=0.0, scale=float(strength) * max(weight, EPSILON))
        affinity[u, v] = affinity[v, u] = float(np.clip(weight + jitter, EPSILON, 1.0))
    rewire_prob = min(0.02, max(0.0, float(strength) * 0.15))
    for u, v in edges.tolist():
        if affinity[u, v] <= 0.0 or rng.random() >= rewire_prob:
            continue
        weight = float(affinity[u, v])
        source = int(u if rng.random() < 0.5 else v)
        candidates = np.flatnonzero((np.arange(graph.n_nodes) != source) & (affinity[source] <= 0.0))
        if candidates.size == 0:
            continue
        affinity[u, v] = affinity[v, u] = 0.0
        target = int(rng.choice(candidates))
        affinity[source, target] = affinity[target, source] = weight
    removable = np.flatnonzero(np.sum(affinity > 0.0, axis=1) > 0)
    cap = int(np.floor(0.009 * graph.n_nodes))
    if cap > 0 and removable.size > 0:
        picked = removable[rng.random(removable.size) < min(0.009, max(0.0, float(strength) * 0.1))]
        for node in picked[:cap].tolist():
            affinity[node, :] = 0.0
            affinity[:, node] = 0.0
    np.fill_diagonal(affinity, 0.0)
    return InteractionGraph(
        positions=np.asarray(graph.positions, dtype=float).copy(),
        affinity=affinity,
        distances=np.asarray(graph.distances, dtype=float).copy(),
        kernel_width=float(graph.kernel_width),
        locality_radius=float(graph.locality_radius),
        seed=int(graph.seed),
        level=int(graph.level),
    )
