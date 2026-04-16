"""
Document type classification for data room files.

Uses rules-based classification by filename patterns and optional text preview.
"""

import re
from enum import Enum
from pathlib import Path


class DocumentType(Enum):
    """Categories of documents commonly found in private credit data rooms."""

    FACILITY_AGREEMENT = "facility_agreement"
    INVESTOR_REPORT = "investor_report"
    FDD_REPORT = "fdd_report"
    FINANCIAL_MODEL = "financial_model"
    FINANCIAL_STATEMENT = "financial_statement"
    TAX_FILING = "tax_filing"
    VINTAGE_COHORT = "vintage_cohort"
    PORTFOLIO_TAPE = "portfolio_tape"
    LEGAL_DOCUMENT = "legal_document"
    COMPANY_PRESENTATION = "company_presentation"
    DEMOGRAPHICS = "demographics"
    BUSINESS_PLAN = "business_plan"
    CREDIT_POLICY = "credit_policy"
    SALES_DATA = "sales_data"
    DEBT_OVERVIEW = "debt_overview"
    ANALYTICS_TAPE = "analytics_tape"
    ANALYTICS_PORTFOLIO = "analytics_portfolio"
    ANALYTICS_AI_SUMMARY = "analytics_ai"
    ANALYTICS_REPORT = "analytics_report"
    MEMO_DRAFT = "memo_draft"
    MEMO_FINAL = "memo_final"
    OTHER = "other"


# ── Filename keyword rules ────────────────────────────────────────────────────
# Each rule: (compiled regex pattern, DocumentType)
# Patterns are tested against the lowercased full file path (including parent dirs).

_FILENAME_RULES = [
    # Facility / loan agreements
    (re.compile(r"(facility|agreement|loan.?doc|credit.?agreement|term.?sheet|indenture)"), DocumentType.FACILITY_AGREEMENT),
    # Investor reports (monthly/quarterly reporting)
    (re.compile(r"(investor.?report|monthly.?report|quarterly.?report|hsbc|trustee.?report)"), DocumentType.INVESTOR_REPORT),
    # Financial due diligence
    (re.compile(r"(fdd|due.?diligence|deloitte|kpmg|ey\b|pwc|ernst)"), DocumentType.FDD_REPORT),
    # Financial models
    (re.compile(r"(financial.?model|financial.?master|fin.?model|valuation.?model)"), DocumentType.FINANCIAL_MODEL),
    # Tax filings (must be before financial statements — "Financial Statements (USA)/US Tax Return" has both keywords)
    (re.compile(r"(tax.?return|tax.?filing|tax.?report|vat.?return|zakat)"), DocumentType.TAX_FILING),
    # Financial statements (audited, management, consolidated)
    (re.compile(r"(audited.?financial|financial.?statement|consolidated.?financial|management.?account|annual.?report|\bfs\b.*\d{4}|\bfs\b.*20[2-3]\d)"), DocumentType.FINANCIAL_STATEMENT),
    # Debt / facility overview
    (re.compile(r"(debt.?facilit|debt.?overview|facility.?overview|facility.?summary|borrowing.?summary)"), DocumentType.DEBT_OVERVIEW),
    # Credit policies
    (re.compile(r"(credit.?polic|underwriting.?polic|risk.?polic|lending.?polic|collection.?polic)"), DocumentType.CREDIT_POLICY),
    # Sales / pipeline data
    (re.compile(r"(sales.?funnel|sales.?pipeline|sales.?data|pipeline.?report|sales.?track)"), DocumentType.SALES_DATA),
    # Vintage / cohort data
    (re.compile(r"(vintage|cohort|default.?rat|delinquen|dilution|dpd|roll.?rate|loss.?curve)"), DocumentType.VINTAGE_COHORT),
    # Portfolio / loan tapes (including date-named files: YYYY-MM-DD_*.csv/xlsx)
    (re.compile(r"(loan.?tape|portfolio.?tape|receivable|loan.?book|tape.?data)"), DocumentType.PORTFOLIO_TAPE),
    (re.compile(r"\d{4}-\d{2}-\d{2}_.*\.(csv|xlsx?)$"), DocumentType.PORTFOLIO_TAPE),
    # Legal documents
    (re.compile(r"(legal|najiz|court|litigation|arbitrat|enforcement|judgment)"), DocumentType.LEGAL_DOCUMENT),
    # Presentations / decks / investor materials
    (re.compile(r"(presentation|deck|pitch|investor.?day|overview.?deck|pptx?|v\s?amwal|investor.?pack)"), DocumentType.COMPANY_PRESENTATION),
    # Demographics / market data
    (re.compile(r"(demographic|breakdown|population|market.?data|segmentation|customer.?profile)"), DocumentType.DEMOGRAPHICS),
    # Business plan / projections
    (re.compile(r"(business.?plan|projection|forecast|budget|strategic.?plan|5.?year)"), DocumentType.BUSINESS_PLAN),
    # Memos
    (re.compile(r"(memo.?final|ic.?memo|credit.?memo|investment.?memo)"), DocumentType.MEMO_FINAL),
    (re.compile(r"(memo.?draft|draft.?memo|working.?memo)"), DocumentType.MEMO_DRAFT),
    # Analytics outputs (from Laith platform)
    (re.compile(r"(analytics.?tape|tape.?analytics)"), DocumentType.ANALYTICS_TAPE),
    (re.compile(r"(analytics.?portfolio|portfolio.?analytics)"), DocumentType.ANALYTICS_PORTFOLIO),
    (re.compile(r"(ai.?summary|executive.?summary|ai.?commentary)"), DocumentType.ANALYTICS_AI_SUMMARY),
    (re.compile(r"(research.?report|compliance.?cert|integrity.?report)"), DocumentType.ANALYTICS_REPORT),
]

