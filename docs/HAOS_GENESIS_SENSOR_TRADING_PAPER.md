# HAOS Genesis Sensor and Trading Adapter Paper: Continuous Stability Monitoring and Regime-Sensitive Market Representation

Author: Tomislav Rupic

Version: v0.1.0

## Abstract

HAOS Genesis originally operated as a one-shot persistence probe: a graph goes in, a trace is
generated, and collapse-related structure is measured. The new additions documented here extend
that capability in two practical directions without altering the frozen core. First, `HAOSSensor`
turns the existing API into a continuous stability monitor by composing successive calls to
`haos_stability_skill` over time and exposing only temporal differences in already existing
signals. Second, `TradingStreamAdapter` maps streaming market ticks into deterministic graph
representations so the same sensor can be applied to rolling market structure.

These additions remain deliberately narrow. They do not modify `generator.py`, `metrics.py`,
`compute_k_star`, or the underlying collapse logic. They do not predict price, emit trade
signals, or introduce new theory. Their only purpose is to expose structural degradation over
time under a fixed operational contract. In synthetic validation, the upgraded trading adapter
separates trend, range, and shock regimes deterministically. The separation is visible in
`k_star`, `safety_margin`, and `confidence`, even though all three regimes still land in the
coarse top-level label `critical`. This is enough to establish the adapter as a regime-sensitive
structural monitor, but not yet as a calibrated market-state classifier.

## 1. Scope

This paper documents two concrete additions:

1. `api/sensor.py`
2. `adapters/trading_stream.py`

The intention is practical rather than theoretical. The question is no longer only whether a
single graph trace is near collapse. The question becomes whether a sequence of externally
supplied graphs can be monitored over time with a stable machine contract.

## 2. HAOS Sensor

### 2.1 Purpose

`HAOSSensor` converts one-shot HAOS outputs into a rolling stability monitor. It does this by
preserving the existing signal and composing it temporally, not by inventing any new metric.

### 2.2 Update Contract

Each call to `update(graph)` performs four steps:

1. validate minimal structure
2. call `haos_stability_skill(graph)`
3. append the result to a bounded internal history
4. compute temporal differences against the previous valid state

The returned schema is:

```python
{
    "state": "stable" | "warning" | "critical",
    "k_star": int,
    "predicted_break": int,
    "safety_margin": float,
    "min_delta": float,
    "confidence": float,
    "drift": float,
    "k_shift": int,
}
```

### 2.3 Validity Guards

The sensor rejects structurally weak inputs before calling the HAOS skill. Invalid payloads
return:

```python
{
    "state": "invalid",
    "reason": "insufficient_structure",
}
```

This guard is applied when the graph is empty, has fewer than three nodes, or is disconnected.

### 2.4 Temporal Composition

The sensor exposes only two temporal differences:

1. `drift = current_safety_margin - previous_safety_margin`
2. `k_shift = current_k_star - previous_k_star`

If no previous valid output exists:

1. `drift = 0.0`
2. `k_shift = 0`

### 2.5 State Classification

The state label is intentionally crude and uses only `safety_margin`:

1. `critical` if `safety_margin < 0`
2. `warning` if `0 <= safety_margin < 0.05`
3. `stable` if `safety_margin >= 0.05`

This simplicity is a feature, not a bug. It prevents interpretation creep. More refined reading
is expected to come from `k_star`, `safety_margin`, and `confidence`, not from the label alone.

## 3. Trading Stream Adapter

### 3.1 Purpose

`TradingStreamAdapter` is a deterministic data adapter. It converts a rolling stream of market
ticks into candle-structured graphs that can be read by `HAOSSensor`.

The adapter answers one question only:

1. is the current market structure still holding?

It does not answer:

1. where price goes next
2. whether to buy or sell
3. whether a move is profitable

### 3.2 Tick Contract

The input stream uses the minimal payload:

```python
{
    "timestamp": int,
    "price": float,
    "volume": float,
}
```

No external APIs or asynchronous infrastructure are required in this version.

### 3.3 Candle Construction

The adapter groups incoming ticks into deterministic fixed-width candles. The current
implementation uses a bucket size of four ticks per candle.

Each candle stores:

1. `open`
2. `high`
3. `low`
4. `close`
5. `volume`

This conversion is important because the first adapter treated each price tick as an isolated
node. That representation proved too weak: trend, range, and shock all collapsed into the same
final signal neighborhood.

### 3.4 Feature Representation

Each candle is converted into a four-dimensional feature vector:

1. `return_t = close_t - close_(t-1)`
2. `range_t = high_t - low_t`
3. `body_t = close_t - open_t`
4. `volume_t = volume_t`

These features are normalized per rolling window:

`x = (x - mean) / (std + 1e-8)`

The resulting node representation is therefore relational rather than level-based. The graph is
meant to encode local market shape, not raw price magnitude.

### 3.5 Graph Construction

The upgraded graph logic has two parts.

First, every pair of nodes receives a feature-distance similarity weight:

`distance(i, j) = ||x_i - x_j||_2`

`weight(i, j) = exp(-(distance(i, j)^2) / tau)`

