"""
Mind / Knowledge Tools — query institutional memory, thesis, knowledge graph.
"""

from __future__ import annotations

import logging
from typing import Optional

from core.agents.tools import registry

logger = logging.getLogger(__name__)


def _query_knowledge_base(
    query: str,
    company: Optional[str] = None,
    categories: Optional[str] = None,
    max_results: int = 10,
) -> str:
    try:
        from core.mind.kb_query import KnowledgeBaseQuery
        kb = KnowledgeBaseQuery()
        cat_list = [c.strip() for c in categories.split(",")] if categories else None
        results = kb.search(query, company=company, categories=cat_list, max_results=max_results)

        if not results:
            return f"No knowledge found for query: '{query}'"

        lines = [f"Knowledge Base Results for '{query}' ({len(results)} results):"]
        for r in results:
            score = r.get("score", 0)
            source = r.get("source", "?")
            content = r.get("content", r.get("text", ""))[:200]
            category = r.get("category", "")
            lines.append(f"\n  [{score:.1f}] ({source}/{category}) {content}")

        return "\n".join(lines)
    except Exception as e:
        return f"Knowledge base query error: {e}"


def _get_mind_context(
    company: str, product: str,
    task_type: str = "chat",
) -> str:
    try:
        from core.mind import build_mind_context
        ctx = build_mind_context(company, product, task_type=task_type)
        if ctx.is_empty:
            return "No institutional context available for this company."
        return f"Institutional Context ({ctx.total_entries} entries):\n{ctx.formatted}"
    except Exception as e:
        return f"Mind context error: {e}"


def _get_thesis(company: str, product: str) -> str:
    try:
        from core.mind.thesis import ThesisTracker
        tracker = ThesisTracker(company, product)
        thesis = tracker.load()

        if not thesis:
            return f"No investment thesis defined for {company}/{product}"

        lines = [f"Investment Thesis — {company}/{product}"]
        lines.append(f"  Title: {thesis.get('title', 'Untitled')}")
        lines.append(f"  Status: {thesis.get('status', 'unknown')}")
        lines.append(f"  Conviction: {thesis.get('conviction_score', 0)}/100")

        pillars = thesis.get("pillars", [])
        for p in pillars:
            name = p.get("name", "?")
            metric = p.get("metric_key", "?")
            threshold = p.get("threshold", "?")
            status = p.get("status", "?")
            lines.append(f"  Pillar: {name}")
            lines.append(f"    Metric: {metric} {p.get('operator', '>')} {threshold}")
            lines.append(f"    Status: {status}")

        return "\n".join(lines)
    except Exception as e:
        return f"Thesis load error: {e}"


def _check_thesis_drift(company: str, product: str) -> str:
    try:
        from core.mind.thesis import ThesisTracker
        tracker = ThesisTracker(company, product)
        alerts = tracker.check_drift()

        if not alerts:
            return f"No thesis drift detected for {company}/{product} — all pillars holding."

        lines = [f"Thesis Drift Alerts — {company}/{product} ({len(alerts)} alerts):"]
        for a in alerts:
            pillar = a.get("pillar_name", "?")
            severity = a.get("severity", "?")
            message = a.get("message", "")
            lines.append(f"  [{severity.upper()}] {pillar}: {message}")

        return "\n".join(lines)
    except Exception as e:
        return f"Thesis drift check error: {e}"


def _get_company_profile(company: str, product: str) -> str:
    try:
        from core.mind.company_mind import CompanyMind
        mind = CompanyMind(company, product)
        profile = mind.get_company_profile()

        lines = [f"Company Profile — {company}/{product}"]
        cats = profile.get("categories", {})
        if cats:
            lines.append(f"  Knowledge entries by category:")
            for cat, count in cats.items():
                lines.append(f"    {cat}: {count}")

        findings = profile.get("key_findings", [])
        if findings:
            lines.append(f"  Key findings ({len(findings)}):")
            for f in findings[:5]:
                lines.append(f"    - {f}")

        issues = profile.get("data_quality_issues", [])
        if issues:
            lines.append(f"  Data quality issues ({len(issues)}):")
            for i in issues[:3]:
                lines.append(f"    - {i}")

        return "\n".join(lines)
    except Exception as e:
        return f"Company profile error: {e}"


