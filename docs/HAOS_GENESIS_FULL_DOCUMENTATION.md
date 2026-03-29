# HAOS Genesis Full Documentation

Author: Tomislav Rupic

Version: v0.1.0

## 1. Purpose

HAOS Genesis is a self-contained subsystem for testing whether graph structure survives
constrained transformation. It was extracted so the package can be moved into its own
repository and run without any dependency on the original HAOS-IIP tree.

The package is intentionally narrow:

- it generates deterministic graph trajectories
- it measures persistence and recovery at each level
- it supports controlled perturbation
- it includes the analysis scripts used to identify collapse bands, predictors, and control behavior
- it exposes a deterministic stability monitor and agent-callable skill for practical use

The package does not model physics, spacetime, or consciousness.
It is an operational persistence probe.

## 2. Core Model

### 2.1 Universe Definition

A universe is represented as:

`(G0, hierarchy trace, metrics trajectory)`

Where:

- `G0` is the initial interaction graph
- the hierarchy trace is the sequence of refined graph states
- the metrics trajectory records persistence-related measurements at each level

### 2.2 Design Constraints

The system is built around the following constraints:

- all behavior is seed-reproducible
- the hierarchy is frozen and explicit
- perturbation can be toggled on or off
- metrics are operational and tied to the evolving state
- the state at the next level depends on the previous level

### 2.3 Why Path Dependence Matters

The package originally risked becoming a parameter sweep.
That was corrected by replacing per-level graph rebuilding with a refinement step that
transforms the previous state.

The current update is:

1. build the target kernel support from the frozen schedule
2. compute a transport operator from the previous graph
3. evolve the previous affinity as `T A T^T`
4. constrain the evolved state by the current kernel support

This makes the trace cumulative rather than independent across levels.

## 3. Package Structure

```text
haos_genesis/
├── __init__.py
├── README.md
├── agent/
├── api/
├── app.py
├── birth_certificate.py
├── boundary_microscope.py
├── collapse_map.py
├── compare_seed_families.py
├── examples/
├── generator.py
├── paths.py
├── predict_collapse.py
├── requirements.txt
├── shift_sweep.py
├── utils.py
├── validate_mechanism.py
├── video.py
├── docs/
├── internal/
└── output/
```

### 3.1 Internal Modules

- `internal/graph_builder.py`
  - defines `InteractionGraph`
  - creates the initial affinity graph from 2D node positions
  - creates the transport operator
- `internal/hierarchy.py`
  - defines the frozen hierarchy schedule
  - supports `schedule_shift`
- `internal/metrics.py`
  - computes persistence, recovery, clustering, overlap, transport efficiency, and labels
- `internal/stability.py`
  - performs perturbation without mutating the original graph
- `internal/plotting.py`
  - renders graph frames for videos

## 4. Installation and Execution

## 4.1 Dependencies

Install:

```bash
python3 -m pip install -r requirements.txt
```

Required packages:

- `numpy`
- `matplotlib`
- `networkx`
- `moviepy`
- `streamlit`
- `reportlab` for rebuilding the technical paper PDF

### 4.2 Running From a Parent Repo

```bash
python3 -m haos_genesis.collapse_map --seed-start 20 --seed-stop 50
python3 -m haos_genesis.compare_seed_families
python3 -m haos_genesis.predict_collapse
python3 -m haos_genesis.boundary_microscope
python3 -m haos_genesis.validate_mechanism
python3 -m haos_genesis.shift_sweep
python3 -m haos_genesis.examples.demo_real_graph
python3 -m haos_genesis.examples.demo_network_failure
streamlit run haos_genesis/app.py
```

### 4.3 Running Directly From the Folder

```bash
python3 collapse_map.py --seed-start 20 --seed-stop 50
python3 compare_seed_families.py
python3 predict_collapse.py
python3 boundary_microscope.py
python3 validate_mechanism.py
python3 shift_sweep.py
python3 examples/demo_real_graph.py
python3 examples/demo_network_failure.py
streamlit run app.py
```

### 4.4 Building the Technical Paper PDF

```bash
python3 docs/build_technical_paper_pdf.py
```

### 4.5 Output Location

All analysis scripts default to:

`haos_genesis/output/`

Matplotlib cache is also redirected into:

`haos_genesis/output/.mpl/`

That keeps the folder self-contained in a new repository or a fresh Codex workspace.

## 5. Generator

### 5.1 Entry Point

Main entry point:

