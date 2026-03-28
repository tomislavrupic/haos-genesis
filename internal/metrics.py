from __future__ import annotations
from collections import deque
from dataclasses import dataclass
import numpy as np
from .graph_builder import EPSILON, InteractionGraph, build_transport_operator

def _probabilities(state: np.ndarray) -> np.ndarray:
    values = np.abs(np.asarray(state, dtype=complex)) ** 2
    total = max(float(np.sum(values)), EPSILON)
    return np.asarray(values / total, dtype=float)

def _safe_relative_change(new_value: float, old_value: float) -> float:
    return abs(float(new_value) - float(old_value)) / max(abs(float(old_value)), EPSILON)

def overlap(reference: np.ndarray, state: np.ndarray) -> float:
    denom = max(float(np.linalg.norm(reference) * np.linalg.norm(state)), EPSILON)
    return float(abs(np.vdot(reference, state)) / denom)

def localization_width(state: np.ndarray, coords: np.ndarray) -> float:
    probabilities = _probabilities(state)
    center = np.asarray(coords, dtype=float)[int(np.argmax(probabilities))]
    delta = np.asarray(coords, dtype=float) - center
    return float(np.sqrt(np.sum(probabilities * np.sum(delta * delta, axis=1))))

def concentration_retention(state: np.ndarray, mask: np.ndarray) -> float:
    return float(np.sum(_probabilities(state)[np.asarray(mask, dtype=bool)]))

def participation_ratio(state: np.ndarray) -> float:
    probabilities = _probabilities(state)
    return float(1.0 / max(float(np.sum(probabilities * probabilities)), EPSILON))

def recovery_score(reference: np.ndarray, state: np.ndarray, coords: np.ndarray, mask: np.ndarray) -> float:
    penalties = [
        min(_safe_relative_change(localization_width(state, coords), localization_width(reference, coords)) / 0.08, 1.0),
        min((1.0 - concentration_retention(state, mask)) / 0.12, 1.0),
        min(_safe_relative_change(participation_ratio(state), participation_ratio(reference)) / 0.20, 1.0),
        min((1.0 - overlap(reference, state)) / 0.08, 1.0),
    ]
    return float(max(0.0, 1.0 - float(np.mean(penalties))))

@dataclass(frozen=True)
class SurvivalThresholds:
    max_width_growth: float
    min_concentration: float
    max_participation_growth: float
    min_overlap: float
    min_recovery_score: float

DEFAULT_THRESHOLDS = SurvivalThresholds(0.10, 0.88, 0.20, 0.90, 0.90)

def classify_single_mode(reference: np.ndarray, state: np.ndarray, coords: np.ndarray, mask: np.ndarray, thresholds: SurvivalThresholds = DEFAULT_THRESHOLDS) -> str:
    ref_width = localization_width(reference, coords)
    state_width = localization_width(state, coords)
    width_growth = 0.0 if ref_width <= EPSILON else max((state_width / ref_width) - 1.0, 0.0)
    ref_participation = participation_ratio(reference)
    state_participation = participation_ratio(state)
    participation_growth = 0.0 if ref_participation <= EPSILON else max((state_participation / ref_participation) - 1.0, 0.0)
    concentration = concentration_retention(state, mask)
    overlap_value = overlap(reference, state)
    score = recovery_score(reference, state, coords, mask)
    if width_growth <= thresholds.max_width_growth and concentration >= thresholds.min_concentration and participation_growth <= thresholds.max_participation_growth and overlap_value >= thresholds.min_overlap and score >= thresholds.min_recovery_score:
        return "persistent"
    if concentration >= 0.5 * thresholds.min_concentration and overlap_value >= 0.5 * thresholds.min_overlap and score >= 0.5 * thresholds.min_recovery_score:
        return "diffusive"
    return "unstable"

def connected_components(adjacency: np.ndarray) -> list[list[int]]:
    seen = np.zeros(adjacency.shape[0], dtype=bool)
    components: list[list[int]] = []
    for start in range(adjacency.shape[0]):
        if seen[start]:
            continue
        stack = [start]
        seen[start] = True
        component: list[int] = []
        while stack:
            node = stack.pop()
            component.append(int(node))
            for neighbor in np.flatnonzero(adjacency[node]).tolist():
                if not seen[neighbor]:
                    seen[neighbor] = True
                    stack.append(int(neighbor))
        components.append(sorted(component))
    return components

