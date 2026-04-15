"""
core/research_report.py
========================
Platform-level credit research report generator.

Produces a comprehensive PDF research report for any company on the platform,
combining parsed analytical data with AI-generated narrative sections.

Works across all analysis types:
  - tamara_summary: BNPL data room analysis
  - ejari_summary:  RNPL pre-computed workbook
  - klaim:          Healthcare receivables (tape-based)
  - silq:           POS lending (tape-based)

Usage:
    from core.research_report import generate_research_report
    pdf_bytes = generate_research_report(company, product, data, analysis_type, ai_narrative)
"""

from datetime import datetime
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY

# ── Brand colours ────────────────────────────────────────────────────────────
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


def _fmt_num(v, prefix='', suffix=''):
    """Format a number with appropriate scale suffix."""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return '--'
    if abs(n) >= 1e9:
        return f'{prefix}{n/1e9:,.1f}B{suffix}'
    if abs(n) >= 1e6:
        return f'{prefix}{n/1e6:,.1f}M{suffix}'
    if abs(n) >= 1e3:
        return f'{prefix}{n/1e3:,.1f}K{suffix}'
    return f'{prefix}{n:,.0f}{suffix}'


def _pct(v):
    try:
        return f'{float(v)*100:.2f}%'
    except (TypeError, ValueError):
        return '--'


# ── Styles ───────────────────────────────────────────────────────────────────

def _build_styles():
    """Build the PDF style sheet."""
    styles = {}

    styles['body'] = ParagraphStyle(
        'body', fontName='Helvetica', fontSize=9, textColor=TEXT,
        leading=14, alignment=TA_JUSTIFY, spaceAfter=6,
    )
    styles['body_small'] = ParagraphStyle(
        'body_small', fontName='Helvetica', fontSize=8, textColor=MUTED,
        leading=11, spaceAfter=4,
    )
    styles['heading1'] = ParagraphStyle(
        'heading1', fontName='Helvetica-Bold', fontSize=16, textColor=GOLD,
        spaceBefore=16, spaceAfter=8, leading=20,
    )
    styles['heading2'] = ParagraphStyle(
        'heading2', fontName='Helvetica-Bold', fontSize=12, textColor=GOLD,
        spaceBefore=12, spaceAfter=6, leading=16,
    )
    styles['heading3'] = ParagraphStyle(
        'heading3', fontName='Helvetica-Bold', fontSize=10, textColor=TEXT,
        spaceBefore=8, spaceAfter=4, leading=13,
    )
    styles['metric'] = ParagraphStyle(
        'metric', fontName='Helvetica-Bold', fontSize=9, textColor=TEAL,
        leading=12, spaceAfter=2,
    )
    styles['metric_label'] = ParagraphStyle(
        'metric_label', fontName='Helvetica', fontSize=8, textColor=MUTED,
        leading=10, spaceAfter=6,
    )
    styles['cover_title'] = ParagraphStyle(
        'cover_title', fontName='Helvetica-Bold', fontSize=28, textColor=TEXT,
        alignment=TA_CENTER, spaceAfter=8, leading=34,
    )
    styles['cover_subtitle'] = ParagraphStyle(
        'cover_subtitle', fontName='Helvetica', fontSize=14, textColor=GOLD,
        alignment=TA_CENTER, spaceAfter=4, leading=18,
    )
    styles['cover_meta'] = ParagraphStyle(
        'cover_meta', fontName='Helvetica', fontSize=10, textColor=MUTED,
        alignment=TA_CENTER, spaceAfter=4, leading=14,
    )
    styles['footer'] = ParagraphStyle(
        'footer', fontName='Helvetica', fontSize=7, textColor=MUTED,
        alignment=TA_CENTER,
    )
    styles['toc_entry'] = ParagraphStyle(
        'toc_entry', fontName='Helvetica', fontSize=10, textColor=TEXT,
        leading=16, spaceAfter=2, leftIndent=20,
    )
    styles['toc_title'] = ParagraphStyle(
        'toc_title', fontName='Helvetica-Bold', fontSize=14, textColor=GOLD,
        spaceAfter=12, spaceBefore=20,
    )
    styles['conclusion'] = ParagraphStyle(
        'conclusion', fontName='Helvetica-Bold', fontSize=9, textColor=GOLD,
        leading=14, spaceBefore=6, spaceAfter=8, leftIndent=12,
        borderColor=GOLD, borderWidth=1, borderPadding=6,
    )

    return styles


# ── Table helpers ────────────────────────────────────────────────────────────

def _make_table(headers, rows, col_widths=None):
    """Create a styled table matching Laith dark theme."""
    data = [headers] + rows

    if col_widths is None:
        page_w = A4[0] - 2 * 0.7 * inch
        col_widths = [page_w / len(headers)] * len(headers)

    t = Table(data, colWidths=col_widths, repeatRows=1)
    style_commands = [
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), SURF),
        ('TEXTCOLOR', (0, 0), (-1, 0), GOLD),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        # Body
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('TEXTCOLOR', (0, 1), (-1, -1), TEXT),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        # Grid
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, GOLD),
        ('LINEBELOW', (0, 1), (-1, -1), 0.25, BORDER),
        # Alignment
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]

    # Alternating row backgrounds
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_commands.append(('BACKGROUND', (0, i), (-1, i), SURF))

    t.setStyle(TableStyle(style_commands))
    return t


