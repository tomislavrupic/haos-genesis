from __future__ import annotations

from pathlib import Path

from build_technical_paper_pdf import build_pdf


DOCS_DIR = Path(__file__).resolve().parent
SOURCE_PATH = DOCS_DIR / "HAOS_GENESIS_SENSOR_TRADING_PAPER.md"
OUTPUT_PATH = DOCS_DIR / "HAOS_GENESIS_SENSOR_TRADING_PAPER.pdf"


if __name__ == "__main__":
    path = build_pdf(
        source_path=SOURCE_PATH,
        output_path=OUTPUT_PATH,
        title="HAOS Genesis Sensor and Trading Adapter Paper",
        author="Tomislav Rupic",
    )
    print(path)
