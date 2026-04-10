"""
Dual-engine research orchestrator for the Laith credit platform.

Runs research queries through Claude RAG and optionally NotebookLM,
then synthesises a unified answer. When NotebookLM is unavailable,
falls back gracefully to Claude-only mode.

Usage::

    engine = DualResearchEngine()
    result = engine.query("klaim", "UAE_healthcare",
                          "What is the current PAR 30+ rate?")
    print(result["answer"])
    print(result["engine"])  # "claude" | "notebooklm" | "merged"
"""

from __future__ import annotations

import logging
from typing import Optional

from core.research.query_engine import ClaudeQueryEngine
from core.research.notebooklm_bridge import NotebookLMEngine
from core.research.synthesizer import ResearchSynthesizer

logger = logging.getLogger(__name__)


class DualResearchEngine:
    """Orchestrates Claude RAG and NotebookLM for research queries.

    The engine runs queries through Claude RAG (always available given an
    API key and data room) and optionally through NotebookLM for a
    second-opinion analysis. When both produce answers, they are merged
    by the ResearchSynthesizer.

    NotebookLM availability is checked lazily on first use and cached.
    """

    def __init__(
        self,
        dataroom_engine=None,
    ):
        """Initialise the dual engine.

        Args:
            dataroom_engine: Optional DataRoomEngine instance to share with
                the Claude query engine. If None, a default is created.
        """
        self.claude_engine = ClaudeQueryEngine(dataroom_engine=dataroom_engine)
        self.nlm_engine: Optional[NotebookLMEngine] = None
        self.synthesizer = ResearchSynthesizer()
        self._nlm_checked = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def query(
        self,
        company: str,
        product: str,
        question: str,
        use_notebooklm: bool = True,
        include_analytics: bool = True,
        doc_types: Optional[list[str]] = None,
        top_k: int = 10,
    ) -> dict:
        """Execute a research query through one or both engines.

        Pipeline:
            1. Always run Claude RAG query (uses internal document chunks).
            2. If ``use_notebooklm`` and NLM is available, run NLM query.
            3. If both return answers, synthesise (merge best from each).
            4. Return unified answer with dual citations.

        Args:
            company: Company slug.
            product: Product slug.
            question: Natural-language research question.
            use_notebooklm: Whether to attempt NLM query (default True).
            include_analytics: Include analytics snapshots in context.
            doc_types: Optional filter for document types.
            top_k: Number of retrieval chunks for Claude RAG.

        Returns:
            Dict with keys:
                ``answer``: Final answer text.
                ``citations``: Source citations (combined if merged).
                ``engine``: ``"claude"`` | ``"notebooklm"`` | ``"merged"``
                    | ``"retrieval_only"``.
                ``claude_answer``: Claude's answer (or None).
                ``nlm_answer``: NLM's answer (or None).
                ``synthesis_notes``: Merge notes (or None).
                ``chunks_searched``: Number of chunks searched.
                ``mind_context_used``: Whether mind context was injected.
                ``nlm_available``: Whether NLM engine was available.
        """
        # Step 1: Claude RAG (always)
        claude_result = self.claude_engine.query(
            company=company,
            product=product,
            question=question,
            doc_types=doc_types,
            include_analytics=include_analytics,
            top_k=top_k,
        )

        # Step 2: NotebookLM (optional)
        nlm_result = None
        nlm_available = False

        if use_notebooklm:
            self._try_init_nlm()
            nlm_available = self.nlm_engine is not None and self.nlm_engine.available

            if nlm_available:
                try:
                    notebook_id = self.nlm_engine.ensure_notebook(company, product)
                    if notebook_id:
                        nlm_result = self.nlm_engine.query(notebook_id, question)
                        # Check if NLM actually returned something useful
                        if not nlm_result or not nlm_result.get("answer", "").strip():
                            nlm_result = None
                except Exception as exc:
                    logger.warning(
                        "DualResearchEngine: NLM query failed: %s", exc
                    )
                    nlm_result = None

        # Step 3: Synthesise or return Claude-only
        if nlm_result and nlm_result.get("answer", "").strip():
            merged = self.synthesizer.synthesize(
                claude_result=claude_result,
                nlm_result=nlm_result,
                question=question,
            )
            return {
                **merged,
                "chunks_searched": claude_result.get("chunks_searched", 0),
                "mind_context_used": claude_result.get("mind_context_used", False),
                "nlm_available": nlm_available,
            }

        # Claude-only result
        return {
            "answer": claude_result.get("answer", ""),
            "citations": claude_result.get("citations", []),
            "engine": claude_result.get("engine", "claude"),
            "claude_answer": claude_result.get("answer"),
            "nlm_answer": None,
            "synthesis_notes": None,
            "chunks_searched": claude_result.get("chunks_searched", 0),
            "mind_context_used": claude_result.get("mind_context_used", False),
            "nlm_available": nlm_available,
        }

    def deep_research(
        self,
        company: str,
        product: str,
        topic: str,
    ) -> dict:
        """Extended research using NotebookLM Deep Research for web crawling.

        This is a premium feature that uses NLM's deep research mode to
        crawl the web for additional context on a topic, then merges with
        internal data room knowledge.

        Falls back to a standard query if NLM deep research is unavailable.

        Args:
            company: Company slug.
            product: Product slug.
            topic: Research topic (broader than a single question).

        Returns:
            Dict with the same schema as ``query()`` plus an additional
            ``deep_research`` boolean flag.
        """
        self._try_init_nlm()

        # Check if NLM supports deep research
        nlm_deep_available = (
            self.nlm_engine is not None
            and self.nlm_engine.available
            and hasattr(self.nlm_engine, "_run_python")
        )

        if nlm_deep_available:
            try:
                notebook_id = self.nlm_engine.ensure_notebook(company, product)
                if notebook_id:
                    # Attempt deep research via NLM
                    if self.nlm_engine._use_python:
                        raw = self.nlm_engine._run_python(
                            "deep_research", notebook_id, topic
                        )
                        nlm_answer, nlm_sources = self.nlm_engine._parse_nlm_response(raw)
                    else:
                        raw = self.nlm_engine._run_cli(
                            "deep-research",
                            "--notebook", notebook_id,
                            "--topic", topic,
                        )
                        nlm_answer, nlm_sources = self.nlm_engine._parse_nlm_response(raw)

                    if nlm_answer:
                        # Run Claude RAG too for internal docs
                        claude_result = self.claude_engine.query(
                            company=company,
                            product=product,
                            question=f"Research topic: {topic}",
                            include_analytics=True,
                        )

                        merged = self.synthesizer.synthesize(
                            claude_result=claude_result,
                            nlm_result={
                                "answer": nlm_answer,
                                "sources": nlm_sources,
                                "engine": "notebooklm_deep",
                            },
                            question=topic,
                        )

                        return {
                            **merged,
                            "deep_research": True,
                            "chunks_searched": claude_result.get("chunks_searched", 0),
                            "mind_context_used": claude_result.get("mind_context_used", False),
                            "nlm_available": True,
                        }

            except Exception as exc:
                logger.warning(
                    "DualResearchEngine: deep research failed, "
                    "falling back to standard query: %s",
                    exc,
                )

        # Fallback to standard query
        result = self.query(
            company=company,
            product=product,
            question=f"Research topic: {topic}",
            use_notebooklm=True,
            include_analytics=True,
        )
        result["deep_research"] = False
        return result

    # ------------------------------------------------------------------
    # NLM lazy init
    # ------------------------------------------------------------------

    def _try_init_nlm(self):
        """Lazy-initialise the NotebookLM engine. Called once.

        After the first call, ``self.nlm_engine`` is either a working
        ``NotebookLMEngine`` instance or ``None`` (permanently).
        """
        if self._nlm_checked:
            return

        self._nlm_checked = True

        try:
            engine = NotebookLMEngine()
            if engine.available:
                self.nlm_engine = engine
                logger.info("DualResearchEngine: NotebookLM available")
            else:
                logger.info("DualResearchEngine: NotebookLM not available")
        except Exception as exc:
            logger.warning(
                "DualResearchEngine: failed to init NLM engine: %s", exc
            )
            self.nlm_engine = None

    # ------------------------------------------------------------------
    # Utility: sync documents to NLM
    # ------------------------------------------------------------------

    def sync_to_notebooklm(
        self,
        company: str,
        product: str,
        documents: Optional[list[dict]] = None,
    ) -> dict:
        """Sync data room documents to the NLM notebook.

        If ``documents`` is not provided, loads the document catalog from
        the DataRoomEngine and syncs all documents.

        Args:
            company: Company slug.
            product: Product slug.
            documents: Optional list of document dicts to upload.

        Returns:
            Sync result dict from ``NotebookLMEngine.sync_sources()``.
        """
        self._try_init_nlm()

        if self.nlm_engine is None or not self.nlm_engine.available:
            return {
                "uploaded": 0,
                "errors": ["NotebookLM is not available"],
                "notebook_id": None,
            }

        if documents is None:
            # Load from data room catalog
            try:
                catalog = self.claude_engine._dr.catalog(company, product)
                documents = [
                    {
                        "filepath": doc.get("filepath", ""),
                        "filename": doc.get("filename", ""),
                    }
                    for doc in catalog
                    if doc.get("filepath")
                ]
            except Exception as exc:
                return {
                    "uploaded": 0,
                    "errors": [f"Failed to load catalog: {exc}"],
                    "notebook_id": None,
                }

        return self.nlm_engine.sync_sources(company, product, documents)
