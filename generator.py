from __future__ import annotations

import numpy as np

from .internal.graph_builder import InteractionGraph, build_graph, build_transport_operator
from .internal.hierarchy import frozen_hierarchy
from .internal.metrics import graph_metrics
from .internal.stability import perturb_graph
from .utils import resolve_seed, safe_graph_copy


def _inject_perturbation(graph, strength):
    return perturb_graph(graph, float(strength), seed=int(graph.seed + 104729 * (graph.level + 1)))


def _refine_graph(prev_graph: InteractionGraph, kernel_width: float, locality_radius: float) -> InteractionGraph:
    target = build_graph(
        size=prev_graph.n_nodes,
        kernel_width=float(kernel_width),
        locality_radius=float(locality_radius),
        seed=prev_graph.seed,
        level=prev_graph.level + 1,
        positions=prev_graph.positions,
    )
    transition = build_transport_operator(prev_graph, self_weight=0.05)
    affinity = transition @ np.asarray(prev_graph.affinity, dtype=float) @ transition.T
    affinity = np.minimum(affinity, np.asarray(target.affinity, dtype=float))
    affinity = np.clip(affinity, 0.0, 1.0)
    np.fill_diagonal(affinity, 0.0)
    return InteractionGraph(target.positions, affinity, target.distances, target.kernel_width, target.locality_radius, target.seed, target.level)


def generate_universe(
    seed: int | None = None,
    size: int = 128,
    refinement_levels: int = 5,
    perturbation: bool = False,
    perturbation_strength: float = 0.03,
    schedule_shift: float = 0.0,
) -> tuple[list[dict], int]:
    used_seed = resolve_seed(seed)
    trace: list[dict] = []
    reference = None
    prev_graph = None
    prev_metrics = None
    graph = None
    for step in frozen_hierarchy(size, refinement_levels, schedule_shift=schedule_shift):
        graph = build_graph(
            size=int(size),
            kernel_width=float(step["kernel_width"]),
            locality_radius=float(step["locality_radius"]),
            seed=used_seed,
            level=int(step["level"]),
        ) if graph is None else _refine_graph(graph, float(step["kernel_width"]), float(step["locality_radius"]))
        if perturbation:
            graph = _inject_perturbation(graph, perturbation_strength)
        reference = safe_graph_copy(graph) if reference is None else reference
        metrics = graph_metrics(graph, reference)
        metrics["local_overlap"] = graph_metrics(graph, prev_graph)["overlap"] if prev_graph is not None else 1.0
        metrics["delta_persistence"] = float(metrics["persistence_score"] - prev_metrics["persistence_score"]) if prev_metrics is not None else 0.0
        trace.append({"level": int(step["level"]), "graph": safe_graph_copy(graph), "metrics": metrics})
        prev_graph = safe_graph_copy(graph)
        prev_metrics = dict(metrics)
    return trace, used_seed
