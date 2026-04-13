"""
Living Mind — Two-tier institutional memory for the Laith credit platform.

Master Mind: Fund-level knowledge (analytical preferences, IC norms, cross-company patterns)
Company Mind: Per-company knowledge (corrections, memo edits, findings, data quality)

The build_mind_context() function assembles a 5-layer knowledge context for any AI prompt:
    Layer 1 -- Framework (codified rules from FRAMEWORK_INDEX.md)
    Layer 2 -- Master Mind (fund-level lessons)
    Layer 3 -- Methodology (codified company rules)
    Layer 4 -- Company Mind (company-level lessons)
    Layer 5 -- Thesis (investment thesis + drift alerts)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from core.mind.company_mind import CompanyMind
from core.mind.master_mind import MasterMind

logger = logging.getLogger(__name__)

__all__ = ["MasterMind", "CompanyMind", "build_mind_context", "MindLayeredContext"]


@dataclass
class MindLayeredContext:
    """The assembled 5-layer context for an AI prompt."""

    framework: str       # Layer 1: codified framework principles
    master_mind: str     # Layer 2: fund-level lessons
    methodology: str     # Layer 3: codified company methodology
    company_mind: str    # Layer 4: company-level lessons
    thesis: str = ""     # Layer 5: investment thesis + drift alerts
    total_entries: int = 0  # Total mind entries included (L2 + L4)

    @property
    def formatted(self) -> str:
        """Return the full formatted context block, all 5 layers combined.

        Layers are separated by blank lines. Empty layers are omitted.
        """
        parts = []
        if self.framework:
            parts.append(self.framework)
        if self.master_mind:
            parts.append(self.master_mind)
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
        return not any([self.framework, self.master_mind, self.methodology, self.company_mind, self.thesis])


def build_mind_context(
    company: str,
    product: str,
    task_type: str,
    analysis_type: Optional[str] = None,
    section_key: Optional[str] = None,
) -> MindLayeredContext:
    """Build 4-layer knowledge context for any AI prompt.

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

    Returns:
        MindLayeredContext with all 4 layers assembled.
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
        master_ctx = master.get_context_for_prompt(task_type, company=company)
        master_formatted = master_ctx.formatted
        total_entries += master_ctx.entry_count
    except Exception as e:
        logger.warning("build_mind_context: Layer 2 (master mind) failed: %s", e)
        master_formatted = ""

    # Layer 3: Methodology (codified company rules)
    try:
        methodology_ctx = master.load_methodology_context(company, product)
    except Exception as e:
        logger.warning("build_mind_context: Layer 3 (methodology) failed: %s", e)
        methodology_ctx = ""

    # Layer 4: Company Mind (per-company lessons)
    try:
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
        methodology=methodology_ctx,
        company_mind=company_formatted,
        thesis=thesis_ctx,
        total_entries=total_entries,
    )
