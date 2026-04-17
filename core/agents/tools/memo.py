"""
Memo Tools — templates, storage, analytics bridge for IC memo generation.
"""

from __future__ import annotations

import logging
from typing import Optional

from core.agents.tools import registry

logger = logging.getLogger(__name__)


def _get_memo_templates() -> str:
    try:
        from core.memo.templates import MEMO_TEMPLATES as TEMPLATES
        lines = ["Available IC Memo Templates:"]
        for key, tmpl in TEMPLATES.items():
            lines.append(f"\n  Template: {key}")
            lines.append(f"    Name: {tmpl.get('name', key)}")
            lines.append(f"    Description: {tmpl.get('description', '')}")
            sections = tmpl.get("sections", [])
            lines.append(f"    Sections ({len(sections)}):")
            for s in sections:
                lines.append(f"      - {s.get('key', '?')}: {s.get('title', '?')}")
        return "\n".join(lines)
    except Exception as e:
        return f"Failed to load memo templates: {e}"


def _get_prior_memos(
    company: Optional[str] = None,
    product: Optional[str] = None,
    status: Optional[str] = None,
) -> str:
    try:
        from core.memo.storage import MemoStorage
        storage = MemoStorage()
        memos = storage.list_memos(company=company, product=product, status=status)

        if not memos:
            return f"No memos found" + (f" for {company}/{product}" if company else "")

        lines = [f"Memos ({len(memos)} total):"]
        for m in memos[:10]:
            lines.append(f"  [{m.get('id', '?')[:8]}] {m.get('title', 'Untitled')}")
            lines.append(f"    Template: {m.get('template_name', '?')}, Status: {m.get('status', '?')}")
            lines.append(f"    Created: {m.get('created_at', '?')}, Version: {m.get('current_version', 1)}")
        return "\n".join(lines)
    except Exception as e:
        return f"Failed to load memos: {e}"


def _get_section_analytics(
    company: str, product: str, section_key: str,
    snapshot: Optional[str] = None,
    currency: Optional[str] = None,
) -> str:
    try:
        from core.memo.analytics_bridge import AnalyticsBridge
        bridge = AnalyticsBridge()
        ctx = bridge.get_section_context(company, product, section_key, snapshot=snapshot, currency=currency)

        if not ctx or not ctx.get("available"):
            return f"No analytics context available for section '{section_key}'"

        lines = [f"Analytics for memo section '{section_key}':"]

        # Metrics
        metrics = ctx.get("metrics", [])
        if metrics:
            lines.append("  Key metrics:")
            for m in metrics:
                label = m.get("label", "?")
                value = m.get("value", "?")
                assessment = m.get("assessment", "")
                lines.append(f"    {label}: {value}" + (f" [{assessment}]" if assessment else ""))

        # Narrative text
        text = ctx.get("text", "")
        if text:
            lines.append(f"\n  Narrative context:\n  {text[:500]}")

        return "\n".join(lines)
    except Exception as e:
        return f"Failed to load section analytics: {e}"


def _get_section_research(
    company: str, product: str, section_key: str,
    top_k: int = 5,
) -> str:
    """Search data room for content relevant to a memo section."""
    try:
        from core.memo.templates import MEMO_TEMPLATES as TEMPLATES

        # Map section keys to search queries
        section_queries = {}
        for tmpl in TEMPLATES.values():
            for s in tmpl.get("sections", []):
                key = s.get("key", "")
                title = s.get("title", "")
                guidance = s.get("guidance", "")
                section_queries[key] = f"{title} {guidance}"

        query = section_queries.get(section_key, section_key)

        from core.dataroom.engine import DataRoomEngine
        engine = DataRoomEngine()
        results = engine.search(company, product, query, top_k=top_k)

        if not results:
            return f"No data room content found for section '{section_key}'"

        lines = [f"Research for section '{section_key}' ({len(results)} results):"]
        for i, r in enumerate(results, 1):
            filename = r.get("filename", r.get("filepath", "?"))
            text = r.get("text", "")[:400]
            lines.append(f"\n  [Source {i}] {filename}")
            lines.append(f"  {text}")

        return "\n".join(lines)
    except Exception as e:
        return f"Section research error: {e}"


# ── Registration ─────────────────────────────────────────────────────────

registry.register(
    "memo.get_templates",
    "List all available IC memo templates with their sections and descriptions.",
    {"type": "object", "properties": {}},
    _get_memo_templates,
)

registry.register(
    "memo.get_prior_memos",
    "List existing memos, optionally filtered by company/product/status.",
    {
        "type": "object",
        "properties": {
            "company": {"type": "string", "description": "Filter by company (optional)"},
            "product": {"type": "string", "description": "Filter by product (optional)"},
            "status": {"type": "string", "description": "Filter by status: draft, review, final (optional)"},
        },
    },
    _get_prior_memos,
)

registry.register(
    "memo.get_section_analytics",
    "Get live analytics metrics relevant to a specific memo section (maps section key to compute functions).",
    {
        "type": "object",
        "properties": {
            "company": {"type": "string", "description": "Company name"},
            "product": {"type": "string", "description": "Product name"},
            "section_key": {"type": "string", "description": "Memo section key (e.g., 'portfolio_overview', 'credit_quality')"},
            "snapshot": {"type": "string", "description": "Snapshot filename (optional)"},
            "currency": {"type": "string", "description": "Display currency (optional)"},
        },
        "required": ["company", "product", "section_key"],
    },
    _get_section_analytics,
)

registry.register(
    "memo.get_section_research",
    "Search data room for content relevant to a specific memo section.",
    {
        "type": "object",
        "properties": {
            "company": {"type": "string", "description": "Company name"},
            "product": {"type": "string", "description": "Product name"},
            "section_key": {"type": "string", "description": "Memo section key"},
            "top_k": {"type": "integer", "description": "Max results (default 5)"},
        },
        "required": ["company", "product", "section_key"],
    },
    _get_section_research,
)
