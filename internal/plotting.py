from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("MPLCONFIGDIR", str(PACKAGE_DIR / "output" / ".mpl"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .graph_builder import InteractionGraph


def render_graph_frame(graph: InteractionGraph, title: str) -> np.ndarray:
    fig, ax = plt.subplots(figsize=(6, 6), facecolor="#070809")
    ax.set_facecolor("#070809")
    positions = np.asarray(graph.positions, dtype=float)
    edges = np.transpose(np.nonzero(np.triu(graph.affinity > 0.0, k=1)))
    for index in np.argsort(graph.affinity[edges[:, 0], edges[:, 1]] if edges.size else np.array([], dtype=float)).tolist():
        u, v = edges[index]
        weight = float(graph.affinity[u, v])
        ax.plot(positions[[u, v], 0], positions[[u, v], 1], color=(0.80, 0.83, 0.88, min(0.55, 0.12 + 0.55 * weight)), lw=0.35 + 1.1 * weight)
    degrees = np.sum(graph.affinity > 0.0, axis=1)
    ax.scatter(positions[:, 0], positions[:, 1], s=8 + 3 * degrees, c="#f2efe8", alpha=np.where(degrees > 0, 0.95, 0.18), linewidths=0)
    ax.set(xlim=(0, 1), ylim=(0, 1), xticks=[], yticks=[], title=title)
    ax.title.set_color("#f2efe8")
    fig.canvas.draw()
    frame = np.asarray(fig.canvas.buffer_rgba())[..., :3].copy()
    plt.close(fig)
    return frame
