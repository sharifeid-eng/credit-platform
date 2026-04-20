"""
Living Mind — institutional memory for the Laith credit platform.

Three stores + one dynamic context assembly:
  - MasterMind: fund-level knowledge (preferences, IC norms, cross-co patterns,
                sector_context for fund-level macro/regulatory)
  - AssetClassMind: keyed by semantic asset-class name (e.g. "healthcare_receivables",
                    "bnpl", "pos_lending"); config.json's `asset_class` field — NOT
                    `analysis_type` — drives Layer 2.5 resolution. Categories:
                    benchmarks, typical_terms, external_research, sector_context,
                    peer_comparison, methodology_note.
  - CompanyMind: per-company knowledge (corrections, memo edits, findings,
                 data quality, entities)

build_mind_context() assembles a 6-layer knowledge context for any AI prompt:
    Layer 1   -- Framework (codified rules from FRAMEWORK_INDEX.md)
    Layer 2   -- Master Mind (fund-level lessons)
    Layer 2.5 -- Asset Class Mind (per-analysis_type, NEW)
    Layer 3   -- Methodology (codified company rules)
    Layer 4   -- Company Mind (company-level lessons)
    Layer 5   -- Thesis (investment thesis + drift alerts)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.mind.asset_class_mind import AssetClassMind
from core.mind.company_mind import CompanyMind
from core.mind.master_mind import MasterMind

logger = logging.getLogger(__name__)

__all__ = [
    "MasterMind", "CompanyMind", "AssetClassMind",
    "build_mind_context", "MindLayeredContext",
]


@dataclass
class MindLayeredContext:
    """The assembled 6-layer context for an AI prompt."""

    framework: str         # Layer 1:   codified framework principles
    master_mind: str       # Layer 2:   fund-level lessons
    asset_class: str = ""  # Layer 2.5: semantic asset-class benchmarks + external research
    methodology: str = ""  # Layer 3:   codified company methodology
    company_mind: str = "" # Layer 4:   company-level lessons
    thesis: str = ""       # Layer 5:   investment thesis + drift alerts
    total_entries: int = 0 # Total mind entries included (L2 + L2.5 + L4)

    # Structured citation sources contributing to Layer 2.5. Populated by
    # build_mind_context() when the resolved AssetClassMind has entries
    # with `metadata.citations` (typically web_search-approved entries).
    # Shape: [{"source": "web_search" | "manual" | ..., "entry_category":
    # "benchmarks" | ..., "entry_title": str, "url": str, "title": str,
    # "page_age": str}]. Frontend renders these under AI output so
    # analysts can see which external sources fed the response.
    asset_class_sources: List[Dict[str, str]] = field(default_factory=list)

    @property
    def formatted(self) -> str:
        """Return the full formatted context block, layers combined.

        Layers are separated by blank lines. Empty layers are omitted.
        Order: L1 Framework → L2 Master → L2.5 Asset Class → L3 Methodology
               → L4 Company → L5 Thesis. Asset Class sits where it does
        because it generalises Master Mind's fund-level statements and
        specialises them for the current analysis_type, while still being
        more general than company methodology.
        """
        parts = []
        if self.framework:
            parts.append(self.framework)
        if self.master_mind:
            parts.append(self.master_mind)
        if self.asset_class:
            parts.append(self.asset_class)
        if self.methodology:
            parts.append(self.methodology)
        if self.company_mind:
            parts.append(self.company_mind)
        if self.thesis:
            parts.append(self.thesis)
        return "\n\n".join(parts)

    @property
    def is_empty(self) -> bool:
        """True if no context was assembled at all."""
        return not any([
            self.framework, self.master_mind, self.asset_class,
            self.methodology, self.company_mind, self.thesis,
        ])


def _graph_query_to_formatted(mind_dir, query_text: str, header: str, categories=None, max_results: int = 15) -> tuple:
    """Use KnowledgeGraph for graph-aware retrieval, return (formatted_str, entry_count)."""
    from core.mind.graph import KnowledgeGraph
    from pathlib import Path

    graph = KnowledgeGraph(Path(mind_dir))
    nodes = graph.query(text=query_text, categories=categories, max_results=max_results)
    if not nodes:
        return "", 0

    lines = [f"--- {header} (graph-scored, {len(nodes)} entries) ---"]
    for node in nodes:
        lines.append(f"[{node.category}] {node.content}")
    return "\n".join(lines), len(nodes)


def build_mind_context(
    company: str,
    product: str,
    task_type: str,
    analysis_type: Optional[str] = None,
    section_key: Optional[str] = None,
    query_text: str = "",
) -> MindLayeredContext:
    """Build 5-layer knowledge context for any AI prompt.

    This is the primary integration point. Call this before any AI prompt to
    inject accumulated institutional knowledge.

    Layer 1 -- Framework: codified rules from FRAMEWORK_INDEX.md core principles.
               Always included. Provides the non-negotiable analytical rules.

    Layer 2 -- Master Mind: fund-level lessons (analytical preferences, IC norms,
               cross-company patterns, writing style). Filtered by task_type.

    Layer 3 -- Methodology: codified company-specific rules from the metric registry.
               Provides key formulas and caveats for this company/product.

    Layer 4 -- Company Mind: per-company lessons (corrections, memo edits, findings,
               data quality notes). Filtered by task_type and optional section_key.

    Layer 5 -- Investment Thesis: per-company thesis + drift alerts.

    When query_text is provided, Layers 2 and 4 use graph-aware scoring
    (KnowledgeGraph) instead of flat recency-based retrieval. This surfaces
    entries connected via knowledge relations and penalises contradicted nodes.

    Args:
        company: Company name (e.g., "klaim")
        product: Product name (e.g., "UAE_healthcare")
        task_type: The type of AI task. Determines which mind entries are relevant.
                   Valid values: "commentary", "executive_summary", "tab_insight",
                   "chat", "memo", "research_report", "onboarding", "validation",
                   "framework", "default"
        analysis_type: Override for analysis type. If None, derived from company config.
        section_key: Optional section to boost relevance for (e.g., "collection",
                     "risk_migration"). Used by Layer 4 scoring.
        query_text: Optional query text to enable graph-aware scoring for
                    Layers 2 and 4. When empty, falls back to flat retrieval.

    Returns:
        MindLayeredContext with all 5 layers assembled.
    """
    master = MasterMind()
    company_mind = CompanyMind(company, product)

    total_entries = 0

    # Layer 1: Framework principles (always included)
    try:
        framework_ctx = master.load_framework_context()
    except Exception as e:
        logger.warning("build_mind_context: Layer 1 (framework) failed: %s", e)
        framework_ctx = ""

    # Layer 2: Master Mind (fund-level)
    try:
        if query_text and master.base_dir.exists():
            master_formatted, master_count = _graph_query_to_formatted(
                master.base_dir, query_text, "Fund-Level Knowledge"
            )
            total_entries += master_count
        else:
            master_ctx = master.get_context_for_prompt(task_type, company=company)
            master_formatted = master_ctx.formatted
            total_entries += master_ctx.entry_count
    except Exception as e:
        logger.warning("build_mind_context: Layer 2 (master mind) failed: %s", e)
        master_formatted = ""

    # Layer 2.5: Asset Class Mind (semantic asset-class key)
    # Resolution order:
    #   1. Explicit `analysis_type` argument (caller override)
    #   2. config.json `asset_class` field — the preferred, semantic key
    #      (e.g. "healthcare_receivables", "bnpl", "pos_lending", "rnpl",
    #      "sme_trade_credit"). Multiple companies in the same asset class
    #      share a single Asset Class Mind file.
    #   3. config.json `analysis_type` — fallback for pre-`asset_class` configs.
    #      Usually the company shortname ("klaim", "silq") and won't match any
    #      on-disk asset class file, but kept for backward compatibility.
    asset_class_formatted = ""
    asset_class_sources: List[Dict[str, str]] = []
    resolved_at = analysis_type
    if resolved_at is None:
        try:
            from core.config import load_config
            cfg = load_config(company, product) or {}
            resolved_at = cfg.get("asset_class") or cfg.get("analysis_type")
        except Exception:
            resolved_at = None
    if resolved_at:
        try:
            ac_mind = AssetClassMind(resolved_at)
            ac_ctx = ac_mind.get_context_for_prompt(task_type)
            asset_class_formatted = ac_ctx.formatted
            total_entries += ac_ctx.entry_count
            # Flatten citation URLs from every entry's metadata into a
            # deduped list the frontend can render. Entries that share
            # the same URL (common — web_search agents often cite the
            # same landing page for related queries) collapse to one row.
            # Each row carries back-pointers (entry category + title +
            # source type) so the UI can show provenance.
            #
            # Cap at _MAX_SOURCES so the payload stays bounded even
            # after years of approved web_search entries accumulate. The
            # cap is generous — analysts asked for transparency, not
            # summarization — but prevents 10K-row UI renders.
            _MAX_SOURCES = 50
            _seen_urls: set = set()
            for e in getattr(ac_ctx, "entries", []) or []:
                if len(asset_class_sources) >= _MAX_SOURCES:
                    break
                meta = getattr(e, "metadata", {}) or {}
                cits = meta.get("citations") or []
                if not cits:
                    continue
                entry_source = meta.get("source", "unknown")
                entry_category = getattr(e, "category", "") or ""
                entry_title = meta.get("query") or (
                    (getattr(e, "content", "") or "")[:80]
                )
                for c in cits:
                    if len(asset_class_sources) >= _MAX_SOURCES:
                        break
                    if not isinstance(c, dict):
                        continue
                    url = c.get("url", "")
                    if not url or url in _seen_urls:
                        continue
                    _seen_urls.add(url)
                    asset_class_sources.append({
                        "source": entry_source,
                        "entry_category": entry_category,
                        "entry_title": entry_title,
                        "url": url,
                        "title": c.get("title", "") or "",
                        "page_age": c.get("page_age", "") or "",
                    })
        except Exception as e:
            logger.warning("build_mind_context: Layer 2.5 (asset class) failed: %s", e)
            asset_class_formatted = ""
            asset_class_sources = []

    # Layer 3: Methodology (codified company rules)
    try:
        methodology_ctx = master.load_methodology_context(company, product)
    except Exception as e:
        logger.warning("build_mind_context: Layer 3 (methodology) failed: %s", e)
        methodology_ctx = ""

    # Layer 4: Company Mind (per-company lessons)
    try:
        if query_text and company_mind.base_dir.exists():
            company_formatted, company_count = _graph_query_to_formatted(
                company_mind.base_dir, query_text,
                f"Company Knowledge: {company}/{product}"
            )
            total_entries += company_count
        else:
            company_ctx = company_mind.get_context_for_prompt(task_type, section_key=section_key)
            company_formatted = company_ctx.formatted
            total_entries += company_ctx.entry_count
    except Exception as e:
        logger.warning("build_mind_context: Layer 4 (company mind) failed: %s", e)
        company_formatted = ""

    # Layer 5: Investment Thesis (thesis + drift alerts)
    thesis_ctx = ""
    try:
        from core.mind.thesis import ThesisTracker
        tracker = ThesisTracker(company, product)
        thesis = tracker.load()
        if thesis:
            thesis_ctx = tracker.get_ai_context()
    except Exception as e:
        logger.warning("build_mind_context: Layer 5 (thesis) failed: %s", e)

    return MindLayeredContext(
        framework=framework_ctx,
        master_mind=master_formatted,
        asset_class=asset_class_formatted,
        methodology=methodology_ctx,
        company_mind=company_formatted,
        thesis=thesis_ctx,
        total_entries=total_entries,
        asset_class_sources=asset_class_sources,
    )
