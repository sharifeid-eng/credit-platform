"""
PDF Export for IC Memos.

Generates dark-themed PDFs matching the Laith platform branding:
  - Navy background, gold headers, teal/red metric callouts
  - Cover page with LAITH wordmark and memo metadata
  - Table of contents
  - One page per section with metric callout boxes
  - DRAFT watermark when status != 'final'
  - Source citations as footnotes

Reuses styling patterns from core/research_report.py.
"""

import logging
from datetime import datetime
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white, Color
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable, Flowable,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY

logger = logging.getLogger(__name__)

# ── Brand colours (same as research_report.py) ──────────────────────────────

NAVY   = HexColor('#121C27')
GOLD   = HexColor('#C9A84C')
TEAL   = HexColor('#2DD4BF')
RED    = HexColor('#F06060')
BLUE   = HexColor('#5B8DEF')
MUTED  = HexColor('#8494A7')
BORDER = HexColor('#243040')
SURF   = HexColor('#172231')
TEXT   = HexColor('#E8EAF0')
DEEP   = HexColor('#0A1119')

# Assessment colors for metric callouts
_ASSESSMENT_COLORS = {
    "healthy": TEAL,
    "warning": GOLD,
    "critical": RED,
    "neutral": BLUE,
    "monitor": MUTED,
}

# Watermark color (semi-transparent red for DRAFT)
WATERMARK_COLOR = Color(0.94, 0.38, 0.38, alpha=0.08)


# ── Styles ──────────────────────────────────────────────────────────────────

def _build_styles() -> dict:
    """Build the PDF style sheet for memos."""
    styles = {}

    styles['body'] = ParagraphStyle(
        'memo_body', fontName='Helvetica', fontSize=9, textColor=TEXT,
        leading=14, alignment=TA_JUSTIFY, spaceAfter=6,
    )
    styles['body_small'] = ParagraphStyle(
        'memo_body_small', fontName='Helvetica', fontSize=8, textColor=MUTED,
        leading=11, spaceAfter=4,
    )
    styles['heading1'] = ParagraphStyle(
        'memo_h1', fontName='Helvetica-Bold', fontSize=16, textColor=GOLD,
        spaceBefore=16, spaceAfter=8, leading=20,
    )
    styles['heading2'] = ParagraphStyle(
        'memo_h2', fontName='Helvetica-Bold', fontSize=12, textColor=GOLD,
        spaceBefore=12, spaceAfter=6, leading=16,
    )
    styles['heading3'] = ParagraphStyle(
        'memo_h3', fontName='Helvetica-Bold', fontSize=10, textColor=TEXT,
        spaceBefore=8, spaceAfter=4, leading=13,
    )
    styles['metric_value'] = ParagraphStyle(
        'memo_metric_val', fontName='Helvetica-Bold', fontSize=11,
        textColor=TEAL, leading=14, alignment=TA_CENTER,
    )
    styles['metric_label'] = ParagraphStyle(
        'memo_metric_lbl', fontName='Helvetica', fontSize=7, textColor=MUTED,
        leading=9, alignment=TA_CENTER, spaceAfter=4,
    )
    styles['cover_title'] = ParagraphStyle(
        'memo_cover_title', fontName='Helvetica-Bold', fontSize=28,
        textColor=TEXT, alignment=TA_CENTER, spaceAfter=8, leading=34,
    )
    styles['cover_subtitle'] = ParagraphStyle(
        'memo_cover_sub', fontName='Helvetica', fontSize=14, textColor=GOLD,
        alignment=TA_CENTER, spaceAfter=4, leading=18,
    )
    styles['cover_meta'] = ParagraphStyle(
        'memo_cover_meta', fontName='Helvetica', fontSize=10, textColor=MUTED,
        alignment=TA_CENTER, spaceAfter=4, leading=14,
    )
    styles['toc_title'] = ParagraphStyle(
        'memo_toc_title', fontName='Helvetica-Bold', fontSize=14,
        textColor=GOLD, spaceAfter=12, spaceBefore=20,
    )
    styles['toc_entry'] = ParagraphStyle(
        'memo_toc_entry', fontName='Helvetica', fontSize=10, textColor=TEXT,
        leading=16, spaceAfter=2, leftIndent=20,
    )
    styles['citation'] = ParagraphStyle(
        'memo_citation', fontName='Helvetica', fontSize=7, textColor=MUTED,
        leading=9, leftIndent=12, spaceAfter=2,
    )
    styles['conclusion'] = ParagraphStyle(
        'memo_conclusion', fontName='Helvetica-Bold', fontSize=9,
        textColor=GOLD, leading=14, spaceBefore=6, spaceAfter=8,
        leftIndent=12, borderColor=GOLD, borderWidth=1, borderPadding=6,
    )
    styles['footer'] = ParagraphStyle(
        'memo_footer', fontName='Helvetica', fontSize=7, textColor=MUTED,
        alignment=TA_CENTER,
    )

    return styles


