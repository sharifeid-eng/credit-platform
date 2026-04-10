"""
Research Intelligence Layer for the Laith credit platform.

Provides Claude-powered RAG query engine, rules-based insight extraction,
dual-engine orchestration (Claude + NotebookLM), and answer synthesis.

Key classes:
    ClaudeQueryEngine   -- RAG query with Claude synthesis + citations
    DualResearchEngine  -- Orchestrates Claude and NotebookLM engines
    ResearchSynthesizer -- Merges answers from multiple engines
    NotebookLMEngine    -- Bridge to notebooklm-py (Python + CLI)

Key functions:
    extract_insights    -- Rules-based insight extraction at ingest time
"""

from core.research.query_engine import ClaudeQueryEngine
from core.research.extractors import extract_insights
from core.research.dual_engine import DualResearchEngine
from core.research.synthesizer import ResearchSynthesizer
from core.research.notebooklm_bridge import NotebookLMEngine

__all__ = [
    "ClaudeQueryEngine",
    "extract_insights",
    "DualResearchEngine",
    "ResearchSynthesizer",
    "NotebookLMEngine",
]
