from __future__ import annotations

import time

import numpy as np

from .internal.graph_builder import InteractionGraph


def resolve_seed(seed: int | None) -> int:
    return int(seed if seed is not None else time.time_ns() % (2**31 - 1))


def deterministic_rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(int(seed))


def safe_graph_copy(graph: InteractionGraph) -> InteractionGraph:
    return InteractionGraph(
        positions=np.asarray(graph.positions, dtype=float).copy(),
        affinity=np.asarray(graph.affinity, dtype=float).copy(),
        distances=np.asarray(graph.distances, dtype=float).copy(),
        kernel_width=float(graph.kernel_width),
        locality_radius=float(graph.locality_radius),
        seed=int(graph.seed),
        level=int(graph.level),
    )