# ── Text preview rules (checked if filename rules don't match) ────────────────
# Each rule: (compiled regex pattern, DocumentType)
# Patterns are tested against the first ~500 chars of extracted text.

_TEXT_RULES = [
    (re.compile(r"(facility\s+agreement|credit\s+agreement|loan\s+agreement|security\s+interest)", re.IGNORECASE), DocumentType.FACILITY_AGREEMENT),
    (re.compile(r"(investor\s+report|monthly\s+report|trustee\s+report|reporting\s+period)", re.IGNORECASE), DocumentType.INVESTOR_REPORT),
    (re.compile(r"(financial\s+due\s+diligence|scope\s+of\s+work|fdd|agreed.upon\s+procedures)", re.IGNORECASE), DocumentType.FDD_REPORT),
    (re.compile(r"(financial\s+model|dcf|wacc|irr\s+sensitivity|net\s+present\s+value)", re.IGNORECASE), DocumentType.FINANCIAL_MODEL),
    (re.compile(r"(vintage\s+cohort|cumulative\s+default|delinquency\s+rate|loss\s+development)", re.IGNORECASE), DocumentType.VINTAGE_COHORT),
    (re.compile(r"(business\s+plan|revenue\s+projection|5.year\s+plan|growth\s+strategy)", re.IGNORECASE), DocumentType.BUSINESS_PLAN),
    # Portfolio / loan tapes (CSV/Excel with loan-related column headers)
    (re.compile(r"(loan.?id|principal.?amount|disburs|days.?past.?due|collection.?rate|outstanding.?balance|maturity.?date|dpd|purchase.?value|collected.?till)", re.IGNORECASE), DocumentType.PORTFOLIO_TAPE),
]


def classify_document(filepath: str, text_preview: str = None) -> DocumentType:
    """Classify a document by filename patterns and optional text preview.

    Classification strategy:
    1. Check filename + parent directory names against keyword rules
    2. If no match and text_preview provided, check text content rules
    3. Fall back to DocumentType.OTHER

    Args:
        filepath: Full path to the document file.
        text_preview: Optional first ~500 characters of extracted text for
                      content-based classification.

    Returns:
        The detected DocumentType enum value.
    """
    # Normalize path for matching: lowercase, forward slashes
    path_str = str(Path(filepath)).lower().replace("\\", "/")

    # Phase 1: filename/path rules
    for pattern, doc_type in _FILENAME_RULES:
        if pattern.search(path_str):
            return doc_type

    # Phase 2: text preview rules
    if text_preview:
        preview = text_preview[:2000]  # Cap to prevent regex on huge strings
        for pattern, doc_type in _TEXT_RULES:
            if pattern.search(preview):
                return doc_type

    return DocumentType.OTHER
