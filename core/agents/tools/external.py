"""External Intelligence tools — web search via Claude.

Exposes one agent tool, `external.web_search`, which performs a web search
using Anthropic's server-side web_search_20250305 tool and writes every
result to the pending-review queue. NOTHING is auto-written to any Mind —
every external finding requires analyst approval via the Operator UI.

The tool handler:
  1. Makes a nested Claude call with web_search_20250305 enabled
  2. Extracts web_search_tool_result citations + synthesized answer
  3. For each distinct citation, creates a PendingEntry in the queue
  4. Returns a summary string for the agent to pass to the analyst
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core.agents.tools import registry
from core.external.pending_review import PendingReviewQueue, TargetScope

logger = logging.getLogger(__name__)

# Anthropic's native web_search tool spec. Handled server-side by the API —
# results come back as web_search_tool_result blocks with citations.
_WEB_SEARCH_TOOL_SPEC = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 5,
}

# Categories allowed per target scope — validated here so the agent can't
# write into a slot that doesn't exist.
_VALID_CATEGORIES = {
    "company":     {"findings", "data_quality", "ic_feedback"},
    "asset_class": {"external_research", "sector_context", "benchmarks", "peer_comparison"},
    "master":      {"sector_context", "framework_evolution"},
}


def _extract_citations_from_response(resp) -> List[Dict[str, Any]]:
    """Walk an Anthropic Message response and pull out web_search results.

    Handles the server-side web_search_20250305 result block shape:
        {type: "web_search_tool_result", content: [{type: "web_search_result",
          title, url, encrypted_content?, page_age?}, ...]}
    """
    citations: List[Dict[str, Any]] = []
    for block in getattr(resp, "content", []) or []:
        btype = getattr(block, "type", None) or (block.get("type") if isinstance(block, dict) else None)
        if btype != "web_search_tool_result":
            continue
        inner = getattr(block, "content", None) or (block.get("content") if isinstance(block, dict) else [])
        for item in inner or []:
            itype = getattr(item, "type", None) or (item.get("type") if isinstance(item, dict) else None)
            if itype != "web_search_result":
                continue
            title = getattr(item, "title", None) or (item.get("title") if isinstance(item, dict) else "") or ""
            url = getattr(item, "url", None) or (item.get("url") if isinstance(item, dict) else "") or ""
            page_age = getattr(item, "page_age", None) or (item.get("page_age") if isinstance(item, dict) else None)
            if url:
                citations.append({
                    "url": url,
                    "title": title,
                    "page_age": page_age or "",
                })
    return citations


def _extract_synthesis_text(resp) -> str:
    """Pull the assistant's synthesized text (the non-tool-result content)."""
    parts: List[str] = []
    for block in getattr(resp, "content", []) or []:
        btype = getattr(block, "type", None) or (block.get("type") if isinstance(block, dict) else None)
        if btype == "text":
            text = getattr(block, "text", None) or (block.get("text") if isinstance(block, dict) else "")
            if text:
                parts.append(text)
    return "\n\n".join(parts).strip()


