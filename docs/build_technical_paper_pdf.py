from __future__ import annotations

import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, Preformatted, SimpleDocTemplate, Spacer


DOCS_DIR = Path(__file__).resolve().parent
SOURCE_PATH = DOCS_DIR / "HAOS_GENESIS_TECHNICAL_PAPER.md"
OUTPUT_PATH = DOCS_DIR / "HAOS_GENESIS_TECHNICAL_PAPER.pdf"


def _page_number(canvas, _doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawRightString(A4[0] - 40, 20, str(canvas.getPageNumber()))
    canvas.restoreState()


def _inline_markup(text: str) -> str:
    escaped = escape(text)

    def replace_code(match: re.Match[str]) -> str:
        return f"<font name='Courier'>{escape(match.group(1))}</font>"

    return re.sub(r"`([^`]+)`", replace_code, escaped)


def _scaled_image(path: Path, max_width: float) -> Image:
    image = Image(str(path))
    width = min(max_width, image.imageWidth)
    scale = width / float(image.imageWidth)
    image.drawWidth = width
    image.drawHeight = float(image.imageHeight) * scale
    return image


def build_pdf(
    source_path: Path = SOURCE_PATH,
    output_path: Path = OUTPUT_PATH,
    title: str = "HAOS Genesis Technical Paper",
    author: str = "Tomislav Rupic",
) -> Path:
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitlePaper",
        parent=styles["Title"],
        fontName="Times-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=16,
    )
    h1_style = ParagraphStyle(
        "Heading1Paper",
        parent=styles["Heading1"],
        fontName="Times-Bold",
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=14,
        spaceAfter=8,
    )
    h2_style = ParagraphStyle(
        "Heading2Paper",
        parent=styles["Heading2"],
        fontName="Times-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodyPaper",
        parent=styles["BodyText"],
        fontName="Times-Roman",
        fontSize=10.5,
        leading=14,
        spaceAfter=6,
    )
    bullet_style = ParagraphStyle(
        "BulletPaper",
        parent=body_style,
        leftIndent=14,
        firstLineIndent=-8,
    )
    code_style = ParagraphStyle(
        "CodePaper",
        parent=body_style,
        fontName="Courier",
        fontSize=9,
        leading=11,
        leftIndent=10,
        rightIndent=10,
        backColor=colors.HexColor("#f8fafc"),
        borderWidth=0.5,
        borderColor=colors.HexColor("#cbd5e1"),
        borderPadding=6,
        spaceAfter=8,
    )
    caption_style = ParagraphStyle(
        "CaptionPaper",
        parent=body_style,
        fontName="Helvetica-Oblique",
        fontSize=8.5,
        leading=10,
        textColor=colors.HexColor("#475569"),
        alignment=1,
        spaceAfter=10,
    )

    story = []
    paragraph_buffer: list[str] = []
    code_lines: list[str] = []
    in_code = False

    def flush_paragraph() -> None:
        nonlocal paragraph_buffer
        if paragraph_buffer:
            story.append(Paragraph(_inline_markup(" ".join(part.strip() for part in paragraph_buffer if part.strip())), body_style))
            paragraph_buffer = []

    for raw_line in source_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_paragraph()
            if in_code:
                story.append(Preformatted("\n".join(code_lines), code_style))
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not stripped:
            flush_paragraph()
            continue
        if stripped.startswith("# "):
            flush_paragraph()
            story.append(Paragraph(_inline_markup(stripped[2:]), title_style))
            continue
        if stripped.startswith("## "):
            flush_paragraph()
            story.append(Paragraph(_inline_markup(stripped[3:]), h1_style))
            continue
        if stripped.startswith("### "):
            flush_paragraph()
            story.append(Paragraph(_inline_markup(stripped[4:]), h2_style))
            continue
        image_match = re.match(r"!\[(.*?)\]\((.*?)\)", stripped)
        if image_match:
            flush_paragraph()
            image_path = (source_path.parent / image_match.group(2)).resolve()
            if image_path.exists():
                story.append(_scaled_image(image_path, max_width=6.6 * inch))
                story.append(Spacer(1, 0.08 * inch))
            continue
        if re.match(r"^\d+\.\s+", stripped):
            flush_paragraph()
            story.append(Paragraph(_inline_markup(stripped), bullet_style))
            continue
        if stripped.startswith("- "):
            flush_paragraph()
            story.append(Paragraph(_inline_markup(stripped), bullet_style))
            continue
        paragraph_buffer.append(stripped)

    flush_paragraph()

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=50,
        rightMargin=50,
        topMargin=48,
        bottomMargin=40,
        title=title,
        author=author,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.build(story, onFirstPage=_page_number, onLaterPages=_page_number)
    return output_path


if __name__ == "__main__":
    path = build_pdf()
    print(path)
