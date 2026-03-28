# HAOS Genesis v0.1

HAOS Genesis is a self-contained persistence engine extracted into a standalone package.
It generates path-dependent graph trajectories, measures stability under controlled change,
and ships with the analysis scripts used to derive the current base-regime results.

## What This Package Does

HAOS Genesis treats a universe as:

`(G0, hierarchy trace, metrics trajectory)`

The package tests whether structure survives constrained transformation.
It does not claim physical realism. It is an operational probe for persistence,
collapse, and pre-collapse prediction.

## Package Contents

- `generator.py`: builds and refines a universe trace.
- `birth_certificate.py`: composes trace-level summary fields.
- `video.py`: renders a symbolic level-by-level video.
- `app.py`: minimal Streamlit interface.
- `internal/`: self-contained graph, hierarchy, perturbation, plotting, and metric logic.
- `collapse_map.py`: sweep seeds and perturbation strengths.
- `compare_seed_families.py`: compare break-2 and break-3 seeds.
- `predict_collapse.py`: fit a minimal threshold predictor.
- `boundary_microscope.py`: inspect seeds nearest the collapse threshold.
- `validate_mechanism.py`: check whether the base mechanism survives size, shift, and perturbation variants.
- `shift_sweep.py`: treat hierarchy schedule shift as a control parameter.
- `output/`: generated figures, CSVs, and validation artifacts.
- `docs/`: full documentation and the numbered technical paper.

## Dependencies

Install:

```bash
python3 -m pip install -r requirements.txt
```

Required packages:

- `numpy`
- `matplotlib`
- `moviepy`
- `streamlit`

## Standalone Use

The folder is designed to work without the original HAOS-IIP repository.

From the parent directory:

```bash
python3 -m haos_genesis.collapse_map --seed-start 20 --seed-stop 50
python3 -m haos_genesis.shift_sweep --seed-start 20 --seed-stop 50
streamlit run haos_genesis/app.py
```

From inside the folder:

```bash
python3 collapse_map.py --seed-start 20 --seed-stop 50
python3 shift_sweep.py --seed-start 20 --seed-stop 50
streamlit run app.py
```

Outputs default to:

`haos_genesis/output/`

## Current Validated Base-Regime Result

Validated base regime:

- size `128`
- schedule shift `0.0`
- perturbation `off`

Within that regime:

- the collapse band is concentrated at levels `2-3`
- `delta_persistence(1->2)` is the sharpest pre-collapse predictor
- the threshold transition band is extremely narrow around `-0.1176`
- the boundary microscope shows connected support is preserved
- the deciding mechanism is consolidation loss, not fragmentation

## Main Artifacts

- full documentation:
  - `docs/HAOS_GENESIS_FULL_DOCUMENTATION.md`
- numbered technical paper:
  - `docs/HAOS_GENESIS_TECHNICAL_PAPER.md`
  - `docs/HAOS_GENESIS_TECHNICAL_PAPER.html`
  - `docs/HAOS_GENESIS_TECHNICAL_PAPER.pdf`

## Recommended Reading Order

1. `docs/HAOS_GENESIS_FULL_DOCUMENTATION.md`
2. `docs/HAOS_GENESIS_TECHNICAL_PAPER.pdf`
3. `output/mechanism_validation.md`
4. `output/shift_sweep_control_map.png`

## Results (v0.1)

- Collapse band: levels 2-3 (base regime, size=128, shift=0)
- Pre-collapse predictor: Delta persistence(1->2)
- Threshold (base): ~ -0.1176 (narrow transition band)
- Mechanism: consolidation failure within connected support (not fragmentation)

### Control (schedule shift)

- shift 0.0-0.3 -> two-family regime (break=2 vs 3)
- shift ~= 0.4 -> split collapses (all break=2)
- shift >= 0.7 -> new regime (break=1 dominant)

Interpretation: shift advances the critical transition step.

### Reproduce collapse map

```bash
python -m haos_genesis.collapse_map --seed-start 20 --seed-stop 50 --strengths 0.0 0.01 0.03 0.05 0.08
```
