"""
core/compliance_cert.py
Borrowing Base Certificate (BBC) PDF generation.
Pure computation — no FastAPI, no I/O beyond writing the PDF bytes.
"""
from datetime import datetime, timezone
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    KeepTogether,
)
from reportlab.lib import colors

# ── Brand colours ────────────────────────────────────────────────────────────
NAVY   = HexColor('#121C27')
GOLD   = HexColor('#C9A84C')
TEAL   = HexColor('#2DD4BF')
RED    = HexColor('#F06060')
MUTED  = HexColor('#8494A7')
BORDER = HexColor('#243040')
SURF   = HexColor('#172231')


def _fmt(v, ccy='AED'):
    """Format a number as currency millions."""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return '—'
    return f'{ccy} {n / 1_000_000:,.2f}M'


def _pct(v):
    try:
        return f'{float(v):.1f}%'
    except (TypeError, ValueError):
        return '—'


def _style():
    styles = getSampleStyleSheet()
    normal = ParagraphStyle(
        'body',
        fontName='Helvetica',
        fontSize=9,
        textColor=HexColor('#E8EAF0'),
        leading=13,
    )
    heading = ParagraphStyle(
        'heading',
        fontName='Helvetica-Bold',
        fontSize=11,
        textColor=GOLD,
        spaceAfter=4,
        spaceBefore=10,
    )
    sub = ParagraphStyle(
        'sub',
        fontName='Helvetica',
        fontSize=8,
        textColor=MUTED,
        leading=11,
    )
    cert = ParagraphStyle(
        'cert',
        fontName='Helvetica-Oblique',
        fontSize=8,
        textColor=MUTED,
        leading=12,
    )
    return normal, heading, sub, cert