```python
generate_universe(
    seed: int | None = None,
    size: int = 128,
    refinement_levels: int = 5,
    perturbation: bool = False,
    perturbation_strength: float = 0.03,
    schedule_shift: float = 0.0,
) -> tuple[list[dict], int]
```

It returns:

- `trace`: a list of per-level records
- `seed`: the resolved deterministic seed

Each trace item contains:

- `level`
- `graph`
- `metrics`

### 5.2 Initial Graph

`build_graph(...)` does the following:

1. sample deterministic 2D node positions in `[0, 1]^2`
2. compute pairwise Euclidean distances
3. build a Gaussian affinity matrix
4. zero out links beyond the locality radius
5. zero the diagonal

Affinity kernel:

`A_ij = exp(-d_ij^2 / (2 sigma^2))`

with support constrained by `d_ij <= locality_radius`.

### 5.3 Frozen Hierarchy

The frozen schedule computes:

- `n_side = round(sqrt(size))`
- `h = 1 / n_side`
- `kernel_width(level) = (level + 1 + schedule_shift) * h`
- `locality_radius = min(3 * kernel_width, sqrt(2))`

Schedule shift must keep all multipliers positive.

### 5.4 Refinement Step

Refinement is path-dependent.

For each level after the initial graph:

1. rebuild only the target support from the new kernel width while preserving node geometry
2. compute the transport operator from the previous graph
3. evolve the previous affinity as:

`A_evolved = T A_prev T^T`

4. constrain the evolved state:

`A_new = min(A_evolved, A_target)`

This is the minimal mechanism that introduces memory and irreversibility.

## 6. Perturbation

Perturbation is deterministic for a given seed and level.

Current perturbation modes inside `perturb_graph(...)`:

- weight jitter by small Gaussian noise
- low-probability rewiring
- rare node removal capped below 1 percent

Important constraint:

- perturbation returns a new graph
- the original graph is never mutated

Known implication:

the node-removal branch introduces possible fragmentation.
That matters when interpreting perturbation-on mechanism tests.

## 7. Metrics

## 7.1 Core Metrics

Per-level metrics include:

- `node_count`
- `edge_count`
- `largest_component_fraction`
- `clustering_coefficient`
- `connectivity_diameter`
- `transport_efficiency`
- `persistence_score`
- `recovery_score`
- `overlap`
- `perturbation_sensitivity`
- `label`

### 7.2 Additional Trajectory Metrics

The generator adds:

- `local_overlap`
  - overlap with the immediately previous graph state
- `delta_persistence`
  - current persistence minus previous persistence

These two fields are essential for collapse analysis.

### 7.3 Metric Intent

- `persistence_score`
  - neighborhood retention under repeated transport steps
- `recovery_score`
  - penalty-based score derived from localization width, concentration retention,
    participation ratio, and overlap
- `overlap`
  - global similarity to the origin state proxy
- `local_overlap`
  - step-to-step similarity
- `perturbation_sensitivity`
  - `1 - overlap`

### 7.4 Birth Certificate

`BirthCertificate.from_trace(...)` composes:

- `stable_identity_count`
- `persistence_score`
- `connectivity_diameter`
- `transport_efficiency`
- `failure_events`
- `recovery_score`

This is a trace summary, not a full dynamic explanation.

## 8. Streamlit App

`app.py` exposes a minimal UI with:

- seed input
- size slider
- refinement level slider
- perturbation toggle
- perturbation strength slider

Outputs:

- symbolic video
- Birth Certificate
- line chart of persistence and recovery by level
- resolved seed display

Run:

```bash
streamlit run app.py
```

## 9. Practical API and Agent Layer

### 9.1 Stability Monitor

`api/stability_monitor.py` defines the shared transition primitive:

`k_star = argmin delta_persistence(k -> k+1)`

`StabilityMonitor.analyze_trace(trace)` returns:

- `k_star`
- `delta_persistence`
- `min_delta`
- `predicted_break`
- `safety_margin`

Interpretation is fixed in code:

- `safety_margin > 0`
  - stable
- `safety_margin ~= 0`
  - boundary
- `safety_margin < 0`
  - predicted collapse

### 9.2 Predictor and Skill Wrapper

`api/predictor.py` exposes:

`predict_collapse(trace, threshold=-0.1176)`

`api/skill.py` exposes:

- `haos_stability_skill(payload)`
- `analyze_many(payloads)`
- `monitor_sequence(payloads)`

The machine contract returned by `haos_stability_skill(...)` is fixed:

```text
{
  "k_star": int,
  "predicted_break": int,
  "safety_margin": float,
  "min_delta": float,
  "confidence": float
}
```

