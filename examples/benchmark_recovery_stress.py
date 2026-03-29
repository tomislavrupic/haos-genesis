from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "haos_genesis" / "output" / ".mpl"))

import networkx as nx
import numpy as np

from haos_genesis.api import haos_stability_skill, suggest_recovery


OUTPUT_DIR = ROOT / "haos_genesis" / "output"


def _normalize_positions(positions: np.ndarray) -> np.ndarray:
    array = np.asarray(positions, dtype=float)
    mins = array.min(axis=0)
    spans = np.maximum(np.ptp(array, axis=0), 1.0e-12)
    return (array - mins) / spans


def _layout_positions(graph, mode: str, seed: int) -> np.ndarray:
    nodes = sorted(graph.nodes())
    if mode == "spring":
        layout = nx.spring_layout(graph, seed=seed)
        positions = np.asarray([layout[node] for node in nodes], dtype=float)
    elif mode == "circular":
        layout = nx.circular_layout(graph)
        positions = np.asarray([layout[node] for node in nodes], dtype=float)
    elif mode == "random":
        rng = np.random.default_rng(int(seed))
        positions = rng.uniform(0.0, 1.0, size=(len(nodes), 2))
    else:
        raise ValueError(f"unknown layout mode: {mode}")
    return _normalize_positions(positions)


def _weighted_edges_from_affinity(affinity: np.ndarray):
    return [
        (int(left), int(right), float(affinity[left, right]))
        for left in range(affinity.shape[0])
        for right in range(left + 1, affinity.shape[1])
        if affinity[left, right] > 0.0
    ]


def _gaussian_affinity(graph, positions: np.ndarray, sigma: float, drop_quantile: float | None = None, scale: float = 1.0, skew: bool = False):
    adjacency = nx.to_numpy_array(graph, nodelist=sorted(graph.nodes()), dtype=float)
    distances = np.linalg.norm(positions[:, None, :] - positions[None, :, :], axis=-1)
    affinity = adjacency * np.exp(-(distances ** 2) / max(2.0 * float(sigma) ** 2, 1.0e-12))
    if drop_quantile is not None and np.any(adjacency > 0.0):
        cutoff = float(np.quantile(distances[adjacency > 0.0], 1.0 - float(drop_quantile)))
        affinity[(adjacency > 0.0) & (distances >= cutoff)] = 0.0
        affinity = np.maximum(affinity, affinity.T)
    if skew:
        indices = [(left, right) for left in range(affinity.shape[0]) for right in range(left + 1, affinity.shape[1]) if affinity[left, right] > 0.0]
        factors = np.geomspace(0.08, 1.0, max(len(indices), 1))
        ranked = sorted(indices, key=lambda item: (distances[item[0], item[1]], item))
        for factor, (left, right) in zip(factors, ranked):
            affinity[left, right] *= float(factor)
            affinity[right, left] *= float(factor)
    affinity *= float(scale)
    return affinity


def _payload(name: str, group: str, graph, positions: np.ndarray, affinity: np.ndarray, seed: int):
    nodes = list(sorted(graph.nodes()))
    return {
        "name": name,
        "group": group,
        "nodes": nodes,
        "edges": _weighted_edges_from_affinity(affinity),
        "positions": positions.tolist(),
        "seed": int(seed),
        "refinement_levels": 5,
    }


