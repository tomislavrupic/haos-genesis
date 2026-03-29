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
from haos_genesis.internal.metrics import connected_components
from haos_genesis.paths import OUTPUT_DIR


TRACE_LEVELS = (1, 2, 3)
SUMMARY_FIELDS = [
    "variant",
    "size",
    "schedule_shift",
    "perturbation",
    "perturbation_strength",
    "n_break_2",
    "n_break_3",
    "threshold",
    "transition_low_seed",
    "transition_high_seed",
    "break_2_mean_delta_persistence_1_to_2",
    "break_3_mean_delta_persistence_1_to_2",
    "break_2_mean_delta_recovery_1_to_2",
    "break_3_mean_delta_recovery_1_to_2",
    "selected_min_largest_component_fraction",
    "selected_max_component_count",
    "selected_seeds",
    "mechanism_holds",
]
SELECTED_FIELDS = [
    "variant",
    "size",
    "schedule_shift",
    "perturbation",
    "perturbation_strength",
    "seed",
    "family",
    "break_level",
    "delta_persistence_1_to_2",
    "delta_recovery_1_to_2",
    "distance_to_threshold",
]
TRACE_FIELDS = [
    "variant",
    "size",
    "schedule_shift",
    "perturbation",
    "perturbation_strength",
    "seed",
    "family",
    "break_level",
    "level",
    "persistence_score",
    "recovery_score",
    "clustering_coefficient",
    "largest_component_fraction",
    "local_overlap",
    "component_count",
]


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _variant_suite(base_size: int, sizes: list[int], schedule_shifts: list[float], perturbation_strength: float) -> list[dict[str, object]]:
    variants = [
        {
            "variant": f"size_{size}",
            "size": int(size),
            "schedule_shift": 0.0,
            "perturbation": False,
            "perturbation_strength": 0.0,
        }
        for size in sizes
    ]
    variants.extend(
        {
            "variant": f"shift_{shift:.1f}".replace(".", "p"),
            "size": int(base_size),
            "schedule_shift": float(shift),
            "perturbation": False,
            "perturbation_strength": 0.0,
        }
        for shift in schedule_shifts
    )
    variants.append(
        {
            "variant": f"perturb_{perturbation_strength:.2f}".replace(".", "p"),
            "size": int(base_size),
            "schedule_shift": 0.0,
            "perturbation": True,
            "perturbation_strength": float(perturbation_strength),
        }
    )
    return variants


def _run_seed_case(seed: int, size: int, refinement_levels: int, schedule_shift: float, perturbation: bool, perturbation_strength: float) -> dict[str, object]:
    trace, _ = generate_universe(
        seed=seed,
        size=size,
        refinement_levels=refinement_levels,
        perturbation=perturbation,
        perturbation_strength=perturbation_strength,
        schedule_shift=schedule_shift,
    )
    metrics = [dict(entry["metrics"]) for entry in trace]
    k_data = compute_k_star(trace)
    break_index = min(int(k_data["k_star"]) + 1, len(trace) - 1)
    return {
        "seed": int(seed),
        "break_level": int(trace[break_index]["level"]),
        "delta_persistence_1_to_2": float(metrics[2]["persistence_score"] - metrics[1]["persistence_score"]),
        "delta_recovery_1_to_2": float(metrics[2]["recovery_score"] - metrics[1]["recovery_score"]),
    }


def _transition_band(rows: list[dict[str, object]], feature: str) -> dict[str, object]:
    ordered = sorted((float(row[feature]), int(row["break_level"]), int(row["seed"])) for row in rows)
    best_gap = None
    best_pair = None
    for left, right in zip(ordered, ordered[1:]):
        if left[1] == right[1]:
            continue
        gap = abs(right[0] - left[0])
        if best_gap is None or gap < best_gap:
            best_gap = gap
            best_pair = (left, right)
    if best_pair is None:
        raise ValueError("Need both break-2 and break-3 seeds to determine a transition band.")
    left, right = best_pair
    return {
        "transition_low_value": float(left[0]),
        "transition_low_break": int(left[1]),
        "transition_low_seed": int(left[2]),
        "transition_high_value": float(right[0]),
        "transition_high_break": int(right[1]),
        "transition_high_seed": int(right[2]),
        "threshold": float((left[0] + right[0]) / 2.0),
    }


