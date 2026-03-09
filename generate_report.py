"""
Laith Portfolio Report Generator
Captures dashboard tabs as screenshots and compiles a professional PDF report.

Usage:
    python generate_report.py [--company klaim] [--product UAE_healthcare]
"""

import os, sys, time, argparse, tempfile, shutil
from datetime import datetime
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────
FRONTEND_URL = "http://localhost:5173"
BACKEND_URL  = "http://localhost:8000"

# Tabs to include in the report (skip Data Integrity — internal only)
REPORT_TABS = [
    "Overview",
    "Actual vs Expected",
    "Deployment",
    "Collection",
    "Denial Trend",
    "Ageing",
    "Revenue",
    "Portfolio",
    "Cohort Analysis",
    "Returns",
    "Risk & Migration",
]

# ── Brand colours ───────────────────────────────────────────────────
BRAND = {
    "bg_base":    (12, 16, 24),       # #0C1018
    "bg_surface": (17, 22, 32),       # #111620
    "gold":       (201, 168, 76),     # #C9A84C
    "gold_dim":   (201, 168, 76, 80), # 30% opacity gold
    "text":       (232, 234, 240),    # #E8EAF0
    "text_muted": (132, 148, 167),    # #8494A7
    "border":     (30, 39, 54),       # #1E2736
}

VIEWPORT_W = 1440
VIEWPORT_H = 900


def rgb(t):
    """Convert (r,g,b) tuple to ReportLab color."""
    from reportlab.lib.colors import Color
    if len(t) == 4:
        return Color(t[0]/255, t[1]/255, t[2]/255, t[3]/255)
    return Color(t[0]/255, t[1]/255, t[2]/255)


def _wait_for_charts(page, tab_name: str, max_wait: int = 30000):
    """Wait until all loading indicators disappear, then settle for animations."""
    import time
    start = time.time()

    # Phase 1: Generous wait for React to mount the component, fire API calls,
    # and receive initial responses. This MUST be long enough for the component
    # to mount and "Loading..." spinners to appear.
    page.wait_for_timeout(4000)

    # Phase 2: Poll until zero "Loading..." spinners remain (max 20s)
    deadline = time.time() + 20
    polls = 0
    while time.time() < deadline:
        loading_count = page.locator("text=Loading...").count()
        polls += 1
        if loading_count == 0 and polls >= 2:
            # Confirm zero on two consecutive checks
            break
        page.wait_for_timeout(500)

    # Phase 3: Extra settle for Recharts animations + rendering
    page.wait_for_timeout(2000)

    elapsed = round((time.time() - start) * 1000)
    return elapsed


def capture_tabs(company: str, product: str, tmp_dir: str) -> list[dict]:
    """Use Playwright to screenshot each dashboard tab."""
    from playwright.sync_api import sync_playwright

    screenshots = []
    url = f"{FRONTEND_URL}/company/{company}"

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception:
            # Fallback: use locally installed Chrome
            browser = p.chromium.launch(headless=True, channel="chrome")
        page = browser.new_page(viewport={"width": VIEWPORT_W, "height": VIEWPORT_H})

        print(f"  Navigating to {url} ...")
        page.goto(url, wait_until="networkidle", timeout=30000)
        # Wait for dashboard to fully load (KPI cards appear)
        page.wait_for_timeout(4000)

        # Hide elements that shouldn't appear in a static report
        page.evaluate("""() => {
            // Add a style tag to hide report-unfriendly elements
            const style = document.createElement('style');
            style.id = 'report-mode';
            style.textContent = `
                /* Hide the user badge and version tag in navbar */
                nav [style*="Sharif"] { visibility: hidden !important; }
            `;
            document.head.appendChild(style);
        }""")

        for i, tab_name in enumerate(REPORT_TABS):
            print(f"  [{i+1}/{len(REPORT_TABS)}] Capturing: {tab_name} ", end="", flush=True)

            # Click the tab button by its exact text
            tab_btn = page.locator(f"button:text-is('{tab_name}')").first
            tab_btn.click()

            # Wait for all loading spinners to disappear
            wait_ms = _wait_for_charts(page, tab_name)
            print(f"(loaded in {wait_ms}ms)")

            # For Overview tab, extra time for KPI grid
            if tab_name == "Overview":
                page.wait_for_timeout(1000)

            # Scroll to top to ensure consistent capture
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(400)

            # Take screenshot of the main content area
            filepath = os.path.join(tmp_dir, f"tab_{i:02d}_{tab_name.replace(' ', '_').replace('&', 'and')}.png")
            page.screenshot(path=filepath, full_page=True)
            screenshots.append({"tab": tab_name, "path": filepath, "index": i})

        browser.close()

    return screenshots