with `tau = 1.0`.

Second, temporal adjacency is preserved explicitly. Consecutive nodes are always connected, and
their weights are floored by:

`adjacency_floor = 0.3`

This matters because the graph should not become purely feature-clustered. Market structure is
both geometric and temporal. The adjacency floor keeps the graph tied to sequence order even
when distant candles are feature-similar.

## 4. Validation Protocol

### 4.1 Goal

The validation target is narrow: determine whether the upgraded adapter can produce different
HAOS signatures for distinct deterministic market regimes.

### 4.2 Regimes

`examples/validate_trading_adapter.py` constructs three deterministic streams of equal length:

1. trend
2. range
3. shock

The regimes are defined as follows:

1. trend: upward drift with low oscillation
2. range: mean-reverting oscillation with moderate noise
3. shock: calm period, one sharp drop, then elevated volatility

### 4.3 Pass Criteria

The adapter passes only if all three conditions hold:

1. repeated runs are identical
2. range does not match trend
3. shock does not match trend

The validator is intentionally allowed to fail. If signatures do not separate, the file exits
with a failure message rather than disguising the problem.

## 5. Results

The validated final signatures are:

1. trend
   `state=critical`, `k_star=3`, `safety_margin=-0.154216`, `confidence=0.005682`
2. range
   `state=critical`, `k_star=1`, `safety_margin=-0.115486`, `confidence=0.002114`
3. shock
   `state=critical`, `k_star=3`, `safety_margin=-0.253826`, `confidence=0.018939`

These results establish three concrete facts.

1. The adapter is deterministic under repeated runs.
2. Range and trend no longer collapse into the same signature.
3. Shock and trend no longer collapse into the same signature.

## 6. Interpretation

The new adapter does real work because the separating dimensions are meaningful.

### 6.1 Range Regime

The range case moves to `k_star = 1`. That suggests instability is being expressed earlier in
the transition chain than in the trend case. The range regime is therefore not simply a weaker
trend; it is structurally different in where the strongest consolidation failure appears.

### 6.2 Shock Regime

The shock case keeps `k_star = 3`, matching the trend regime, but with a much more negative
`safety_margin` and a much larger `confidence`. That means the dominant failure step is the same
index, but the underlying structural stress is much stronger.

### 6.3 Coarse State Label

All three regimes still map to `critical`. This does not invalidate the adapter. It shows that
the current top-level state label is too blunt to carry the whole interpretation for market
windows. The finer signals already separate:

1. `k_star`
2. `safety_margin`
3. `confidence`

This is the correct honest reading of the result.

## 7. What Changed from Adapter V1

The first trading adapter failed because it was too thin.

Its limitations were:

1. each tick became a trivial single-point candle
2. edges depended only on immediate price similarity
3. the graph mostly tracked price proximity rather than regime shape

The upgraded adapter fixes those specific weaknesses:

1. ticks are aggregated into candles
2. candles are represented by multi-feature vectors
3. graph weights are based on feature distance
4. temporal adjacency is preserved explicitly

The gain is not cosmetic. The validator confirms that the graph now carries regime information
into HAOS rather than simply replaying price level differences.

## 8. Constraints

The present implementation also has clear limits.

### 8.1 No Predictive Claim

The adapter is not a price predictor and does not emit trading actions.

### 8.2 Synthetic Validation Only

The current evidence comes from deterministic synthetic streams, not real market feeds.

### 8.3 Coarse State Threshold

The top-level state label remains overly severe for these market windows. This is a calibration
issue for later study, not a reason to reject the representation upgrade.

### 8.4 Representation Dependence

As with other external graph applications in HAOS Genesis, the signal depends on how the domain
is mapped into a graph. The present mapping is now strong enough to separate synthetic regimes,
but it is not yet a universal market representation.

## 9. Practical Use

The present adapter is best understood as a regime-sensitive structural monitor.

A rolling workflow is:

1. ingest ticks
2. aggregate ticks into deterministic candles
3. map candles into a feature graph
4. call `HAOSSensor.update(graph)`
5. read `k_star`, `safety_margin`, `confidence`, `drift`, and `k_shift`

The main operational question becomes:

1. is the market structure changing in a way that weakens consolidation?

That is a legitimate and narrower question than price forecasting.

## 10. Next Step

The correct next step is not to retune the threshold or embellish the state label. The correct
next step is one rolling-window experiment on real historical or live market data.

The purpose of that test is simple:

1. see whether `k_star` shifts before visible structural change
2. see whether `safety_margin` deteriorates before volatility expansion
3. determine whether the adapter remains useful outside synthetic regimes

## 11. Conclusion

The new additions move HAOS Genesis from one-shot graph analysis toward continuous structural
monitoring. `HAOSSensor` provides a minimal rolling stability contract on top of the existing
API, and `TradingStreamAdapter` gives that sensor a deterministic market representation. The
adapter now clears the first meaningful gate: deterministic trend, range, and shock regimes no
longer collapse into the same signature.

That is enough to justify the new layer as a practical extension of HAOS Genesis. It is still
early, still synthetic, and still narrow. But it now behaves like an instrument rather than an
idea.
