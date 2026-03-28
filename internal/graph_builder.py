from __future__ import annotations
from dataclasses import dataclass
import numpy as np
EPSILON = 1.0e-12

def _pairwise_distances(positions: np.ndarray) -> np.ndarray:
    delta = positions[:, None, :] - positions[None, :, :]
    return np.linalg.norm(delta, axis=-1)

@dataclass(frozen=True)
class InteractionGraph:
    positions: np.ndarray
    affinity: np.ndarray
    distances: np.ndarray
    kernel_width: float
    locality_radius: float
    seed: int
    level: int

    @property
    def n_nodes(self) -> int:
        return int(self.positions.shape[0])

def _resolve_locality_radius(kernel_width: float, locality_radius: float | None, embedding_dim: int) -> float:
    if locality_radius is not None:
        return float(locality_radius)
    return float(min(3.0 * kernel_width, np.sqrt(float(embedding_dim))))

def build_graph(
    size: int,
    kernel_width: float,
    seed: int,
    level: int = 0,
    positions: np.ndarray | None = None,
    locality_radius: float | None = None,
) -> InteractionGraph:
    rng = np.random.default_rng(int(seed))
    positions = rng.uniform(0.0, 1.0, size=(int(size), 2)) if positions is None else np.asarray(positions, dtype=float)
    distances = _pairwise_distances(positions)
    radius = _resolve_locality_radius(float(kernel_width), locality_radius, int(positions.shape[1]))
    affinity = np.exp(-(distances ** 2) / max(2.0 * float(kernel_width) ** 2, EPSILON))
    affinity[distances > radius] = 0.0
    np.fill_diagonal(affinity, 0.0)
    return InteractionGraph(positions, affinity, distances, float(kernel_width), radius, int(seed), int(level))

def build_transport_operator(graph: InteractionGraph, self_weight: float = 0.05) -> np.ndarray:
    affinity = np.asarray(graph.affinity, dtype=float)
    transition = np.zeros_like(affinity, dtype=float)
    row_sums = affinity.sum(axis=1)
    nonzero_rows = row_sums > EPSILON
    transition[nonzero_rows] = affinity[nonzero_rows] / row_sums[nonzero_rows, None]
    for index in np.flatnonzero(~nonzero_rows).tolist():
        transition[index, index] = 1.0
    transition = (1.0 - float(self_weight)) * transition + float(self_weight) * np.eye(graph.n_nodes, dtype=float)
    return transition / np.maximum(transition.sum(axis=1, keepdims=True), EPSILON)