def _record_finding(
    company: str, product: str,
    finding: str,
    confidence: str = "medium",
) -> str:
    try:
        from core.mind.company_mind import CompanyMind
        from core.mind.event_bus import event_bus, Events

        mind = CompanyMind(company, product)
        entry = mind.record_research_finding(finding, confidence=confidence)

        # Publish event for other listeners
        try:
            event_bus.publish(Events.MIND_ENTRY_CREATED, {
                "company": company,
                "product": product,
                "entry_id": entry.id if hasattr(entry, "id") else "unknown",
                "category": "research_finding",
                "source": "agent",
            })
        except Exception:
            pass

        return f"Finding recorded for {company}/{product}: '{finding[:100]}...' (confidence: {confidence})"
    except Exception as e:
        return f"Failed to record finding: {e}"


def _get_cross_company_patterns() -> str:
    try:
        from core.mind.intelligence import IntelligenceEngine
        engine = IntelligenceEngine()
        patterns = engine.detect_patterns()

        if not patterns:
            return "No cross-company patterns detected."

        lines = [f"Cross-Company Patterns ({len(patterns)} detected):"]
        for p in patterns[:10]:
            pattern_type = p.get("type", "?")
            companies = p.get("companies", [])
            score = p.get("score", 0)
            description = p.get("description", "")
            lines.append(f"  [{score:.1f}] {pattern_type}: {description}")
            lines.append(f"    Companies: {', '.join(companies)}")

        return "\n".join(lines)
    except Exception as e:
        return f"Pattern detection error: {e}"


# ── Registration ─────────────────────────────────────────────────────────

registry.register(
    "mind.query_knowledge_base",
    "Search the unified knowledge base across all mind entries, lessons, decisions, and entities.",
    {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "company": {"type": "string", "description": "Filter to specific company (optional)"},
            "categories": {"type": "string", "description": "Comma-separated category filter (optional)"},
            "max_results": {"type": "integer", "description": "Max results (default 10)"},
        },
        "required": ["query"],
    },
    _query_knowledge_base,
)

registry.register(
    "mind.get_context",
    "Load the full 5-layer institutional context (Framework, Master Mind, Methodology, Company Mind, Thesis) for a company.",
    {
        "type": "object",
        "properties": {
            "company": {"type": "string", "description": "Company name"},
            "product": {"type": "string", "description": "Product name"},
            "task_type": {"type": "string", "description": "Context type: chat, commentary, executive_summary, memo, research_report"},
        },
        "required": ["company", "product"],
    },
    _get_mind_context,
)

registry.register(
    "mind.get_thesis",
    "Load the current investment thesis for a company including pillars, conviction score, and status.",
    {
        "type": "object",
        "properties": {
            "company": {"type": "string", "description": "Company name"},
            "product": {"type": "string", "description": "Product name"},
        },
        "required": ["company", "product"],
    },
    _get_thesis,
)

registry.register(
    "mind.check_thesis_drift",
    "Check if any investment thesis pillars are weakening or broken based on latest metrics.",
    {
        "type": "object",
        "properties": {
            "company": {"type": "string", "description": "Company name"},
            "product": {"type": "string", "description": "Product name"},
        },
        "required": ["company", "product"],
    },
    _check_thesis_drift,
)

registry.register(
    "mind.get_company_profile",
    "Get a synthesized view of everything known about a company: knowledge categories, key findings, data quality issues.",
    {
        "type": "object",
        "properties": {
            "company": {"type": "string", "description": "Company name"},
            "product": {"type": "string", "description": "Product name"},
        },
        "required": ["company", "product"],
    },
    _get_company_profile,
)

registry.register(
    "mind.record_finding",
    "Record a research finding or insight for a company. This persists in the company's institutional memory.",
    {
        "type": "object",
        "properties": {
            "company": {"type": "string", "description": "Company name"},
            "product": {"type": "string", "description": "Product name"},
            "finding": {"type": "string", "description": "The finding or insight to record"},
            "confidence": {"type": "string", "description": "Confidence level: high, medium, low", "enum": ["high", "medium", "low"]},
        },
        "required": ["company", "product", "finding"],
    },
    _record_finding,
)

registry.register(
    "mind.get_cross_company_patterns",
    "Detect patterns across all portfolio companies: metric trends, risk convergence, covenant pressure.",
    {
        "type": "object",
        "properties": {},
    },
    _get_cross_company_patterns,
)
