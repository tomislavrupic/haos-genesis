from __future__ import annotations

import argparse
import csv
import math
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

from haos_genesis.generator import generate_universe
from haos_genesis.paths import OUTPUT_DIR


LEVELS = (0, 1, 2)
LEVEL_FEATURES = (
    "largest_component_fraction",
    "clustering_coefficient",
    "connectivity_diameter",
    "transport_efficiency",
    "persistence_score",
    "recovery_score",
    "local_overlap",
    "perturbation_sensitivity",
    "edge_count",
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


def _select_seed_families(rows: list[dict[str, str]], strength_label: str) -> dict[int, list[int]]:
    selected = [row for row in rows if row["strength_label"] == strength_label and int(row["break_level"]) in (2, 3)]
    return {
        2: sorted(int(row["seed"]) for row in selected if int(row["break_level"]) == 2),
        3: sorted(int(row["seed"]) for row in selected if int(row["break_level"]) == 3),
    }


def _mode_from_strength_label(strength_label: str) -> tuple[bool, float]:
    if strength_label == "off":
        return False, 0.0
    return True, float(strength_label)


def _extract_seed_record(seed: int, break_level: int, size: int, refinement_levels: int, strength_label: str) -> dict[str, object]:
    perturbation, strength = _mode_from_strength_label(strength_label)
    trace, _ = generate_universe(
        seed=seed,
        size=size,
        refinement_levels=refinement_levels,
        perturbation=perturbation,
        perturbation_strength=strength,
    )
    metric_by_level = {int(entry["level"]): dict(entry["metrics"]) for entry in trace}
    record: dict[str, object] = {
        "seed": int(seed),
        "family": f"break_{break_level}",
        "break_level": int(break_level),
        "strength_label": strength_label,
    }
    for level in LEVELS:
        metrics = metric_by_level[level]
        node_count = max(int(metrics["node_count"]), 1)
        record[f"L{level}_mean_degree"] = float(2.0 * float(metrics["edge_count"]) / node_count)
        for feature in LEVEL_FEATURES:
            record[f"L{level}_{feature}"] = float(metrics[feature])
    record["delta_persistence_1_to_2"] = float(metric_by_level[2]["persistence_score"] - metric_by_level[1]["persistence_score"])
    record["delta_recovery_1_to_2"] = float(metric_by_level[2]["recovery_score"] - metric_by_level[1]["recovery_score"])
    record["delta_local_overlap_1_to_2"] = float(metric_by_level[2]["local_overlap"] - metric_by_level[1]["local_overlap"])
    return record


def _pooled_std(left: np.ndarray, right: np.ndarray) -> float:
    if left.size < 2 or right.size < 2:
        merged = np.concatenate([left, right])
        return float(np.std(merged, ddof=0)) if merged.size else 0.0
    numerator = (left.size - 1) * float(np.var(left, ddof=1)) + (right.size - 1) * float(np.var(right, ddof=1))
    denominator = max(left.size + right.size - 2, 1)
    return float(math.sqrt(max(numerator / denominator, 0.0)))


def _summarize(records: list[dict[str, object]]) -> list[dict[str, object]]:
    early = [record for record in records if record["family"] == "break_2"]
    late = [record for record in records if record["family"] == "break_3"]
    feature_names = [name for name in records[0].keys() if name not in {"seed", "family", "break_level", "strength_label"}]
    summary: list[dict[str, object]] = []
    for feature in feature_names:
        left = np.asarray([float(record[feature]) for record in early], dtype=float)
        right = np.asarray([float(record[feature]) for record in late], dtype=float)
        difference = float(np.mean(left) - np.mean(right))
        pooled = _pooled_std(left, right)
        effect = 0.0 if pooled <= 1.0e-12 else float(difference / pooled)
        summary.append(
            {
                "feature": feature,
                "break_2_mean": float(np.mean(left)),
                "break_3_mean": float(np.mean(right)),
                "difference": difference,
                "effect_size": effect,
                "abs_effect_size": abs(effect),
            }
        )
    return sorted(summary, key=lambda row: float(row["abs_effect_size"]), reverse=True)


def _plot_top_features(path: Path, records: list[dict[str, object]], summary: list[dict[str, object]], top_k: int = 6) -> None:
    early = [record for record in records if record["family"] == "break_2"]
    late = [record for record in records if record["family"] == "break_3"]
    features = [row["feature"] for row in summary[:top_k]]
    rows = math.ceil(len(features) / 2)
    fig, axes = plt.subplots(rows, 2, figsize=(12, 3.2 * rows))
    axes_array = np.atleast_1d(axes).ravel()
    for axis, feature in zip(axes_array, features):
        axis.boxplot(
            [
                [float(record[feature]) for record in early],
                [float(record[feature]) for record in late],
            ],
            tick_labels=["break=2", "break=3"],
            patch_artist=True,
            boxprops={"facecolor": "#cbd5e1"},
            medianprops={"color": "#0f172a"},
        )
        axis.set_title(str(feature))
        axis.tick_params(axis="x", labelrotation=0)
    for axis in axes_array[len(features):]:
        axis.axis("off")
    fig.suptitle("Top Separating Pre-Break Features", y=0.995)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def build_seed_family_comparison(
    collapse_map_path: str,
    strength_label: str = "off",
    size: int = 128,
    refinement_levels: int = 5,
    output_dir: str | Path = OUTPUT_DIR,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    families = _select_seed_families(_read_rows(Path(collapse_map_path)), strength_label)
    if not families[2] or not families[3]:
        raise ValueError(f"Need both break-2 and break-3 seed families for strength_label={strength_label}.")
    records = [_extract_seed_record(seed, 2, size, refinement_levels, strength_label) for seed in families[2]]
    records.extend(_extract_seed_record(seed, 3, size, refinement_levels, strength_label) for seed in families[3])
    summary = _summarize(records)
    output_root = Path(output_dir)
    stem = f"seed_family_{strength_label.replace('.', 'p')}"
    _write_csv(output_root / f"{stem}_features.csv", records, list(records[0].keys()))
    _write_csv(output_root / f"{stem}_summary.csv", summary, list(summary[0].keys()))
    _plot_top_features(output_root / f"{stem}_top_features.png", records, summary)
    return records, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare break-2 versus break-3 seed families from a HAOS Genesis collapse map.")
    parser.add_argument("--collapse-map", default=str(OUTPUT_DIR / "collapse_map.csv"))
    parser.add_argument("--strength-label", default="off")
    parser.add_argument("--size", type=int, default=128)
    parser.add_argument("--refinement-levels", type=int, default=5)
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    args = parser.parse_args()
    records, summary = build_seed_family_comparison(
        collapse_map_path=str(args.collapse_map),
        strength_label=str(args.strength_label),
        size=int(args.size),
        refinement_levels=int(args.refinement_levels),
        output_dir=str(args.output_dir),
    )
    early = sum(1 for record in records if record["family"] == "break_2")
    late = sum(1 for record in records if record["family"] == "break_3")
    print(f"break_2={early} break_3={late} strength_label={args.strength_label}")
    for row in summary[:10]:
        print(
            f"{row['feature']}: break_2_mean={row['break_2_mean']:.6f} "
            f"break_3_mean={row['break_3_mean']:.6f} diff={row['difference']:.6f} "
            f"effect={row['effect_size']:.6f}"
        )


if __name__ == "__main__":
    main()