def mean_local_clustering_coefficient(adjacency: np.ndarray) -> float:
    scores: list[float] = []
    for node in range(adjacency.shape[0]):
        neighbors = np.flatnonzero(adjacency[node])
        degree = int(neighbors.size)
        if degree < 2:
            scores.append(0.0)
            continue
        induced = adjacency[np.ix_(neighbors, neighbors)]
        scores.append(float(np.sum(induced) / 2.0) / max(degree * (degree - 1) / 2.0, 1.0))
    return float(np.mean(scores)) if scores else 0.0

def _bfs_distances(adjacency: np.ndarray, source: int, nodes: list[int]) -> dict[int, int]:
    allowed = set(nodes)
    queue: deque[int] = deque([int(source)])
    depths = {int(source): 0}
    while queue:
        node = queue.popleft()
        for nxt in np.flatnonzero(adjacency[node]).tolist():
            if nxt in allowed and nxt not in depths:
                depths[nxt] = depths[node] + 1
                queue.append(int(nxt))
    return depths

def _top_k_indices(values: np.ndarray, k: int, exclude_index: int) -> np.ndarray:
    ranking = np.lexsort((np.arange(values.size), -values))
    return ranking[ranking != int(exclude_index)][: int(k)]

def neighborhood_retention(transition: np.ndarray, k_nearest: int = 6, steps: int = 12, support_threshold: float = 0.01) -> float:
    n_nodes = int(transition.shape[0])
    current = np.eye(n_nodes, dtype=float)
    prior_neighbors: list[np.ndarray] | None = None
    prior_coverages: list[float] | None = None
    retentions: list[float] = []
    for _ in range(int(steps)):
        current = current @ transition
        coverages: list[float] = []
        neighbors = [_top_k_indices(current[row], min(int(k_nearest), n_nodes - 1), row) for row in range(n_nodes)]
        for row in range(n_nodes):
            support = current[row] >= float(support_threshold)
            support[row] = False
            coverages.append(float(np.sum(support) / max(n_nodes - 1, 1)))
        if prior_neighbors is not None and prior_coverages is not None:
            values: list[float] = []
            for prev, curr, prev_cov, curr_cov in zip(prior_neighbors, neighbors, prior_coverages, coverages):
                overlap_size = np.intersect1d(prev, curr, assume_unique=False).size
                values.append(float(overlap_size / max(prev.size, 1)) * min(prev_cov, curr_cov))
            retentions.append(float(np.mean(values)) if values else 0.0)
        prior_neighbors, prior_coverages = neighbors, coverages
    return float(np.mean(retentions)) if retentions else 0.0

def largest_component_mask(graph: InteractionGraph) -> np.ndarray:
    components = connected_components(graph.affinity > 0.0)
    mask = np.zeros(graph.n_nodes, dtype=bool)
    if components:
        mask[max(components, key=len)] = True
    return mask

def graph_metrics(graph: InteractionGraph, reference: InteractionGraph) -> dict[str, object]:
    adjacency = np.asarray(graph.affinity > 0.0, dtype=bool)
    largest_mask = largest_component_mask(graph)
    largest = np.flatnonzero(largest_mask).tolist()
    degree_state = np.sum(graph.affinity, axis=1)
    reference_state = np.sum(reference.affinity, axis=1)
    reference_mask = largest_component_mask(reference)
    transition = build_transport_operator(graph)
    efficiency_values: list[float] = []
    diameter = 0
    for source in largest:
        depths = _bfs_distances(adjacency, source, largest)
        for target in largest:
            if target > source and target in depths:
                diameter = max(diameter, int(depths[target]))
                efficiency_values.append(1.0 / max(depths[target], 1))
    return {
        "node_count": int(graph.n_nodes),
        "edge_count": int(np.sum(np.triu(adjacency, k=1))),
        "largest_component_fraction": float(len(largest) / max(graph.n_nodes, 1)),
        "clustering_coefficient": mean_local_clustering_coefficient(adjacency),
        "connectivity_diameter": float(diameter),
        "transport_efficiency": float(np.mean(efficiency_values)) if efficiency_values else 0.0,
        "persistence_score": neighborhood_retention(transition),
        "recovery_score": recovery_score(reference_state, degree_state, graph.positions, reference_mask),
        "overlap": overlap(reference_state, degree_state),
        "perturbation_sensitivity": 1.0 - overlap(reference_state, degree_state),
        "label": classify_single_mode(reference_state, degree_state, graph.positions, reference_mask),
        "largest_component_mask": largest_mask,
    }
