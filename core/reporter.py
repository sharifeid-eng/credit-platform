import os
import anthropic
from datetime import datetime
from dotenv import load_dotenv
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib import colors

load_dotenv()

REPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "reports"
)

def ensure_reports_dir():
    if not os.path.exists(REPORTS_DIR):
        os.makedirs(REPORTS_DIR)

def build_consistency_prompt(company, product, checks):
    """Build the prompt for Claude to analyze consistency findings"""
    
    findings_text = ""
    for check in checks:
        old_label = check['old_label']
        new_label = check['new_label']
        report = check['report']
        
        findings_text += f"\n\n--- Comparison: {old_label} vs {new_label} ---\n"
        
        if report['issues']:
            findings_text += "\nCRITICAL ISSUES:\n"
            for item in report['issues']:
                findings_text += f"  - [{item['check']}] {item['detail']}\n"
        
        if report['warnings']:
            findings_text += "\nWARNINGS:\n"
            for item in report['warnings']:
                findings_text += f"  - [{item['check']}] {item['detail']}\n"
        
        if report['info']:
            findings_text += "\nINFO:\n"
            for item in report['info']:
                findings_text += f"  - [{item['check']}] {item['detail']}\n"
    
    prompt = f"""You are a senior analyst at a private credit fund specializing in asset-backed lending. 
You are reviewing data integrity findings from loan tape snapshots provided by {company.upper()}, 
a portfolio company in the {product.replace('_', ' ').title()} segment.

The following consistency checks were run comparing multiple data snapshots over time:
{findings_text}

Please write a detailed, professional data integrity report that includes:

1. EXECUTIVE SUMMARY
   - Overall assessment of data quality (1-2 paragraphs)
   - Key concerns ranked by severity

2. DETAILED FINDINGS
   For each issue found, explain:
   - What the issue is in plain terms
   - Why it matters from a credit and data integrity perspective
   - Whether it could have an innocent explanation or is genuinely concerning
   - The potential financial impact if any

3. QUESTIONS FOR THE COMPANY
   - A numbered list of specific, direct questions to ask {company.upper()} 
   - Frame them professionally but do not soften the important ones

4. RECOMMENDED NEXT STEPS
   - What the fund should do before relying on this data for any decisions
   - Any additional data or verification needed

Write in a professional tone suitable for sharing with an investment committee. 
Be direct about concerns but fair in acknowledging possible explanations.
Do not use overly technical language — this should be readable by both credit professionals and lawyers."""

    return prompt

def generate_ai_analysis(company, product, checks):
    """Call Claude API to generate the analysis"""
    print("\nGenerating AI analysis of consistency findings...")
    
    client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
    
    prompt = build_consistency_prompt(company, product, checks)
    
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4000,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    return message.content[0].text

def save_pdf_report(company, product, analysis_text, checks):
    """Save the analysis as a formatted PDF"""
    ensure_reports_dir()
    
    date_str = datetime.now().strftime('%Y-%m-%d')
    filename = f"{date_str}_{company}_{product}_data_integrity_report.pdf"
    filepath = os.path.join(REPORTS_DIR, filename)
    
    # ── Colors ───────────────────────────────────────────────
    dark_blue = HexColor('#1B3A6B')
    medium_blue = HexColor('#2E5FA3')
    light_gray = HexColor('#F5F5F5')
    red = HexColor('#C0392B')
    orange = HexColor('#E67E22')
    green = HexColor('#27AE60')
    
    # ── Document setup ───────────────────────────────────────
    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=1*inch,
        bottomMargin=0.75*inch
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=24,
        textColor=dark_blue,
        spaceAfter=6,
        fontName='Helvetica-Bold'
    )
    
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=medium_blue,
        spaceAfter=4,
        fontName='Helvetica'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading1'],
        fontSize=14,
        textColor=dark_blue,
        spaceBefore=16,
        spaceAfter=8,
        fontName='Helvetica-Bold'
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=10,
        leading=16,
        spaceAfter=8,
        fontName='Helvetica'
    )
    
    # ── Build document content ───────────────────────────────
    content = []
    
    # Header
    content.append(Paragraph("DATA INTEGRITY REPORT", title_style))
    content.append(Paragraph(
        f"{company.upper()} — {product.replace('_', ' ').title()}", 
        subtitle_style
    ))
    content.append(Paragraph(
        f"Prepared: {datetime.now().strftime('%B %d, %Y')} | Confidential", 
        subtitle_style
    ))
    content.append(HRFlowable(width="100%", thickness=2, color=dark_blue))
    content.append(Spacer(1, 0.2*inch))
    
    # Snapshot summary table
    snapshot_data = [['Snapshot Comparison', 'Critical Issues', 'Warnings', 'Status']]
    for check in checks:
        report = check['report']
        n_issues = len(report['issues'])
        n_warnings = len(report['warnings'])
        status = 'PASS' if report['passed'] else 'FAIL'
        status_color = green if report['passed'] else red
        
        snapshot_data.append([
            f"{check['old_label']} → {check['new_label']}",
            str(n_issues),
            str(n_warnings),
            status
        ])
    
    table = Table(snapshot_data, colWidths=[3*inch, 1.2*inch, 1.2*inch, 1*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), dark_blue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('BACKGROUND', (0, 1), (-1, -1), light_gray),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, light_gray]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    content.append(table)
    content.append(Spacer(1, 0.3*inch))
    content.append(HRFlowable(width="100%", thickness=1, color=HexColor('#CCCCCC')))
    
    # AI Analysis
    # Parse the analysis text into sections
    lines = analysis_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            content.append(Spacer(1, 0.1*inch))
            continue
        
        # Detect headings
        if line.startswith('##'):
            content.append(Paragraph(line.replace('##', '').strip(), heading_style))
        elif line.startswith('#'):
            content.append(Paragraph(line.replace('#', '').strip(), heading_style))
        elif (line.isupper() and len(line) > 5) or (
            line.startswith('1.') or line.startswith('2.') or 
            line.startswith('3.') or line.startswith('4.')
        ) and len(line) < 60:
            content.append(Paragraph(f"<b>{line}</b>", body_style))
        elif line.startswith('-') or line.startswith('•'):
            content.append(Paragraph(
                f"&nbsp;&nbsp;&nbsp;{line}", 
                body_style
            ))
        else:
            content.append(Paragraph(line, body_style))
    
    # Footer note
    content.append(Spacer(1, 0.3*inch))
    content.append(HRFlowable(width="100%", thickness=1, color=HexColor('#CCCCCC')))
    content.append(Spacer(1, 0.1*inch))
    content.append(Paragraph(
        "This report was generated by an automated data integrity system and reviewed by the investment team. "
        "It is confidential and intended solely for internal use and authorized communications.",
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, 
                      textColor=HexColor('#888888'), fontName='Helvetica-Oblique')
    ))
    
    # Build PDF
    doc.build(content)
    return filepath

def run_and_save_report(company, product, checks):
    """Main function - generate AI analysis and save PDF"""
    
    # Generate AI analysis
    analysis_text = generate_ai_analysis(company, product, checks)
    
    # Save PDF
    filepath = save_pdf_report(company, product, analysis_text, checks)
    
    print(f"\n{'='*60}")
    print(f"REPORT SAVED")
    print(f"{'='*60}")
    print(f"Location: {filepath}")
    print(f"{'='*60}\n")
    
    # Also print a summary to terminal
    print("AI ANALYSIS SUMMARY:")
    print("-" * 60)
    # Print first 500 chars as preview
    preview = analysis_text[:800]
    print(preview + "...\n[Full report saved to PDF]")
    
    return filepath, analysis_text