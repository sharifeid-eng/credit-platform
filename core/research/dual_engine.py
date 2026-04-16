"""
Research engine for the Laith credit platform.

Wraps the Claude RAG query engine to provide a consistent interface
for research queries across all ingested documents.

Usage::

    engine = DualResearchEngine()
    result = engine.query("klaim", "UAE_healthcare",
                          "What is the current PAR 30+ rate?")
    print(result["answer"])
    print(result["engine"])  # "claude"
"""

from __future__ import annotations

import logging
from typing import Optional

from core.research.query_engine import ClaudeQueryEngine

logger = logging.getLogger(__name__)


class DualResearchEngine:
    """Research engine wrapping Claude RAG for document queries.

    Provides a consistent interface for research queries. Previously
    orchestrated Claude RAG + NotebookLM; now Claude-only.
    """

    def __init__(
        self,
        dataroom_engine=None,
    ):
        """Initialise the research engine.

        Args:
            dataroom_engine: Optional DataRoomEngine instance to share with
                the Claude query engine. If None, a default is created.
        """
        self.claude_engine = ClaudeQueryEngine(dataroom_engine=dataroom_engine)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def query(
        self,
        company: str,
        product: str,
        question: str,
        include_analytics: bool = True,
        doc_types: Optional[list[str]] = None,
        top_k: int = 10,
    ) -> dict:
        """Execute a research query through Claude RAG.

        Args:
            company: Company slug.
            product: Product slug.
            question: Natural-language research question.
            include_analytics: Include analytics snapshots in context.
            doc_types: Optional filter for document types.
            top_k: Number of retrieval chunks for Claude RAG.

        Returns:
            Dict with keys:
                ``answer``: Final answer text.
                ``citations``: Source citations.
                ``engine``: ``"claude"`` | ``"retrieval_only"``.
                ``claude_answer``: Claude's answer (or None).
                ``chunks_searched``: Number of chunks searched.
                ``mind_context_used``: Whether mind context was injected.
        """
        claude_result = self.claude_engine.query(
            company=company,
            product=product,
            question=question,
            doc_types=doc_types,
            include_analytics=include_analytics,
            top_k=top_k,
        )

        return {
            "answer": claude_result.get("answer", ""),
            "citations": claude_result.get("citations", []),
            "engine": claude_result.get("engine", "claude"),
            "claude_answer": claude_result.get("answer"),
            "chunks_searched": claude_result.get("chunks_searched", 0),
            "mind_context_used": claude_result.get("mind_context_used", False),
        }

    def deep_research(
        self,
        company: str,
        product: str,
        topic: str,
    ) -> dict:
        """Extended research query (delegates to standard query).

        Args:
            company: Company slug.
            product: Product slug.
            topic: Research topic.

        Returns:
            Dict with the same schema as ``query()`` plus ``deep_research``.
        """
        result = self.query(
            company=company,
            product=product,
            question=f"Research topic: {topic}",
            include_analytics=True,
        )
        result["deep_research"] = True
        return result