# ── Page template ────────────────────────────────────────────────────────────

def _page_bg(canvas, doc):
    """Draw dark background on every page."""
    w, h = A4
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, w, h, fill=1, stroke=0)

    # Footer
    canvas.setFillColor(MUTED)
    canvas.setFont('Helvetica', 7)
    canvas.drawCentredString(w / 2, 20, 'CONFIDENTIAL  |  Generated by LAITH Analytics Platform  |  Amwal Capital Partners')
    canvas.drawRightString(w - 0.7 * inch, 20, f'Page {doc.page}')

    # Gold accent line at top
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(2)
    canvas.line(0.7 * inch, h - 0.5 * inch, w - 0.7 * inch, h - 0.5 * inch)

    canvas.restoreState()


def _cover_bg(canvas, doc):
    """Draw cover page background."""
    w, h = A4
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, w, h, fill=1, stroke=0)

    # Gold border
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(2)
    margin = 0.5 * inch
    canvas.rect(margin, margin, w - 2 * margin, h - 2 * margin, fill=0, stroke=1)

    # LAITH wordmark at top
    canvas.setFillColor(TEXT)
    canvas.setFont('Helvetica-Bold', 36)
    x_center = w / 2
    canvas.drawCentredString(x_center - 20, h - 2.5 * inch, 'L')
    canvas.setFillColor(GOLD)
    canvas.drawCentredString(x_center, h - 2.5 * inch, 'AI')
    canvas.setFillColor(TEXT)
    canvas.drawCentredString(x_center + 22, h - 2.5 * inch, 'TH')

    # Confidentiality banner at bottom
    canvas.setFillColor(SURF)
    canvas.rect(margin, margin, w - 2 * margin, 0.6 * inch, fill=1, stroke=0)
    canvas.setFillColor(MUTED)
    canvas.setFont('Helvetica', 7)
    canvas.drawCentredString(w / 2, margin + 0.3 * inch, 'STRICTLY PRIVATE AND CONFIDENTIAL  |  FOR INVESTMENT COMMITTEE USE ONLY')
    canvas.drawCentredString(w / 2, margin + 0.15 * inch,
                             f'Report generated {datetime.now().strftime("%d %B %Y")}  |  Amwal Capital Partners')

    canvas.restoreState()


# ═══════════════════════════════════════════════════════════════════════════════
# CONTENT BUILDERS (per analysis type)
# ═══════════════════════════════════════════════════════════════════════════════

