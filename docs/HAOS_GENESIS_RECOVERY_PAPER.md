# HAOS Genesis Recovery Paper: A Deterministic Search for Minimal Stabilizing Interventions

Author: Tomislav Rupic

Version: v0.1.0

## Abstract

HAOS Genesis originally established a narrow collapse boundary in a path-dependent graph
evolution system. The recovery layer extends that work in a minimal way: it does not
change the core dynamics, the metrics, or the prediction rule. Instead, it asks a more
practical question. Given an externally supplied graph that is already near collapse, can
the system propose a small deterministic intervention that delays the critical transition
or weakens the sharpest consolidation failure?

The present implementation answers that question with a bounded recovery search over two
intervention families: reinforcing weak existing edges and adding short-range missing
edges. Candidates are evaluated with the same stability probe already used elsewhere in the
repository. The scoring rule is explicit and lexicographic: prioritize later `k_star`,
then a weaker `min_delta`, then a safer threshold margin, then lower cost. In a degraded
network demonstration, the best intervention moves `k_star` from `2` to `4` by adding one
edge. Stress tests show that the recovery layer is scale-stable after normalization but
remains sensitive to graph embedding. That makes the current result useful as a local
stability design primitive, but not yet representation-invariant.

## 1. Recovery Objective

The collapse work in HAOS Genesis established three operational facts:

1. collapse can be measured from a deterministic trace
2. collapse can be predicted before the visible break
3. `k_star = argmin delta_persistence` identifies the critical transition step

Recovery design adds one more question:

1. what is the smallest intervention that pushes the critical transition later or weakens
   the sharpest persistence drop?

The implementation is intentionally narrow. It does not attempt global optimization, causal
inference, or multi-step planning. It performs a local search over a small bounded set of
candidate edge edits and ranks them with the same stability signal already used throughout
the repository.

## 2. Operational Definition of Recovery

Recovery is defined operationally, not rhetorically. A candidate intervention is considered
better than baseline when it improves the transition profile under the existing trace
analysis.

### 2.1 Baseline Signal

For any input graph, the stability probe returns:

```python
{
    "k_star": int,
    "predicted_break": int,
    "safety_margin": float,
    "min_delta": float,
    "confidence": float,
}
```

These values have fixed meanings:

1. `k_star`: index of the strongest persistence drop
2. `predicted_break`: threshold-based break-family prediction from `delta_persistence(1->2)`
3. `safety_margin`: `threshold - delta_persistence(1->2)`
4. `min_delta`: most negative or weakest transition value selected by `k_star`
5. `confidence`: raw magnitude `abs(min_delta)`

### 2.2 Intervention Space

The current recovery layer searches only two edit families:

1. reinforce weak existing edges
2. add short-range missing edges

This is deliberate. The goal is to keep the intervention space small, deterministic, and
comparable across runs.

### 2.3 Candidate Ranking

Each candidate is compared against baseline with the lexicographic score:

`(delta_k_star, delta_min_delta, delta_safety_margin, delta_predicted_break, -cost)`

In plain terms, the search prefers:

1. later critical transition
2. weaker sharpest persistence loss
3. safer threshold margin
4. later predicted break family
5. lower intervention cost

This ordering matters. It means the current implementation treats delayed collapse origin as
the primary definition of recovery. A candidate can therefore be selected even if one
secondary scalar does not improve.

## 3. Implementation in the Repository

The recovery layer is implemented without changing the frozen HAOS core.

### 3.1 Files

1. `api/recovery.py`
2. `api/skill.py`
3. `examples/demo_recovery_design.py`
4. `examples/benchmark_recovery_stress.py`

### 3.2 Primary Functions

1. `suggest_recovery(input_payload)`
2. `apply_intervention(input_payload, intervention)`
3. `haos_stability_skill(input_payload)`

### 3.3 Input Contract

Recovery currently requires external graph input:

```python
{
    "nodes": [...],
    "edges": [(u, v, weight), ...],
    "positions": [...],  # optional but recommended
    "seed": 19,
    "refinement_levels": 5,
}
```

Affinity is normalized before trace construction. The normalization is idempotent with
respect to already scaled inputs and row-consistent for transport.

### 3.4 Output Contract

The recovery search returns:

```python
{
    "baseline": {...},
    "best_intervention": {
        "kind": "add_edge" | "reinforce_edge",
        "edge": [u, v],
        "cost": float,
        "weight_before": float,
        "weight_after": float,
        "k_star_gain": int,
        "min_delta_gain": float,
        "safety_margin_gain": float,
        "predicted_break_gain": int,
        "result": {...},
    } | None,
    "candidates_evaluated": int,
}
```

## 4. Deterministic Recovery Demonstration