def _stress_payloads():
    payloads = []

    sparse_graph = nx.path_graph(24)
    sparse_positions = _layout_positions(sparse_graph, "circular", seed=11)
    sparse_affinity = _gaussian_affinity(sparse_graph, sparse_positions, sigma=0.22)
    payloads.append(_payload("sparse_path", "sparse", sparse_graph, sparse_positions, sparse_affinity, seed=11))

    dense_graph = nx.complete_graph(18)
    dense_positions = _layout_positions(dense_graph, "spring", seed=13)
    dense_affinity = _gaussian_affinity(dense_graph, dense_positions, sigma=0.32)
    payloads.append(_payload("dense_complete", "dense", dense_graph, dense_positions, dense_affinity, seed=13))

    skew_graph = nx.watts_strogatz_graph(28, 4, 0.12, seed=17)
    skew_positions = _layout_positions(skew_graph, "spring", seed=17)
    skew_affinity = _gaussian_affinity(skew_graph, skew_positions, sigma=0.18, drop_quantile=0.5, skew=True)
    payloads.append(_payload("skewed_weights", "skewed", skew_graph, skew_positions, skew_affinity, seed=17))

    base_graph = nx.watts_strogatz_graph(36, 4, 0.08, seed=19)
    base_positions = _layout_positions(base_graph, "spring", seed=19)
    for scale_name, scale_value in (("x0p5", 0.5), ("x1p0", 1.0), ("x5p0", 5.0)):
        affinity = _gaussian_affinity(base_graph, base_positions, sigma=0.18, drop_quantile=0.65, scale=scale_value)
        payloads.append(_payload(f"scale_{scale_name}", "scale_equivalent", base_graph, base_positions, affinity, seed=19))

    for layout_name in ("spring", "circular", "random"):
        positions = _layout_positions(base_graph, layout_name, seed=29)
        affinity = _gaussian_affinity(base_graph, positions, sigma=0.18, drop_quantile=0.65)
        payloads.append(_payload(f"embedding_{layout_name}", "embedding_variants", base_graph, positions, affinity, seed=29))

    return payloads


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _run_row(payload: dict[str, object]) -> dict[str, object]:
    result = haos_stability_skill(payload)
    recovery = suggest_recovery(payload)
    intervention = recovery["best_intervention"]
    return {
        "group": str(payload["group"]),
        "name": str(payload["name"]),
        "n_nodes": int(len(payload["nodes"])),
        "n_edges": int(len(payload["edges"])),
        "k_star": int(result["k_star"]),
        "predicted_break": int(result["predicted_break"]),
        "safety_margin": float(result["safety_margin"]),
        "min_delta": float(result["min_delta"]),
        "confidence": float(result["confidence"]),
        "signature": f"{int(result['k_star'])}|{int(result['predicted_break'])}|{float(result['safety_margin']):.6f}|{float(result['min_delta']):.6f}",
        "has_intervention": int(intervention is not None),
        "intervention_kind": "" if intervention is None else str(intervention["kind"]),
        "intervention_edge": "" if intervention is None else f"{intervention['edge'][0]}-{intervention['edge'][1]}",
        "intervention_cost": 0.0 if intervention is None else float(intervention["cost"]),
        "k_star_gain": 0 if intervention is None else int(intervention["k_star_gain"]),
        "min_delta_gain": 0.0 if intervention is None else float(intervention["min_delta_gain"]),
        "safety_margin_gain": 0.0 if intervention is None else float(intervention["safety_margin_gain"]),
        "predicted_break_gain": 0 if intervention is None else int(intervention["predicted_break_gain"]),
    }


def _summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    summary = []
    groups = sorted({str(row["group"]) for row in rows})
    for group in groups:
        items = [row for row in rows if row["group"] == group]
        signatures = sorted({str(row["signature"]) for row in items})
        k_stars = sorted({int(row["k_star"]) for row in items})
        summary.append(
            {
                "group": group,
                "n_variants": int(len(items)),
                "signature_count": int(len(signatures)),
                "same_signature": int(len(signatures) == 1),
                "k_star_values": ",".join(str(value) for value in k_stars),
                "same_k_star": int(len(k_stars) == 1),
                "min_safety_margin": float(min(float(row["safety_margin"]) for row in items)),
                "max_safety_margin": float(max(float(row["safety_margin"]) for row in items)),
                "intervention_rate": float(sum(int(row["has_intervention"]) for row in items) / max(len(items), 1)),
                "best_k_star_gain": int(max(max(int(row["k_star_gain"]), 0) for row in items)),
                "max_min_delta_gain": float(max(float(row["min_delta_gain"]) for row in items)),
                "max_safety_margin_gain": float(max(float(row["safety_margin_gain"]) for row in items)),
            }
        )
    return summary


def main():
    payloads = _stress_payloads()
    run_rows = [_run_row(payload) for payload in payloads]
    summary_rows = _summarize(run_rows)
    _write_csv(OUTPUT_DIR / "recovery_stress_runs.csv", run_rows, list(run_rows[0].keys()))
    _write_csv(OUTPUT_DIR / "recovery_stress_summary.csv", summary_rows, list(summary_rows[0].keys()))
    for row in summary_rows:
        print(
            f"{row['group']}: variants={row['n_variants']} signatures={row['signature_count']} "
            f"k_star={row['k_star_values']} intervention_rate={row['intervention_rate']:.2f} "
            f"safety_margin=[{row['min_safety_margin']:.6f}, {row['max_safety_margin']:.6f}]"
        )


if __name__ == "__main__":
    main()
