from __future__ import annotations

from typing import Any

import numpy as np

from .predictor import predict_collapse
from ..generator import _refine_graph, generate_universe
from ..internal.graph_builder import InteractionGraph
from ..internal.hierarchy import frozen_hierarchy
from ..internal.metrics import graph_metrics
from ..utils import deterministic_rng, safe_graph_copy


def _normalize_positions(positions: np.ndarray) -> np.ndarray:
    array = np.asarray(positions, dtype=float)
    mins = array.min(axis=0)
    spans = np.maximum(np.ptp(array, axis=0), 1.0e-12)
    return (array - mins) / spans


def _normalize_affinity(affinity: np.ndarray) -> np.ndarray:
    array = np.asarray(affinity, dtype=float)
    if float(array.max()) > 1.0 + 1.0e-9:
        array = array / max(float(array.max()), 1.0e-12)
    row_sum = array.sum(axis=1, keepdims=True)
    return array / (row_sum + 1.0e-12)


def _build_graph_from_edges(nodes, edges, seed: int = 42, positions=None):
    if not nodes:
        raise ValueError("nodes must not be empty")
    node_to_index = {node: index for index, node in enumerate(nodes)}
    rng = deterministic_rng(int(seed))
    coords = rng.uniform(0.0, 1.0, size=(len(nodes), 2)) if positions is None else _normalize_positions(np.asarray(positions, dtype=float))
    affinity = np.zeros((len(nodes), len(nodes)), dtype=float)
    for edge in edges:
        if len(edge) == 2:
            left, right = edge
            weight = 1.0
        elif len(edge) == 3:
            left, right, weight = edge
        else:
            raise ValueError("edges must contain [u, v] or [u, v, weight]")
        i = node_to_index[left]
        j = node_to_index[right]
        affinity[i, j] = float(weight)
        affinity[j, i] = float(weight)
    np.fill_diagonal(affinity, 0.0)
    if affinity.shape[0] < 4:
        raise ValueError("Graph too small for stability analysis")
    if not np.any(affinity > 0.0):
        raise ValueError("Graph has no connectivity")
    affinity = _normalize_affinity(affinity)
    delta = coords[:, None, :] - coords[None, :, :]
    distances = np.linalg.norm(delta, axis=-1)
    return {
        "positions": coords,
        "affinity": affinity,
        "distances": distances,
    }


def _build_trace_from_graph(graph_data: dict[str, np.ndarray], seed: int = 42, refinement_levels: int = 5, schedule_shift: float = 0.0):
    levels = frozen_hierarchy(len(graph_data["positions"]), refinement_levels, schedule_shift=schedule_shift)
    graph = InteractionGraph(
        positions=np.asarray(graph_data["positions"], dtype=float),
        affinity=np.asarray(graph_data["affinity"], dtype=float),
        distances=np.asarray(graph_data["distances"], dtype=float),
        kernel_width=float(levels[0]["kernel_width"]),
        locality_radius=float(levels[0]["locality_radius"]),
        seed=int(seed),
        level=0,
    )
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


def haos_stability_skill(input_payload: dict[str, Any]):
    threshold = float(input_payload.get("threshold", -0.1176))
    if "nodes" not in input_payload:
        trace, _ = generate_universe(
            seed=int(input_payload.get("seed", 42)),
            size=int(input_payload.get("size", 128)),
            refinement_levels=int(input_payload.get("refinement_levels", 5)),
            perturbation=bool(input_payload.get("perturbation", False)),
            perturbation_strength=float(input_payload.get("perturbation_strength", 0.03)),
            schedule_shift=float(input_payload.get("schedule_shift", 0.0)),
        )
    else:
        graph_data = _build_graph_from_edges(
            input_payload["nodes"],
            input_payload.get("edges", []),
            seed=int(input_payload.get("seed", 42)),
            positions=input_payload.get("positions"),
        )
        trace = _build_trace_from_graph(
            graph_data,
            seed=int(input_payload.get("seed", 42)),
            refinement_levels=int(input_payload.get("refinement_levels", 5)),
            schedule_shift=float(input_payload.get("schedule_shift", 0.0)),
        )
    result = predict_collapse(trace, threshold=threshold)
    if result["predicted_break"] is None or result["safety_margin"] is None:
        raise ValueError("Trace too short for stability prediction")
    return {
        "k_star": int(result["k_star"]),
        "predicted_break": int(result["predicted_break"]),
        "safety_margin": float(result["safety_margin"]),
        "min_delta": float(result["min_delta"]),
        "confidence": abs(float(result["min_delta"])),
    }


def analyze_many(payloads: list[dict[str, Any]]):
    return [{"index": index, "result": haos_stability_skill(payload)} for index, payload in enumerate(payloads)]


def monitor_sequence(payloads: list[dict[str, Any]]):
    return [haos_stability_skill(payload) for payload in payloads]