# ── Page templates ──────────────────────────────────────────────────────────

class _MemoPageTemplate:
    """Holds memo metadata for page rendering callbacks."""

    def __init__(self, memo: dict):
        self.memo = memo
        self.is_draft = memo.get("status", "draft") != "final"
        self.title = memo.get("title", "IC Memo")

    def page_bg(self, canvas, doc):
        """Draw dark background on every content page."""
        w, h = A4
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, 0, w, h, fill=1, stroke=0)

        # Footer
        canvas.setFillColor(MUTED)
        canvas.setFont('Helvetica', 7)
        canvas.drawCentredString(
            w / 2, 20,
            'CONFIDENTIAL  |  Generated by LAITH Analytics Platform  '
            '|  Amwal Capital Partners'
        )
        canvas.drawRightString(w - 0.7 * inch, 20, f'Page {doc.page}')

        # Gold accent line at top
        canvas.setStrokeColor(GOLD)
        canvas.setLineWidth(2)
        canvas.line(
            0.7 * inch, h - 0.5 * inch,
            w - 0.7 * inch, h - 0.5 * inch,
        )

        # DRAFT watermark
        if self.is_draft:
            canvas.saveState()
            canvas.setFillColor(WATERMARK_COLOR)
            canvas.setFont('Helvetica-Bold', 72)
            canvas.translate(w / 2, h / 2)
            canvas.rotate(45)
            canvas.drawCentredString(0, 0, 'DRAFT')
            canvas.restoreState()

        canvas.restoreState()

    def cover_bg(self, canvas, doc):
        """Draw cover page background."""
        w, h = A4
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, 0, w, h, fill=1, stroke=0)

        # Gold border
        canvas.setStrokeColor(GOLD)
        canvas.setLineWidth(2)
        margin = 0.5 * inch
        canvas.rect(
            margin, margin, w - 2 * margin, h - 2 * margin,
            fill=0, stroke=1,
        )

        # LAITH wordmark at top
        canvas.setFillColor(TEXT)
        canvas.setFont('Helvetica-Bold', 36)
        x_center = w / 2
        canvas.drawCentredString(x_center - 20, h - 2.5 * inch, 'L')
        canvas.setFillColor(GOLD)
        canvas.drawCentredString(x_center, h - 2.5 * inch, 'AI')
        canvas.setFillColor(TEXT)
        canvas.drawCentredString(x_center + 22, h - 2.5 * inch, 'TH')

        # DRAFT watermark on cover too
        if self.is_draft:
            canvas.saveState()
            canvas.setFillColor(WATERMARK_COLOR)
            canvas.setFont('Helvetica-Bold', 90)
            canvas.translate(w / 2, h / 2 - 1.5 * inch)
            canvas.rotate(45)
            canvas.drawCentredString(0, 0, 'DRAFT')
            canvas.restoreState()

        # Confidentiality banner at bottom
        canvas.setFillColor(SURF)
        canvas.rect(margin, margin, w - 2 * margin, 0.6 * inch,
                     fill=1, stroke=0)
        canvas.setFillColor(MUTED)
        canvas.setFont('Helvetica', 7)
        canvas.drawCentredString(
            w / 2, margin + 0.3 * inch,
            'STRICTLY PRIVATE AND CONFIDENTIAL  '
            '|  FOR INVESTMENT COMMITTEE USE ONLY'
        )
        canvas.drawCentredString(
            w / 2, margin + 0.15 * inch,
            f'Report generated {datetime.now().strftime("%d %B %Y")}  '
            '|  Amwal Capital Partners'
        )

        canvas.restoreState()


