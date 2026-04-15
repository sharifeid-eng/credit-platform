"""
IC Memo Templates — section definitions for four memo types.

Each template defines an ordered list of sections with:
  - key: unique identifier (used for storage, generation, editing)
  - title: display name for the section heading
  - required: whether the section must be present in a final memo
  - source: where the primary content comes from (SourceLayer)
  - ai_guided: whether AI generates a full narrative (vs structured data fill)
  - guidance: prompt-level instructions for AI generation
"""

from enum import Enum
from typing import Optional


class SourceLayer(Enum):
    """Where the section's primary content originates."""
    DATAROOM = "dataroom"
    ANALYTICS = "analytics"
    AI_NARRATIVE = "ai_narrative"
    MIXED = "mixed"
    MANUAL = "manual"
    AUTO = "auto"


# ── Template definitions ────────────────────────────────────────────────────

MEMO_TEMPLATES = {
    "credit_memo": {
        "name": "Credit Memo",
        "description": "Initial investment recommendation for IC approval",
        "sections": [
            {
                "key": "exec_summary",
                "title": "Executive Summary",
                "required": True,
                "source": "mixed",
                "ai_guided": True,
                "guidance": (
                    "2-3 paragraph overview: what the investment is, key thesis, "
                    "primary risks, recommendation. Reference specific metrics from "
                    "the analytics context."
                ),
            },
            {
                "key": "company_overview",
                "title": "Company Overview",
                "required": True,
                "source": "dataroom",
                "ai_guided": False,
                "guidance": (
                    "Company background, founders, key metrics (users, GMV, merchants), "
                    "regulatory status. Pull from data room documents."
                ),
            },
            {
                "key": "market_context",
                "title": "Market & Competitive Context",
                "required": False,
                "source": "dataroom",
                "ai_guided": False,
                "guidance": (
                    "Market size, competitive landscape, company positioning, "
                    "growth drivers."
                ),
            },
            {
                "key": "portfolio_analytics",
                "title": "Portfolio Analytics",
                "required": True,
                "source": "analytics",
                "ai_guided": False,
                "guidance": (
                    "Key portfolio metrics from tape analytics: collection rate, "
                    "PAR, DSO, deployment trends. Present data clearly with "
                    "context and trend direction."
                ),
            },
            {
                "key": "credit_quality",
                "title": "Credit Quality & Risk",
                "required": True,
                "source": "analytics",
                "ai_guided": False,
                "guidance": (
                    "PAR trends, loss waterfall, recovery analysis, underwriting "
                    "drift flags. Quantify risk using the analytics data provided."
                ),
            },
            {
                "key": "facility_structure",
                "title": "Facility Structure",
                "required": True,
                "source": "dataroom",
                "ai_guided": False,
                "guidance": (
                    "SPV, tranches, advance rates, concentration limits, maturity, "
                    "lenders. Structure details from facility agreements."
                ),
            },
            {
                "key": "covenant_analysis",
                "title": "Covenant Analysis",
                "required": True,
                "source": "mixed",
                "ai_guided": False,
                "guidance": (
                    "Covenant compliance status from both data room and live "
                    "analytics. Headroom analysis. Identify any triggers approaching."
                ),
            },
            {
                "key": "financial_performance",
                "title": "Financial Performance",
                "required": False,
                "source": "dataroom",
                "ai_guided": False,
                "guidance": (
                    "Revenue, margins, unit economics, profitability trajectory. "
                    "Historical financials and projections from data room."
                ),
            },
            {
                "key": "concentration_risk",
                "title": "Concentration Risk",
                "required": True,
                "source": "analytics",
                "ai_guided": False,
                "guidance": (
                    "HHI, top counterparty exposure, segment analysis. "
                    "Flag any concentration breaches or trends."
                ),
            },
            {
                "key": "stress_scenarios",
                "title": "Stress Scenarios",
                "required": True,
                "source": "analytics",
                "ai_guided": False,
                "guidance": (
                    "Provider shock, collection slowdown, denial spike scenarios "
                    "with impact estimates from the stress test engine."
                ),
            },
            {
                "key": "investment_thesis",
                "title": "Investment Thesis & Recommendation",
                "required": True,
                "source": "mixed",
                "ai_guided": True,
                "guidance": (
                    "Clear recommendation (invest/pass/watchlist), key conditions, "
                    "specific diligence items. Tie back to all preceding analysis. "
                    "Must reference specific metrics and thresholds."
                ),
            },
            {
                "key": "appendix",
                "title": "Appendix \u2014 Data Sources",
                "required": False,
                "source": "auto",
                "ai_guided": False,
                "guidance": (
                    "Auto-generated: list of all data room documents and analytics "
                    "snapshots used in this memo."
                ),
            },
        ],
    },

    "monitoring_update": {
        "name": "Monthly Monitoring Update",
        "description": "Periodic portfolio health check for existing positions",
        "sections": [
            {
                "key": "exec_summary",
                "title": "Executive Summary",
                "required": True,
                "source": "mixed",
                "ai_guided": True,
                "guidance": (
                    "One paragraph: overall health, any changes since last review, "
                    "action items."
                ),
            },
            {
                "key": "portfolio_performance",
                "title": "Portfolio Performance",
                "required": True,
                "source": "analytics",
                "ai_guided": False,
                "guidance": (
                    "Collection rate, deployment, denial trends vs prior period."
                ),
            },
            {
                "key": "credit_quality",
                "title": "Credit Quality Update",
                "required": True,
                "source": "analytics",
                "ai_guided": False,
                "guidance": (
                    "PAR movement, new vintage quality, any drift flags."
                ),
            },
            {
                "key": "covenant_compliance",
                "title": "Covenant Compliance",
                "required": True,
                "source": "mixed",
                "ai_guided": False,
                "guidance": (
                    "Current compliance status, headroom changes, any triggers "
                    "approaching."
                ),
            },
            {
                "key": "concentration_update",
                "title": "Concentration Update",
                "required": True,
                "source": "analytics",
                "ai_guided": False,
                "guidance": (
                    "HHI movement, any new concentration risks."
                ),
            },
            {
                "key": "action_items",
                "title": "Action Items & Watchlist",
                "required": True,
                "source": "mixed",
                "ai_guided": True,
                "guidance": (
                    "Specific items requiring attention, timeline, responsible party."
                ),
            },
        ],
    },

    "due_diligence": {
        "name": "Due Diligence Report",
        "description": "Deep-dive analysis for a new prospective company",
        "sections": [
            {
                "key": "exec_summary",
                "title": "Executive Summary",
                "required": True,
                "source": "mixed",
                "ai_guided": True,
                "guidance": (
                    "Investment opportunity overview, key findings, preliminary "
                    "recommendation."
                ),
            },
            {
                "key": "company_deep_dive",
                "title": "Company Deep Dive",
                "required": True,
                "source": "dataroom",
                "ai_guided": False,
                "guidance": (
                    "Comprehensive company analysis: history, management, strategy, "
                    "competitive moat."
                ),
            },
            {
                "key": "market_analysis",
                "title": "Market Analysis",
                "required": True,
                "source": "dataroom",
                "ai_guided": False,
                "guidance": (
                    "TAM/SAM/SOM, market dynamics, regulatory environment, growth "
                    "outlook."
                ),
            },
            {
                "key": "portfolio_analysis",
                "title": "Portfolio Analysis",
                "required": True,
                "source": "analytics",
                "ai_guided": False,
                "guidance": (
                    "Full tape analytics summary if available, or data room portfolio "
                    "data."
                ),
            },
            {
                "key": "risk_assessment",
                "title": "Risk Assessment",
                "required": True,
                "source": "mixed",
                "ai_guided": False,
                "guidance": (
                    "Credit risk, operational risk, regulatory risk, concentration "
                    "risk."
                ),
            },
            {
                "key": "facility_terms",
                "title": "Proposed Facility Terms",
                "required": True,
                "source": "dataroom",
                "ai_guided": False,
                "guidance": (
                    "Proposed structure, advance rates, covenants, pricing."
                ),
            },
            {
                "key": "financial_analysis",
                "title": "Financial Analysis",
                "required": True,
                "source": "dataroom",
                "ai_guided": False,
                "guidance": (
                    "P&L, balance sheet, cash flow, projections, unit economics."
                ),
            },
            {
                "key": "peer_comparison",
                "title": "Peer Comparison",
                "required": False,
                "source": "mixed",
                "ai_guided": False,
                "guidance": (
                    "How this company compares to existing portfolio companies."
                ),
            },
            {
                "key": "recommendation",
                "title": "Recommendation & Terms",
                "required": True,
                "source": "mixed",
                "ai_guided": True,
                "guidance": (
                    "Clear recommendation with specific terms, conditions, and "
                    "next steps."
                ),
            },
        ],
    },

    "quarterly_review": {
        "name": "Quarterly Review",
        "description": "Fund-level portfolio performance across all companies",
        "sections": [
            {
                "key": "exec_summary",
                "title": "Executive Summary",
                "required": True,
                "source": "mixed",
                "ai_guided": True,
                "guidance": (
                    "Fund-level overview: total exposure, aggregate performance, "
                    "key events."
                ),
            },
            {
                "key": "portfolio_overview",
                "title": "Portfolio Overview",
                "required": True,
                "source": "analytics",
                "ai_guided": False,
                "guidance": (
                    "All companies side-by-side: face value, collection rates, "
                    "PAR, HHI."
                ),
            },
            {
                "key": "company_updates",
                "title": "Company-by-Company Updates",
                "required": True,
                "source": "mixed",
                "ai_guided": False,
                "guidance": (
                    "One section per company with key metrics and developments."
                ),
            },
            {
                "key": "risk_dashboard",
                "title": "Risk Dashboard",
                "required": True,
                "source": "analytics",
                "ai_guided": False,
                "guidance": (
                    "Fund-level risk metrics: aggregate PAR, concentration, "
                    "covenant compliance."
                ),
            },
            {
                "key": "outlook",
                "title": "Outlook & Recommendations",
                "required": True,
                "source": "mixed",
                "ai_guided": True,
                "guidance": (
                    "Forward-looking assessment, pipeline, recommended actions."
                ),
            },
        ],
    },

    "amendment_memo": {
        "name": "Amendment Memo",
        "description": "Facility amendment analysis — size changes, covenant modifications, impact assessment",
        "sections": [
            {
                "key": "exec_summary",
                "title": "Executive Summary",
                "required": True,
                "source": "mixed",
                "ai_guided": True,
                "guidance": (
                    "1-2 paragraph overview: what is being amended, rationale, "
                    "net impact on borrowing capacity and risk profile. "
                    "Reference specific before/after metrics."
                ),
            },
            {
                "key": "facility_size_changes",
                "title": "Facility Size Changes",
                "required": True,
                "source": "dataroom",
                "ai_guided": False,
                "guidance": (
                    "Old vs new facility limit, availability impact, "
                    "tranche-level changes if applicable. "
                    "Pull from amended facility agreement."
                ),
            },
            {
                "key": "advance_rate_modifications",
                "title": "Advance Rate Modifications",
                "required": True,
                "source": "dataroom",
                "ai_guided": False,
                "guidance": (
                    "Old vs new advance rates by product/segment/region. "
                    "Impact on eligible receivable base and borrowing base."
                ),
            },
            {
                "key": "covenant_amendments",
                "title": "Covenant Amendments",
                "required": True,
                "source": "mixed",
                "ai_guided": False,
                "guidance": (
                    "Old thresholds vs new thresholds for each modified covenant. "
                    "Rationale for changes. Impact on compliance headroom."
                ),
            },
            {
                "key": "concentration_limit_updates",
                "title": "Concentration Limit Updates",
                "required": True,
                "source": "analytics",
                "ai_guided": False,
                "guidance": (
                    "Tier changes, new single-borrower limits, sector caps. "
                    "Identify currently breaching counterparties affected."
                ),
            },
            {
                "key": "covenant_compliance_impact",
                "title": "Covenant Compliance Impact",
                "required": True,
                "source": "analytics",
                "ai_guided": False,
                "guidance": (
                    "Headroom analysis under new covenants using current portfolio "
                    "metrics. Flag any covenants that move from compliant to "
                    "breaching or vice versa."
                ),
            },
            {
                "key": "recommendation",
                "title": "Recommendation",
                "required": True,
                "source": "mixed",
                "ai_guided": True,
                "guidance": (
                    "Net effect on borrowing capacity, risk profile, and fund "
                    "economics. Clear recommendation (approve/reject/negotiate). "
                    "Specific conditions or counter-proposals if applicable."
                ),
            },
            {
                "key": "implementation_timeline",
                "title": "Implementation Timeline",
                "required": True,
                "source": "manual",
                "ai_guided": False,
                "guidance": (
                    "Effective date, transition period, required approvals, "
                    "operational steps for implementation."
                ),
            },
            {
                "key": "appendix",
                "title": "Appendix \u2014 Old vs New Terms",
                "required": False,
                "source": "auto",
                "ai_guided": False,
                "guidance": (
                    "Auto-generated: side-by-side comparison of old vs new "
                    "facility agreement terms. Uses legal extraction diff engine."
                ),
            },
        ],
    },
}


# ── Public API ──────────────────────────────────────────────────────────────

def get_template(template_key: str) -> Optional[dict]:
    """Get a memo template by key. Returns None if not found."""
    return MEMO_TEMPLATES.get(template_key)


def list_templates() -> list:
    """List all available templates with name, description, section count."""
    result = []
    for key, tmpl in MEMO_TEMPLATES.items():
        result.append({
            "key": key,
            "name": tmpl["name"],
            "description": tmpl["description"],
            "section_count": len(tmpl["sections"]),
            "required_sections": sum(
                1 for s in tmpl["sections"] if s.get("required")
            ),
        })
    return result
