"""
dashboard_pdf_service.py — Render the recruiter scorecard HTML to PDF.

Uses WeasyPrint (HTML+CSS → PDF). Carries its own self-contained CSS
that mirrors the Streamlit visual but is tuned for A4 print:
slightly smaller type, no shadows on print, page-size aware.

If WeasyPrint isn't available (missing system libs), the import in
``report_view`` is wrapped in try/except so the screen just disables
the PDF download button instead of crashing.
"""

from __future__ import annotations

from io import BytesIO

from utils.logger import get_logger


logger = get_logger(__name__)


# Self-contained CSS — must match the visual of ui/streamlit/styles.py
# scorecard classes. Re-implemented (not imported) because Streamlit
# styles use selectors that don't apply to a standalone HTML page.
_PDF_CSS = """
@page {
    size: A4;
    margin: 16mm 14mm;
}
* { box-sizing: border-box; }
body {
    font-family: 'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 10pt;
    color: #18181B;
    margin: 0;
    background: white;
}
.scorecard {
    background: white;
    border: 1px solid #E4E4E7;
    border-radius: 14px;
    padding: 22px 26px;
}

/* HERO */
.scorecard-hero {
    display: flex; justify-content: space-between; align-items: center;
    gap: 18px;
    padding-bottom: 16px;
    border-bottom: 1px solid #E4E4E7;
    margin-bottom: 18px;
}
.scorecard-hero-left { display: flex; align-items: center; gap: 14px; }
.scorecard-avatar {
    width: 56px; height: 56px;
    border-radius: 50%;
    background: linear-gradient(135deg, #6366f1, #06b6d4);
    color: white;
    display: flex; align-items: center; justify-content: center;
    font-size: 18pt; font-weight: 700;
}
.scorecard-name {
    font-size: 17pt; font-weight: 800; line-height: 1.1;
    color: #18181B;
}
.scorecard-sub {
    color: #71717A;
    font-size: 9pt;
    margin-top: 3px;
}
.scorecard-sub-dot { color: #D4D4D8; margin: 0 4px; }

.scorecard-hero-right { text-align: right; }
.scorecard-score-num {
    font-size: 36pt;
    font-weight: 800;
    line-height: 1;
    color: #10b981;
}
.scorecard-score-suffix {
    font-size: 8pt; color: #71717A; margin-top: -2px;
    letter-spacing: 0.05em;
}
.scorecard-badge {
    display: inline-block;
    padding: 4px 11px;
    border-radius: 999px;
    font-size: 8pt; font-weight: 700;
    margin-top: 6px;
}
.scorecard-badge.yes { background: rgba(16,185,129,0.10); color: #047857; }
.scorecard-badge.no  { background: rgba(239,68,68,0.10); color: #b91c1c; }
.scorecard-badge.pending { background: #F4F4F5; color: #71717A; }

/* SECTIONS */
.scorecard-section { margin-bottom: 18px; }
.scorecard-section-label {
    font-size: 7.5pt; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.10em;
    color: #71717A;
    margin-bottom: 8px;
}
.scorecard-paragraph {
    font-size: 9.5pt; color: #3F3F46; line-height: 1.55;
}
.scorecard-empty {
    font-size: 9pt; color: #71717A; font-style: italic;
}

/* STRENGTHS / IMPROVEMENTS */
.scorecard-row-pair {
    display: table; width: 100%;
    margin-bottom: 18px;
}
.scorecard-row-pair > .scorecard-section {
    display: table-cell; width: 50%;
    padding-right: 16px;
    vertical-align: top;
}
.scorecard-row-pair > .scorecard-section:last-child { padding-right: 0; padding-left: 16px; }
.scorecard-bullet {
    display: flex; gap: 6px; align-items: flex-start;
    padding: 3px 0;
    font-size: 9pt; color: #3F3F46;
    line-height: 1.45;
}
.scorecard-bullet-tick { font-weight: 700; }

/* SCORE BREAKDOWN */
.scorecard-row {
    display: flex; align-items: center; gap: 12px;
    margin-bottom: 7px;
    font-size: 9pt;
}
.scorecard-row-label { flex: 0 0 130px; color: #3F3F46; }
.scorecard-row-track {
    flex: 1;
    height: 5px;
    background: #E4E4E7;
    border-radius: 999px;
    overflow: hidden;
}
.scorecard-row-bar {
    height: 100%;
    background: linear-gradient(90deg, #06b6d4, #10b981);
    border-radius: 999px;
}
.scorecard-row-num {
    flex: 0 0 22px;
    text-align: right;
    font-weight: 700;
    color: #18181B;
}

/* TRUST PROFILE (behavioral) */
.trust-section {
    margin-top: 18px;
    padding-top: 14px;
    border-top: 1px solid #E4E4E7;
}
.trust-summary {
    background: rgba(99,102,241,0.04);
    border-left: 3px solid #6366f1;
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 9pt; line-height: 1.5;
    color: #3F3F46;
    margin-bottom: 14px;
}
.trust-grid {
    display: table; width: 100%;
    margin-bottom: 14px;
}
.trust-radar {
    display: table-cell; width: 45%;
    vertical-align: middle;
    padding-right: 14px;
}
.trust-bars {
    display: table-cell; width: 55%;
    vertical-align: middle;
}
.trust-trait-row {
    display: flex; align-items: center; gap: 8px;
    margin-bottom: 5px;
    font-size: 9pt;
}
.trust-trait-icon { flex: 0 0 16px; }
.trust-trait-label { flex: 0 0 110px; color: #3F3F46; }
.trust-trait-track {
    flex: 1; height: 5px;
    background: #E4E4E7;
    border-radius: 999px;
}
.trust-trait-bar {
    height: 100%;
    background: linear-gradient(90deg, #6366f1, #06b6d4);
    border-radius: 999px;
}
.trust-trait-num {
    flex: 0 0 20px; text-align: right;
    font-weight: 700; color: #18181B;
}
.trust-signals {
    padding: 8px 12px;
    background: #F4F4F5;
    border-radius: 8px;
    margin-bottom: 12px;
    font-size: 8.5pt;
    color: #3F3F46;
}
.trust-signal-item { display: inline-block; margin-right: 12px; }
.trust-reasoning {
    background: white;
    border: 1px solid #E4E4E7;
    border-radius: 8px;
    padding: 10px 14px;
}
.trust-reason-item {
    display: flex; gap: 6px; align-items: flex-start;
    padding: 3px 0;
    font-size: 8.5pt; color: #3F3F46;
    line-height: 1.4;
}
.trust-reason-icon { flex: 0 0 16px; }
"""


def build_dashboard_pdf(dashboard_html: str) -> bytes:
    """Wrap the dashboard HTML in a printable page and return PDF bytes."""
    from weasyprint import HTML, CSS

    page = (
        "<!DOCTYPE html>"
        "<html><head><meta charset='utf-8'><title>Candidate Scorecard</title></head>"
        f"<body>{dashboard_html}</body></html>"
    )

    buf = BytesIO()
    HTML(string=page).write_pdf(
        target=buf,
        stylesheets=[CSS(string=_PDF_CSS)],
    )
    pdf_bytes = buf.getvalue()
    logger.info("Dashboard PDF built: %d bytes", len(pdf_bytes))
    return pdf_bytes
