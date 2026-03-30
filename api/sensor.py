from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any

try:
    from .skill import haos_stability_skill
except ImportError:  # pragma: no cover - direct script execution
    import sys

    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT.parent) not in sys.path:
        sys.path.insert(0, str(ROOT.parent))
    from haos_genesis.api.skill import haos_stability_skill


INVALID_OUTPUT = {"state": "invalid", "reason": "insufficient_structure"}


def _is_connected(nodes, edges) -> bool:
    if not nodes or not edges:
        return False
    adjacency = {node: set() for node in nodes}
    for edge in edges:
        if len(edge) < 2:
            return False
        left, right = edge[0], edge[1]
        if left not in adjacency or right not in adjacency:
            return False
        adjacency[left].add(right)
        adjacency[right].add(left)
    start = nodes[0]
    stack = [start]
    seen = {start}
    while stack:
        node = stack.pop()
        for neighbor in adjacency[node]:
            if neighbor in seen:
                continue
            seen.add(neighbor)
            stack.append(neighbor)
    return len(seen) == len(nodes)


def _classify_state(safety_margin: float) -> str:
    if safety_margin < 0.0:
        return "critical"
    if safety_margin < 0.05:
        return "warning"
    return "stable"


class HAOSSensor:
    def __init__(self, window_size: int = 20):
        self.window_size = int(window_size)
        if self.window_size < 1:
            raise ValueError("window_size must be positive")
        self.history: deque[dict[str, Any]] = deque(maxlen=self.window_size)

    def update(self, graph: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(graph, dict) or not graph:
            return dict(INVALID_OUTPUT)
        if "nodes" in graph:
            nodes = list(graph.get("nodes", []))
            edges = list(graph.get("edges", []))
            if len(nodes) < 3 or not _is_connected(nodes, edges):
                return dict(INVALID_OUTPUT)
        try:
            current = haos_stability_skill(graph)
        except (KeyError, TypeError, ValueError):
            return dict(INVALID_OUTPUT)

        previous = self.history[-1] if self.history else None
        drift = 0.0 if previous is None else float(current["safety_margin"]) - float(previous["safety_margin"])
        k_shift = 0 if previous is None else int(current["k_star"]) - int(previous["k_star"])
        output = {
            "state": _classify_state(float(current["safety_margin"])),
            "k_star": int(current["k_star"]),
            "predicted_break": int(current["predicted_break"]),
            "safety_margin": float(current["safety_margin"]),
            "min_delta": float(current["min_delta"]),
            "confidence": float(current["confidence"]),
            "drift": float(drift),
            "k_shift": int(k_shift),
        }
        self.history.append(output)
        return output


def monitor_sequence(graphs: list[dict[str, Any]], window_size: int = 20) -> list[dict[str, Any]]:
    sensor = HAOSSensor(window_size=window_size)
    return [sensor.update(graph) for graph in graphs]


if __name__ == "__main__":
    import sys

    ROOT = Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from haos_genesis.api import haos_stability_skill

    sensor = HAOSSensor()
    for i in range(5):
        graph = {
            "nodes": [0, 1, 2, 3],
            "edges": [(0, 1, 1.0), (1, 2, max(0.2, 0.9 - 0.1 * i)), (2, 3, 0.8)],
        }
        print(sensor.update(graph))
