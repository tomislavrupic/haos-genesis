from __future__ import annotations
from pathlib import Path

from .internal.plotting import render_graph_frame

def make_symbolic_video(trace, output_path: str) -> str:
    from moviepy.video.io.ImageSequenceClip import ImageSequenceClip

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    duration = 60.0 / max(len(trace), 1)
    frames = [render_graph_frame(entry["graph"], f"Level {entry['level']}") for entry in trace]
    clip = ImageSequenceClip(frames, durations=[duration] * len(frames))
    clip.write_videofile(str(path), fps=30, codec="libx264", audio=False, logger=None)
    clip.close()
    return str(path)
