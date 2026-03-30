from __future__ import annotations

from pathlib import Path

from build_technical_paper_pdf import build_pdf


DOCS_DIR = Path(__file__).resolve().parent
SOURCE_PATH = DOCS_DIR / "MARKET_SIGNAL_INTERPRETATION_PROTOCOL_V0_1.md"
OUTPUT_PATH = DOCS_DIR / "MARKET_SIGNAL_INTERPRETATION_PROTOCOL_V0_1.pdf"


if __name__ == "__main__":
    path = build_pdf(
        source_path=SOURCE_PATH,
        output_path=OUTPUT_PATH,
        title="HAOS Genesis Market Signal Interpretation Protocol v0.1",
        author="Tomislav Rupic",
    )
    print(path)
