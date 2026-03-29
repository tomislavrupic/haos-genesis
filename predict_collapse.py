from __future__ import annotations

import argparse
import csv
import os
import random
from pathlib import Path
import sys

PACKAGE_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(PACKAGE_DIR / "output" / ".mpl"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from haos_genesis.compare_seed_families import build_seed_family_comparison
from haos_genesis.paths import OUTPUT_DIR


FEATURES = ("delta_persistence_1_to_2", "L2_persistence_score")


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _load_feature_rows(features_csv: str | None, collapse_map: str, strength_label: str, size: int, refinement_levels: int, output_dir: str) -> list[dict[str, object]]:
    if features_csv is None:
        rows, _ = build_seed_family_comparison(collapse_map, strength_label, size, refinement_levels, output_dir)
        return rows
    return [
        {
            **row,
            "seed": int(row["seed"]),
            "break_level": int(row["break_level"]),
            **{key: float(value) for key, value in row.items() if key not in {"seed", "family", "break_level", "strength_label"}},
        }
        for row in _read_rows(Path(features_csv))
    ]


def _stratified_split(rows: list[dict[str, object]], test_fraction: float, split_seed: int) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    rng = random.Random(int(split_seed))
    train: list[dict[str, object]] = []
    test: list[dict[str, object]] = []
    for family in ("break_2", "break_3"):
        items = [row for row in rows if row["family"] == family]
        rng.shuffle(items)
        n_test = max(1, round(len(items) * float(test_fraction)))
        test.extend(items[:n_test])
        train.extend(items[n_test:])
    return train, test


def _fit_threshold(train_rows: list[dict[str, object]], feature: str) -> tuple[str, float, float]:
    values = sorted({float(row[feature]) for row in train_rows})
    candidates = [values[0] - 1.0e-9]
    candidates.extend((left + right) / 2.0 for left, right in zip(values, values[1:]))
    candidates.append(values[-1] + 1.0e-9)
    best: tuple[float, str, float] | None = None
    for direction in ("<=", ">="):
        for threshold in candidates:
            accuracy = sum(_predict_break_level(float(row[feature]), direction, threshold) == int(row["break_level"]) for row in train_rows) / max(len(train_rows), 1)
            candidate = (float(accuracy), direction, float(threshold))
            if best is None or candidate > best:
                best = candidate
    assert best is not None
    return best[1], best[2], best[0]


def _predict_break_level(value: float, direction: str, threshold: float) -> int:
    condition = value <= threshold if direction == "<=" else value >= threshold
    return 2 if condition else 3


def _accuracy(rows: list[dict[str, object]], feature: str, direction: str, threshold: float) -> float:
    if not rows:
        return 0.0
    correct = sum(_predict_break_level(float(row[feature]), direction, threshold) == int(row["break_level"]) for row in rows)
    return float(correct / len(rows))


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
    assert best_pair is not None
    left, right = best_pair
    return {
        "transition_low_value": left[0],
        "transition_low_break": left[1],
        "transition_low_seed": left[2],
        "transition_high_value": right[0],
        "transition_high_break": right[1],
        "transition_high_seed": right[2],
        "transition_midpoint": (left[0] + right[0]) / 2.0,
    }


def _prediction_rows(train_rows: list[dict[str, object]], test_rows: list[dict[str, object]], feature: str, direction: str, threshold: float) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for split_name, items in (("train", train_rows), ("test", test_rows)):
        for row in items:
            predicted = _predict_break_level(float(row[feature]), direction, threshold)
            rows.append(
                {
                    "feature": feature,
                    "split": split_name,
                    "seed": int(row["seed"]),
                    "actual_break_level": int(row["break_level"]),
                    "predicted_break_level": predicted,
                    "correct": int(predicted == int(row["break_level"])),
                    "value": float(row[feature]),
                }
            )
    return rows


def _plot_feature_threshold(path: Path, rows: list[dict[str, object]], feature: str, direction: str, threshold: float) -> None:
    ordered = sorted(rows, key=lambda row: float(row[feature]))
    x_values = list(range(len(ordered)))
    y_values = [float(row[feature]) for row in ordered]
    colors = ["#b45309" if row["family"] == "break_2" else "#0f766e" for row in ordered]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.scatter(x_values, y_values, c=colors, s=42)
    ax.axhline(threshold, color="#1f2937", linestyle="--", linewidth=1.2, label=f"threshold {direction} {threshold:.6f}")
    ax.set_xlabel("ordered seeds")
    ax.set_ylabel(feature)
    ax.set_title(f"{feature} Threshold Predictor")
    ax.legend()
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def build_predictor_report(
    collapse_map: str,
    features_csv: str | None = None,
    strength_label: str = "off",
    size: int = 128,
    refinement_levels: int = 5,
    output_dir: str | Path = OUTPUT_DIR,
    split_seed: int = 17,
    test_fraction: float = 0.25,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    feature_rows = _load_feature_rows(features_csv, collapse_map, strength_label, size, refinement_levels, output_dir)
    train_rows, test_rows = _stratified_split(feature_rows, test_fraction, split_seed)
    summary_rows: list[dict[str, object]] = []
    prediction_rows: list[dict[str, object]] = []
    output_root = Path(output_dir)
    for feature in FEATURES:
        direction, threshold, train_accuracy = _fit_threshold(train_rows, feature)
        test_accuracy = _accuracy(test_rows, feature, direction, threshold)
        band = _transition_band(feature_rows, feature)
        summary = {
            "feature": feature,
            "direction": direction,
            "threshold": threshold,
            "train_accuracy": train_accuracy,
            "test_accuracy": test_accuracy,
            "n_train": len(train_rows),
            "n_test": len(test_rows),
            "split_seed": int(split_seed),
            "test_fraction": float(test_fraction),
            **band,
        }
        summary_rows.append(summary)
        prediction_rows.extend(_prediction_rows(train_rows, test_rows, feature, direction, threshold))
        _plot_feature_threshold(output_root / f"predictor_{strength_label.replace('.', 'p')}_{feature}.png", feature_rows, feature, direction, threshold)
    _write_csv(output_root / f"predictor_{strength_label.replace('.', 'p')}_summary.csv", summary_rows, list(summary_rows[0].keys()))
    _write_csv(output_root / f"predictor_{strength_label.replace('.', 'p')}_predictions.csv", prediction_rows, list(prediction_rows[0].keys()))
    return summary_rows, prediction_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Fit a minimal threshold predictor for HAOS Genesis collapse families.")
    parser.add_argument("--collapse-map", default=str(OUTPUT_DIR / "collapse_map.csv"))
    parser.add_argument("--features-csv")
    parser.add_argument("--strength-label", default="off")
    parser.add_argument("--size", type=int, default=128)
    parser.add_argument("--refinement-levels", type=int, default=5)
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--split-seed", type=int, default=17)
    parser.add_argument("--test-fraction", type=float, default=0.25)
    args = parser.parse_args()
    try:
        summary_rows, _ = build_predictor_report(
            collapse_map=str(args.collapse_map),
            features_csv=args.features_csv,
            strength_label=str(args.strength_label),
            size=int(args.size),
            refinement_levels=int(args.refinement_levels),
            output_dir=str(args.output_dir),
            split_seed=int(args.split_seed),
            test_fraction=float(args.test_fraction),
        )
    except ValueError as exc:
        parser.error(str(exc))
    for row in summary_rows:
        print(
            f"{row['feature']}: threshold={row['direction']} {row['threshold']:.6f} "
            f"train_accuracy={row['train_accuracy']:.6f} test_accuracy={row['test_accuracy']:.6f} "
            f"transition_midpoint={row['transition_midpoint']:.6f}"
        )


if __name__ == "__main__":
    main()
