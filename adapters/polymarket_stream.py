from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np

try:
    from ..api import HAOSSensor
except ImportError:  # pragma: no cover - direct script execution
    import sys

    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT.parent) not in sys.path:
        sys.path.insert(0, str(ROOT.parent))
    from haos_genesis.api import HAOSSensor


class PolymarketAdapter:
    def __init__(self, window_size: int = 50, market_id: str = ""):
        self.window_size = int(window_size)
        if self.window_size < 1:
            raise ValueError("window_size must be positive")
        self.market_id = str(market_id)
        self.sensor = HAOSSensor(window_size=self.window_size)
        self.buffer: list[dict[str, float | int]] = []
        self.alpha = 0.5
        self.time_tau = 4.0

    def _coerce_point(self, point: dict[str, Any]) -> dict[str, float | int]:
        timestamp = point["timestamp"] if "timestamp" in point else point["t"]
        price = point["price"] if "price" in point else point["p"]
        return {"timestamp": int(timestamp), "price": float(price)}

    def _append_point(self, point: dict[str, float | int]) -> None:
        self.buffer.append(point)
        if len(self.buffer) > self.window_size:
            self.buffer = self.buffer[-self.window_size :]

    def _feature_matrix(self) -> np.ndarray:
        prices = np.asarray([float(point["price"]) for point in self.buffer], dtype=float)
        if prices.size == 0:
            return np.zeros((0, 4), dtype=float)
        returns = np.zeros_like(prices)
        returns[1:] = prices[1:] - prices[:-1]
        velocity = np.zeros_like(prices)
        velocity[1:] = returns[1:] - returns[:-1]
        local_vol = np.zeros_like(prices)
        for index in range(prices.size):
            start = max(0, index - 4)
            local_vol[index] = float(np.std(prices[start : index + 1]))
        features = np.column_stack([prices, returns, velocity, local_vol])
        mean = features.mean(axis=0, keepdims=True)
        std = features.std(axis=0, keepdims=True)
        return (features - mean) / (std + 1.0e-8)

    def build_graph_from_window(self) -> dict[str, Any]:
        size = len(self.buffer)
        if size == 0:
            return {"nodes": [], "edges": []}
        features = self._feature_matrix()
        affinity = np.zeros((size, size), dtype=float)
        for left in range(size):
            for right in range(left + 1, size):
                w_time = math.exp(-abs(left - right) / self.time_tau)
                dist = float(np.linalg.norm(features[left] - features[right]))
                w_feat = math.exp(-dist)
                weight = self.alpha * w_time + (1.0 - self.alpha) * w_feat
                affinity[left, right] = weight
                affinity[right, left] = weight
        np.fill_diagonal(affinity, 0.0)
        affinity = affinity / max(float(np.max(affinity)), 1.0e-12)
        affinity = affinity / (affinity.sum(axis=1, keepdims=True) + 1.0e-12)
        affinity = 0.5 * (affinity + affinity.T)
        np.fill_diagonal(affinity, 0.0)
        edges = [
            (left, right, float(affinity[left, right]))
            for left in range(size)
            for right in range(left + 1, size)
            if affinity[left, right] > 0.0
        ]
        return {
            "nodes": list(range(size)),
            "edges": edges,
            "seed": 42,
            "refinement_levels": 5,
        }

    def update(self, point: dict[str, Any]) -> dict[str, Any]:
        coerced = self._coerce_point(point)
        self._append_point(coerced)
        result = self.sensor.update(self.build_graph_from_window())
        if result.get("state") == "invalid":
            return {
                "timestamp": int(coerced["timestamp"]),
                "price": float(coerced["price"]),
                "state": "invalid",
                "reason": str(result["reason"]),
            }
        return {
            "timestamp": int(coerced["timestamp"]),
            "price": float(coerced["price"]),
            "k_star": int(result["k_star"]),
            "predicted_break": int(result["predicted_break"]),
            "safety_margin": float(result["safety_margin"]),
            "min_delta": float(result["min_delta"]),
            "confidence": float(result["confidence"]),
        }


def fetch_price_history(
    market_id: str,
    interval: str = "1m",
    limit: int = 500,
    start_ts: int | None = None,
    end_ts: int | None = None,
) -> list[dict[str, float | int]]:
    import requests

    params: dict[str, Any] = {"market": market_id, "interval": interval, "limit": int(limit)}
    if start_ts is not None:
        params["startTs"] = int(start_ts)
    if end_ts is not None:
        params["endTs"] = int(end_ts)
    response = requests.get("https://clob.polymarket.com/prices-history", params=params, timeout=30)
    response.raise_for_status()
    history = response.json().get("history", [])
    return [{"t": int(item["t"]), "p": float(item["p"])} for item in sorted(history, key=lambda item: int(item["t"]))]


def run_stream(history, window_size: int = 50, market_id: str = "") -> list[dict[str, Any]]:
    adapter = PolymarketAdapter(window_size=window_size, market_id=market_id)
    outputs = []
    for point in history:
        result = adapter.update(point)
        if result.get("state") == "invalid":
            continue
        outputs.append(result)
    return outputs