def _build_tamara_sections(data, product, styles, ai_narrative=None):
    """Build report sections for Tamara BNPL."""
    story = []
    ccy = 'SAR' if product == 'KSA' else 'AED'
    overview = data.get('overview', {})
    co = data.get('company_overview', {})
    ft = data.get('facility_terms', {})
    fdd = data.get('deloitte_fdd', {})
    covenant = data.get('covenant_status', {})
    vp = data.get('vintage_performance', {})

    # ── Section 1: Executive Summary ────────────────────────────────────────
    story.append(Paragraph('1. Executive Summary', styles['heading1']))
    if ai_narrative and isinstance(ai_narrative, dict):
        bottom_line = ai_narrative.get('bottom_line', '')
        if bottom_line:
            story.append(Paragraph(bottom_line, styles['body']))
        sections = ai_narrative.get('sections', [])
        for sec in sections[:3]:  # First 3 sections for exec summary
            story.append(Paragraph(f"<b>{sec.get('title', '')}</b>", styles['heading3']))
            story.append(Paragraph(sec.get('content', ''), styles['body']))
            conclusion = sec.get('conclusion', '')
            if conclusion:
                story.append(Paragraph(conclusion, styles['conclusion']))
    else:
        story.append(Paragraph(
            'Tamara is Saudi Arabia\'s first fintech unicorn and the leading BNPL provider in the GCC. '
            f'The {product} portfolio is backed by a ${ft.get("total_limit", 0)/1e9:.1f}B securitisation facility. '
            'This report analyses vintage cohort performance, covenant compliance, facility structure, '
            'and financial trajectory based on data room materials.',
            styles['body']))
    story.append(PageBreak())

    # ── Section 2: Company Overview ─────────────────────────────────────────
    story.append(Paragraph('2. Company Overview', styles['heading1']))

    company_data = [
        ['Founded', str(co.get('founded', '--')), 'Headquarters', co.get('headquarters', '--')],
        ['CEO', co.get('ceo', '--'), 'Employees', str(co.get('employees', '--'))],
        ['Valuation', _fmt_num(co.get('valuation'), '$'), 'Equity Raised', _fmt_num(co.get('total_equity_raised'), '$')],
        ['Users', _fmt_num(co.get('registered_users')), 'Merchants', _fmt_num(co.get('merchants'))],
        ['Latest Round', co.get('latest_round', '--'), 'IPO Target', co.get('ipo_target', '--')],
    ]
    t = _make_table(['Field', 'Value', 'Field', 'Value'], company_data)
    story.append(t)
    story.append(Spacer(1, 12))

    # Market position
    story.append(Paragraph('<b>Market Position</b>', styles['heading3']))
    story.append(Paragraph(co.get('market_position', 'Leading BNPL provider in KSA'), styles['body']))

    # Products
    products = co.get('products', {})
    if products:
        story.append(Paragraph('<b>Product Suite</b>', styles['heading3']))
        prod_rows = []
        for key, prod in products.items():
            prod_rows.append([
                prod.get('name', key),
                prod.get('tenor', '--'),
                prod.get('max_size', '--'),
                str(prod.get('splits', '--')) if 'splits' in prod else prod.get('fee', '--'),
            ])
        t = _make_table(['Product', 'Tenor', 'Max Size', 'Details'], prod_rows)
        story.append(t)

    story.append(PageBreak())

    # ── Section 3: Portfolio Analytics ───────────────────────────────────────
    story.append(Paragraph(f'3. Portfolio Analytics -- {product}', styles['heading1']))

    # Key metrics
    story.append(Paragraph('<b>Portfolio Snapshot</b>', styles['heading3']))
    metrics_rows = [
        ['Outstanding AR', _fmt_num(overview.get('total_pending'), f'{ccy} ')],
        ['Data Coverage', f'{overview.get("months_of_data", 0)} monthly snapshots'],
        ['Vintage Cohorts', str(overview.get('vintage_count', 0))],
        ['Facility Limit', _fmt_num(ft.get('total_limit'), '$')],
        ['Max Advance Rate', f'{(ft.get("max_advance_rate", 0) * 100):.0f}%'],
    ]
    t = _make_table(['Metric', 'Value'], metrics_rows)
    story.append(t)
    story.append(Spacer(1, 12))

    # Product breakdown
    pb = fdd.get('product_breakdown', [])
    if pb:
        story.append(Paragraph('<b>Outstanding by Product Type</b>', styles['heading3']))
        pb_rows = [[p['product'], _fmt_num(p['pending_amount'], f'{ccy} '),
                     f"{(p.get('writeoff_pct', 0) * 100):.2f}%"] for p in pb if p.get('pending_amount')]
        t = _make_table(['Product', 'Outstanding', 'Write-off %'], pb_rows)
        story.append(t)

    story.append(PageBreak())

    # ── Section 4: Vintage Performance ──────────────────────────────────────
    story.append(Paragraph('4. Vintage Cohort Performance', styles['heading1']))

    for metric_name in ['default', 'delinquency']:
        portfolio = vp.get(metric_name, {}).get('portfolio', [])
        if not portfolio:
            continue

        label = 'Default (+120DPD)' if metric_name == 'default' else 'Delinquency (+7DPD)'
        story.append(Paragraph(f'<b>{label} by Vintage</b>', styles['heading3']))

        # Get last 8 vintages, show latest 4 reporting months
        recent = portfolio[-8:]
        if recent:
            cols = sorted(set(k for r in recent for k in r if k != 'vintage'))[-4:]
            headers = ['Vintage'] + [c.replace('20', "'") for c in cols]
            rows = []
            for r in recent:
                row = [r['vintage']]
                for c in cols:
                    v = r.get(c)
                    row.append(f'{v*100:.2f}%' if v is not None else '--')
                rows.append(row)
            t = _make_table(headers, rows)
            story.append(t)
            story.append(Spacer(1, 8))

        scale = vp.get(metric_name, {}).get('_color_scale', {})
        if scale:
            story.append(Paragraph(
                f'Range: {scale.get("min", 0)*100:.2f}% to {scale.get("max", 0)*100:.2f}% '
                f'(P25: {scale.get("p25", 0)*100:.2f}%, P75: {scale.get("p75", 0)*100:.2f}%, '
                f'{scale.get("count", 0)} data points)',
                styles['body_small']))

    story.append(PageBreak())

    # ── Section 5: Covenant Compliance ──────────────────────────────────────
    story.append(Paragraph('5. Covenant Compliance', styles['heading1']))

    triggers = covenant.get('triggers', [])
    if triggers:
        story.append(Paragraph('<b>Performance Trigger Tests</b>', styles['heading3']))
        trig_rows = []
        for t_data in triggers:
            status_text = t_data.get('status', 'unknown').upper().replace('_', ' ')
            trig_rows.append([
                t_data.get('name', '').replace('_', ' ').title(),
                f"{t_data['current_value']:.2f}%" if t_data.get('current_value') is not None else 'N/A',
                f"{t_data.get('l1_threshold', 0):.1f}%",
                f"{t_data.get('l2_threshold', 0):.1f}%",
                f"{t_data.get('l3_threshold', 0):.1f}%",
                status_text,
            ])
        t = _make_table(['Trigger', 'Current', 'L1', 'L2', 'L3', 'Status'], trig_rows)
        story.append(t)

    # Corporate covenants
    corp = ft.get('corporate_covenants', {})
    if corp:
        story.append(Spacer(1, 12))
        story.append(Paragraph('<b>Corporate Covenants</b>', styles['heading3']))
        corp_rows = []
        for name, vals in corp.items():
            display_name = name.replace('_', ' ').title()
            threshold = vals.get('threshold', 0)
            if isinstance(threshold, (int, float)):
                if threshold < 1:
                    corp_rows.append([display_name, _pct(threshold), _pct(vals.get('l2')), _pct(vals.get('l3'))])
                else:
                    corp_rows.append([display_name, _fmt_num(threshold, '$'), _fmt_num(vals.get('l2'), '$'), _fmt_num(vals.get('l3'), '$')])
        t = _make_table(['Covenant', 'L1 Threshold', 'L2', 'L3'], corp_rows)
        story.append(t)

    story.append(PageBreak())

    # ── Section 6: Facility Structure ───────────────────────────────────────
    story.append(Paragraph('6. Facility Structure', styles['heading1']))

    story.append(Paragraph(f'<b>{ft.get("facility_name", "Securitisation Facility")}</b>', styles['heading3']))
    facility_info = [
        ['SPV', ft.get('spv', '--')],
        ['Originator', ft.get('originator', '--')],
        ['Close Date', ft.get('close_date', '--')],
        ['Revolving Period End', ft.get('revolving_end', '--')],
        ['Final Maturity', ft.get('final_maturity', '--')],
        ['Total Limit', _fmt_num(ft.get('total_limit'), '$')],
        ['Max Advance Rate', f"{(ft.get('max_advance_rate', 0) * 100):.0f}%"],
    ]
    t = _make_table(['Field', 'Value'], facility_info)
    story.append(t)
    story.append(Spacer(1, 12))

    # Tranches
    tranches = ft.get('tranches', [])
    if tranches:
        story.append(Paragraph('<b>Tranche Structure</b>', styles['heading3']))
        tranche_rows = [[tr['name'], _fmt_num(tr['limit'], '$'), tr['rate'], tr['lender']] for tr in tranches]
        t = _make_table(['Tranche', 'Limit', 'Rate', 'Lender'], tranche_rows)
        story.append(t)

    story.append(PageBreak())

    # ── Section 7: Deloitte FDD Summary ─────────────────────────────────────
    story.append(Paragraph('7. DPD Analysis (Deloitte FDD)', styles['heading1']))

    ts = fdd.get('dpd_timeseries', [])
    if ts:
        story.append(Paragraph(
            f'The Deloitte FDD loan portfolio contains {fdd.get("total_rows", 0):,} rows spanning '
            f'{len(ts)} monthly snapshots from {ts[0].get("date", "")} to {ts[-1].get("date", "")}.',
            styles['body']))

        # Show latest 6 months
        recent_ts = ts[-6:]
        dpd_rows = []
        for entry in recent_ts:
            dpd = entry.get('dpd_distribution', {})
            total = sum(v for v in dpd.values() if v) or 1
            not_late_pct = (dpd.get('Not Late', 0) or 0) / total * 100
            dpd_rows.append([
                str(entry.get('date', ''))[:7],
                _fmt_num(entry.get('total_pending'), f'{ccy} '),
                _fmt_num(entry.get('total_written_off'), f'{ccy} '),
                f'{not_late_pct:.1f}%',
                f'{100 - not_late_pct:.1f}%',
            ])
        t = _make_table(['Month', 'Outstanding', 'Written Off', 'Current %', 'Delinquent %'], dpd_rows)
        story.append(t)

    # ECL movement
    ecl = fdd.get('ecl_movement', [])
    if ecl:
        story.append(Spacer(1, 12))
        story.append(Paragraph('<b>ECL Provision Movement</b>', styles['heading3']))
        ecl_headers = list(ecl[0].keys()) if ecl else []
        ecl_rows = [[str(row.get(h, '')) for h in ecl_headers] for row in ecl]
        if ecl_headers and ecl_rows:
            t = _make_table(ecl_headers, ecl_rows)
            story.append(t)

    story.append(PageBreak())

    # ── Section 8: Data Sources & Methodology ───────────────────────────────
    story.append(Paragraph('8. Data Sources & Methodology', styles['heading1']))

    sources = data.get('meta', {}).get('data_sources', [])
    for src in sources:
        story.append(Paragraph(f'  {src}', styles['body']))

    story.append(Spacer(1, 12))
    notes = data.get('data_notes', [])
    if notes:
        story.append(Paragraph('<b>Key Definitions</b>', styles['heading3']))
        for note in notes:
            story.append(Paragraph(f'  {note}', styles['body_small']))

    return story


