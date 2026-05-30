"""
pdf_renderer.py — Convert a plain-text resume to a coloured A4 PDF.

UI-agnostic: any presentation layer (Streamlit today, FastAPI tomorrow)
can call ``render_resume_to_pdf()`` and receive bytes it can serve or
attach.
"""

from __future__ import annotations

from fpdf import FPDF

from constants.app_constants import SECTION_COLOURS_RGB
from utils.helpers import ascii_safe


def render_resume_to_pdf(resume_text: str, candidate_name: str = "Candidate") -> bytes:
    """Render the resume text as a one-page A4 PDF.

    Section headers are styled in the same accent colours used by the
    on-screen Streamlit cards. The header band (name + contact lines)
    gets a flat-colour blue rectangle.

    Args:
        resume_text:    The plain-text resume produced by the resume service.
        candidate_name: Fallback used in the header if the text is empty.

    Returns:
        Raw PDF bytes suitable for ``st.download_button`` or HTTP
        ``Content-Type: application/pdf`` responses.
    """
    pdf = FPDF(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(left=18, top=15, right=18)

    lines = resume_text.splitlines()
    header_lines: list[str] = []
    body_start = 0
    for i, raw in enumerate(lines):
        norm = raw.strip().rstrip(":").strip().lower()
        if norm in SECTION_COLOURS_RGB:
            body_start = i
            break
        if raw.strip():
            header_lines.append(raw.strip())
    else:
        body_start = len(lines)

    if not header_lines:
        header_lines = [candidate_name]
    name = header_lines[0]
    contact = header_lines[1:]

    # ── Header band (name + contact) ────────────────────────────────────
    pdf.set_fill_color(79, 142, 247)
    pdf.rect(x=0, y=0, w=210, h=32, style="F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_xy(18, 9)
    pdf.cell(0, 9, ascii_safe(name), ln=1)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(18, 19)
    pdf.cell(0, 5, ascii_safe(" | ".join(contact)) if contact else "", ln=1)
    pdf.set_y(40)
    pdf.set_text_color(0, 0, 0)

    # ── Body sections ───────────────────────────────────────────────────
    body_w = 210 - 18 - 18   # writable width after margins
    current_colour: tuple[int, int, int] | None = None

    for raw in lines[body_start:]:
        stripped = raw.strip()
        norm = stripped.rstrip(":").strip().lower()

        # Reset x to left margin before each line so the cursor cannot
        # drift past the right edge (which makes fpdf throw "not enough
        # horizontal space").
        pdf.set_x(18)

        if norm in SECTION_COLOURS_RGB:
            current_colour = SECTION_COLOURS_RGB[norm]
            pdf.ln(4)
            pdf.set_x(18)
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(*current_colour)
            pdf.multi_cell(body_w, 7, ascii_safe(stripped.rstrip(":").upper()))
            y = pdf.get_y()
            pdf.set_draw_color(*current_colour)
            pdf.set_line_width(0.6)
            pdf.line(18, y, 192, y)
            pdf.ln(2)
            pdf.set_text_color(0, 0, 0)
            continue

        if not stripped:
            pdf.ln(2)
            continue

        # Body line — bullet or paragraph. One multi_cell per line.
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)
        if stripped.startswith(("-", "•", "*")):
            text = stripped.lstrip("-•* ").strip()
            pdf.multi_cell(body_w, 5, ascii_safe(f"  - {text}"))
        else:
            pdf.multi_cell(body_w, 5, ascii_safe(stripped))

    raw_bytes = pdf.output(dest="S")
    return bytes(raw_bytes) if not isinstance(raw_bytes, bytes) else raw_bytes
