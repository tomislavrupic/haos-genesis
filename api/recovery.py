from __future__ import annotations

from typing import Any

import numpy as np

from .skill import _build_graph_from_edges, haos_stability_skill


def _parse_weighted_edges(nodes, edges) -> dict[tuple[int, int], float]:
    node_to_index = {node: index for index, node in enumerate(nodes)}
    weighted_edges: dict[tuple[int, int], float] = {}
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
        key = (i, j) if i < j else (j, i)
        weighted_edges[key] = float(weight)
    return weighted_edges


def _serialize_edges(nodes, weighted_edges: dict[tuple[int, int], float]):
    return [(nodes[i], nodes[j], float(weight)) for (i, j), weight in sorted(weighted_edges.items()) if weight > 0.0]


def _missing_pairs(distances: np.ndarray, existing_edges: dict[tuple[int, int], float], limit: int) -> list[tuple[int, int]]:
    pairs = []
    size = int(distances.shape[0])
    for left in range(size):
        for right in range(left + 1, size):
            key = (left, right)
            if key in existing_edges:
                continue
            pairs.append((float(distances[left, right]), key))
    pairs.sort(key=lambda item: (item[0], item[1]))
    return [key for _, key in pairs[: max(int(limit), 0)]]


def _candidate_score(result: dict[str, float | int], baseline: dict[str, float | int], cost: float) -> tuple[float, float, float, float, float]:
    return (
        float(int(result["k_star"]) - int(baseline["k_star"])),
        float(result["min_delta"]) - float(baseline["min_delta"]),
        float(result["safety_margin"]) - float(baseline["safety_margin"]),
        float(int(result["predicted_break"]) - int(baseline["predicted_break"])),
        -float(cost),
    )


def _is_improvement(score: tuple[float, float, float, float, float]) -> bool:
    return bool(score[0] > 0.0 or score[1] > 0.0 or score[2] > 0.0 or score[3] > 0.0)


def apply_intervention(input_payload: dict[str, Any], intervention: dict[str, Any] | None):
    if intervention is None:
        return dict(input_payload)
    if "nodes" not in input_payload or "edges" not in input_payload:
        raise ValueError("Applying a recovery intervention requires external graph input with nodes and edges")
    nodes = list(input_payload["nodes"])
    node_to_index = {node: index for index, node in enumerate(nodes)}
    weighted_edges = _parse_weighted_edges(nodes, input_payload["edges"])
    left, right = intervention["edge"]
    i = node_to_index[left]
    j = node_to_index[right]
    key = (i, j) if i < j else (j, i)
    weighted_edges[key] = float(intervention["weight_after"])
    candidate_payload = dict(input_payload)
    candidate_payload["nodes"] = list(nodes)
    candidate_payload["edges"] = _serialize_edges(nodes, weighted_edges)
    return candidate_payload


def suggest_recovery(input_payload: dict[str, Any]):
    if "nodes" not in input_payload or "edges" not in input_payload:
        raise ValueError("Recovery design currently requires external graph input with nodes and edges")

    nodes = list(input_payload["nodes"])
    weighted_edges = _parse_weighted_edges(nodes, input_payload["edges"])
    graph_data = _build_graph_from_edges(
        nodes,
        input_payload["edges"],
        seed=int(input_payload.get("seed", 42)),
        positions=input_payload.get("positions"),
    )
    baseline = haos_stability_skill(input_payload)
    positive_weights = np.asarray([weight for weight in weighted_edges.values() if weight > 0.0], dtype=float)
    base_scale = float(np.median(positive_weights)) if positive_weights.size else 1.0
    reinforce_delta = max(base_scale * float(input_payload.get("reinforce_scale", 0.25)), 1.0e-6)
    add_weight = max(base_scale * float(input_payload.get("add_scale", 0.5)), 1.0e-6)
    max_existing = int(input_payload.get("max_existing_candidates", 8))
    max_missing = int(input_payload.get("max_missing_candidates", 8))

    existing_candidates = sorted(weighted_edges.items(), key=lambda item: (item[1], item[0]))[: max(max_existing, 0)]
    missing_candidates = _missing_pairs(np.asarray(graph_data["distances"], dtype=float), weighted_edges, max_missing)
    best: dict[str, Any] | None = None
    best_score: tuple[float, float, float, float, float] | None = None

    def evaluate(kind: str, edge_key: tuple[int, int], weight_before: float, weight_after: float, cost: float) -> None:
        nonlocal best, best_score
        candidate_edges = dict(weighted_edges)
        candidate_edges[edge_key] = float(weight_after)
        candidate_payload = dict(input_payload)
        candidate_payload["nodes"] = list(nodes)
        candidate_payload["edges"] = _serialize_edges(nodes, candidate_edges)
        result = haos_stability_skill(candidate_payload)
        score = _candidate_score(result, baseline, cost)
        if not _is_improvement(score):
            return
        if best_score is None or score > best_score:
            left, right = edge_key
            best_score = score
            best = {
                "kind": kind,
                "edge": [nodes[left], nodes[right]],
                "cost": float(cost),
                "weight_before": float(weight_before),
                "weight_after": float(weight_after),
                "k_star_gain": int(result["k_star"]) - int(baseline["k_star"]),
                "min_delta_gain": float(result["min_delta"]) - float(baseline["min_delta"]),
                "safety_margin_gain": float(result["safety_margin"]) - float(baseline["safety_margin"]),
                "predicted_break_gain": int(result["predicted_break"]) - int(baseline["predicted_break"]),
                "result": result,
            }

    for edge_key, weight in existing_candidates:
        evaluate("reinforce_edge", edge_key, float(weight), float(weight + reinforce_delta), float(reinforce_delta))
    for edge_key in missing_candidates:
        evaluate("add_edge", edge_key, 0.0, float(add_weight), float(add_weight))

    return {
        "baseline": baseline,
        "best_intervention": best,
        "candidates_evaluated": int(len(existing_candidates) + len(missing_candidates)),
    }
