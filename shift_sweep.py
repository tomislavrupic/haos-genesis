from __future__ import annotations

import argparse
import csv
from collections import Counter
import json
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
    "shift",
    "size",
    "perturbation",
    "perturbation_strength",
    "n_runs",
    "n_break_2",
    "n_break_3",
    "n_other",
    "dominant_break_level",
    "split_exists",
    "split_collapsed",
    "threshold",
    "transition_low_seed",
    "transition_high_seed",
    "connected_support_holds",
    "selected_min_largest_component_fraction",
    "selected_max_component_count",
    "break_2_mean_delta_persistence_1_to_2",
    "break_3_mean_delta_persistence_1_to_2",
    "break_2_mean_delta_recovery_1_to_2",
    "break_3_mean_delta_recovery_1_to_2",
    "k_star_mode",
    "k_star_mean",
    "k_star_counts",
    "selected_seeds",
]
COUNT_FIELDS = ["shift", "break_level", "count"]
KSTAR_COUNT_FIELDS = ["shift", "k_star", "count"]
RUN_FIELDS = ["shift", "seed", "break_level", "k_star", "min_delta_persistence", "delta_persistence_1_to_2", "delta_recovery_1_to_2"]


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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
        "k_star": int(k_data["k_star"]),
        "min_delta_persistence": float(k_data["min_delta"]),
        "break_level": int(trace[break_index]["level"]),
        "delta_persistence_1_to_2": float(metrics[2]["persistence_score"] - metrics[1]["persistence_score"]),
        "delta_recovery_1_to_2": float(metrics[2]["recovery_score"] - metrics[1]["recovery_score"]),
    }


def _k_star_summary(rows: list[dict[str, object]]) -> tuple[int, float, str, list[dict[str, object]]]:
    counts = Counter(int(row["k_star"]) for row in rows)
    mode = min(value for value, count in counts.items() if count == max(counts.values()))
    mean = float(np.mean([int(row["k_star"]) for row in rows])) if rows else float("nan")
    counts_json = json.dumps({str(key): int(counts[key]) for key in sorted(counts)})
    count_rows = [{"k_star": int(key), "count": int(counts[key])} for key in sorted(counts)]
    return int(mode), float(mean), counts_json, count_rows


def _transition_band(rows: list[dict[str, object]]) -> dict[str, object]:
    ordered = sorted((float(row["delta_persistence_1_to_2"]), int(row["break_level"]), int(row["seed"])) for row in rows)
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
                    "break_level": int(row["break_level"]),
                    "distance_to_threshold": abs(float(row["delta_persistence_1_to_2"]) - threshold),
                }
            )
    return sorted(selected, key=lambda row: (int(row["break_level"]), float(row["distance_to_threshold"]), int(row["seed"])))


def _connected_support(selected: list[dict[str, object]], size: int, refinement_levels: int, schedule_shift: float, perturbation: bool, perturbation_strength: float) -> tuple[float, int]:
    min_fraction = 1.0
    max_components = 1
    for row in selected:
        trace, _ = generate_universe(
            seed=int(row["seed"]),
            size=size,
            refinement_levels=refinement_levels,
            perturbation=perturbation,
            perturbation_strength=perturbation_strength,
            schedule_shift=schedule_shift,
        )
        for entry in trace:
            if int(entry["level"]) not in TRACE_LEVELS:
                continue
            min_fraction = min(min_fraction, float(entry["metrics"]["largest_component_fraction"]))
            max_components = max(max_components, len(connected_components(entry["graph"].affinity > 0.0)))
    return float(min_fraction), int(max_components)


def _empty_summary(
    shift: float,
    size: int,
    perturbation: bool,
    perturbation_strength: float,
    n_runs: int,
    dominant_break_level: int,
    n_break_2: int,
    n_break_3: int,
    k_star_mode: int,
    k_star_mean: float,
    k_star_counts: str,
) -> dict[str, object]:
    return {
        "shift": float(shift),
        "size": int(size),
        "perturbation": int(bool(perturbation)),
        "perturbation_strength": float(perturbation_strength),
        "n_runs": int(n_runs),
        "n_break_2": int(n_break_2),
        "n_break_3": int(n_break_3),
        "n_other": int(n_runs - n_break_2 - n_break_3),
        "dominant_break_level": int(dominant_break_level),
        "split_exists": 0,
        "split_collapsed": 1,
        "threshold": float("nan"),
        "transition_low_seed": -1,
        "transition_high_seed": -1,
        "connected_support_holds": 0,
        "selected_min_largest_component_fraction": float("nan"),
        "selected_max_component_count": -1,
        "break_2_mean_delta_persistence_1_to_2": float("nan"),
        "break_3_mean_delta_persistence_1_to_2": float("nan"),
        "break_2_mean_delta_recovery_1_to_2": float("nan"),
        "break_3_mean_delta_recovery_1_to_2": float("nan"),
        "k_star_mode": int(k_star_mode),
        "k_star_mean": float(k_star_mean),
        "k_star_counts": str(k_star_counts),
        "selected_seeds": "",
    }