def build_pdf(screenshots: list[dict], company: str, product: str, output_path: str):
    """Compose screenshots into a professional PDF report."""
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import inch, mm
    from reportlab.lib.colors import Color, white, black
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from PIL import Image

    page_w, page_h = landscape(A4)
    margin = 28

    c = canvas.Canvas(output_path, pagesize=landscape(A4))
    c.setTitle(f"Laith — {company.upper()} Portfolio Analytics Report")
    c.setAuthor("Laith Portfolio Analytics Platform")
    c.setSubject(f"{company.upper()} / {product} — Dashboard Report")

    # ────────────────────────────────────────────────────────────────
    # COVER PAGE
    # ────────────────────────────────────────────────────────────────
    bg = rgb(BRAND["bg_base"])
    c.setFillColor(bg)
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    # Subtle border accent line at top
    c.setStrokeColor(rgb(BRAND["gold"]))
    c.setLineWidth(3)
    c.line(0, page_h - 4, page_w, page_h - 4)

    # Logo: L  AI  TH
    logo_y = page_h * 0.58
    c.setFont("Helvetica-Bold", 72)

    # "L" in white
    c.setFillColor(rgb(BRAND["text"]))
    l_w = c.stringWidth("L", "Helvetica-Bold", 72)
    ai_w = c.stringWidth("AI", "Helvetica-Bold", 72)
    th_w = c.stringWidth("TH", "Helvetica-Bold", 72)
    total_w = l_w + ai_w + th_w
    start_x = (page_w - total_w) / 2

    c.drawString(start_x, logo_y, "L")
    # "AI" in gold
    c.setFillColor(rgb(BRAND["gold"]))
    c.drawString(start_x + l_w, logo_y, "AI")
    # "TH" in white
    c.setFillColor(rgb(BRAND["text"]))
    c.drawString(start_x + l_w + ai_w, logo_y, "TH")

    # Tagline
    c.setFont("Helvetica", 11)
    c.setFillColor(rgb(BRAND["text_muted"]))
    tagline = "Portfolio Analytics Platform"
    c.drawCentredString(page_w / 2, logo_y - 30, tagline)

    # Horizontal rule
    rule_y = logo_y - 55
    c.setStrokeColor(rgb(BRAND["border"]))
    c.setLineWidth(0.5)
    rule_half = 140
    c.line(page_w/2 - rule_half, rule_y, page_w/2 + rule_half, rule_y)

    # Company name
    c.setFont("Helvetica-Bold", 32)
    c.setFillColor(rgb(BRAND["text"]))
    c.drawCentredString(page_w / 2, rule_y - 42, company.upper())

    # Product / description
    c.setFont("Helvetica", 13)
    c.setFillColor(rgb(BRAND["text_muted"]))
    # Smart title-case: preserve known acronyms (UAE, POS, etc.)
    ACRONYMS = {"uae", "pos", "spv", "irr", "dso", "hhi"}
    product_label = " ".join(
        w.upper() if w.lower() in ACRONYMS else w.title()
        for w in product.replace("_", " ").split()
    )
    c.drawCentredString(page_w / 2, rule_y - 65, product_label)

    # Date
    c.setFont("Helvetica", 11)
    c.setFillColor(rgb(BRAND["text_muted"]))
    report_date = datetime.now().strftime("%B %d, %Y")
    c.drawCentredString(page_w / 2, rule_y - 95, f"Report generated {report_date}")

    # Snapshot info
    c.setFont("Helvetica", 10)
    c.setFillColor(Color(201/255, 168/255, 76/255, 0.6))
    c.drawCentredString(page_w / 2, rule_y - 115, "Latest snapshot: 2026-03-03")

    # Confidential footer
    c.setFont("Helvetica", 8)
    c.setFillColor(rgb(BRAND["text_muted"]))
    c.drawCentredString(page_w / 2, 36, "CONFIDENTIAL  —  For authorised recipients only")

    # Small border at bottom
    c.setStrokeColor(rgb(BRAND["gold"]))
    c.setLineWidth(1.5)
    c.line(0, 2, page_w, 2)

    c.showPage()

    # ────────────────────────────────────────────────────────────────
    # TABLE OF CONTENTS
    # ────────────────────────────────────────────────────────────────
    c.setFillColor(bg)
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    # Gold accent line at top
    c.setStrokeColor(rgb(BRAND["gold"]))
    c.setLineWidth(2)
    c.line(0, page_h - 3, page_w, page_h - 3)

    # Title
    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(rgb(BRAND["text"]))
    c.drawString(margin + 20, page_h - 65, "Contents")

    # TOC entries
    toc_y = page_h - 110
    for i, s in enumerate(screenshots):
        page_num = i + 3  # cover=1, toc=2, tabs start at 3
        c.setFont("Helvetica", 12)
        c.setFillColor(rgb(BRAND["text"]))
        c.drawString(margin + 30, toc_y, f"{i+1}.")
        c.drawString(margin + 58, toc_y, s["tab"])

        # Dotted leader
        c.setFont("Helvetica", 10)
        c.setFillColor(rgb(BRAND["text_muted"]))
        dots_x_start = margin + 58 + c.stringWidth(s["tab"], "Helvetica", 12) + 8
        dots_x_end = page_w - margin - 60
        dot_text = " . " * int((dots_x_end - dots_x_start) / c.stringWidth(" . ", "Helvetica", 10))
        c.drawString(dots_x_start, toc_y, dot_text)

        # Page number
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(rgb(BRAND["gold"]))
        c.drawRightString(page_w - margin - 20, toc_y, str(page_num))

        toc_y -= 32

    # Footer
    c.setFont("Helvetica", 8)
    c.setFillColor(rgb(BRAND["text_muted"]))
    c.drawCentredString(page_w / 2, 20, f"Laith — {company.upper()} Portfolio Analytics Report")
    c.setStrokeColor(rgb(BRAND["gold"]))
    c.setLineWidth(1)
    c.line(0, 2, page_w, 2)

    c.showPage()

    # ────────────────────────────────────────────────────────────────
    # TAB PAGES
    # ────────────────────────────────────────────────────────────────
    for i, s in enumerate(screenshots):
        page_num = i + 3

        # Dark background
        c.setFillColor(bg)
        c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

        # ── Top header bar ──
        header_h = 36
        header_y = page_h - header_h
        c.setFillColor(rgb(BRAND["bg_surface"]))
        c.rect(0, header_y, page_w, header_h, fill=1, stroke=0)
        # Gold accent line below header
        c.setStrokeColor(rgb(BRAND["gold"]))
        c.setLineWidth(1.5)
        c.line(0, header_y, page_w, header_y)

        # Header: mini logo + tab name
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(rgb(BRAND["text_muted"]))
        c.drawString(margin, header_y + 12, "LAITH")
        c.setFillColor(rgb(BRAND["gold"]))
        separator_x = margin + c.stringWidth("LAITH", "Helvetica-Bold", 10) + 10
        c.drawString(separator_x, header_y + 12, "|")
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(rgb(BRAND["text"]))
        c.drawString(separator_x + 14, header_y + 12, s["tab"])

        # Page number on right
        c.setFont("Helvetica", 9)
        c.setFillColor(rgb(BRAND["text_muted"]))
        c.drawRightString(page_w - margin, header_y + 12, f"Page {page_num}")

        # ── Screenshot image ──
        img_path = s["path"]
        img = Image.open(img_path)
        img_w, img_h = img.size

        # Calculate available space
        avail_w = page_w - (margin * 2)
        avail_h = header_y - 28 - 20  # 28 bottom margin, 20 footer

        # Scale to fit
        scale = min(avail_w / img_w, avail_h / img_h)
        draw_w = img_w * scale
        draw_h = img_h * scale

        # Center horizontally, align to top
        draw_x = (page_w - draw_w) / 2
        draw_y = header_y - 8 - draw_h  # 8px gap from header

        # Clip to available space if image is very tall
        if draw_y < 24:
            # Image is taller than page — crop from top to fit
            crop_h = avail_h / scale
            img_cropped = img.crop((0, 0, img_w, int(crop_h)))
            draw_h = avail_h
            draw_y = 24
            # Save cropped version
            cropped_path = img_path.replace(".png", "_cropped.png")
            img_cropped.save(cropped_path)
            c.drawImage(cropped_path, draw_x, draw_y, width=draw_w, height=draw_h,
                       preserveAspectRatio=False)
        else:
            c.drawImage(img_path, draw_x, draw_y, width=draw_w, height=draw_h,
                       preserveAspectRatio=True)

        # ── Footer ──
        c.setFont("Helvetica", 7)
        c.setFillColor(rgb(BRAND["text_muted"]))
        c.drawCentredString(page_w / 2, 10, f"CONFIDENTIAL  |  {company.upper()} — {product_label}  |  {report_date}")
        c.setStrokeColor(rgb(BRAND["gold"]))
        c.setLineWidth(0.8)
        c.line(0, 2, page_w, 2)

        c.showPage()
        img.close()

    c.save()
    print(f"\n  PDF saved to: {output_path}")
    print(f"  Total pages: {len(screenshots) + 2} (cover + TOC + {len(screenshots)} tabs)")