def _build_klaim_sections(data, product, styles, ai_narrative=None, currency='AED'):
    """Build report sections for Klaim healthcare receivables."""
    story = []
    s = data.get('summary', {})
    par = data.get('par', {})
    el = data.get('expected_loss', {}).get('portfolio', {})
    cohort = data.get('cohort', {})
    conc = data.get('concentration', {})
    dso = data.get('dso', {})

    # ── 1. Executive Summary ───────────────────────────────────────────────
    story.append(Paragraph('1. Executive Summary', styles['heading1']))
    if ai_narrative and isinstance(ai_narrative, dict):
        bl = ai_narrative.get('bottom_line', '')
        if bl:
            story.append(Paragraph(bl, styles['body']))
        for sec in ai_narrative.get('sections', [])[:3]:
            story.append(Paragraph(f"<b>{sec.get('title', '')}</b>", styles['heading3']))
            story.append(Paragraph(sec.get('content', ''), styles['body']))
    else:
        story.append(Paragraph(
            f'Klaim ({product}) is a healthcare insurance claims factoring portfolio. '
            f'The portfolio comprises {_fmt_num(s.get("total_deals"))} deals with '
            f'{currency} {_fmt_num(s.get("total_purchase_value"))} face value and a '
            f'{_pct(s.get("collection_rate"))} collection rate.',
            styles['body']))
    story.append(PageBreak())

    # ── 2. Portfolio Overview ──────────────────────────────────────────────
    story.append(Paragraph('2. Portfolio Overview', styles['heading1']))
    overview_rows = [
        ['Total Deals', _fmt_num(s.get('total_deals'))],
        ['Face Value', _fmt_num(s.get('total_purchase_value'), f'{currency} ')],
        ['Collected', _fmt_num(s.get('total_collected'), f'{currency} ')],
        ['Collection Rate', _pct(s.get('collection_rate'))],
        ['Denial Rate', _pct(s.get('denial_rate'))],
        ['Pending Rate', _pct(s.get('pending_rate'))],
        ['Active Deals', _fmt_num(s.get('active_deals'))],
        ['DSO (Weighted)', f"{dso.get('weighted_dso', '--')} days" if dso.get('available') else '--'],
    ]
    story.append(_make_table(['Metric', 'Value'], overview_rows))
    story.append(PageBreak())

    # ── 3. Credit Quality ──────────────────────────────────────────────────
    story.append(Paragraph('3. Credit Quality', styles['heading1']))
    if par.get('available'):
        story.append(Paragraph('<b>Portfolio at Risk</b>', styles['heading3']))
        par_rows = []
        for label, key in [('PAR 30+', 'par_30'), ('PAR 60+', 'par_60'), ('PAR 90+', 'par_90')]:
            p = par.get(key, {})
            par_rows.append([label, _pct(p.get('balance_pct')), _fmt_num(p.get('balance'), f'{currency} ')])
        story.append(_make_table(['Bucket', '% Outstanding', 'Balance'], par_rows))
        story.append(Spacer(1, 0.3 * inch))

    if el:
        story.append(Paragraph('<b>Expected Loss Model</b>', styles['heading3']))
        el_rows = [
            ['PD (Probability of Default)', _pct(el.get('pd'))],
            ['LGD (Loss Given Default)', _pct(el.get('lgd'))],
            ['EAD (Exposure at Default)', _fmt_num(el.get('ead'), f'{currency} ')],
            ['Expected Loss', _fmt_num(el.get('el'), f'{currency} ')],
            ['EL Rate', _pct(el.get('el_rate'))],
        ]
        story.append(_make_table(['Parameter', 'Value'], el_rows))
    story.append(PageBreak())

    # ── 4. Cohort Performance ──────────────────────────────────────────────
    story.append(Paragraph('4. Cohort Performance', styles['heading1']))
    cohorts = cohort.get('cohorts', [])
    if cohorts:
        rows = []
        for c in cohorts[-10:]:
            rows.append([
                str(c.get('vintage', '')),
                _fmt_num(c.get('deals')),
                _fmt_num(c.get('purchase_value'), f'{currency} '),
                _fmt_num(c.get('collected'), f'{currency} '),
                _fmt_num(c.get('denied'), f'{currency} '),
                _pct(c.get('collection_rate')),
            ])
        story.append(_make_table(
            ['Vintage', 'Deals', 'Originated', 'Collected', 'Denied', 'Coll. Rate'], rows))
    else:
        story.append(Paragraph('No cohort data available.', styles['body']))
    story.append(PageBreak())

    # ── 5. Concentration & Segments ────────────────────────────────────────
    story.append(Paragraph('5. Concentration & Segments', styles['heading1']))
    groups = conc.get('group', [])
    hhi = conc.get('hhi', {})
    if hhi:
        story.append(Paragraph(f'<b>HHI: {hhi.get("hhi", 0):,.0f}</b> ({hhi.get("interpretation", "")})',
                                styles['heading3']))
        story.append(Spacer(1, 0.2 * inch))
    if groups:
        rows = []
        for g in groups[:10]:
            rows.append([
                str(g.get('group', '')),
                _fmt_num(g.get('purchase_value'), f'{currency} '),
                _pct(g.get('share')),
            ])
        story.append(_make_table(['Provider', 'Face Value', 'Share'], rows))
    story.append(PageBreak())

    # ── 6. Appendix ────────────────────────────────────────────────────────
    story.append(Paragraph('6. Appendix', styles['heading1']))
    story.append(Paragraph(
        'Data sourced from loan tape CSV/Excel snapshots uploaded to the LAITH platform. '
        'All metrics computed in real-time from the latest available snapshot.',
        styles['body']))

    return story


