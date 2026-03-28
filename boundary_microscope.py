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

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from haos_genesis.generator import generate_universe
from haos_genesis.internal.metrics import connected_components
from haos_genesis.paths import OUTPUT_DIR


TRACE_LEVELS = (1, 2, 3)
PLOT_FEATURES = (
    "persistence_score",
    "recovery_score",
    "clustering_coefficient",
    "largest_component_fraction",
    "local_overlap",
    "component_count",
)


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _load_threshold(predictor_summary_csv: str, feature: str = "delta_persistence_1_to_2") -> float:
    rows = _read_rows(Path(predictor_summary_csv))
    match = next(row for row in rows if row["feature"] == feature)
    return float(match["threshold"])


def _select_boundary_seeds(features_csv: str, threshold: float, n_per_family: int) -> list[dict[str, object]]:
    rows = _read_rows(Path(features_csv))
    selected: list[dict[str, object]] = []
    for family in ("break_2", "break_3"):
        family_rows = [row for row in rows if row["family"] == family]
        ordered = sorted(family_rows, key=lambda row: abs(float(row["delta_persistence_1_to_2"]) - threshold))
        for row in ordered[: int(n_per_family)]:
            selected.append(
                {
                    "seed": int(row["seed"]),
                    "family": family,
                    "break_level": int(row["break_level"]),
                    "delta_persistence_1_to_2": float(row["delta_persistence_1_to_2"]),
                    "distance_to_threshold": abs(float(row["delta_persistence_1_to_2"]) - threshold),
                }
            )
    return sorted(selected, key=lambda row: (row["family"], row["distance_to_threshold"], row["seed"]))


def _component_count(entry: dict) -> int:
    graph = entry["graph"]
    return len(connected_components(graph.affinity > 0.0))


def _trace_rows(selected: list[dict[str, object]], size: int, refinement_levels: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in selected:
        trace, _ = generate_universe(seed=int(item["seed"]), size=size, refinement_levels=refinement_levels, perturbation=False, perturbation_strength=0.0)
        for entry in trace:
            level = int(entry["level"])
            if level not in TRACE_LEVELS:
                continue
            metrics = dict(entry["metrics"])
            rows.append(
                {
                    "seed": int(item["seed"]),
                    "family": str(item["family"]),
                    "break_level": int(item["break_level"]),
                    "level": level,
                    "delta_persistence_1_to_2": float(item["delta_persistence_1_to_2"]),
                    "distance_to_threshold": float(item["distance_to_threshold"]),
                    "persistence_score": float(metrics["persistence_score"]),
                    "recovery_score": float(metrics["recovery_score"]),
                    "clustering_coefficient": float(metrics["clustering_coefficient"]),
                    "largest_component_fraction": float(metrics["largest_component_fraction"]),
                    "local_overlap": float(metrics["local_overlap"]),
                    "component_count": int(_component_count(entry)),
                }
            )
    return rows


def _plot_boundary_microscope(path: Path, rows: list[dict[str, object]]) -> None:
    seeds = sorted({int(row["seed"]) for row in rows})
    style = {seed: ("#b45309" if any(r["family"] == "break_2" and int(r["seed"]) == seed for r in rows) else "#0f766e") for seed in seeds}
    lines = {seed: ("-" if any(r["family"] == "break_2" and int(r["seed"]) == seed for r in rows) else "--") for seed in seeds}
    fig, axes = plt.subplots(3, 2, figsize=(11.5, 10))
    axes_array = axes.ravel()
    for axis, feature in zip(axes_array, PLOT_FEATURES):
        for seed in seeds:
            seed_rows = sorted((row for row in rows if int(row["seed"]) == seed), key=lambda row: int(row["level"]))
            axis.plot(
                [int(row["level"]) for row in seed_rows],
                [float(row[feature]) for row in seed_rows],
                color=style[seed],
                linestyle=lines[seed],
                marker="o",
                label=f"{seed}",
            )
        axis.set_title(feature)
        axis.set_xlabel("level")
    handles, labels = axes_array[0].get_legend_handles_labels()
    fig.legend(handles, labels, title="seed", loc="upper right", ncol=2)
    fig.suptitle("Boundary Microscope: Levels 1→3", y=0.995)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def build_boundary_microscope(
    predictor_summary_csv: str,
    features_csv: str,
    size: int = 128,
    refinement_levels: int = 5,
    n_per_family: int = 3,
    output_dir: str | Path = OUTPUT_DIR,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    threshold = _load_threshold(predictor_summary_csv)
    selected = _select_boundary_seeds(features_csv, threshold, n_per_family)
    rows = _trace_rows(selected, size, refinement_levels)
    output_root = Path(output_dir)
    _write_csv(output_root / "boundary_microscope_selected.csv", selected, list(selected[0].keys()))
    _write_csv(output_root / "boundary_microscope_traces.csv", rows, list(rows[0].keys()))
    _plot_boundary_microscope(output_root / "boundary_microscope_levels_1_to_3.png", rows)
    return selected, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Zoom into seeds nearest the HAOS Genesis collapse threshold.")
    parser.add_argument("--predictor-summary", default=str(OUTPUT_DIR / "predictor_off_summary.csv"))
    parser.add_argument("--features-csv", default=str(OUTPUT_DIR / "seed_family_off_features.csv"))
    parser.add_argument("--size", type=int, default=128)
    parser.add_argument("--refinement-levels", type=int, default=5)
    parser.add_argument("--n-per-family", type=int, default=3)
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    args = parser.parse_args()
    selected, _ = build_boundary_microscope(
        predictor_summary_csv=str(args.predictor_summary),
        features_csv=str(args.features_csv),
        size=int(args.size),
        refinement_levels=int(args.refinement_levels),
        n_per_family=int(args.n_per_family),
        output_dir=str(args.output_dir),
    )
    for row in selected:
        print(
            f"seed={row['seed']} family={row['family']} break={row['break_level']} "
            f"delta_persistence_1_to_2={row['delta_persistence_1_to_2']:.6f} "
            f"distance_to_threshold={row['distance_to_threshold']:.6f}"
        )


if __name__ == "__main__":
    main()
