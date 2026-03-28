# HAOS Genesis

![Architecture of Graph Collapse Analysis](docs/Architecture%20of%20Graph%20Collapse%20Analysis.png)

HAOS Genesis is a minimal universe generator for studying persistence and collapse under constrained evolution. Each run creates a seeded interaction graph-world, evolves it through a frozen hierarchy, and measures persistence and recovery at each step. In the validated base regime, the system exposes a narrow pre-collapse boundary.

## v0.1 Highlights

- Collapse concentrates at levels `2-3` in the validated base regime (`size=128`, `shift=0.0`, perturbation off).
- `delta_persistence(1->2)` predicts break family before collapse, with held-out accuracy `87.5%`.
- The decisive mechanism is consolidation failure within connected support, not fragmentation.
- Schedule shift acts as a control parameter that advances the critical transition step and changes the collapse regime.

## Validated Claim

In the regime defined by `size=128`, `shift=0.0`, and perturbation off, a seed breaks at level `2` rather than `3` when the `1->2` transition produces a stronger consolidation loss while connected support remains intact.

## Reproduce Collapse Map

From the repository root:

```bash
python3 -m pip install -r requirements.txt
python3 collapse_map.py --seed-start 20 --seed-stop 50 --strengths 0.0 0.01 0.03 0.05 0.08
```

Outputs are written locally to `output/` and are ignored by git.

## Explore the System

```bash
streamlit run app.py
```

## Repository Contents

- `generator.py`: path-dependent graph evolution engine
- `collapse_map.py`: collapse-band sweep across seeds and perturbation strengths
- `predict_collapse.py`: minimal threshold predictor for break family
- `boundary_microscope.py`: boundary inspection for connected-support behavior
- `validate_mechanism.py`: regime-local mechanism checks across variants
- `shift_sweep.py`: schedule-shift control mapping

## Docs

- [Full documentation](docs/HAOS_GENESIS_FULL_DOCUMENTATION.md)
- [Technical paper](docs/HAOS_GENESIS_TECHNICAL_PAPER.md)
- [v0.1.0 release body](docs/V0_1_RELEASE_BODY.md)
- [Landing page copy](docs/V0_1_LANDING_PAGE_COPY.md)