def _summarize_shift(
    shift: float,
    case_rows: list[dict[str, object]],
    size: int,
    refinement_levels: int,
    perturbation: bool,
    perturbation_strength: float,
    n_per_family: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    counts = Counter(int(row["break_level"]) for row in case_rows)
    k_star_mode, k_star_mean, k_star_counts, k_star_count_rows = _k_star_summary(case_rows)
    dominant_break_level = min(level for level, count in counts.items() if count == max(counts.values()))
    n_break_2 = int(counts.get(2, 0))
    n_break_3 = int(counts.get(3, 0))
    families = [row for row in case_rows if int(row["break_level"]) in (2, 3)]
    if not n_break_2 or not n_break_3:
        return _empty_summary(
            shift,
            size,
            perturbation,
            perturbation_strength,
            len(case_rows),
            dominant_break_level,
            n_break_2,
            n_break_3,
            k_star_mode,
            k_star_mean,
            k_star_counts,
        ), [
            {"shift": float(shift), "break_level": int(level), "count": int(count)} for level, count in sorted(counts.items())
        ], [{"shift": float(shift), **row} for row in k_star_count_rows]
    band = _transition_band(families)
    selected = _select_boundary_seeds(families, float(band["threshold"]), n_per_family)
    min_fraction, max_components = _connected_support(selected, size, refinement_levels, shift, perturbation, perturbation_strength)
    break_2_rows = [row for row in families if int(row["break_level"]) == 2]
    break_3_rows = [row for row in families if int(row["break_level"]) == 3]
    summary = {
        "shift": float(shift),
        "size": int(size),
        "perturbation": int(bool(perturbation)),
        "perturbation_strength": float(perturbation_strength),
        "n_runs": int(len(case_rows)),
        "n_break_2": int(n_break_2),
        "n_break_3": int(n_break_3),
        "n_other": int(len(case_rows) - n_break_2 - n_break_3),
        "dominant_break_level": int(dominant_break_level),
        "split_exists": 1,
        "split_collapsed": 0,
        "threshold": float(band["threshold"]),
        "transition_low_seed": int(band["transition_low_seed"]),
        "transition_high_seed": int(band["transition_high_seed"]),
        "connected_support_holds": int(min_fraction >= 0.999999 and max_components == 1),
        "selected_min_largest_component_fraction": float(min_fraction),
        "selected_max_component_count": int(max_components),
        "break_2_mean_delta_persistence_1_to_2": float(np.mean([float(row["delta_persistence_1_to_2"]) for row in break_2_rows])),
        "break_3_mean_delta_persistence_1_to_2": float(np.mean([float(row["delta_persistence_1_to_2"]) for row in break_3_rows])),
        "break_2_mean_delta_recovery_1_to_2": float(np.mean([float(row["delta_recovery_1_to_2"]) for row in break_2_rows])),
        "break_3_mean_delta_recovery_1_to_2": float(np.mean([float(row["delta_recovery_1_to_2"]) for row in break_3_rows])),
        "k_star_mode": int(k_star_mode),
        "k_star_mean": float(k_star_mean),
        "k_star_counts": str(k_star_counts),
        "selected_seeds": ",".join(str(int(row["seed"])) for row in selected),
    }
    count_rows = [{"shift": float(shift), "break_level": int(level), "count": int(count)} for level, count in sorted(counts.items())]
    return summary, count_rows, [{"shift": float(shift), **row} for row in k_star_count_rows]


def _plot_shift_control_map(path: Path, summary_rows: list[dict[str, object]]) -> None:
    shifts = [float(row["shift"]) for row in summary_rows]
    split_exists = [int(row["split_exists"]) for row in summary_rows]
    connected = [int(row["connected_support_holds"]) for row in summary_rows]
    threshold_values = [float(row["threshold"]) if int(row["split_exists"]) else np.nan for row in summary_rows]
    fig, axes = plt.subplots(5, 1, figsize=(11, 14), sharex=True)
    axes[0].plot(shifts, [int(row["n_break_2"]) for row in summary_rows], marker="o", label="break=2")
    axes[0].plot(shifts, [int(row["n_break_3"]) for row in summary_rows], marker="s", label="break=3")
    axes[0].plot(shifts, [int(row["n_other"]) for row in summary_rows], marker="^", label="other")
    axes[0].set_ylabel("seed count")
    axes[0].set_title("Family Balance vs Schedule Shift")
    axes[0].legend()
    axes[1].plot(shifts, [int(row["dominant_break_level"]) for row in summary_rows], marker="o", color="#1d4ed8")
    axes[1].set_ylabel("break level")
    axes[1].set_title("Dominant Break Level")
    axes[2].plot(shifts, threshold_values, marker="o", color="#0f766e")
    axes[2].set_ylabel("threshold")
    axes[2].set_title("Delta Persistence Threshold (when split exists)")
    axes[3].plot(shifts, [float(row["k_star_mean"]) for row in summary_rows], marker="o", color="#dc2626", label="k_star_mean")
    axes[3].plot(shifts, [int(row["k_star_mode"]) for row in summary_rows], marker="s", color="#7c2d12", label="k_star_mode")
    axes[3].set_ylabel("k_star")
    axes[3].set_title("Critical Transition Index vs Schedule Shift")
    axes[3].legend()
    axes[4].step(shifts, split_exists, where="mid", label="split exists", color="#7c3aed")
    axes[4].step(shifts, connected, where="mid", label="connected support", color="#b45309")
    axes[4].set_ylabel("flag")
    axes[4].set_xlabel("schedule shift")
    axes[4].set_yticks([0, 1])
    axes[4].set_title("Split and Connected-Support Status")
    axes[4].legend()
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_k_star_distribution(path: Path, count_rows: list[dict[str, object]], shifts: list[float]) -> None:
    k_values = sorted({int(row["k_star"]) for row in count_rows})
    bottoms = np.zeros(len(shifts), dtype=float)
    fig, ax = plt.subplots(figsize=(11, 4.5))
    for index, k_star in enumerate(k_values):
        counts = np.asarray(
            [
                next(
                    (int(row["count"]) for row in count_rows if float(row["shift"]) == float(shift) and int(row["k_star"]) == k_star),
                    0,
                )
                for shift in shifts
            ],
            dtype=float,
        )
        ax.bar(shifts, counts, bottom=bottoms, width=0.075, label=f"k_star={k_star}", color=plt.cm.cividis(index / max(len(k_values) - 1, 1)))
        bottoms += counts
    ax.set_xlabel("schedule shift")
    ax.set_ylabel("seed count")
    ax.set_title("k_star Distribution by Schedule Shift")
    ax.legend()
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def build_shift_sweep(
    seeds: list[int],
    shifts: list[float],
    size: int = 128,
    refinement_levels: int = 5,
    perturbation: bool = False,
    perturbation_strength: float = 0.0,
    n_per_family: int = 3,
    output_dir: str | Path = OUTPUT_DIR,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    summary_rows: list[dict[str, object]] = []
    count_rows: list[dict[str, object]] = []
    k_star_count_rows: list[dict[str, object]] = []
    run_rows: list[dict[str, object]] = []
    for shift in shifts:
        case_rows = [
            {"shift": float(shift), **_run_seed_case(int(seed), size, refinement_levels, float(shift), perturbation, perturbation_strength)}
            for seed in seeds
        ]
        summary, counts, k_counts = _summarize_shift(float(shift), case_rows, size, refinement_levels, perturbation, perturbation_strength, n_per_family)
        summary_rows.append(summary)
        count_rows.extend(counts)
        k_star_count_rows.extend(k_counts)
        run_rows.extend(case_rows)
    output_root = Path(output_dir)
    _write_csv(output_root / "shift_sweep_summary.csv", summary_rows, SUMMARY_FIELDS)
    _write_csv(output_root / "shift_sweep_runs.csv", run_rows, RUN_FIELDS)
    _write_csv(output_root / "shift_sweep_break_counts.csv", count_rows, COUNT_FIELDS)
    _write_csv(output_root / "shift_sweep_k_star_counts.csv", k_star_count_rows, KSTAR_COUNT_FIELDS)
    _plot_shift_control_map(output_root / "shift_sweep_control_map.png", summary_rows)
    _plot_k_star_distribution(output_root / "shift_sweep_k_star_distribution.png", k_star_count_rows, [float(value) for value in shifts])
    return summary_rows, count_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep schedule shift as a HAOS Genesis control parameter.")
    parser.add_argument("--seed-start", type=int, default=20)
    parser.add_argument("--seed-stop", type=int, default=50)
    parser.add_argument("--shifts", type=float, nargs="*", default=[round(0.1 * index, 1) for index in range(13)])
    parser.add_argument("--size", type=int, default=128)
    parser.add_argument("--refinement-levels", type=int, default=5)
    parser.add_argument("--perturbation", action="store_true")
    parser.add_argument("--perturbation-strength", type=float, default=0.0)
    parser.add_argument("--n-per-family", type=int, default=3)
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    args = parser.parse_args()
    seeds = list(range(int(args.seed_start), int(args.seed_stop) + 1))
    summary_rows, _ = build_shift_sweep(
        seeds=seeds,
        shifts=[float(value) for value in args.shifts],
        size=int(args.size),
        refinement_levels=int(args.refinement_levels),
        perturbation=bool(args.perturbation),
        perturbation_strength=float(args.perturbation_strength),
        n_per_family=int(args.n_per_family),
        output_dir=str(args.output_dir),
    )
    for row in summary_rows:
        print(
            f"shift={row['shift']:.1f} break_2={row['n_break_2']} break_3={row['n_break_3']} "
            f"dominant={row['dominant_break_level']} k_star_mode={row['k_star_mode']} "
            f"k_star_mean={float(row['k_star_mean']):.3f} split_exists={row['split_exists']} "
            f"threshold={row['threshold']:.6f} connected_support={row['connected_support_holds']}"
        )


if __name__ == "__main__":
    main()