# ── Table helpers ───────────────────────────────────────────────────────────

def _make_metric_table(metrics: list, styles: dict) -> Table:
    """Create a metrics callout box (horizontal strip of KPI cards)."""
    if not metrics:
        return Spacer(1, 0)

    # Up to 4 metrics per row
    display_metrics = metrics[:6]
    cols = min(len(display_metrics), 4)

    # Build rows: value row + label row
    value_cells = []
    label_cells = []

    for m in display_metrics[:cols]:
        color = _ASSESSMENT_COLORS.get(m.get("assessment", "neutral"), BLUE)
        value_style = ParagraphStyle(
            'mv', fontName='Helvetica-Bold', fontSize=11,
            textColor=color, leading=14, alignment=TA_CENTER,
        )
        value_cells.append(Paragraph(str(m.get("value", "--")), value_style))
        label_cells.append(Paragraph(
            str(m.get("label", "")), styles['metric_label']
        ))

    page_w = A4[0] - 2 * 0.7 * inch
    col_w = page_w / cols

    data = [value_cells, label_cells]
    t = Table(data, colWidths=[col_w] * cols)

    style_commands = [
        ('BACKGROUND', (0, 0), (-1, -1), SURF),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, BORDER),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
    ]
    t.setStyle(TableStyle(style_commands))
    return t


def _make_data_table(headers: list, rows: list) -> Table:
    """Create a styled data table matching Laith dark theme."""
    data = [headers] + rows
    page_w = A4[0] - 2 * 0.7 * inch
    col_widths = [page_w / len(headers)] * len(headers)

    t = Table(data, colWidths=col_widths, repeatRows=1)
    style_commands = [
        ('BACKGROUND', (0, 0), (-1, 0), SURF),
        ('TEXTCOLOR', (0, 0), (-1, 0), GOLD),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('TEXTCOLOR', (0, 1), (-1, -1), TEXT),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, GOLD),
        ('LINEBELOW', (0, 1), (-1, -1), 0.25, BORDER),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]

    for i in range(1, len(data)):
        if i % 2 == 0:
            style_commands.append(('BACKGROUND', (0, i), (-1, i), SURF))

    t.setStyle(TableStyle(style_commands))
    return t


# ── Content builders ────────────────────────────────────────────────────────

def _build_cover(memo: dict, styles: dict) -> list:
    """Build the cover page content."""
    story = []

    story.append(Spacer(1, 3 * inch))

    # Memo type badge
    template_name = memo.get("template_name", "IC Memo")
    story.append(Paragraph(template_name.upper(), styles['cover_meta']))
    story.append(Spacer(1, 8))

    # Main title
    title = memo.get("title", "Investment Committee Memo")
    story.append(Paragraph(title, styles['cover_title']))
    story.append(Spacer(1, 12))

    # Company / Product
    company = memo.get("company", "")
    product = memo.get("product", "")
    story.append(Paragraph(
        f"{company} / {product}", styles['cover_subtitle']
    ))
    story.append(Spacer(1, 24))

    # Metadata
    created = memo.get("created_at", "")
    if created:
        try:
            dt = datetime.fromisoformat(created)
            created = dt.strftime("%d %B %Y")
        except (ValueError, TypeError):
            pass
    story.append(Paragraph(f"Date: {created}", styles['cover_meta']))

    status = memo.get("status", "draft").upper()
    version = memo.get("version", 1)
    story.append(Paragraph(
        f"Status: {status}  |  Version: {version}",
        styles['cover_meta'],
    ))

    snapshot = memo.get("snapshot", "")
    if snapshot:
        story.append(Paragraph(f"Snapshot: {snapshot}", styles['cover_meta']))

    story.append(PageBreak())
    return story


def _build_toc(memo: dict, styles: dict) -> list:
    """Build the table of contents."""
    story = []
    story.append(Paragraph("Table of Contents", styles['toc_title']))

    sections = memo.get("sections", [])
    for i, section in enumerate(sections, 1):
        title = section.get("title", f"Section {i}")
        story.append(Paragraph(
            f"{i}. {title}", styles['toc_entry']
        ))

    story.append(PageBreak())
    return story