### 9.3 External Graph Mode and Agent Bindings

The skill accepts either:

- synthetic configuration input
- external graph input with `nodes`, `edges`, and optional `positions`

External graph mode:

- normalizes affinity once before building the trace
- guards against graphs with fewer than four nodes
- rejects disconnected zero-affinity input
- preserves deterministic behavior for a fixed seed

Agent bindings currently live in:

- `agent/hermes_tool.json`
- `agent/openclaw_tool.py`

## 10. Analysis Scripts

### 10.1 Collapse Map

Script:

`collapse_map.py`

Purpose:

- sweep seeds and perturbation strengths
- record the break level determined by the minimum `delta_persistence`
- compute final overlap, failure events, and mean recovery

Primary outputs:

- `collapse_map.csv`
  - includes `k_star` and `min_delta_persistence`
- `collapse_map_break_level.png`

### 10.2 Seed Family Comparison

Script:

`compare_seed_families.py`

Purpose:

- split runs into `break_2` and `break_3` families
- compare pre-break features at levels `0`, `1`, and `2`
- rank separators by effect size

Primary outputs:

- `seed_family_off_features.csv`
- `seed_family_off_summary.csv`
- `seed_family_off_top_features.png`

### 10.3 Collapse Predictor

Script:

`predict_collapse.py`

Purpose:

- fit a minimal threshold predictor for break family
- currently tests:
  - `delta_persistence_1_to_2`
  - `L2_persistence_score`

Primary outputs:

- `predictor_off_summary.csv`
- `predictor_off_predictions.csv`
- threshold plots

### 10.4 Boundary Microscope

Script:

`boundary_microscope.py`

Purpose:

- select seeds nearest the family threshold
- inspect levels `1`, `2`, and `3`
- determine whether the boundary is fragmentation-based or consolidation-based

Primary outputs:

- `boundary_microscope_selected.csv`
- `boundary_microscope_traces.csv`
- `boundary_microscope_levels_1_to_3.png`

### 10.5 Mechanism Validation

Script:

`validate_mechanism.py`

Purpose:

- check whether the base mechanism survives size change, schedule shift, and perturbation
- prevent over-generalization of the base-regime explanation

Primary outputs:

- `mechanism_validation_summary.csv`
- `mechanism_validation_traces.csv`
- `mechanism_validation.md`

### 10.6 Shift Sweep

Script:

`shift_sweep.py`

Purpose:

- treat hierarchy schedule shift as a control parameter
- record family counts, dominant break level, threshold existence, and connected-support status
- summarize the critical transition through `k_star_mode`, `k_star_mean`, and `k_star_counts`

Primary outputs:

- `shift_sweep_summary.csv`
- `shift_sweep_break_counts.csv`
- `shift_sweep_runs.csv`
- `shift_sweep_k_star_counts.csv`
- `shift_sweep_k_star_distribution.png`
- `shift_sweep_control_map.png`

## 11. Validated Results

## 11.1 Collapse Band

On the base sweep over seeds `20-50` and strengths `off`, `0.01`, `0.03`, `0.05`, `0.08`:

- break level counts: `{2: 42, 3: 111, 4: 2}`
- dominant collapse band: levels `2-3`

By strength:

- `off`: `{2: 7, 3: 23, 4: 1}`
- `0.01`: `{2: 8, 3: 23}`
- `0.03`: `{2: 8, 3: 22, 4: 1}`
- `0.05`: `{2: 10, 3: 21}`
- `0.08`: `{2: 9, 3: 22}`

The boundary location remains narrow while severity degrades gradually.

### 11.2 Base-Regime Predictor

For the validated base regime:

- `delta_persistence_1_to_2` threshold predictor:
  - threshold fit: `<= -0.115589`
  - training accuracy: `1.000`
  - held-out accuracy: `0.875`
- transition band:
  - break-2 seed `35`: `-0.11766937335958003`
  - break-3 seed `41`: `-0.1175659150560725`
  - midpoint: `-0.11761764420782626`

Interpretation:

- uncertainty is localized to an extremely narrow band
- the predictor is derivative-based rather than state-based

### 11.3 Family Separation

Top separating features in the base regime:

1. `delta_persistence_1_to_2`
   - effect size: `-2.3289`
2. `L2_persistence_score`
   - effect size: `-2.0599`
3. `L2_local_overlap`
   - effect size: `1.0273`
4. `L0_clustering_coefficient`
   - effect size: `-0.9327`
