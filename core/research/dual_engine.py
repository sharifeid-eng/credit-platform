"""
Dual-engine research orchestrator for the Laith credit platform.

Runs research queries through Claude RAG and optionally NotebookLM,
then synthesises a unified answer. When NotebookLM is unavailable,
falls back gracefully to Claude-only mode.

NotebookLM is a first-class research engine — not an afterthought. When
available, it provides independent document understanding that catches
things Claude's RAG might miss (different chunking, different attention).

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
                ``nlm_references``: NLM ChatReference dicts (or []).
                ``nlm_conversation_id``: For follow-up queries (or None).
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

        # Step 2: NotebookLM (optional but encouraged)
        nlm_result = None
        nlm_available = False
        nlm_warning = None

        if use_notebooklm:
            self._try_init_nlm()
            nlm_available = self.nlm_engine is not None and self.nlm_engine.available

            if not nlm_available:
                nlm_warning = (
                    self.nlm_engine.get_warning()
                    if self.nlm_engine is not None
                    else {
                        "code": "nlm_not_installed",
                        "message": "NotebookLM library is not installed. Research will use Claude RAG only.",
                        "fix": "Install with 'pip install notebooklm-py' then run 'notebooklm login'.",
                        "severity": "warning",
                    }
                )

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
            # Convert NLM references to synthesizer-compatible format
            nlm_for_synth = {
                "answer": nlm_result["answer"],
                "sources": nlm_result.get("references", []),
                "engine": "notebooklm",
            }

            merged = self.synthesizer.synthesize(
                claude_result=claude_result,
                nlm_result=nlm_for_synth,
                question=question,
            )
            return {
                **merged,
                "chunks_searched": claude_result.get("chunks_searched", 0),
                "mind_context_used": claude_result.get("mind_context_used", False),
                "nlm_available": nlm_available,
                "nlm_warning": None,
                "nlm_references": nlm_result.get("references", []),
                "nlm_conversation_id": nlm_result.get("conversation_id"),
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
            "nlm_warning": nlm_warning,
            "nlm_references": [],
            "nlm_conversation_id": None,
        }

    def deep_research(
        self,
        company: str,
        product: str,
        topic: str,
    ) -> dict:
        """Extended research using NotebookLM's web research + Claude RAG.

        Starts a NotebookLM web research session, then queries both engines
        for a comprehensive answer. Falls back to standard query if NLM
        deep research is unavailable.

        Args:
            company: Company slug.
            product: Product slug.
            topic: Research topic (broader than a single question).

        Returns:
            Dict with the same schema as ``query()`` plus ``deep_research``.
        """
        self._try_init_nlm()

        if self.nlm_engine and self.nlm_engine.available:
            try:
                notebook_id = self.nlm_engine.ensure_notebook(company, product)
                if notebook_id:
                    # Start web research
                    research_info = self.nlm_engine.start_research(
                        notebook_id, topic, source="web", mode="deep",
                    )
                    if research_info:
                        logger.info(
                            "DualResearchEngine: deep research started for %s/%s: %s",
                            company, product, topic[:60],
                        )

                    # Now query both engines (NLM will have fresh web context)
                    result = self.query(
                        company=company,
                        product=product,
                        question=f"Research topic: {topic}",
                        use_notebooklm=True,
                        include_analytics=True,
                    )
                    result["deep_research"] = True
                    return result

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
    # NLM status
    # ------------------------------------------------------------------

    def get_nlm_status(self) -> dict:
        """Return NotebookLM engine status for operator dashboards."""
        self._try_init_nlm()
        if self.nlm_engine:
            return self.nlm_engine.get_status()
        return {
            "library_installed": False,
            "integration_method": None,
            "authenticated": False,
            "available": False,
            "notebooks_cached": 0,
        }

    # ------------------------------------------------------------------
    # NLM lazy init
    # ------------------------------------------------------------------

    def _try_init_nlm(self):
        """Lazy-initialise the NotebookLM engine. Called once."""
        if self._nlm_checked:
            return

        self._nlm_checked = True

        try:
            engine = NotebookLMEngine()
            if engine.available:
                self.nlm_engine = engine
                logger.info("DualResearchEngine: NotebookLM available")
            else:
                # Keep the engine reference even if not authenticated —
                # status endpoint can report why it's unavailable
                self.nlm_engine = engine
                logger.info(
                    "DualResearchEngine: NotebookLM not available — %s",
                    "not authenticated" if (engine._use_python or engine._use_cli)
                    else "library not installed",
                )
        except Exception as exc:
            logger.warning(
                "DualResearchEngine: failed to init NLM engine: %s", exc
            )
            self.nlm_engine = None

    # ------------------------------------------------------------------
    # Source sync
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
                "skipped": 0,
                "errors": ["NotebookLM is not available"],
                "notebook_id": None,
            }

        if documents is None:
            # Load from data room catalog
            try:
                catalog = self.claude_engine._dr.catalog(company, product)
                documents = [
                    {
                        "doc_id": doc.get("doc_id", doc.get("filename", "")),
                        "filepath": doc.get("filepath", ""),
                        "title": doc.get("filename", ""),
                    }
                    for doc in catalog
                    if doc.get("filepath")
                ]
            except Exception as exc:
                return {
                    "uploaded": 0,
                    "skipped": 0,
                    "errors": [f"Failed to load catalog: {exc}"],
                    "notebook_id": None,
                }

        return self.nlm_engine.sync_sources(company, product, documents)

    def configure_notebook(self, company: str, product: str) -> bool:
        """Configure the NLM notebook chat persona for credit analysis.

        Should be called after creating/restoring a notebook to set the
        appropriate analytical tone.
        """
        self._try_init_nlm()
        if not self.nlm_engine or not self.nlm_engine.available:
            return False

        notebook_id = self.nlm_engine.ensure_notebook(company, product)
        if not notebook_id:
            return False

        return self.nlm_engine.configure_chat(notebook_id)