def _build_silq_sections(data, product, styles, ai_narrative=None, currency='SAR'):
    """Build report sections for SILQ POS lending."""
    story = []
    s = data.get('summary', {})
    delinq = data.get('delinquency', {})
    cohort = data.get('cohort', {})
    conc = data.get('concentration', {})

    # ── 1. Executive Summary ───────────────────────────────────────────────
    story.append(Paragraph('1. Executive Summary', styles['heading1']))
    if ai_narrative and isinstance(ai_narrative, dict):
        bl = ai_narrative.get('bottom_line', '')
        if bl:
            story.append(Paragraph(bl, styles['body']))
        for sec in ai_narrative.get('sections', [])[:3]:
            story.append(Paragraph(f"<b>{sec.get('title', '')}</b>", styles['heading3']))
            story.append(Paragraph(sec.get('content', ''), styles['body']))
    else:
        story.append(Paragraph(
            f'SILQ ({product}) is a POS lending portfolio with '
            f'{_fmt_num(s.get("total_deals"))} loans totalling '
            f'{currency} {_fmt_num(s.get("total_purchase_value", s.get("total_disbursed")))} disbursed. '
            f'Collection rate stands at {_pct(s.get("collection_rate"))}.',
            styles['body']))
    story.append(PageBreak())

    # ── 2. Portfolio Overview ──────────────────────────────────────────────
    story.append(Paragraph('2. Portfolio Overview', styles['heading1']))
    overview_rows = [
        ['Total Loans', _fmt_num(s.get('total_deals'))],
        ['Total Disbursed', _fmt_num(s.get('total_purchase_value', s.get('total_disbursed')), f'{currency} ')],
        ['Active Loans', _fmt_num(s.get('active_deals'))],
        ['Collection Rate', _pct(s.get('collection_rate'))],
        ['Delinquency Rate', _pct(s.get('delinquency_rate', s.get('denial_rate')))],
        ['Average Ticket', _fmt_num(s.get('avg_deal_size', s.get('avg_ticket')), f'{currency} ')],
    ]
    story.append(_make_table(['Metric', 'Value'], overview_rows))
    story.append(PageBreak())

    # ── 3. Delinquency Analysis ────────────────────────────────────────────
    story.append(Paragraph('3. Delinquency Analysis', styles['heading1']))
    buckets = delinq.get('buckets', [])
    if buckets:
        rows = []
        for b in buckets:
            rows.append([
                str(b.get('bucket', b.get('label', ''))),
                _fmt_num(b.get('count')),
                _fmt_num(b.get('balance', b.get('amount')), f'{currency} '),
                _pct(b.get('pct', b.get('share'))),
            ])
        story.append(_make_table(['DPD Bucket', 'Count', 'Balance', '% of Total'], rows))
    else:
        story.append(Paragraph('No delinquency data available.', styles['body']))
    story.append(PageBreak())

    # ── 4. Cohort Performance ──────────────────────────────────────────────
    story.append(Paragraph('4. Cohort Performance', styles['heading1']))
    cohorts = cohort.get('cohorts', [])
    if cohorts:
        rows = []
        for c in cohorts[-10:]:
            rows.append([
                str(c.get('vintage', '')),
                _fmt_num(c.get('deals', c.get('count'))),
                _fmt_num(c.get('purchase_value', c.get('disbursed')), f'{currency} '),
                _pct(c.get('collection_rate')),
            ])
        story.append(_make_table(['Vintage', 'Loans', 'Disbursed', 'Coll. Rate'], rows))
    else:
        story.append(Paragraph('No cohort data available.', styles['body']))
    story.append(PageBreak())

    # ── 5. Concentration ───────────────────────────────────────────────────
    story.append(Paragraph('5. Concentration', styles['heading1']))
    hhi = conc.get('hhi', {})
    if hhi:
        story.append(Paragraph(f'<b>HHI: {hhi.get("hhi", 0):,.0f}</b> ({hhi.get("interpretation", "")})',
                                styles['heading3']))
        story.append(Spacer(1, 0.2 * inch))
    groups = conc.get('group', [])
    if groups:
        rows = []
        for g in groups[:10]:
            rows.append([
                str(g.get('group', g.get('merchant', ''))),
                _fmt_num(g.get('purchase_value', g.get('disbursed')), f'{currency} '),
                _pct(g.get('share')),
            ])
        story.append(_make_table(['Merchant', 'Disbursed', 'Share'], rows))
    story.append(PageBreak())

    # ── 6. Appendix ────────────────────────────────────────────────────────
    story.append(Paragraph('6. Appendix', styles['heading1']))
    story.append(Paragraph(
        'Data sourced from SILQ loan tape Excel snapshots uploaded to the LAITH platform. '
        'Three product types analysed: BNPL, RBF, and RCL.',
        styles['body']))

    return story