def _section_table(headers, rows, col_widths, ccy='AED'):
    """Build a styled ReportLab Table."""
    data = [headers] + rows
    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    n_cols = len(headers)
    tbl.setStyle(TableStyle([
        # Header row
        ('BACKGROUND',    (0, 0), (-1, 0), SURF),
        ('TEXTCOLOR',     (0, 0), (-1, 0), GOLD),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, 0), 7.5),
        ('ALIGN',         (0, 0), (-1, 0), 'LEFT'),
        ('ALIGN',         (1, 0), (-1, 0), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
        ('TOPPADDING',    (0, 0), (-1, 0), 5),
        # Body rows
        ('FONTNAME',      (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',      (0, 1), (-1, -1), 8),
        ('TEXTCOLOR',     (0, 1), (-1, -1), HexColor('#E8EAF0')),
        ('ALIGN',         (0, 1), (0,  -1), 'LEFT'),
        ('ALIGN',         (1, 1), (-1, -1), 'RIGHT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [NAVY, SURF]),
        ('LINEBELOW',     (0, 0), (-1, 0), 0.5, BORDER),
        ('LINEBELOW',     (0, -1), (-1, -1), 0.5, BORDER),
        ('TOPPADDING',    (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
    ]))
    return tbl


def generate_compliance_cert(
    bb_data: dict,
    conc_data: dict,
    cov_data: dict,
    company: str,
    product: str,
    currency: str = 'AED',
    officer_name: str = '',
) -> bytes:
    """
    Generate a Borrowing Base Certificate PDF.
    Returns raw PDF bytes.

    Parameters
    ----------
    bb_data   : response from portfolio/borrowing-base endpoint
    conc_data : response from portfolio/concentration-limits endpoint
    cov_data  : response from portfolio/covenants endpoint
    company   : company slug (display name)
    product   : product slug (display name)
    currency  : display currency symbol
    officer_name : optional officer name on signature line
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=0.65 * inch, rightMargin=0.65 * inch,
        topMargin=0.65 * inch,  bottomMargin=0.65 * inch,
        title='Borrowing Base Certificate',
    )

    normal, heading, sub, cert = _style()
    W = A4[0] - 1.3 * inch   # usable width

    now   = datetime.now(timezone.utc)
    today = now.strftime('%d %B %Y')
    kpis  = bb_data.get('kpis', {})
    snap  = bb_data.get('snapshot', today)
    ccy   = currency or 'AED'

    story = []

    # ── Cover Header ─────────────────────────────────────────────────────────
    cover_data = [[
        Paragraph(
            f'<font color="#C9A84C"><b>LAITH</b></font> '
            f'<font color="#E8EAF0">BORROWING BASE CERTIFICATE</font>',
            ParagraphStyle('cover_title', fontName='Helvetica-Bold', fontSize=16,
                           textColor=HexColor('#E8EAF0'), leading=20),
        ),
        Paragraph(
            f'<font color="#8494A7">Prepared: {today}<br/>Portfolio Company: '
            f'{company.upper()}<br/>Product: {product.replace("_", " ").title()}<br/>'
            f'Data as of: {snap}</font>',
            ParagraphStyle('cover_sub', fontName='Helvetica', fontSize=8,
                           textColor=MUTED, leading=13, alignment=2),
        ),
    ]]
    cov_tbl = Table(cover_data, colWidths=[W * 0.6, W * 0.4])
    cov_tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), SURF),
        ('TOPPADDING',    (0, 0), (-1, -1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 14),
        ('LEFTPADDING',   (0, 0), (-1, -1), 12),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 12),
        ('LINEBELOW', (0, 0), (-1, -1), 1.5, GOLD),
    ]))
    story.append(cov_tbl)
    story.append(Spacer(1, 14))

    # ── Section 1: Facility Summary KPIs ────────────────────────────────────
    story.append(Paragraph('1. Facility Summary', heading))
    story.append(HRFlowable(width=W, thickness=0.5, color=BORDER, spaceAfter=8))

    facility = bb_data.get('facility', {})
    kpi_rows = [
        ['Gross A/R Pool',     _fmt(kpis.get('total_ar'), ccy),     'Facility Limit',  _fmt(facility.get('limit'), ccy)],
        ['Eligible A/R',       _fmt(kpis.get('eligible_ar'), ccy),  'Facility Outstanding', _fmt(facility.get('outstanding'), ccy)],
        ['Borrowing Base',     _fmt(kpis.get('borrowing_base'), ccy), 'Available to Draw', _fmt(kpis.get('available_to_draw'), ccy)],
        ['Ineligible A/R',     _fmt(kpis.get('ineligible'), ccy),   'Utilisation',
            _pct((facility.get('outstanding', 0) / facility.get('limit', 1) * 100) if facility.get('limit') else 0)],
    ]
    kpi_tbl = Table(kpi_rows, colWidths=[W * 0.22, W * 0.25, W * 0.26, W * 0.27])
    kpi_tbl.setStyle(TableStyle([
        ('FONTNAME',  (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE',  (0, 0), (-1, -1), 8),
        ('TEXTCOLOR', (0, 0), (0, -1), MUTED),
        ('TEXTCOLOR', (1, 0), (1, -1), HexColor('#E8EAF0')),
        ('TEXTCOLOR', (2, 0), (2, -1), MUTED),
        ('TEXTCOLOR', (3, 0), (3, -1), HexColor('#E8EAF0')),
        ('FONTNAME',  (1, 0), (1, -1), 'Helvetica-Bold'),
        ('FONTNAME',  (3, 0), (3, -1), 'Helvetica-Bold'),
        ('ALIGN',     (1, 0), (1, -1), 'RIGHT'),
        ('ALIGN',     (3, 0), (3, -1), 'RIGHT'),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [NAVY, SURF]),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ('LINEBELOW',  (0, -1), (-1, -1), 0.5, BORDER),
    ]))
    story.append(kpi_tbl)
    story.append(Spacer(1, 14))

    # ── Section 2: Borrowing Base Waterfall ──────────────────────────────────
    story.append(Paragraph('2. Borrowing Base Waterfall', heading))
    story.append(HRFlowable(width=W, thickness=0.5, color=BORDER, spaceAfter=8))

    waterfall = bb_data.get('waterfall', [])
    if waterfall:
        wf_rows = []
        for row in waterfall:
            label   = row.get('label', '')
            amount  = row.get('amount')
            pct_str = _pct(row.get('pct', '')) if row.get('pct') is not None else ''
            indent  = '    ' * row.get('indent', 0)
            wf_rows.append([indent + label, _fmt(amount, ccy) if amount is not None else '', pct_str])
        wf_tbl = _section_table(
            ['Step', 'Amount', '%'],
            wf_rows,
            [W * 0.60, W * 0.25, W * 0.15],
            ccy,
        )
        story.append(wf_tbl)
    else:
        story.append(Paragraph('No waterfall data available.', sub))
    story.append(Spacer(1, 14))

    # ── Section 3: Concentration Limits ─────────────────────────────────────
    story.append(Paragraph('3. Concentration Limits', heading))
    story.append(HRFlowable(width=W, thickness=0.5, color=BORDER, spaceAfter=8))

    limits = conc_data.get('limits', [])
    if limits:
        cl_rows = []
        for lim in limits:
            compliant = lim.get('compliant')  # may be None for proxy/data-gap limits
            if compliant is None:
                status = 'UNVERIFIED'
            else:
                status = 'COMPLIANT' if compliant else 'BREACH'
            cl_rows.append([
                lim.get('name', ''),
                _fmt(lim.get('current_value'), ccy),
                _pct(lim.get('utilisation_pct', '')),
                _pct(lim.get('limit_pct', '')),
                status,
            ])
        cl_tbl = _section_table(
            ['Limit', 'Exposure', 'Util.', 'Threshold', 'Status'],
            cl_rows,
            [W * 0.32, W * 0.20, W * 0.12, W * 0.16, W * 0.20],
            ccy,
        )
        # Color status column. None (UNVERIFIED) renders gold/amber so the
        # certificate doesn't mislead with a false PASS/FAIL on a proxy field.
        try:
            from reportlab.lib.colors import HexColor
            GOLD = HexColor('#C9A84C')
        except Exception:
            GOLD = TEAL  # fallback if HexColor not importable
        for i, lim in enumerate(limits):
            row_idx = i + 1  # 0 is header
            compliant = lim.get('compliant')
            color = GOLD if compliant is None else (TEAL if compliant else RED)
            cl_tbl.setStyle(TableStyle([
                ('TEXTCOLOR', (4, row_idx), (4, row_idx), color),
                ('FONTNAME',  (4, row_idx), (4, row_idx), 'Helvetica-Bold'),
            ]))
        story.append(cl_tbl)
    else:
        story.append(Paragraph('No concentration limit data available.', sub))
    story.append(Spacer(1, 14))

    # ── Section 4: Covenants ─────────────────────────────────────────────────
    story.append(Paragraph('4. Financial Covenants', heading))
    story.append(HRFlowable(width=W, thickness=0.5, color=BORDER, spaceAfter=8))

    covenants = cov_data.get('covenants', [])
    if covenants:
        cv_rows = []
        for cv in covenants:
            compliant  = cv.get('compliant', True)
            status = 'COMPLIANT' if compliant else 'BREACH'
            cv_val = cv.get('value')
            cv_thr = cv.get('threshold')
            val_str = _pct(cv_val * 100) if cv_val is not None and abs(cv_val) < 100 else _fmt(cv_val, ccy)
            thr_str = _pct(cv_thr * 100) if cv_thr is not None and abs(cv_thr) < 100 else _fmt(cv_thr, ccy)
            try:
                # Values < 2 are likely rates (0–1 scale), format as %
                float(cv_val)
                float(cv_thr)
                if abs(float(cv_val)) <= 2 and abs(float(cv_thr)) <= 2:
                    val_str = _pct(float(cv_val) * 100)
                    thr_str = _pct(float(cv_thr) * 100)
                else:
                    val_str = _fmt(float(cv_val), ccy)
                    thr_str = _fmt(float(cv_thr), ccy)
            except (TypeError, ValueError):
                pass
            cv_rows.append([cv.get('name', ''), val_str, thr_str, status])
        cv_tbl = _section_table(
            ['Covenant', 'Actual', 'Threshold', 'Status'],
            cv_rows,
            [W * 0.44, W * 0.18, W * 0.18, W * 0.20],
            ccy,
        )
        for i, cv in enumerate(covenants):
            row_idx = i + 1
            is_compliant = cv.get('compliant', True)
            cv_tbl.setStyle(TableStyle([
                ('TEXTCOLOR', (3, row_idx), (3, row_idx), TEAL if is_compliant else RED),
                ('FONTNAME',  (3, row_idx), (3, row_idx), 'Helvetica-Bold'),
            ]))
        story.append(cv_tbl)
    else:
        story.append(Paragraph('No covenant data available.', sub))
    story.append(Spacer(1, 20))

    # ── Section 5: Officer Certification ────────────────────────────────────
    story.append(HRFlowable(width=W, thickness=1, color=BORDER, spaceAfter=10))
    story.append(Paragraph('5. Officer Certification', heading))

    cert_text = (
        'The undersigned authorized officer of the Borrower hereby certifies that, '
        'as of the date set forth above: (i) this Borrowing Base Certificate has been '
        'prepared in accordance with the Credit Agreement and the information contained '
        'herein is true, accurate and complete in all material respects; (ii) no Default '
        'or Event of Default exists; and (iii) the representations and warranties of the '
        'Borrower set forth in the Credit Agreement are true and correct as of the date '
        'hereof.'
    )
    story.append(Paragraph(cert_text, cert))
    story.append(Spacer(1, 20))

    sig_data = [
        ['Authorized Officer', 'Title', 'Date'],
        [officer_name or '________________________', '________________________', today],
    ]
    sig_tbl = Table(sig_data, colWidths=[W / 3, W / 3, W / 3])
    sig_tbl.setStyle(TableStyle([
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, -1), 8),
        ('TEXTCOLOR',     (0, 0), (-1, 0), MUTED),
        ('TEXTCOLOR',     (0, 1), (-1, 1), HexColor('#E8EAF0')),
        ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LINEABOVE',     (0, 1), (-1, 1), 0.5, BORDER),
    ]))
    story.append(KeepTogether(sig_tbl))
    story.append(Spacer(1, 8))

    conf_note = (
        '<font color="#8494A7"><i>CONFIDENTIAL — This certificate is prepared for '
        'the internal use of the Fund and its lenders only. Not for distribution. '
        'Generated by LAITH Analytics Platform.</i></font>'
    )
    story.append(Paragraph(conf_note, ParagraphStyle(
        'footnote', fontName='Helvetica-Oblique', fontSize=7,
        textColor=MUTED, leading=10, alignment=1,
    )))

    # ── Build PDF with dark background ──────────────────────────────────────
    def _on_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        canvas.restoreState()

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()