def main():
    parser = argparse.ArgumentParser(description="Laith Portfolio Report Generator")
    parser.add_argument("--company", default="klaim", help="Company name")
    parser.add_argument("--product", default="UAE_healthcare", help="Product name")
    parser.add_argument("--output", default=None, help="Output PDF path")
    args = parser.parse_args()

    company = args.company
    product = args.product
    timestamp = datetime.now().strftime("%Y-%m-%d")
    output = args.output or os.path.join(
        "reports", f"{company}_{product}", f"Laith_{company.upper()}_Report_{timestamp}.pdf"
    )

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output), exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  LAITH — Portfolio Report Generator")
    print(f"  Company: {company.upper()} / {product}")
    print(f"  Date:    {timestamp}")
    print(f"{'='*60}\n")

    # Step 1: Capture screenshots
    print("[1/2] Capturing dashboard screenshots...")
    tmp_dir = tempfile.mkdtemp(prefix="laith_report_")
    try:
        screenshots = capture_tabs(company, product, tmp_dir)
        print(f"  Captured {len(screenshots)} tabs\n")

        # Step 2: Build PDF
        print("[2/2] Building PDF report...")
        build_pdf(screenshots, company, product, output)

    finally:
        # Clean up temp screenshots
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"\n{'='*60}")
    print(f"  Report complete!")
    print(f"  Output: {os.path.abspath(output)}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