def _build_ejari_sections(data, product, styles, ai_narrative=None, currency='USD'):
    """Build report sections for Ejari RNPL (read-only ODS summary)."""
    story = []
    overview = data.get('portfolio_overview', {})
    dpd = data.get('dpd_distribution', {})
    cohorts = data.get('monthly_cohorts', {})
    segments = data.get('segment_analysis', {})

    # ── 1. Executive Summary ───────────────────────────────────────────────
    story.append(Paragraph('1. Executive Summary', styles['heading1']))
    if ai_narrative and isinstance(ai_narrative, dict):
        bl = ai_narrative.get('bottom_line', '')
        if bl:
            story.append(Paragraph(bl, styles['body']))
        for sec in ai_narrative.get('sections', [])[:3]:
            story.append(Paragraph(f"<b>{sec.get('title', '')}</b>", styles['heading3']))
            story.append(Paragraph(sec.get('content', ''), styles['body']))
    else:
        kpis = overview.get('kpis', [])
        contracts = next((k.get('value', '--') for k in kpis if 'contract' in str(k.get('label', '')).lower()), '--')
        story.append(Paragraph(
            f'Ejari ({product}) is a Rent Now Pay Later portfolio with {contracts} contracts. '
            'This report summarises portfolio health, DPD distribution, and cohort performance '
            'from the pre-computed ODS workbook.',
            styles['body']))
    story.append(PageBreak())

    # ── 2. Portfolio Overview ──────────────────────────────────────────────
    story.append(Paragraph('2. Portfolio Overview', styles['heading1']))
    kpis = overview.get('kpis', [])
    if kpis:
        rows = [[str(k.get('label', '')), str(k.get('value', '--'))] for k in kpis]
        story.append(_make_table(['Metric', 'Value'], rows))
    else:
        story.append(Paragraph('No overview KPIs available.', styles['body']))

    # DPD summary from overview if present
    dpd_summary = overview.get('dpd_summary', [])
    if dpd_summary:
        story.append(Spacer(1, 0.3 * inch))
        story.append(Paragraph('<b>DPD Summary</b>', styles['heading3']))
        rows = [[str(d.get('bucket', '')), str(d.get('count', '--')),
                 str(d.get('amount', '--'))] for d in dpd_summary]
        story.append(_make_table(['Bucket', 'Count', 'Amount'], rows))
    story.append(PageBreak())

    # ── 3. DPD & Credit Quality ────────────────────────────────────────────
    story.append(Paragraph('3. DPD & Credit Quality', styles['heading1']))
    dpd_table = dpd.get('table', [])
    dpd_headers = dpd.get('headers', [])
    if dpd_table and dpd_headers:
        rows = [[str(cell) for cell in row] for row in dpd_table[:15]]
        story.append(_make_table(dpd_headers, rows))
    elif isinstance(dpd, list) and dpd:
        # Flat list of dicts fallback
        keys = list(dpd[0].keys()) if dpd else []
        rows = [[str(d.get(k, '')) for k in keys] for d in dpd[:15]]
        if keys:
            story.append(_make_table(keys, rows))
    else:
        story.append(Paragraph('No DPD distribution data available.', styles['body']))
    story.append(PageBreak())

    # ── 4. Cohort & Roll Rates ─────────────────────────────────────────────
    story.append(Paragraph('4. Cohort & Roll Rates', styles['heading1']))
    cohort_table = cohorts.get('table', [])
    cohort_headers = cohorts.get('headers', [])
    if cohort_table and cohort_headers:
        rows = [[str(cell) for cell in row] for row in cohort_table[:12]]
        story.append(_make_table(cohort_headers, rows))
    else:
        story.append(Paragraph('No monthly cohort data available.', styles['body']))
    story.append(PageBreak())

    # ── 5. Appendix ────────────────────────────────────────────────────────
    story.append(Paragraph('5. Appendix', styles['heading1']))
    story.append(Paragraph(
        'Data sourced from a pre-computed ODS workbook provided by Ejari. '
        'All figures are read-only summaries; no live computation is performed.',
        styles['body']))

    return story


