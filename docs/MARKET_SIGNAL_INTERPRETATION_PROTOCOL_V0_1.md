# HAOS Genesis — Market Signal Interpretation Protocol v0.1

## Purpose

Provide a fixed, minimal, and reproducible method for interpreting HAOS signals on market data.

This protocol prevents drift in interpretation across datasets and ensures that all readings are
judged by the same criteria.

## Scope

Applies to outputs from:

1. `examples/test_real_market_stream.py`
2. `adapters/trading_stream.py`
3. `api/sensor.py`

Signals evaluated:

1. `safety_margin`
2. `k_star`
3. `confidence`

## General Rules

1. No smoothing, filtering, or transformation of outputs.
2. No parameter tuning during interpretation.
3. No cross-signal inference during first-pass evaluation.
4. No narrative fitting after the fact.
5. Evaluation must be done on a pre-selected visible market transition window.

## Evaluation Window

Each test must define:

1. One clear visible regime change:
   1. range -> breakout
   2. calm -> volatility expansion
   3. trend -> chop
2. A fixed window split into:
   1. pre-transition
   2. transition
   3. post-transition

## Signal Criteria

### 1. safety_margin

Definition of valid signal:

1. A consistent downward trend in `safety_margin`.
2. The deterioration occurs during the pre-transition window.
3. The deterioration leads into the transition rather than starting only during or after it.

Not valid if:

1. Oscillatory without direction.
2. Flat before the transition.
3. Only drops after the move.

Label:

1. `lead`: clear downward trend before transition.
2. `during`: drop begins only at transition.
3. `absent`: no meaningful deterioration.

### 2. k_star

Definition of valid signal:

1. `k_star` becomes coherent rather than random near instability.
2. The coherent behavior may appear as a shift toward lower values or as stabilization inside a
   consistent band.

Not valid if:

1. Rapid flickering without pattern.
2. No change across the evaluation window.

Label:

1. `lead`: coherent shift occurs before transition.
2. `during`: coherence appears at or after transition.
3. `absent`: no stable pattern.

### 3. confidence

Definition of valid signal:

1. `confidence` increases meaningfully near instability.
2. The increase may peak during or after the transition.

Not valid if:

1. Flat near zero throughout.
2. Isolated spikes with no relation to the transition.

Label:

1. `lead`: increase occurs before transition.
2. `during`: increase occurs during or after transition.
3. `absent`: no meaningful rise.

## Output Format

Each evaluated segment must produce:

```text
Asset: BTC / ETH / ...
Window: [start -> end]

safety_margin: lead | during | absent
k_star:         lead | during | absent
confidence:     lead | during | absent
```

Optional note:

1. Maximum two lines.
2. Objective observations only.
3. No interpretation or claims.

## Interpretation Rules

1. A valid early-warning signal requires:
   1. `safety_margin = lead`
2. `k_star` and `confidence` are supporting signals and are not required to lead.
3. A segment is classified as:
   1. `early-detected instability` if `safety_margin = lead`
   2. `detected instability (non-leading)` if only `during` signals appear
   3. `no detection` if all signals are `absent`

## Cross-Run Consistency Check

A pattern is considered real only if:

1. It appears in multiple assets or segments.
2. It is judged under the same protocol.
3. No parameters or interpretation rules were modified between runs.

## Known Limitations

1. Price-only input weakens signal quality.
2. Small windows may exaggerate noise.
3. The top-level `state` label is not currently reliable for interpretation.
4. `k_star` is not expected to lead in the current version.

## Non-Goals

This protocol does not:

1. Define trading signals.
2. Define thresholds for execution.
3. Claim predictive power.
4. Optimize performance.

## Versioning

1. `v0.1`: initial protocol for price-only and early OHLCV-stage testing.
2. Future versions may refine criteria only if justified by consistent cross-run evidence.
