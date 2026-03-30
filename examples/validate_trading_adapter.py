from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "output" / ".mpl"))

from haos_genesis.adapters.trading_stream import TradingStreamAdapter


def _tick(timestamp: int, price: float, volume: float) -> dict[str, float | int]:
    return {"timestamp": int(timestamp), "price": float(price), "volume": float(volume)}


def trend_stream(length: int = 96):
    price = 100.0
    for step in range(length):
        price += 0.14 + 0.02 * ((step % 4) - 1.5)
        yield _tick(step, price, 1.0 + 0.03 * (step % 5))


def range_stream(length: int = 96):
    price = 100.0
    center = 100.0
    for step in range(length):
        price += -0.42 * (price - center) + (0.45 if step % 2 == 0 else -0.45) + 0.08 * ((step % 3) - 1)
        yield _tick(step, price, 1.25 + 0.06 * (step % 4))


def shock_stream(length: int = 96):
    price = 100.0
    for step in range(length):
        if step < 48:
            price += 0.02 * ((step % 4) - 1.5)
        elif step == 48:
            price -= 9.0
        else:
            price += (0.62 if step % 2 == 0 else -0.62) + 0.16 * ((step % 3) - 1)
        volume = 1.1 + 0.04 * (step % 4)
        if step >= 48:
            volume += 0.9
        yield _tick(step, price, volume)


def _signature(result: dict) -> tuple[str, int, float, float]:
    return (
        str(result["state"]),
        int(result["k_star"]),
        round(float(result["safety_margin"]), 6),
        round(float(result["confidence"]), 6),
    )


def _run_regime(name: str, stream) -> dict:
    adapter = TradingStreamAdapter(window_size=24, symbol=name)
    outputs = [adapter.update(tick) for tick in stream]
    valid = [item for item in outputs if item.get("state") != "invalid"]
    if not valid:
        raise ValueError(f"{name} produced no valid outputs")
    final = valid[-1]
    return {
        "name": name,
        "state": str(final["state"]),
        "k_star": int(final["k_star"]),
        "safety_margin": round(float(final["safety_margin"]), 6),
        "confidence": round(float(final["confidence"]), 6),
    }


def _run_once() -> list[dict]:
    return [
        _run_regime("trend", trend_stream()),
        _run_regime("range", range_stream()),
        _run_regime("shock", shock_stream()),
    ]


def main() -> None:
    first = _run_once()
    second = _run_once()
    if first != second:
        raise SystemExit("VALIDATION FAILURE: repeated runs are not identical")

    trend, range_case, shock = first
    if _signature(range_case) == _signature(trend):
        raise SystemExit("VALIDATION FAILURE: range matches trend")
    if _signature(shock) == _signature(trend):
        raise SystemExit("VALIDATION FAILURE: shock matches trend")

    for result in first:
        print(f"REGIME: {result['name']}")
        print(f"state={result['state']}")
        print(f"k_star={result['k_star']}")
        print(f"safety_margin={result['safety_margin']}")
        print(f"confidence={result['confidence']}")
        print()


if __name__ == "__main__":
    main()