def _build_generic_sections(data, company, product, analysis_type, styles, ai_narrative=None):
    """Fallback report builder for non-Tamara companies."""
    story = []

    story.append(Paragraph('1. Executive Summary', styles['heading1']))
    if ai_narrative and isinstance(ai_narrative, dict):
        bottom_line = ai_narrative.get('bottom_line', '')
        if bottom_line:
            story.append(Paragraph(bottom_line, styles['body']))
    else:
        story.append(Paragraph(
            f'This report provides a credit analysis of {company} ({product}) based on available '
            f'analytical data. Analysis type: {analysis_type}.',
            styles['body']))

    story.append(PageBreak())
    story.append(Paragraph('2. Data Summary', styles['heading1']))
    story.append(Paragraph(f'Analysis type: {analysis_type}', styles['body']))
    story.append(Paragraph(f'Available data keys: {", ".join(data.keys())}', styles['body']))

    return story


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def generate_research_report(company, product, data, analysis_type,
                             ai_narrative=None, currency='USD',
                             section_order=None, excluded_sections=None):
    """Generate a comprehensive credit research report PDF.

    Args:
        company: Company name (e.g., 'Tamara')
        product: Product name (e.g., 'KSA')
        data: Parsed data dict from the appropriate parser
        analysis_type: One of 'tamara_summary', 'ejari_summary', 'klaim', 'silq', 'aajil'
        ai_narrative: Optional AI-generated narrative (dict with sections, summary_table, bottom_line)
        currency: Display currency
        section_order: Optional list of section numbers (1-based) to include, in order.
                       If None, all sections in default order.
        excluded_sections: Optional list of section numbers to skip.

    Returns:
        bytes: PDF file content
    """
    buf = BytesIO()
    styles = _build_styles()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        topMargin=0.8 * inch, bottomMargin=0.6 * inch,
    )

    story = []

    # ── Cover Page ──────────────────────────────────────────────────────────
    story.append(Spacer(1, 2.5 * inch))

    # Company-specific title
    co = data.get('company_overview', {})
    company_display = co.get('full_name', company)
    asset_class = {
        'tamara_summary': 'Buy Now Pay Later',
        'ejari_summary': 'Rent Now Pay Later',
        'klaim': 'Healthcare Receivables',
        'silq': 'POS Lending',
        'aajil': 'SME Trade Credit',
    }.get(analysis_type, 'Portfolio')

    story.append(Paragraph(f'{company_display}', styles['cover_title']))
    story.append(Paragraph(f'{asset_class} -- {product}', styles['cover_subtitle']))
    story.append(Spacer(1, 0.5 * inch))
    story.append(Paragraph('Credit Research Report', styles['cover_meta']))
    story.append(Paragraph(datetime.now().strftime('%B %Y'), styles['cover_meta']))
    story.append(Spacer(1, 1 * inch))
    story.append(Paragraph('Prepared for the Investment Committee', styles['cover_meta']))
    story.append(Paragraph('Amwal Capital Partners', styles['cover_meta']))
    story.append(PageBreak())

    # ── Table of Contents ───────────────────────────────────────────────────
    story.append(Paragraph('Table of Contents', styles['toc_title']))

    if analysis_type == 'tamara_summary':
        toc_entries = [
            '1. Executive Summary',
            '2. Company Overview',
            '3. Portfolio Analytics',
            '4. Vintage Cohort Performance',
            '5. Covenant Compliance',
            '6. Facility Structure',
            '7. DPD Analysis (Deloitte FDD)',
            '8. Data Sources & Methodology',
        ]
    elif analysis_type == 'klaim':
        toc_entries = [
            '1. Executive Summary',
            '2. Portfolio Overview',
            '3. Credit Quality',
            '4. Cohort Performance',
            '5. Concentration & Segments',
            '6. Appendix',
        ]
    elif analysis_type == 'silq':
        toc_entries = [
            '1. Executive Summary',
            '2. Portfolio Overview',
            '3. Delinquency Analysis',
            '4. Cohort Performance',
            '5. Concentration',
            '6. Appendix',
        ]
    elif analysis_type == 'ejari_summary':
        toc_entries = [
            '1. Executive Summary',
            '2. Portfolio Overview',
            '3. DPD & Credit Quality',
            '4. Cohort & Roll Rates',
            '5. Appendix',
        ]
    else:
        toc_entries = ['1. Executive Summary', '2. Data Summary']

    for entry in toc_entries:
        story.append(Paragraph(entry, styles['toc_entry']))

    story.append(PageBreak())

    # ── Content Sections ────────────────────────────────────────────────────
    if analysis_type == 'tamara_summary':
        story.extend(_build_tamara_sections(data, product, styles, ai_narrative))
    elif analysis_type == 'klaim':
        story.extend(_build_klaim_sections(data, product, styles, ai_narrative, currency))
    elif analysis_type == 'silq':
        story.extend(_build_silq_sections(data, product, styles, ai_narrative, currency))
    elif analysis_type == 'ejari_summary':
        story.extend(_build_ejari_sections(data, product, styles, ai_narrative, currency))
    else:
        story.extend(_build_generic_sections(data, company, product, analysis_type, styles, ai_narrative))

    # ── Build PDF ───────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=_cover_bg, onLaterPages=_page_bg)
    return buf.getvalue()