5. `delta_local_overlap_1_to_2`
   - effect size: `0.9034`

Interpretation:

- break-2 seeds are already weaker before the boundary
- the sharpest separation comes from failed consolidation during the `1->2` step

### 11.4 Boundary Microscope

Selected near-threshold seeds:

- break-2: `35`, `23`, `47`
- break-3: `41`, `43`, `21`

Average boundary traces:

- break-2 level 1:
  - persistence `0.250181`
  - recovery `0.759912`
- break-2 level 2:
  - persistence `0.129318`
  - recovery `0.566563`
- break-3 level 1:
  - persistence `0.244314`
  - recovery `0.790222`
- break-3 level 2:
  - persistence `0.131726`
  - recovery `0.652817`

Boundary-support condition:

- `largest_component_fraction = 1.0`
- `component_count = 1`

Conclusion:

the base boundary is not driven by fragmentation.
It is a consolidation-loss boundary inside a connected support.

### 11.5 Mechanism Validation

Mechanism validation summary:

- `size_128, shift_0.0, perturbation_off`
  - mechanism holds
- `size_256`
  - support remains connected
  - family balance collapses too strongly to preserve the same two-family explanation
- `perturb_0.03`
  - consolidation-loss separation remains visible
  - strict non-fragmentation no longer holds because node removal can create a second component
- shifted schedules
  - do not preserve the original family split

### 11.6 Shift Sweep

Shift sweep over `0.0 -> 1.2` in `0.1` steps:

- `0.0`: break-2 `7`, break-3 `23`, split exists
- `0.1`: break-2 `16`, break-3 `15`, split exists
- `0.2`: break-2 `26`, break-3 `5`, split exists
- `0.3`: break-2 `28`, break-3 `3`, split exists
- `0.4`: break-2 `31`, break-3 `0`, split collapses
- `0.7`: dominant break level moves to `1`
- `1.2`: all runs break at `1`

This means schedule shift is a control parameter.
It does not simply move the original threshold smoothly.
It changes the regime itself.

Operationally, the current codebase now expresses this more directly through `k_star`.
In the base regime the dominant critical step is the `1->2` transition. Under sufficiently
shifted schedules the critical transition moves earlier toward `0->1`, which is why later
shifts stop looking like a modified `2 vs 3` problem and become a different regime.

## 12. Validated Mechanism Claim

The current validated mechanism claim must remain narrow:

In the base regime defined by size `128`, schedule shift `0.0`, and perturbation `off`,
a seed breaks at level `2` rather than `3` when the `1->2` transition produces a sufficiently
stronger loss of persistence, and usually a stronger recovery loss, while connected support remains intact.

This is the current mechanism claim.
It should not be generalized automatically to larger sizes, shifted schedules, or fragmenting perturbations.

## 13. Limitations

- perturbation currently mixes non-fragmenting and fragmenting effects
- recovery is computed from operational state proxies, not a deeper dynamical field model
- large-size regimes can compress the family split
- shifted schedules can erase the `2 vs 3` comparison regime altogether
- the current video is symbolic, not analytical
- external graph mode is representation-sensitive because positions and affinity scaling can alter the observed trace

## 14. Recommended Next Work

Recommended next steps for the package:

1. stress-test the practical skill on sparse, dense, skewed, and scale-equivalent graphs
2. apply the system to one external use case rather than many at once
3. keep `k_star` as the primary transition language across scripts, summaries, and examples
4. avoid changing the update rule until pressure-testing is complete

## 15. Reproducibility Checklist

- deterministic seed handling is built in
- node geometry is preserved across refinement
- perturbation seed depends deterministically on graph seed and level
- default outputs stay inside the package folder
- the package runs without the original HAOS-IIP repository
- external graph affinity normalization is deterministic
- the technical paper PDF can be rebuilt locally from markdown

## 16. Key Files

- package overview:
  - `README.md`
- full documentation:
  - `docs/HAOS_GENESIS_FULL_DOCUMENTATION.md`
- technical paper source:
  - `docs/HAOS_GENESIS_TECHNICAL_PAPER.md`
- technical paper PDF:
  - `docs/HAOS_GENESIS_TECHNICAL_PAPER.pdf`
- practical skill:
  - `api/skill.py`
- stability monitor:
  - `api/stability_monitor.py`
- agent bindings:
  - `agent/hermes_tool.json`
- examples:
  - `examples/`
- paper builder:
  - `docs/build_technical_paper_pdf.py`
- analysis outputs:
  - `output/`
