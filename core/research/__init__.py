"""
Research Intelligence Layer for the Laith credit platform.

Provides Claude-powered RAG query engine, rules-based insight extraction,
and research orchestration.

Key classes:
    ClaudeQueryEngine   -- RAG query with Claude synthesis + citations
    DualResearchEngine  -- Research orchestrator (Claude RAG)

Key functions:
    extract_insights    -- Rules-based insight extraction at ingest time
"""

from core.research.query_engine import ClaudeQueryEngine
from core.research.extractors import extract_insights
from core.research.dual_engine import DualResearchEngine

__all__ = [
    "ClaudeQueryEngine",
    "extract_insights",
    "DualResearchEngine",
]
