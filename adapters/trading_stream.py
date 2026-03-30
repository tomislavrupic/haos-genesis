from __future__ import annotations

import math
from pathlib import Path
from typing import Iterator

import numpy as np

try:
    from ..api import HAOSSensor
except ImportError:  # pragma: no cover - direct script execution
    import sys

    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT.parent) not in sys.path:
        sys.path.insert(0, str(ROOT.parent))
    from haos_genesis.api import HAOSSensor


class TradingStreamAdapter:
    def __init__(self, window_size: int = 50, symbol: str = "BTCUSDT"):
        self.window_size = int(window_size)
        if self.window_size < 1:
            raise ValueError("window_size must be positive")
        self.symbol = str(symbol)
        self.sensor = HAOSSensor(window_size=self.window_size)
        self.buffer: list[dict[str, float | int]] = []
        self._bucket_size = 4
        self._bucket_fill = 0

    def _start_candle(self, tick: dict) -> None:
        price = float(tick["price"])
        volume = float(tick.get("volume", 0.0))
        self.buffer.append(
            {
                "timestamp": int(tick["timestamp"]),
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
            }
        )
        self._bucket_fill = 1
        if len(self.buffer) > self.window_size:
            self.buffer = self.buffer[-self.window_size :]

    def _update_candle(self, tick: dict) -> None:
        price = float(tick["price"])
        volume = float(tick.get("volume", 0.0))
        candle = self.buffer[-1]
        candle.update(
            {
                "timestamp": int(tick["timestamp"]),
                "high": max(float(candle["high"]), price),
                "low": min(float(candle["low"]), price),
                "close": price,
                "volume": float(candle["volume"]) + volume,
            }
        )

    def _append_tick(self, tick: dict) -> None:
        if not self.buffer or self._bucket_fill >= self._bucket_size:
            self._start_candle(tick)
            return
        self._update_candle(tick)
        self._bucket_fill += 1

    def _node_features(self) -> np.ndarray:
        candles = self.buffer
        if not candles:
            return np.zeros((0, 4), dtype=float)
        features = np.zeros((len(candles), 4), dtype=float)
        closes = [float(candle["close"]) for candle in candles]
        for index, candle in enumerate(candles):
            previous_close = closes[index - 1] if index > 0 else closes[index]
            features[index] = [
                float(candle["close"]) - previous_close,
                float(candle["high"]) - float(candle["low"]),
                float(candle["close"]) - float(candle["open"]),
                float(candle["volume"]),
            ]
        mean = features.mean(axis=0, keepdims=True)
        std = features.std(axis=0, keepdims=True)
        return (features - mean) / (std + 1.0e-8)

    def build_graph_from_window(self) -> dict:
        nodes = list(range(len(self.buffer)))
        if not nodes:
            return {"nodes": [], "edges": []}

        features = self._node_features()
        tau = 1.0
        adjacency_floor = 0.3
        edge_weights: dict[tuple[int, int], float] = {}
        for left in range(len(nodes)):
            for right in range(left + 1, len(nodes)):
                distance = float(np.linalg.norm(features[left] - features[right]))
                weight = math.exp(-((distance ** 2) / tau))
                edge_weights[(left, right)] = float(weight)
        for left in range(len(nodes) - 1):
            key = (left, left + 1)
            edge_weights[key] = max(edge_weights.get(key, 0.0), adjacency_floor)

        return {
            "nodes": nodes,
            "edges": [(left, right, weight) for (left, right), weight in sorted(edge_weights.items())],
            "seed": 42,
            "refinement_levels": 5,
        }

    def update(self, tick: dict) -> dict:
        self._append_tick(tick)
        graph = self.build_graph_from_window()
        return self.sensor.update(graph)


def mock_price_stream(length: int = 120, start_price: float = 100.0) -> Iterator[dict[str, float | int]]:
    price = float(start_price)
    for step in range(int(length)):
        shock = 0.06 * ((step % 5) - 2)
        if step and step % 29 == 0:
            shock -= 1.8
        price = max(1.0, price + shock)
        volume = 1.0 + 0.12 * (step % 4)
        yield {
            "timestamp": step,
            "price": float(price),
            "volume": float(volume),
        }


def run_stream(stream) -> None:
    adapter = TradingStreamAdapter()
    for tick in stream:
        print(adapter.update(tick))


if __name__ == "__main__":
    adapter = TradingStreamAdapter()

    for tick in mock_price_stream():
        result = adapter.update(tick)
        print(result)
