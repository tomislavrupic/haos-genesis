from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
import sys

PACKAGE_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(PACKAGE_DIR / "output" / ".mpl"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from haos_genesis.api import compute_k_star
from haos_genesis.generator import generate_universe
from haos_genesis.paths import OUTPUT_DIR


def _run_case(seed: int, size: int, refinement_levels: int, perturbation: bool, strength: float) -> dict[str, float | int | str]:
    trace, _ = generate_universe(
        seed=seed,
        size=size,
        refinement_levels=refinement_levels,
        perturbation=perturbation,
        perturbation_strength=strength,
    )
    metrics = [entry["metrics"] for entry in trace]
    k_data = compute_k_star(trace)
    break_index = min(int(k_data["k_star"]) + 1, len(trace) - 1)
    return {
        "seed": int(seed),
        "mode": "off" if not perturbation else "on",
        "strength": float(strength),
        "strength_label": "off" if not perturbation else f"{strength:.2f}",
        "break_level": int(trace[break_index]["level"]),
        "final_global_overlap": float(metrics[-1]["overlap"]),
        "failure_events": int(sum(1 for item in metrics if str(item["label"]) == "unstable")),
        "mean_recovery_score": float(np.mean([float(item["recovery_score"]) for item in metrics])),
    }


def _write_csv(path: Path, rows: list[dict[str, float | int | str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["seed", "mode", "strength", "strength_label", "break_level", "final_global_overlap", "failure_events", "mean_recovery_score"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _plot_break_heatmap(path: Path, rows: list[dict[str, float | int | str]], strengths: list[float], seeds: list[int]) -> None:
    labels = ["off"] + [f"{value:.2f}" for value in strengths]
    matrix = np.full((len(seeds), len(labels)), np.nan, dtype=float)
    lookup = {(int(row["seed"]), str(row["strength_label"])): int(row["break_level"]) for row in rows}
    for row_index, seed in enumerate(seeds):
        for col_index, label in enumerate(labels):
            matrix[row_index, col_index] = lookup.get((int(seed), label), np.nan)
    fig, ax = plt.subplots(figsize=(1.2 + 1.1 * len(labels), 1.2 + 0.35 * len(seeds)))
    image = ax.imshow(matrix, aspect="auto", cmap="magma", vmin=0, vmax=np.nanmax(matrix) if np.isfinite(matrix).any() else 1.0)
    ax.set_xticks(range(len(labels)), labels=labels)
    ax.set_yticks(range(len(seeds)), labels=[str(seed) for seed in seeds])
    ax.set_xlabel("perturbation strength")
    ax.set_ylabel("seed")
    ax.set_title("Break Level by Seed and Perturbation Strength")
    for row_index, seed in enumerate(seeds):
        for col_index, label in enumerate(labels):
            value = lookup.get((int(seed), label))
            if value is not None:
                ax.text(col_index, row_index, str(value), ha="center", va="center", color="#f8fafc", fontsize=8)
    fig.colorbar(image, ax=ax, label="break level")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def build_collapse_map(
    seeds: list[int],
    strengths: list[float],
    size: int = 128,
    refinement_levels: int = 5,
    output_dir: str | Path = OUTPUT_DIR,
) -> list[dict[str, float | int | str]]:
    rows = [_run_case(seed, size, refinement_levels, False, 0.0) for seed in seeds]
    rows.extend(_run_case(seed, size, refinement_levels, True, strength) for seed in seeds for strength in strengths)
    output_root = Path(output_dir)
    _write_csv(output_root / "collapse_map.csv", rows)
    _plot_break_heatmap(output_root / "collapse_map_break_level.png", rows, strengths, seeds)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep HAOS Genesis collapse break levels across seeds and perturbation strengths.")
    parser.add_argument("--seed-start", type=int, default=20)
    parser.add_argument("--seed-stop", type=int, default=30)
    parser.add_argument("--strengths", type=float, nargs="*", default=[0.01, 0.03, 0.05, 0.08])
    parser.add_argument("--size", type=int, default=128)
    parser.add_argument("--refinement-levels", type=int, default=5)
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    args = parser.parse_args()
    seeds = list(range(int(args.seed_start), int(args.seed_stop) + 1))
    rows = build_collapse_map(seeds, [float(value) for value in args.strengths], int(args.size), int(args.refinement_levels), str(args.output_dir))
    for row in rows:
        print(
            f"seed={row['seed']} strength={row['strength_label']} break={row['break_level']} "
            f"final_overlap={row['final_global_overlap']:.6f} failures={row['failure_events']} "
            f"mean_recovery={row['mean_recovery_score']:.6f}"
        )


if __name__ == "__main__":
    main()
