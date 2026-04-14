#!/usr/bin/env python3
"""
Aajil Data Preparation Script
================================
Extracts structured data from the Aajil investor deck PDF and any
supplementary files in the data room. Produces a JSON snapshot for
the Laith platform.

Output:
  data/Aajil/KSA/2026-04-14_aajil_ksa.json

Usage:
  python scripts/prepare_aajil_data.py
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_OUT = PROJECT_ROOT / "data" / "Aajil" / "KSA"


def build_snapshot():
    """Build the Aajil KSA JSON snapshot from investor deck data.

    Currently, the data is manually extracted from the 47-page investor
    deck. When the loan tape arrives from Cascade Debt, this script will
    be replaced by direct tape parsing.
    """

    data = {
        "metadata": {
            "company": "Aajil",
            "product": "KSA",
            "source": "Investor Deck (Mar 2026) — 03.2026 - Aajil - vAmwal - vF.pdf",
            "snapshot_date": "2026-04-14",
            "currency": "SAR",
            "analysis_type": "aajil",
            "data_completeness": "partial",
            "notes": "Extracted from investor pitch deck. Tape data from Cascade Debt pending."
        },

        # ── Company Overview (from pages 1-2, 8-9) ─────────────────────
        "company_overview": {
            "name": "Aajil",
            "parent": "Buildnow",
            "founded": 2022,
            "sector": "SME lending — industrial raw materials trade credit",
            "country": "Saudi Arabia",
            "currency": "SAR",
            "employees": 64,
            "total_customers": 206,
            "total_transactions": 1136,
            "avg_deals_per_customer": 4,
            "credit_as_pct_revenue": "2.5% - 5.0%",
            "pn_coverage": 1.0,
            "dpd60_plus_rate": 0.05,
            "dpd60_plus_note": "Last twelve months data as of December 2025",
            "aum_sar": 120000000,
            "aum_usd": 30000000,
            "gmv_sar": 340000000,
            "gmv_usd": 90000000,
            "avg_tenor_months": 4.5,
            "max_tenor_months": 6,
            "repayment_structure": "Instalments",
            "tam_sar": 277000000000,
            "sam_sar": 150000000000,
            "som_sar": 2000000000,
            "document_upload_time_seconds": 10,
            "kyb_assessment": "Instantaneous",
            "credit_deployment_hours": 24,
            "investors": [
                "SIC (Sovereign Wealth Fund)",
                "Khawrizmi Ventures",
                "RAED",
                "Arbah Capital",
                "STV",
                "Al-Raedah Finance",
                "JOA Capital"
            ]
        },

        # ── Customer Growth (from page 8) ───────────────────────────────
        "customer_growth": [
            {"date": "2023-06-30", "total_customers": 23},
            {"date": "2023-12-31", "total_customers": 48},
            {"date": "2024-06-30", "total_customers": 66},
            {"date": "2024-12-31", "total_customers": 85},
            {"date": "2025-06-30", "total_customers": 138},
            {"date": "2025-11-30", "total_customers": 206}
        ],

        # ── GMV Milestones (from page 9) ────────────────────────────────
        "gmv_milestones": [
            {"year": 2022, "gmv_sar": 14000000, "gmv_usd": 4000000},
            {"year": 2023, "gmv_sar": 75000000, "gmv_usd": 20000000},
            {"year": 2024, "gmv_sar": 156000000, "gmv_usd": 42000000},
            {"year": 2025, "gmv_sar": 320000000, "gmv_usd": 85000000}
        ],

        # ── Customer Types (from page 2, 29-30) ────────────────────────
        "customer_types": [
            {
                "type": "Manufacturer",
                "description": "Industrial manufacturers purchasing raw materials",
                "min_gross_margin": 0.06,
                "min_net_margin": 0.01,
                "min_current_ratio": 0.8,
                "ideal_gross_margin": "20-34%",
                "ideal_net_margin": "4-10%"
            },
            {
                "type": "Contractor",
                "description": "Construction and project-based contractors",
                "min_gross_margin": 0.07,
                "min_net_margin": 0.01,
                "min_current_ratio": 0.8,
                "ideal_gross_margin": "20-34%",
                "ideal_net_margin": "7-10%"
            },
            {
                "type": "Wholesale Trader",
                "description": "Wholesale trading companies",
                "min_gross_margin": 0.07,
                "min_net_margin": 0.01,
                "min_current_ratio": 0.8,
                "ideal_gross_margin": "20-34%",
                "ideal_net_margin": "4-10%"
            }
        ],

        # ── Sales Channels (from page 21) ───────────────────────────────
        "sales_channels": [
            {"channel": "Performance Marketing", "pct": 34},
            {"channel": "Outbound Prospecting", "pct": 33},
            {"channel": "Referral Networks", "pct": 25},
            {"channel": "Field Sales", "pct": 8}
        ],

        # ── Underwriting (from pages 23-32) ─────────────────────────────
        "underwriting": {
            "stages": [
                "Sales Screening",
                "Risk Assessment",
                "Credit Report",
                "Credit Decision Committee"
            ],
            "avg_assessment_hours": 4,
            "reassessment_time_minutes": 30,
            "min_revenue_sar": 5000000,
            "revenue_variance_threshold": 0.10,
            "max_leverage": 0.50,
            "max_funded_exposure_pct": 0.30,
            "max_total_exposure_pct": 0.50,
            "non_cdc_approval_limit_sar": 400000,
            "non_cdc_max_cashflow_pct": 0.04,
            "disqualification_rules": [
                "Revenue below SAR 5M in last 12 months",
                "Revenue variance >10% between bank/VAT sources",
                "Continuous revenue decline >20%/year for 3 consecutive years",
                "Manufacturers/Traders: >40% revenue decline in one year",
                "Contractors: 25-39% decline + pipeline <30% of revenue",
                "Leverage >50% with current ratio <1.0",
                "Funded exposure >30% of revenue",
                "Active legal cases (company or personal)",
                "Past due obligations without proof of payment",
                "Revenue fluctuation: months 1-3 avg <= 50% of months 4-6 avg"
            ]
        },

        # ── Trust Score System (from pages 35, 42) ──────────────────────
        "trust_score_system": {
            "scores": [
                {"score": 5, "label": "Green", "description": "Good history, enablement-first approach"},
                {"score": 4, "label": "Amber", "description": "Minor delays, tighter timelines"},
                {"score": 3, "label": "Red", "description": "Repeated issues, bank statement required"},
                {"score": 2, "label": "Critical", "description": "Severe default risk, 48h payment deadline"},
                {"score": 1, "label": "Critical", "description": "Extreme risk, immediate escalation"}
            ],
            "collections_phases": [
                {
                    "phase": "Preventive",
                    "dpd_range": "-15 to 0",
                    "description": "Proactive reminders, payment facilitation, SIMAH incentives"
                },
                {
                    "phase": "Active",
                    "dpd_range": "1 to 60",
                    "description": "Personal calls, site visits, escalation to senior management"
                },
                {
                    "phase": "Legal",
                    "dpd_range": "60+",
                    "description": "Promissory note enforcement, SIMAH classification, asset recovery"
                }
            ],
            "simah_npl_notice_days": 150,
            "simah_auto_report_days": 180
        },

        # ── Risk Mitigation (from page 7) ───────────────────────────────
        "risk_mitigation": [
            {"factor": "Minimal Exposure", "detail": "Credit at 2.5-5.0% of client revenue"},
            {"factor": "Diversification", "detail": "Multiple sectors: manufacturer, contractor, trader"},
            {"factor": "Asset-Based", "detail": "Purchasing raw materials directly, not disbursing cash"},
            {"factor": "Short Duration", "detail": "4-5 month avg tenor, max 6 months"},
            {"factor": "Robust Collections", "detail": "Automated messages, site visits, calls, legal"},
            {"factor": "Promissory Notes", "detail": "100% PN coverage for each issuance"},
            {"factor": "Credit Assessment", "detail": "Technical, financial, and legal assessment"},
            {"factor": "Instalments", "detail": "Instalment repayment, not bullet at maturity"}
        ],

        # ── Technology Stack (from page 2) ──────────────────────────────
        "technology": {
            "platforms": ["R-Square (deal orchestration)", "C-Square (credit intelligence)", "Basirah (AI document intelligence)"],
            "stack": ["FastAPI", "Django", "PostgreSQL", "BigQuery", "Docker", "Kubernetes", "Redis", "Celery", "Sentry"],
            "ai_tools": ["Claude", "OpenAI", "Gemini", "Google AI Studio", "Neo4j"]
        },

        # ── DPD Reassessment Rules (from page 35) ──────────────────────
        "dpd_reassessment": [
            {"dpd_range": "1-10", "policy": "Eligible for standard reassessment"},
            {"dpd_range": "11-29 (compliant)", "policy": "New facility if trust score >= 80 AND bank confirms liquidity shortfall"},
            {"dpd_range": "11-29 (non-compliant)", "policy": "Trust score < 80: disqualified (behavioural default)"},
            {"dpd_range": "11-29 (with liquidity)", "policy": "Bank confirms >= 200% available: disqualified"},
            {"dpd_range": "30+ (first facility)", "policy": "Suspended min 2 quarters, full reassessment required"},
            {"dpd_range": "30+ (wilful)", "policy": "Permanently disqualified if cash >= 150% of past due on due date"}
        ],

        # ── Financial Ratio Thresholds (from page 29) ───────────────────
        "financial_thresholds": {
            "gross_profit_margin": {
                "Contractor": {"minimum": 0.07, "acceptable": "8-19%", "ideal": "20-34%", "strong": "35%+"},
                "Manufacturer": {"minimum": 0.06, "acceptable": "7-19%", "ideal": "20-34%", "strong": "35%+"},
                "Wholesale Trader": {"minimum": 0.07, "acceptable": "8-19%", "ideal": "20-34%", "strong": "35%+"}
            },
            "net_profit_margin": {
                "Contractor": {"minimum": 0.01, "acceptable": "2.5-7%", "ideal": "7-10%", "strong": "10%+"},
                "Manufacturer": {"minimum": 0.01, "acceptable": "2.5-4%", "ideal": "4-10%", "strong": "10%+"},
                "Wholesale Trader": {"minimum": 0.01, "acceptable": "2.5-4%", "ideal": "4-10%", "strong": "10%+"}
            },
            "current_ratio": {
                "Contractor": {"minimum": 0.8, "acceptable": "0.8-0.9", "ideal": "1.2-1.5", "strong": "1.5+"},
                "Manufacturer": {"minimum": 0.8, "acceptable": "0.8-0.9", "ideal": "1.0-1.5", "strong": "1.5+"},
                "Wholesale Trader": {"minimum": 0.8, "acceptable": "0.8-0.9", "ideal": "1.0-1.5", "strong": "1.5+"}
            }
        },

        # ── Cascade Debt Platform Info ──────────────────────────────────
        "cascade_debt": {
            "note": "Aajil uses Cascade Debt (app.cascadedebt.com) for portfolio analytics",
            "features_observed": [
                "Traction (Volume + Balance)",
                "Delinquency (Rolling Default Rate at 7/30/60/90 DPD)",
                "Collection (Cash Collected by Cohort with payment breakdown)",
                "Cohort (Vintage Analysis with cure toggle, loan/borrower toggle)",
                "Analytics Pro (Weekly Collection Rates — Total vs Principal)",
                "Display by segmentation (Customer Type, Loan Grade, Product Type, Term Group, VAT/Non-VAT)"
            ],
            "data_as_of": "2026-04-14",
            "dpd_thresholds": [7, 30, 60, 90]
        },

        # ── Data Notes ──────────────────────────────────────────────────
        "data_notes": [
            "All data extracted from investor deck (Mar 2026), not from loan tape",
            "Loan tape expected from Cascade Debt platform — will enable full analytics",
            "DPD60+ < 5% is a self-reported trailing-12-month figure (Dec 2025)",
            "GMV figures are cumulative disbursements, not outstanding balance",
            "AUM (SAR 120M) represents current outstanding balance",
            "Customer count (206) is cumulative served, not necessarily all active",
            "Financial ratio thresholds vary by customer type (Contractor vs Manufacturer vs Trader)",
            "Trust score system (1-5) is Aajil's proprietary collections prioritization model",
            "Buildnow is the parent company; Aajil is the product/brand name",
            "Technology: FastAPI+Django backend, multiple AI integrations (Claude, OpenAI, Gemini)"
        ]
    }

    return data


def main():
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot()
    out_path = DATA_OUT / "2026-04-14_aajil_ksa.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
    print(f"Written: {out_path}")
    print(f"  Sections: {len(snapshot)}")


if __name__ == '__main__':
    main()
