from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "haos_genesis" / "output" / ".mpl"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from haos_genesis.adapters.trading_stream import TradingStreamAdapter


def _load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise ValueError("CSV must contain timestamp,open,high,low,close,volume")
        return [dict(row) for row in reader]


def _pseudo_ticks(row: dict[str, str], base_index: int):
    open_price = float(row["open"])
    high_price = float(row["high"])
    low_price = float(row["low"])
    close_price = float(row["close"])
    volume = float(row["volume"]) / 4.0
    prices = [open_price, high_price, low_price, close_price]
    for offset, price in enumerate(prices):
        yield {
            "timestamp": int(base_index * 4 + offset),
            "price": float(price),
            "volume": float(volume),
        }


def _write_output_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "timestamp",
        "close",
        "state",
        "k_star",
        "predicted_break",
        "safety_margin",
        "min_delta",
        "confidence",
        "drift",
        "k_shift",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _plot_output(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    steps = np.arange(len(rows), dtype=float)
    closes = np.asarray([float(row["close"]) for row in rows], dtype=float)
    margins = np.asarray([float(row["safety_margin"]) for row in rows], dtype=float)
    critical_steps = [index for index, row in enumerate(rows) if row["state"] == "critical"]

    fig, (ax_price, ax_margin) = plt.subplots(2, 1, figsize=(10.0, 6.0), sharex=True)
    ax_price.plot(steps, closes, color="#0f172a", linewidth=1.2)
    ax_price.set_ylabel("close")
    ax_price.set_title("Real Market Stream: Price and Safety Margin")

    ax_margin.plot(steps, margins, color="#0f766e", linewidth=1.2)
    ax_margin.axhline(0.0, color="#64748b", linestyle="--", linewidth=0.9)
    ax_margin.set_xlabel("step")
    ax_margin.set_ylabel("safety_margin")

    for step in critical_steps:
        ax_price.axvline(step, color="#dc2626", alpha=0.08, linewidth=0.8)
        ax_margin.axvline(step, color="#dc2626", alpha=0.08, linewidth=0.8)

    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def run(csv_path: Path, window_size: int, output_dir: Path) -> None:
    rows = _load_rows(csv_path)
    adapter = TradingStreamAdapter(window_size=window_size)
    output_rows: list[dict[str, object]] = []

    for index, row in enumerate(rows):
        result = None
        for tick in _pseudo_ticks(row, index):
            result = adapter.update(tick)
        if result is None or result.get("state") == "invalid":
            continue
        output_rows.append(
            {
                "timestamp": row["timestamp"],
                "close": float(row["close"]),
                "state": str(result["state"]),
                "k_star": int(result["k_star"]),
                "predicted_break": int(result["predicted_break"]),
                "safety_margin": float(result["safety_margin"]),
                "min_delta": float(result["min_delta"]),
                "confidence": float(result["confidence"]),
                "drift": float(result["drift"]),
                "k_shift": int(result["k_shift"]),
            }
        )

    csv_output = output_dir / "real_market_sensor.csv"
    png_output = output_dir / "real_market_sensor.png"
    _write_output_csv(csv_output, output_rows)
    _plot_output(png_output, output_rows)

    margins = np.asarray([float(row["safety_margin"]) for row in output_rows], dtype=float)
    unique_k = sorted({int(row["k_star"]) for row in output_rows})
    print(f"rows_processed={len(output_rows)}")
    print(f"critical_count={sum(1 for row in output_rows if row['state'] == 'critical')}")
    print(f"warning_count={sum(1 for row in output_rows if row['state'] == 'warning')}")
    print(f"mean_safety_margin={float(margins.mean()) if margins.size else 0.0}")
    print(f"min_safety_margin={float(margins.min()) if margins.size else 0.0}")
    print(f"unique_k_star={','.join(str(value) for value in unique_k)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run HAOS sensor over historical OHLCV CSV data.")
    parser.add_argument("--csv", required=True, help="Path to CSV with timestamp,open,high,low,close,volume")
    parser.add_argument("--window-size", type=int, default=24, help="Rolling window size for the trading adapter")
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "haos_genesis" / "output"),
        help="Directory for real_market_sensor.csv and real_market_sensor.png",
    )
    args = parser.parse_args()

    run(
        csv_path=Path(args.csv).expanduser().resolve(),
        window_size=int(args.window_size),
        output_dir=Path(args.output_dir).expanduser().resolve(),
    )


if __name__ == "__main__":
    main()
