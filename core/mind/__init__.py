"""
Living Mind — institutional memory for the Laith credit platform.

Three stores + one dynamic context assembly:
  - MasterMind: fund-level knowledge (preferences, IC norms, cross-co patterns,
                sector_context for fund-level macro/regulatory)
  - AssetClassMind: keyed by analysis_type (benchmarks, typical terms, external
                    research, sector_context, peer_comparison)
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
from dataclasses import dataclass
from typing import Optional

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
    asset_class: str = ""  # Layer 2.5: per-analysis_type benchmarks + external research
    methodology: str = ""  # Layer 3:   codified company methodology
    company_mind: str = "" # Layer 4:   company-level lessons
    thesis: str = ""       # Layer 5:   investment thesis + drift alerts
    total_entries: int = 0 # Total mind entries included (L2 + L2.5 + L4)

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

    # Layer 2.5: Asset Class Mind (per-analysis_type)
    # Resolved analysis_type is either passed in, or pulled from company config.
    asset_class_formatted = ""
    resolved_at = analysis_type
    if resolved_at is None:
        try:
            from core.config import load_config
            cfg = load_config(company, product) or {}
            resolved_at = cfg.get("analysis_type")
        except Exception:
            resolved_at = None
    if resolved_at:
        try:
            ac_mind = AssetClassMind(resolved_at)
            ac_ctx = ac_mind.get_context_for_prompt(task_type)
            asset_class_formatted = ac_ctx.formatted
            total_entries += ac_ctx.entry_count
        except Exception as e:
            logger.warning("build_mind_context: Layer 2.5 (asset class) failed: %s", e)
            asset_class_formatted = ""

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
    )