The recovery demo uses a degraded Watts-Strogatz graph with `36` nodes. Long edges are
removed from a weighted neighborhood graph, producing a connected but weakened support
structure.

The baseline signal is:

1. `k_star = 2`
2. `predicted_break = 3`
3. `safety_margin = -0.11796075036075035`
4. `min_delta = 0.0`

The best intervention found by the bounded search is:

1. `kind = add_edge`
2. `edge = [18, 24]`
3. `cost = 0.43336804810915786`
4. `k_star_gain = 2`
5. `min_delta_gain = 0.0003848003848003906`

The resulting state is:

1. `k_star = 4`
2. `predicted_break = 3`
3. `safety_margin = -0.12456248196248196`
4. `min_delta = 0.0003848003848003906`

This result is important because it is mixed, not cosmetic. The best candidate delays the
critical transition and weakens the sharpest persistence break, but it does not improve the
threshold margin. That behavior is consistent with the current scoring rule and makes the
definition of recovery explicit: recovery here means pushing the collapse origin later
before it means making every scalar look safer.

![](../output/demo_recovery_design.png)

Figure 1. Recovery demonstration from `examples/demo_recovery_design.py`. The repaired graph
pushes the critical transition later in the trace.

## 5. Stress Test Summary

The recovery layer was pressure-tested on five graph groups:

1. sparse path graph
2. dense complete graph
3. skewed-weight small-world graph
4. scale-equivalent variants of the same degraded graph
5. embedding variants of the same degraded graph

The summary results are:

1. `scale_equivalent`: `3` variants, `1` signature, identical `k_star = 2`
2. `embedding_variants`: `3` variants, `3` signatures, `k_star` values `2` and `4`
3. `dense`: `1` variant, `k_star = 4`
4. `skewed`: `1` variant, `k_star = 3`
5. `sparse`: `1` variant, `k_star = 3`

Three observations follow immediately:

1. normalization removes trivial scale dependence in the tested setup
2. embedding changes can move the signal even when topology is nominally comparable
3. every tested group produced at least one bounded intervention candidate

The stress benchmark therefore validates one invariance and exposes one limitation. Scale is
handled cleanly after normalization. Representation is not yet neutral.

## 6. Interpretation

The recovery layer should be read narrowly.

1. It is a deterministic search over local graph edits.
2. It does not guarantee global stabilization.
3. It does not guarantee improvement on every scalar.
4. It does expose which small edits most effectively move the collapse origin under the
   current signal definition.

This makes the recovery primitive useful as a design instrument. It can answer questions of
the form:

1. which missing bridge most delays failure?
2. which weak edge is worth reinforcing first?
3. does the graph admit a cheap local intervention at all?

## 7. Constraints

The current implementation has clear limits.

### 7.1 Representation Sensitivity

Equivalent topology can still produce different signals when positions or embeddings differ.
This is visible in the embedding stress test and should be treated as a real constraint.

### 7.2 Local Search Only

The search space is bounded and shallow. It does not consider multi-step repair programs,
node interventions, or counterfactual hierarchy changes.

### 7.3 Cost is Raw

Intervention cost is currently the raw added or reinforced weight. It is useful for ranking
inside a run, but it is not yet normalized into a domain-level budget model.

### 7.4 Recovery is Regime-Local

The recovery objective inherits the same regime-local character as the collapse work. A
candidate that helps in one graph family is not automatically portable to another.

## 8. Creative Domain Outlook

The recovery primitive opens a careful path into creative systems, but only if the mapping
is explicit.

A creative workflow could be represented as a graph where:

1. nodes are motifs, scenes, phrases, shots, or idea fragments
2. weighted edges represent compatibility, continuity, or harmonic fit
3. positions represent a chosen semantic or aesthetic embedding

Under that representation, the recovery search becomes a question of minimal structural
repair:

1. which bridge between motifs restores continuity?
2. which weak relation needs reinforcement to keep a sequence coherent?
3. where does the creative structure stop consolidating before visible breakdown?

This is promising, but not yet validated. The same representation sensitivity seen in the
stress test will matter even more in creative domains, because the embedding itself becomes
part of the artistic decision surface. For that reason, the creative path should begin as a
bounded experiment, not as a general claim.

## 9. Conclusion

HAOS Genesis recovery design is now a concrete layer on top of the frozen collapse system.
It does one practical thing: given a graph near collapse, it proposes a small deterministic
edit that best delays the critical transition under the current signal definition.

The result is modest but real. Recovery is now measurable, callable, and testable inside the
same framework that already measured collapse. The next serious step is not expansion. It is
selective application: either improve representation robustness or test one real domain with
a clearly defined graph construction rule.