def _build_section(section: dict, section_num: int,
                   styles: dict) -> list:
    """Build one memo section as PDF flowables."""
    story = []

    # Section heading
    title = section.get("title", f"Section {section_num}")
    story.append(Paragraph(f"{section_num}. {title}", styles['heading1']))

    # Metrics callout box (if any)
    metrics = section.get("metrics", [])
    if metrics:
        story.append(Spacer(1, 6))
        story.append(_make_metric_table(metrics, styles))
        story.append(Spacer(1, 10))

    # Section content
    content = section.get("content", "")
    if content:
        # Split content into paragraphs and render each
        paragraphs = content.split("\n\n")
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Detect sub-headings (lines starting with ## or **)
            if para.startswith("## "):
                story.append(Paragraph(
                    para[3:], styles['heading2']
                ))
            elif para.startswith("### "):
                story.append(Paragraph(
                    para[4:], styles['heading3']
                ))
            elif para.startswith("- ") or para.startswith("  - "):
                # Bullet list — render each line
                for line in para.split("\n"):
                    line = line.strip()
                    if line.startswith("- "):
                        line = line[2:]
                    # Use bullet character
                    story.append(Paragraph(
                        f"\u2022  {_escape_xml(line)}",
                        styles['body'],
                    ))
            else:
                story.append(Paragraph(
                    _escape_xml(para), styles['body']
                ))

    # Citations (as footnotes)
    citations = section.get("citations", [])
    if citations:
        story.append(Spacer(1, 8))
        story.append(HRFlowable(
            width="40%", thickness=0.5, color=BORDER,
            spaceAfter=4, spaceBefore=4,
        ))
        for cite in citations:
            idx = cite.get("index", "")
            source = cite.get("source", "")
            snippet = cite.get("snippet", "")
            cite_text = f"[{idx}] {source}"
            if snippet:
                cite_text += f" \u2014 {snippet[:80]}"
            story.append(Paragraph(
                _escape_xml(cite_text), styles['citation']
            ))

    # Generation metadata
    generated_by = section.get("generated_by", "")
    if generated_by:
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            f"Generated by: {generated_by}",
            styles['body_small'],
        ))

    story.append(PageBreak())
    return story


def _escape_xml(text: str) -> str:
    """Escape XML special characters for ReportLab Paragraph."""
    if not text:
        return ""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# ── Public API ──────────────────────────────────────────────────────────────

def export_memo_pdf(memo: dict, company: str, product: str) -> bytes:
    """Generate a dark-themed PDF from a memo dict.

    Uses the same styling as core/research_report.py:
      - Navy background, gold headers, teal/red metrics
      - Cover page with LAITH branding
      - TOC
      - One page per section with metrics callout boxes
      - DRAFT watermark if status != 'final'
      - Source citations as footnotes

    Args:
        memo: Full memo dict (from MemoGenerator or MemoStorage).
        company: Company name (for metadata).
        product: Product name (for metadata).

    Returns:
        PDF file as bytes.
    """
    buf = BytesIO()
    styles = _build_styles()
    page_tmpl = _MemoPageTemplate(memo)

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.6 * inch,
    )

    # Build the story (sequence of flowables)
    story = []

    # Cover page
    story.extend(_build_cover(memo, styles))

    # Table of contents
    story.extend(_build_toc(memo, styles))

    # Sections
    sections = memo.get("sections", [])
    for i, section in enumerate(sections, 1):
        story.extend(_build_section(section, i, styles))

    # Build PDF with page templates
    def _on_first_page(canvas, doc):
        page_tmpl.cover_bg(canvas, doc)

    def _on_later_pages(canvas, doc):
        page_tmpl.page_bg(canvas, doc)

    doc.build(
        story,
        onFirstPage=_on_first_page,
        onLaterPages=_on_later_pages,
    )

    pdf_bytes = buf.getvalue()
    buf.close()

    logger.info(
        "Generated memo PDF: %s (%d bytes, %d sections)",
        memo.get("title", "untitled"),
        len(pdf_bytes),
        len(sections),
    )
    return pdf_bytes