def _select_boundary_seeds(rows: list[dict[str, object]], threshold: float, n_per_family: int) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    for break_level in (2, 3):
        family = [row for row in rows if int(row["break_level"]) == break_level]
        ordered = sorted(family, key=lambda row: abs(float(row["delta_persistence_1_to_2"]) - threshold))
        for row in ordered[: int(n_per_family)]:
            selected.append(
                {
                    "seed": int(row["seed"]),
                    "family": f"break_{break_level}",
                    "break_level": int(break_level),
                    "delta_persistence_1_to_2": float(row["delta_persistence_1_to_2"]),
                    "delta_recovery_1_to_2": float(row["delta_recovery_1_to_2"]),
                    "distance_to_threshold": abs(float(row["delta_persistence_1_to_2"]) - threshold),
                }
            )
    return sorted(selected, key=lambda row: (str(row["family"]), float(row["distance_to_threshold"]), int(row["seed"])))


def _trace_rows(variant: dict[str, object], selected: list[dict[str, object]], refinement_levels: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in selected:
        trace, _ = generate_universe(
            seed=int(item["seed"]),
            size=int(variant["size"]),
            refinement_levels=refinement_levels,
            perturbation=bool(variant["perturbation"]),
            perturbation_strength=float(variant["perturbation_strength"]),
            schedule_shift=float(variant["schedule_shift"]),
        )
        for entry in trace:
            level = int(entry["level"])
            if level not in TRACE_LEVELS:
                continue
            metrics = dict(entry["metrics"])
            rows.append(
                {
                    "variant": str(variant["variant"]),
                    "size": int(variant["size"]),
                    "schedule_shift": float(variant["schedule_shift"]),
                    "perturbation": int(bool(variant["perturbation"])),
                    "perturbation_strength": float(variant["perturbation_strength"]),
                    "seed": int(item["seed"]),
                    "family": str(item["family"]),
                    "break_level": int(item["break_level"]),
                    "level": level,
                    "persistence_score": float(metrics["persistence_score"]),
                    "recovery_score": float(metrics["recovery_score"]),
                    "clustering_coefficient": float(metrics["clustering_coefficient"]),
                    "largest_component_fraction": float(metrics["largest_component_fraction"]),
                    "local_overlap": float(metrics["local_overlap"]),
                    "component_count": int(len(connected_components(entry["graph"].affinity > 0.0))),
                }
            )
    return rows


def _summarize_variant(variant: dict[str, object], case_rows: list[dict[str, object]], selected: list[dict[str, object]], trace_rows: list[dict[str, object]], band: dict[str, object]) -> dict[str, object]:
    break_2 = [row for row in case_rows if int(row["break_level"]) == 2]
    break_3 = [row for row in case_rows if int(row["break_level"]) == 3]
    min_component_fraction = min(float(row["largest_component_fraction"]) for row in trace_rows)
    max_component_count = max(int(row["component_count"]) for row in trace_rows)
    mean_break_2_dp = float(np.mean([float(row["delta_persistence_1_to_2"]) for row in break_2]))
    mean_break_3_dp = float(np.mean([float(row["delta_persistence_1_to_2"]) for row in break_3]))
    mean_break_2_dr = float(np.mean([float(row["delta_recovery_1_to_2"]) for row in break_2]))
    mean_break_3_dr = float(np.mean([float(row["delta_recovery_1_to_2"]) for row in break_3]))
    mechanism_holds = (
        min_component_fraction >= 0.999999
        and max_component_count == 1
        and mean_break_2_dp < mean_break_3_dp
        and mean_break_2_dr < mean_break_3_dr
    )
    return {
        "variant": str(variant["variant"]),
        "size": int(variant["size"]),
        "schedule_shift": float(variant["schedule_shift"]),
        "perturbation": int(bool(variant["perturbation"])),
        "perturbation_strength": float(variant["perturbation_strength"]),
        "n_break_2": int(len(break_2)),
        "n_break_3": int(len(break_3)),
        "threshold": float(band["threshold"]),
        "transition_low_seed": int(band["transition_low_seed"]),
        "transition_high_seed": int(band["transition_high_seed"]),
        "break_2_mean_delta_persistence_1_to_2": mean_break_2_dp,
        "break_3_mean_delta_persistence_1_to_2": mean_break_3_dp,
        "break_2_mean_delta_recovery_1_to_2": mean_break_2_dr,
        "break_3_mean_delta_recovery_1_to_2": mean_break_3_dr,
        "selected_min_largest_component_fraction": float(min_component_fraction),
        "selected_max_component_count": int(max_component_count),
        "selected_seeds": ",".join(str(int(row["seed"])) for row in selected),
        "mechanism_holds": int(bool(mechanism_holds)),
    }


def _plot_variant_gaps(path: Path, summary_rows: list[dict[str, object]]) -> None:
    labels = [str(row["variant"]) for row in summary_rows]
    dp_gap = [float(row["break_2_mean_delta_persistence_1_to_2"]) - float(row["break_3_mean_delta_persistence_1_to_2"]) for row in summary_rows]
    dr_gap = [float(row["break_2_mean_delta_recovery_1_to_2"]) - float(row["break_3_mean_delta_recovery_1_to_2"]) for row in summary_rows]
    colors = ["#0f766e" if int(row["mechanism_holds"]) else "#b91c1c" for row in summary_rows]
    x = np.arange(len(labels))
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    axes[0].bar(x, dp_gap, color=colors)
    axes[0].axhline(0.0, color="#1f2937", linewidth=1.0)
    axes[0].set_ylabel("break2 - break3")
    axes[0].set_title("Delta Persistence Separation")
    axes[1].bar(x, dr_gap, color=colors)
    axes[1].axhline(0.0, color="#1f2937", linewidth=1.0)
    axes[1].set_ylabel("break2 - break3")
    axes[1].set_title("Delta Recovery Separation")
    axes[1].set_xticks(x, labels=labels, rotation=25, ha="right")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _write_note(path: Path, summary_rows: list[dict[str, object]]) -> None:
    lines = ["# HAOS Genesis Mechanism Validation", ""]
    for row in summary_rows:
        status = "holds" if int(row["mechanism_holds"]) else "mixed"
        lines.extend(
            [
                f"## {row['variant']}",
                f"- status: {status}",
                f"- break families: break_2={row['n_break_2']}, break_3={row['n_break_3']}",
                f"- threshold: {float(row['threshold']):.6f}",
                f"- delta persistence means: break_2={float(row['break_2_mean_delta_persistence_1_to_2']):.6f}, break_3={float(row['break_3_mean_delta_persistence_1_to_2']):.6f}",
                f"- delta recovery means: break_2={float(row['break_2_mean_delta_recovery_1_to_2']):.6f}, break_3={float(row['break_3_mean_delta_recovery_1_to_2']):.6f}",
                f"- connected support: min_largest_component_fraction={float(row['selected_min_largest_component_fraction']):.6f}, max_component_count={int(row['selected_max_component_count'])}",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_mechanism_validation(
    seeds: list[int],
    base_size: int = 128,
    sizes: list[int] | None = None,
    schedule_shifts: list[float] | None = None,
    perturbation_strength: float = 0.03,
    refinement_levels: int = 5,
    n_per_family: int = 3,
    output_dir: str | Path = OUTPUT_DIR,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    sizes = [64, 128, 256] if sizes is None else [int(value) for value in sizes]
    schedule_shifts = [0.5, 1.2] if schedule_shifts is None else [float(value) for value in schedule_shifts]
    summary_rows: list[dict[str, object]] = []
    selected_rows: list[dict[str, object]] = []
    trace_rows: list[dict[str, object]] = []
    for variant in _variant_suite(base_size, sizes, schedule_shifts, perturbation_strength):
        case_rows = [
            _run_seed_case(
                seed=int(seed),
                size=int(variant["size"]),
                refinement_levels=refinement_levels,
                schedule_shift=float(variant["schedule_shift"]),
                perturbation=bool(variant["perturbation"]),
                perturbation_strength=float(variant["perturbation_strength"]),
            )
            for seed in seeds
        ]
        families = [row for row in case_rows if int(row["break_level"]) in (2, 3)]
        break_2 = [row for row in families if int(row["break_level"]) == 2]
        break_3 = [row for row in families if int(row["break_level"]) == 3]
        if not break_2 or not break_3:
            summary_rows.append(
                {
                    "variant": str(variant["variant"]),
                    "size": int(variant["size"]),
                    "schedule_shift": float(variant["schedule_shift"]),
                    "perturbation": int(bool(variant["perturbation"])),
                    "perturbation_strength": float(variant["perturbation_strength"]),
                    "n_break_2": int(len(break_2)),
                    "n_break_3": int(len(break_3)),
                    "threshold": float("nan"),
                    "transition_low_seed": -1,
                    "transition_high_seed": -1,
                    "break_2_mean_delta_persistence_1_to_2": float("nan"),
                    "break_3_mean_delta_persistence_1_to_2": float("nan"),
                    "break_2_mean_delta_recovery_1_to_2": float("nan"),
                    "break_3_mean_delta_recovery_1_to_2": float("nan"),
                    "selected_min_largest_component_fraction": float("nan"),
                    "selected_max_component_count": -1,
                    "selected_seeds": "",
                    "mechanism_holds": 0,
                }
            )
            continue
        band = _transition_band(families, "delta_persistence_1_to_2")
        selected = _select_boundary_seeds(families, float(band["threshold"]), n_per_family)
        for row in selected:
            selected_rows.append(
                {
                    "variant": str(variant["variant"]),
                    "size": int(variant["size"]),
                    "schedule_shift": float(variant["schedule_shift"]),
                    "perturbation": int(bool(variant["perturbation"])),
                    "perturbation_strength": float(variant["perturbation_strength"]),
                    **row,
                }
            )
        variant_traces = _trace_rows(variant, selected, refinement_levels)
        trace_rows.extend(variant_traces)
        summary_rows.append(_summarize_variant(variant, families, selected, variant_traces, band))
    output_root = Path(output_dir)
    _write_csv(output_root / "mechanism_validation_summary.csv", summary_rows, SUMMARY_FIELDS)
    _write_csv(output_root / "mechanism_validation_selected.csv", selected_rows, SELECTED_FIELDS)
    _write_csv(output_root / "mechanism_validation_traces.csv", trace_rows, TRACE_FIELDS)
    _plot_variant_gaps(output_root / "mechanism_validation_gaps.png", summary_rows)
    _write_note(output_root / "mechanism_validation.md", summary_rows)
    return summary_rows, selected_rows, trace_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the HAOS Genesis non-fragmentation consolidation mechanism across size and schedule variants.")
    parser.add_argument("--seed-start", type=int, default=20)
    parser.add_argument("--seed-stop", type=int, default=50)
    parser.add_argument("--base-size", type=int, default=128)
    parser.add_argument("--sizes", type=int, nargs="*", default=[64, 128, 256])
    parser.add_argument("--schedule-shifts", type=float, nargs="*", default=[0.5, 1.2])
    parser.add_argument("--perturbation-strength", type=float, default=0.03)
    parser.add_argument("--refinement-levels", type=int, default=5)
    parser.add_argument("--n-per-family", type=int, default=3)
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    args = parser.parse_args()
    seeds = list(range(int(args.seed_start), int(args.seed_stop) + 1))
    summary_rows, _, _ = build_mechanism_validation(
        seeds=seeds,
        base_size=int(args.base_size),
        sizes=[int(value) for value in args.sizes],
        schedule_shifts=[float(value) for value in args.schedule_shifts],
        perturbation_strength=float(args.perturbation_strength),
        refinement_levels=int(args.refinement_levels),
        n_per_family=int(args.n_per_family),
        output_dir=str(args.output_dir),
    )
    for row in summary_rows:
        print(
            f"{row['variant']}: break_2={row['n_break_2']} break_3={row['n_break_3']} "
            f"threshold={row['threshold']:.6f} mechanism_holds={row['mechanism_holds']} "
            f"dp_gap={float(row['break_2_mean_delta_persistence_1_to_2']) - float(row['break_3_mean_delta_persistence_1_to_2']):.6f} "
            f"dr_gap={float(row['break_2_mean_delta_recovery_1_to_2']) - float(row['break_3_mean_delta_recovery_1_to_2']):.6f}"
        )


if __name__ == "__main__":
    main()