def _web_search(
    query: str,
    target_scope: str = "asset_class",
    target_key: Optional[str] = None,
    category: str = "external_research",
) -> str:
    """Run a web search, stash results in pending-review queue.

    Args:
        query: The search query (plain English, as specific as possible).
        target_scope: Where approved results should eventually land.
                      One of "company" | "asset_class" | "master".
        target_key: Company name (if scope=company), analysis_type (if
                    scope=asset_class), or None (if scope=master).
        category: The mind category to tag the approved entry with — must
                  be valid for the chosen target_scope.
    """
    # Validate inputs
    if target_scope not in _VALID_CATEGORIES:
        return (f"Invalid target_scope '{target_scope}'. "
                f"Must be one of: {sorted(_VALID_CATEGORIES.keys())}.")
    allowed = _VALID_CATEGORIES[target_scope]
    if category not in allowed:
        return (f"Invalid category '{category}' for target_scope='{target_scope}'. "
                f"Allowed: {sorted(allowed)}.")
    if target_scope in ("company", "asset_class") and not target_key:
        return f"target_key is required when target_scope='{target_scope}'."
    if target_scope == "master" and target_key:
        return "target_key must be omitted when target_scope='master'."

    # Perform the search via Anthropic's server-side web_search tool
    try:
        from core.ai_client import complete
        resp = complete(
            tier="research",
            system=(
                "You are a research assistant. Use the web_search tool to answer "
                "the user's query about private credit, fintech, or asset-backed "
                "lending. Return a concise synthesized answer (3-6 sentences). "
                "Prioritise authoritative sources (regulators, industry reports, "
                "reputable news outlets)."
            ),
            messages=[{"role": "user", "content": query}],
            max_tokens=1500,
            tools=[_WEB_SEARCH_TOOL_SPEC],
            log_prefix="external.web_search",
        )
    except Exception as e:
        logger.exception("web_search: Anthropic call failed")
        return f"Web search failed: {e}"

    citations = _extract_citations_from_response(resp)
    synthesis = _extract_synthesis_text(resp)

    if not citations and not synthesis:
        return "Web search returned no usable results."

    # Write ONE pending-review entry containing the full synthesis + every
    # citation. One entry per search keeps analyst review tractable — they
    # can drill into citations via URL if they want detail.
    try:
        queue = PendingReviewQueue()
        entry = queue.add(
            source="web_search",
            target_scope=TargetScope(target_scope),
            target_key=target_key,
            category=category,
            title=query[:120],
            content=synthesis or "(no synthesis text)",
            citations=citations,
            query=query,
        )
    except Exception as e:
        logger.exception("web_search: pending-review queue write failed")
        return f"Search completed but pending-review write failed: {e}"

    cite_count = len(citations)
    scope_label = f"{target_scope}" + (f"/{target_key}" if target_key else "")
    summary = (
        f"Web search complete. {cite_count} source{'s' if cite_count != 1 else ''} collected. "
        f"One entry queued for analyst review → target: {scope_label} · category: {category}. "
        f"Pending ID: {entry.id[:8]}\n\n"
        f"Synthesis:\n{synthesis[:800]}"
    )
    if cite_count:
        summary += "\n\nSources:\n" + "\n".join(
            f"  - {c['title'] or '(no title)'}: {c['url']}" for c in citations[:5]
        )
        if cite_count > 5:
            summary += f"\n  ... and {cite_count - 5} more"
    return summary


# ── Registration ─────────────────────────────────────────────────────────────

registry.register(
    "external.web_search",
    (
        "Search the public web for information the platform doesn't already know. "
        "Every result lands in the pending-review queue for analyst approval — NOT "
        "written directly to any Mind. Use this for sector trends, regulatory changes, "
        "peer benchmarks, company news, or any knowledge the analyst hasn't uploaded. "
        "Always specify where the finding should eventually land (company / asset_class / master) "
        "and what category it represents."
    ),
    {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query in plain English. Be specific — include asset class, geography, and time frame where relevant.",
            },
            "target_scope": {
                "type": "string",
                "enum": ["company", "asset_class", "master"],
                "description": "Where this finding should eventually land after analyst approval.",
            },
            "target_key": {
                "type": "string",
                "description": "Required if scope is 'company' (company name, e.g. 'klaim') or 'asset_class' (analysis_type, e.g. 'bnpl'). Omit for 'master'.",
            },
            "category": {
                "type": "string",
                "description": (
                    "The mind category to tag. Valid categories by scope:\n"
                    "  company:     findings | data_quality | ic_feedback\n"
                    "  asset_class: external_research | sector_context | benchmarks | peer_comparison\n"
                    "  master:      sector_context | framework_evolution"
                ),
            },
        },
        "required": ["query", "target_scope", "category"],
    },
    _web_search,
)


__all__ = ["_web_search"]
