"""
Research answer synthesizer — merges results from multiple engines.

When the DualResearchEngine obtains answers from both Claude RAG and
NotebookLM, this module merges them into a single, authoritative response.
Uses Claude to perform the merge so that contradictions are flagged and
the strongest points from each source are preserved.
"""

from __future__ import annotations

import logging
import os
import textwrap
from typing import Optional

logger = logging.getLogger(__name__)


class ResearchSynthesizer:
    """Merges Claude RAG and NotebookLM answers into a unified response.

    If the Anthropic API is unavailable, falls back to simple concatenation
    with section headers.
    """

    MODEL = "claude-opus-4-6"
    MAX_TOKENS = 1500

    def __init__(self):
        """Initialise the synthesizer."""
        self._client = None
        self._client_checked = False

    def synthesize(
        self,
        claude_result: dict,
        nlm_result: dict,
        question: str = "",
        mind_context: str = "",
    ) -> dict:
        """Merge two independent research answers into one.

        Takes the strongest points from each, flags contradictions, and
        notes which source was more authoritative for each claim.

        Args:
            claude_result: Result dict from ClaudeQueryEngine.query().
                Must have ``answer`` and ``citations`` keys.
            nlm_result: Result dict from NotebookLMEngine.query().
                Must have ``answer`` and ``sources`` keys.
            question: The original analyst question (for context).
            mind_context: Optional mind context for the merge prompt.

        Returns:
            Merged result dict with keys:
                ``answer``: Unified answer text.
                ``citations``: Combined citations from both engines.
                ``engine``: ``"merged"``.
                ``synthesis_notes``: What was different/complementary.
                ``claude_answer``: Original Claude answer.
                ``nlm_answer``: Original NLM answer.
        """
        claude_answer = claude_result.get("answer", "")
        claude_citations = claude_result.get("citations", [])

        nlm_answer = nlm_result.get("answer", "")
        nlm_sources = nlm_result.get("sources", [])

        # If one side is empty, return the other directly
        if not nlm_answer.strip():
            return {
                "answer": claude_answer,
                "citations": claude_citations,
                "engine": "claude",
                "synthesis_notes": "NotebookLM returned no answer; using Claude only.",
                "claude_answer": claude_answer,
                "nlm_answer": None,
            }

        if not claude_answer.strip():
            return {
                "answer": nlm_answer,
                "citations": self._convert_nlm_sources(nlm_sources),
                "engine": "notebooklm",
                "synthesis_notes": "Claude returned no answer; using NotebookLM only.",
                "claude_answer": None,
                "nlm_answer": nlm_answer,
            }

        # Both have answers — attempt AI-powered merge
        merged_answer, synthesis_notes = self._ai_merge(
            claude_answer, nlm_answer, question, mind_context
        )

        # Combine citations
        combined_citations = self._merge_citations(claude_citations, nlm_sources)

        return {
            "answer": merged_answer,
            "citations": combined_citations,
            "engine": "merged",
            "synthesis_notes": synthesis_notes,
            "claude_answer": claude_answer,
            "nlm_answer": nlm_answer,
        }

    # ------------------------------------------------------------------
    # AI merge
    # ------------------------------------------------------------------

    def _ai_merge(
        self,
        claude_answer: str,
        nlm_answer: str,
        question: str,
        mind_context: str,
    ) -> tuple[str, str]:
        """Use Claude to merge two independent analyses.

        Returns (merged_answer, synthesis_notes). Falls back to simple
        concatenation if the API is unavailable.
        """
        client = self._get_client()
        if client is None:
            return self._simple_merge(claude_answer, nlm_answer)

        prompt = self._build_merge_prompt(
            claude_answer, nlm_answer, question, mind_context
        )

        try:
            response = client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text

            # Parse the response — expect MERGED ANSWER and SYNTHESIS NOTES sections
            merged, notes = self._parse_merge_response(raw)
            return (merged, notes)

        except Exception as exc:
            logger.warning("ResearchSynthesizer: AI merge failed: %s", exc)
            return self._simple_merge(claude_answer, nlm_answer)

    def _build_merge_prompt(
        self,
        claude_answer: str,
        nlm_answer: str,
        question: str,
        mind_context: str,
    ) -> str:
        """Build the prompt for the merge Claude call."""
        parts: list[str] = []

        parts.append(textwrap.dedent("""\
            You are a senior credit analyst synthesising two independent research
            analyses into a single, authoritative answer.

            RULES:
            - Take the strongest, most specific points from each analysis.
            - If both sources agree, state the finding once with confidence.
            - If sources contradict, note the discrepancy and state which source
              you consider more authoritative and why.
            - If one source provides data the other lacks, include it.
            - Write in a professional, concise style suitable for an IC memo.
            - Preserve all specific numbers and metrics from both sources.

            OUTPUT FORMAT:
            First section: "MERGED ANSWER" — the unified analysis.
            Second section: "SYNTHESIS NOTES" — brief notes on what was
            different, complementary, or contradictory between the two sources.
        """))

        if mind_context:
            parts.append(f"INSTITUTIONAL CONTEXT:\n{mind_context}\n")

        if question:
            parts.append(f"QUESTION:\n{question}\n")

        parts.append(f"ANALYSIS A (Claude RAG — internal documents):\n{claude_answer}\n")
        parts.append(f"ANALYSIS B (NotebookLM — document understanding):\n{nlm_answer}\n")

        parts.append("Now produce the MERGED ANSWER and SYNTHESIS NOTES.")

        return "\n".join(parts)

    def _parse_merge_response(self, raw: str) -> tuple[str, str]:
        """Parse the merge response into (answer, notes) sections.

        Looks for ``MERGED ANSWER`` and ``SYNTHESIS NOTES`` headers.
        Falls back to treating the entire response as the answer.
        """
        merged = raw
        notes = ""

        # Try splitting on headers
        upper = raw.upper()
        ma_idx = upper.find("MERGED ANSWER")
        sn_idx = upper.find("SYNTHESIS NOTES")

        if ma_idx >= 0 and sn_idx >= 0 and sn_idx > ma_idx:
            # Extract content after "MERGED ANSWER" header
            after_ma = raw[ma_idx:]
            # Skip the header line
            lines = after_ma.split("\n", 1)
            ma_content = lines[1] if len(lines) > 1 else ""

            # Find where synthesis notes start within ma_content
            sn_offset = ma_content.upper().find("SYNTHESIS NOTES")
            if sn_offset >= 0:
                merged = ma_content[:sn_offset].strip()
                after_sn = ma_content[sn_offset:]
                sn_lines = after_sn.split("\n", 1)
                notes = sn_lines[1].strip() if len(sn_lines) > 1 else ""
            else:
                merged = ma_content.strip()
        elif ma_idx >= 0:
            after_ma = raw[ma_idx:]
            lines = after_ma.split("\n", 1)
            merged = lines[1].strip() if len(lines) > 1 else raw
        elif sn_idx >= 0:
            merged = raw[:sn_idx].strip()
            after_sn = raw[sn_idx:]
            sn_lines = after_sn.split("\n", 1)
            notes = sn_lines[1].strip() if len(sn_lines) > 1 else ""

        return (merged or raw, notes)

    # ------------------------------------------------------------------
    # Simple fallback merge
    # ------------------------------------------------------------------

    def _simple_merge(
        self, claude_answer: str, nlm_answer: str
    ) -> tuple[str, str]:
        """Simple concatenation merge when AI is unavailable.

        Returns (merged_text, notes).
        """
        merged = (
            "From internal document analysis (Claude RAG):\n"
            f"{claude_answer}\n\n"
            "From document understanding engine (NotebookLM):\n"
            f"{nlm_answer}"
        )
        notes = (
            "AI synthesis unavailable. Both analyses presented sequentially. "
            "Manual review recommended to identify contradictions."
        )
        return (merged, notes)

    # ------------------------------------------------------------------
    # Citation merging
    # ------------------------------------------------------------------

    def _merge_citations(
        self,
        claude_citations: list[dict],
        nlm_sources: list,
    ) -> list[dict]:
        """Combine citations from both engines into a unified list.

        Claude citations are preserved as-is with an ``origin: "claude"``
        tag. NLM sources are converted to the standard citation format
        with an ``origin: "notebooklm"`` tag.
        """
        combined: list[dict] = []

        for cit in claude_citations:
            combined.append({**cit, "origin": "claude"})

        for nlm_src in self._convert_nlm_sources(nlm_sources):
            combined.append({**nlm_src, "origin": "notebooklm"})

        # Re-number
        for i, cit in enumerate(combined, 1):
            cit["index"] = i

        return combined

    def _convert_nlm_sources(self, nlm_sources: list) -> list[dict]:
        """Convert NLM source references to the standard citation format.

        NLM sources may be strings, dicts, or objects. This normalises
        them into the standard ``{index, doc_id, filename, snippet, ...}``
        format.
        """
        converted: list[dict] = []

        for i, src in enumerate(nlm_sources, 1):
            if isinstance(src, str):
                converted.append({
                    "index": i,
                    "doc_id": "",
                    "filename": "",
                    "document_type": "",
                    "snippet": src[:200],
                    "score": 0,
                    "origin": "notebooklm",
                })
            elif isinstance(src, dict):
                converted.append({
                    "index": i,
                    "doc_id": src.get("doc_id", src.get("id", "")),
                    "filename": src.get("filename", src.get("name", "")),
                    "document_type": src.get("document_type", src.get("type", "")),
                    "snippet": (
                        src.get("snippet", src.get("text", src.get("excerpt", "")))
                    )[:200],
                    "score": src.get("score", src.get("relevance", 0)),
                    "origin": "notebooklm",
                })
            else:
                # Object with attributes
                converted.append({
                    "index": i,
                    "doc_id": getattr(src, "doc_id", getattr(src, "id", "")),
                    "filename": getattr(src, "filename", getattr(src, "name", "")),
                    "document_type": getattr(src, "document_type", ""),
                    "snippet": str(getattr(src, "snippet", getattr(src, "text", "")))[:200],
                    "score": getattr(src, "score", 0),
                    "origin": "notebooklm",
                })

        return converted

    # ------------------------------------------------------------------
    # Anthropic client
    # ------------------------------------------------------------------

    def _get_client(self):
        """Lazy-initialise the Anthropic client."""
        if self._client_checked:
            return self._client

        self._client_checked = True

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return None

        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)
            return self._client
        except ImportError:
            return None
        except Exception as exc:
            logger.error("ResearchSynthesizer: client init failed: %s", exc)
            return None
