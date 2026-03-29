from __future__ import annotations

import numpy as np

from demo_real_graph import build_trace_from_affinity, plot_trace
from haos_genesis.api import predict_collapse


def main():
    rng = np.random.default_rng(11)
    centers = np.asarray([[0.2, 0.2], [0.75, 0.25], [0.45, 0.8]], dtype=float)
    positions = np.vstack([center + 0.07 * rng.normal(size=(12, 2)) for center in centers])
    positions = np.clip(positions, 0.0, 1.0)
    distances = np.linalg.norm(positions[:, None, :] - positions[None, :, :], axis=-1)
    affinity = np.exp(-(distances ** 2) / (2.0 * 0.13 ** 2))
    affinity[distances > 0.32] = 0.0
    np.fill_diagonal(affinity, 0.0)
    trace = build_trace_from_affinity(positions, affinity, seed=11, refinement_levels=5)
    analysis = predict_collapse(trace)
    plot_trace(trace, analysis, "Embedding Stability Trace", "demo_ml_embeddings.png")
    print({key: analysis[key] for key in ("k_star", "predicted_break", "safety_margin")})


if __name__ == "__main__":
    main()
