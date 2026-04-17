"""
Data Room Tools — search and browse ingested documents.
"""

from __future__ import annotations

import logging
from typing import Optional

from core.agents.tools import registry

logger = logging.getLogger(__name__)


def _search_dataroom(
    company: str, product: str, query: str,
    top_k: int = 10,
    doc_types: Optional[str] = None,
) -> str:
    from core.dataroom.engine import DataRoomEngine

    engine = DataRoomEngine()
    results = engine.search(company, product, query, top_k=top_k * 2)

    # Filter by doc type if requested
    if doc_types:
        type_list = [t.strip().lower() for t in doc_types.split(",")]
        results = [r for r in results if r.get("doc_type", "").lower() in type_list]

    results = results[:top_k]

    if not results:
        return f"No results found in {company} data room for query: '{query}'"

    lines = [f"Data Room Search Results for '{query}' ({len(results)} results):"]
    for i, r in enumerate(results, 1):
        doc_type = r.get("doc_type", "unknown")
        filename = r.get("filename", r.get("filepath", "?"))
        score = r.get("score", 0)
        text = r.get("text", "")[:300]
        lines.append(f"\n[Source {i}] {filename} ({doc_type}, score: {score:.2f})")
        lines.append(f"  {text}")

    return "\n".join(lines)


def _get_document_text(company: str, product: str, doc_id: str) -> str:
    from core.dataroom.engine import DataRoomEngine

    engine = DataRoomEngine()
    doc = engine.get_document(company, product, doc_id)

    if not doc or doc.get("error"):
        return f"Document not found: {doc_id}"

    chunks = doc.get("chunks", [])
    filename = doc.get("filepath", doc_id)
    doc_type = doc.get("doc_type", "unknown")

    text_parts = [chunk.get("text", "") for chunk in chunks]
    full_text = "\n\n".join(text_parts)

    # Truncate to avoid context overflow
    if len(full_text) > 10_000:
        full_text = full_text[:10_000] + "\n\n... [truncated — document too long, use search for specific sections]"

    return f"Document: {filename} ({doc_type})\n\n{full_text}"


def _list_dataroom_documents(company: str, product: str) -> str:
    from core.dataroom.engine import DataRoomEngine

    engine = DataRoomEngine()
    docs = engine.catalog(company, product)

    if not docs:
        return f"No documents ingested for {company}/{product}"

    lines = [f"Data Room — {company} ({len(docs)} documents):"]
    for d in docs:
        doc_id = d.get("id", "?")
        filename = d.get("filepath", "?")
        doc_type = d.get("doc_type", "unknown")
        pages = d.get("page_count", d.get("pages", "?"))
        lines.append(f"  [{doc_id}] {filename} — {doc_type}, {pages} pages")

    return "\n".join(lines)


def _get_analytics_snapshots(company: str, product: str) -> str:
    from core.dataroom.analytics_snapshot import AnalyticsSnapshotEngine

    engine = AnalyticsSnapshotEngine()
    snapshots = engine.list_snapshots(company, product)

    if not snapshots:
        return f"No analytics snapshots for {company}/{product}"

    lines = [f"Analytics Snapshots — {company}/{product} ({len(snapshots)}):"]
    for s in snapshots[-10:]:
        snap_id = s.get("id", "?")
        snap_type = s.get("type", "?")
        created = s.get("created_at", "?")
        lines.append(f"  [{snap_id}] {snap_type} — {created}")

    return "\n".join(lines)


# ── Registration ─────────────────────────────────────────────────────────

registry.register(
    "dataroom.search",
    "Search across all ingested data room documents using text similarity. Returns relevant chunks with source citations.",
    {
        "type": "object",
        "properties": {
            "company": {"type": "string", "description": "Company name"},
            "product": {"type": "string", "description": "Product name"},
            "query": {"type": "string", "description": "Search query (natural language)"},
            "top_k": {"type": "integer", "description": "Max results to return (default 10)", "default": 10},
            "doc_types": {"type": "string", "description": "Comma-separated doc type filter (optional, e.g., 'facility_agreement,investor_report')"},
        },
        "required": ["company", "product", "query"],
    },
    _search_dataroom,
)

registry.register(
    "dataroom.get_document_text",
    "Read the full text of a specific document by its ID. Use list_dataroom_documents first to find IDs.",
    {
        "type": "object",
        "properties": {
            "company": {"type": "string", "description": "Company name"},
            "product": {"type": "string", "description": "Product name"},
            "doc_id": {"type": "string", "description": "Document ID from list_dataroom_documents"},
        },
        "required": ["company", "product", "doc_id"],
    },
    _get_document_text,
)

registry.register(
    "dataroom.list_documents",
    "List all ingested documents in the company's data room with types and page counts.",
    {
        "type": "object",
        "properties": {
            "company": {"type": "string", "description": "Company name"},
            "product": {"type": "string", "description": "Product name"},
        },
        "required": ["company", "product"],
    },
    _list_dataroom_documents,
)

registry.register(
    "dataroom.get_analytics_snapshots",
    "List analytics snapshots (tape summaries, PAR, DSO) that were saved as research sources.",
    {
        "type": "object",
        "properties": {
            "company": {"type": "string", "description": "Company name"},
            "product": {"type": "string", "description": "Product name"},
        },
        "required": ["company", "product"],
    },
    _get_analytics_snapshots,
)
