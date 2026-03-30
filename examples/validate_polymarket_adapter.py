from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from haos_genesis.adapters.polymarket_stream import PolymarketAdapter


def _point(timestamp: int, price: float) -> dict[str, float | int]:
    return {"t": int(timestamp), "p": float(price)}


def stable_history(length: int = 96) -> list[dict[str, float | int]]:
    return [_point(step, 0.6) for step in range(length)]


def drift_history(length: int = 96) -> list[dict[str, float | int]]:
    history = []
    for step in range(length):
        price = 0.6 + 0.0012 * step
        history.append(_point(step, min(price, 0.7)))
    return history


def shock_history(length: int = 96) -> list[dict[str, float | int]]:
    history = []
    for step in range(length):
        if step < max(length - 4, 0):
            price = 0.6
        elif step == max(length - 4, 0):
            price = 0.82
        else:
            offset = step - max(length - 4, 0)
            price = 0.82 + (0.03 if offset % 2 == 0 else -0.03)
        history.append(_point(step, price))
    return history


def _signature(result: dict[str, object]) -> tuple[int, float, float]:
    return (
        int(result["k_star"]),
        round(float(result["safety_margin"]), 6),
        round(float(result["confidence"]), 6),
    )


def _run_regime(name: str, history: list[dict[str, float | int]]) -> dict[str, object]:
    adapter = PolymarketAdapter(window_size=24, market_id=name)
    outputs = [adapter.update(point) for point in history]
    valid = [item for item in outputs if item.get("state") != "invalid"]
    if not valid:
        raise SystemExit(f"VALIDATION FAILURE: {name} produced no valid outputs")
    final = valid[-1]
    return {
        "regime": name,
        "k_star": int(final["k_star"]),
        "safety_margin": round(float(final["safety_margin"]), 6),
        "confidence": round(float(final["confidence"]), 6),
    }


def _run_once() -> list[dict[str, object]]:
    return [
        _run_regime("stable", stable_history()),
        _run_regime("drift", drift_history()),
        _run_regime("shock", shock_history()),
    ]


def main() -> None:
    first = _run_once()
    second = _run_once()
    if first != second:
        raise SystemExit("VALIDATION FAILURE: repeated runs are not identical")

    stable_case, drift_case, shock_case = first
    if _signature(drift_case) == _signature(stable_case):
        raise SystemExit("VALIDATION FAILURE: drift matches stable")
    if _signature(shock_case) == _signature(stable_case):
        raise SystemExit("VALIDATION FAILURE: shock matches stable")

    shock_margin = float(shock_case["safety_margin"])
    stable_margin = float(stable_case["safety_margin"])
    shock_confidence = float(shock_case["confidence"])
    stable_confidence = float(stable_case["confidence"])
    if not (shock_margin < stable_margin or shock_confidence > stable_confidence):
        raise SystemExit("VALIDATION FAILURE: shock is not more stressed than stable")

    for result in first:
        print(f"regime: {result['regime']}")
        print(f"k_star: {result['k_star']}")
        print(f"safety_margin: {result['safety_margin']}")
        print(f"confidence: {result['confidence']}")
        print()


if __name__ == "__main__":
    main()
