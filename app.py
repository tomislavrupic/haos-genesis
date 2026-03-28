from __future__ import annotations
import os
from pathlib import Path
import sys
import tempfile

PACKAGE_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(PACKAGE_DIR / "output" / ".mpl"))

import matplotlib.pyplot as plt
import streamlit as st

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from haos_genesis.birth_certificate import BirthCertificate
from haos_genesis.generator import generate_universe

st.set_page_config(page_title="HAOS Genesis", layout="wide")
st.sidebar.header("Controls")
seed = st.sidebar.number_input("Seed", min_value=0, value=22, step=1)
size = st.sidebar.slider("Size", 64, 512, 128, step=16)
levels = st.sidebar.slider("Refinement Levels", 3, 8, 5)
perturbation = st.sidebar.toggle("Perturbation", value=False)
strength = st.sidebar.slider("Perturbation Strength", 0.0, 0.15, 0.03, step=0.01)
st.title("HAOS Genesis — Persistence Engine")
if st.button("Generate Universe", type="primary"):
    from haos_genesis.video import make_symbolic_video

    trace, used_seed = generate_universe(
        seed=int(seed),
        size=int(size),
        refinement_levels=int(levels),
        perturbation=bool(perturbation),
        perturbation_strength=float(strength),
    )
    certificate = BirthCertificate.from_trace(trace)
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as handle:
        video_path = make_symbolic_video(trace, handle.name)
    st.video(video_path)
    st.markdown(certificate.to_markdown())
    fig, ax = plt.subplots(figsize=(6, 3))
    xs = [entry["level"] for entry in trace]
    ax.plot(xs, [entry["metrics"]["persistence_score"] for entry in trace], marker="o", label="persistence_score")
    ax.plot(xs, [entry["metrics"]["recovery_score"] for entry in trace], marker="s", label="recovery_score")
    ax.set_xlabel("level")
    ax.set_ylim(0.0, 1.05)
    ax.legend()
    st.pyplot(fig)
    st.caption(f"Seed: {used_seed}")
# HAOS Genesis v0.1 — aligned with frozen audit XVIII
