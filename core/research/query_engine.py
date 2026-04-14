"""
Claude-powered RAG query engine for the Laith credit platform.

Retrieves relevant document chunks from DataRoomEngine.search(), enriches
with analytics snapshots and living mind context, then synthesises an answer
via the Claude API with structured source citations.
"""

from __future__ import annotations

import logging
import os
import textwrap
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ClaudeQueryEngine:
    """RAG query engine using internal document chunks + Claude for synthesis.

    Pipeline:
        1. Retrieve relevant chunks from DataRoomEngine.search()
        2. Optionally include analytics snapshots (tape/portfolio metrics)
        3. Build a prompt with retrieved context + mind context
        4. Send to Claude for synthesis with citations
        5. Return structured answer with source citations

    If the Anthropic API is unavailable (missing key, network error), the
    engine degrades gracefully and returns retrieval-only results.
    """

    MODEL = "claude-opus-4-6"
    MAX_TOKENS = 2000
    # Maximum characters of retrieved context to feed into the prompt.
    # Prevents token overflow on very large data rooms.
    MAX_CONTEXT_CHARS = 60_000

    def __init__(self, dataroom_engine=None):
        """Initialise the query engine.

        Args:
            dataroom_engine: An existing DataRoomEngine instance. If None,
                a default one rooted at the project ``data/`` folder is created.
        """
        if dataroom_engine is not None:
            self._dr = dataroom_engine
        else:
            from core.dataroom.engine import DataRoomEngine
            self._dr = DataRoomEngine()

        # Lazy-init Anthropic client on first query
        self._client = None
        self._client_checked = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def query(
        self,
        company: str,
        product: str,
        question: str,
        doc_types: Optional[list[str]] = None,
        include_analytics: bool = True,
        top_k: int = 10,
    ) -> dict:
        """Execute a full RAG query with Claude synthesis.

        Args:
            company: Company slug (e.g. ``"klaim"``).
            product: Product slug (e.g. ``"UAE_healthcare"``).
            question: Natural-language question from the analyst.
            doc_types: Optional filter — only search docs of these types.
            include_analytics: Whether to pull analytics snapshots as extra context.
            top_k: Number of top retrieval chunks to use (default 10).

        Returns:
            Dict with keys: ``answer``, ``citations``, ``engine``,
            ``chunks_searched``, ``mind_context_used``.
        """
        # Step 1 — retrieve chunks
        raw_chunks = self._dr.search(company, product, question, top_k=top_k * 2)

        # Optional doc_type filter
        if doc_types:
            types_set = set(doc_types)
            raw_chunks = [
                c for c in raw_chunks
                if c.get("document_type") in types_set
            ]

        chunks = raw_chunks[:top_k]

        # Step 2 — build mind context
        mind_context = self._get_mind_context(company, product)
        mind_used = bool(mind_context)

        # Step 3 — optional analytics context
        analytics_context = None
        if include_analytics:
            analytics_context = self._get_analytics_context(company, product)

        # Step 4 — build citations from chunks
        citations = self._build_citations(chunks)

        # Step 5 — Claude synthesis
        client = self._get_client()
        if client is None:
            # Graceful degradation: return retrieval-only results
            logger.warning(
                "ClaudeQueryEngine: Anthropic client unavailable, "
                "returning retrieval-only results."
            )
            return {
                "answer": self._build_retrieval_only_answer(question, chunks),
                "citations": citations,
                "engine": "retrieval_only",
                "chunks_searched": len(raw_chunks),
                "mind_context_used": mind_used,
            }

        prompt = self._build_rag_prompt(
            question, chunks, mind_context, analytics_context
        )

        try:
            response = client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            answer = response.content[0].text
        except Exception as exc:
            logger.error("ClaudeQueryEngine: Claude API error: %s", exc)
            return {
                "answer": self._build_retrieval_only_answer(question, chunks),
                "citations": citations,
                "engine": "retrieval_only",
                "chunks_searched": len(raw_chunks),
                "mind_context_used": mind_used,
                "error": str(exc),
            }

        return {
            "answer": answer,
            "citations": citations,
            "engine": "claude",
            "chunks_searched": len(raw_chunks),
            "mind_context_used": mind_used,
        }

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_rag_prompt(
        self,
        question: str,
        chunks: list[dict],
        mind_context: str,
        analytics_context: Optional[str] = None,
    ) -> str:
        """Build the Claude prompt with retrieved context.

        The prompt structure:
            1. System instructions (role, citation rules)
            2. Mind context (institutional knowledge)
            3. Analytics context (latest metrics, if available)
            4. Retrieved document chunks (numbered for citation)
            5. The analyst's question
        """
        parts: list[str] = []

        # Instructions
        parts.append(textwrap.dedent("""\
            You are a senior credit analyst for a private credit fund called ACP.
            You are answering a research question using internal data room documents
            and platform analytics.

            CITATION RULES:
            - Reference sources by their [Source N] number when making factual claims.
            - If information comes from multiple sources, cite all relevant ones.
            - If no source supports a claim, say so explicitly.
            - Do not fabricate data or citations.
            - Be precise with numbers — quote them exactly as they appear in sources.
            - When sources conflict, note the discrepancy and state which source
              you consider more authoritative and why.

            FORMAT:
            - Write clear, professional prose suitable for an investment committee memo.
            - Use bullet points for lists of findings or metrics.
            - Keep the answer focused and concise (300-500 words typical).
        """))

        # Mind context (institutional knowledge)
        if mind_context:
            parts.append("=== INSTITUTIONAL KNOWLEDGE ===")
            parts.append(mind_context)
            parts.append("")

        # Analytics context
        if analytics_context:
            parts.append("=== LATEST PLATFORM ANALYTICS ===")
            parts.append(analytics_context)
            parts.append("")

        # Retrieved chunks
        if chunks:
            parts.append("=== RETRIEVED DOCUMENTS ===")
            for i, chunk in enumerate(chunks, 1):
                filename = chunk.get("filename", "unknown")
                doc_type = chunk.get("document_type", "unknown")
                heading = chunk.get("section_heading") or ""
                snippet = chunk.get("snippet", "")
                score = chunk.get("score", 0)

                header = f"[Source {i}] {filename} ({doc_type})"
                if heading:
                    header += f" — {heading}"
                header += f"  [relevance: {score}]"

                parts.append(header)
                parts.append(snippet)
                parts.append("")
        else:
            parts.append(
                "No relevant documents were found in the data room for this query."
            )

        # The question
        parts.append("=== QUESTION ===")
        parts.append(question)

        full_prompt = "\n".join(parts)

        # Truncate if excessively long
        if len(full_prompt) > self.MAX_CONTEXT_CHARS:
            logger.warning(
                "ClaudeQueryEngine: prompt truncated from %d to %d chars",
                len(full_prompt),
                self.MAX_CONTEXT_CHARS,
            )
            full_prompt = full_prompt[: self.MAX_CONTEXT_CHARS] + (
                "\n\n[Context truncated due to length. "
                "Answer based on what is available above.]\n\n"
                f"=== QUESTION ===\n{question}"
            )

        return full_prompt

    # ------------------------------------------------------------------
    # Context helpers
    # ------------------------------------------------------------------

    def _get_mind_context(self, company: str, product: str) -> str:
        """Pull the 4-layer living mind context for this company/product.

        Returns an empty string if the mind module is unavailable.
        """
        try:
            from core.mind import build_mind_context
            ctx = build_mind_context(
                company=company,
                product=product,
                task_type="research_report",
            )
            return ctx.formatted if not ctx.is_empty else ""
        except Exception as exc:
            logger.warning("ClaudeQueryEngine: mind context unavailable: %s", exc)
            return ""

    def _get_analytics_context(self, company: str, product: str) -> str:
        """Pull latest analytics snapshots for context enrichment.

        Returns a human-readable summary of the most recent tape and
        portfolio analytics, or an empty string if unavailable.
        """
        try:
            from core.dataroom.analytics_snapshot import AnalyticsSnapshotEngine
            engine = AnalyticsSnapshotEngine()
            timeline = engine.get_analytics_timeline(company, product)

            if not timeline:
                return ""

            lines: list[str] = []
            lines.append(
                f"Analytics timeline: {len(timeline)} snapshots available."
            )

            # Show latest few entries with key metrics
            for entry in timeline[-5:]:
                snap_date = entry.get("snapshot_date", "?")
                doc_type = entry.get("doc_type", "?")
                key_metrics = entry.get("key_metrics", {})

                if key_metrics:
                    metrics_str = ", ".join(
                        f"{k}: {v}" for k, v in list(key_metrics.items())[:6]
                    )
                    lines.append(f"  {snap_date} | {doc_type}: {metrics_str}")
                else:
                    lines.append(f"  {snap_date} | {doc_type}")

            return "\n".join(lines)
        except Exception as exc:
            logger.warning(
                "ClaudeQueryEngine: analytics context unavailable: %s", exc
            )
            return ""

    # ------------------------------------------------------------------
    # Citation helpers
    # ------------------------------------------------------------------

    def _build_citations(self, chunks: list[dict]) -> list[dict]:
        """Build structured citations from retrieval chunks.

        Each citation maps back to a source document with doc_id and snippet.
        """
        citations = []
        for i, chunk in enumerate(chunks, 1):
            citations.append({
                "index": i,
                "doc_id": chunk.get("doc_id", ""),
                "filename": chunk.get("filename", ""),
                "document_type": chunk.get("document_type", ""),
                "snippet": (chunk.get("snippet", ""))[:200],
                "score": chunk.get("score", 0),
                "section_heading": chunk.get("section_heading"),
            })
        return citations

    # ------------------------------------------------------------------
    # Fallback answer
    # ------------------------------------------------------------------

    def _build_retrieval_only_answer(
        self, question: str, chunks: list[dict]
    ) -> str:
        """Build a retrieval-only answer when Claude is unavailable.

        Returns the top chunks formatted as a simple list so the analyst
        still gets useful information even without AI synthesis.
        """
        if not chunks:
            return (
                "No relevant documents were found in the data room. "
                "Try uploading more source materials or rephrasing the question."
            )

        lines = [
            "AI synthesis is currently unavailable. "
            "Here are the most relevant document excerpts found:\n"
        ]
        for i, chunk in enumerate(chunks[:5], 1):
            filename = chunk.get("filename", "unknown")
            snippet = chunk.get("snippet", "")[:300]
            lines.append(f"[{i}] {filename}:")
            lines.append(f"   {snippet}\n")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Anthropic client
    # ------------------------------------------------------------------

    def _get_client(self):
        """Lazy-initialise the Anthropic client.

        Returns None if the API key is missing or the library is not installed.
        """
        if self._client_checked:
            return self._client

        self._client_checked = True

        try:
            from dotenv import load_dotenv
            load_dotenv(override=True)
        except ImportError:
            pass

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning(
                "ClaudeQueryEngine: ANTHROPIC_API_KEY not set — "
                "Claude synthesis disabled."
            )
            return None

        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)
            return self._client
        except ImportError:
            logger.warning(
                "ClaudeQueryEngine: anthropic package not installed — "
                "Claude synthesis disabled."
            )
            return None
        except Exception as exc:
            logger.error("ClaudeQueryEngine: failed to init client: %s", exc)
            return None
