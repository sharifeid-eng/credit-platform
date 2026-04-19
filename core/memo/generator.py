"""
AI-powered IC Memo Generator — Hybrid 6-Stage Pipeline.

Stages:
  1. Context Assembly   — load analytics + research + mind context (no API calls)
  2. Parallel Structured — fan out structured sections via ThreadPoolExecutor (Sonnet)
  3. Auto Sections      — cheap templated content (Haiku) — parallel with stage 2
  4. Research Packs     — short-burst agent runs per judgment section (Sonnet, 5-turn cap)
  5. Judgment Synthesis — one Opus call per judgment section, sequential (for coherence)
  6. Polish Pass        — single Opus call rewriting the whole memo for coherence

Model routing (all via core.ai_client):
  auto       → Haiku 4    (appendix)
  structured → Sonnet 4.6 (analytics / dataroom / mixed sections, ai_guided=False)
  research   → Sonnet 4.6 (agent research packs)
  judgment   → Opus 4.7   (ai_guided=True: exec_summary, investment_thesis, recommendation)
  polish     → Opus 4.7   (final whole-memo pass)

Rate-limit engineering: retries handled by core.ai_client.get_client() with max_retries=3.
A `LAITH_PARALLEL_SECTIONS` env var (default 3) caps concurrent stage-2 calls to
avoid bursting past org ITPM limits.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .templates import get_template, MEMO_TEMPLATES
from .analytics_bridge import AnalyticsBridge

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

# Output token budgets per tier/section type
_MAX_TOKENS_STRUCTURED     = 2000
_MAX_TOKENS_AUTO           = 800
_MAX_TOKENS_JUDGMENT       = 3500
# Polish is now per-section (see _polish_memo). One section rarely exceeds
# 3-5K chars of content, so 4000 output tokens is ample. The old one-shot
# all-sections polish used 16000 and still hit max_tokens truncation on
# memos ~40K+ chars combined.
_MAX_TOKENS_POLISH_SECTION = 4000
# Per-section citation audit issues list is small — 1500 is plenty.
_MAX_TOKENS_CITATION_AUDIT = 1500

# Maximum concurrent section calls during stage 2 (Sonnet parallel fan-out).
# Low default keeps peak input-tokens-per-minute under common org caps.
_PARALLEL_CAP = int(os.getenv("LAITH_PARALLEL_SECTIONS", "3"))

# Section source types (from templates.SourceLayer enum, used as strings here)
_SOURCE_ANALYTICS = "analytics"
_SOURCE_DATAROOM  = "dataroom"
_SOURCE_MIXED     = "mixed"
_SOURCE_AUTO      = "auto"
_SOURCE_NARRATIVE = "ai_narrative"


# ── Tier classification ──────────────────────────────────────────────────────

def classify_section(section_def: Dict[str, Any]) -> str:
    """Return tier name for a section based on template metadata.

    Uses existing `ai_guided` and `source` fields — no new schema required.

    - source=auto               → "auto" (Haiku)
    - ai_guided=True            → "judgment" (Opus)
    - anything else             → "structured" (Sonnet)
    """
    source = section_def.get("source", "")
    if source == _SOURCE_AUTO:
        return "auto"
    if section_def.get("ai_guided"):
        return "judgment"
    return "structured"


# ── Prompt builders ──────────────────────────────────────────────────────────

def _build_section_system_prompt(company: str, product: str,
                                 template_name: str,
                                 mind_context: str) -> str:
    """Build the system prompt for section generation."""
    return (
        f"You are a senior credit analyst at Amwal Capital Partners (ACP), "
        f"a private credit fund. You are writing an IC memo section for "
        f"{company} / {product}.\n\n"
        f"Memo type: {template_name}\n\n"
        f"Writing style:\n"
        f"- Institutional tone: precise, data-driven, no fluff\n"
        f"- Reference specific numbers from the analytics and research context\n"
        f"- Use metric callouts like [Collection Rate: 87.3%] inline\n"
        f"- Flag risks clearly with severity (critical/warning/monitor)\n"
        f"- Keep paragraphs concise (3-5 sentences)\n"
        f"- Use sub-headings within sections when content is dense\n"
        f"- End each section with a clear conclusion or takeaway\n\n"
        f"IMPORTANT: Base your analysis ONLY on the data provided in the context. "
        f"Do not invent or hallucinate metrics. If data is insufficient, "
        f"explicitly state what is missing.\n\n"
        f"{mind_context}"
    )


def _build_section_user_prompt(section: Dict[str, Any],
                               analytics_text: str,
                               research_text: str,
                               prior_text: str,
                               research_pack_text: str = "") -> str:
    """Build the user prompt for a section."""
    parts = [
        f"## Section: {section['title']}\n",
        f"**Guidance:** {section['guidance']}\n",
    ]
    if analytics_text:
        parts.append(f"\n### Analytics Context\n{analytics_text}\n")
    if research_text:
        parts.append(f"\n### Data Room Research\n{research_text}\n")
    if research_pack_text:
        parts.append(f"\n{research_pack_text}\n")
    if prior_text:
        parts.append(f"\n### Prior Sections (for coherence)\n{prior_text}\n")
    parts.append(
        "\nWrite this section now. Return JSON with this structure:\n"
        '{\n'
        '  "content": "Multi-paragraph section text...",\n'
        '  "metrics": [{"label": "...", "value": "...", '
        '"assessment": "healthy|warning|critical|neutral"}],\n'
        '  "citations": [{"index": 1, "source": "...", "snippet": "..."}]\n'
        '}\n\n'
        "The content field should be the full section text. "
        "Metrics should highlight 3-6 key numbers mentioned in the content. "
        "Citations should reference specific data room documents or analytics "
        "sources used. Return ONLY valid JSON, no markdown fences."
    )
    return "\n".join(parts)


def _parse_ai_response(text: str) -> Dict[str, Any]:
    """Parse AI response, handling JSON with or without fences, plus plain-text fallback."""
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)
        return {
            "content": parsed.get("content", ""),
            "metrics": parsed.get("metrics", []),
            "citations": parsed.get("citations", []),
        }
    except (json.JSONDecodeError, TypeError):
        logger.warning("AI response was not valid JSON; using as plain text")
        return {"content": text.strip(), "metrics": [], "citations": []}


# ── Prior-sections summary (now much richer — full analytical content visible) ──

def _build_prior_text(prior_sections: List[Dict[str, Any]], char_cap_per_section: int = 1200) -> str:
    """Render prior sections for coherence. Richer than the old 200-char × 3 approach:
    all structured sections are included, each capped at char_cap_per_section chars."""
    if not prior_sections:
        return ""
    parts = []
    for ps in prior_sections:
        title = ps.get("title", "")
        content = ps.get("content", "") or ""
        if len(content) > char_cap_per_section:
            content = content[:char_cap_per_section] + "…"
        parts.append(f"**{title}:**\n{content}")
    return "\n\n".join(parts)


# ── MemoGenerator ────────────────────────────────────────────────────────────

class MemoGenerator:
    """Hybrid memo generator — tier-routed, parallel where safe, polished at the end."""

    def __init__(self):
        self.bridge = AnalyticsBridge()
        self._dataroom = None
        self._mind_available = False

        try:
            from core.dataroom import DataRoomEngine
            self._dataroom = DataRoomEngine()
        except Exception as e:
            logger.warning("DataRoomEngine not available: %s", e)

        try:
            from core.mind import build_mind_context  # noqa: F401
            self._mind_available = True
        except Exception as e:
            logger.warning("Mind module not available: %s", e)

    # ── Research chunks ─────────────────────────────────────────────────────

    def _get_research_chunks(self, company: str, product: str,
                             section: Dict[str, Any],
                             top_k: int = 5) -> str:
        if self._dataroom is None:
            return ""
        query = f"{section.get('title', '')} {section.get('guidance', '')}"
        try:
            results = self._dataroom.search(company, product, query, top_k=top_k)
        except Exception as e:
            logger.warning("Data room search failed for '%s': %s", section.get("key"), e)
            return ""
        if not results:
            return ""
        parts = []
        for i, hit in enumerate(results, 1):
            source = hit.get("source_file", hit.get("doc_id", "unknown"))
            text = hit.get("text", hit.get("content", ""))
            score = hit.get("score", 0)
            if len(text) > 600:
                text = text[:600] + "..."
            parts.append(f"[{i}] Source: {source} (relevance: {score:.2f})\n{text}")
        return "\n\n".join(parts)

    # ── Mind context ────────────────────────────────────────────────────────

    def _get_mind_context(self, company: str, product: str,
                          section_key: Optional[str],
                          query_text: str = "") -> str:
        if not self._mind_available:
            return ""
        try:
            from core.mind import build_mind_context
            ctx = build_mind_context(
                company=company, product=product,
                task_type="memo",
                section_key=section_key,
                query_text=query_text,
            )
            if ctx.is_empty:
                return ""
            return f"### Institutional Knowledge\n{ctx.formatted}\n"
        except Exception as e:
            logger.warning("Mind context failed: %s", e)
            return ""

    # ── Analytics formatting ────────────────────────────────────────────────

    def _format_analytics(self, analytics_context: Optional[Dict[str, Any]]) -> str:
        if not analytics_context or not analytics_context.get("available"):
            return ""
        text = analytics_context.get("text", "") or ""
        metrics = analytics_context.get("metrics", [])
        if metrics:
            bullets = [f"- {m.get('label')}: {m.get('value')} ({m.get('assessment', 'neutral')})"
                       for m in metrics]
            text += "\n\nMetrics:\n" + "\n".join(bullets)
        return text

    # ── Single-section generation (tier-aware) ──────────────────────────────

    def generate_section(self, company: str, product: str,
                         template_key: str, section_key: str,
                         tier: Optional[str] = None,
                         analytics_context: Optional[Dict[str, Any]] = None,
                         research_chunks: Optional[str] = None,
                         prior_sections: Optional[List[Dict[str, Any]]] = None,
                         research_pack: Optional[Dict[str, Any]] = None,
                         snapshot: Optional[str] = None,
                         currency: Optional[str] = None) -> Dict[str, Any]:
        """Generate one memo section.

        If `tier` is None, classify from template metadata.
        If `research_pack` is provided, its formatted summary is injected into the user prompt.
        """
        template = get_template(template_key)
        if not template:
            raise ValueError(f"Unknown template: {template_key}")

        # Find the section definition
        section_def = next((s for s in template["sections"] if s["key"] == section_key), None)
        if not section_def:
            raise ValueError(f"Unknown section '{section_key}' in template '{template_key}'")

        # Tier resolution
        if tier is None:
            tier = classify_section(section_def)

        # Auto sections have their own builder
        if tier == "auto" or section_def.get("source") == _SOURCE_AUTO:
            return self._generate_auto_section(company, product, section_def)

        # Gather context if not pre-computed
        source = section_def.get("source", "")
        if analytics_context is None and source in (_SOURCE_ANALYTICS, _SOURCE_MIXED):
            try:
                analytics_context = self.bridge.get_section_context(
                    company, product, section_key,
                    snapshot=snapshot, currency=currency,
                )
            except Exception as e:
                logger.warning("Analytics bridge error for section '%s': %s", section_key, e)
                analytics_context = None

        if research_chunks is None and source in (_SOURCE_DATAROOM, _SOURCE_MIXED):
            research_chunks = self._get_research_chunks(company, product, section_def)

        analytics_text = self._format_analytics(analytics_context)
        prior_text = _build_prior_text(prior_sections or [])

        # Research pack (judgment sections)
        research_pack_text = ""
        if research_pack:
            from core.memo.agent_research import format_pack_for_prompt
            research_pack_text = format_pack_for_prompt(research_pack)

        # Mind context — use section guidance as query_text for graph-aware scoring
        mind_ctx = self._get_mind_context(
            company, product, section_key,
            query_text=f"{section_def.get('title', '')} {section_def.get('guidance', '')}",
        )

        system_prompt = _build_section_system_prompt(
            company, product, template["name"], mind_ctx,
        )
        user_prompt = _build_section_user_prompt(
            section_def, analytics_text, research_chunks or "",
            prior_text, research_pack_text,
        )

        # Token budget by tier
        if tier == "judgment":
            max_tokens = _MAX_TOKENS_JUDGMENT
        elif tier == "auto":
            max_tokens = _MAX_TOKENS_AUTO
        else:
            max_tokens = _MAX_TOKENS_STRUCTURED

        # Call via central client with retry + caching
        from core.ai_client import complete
        start = time.time()
        try:
            resp = complete(
                tier=tier,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=max_tokens,
                log_prefix=f"memo.{section_key}",
            )
        except Exception as e:
            logger.error("AI call failed for section '%s' (tier=%s): %s", section_key, tier, e)
            return self._placeholder(section_def, analytics_context, research_chunks)

        elapsed = time.time() - start
        ai_text = resp.content[0].text if resp.content else ""
        parsed = _parse_ai_response(ai_text)

        # Extract metadata attached by core.ai_client.complete
        meta = getattr(resp, "_laith_metadata", {}) or {}
        gen_meta = {
            "model_used": meta.get("model"),
            "tier": tier,
            "tokens_in": resp.usage.input_tokens,
            "tokens_out": resp.usage.output_tokens,
            "cache_read_tokens": meta.get("cache_read_tokens", 0),
            "elapsed_s": round(elapsed, 2),
        }

        return {
            "key": section_def["key"],
            "title": section_def["title"],
            "content": parsed["content"],
            "metrics": parsed["metrics"],
            "citations": parsed["citations"],
            "generated_by": "ai",
            "source": section_def.get("source"),
            "generated_at": datetime.utcnow().isoformat(),
            "generation_meta": gen_meta,
        }

    # ── Placeholder / auto builders ─────────────────────────────────────────

    def _placeholder(self, section_def: Dict[str, Any],
                     analytics_context: Optional[Dict[str, Any]],
                     research_chunks: Optional[str]) -> Dict[str, Any]:
        """Structured placeholder when AI call fails entirely."""
        content_parts = []
        if analytics_context and analytics_context.get("available"):
            content_parts.append(analytics_context.get("text", "") or "")
            for m in analytics_context.get("metrics", []):
                content_parts.append(f"- {m.get('label')}: {m.get('value')}")
        if research_chunks:
            content_parts.append("\nData Room Sources:\n" + research_chunks[:500])
        if not content_parts:
            content_parts.append(
                f"[Placeholder: {section_def['title']}]\n{section_def.get('guidance', '')}\n\n"
                "AI generation failed. Fill in manually or regenerate."
            )
        return {
            "key": section_def["key"],
            "title": section_def["title"],
            "content": "\n".join(content_parts),
            "metrics": (analytics_context or {}).get("metrics", []),
            "citations": [],
            "generated_by": "placeholder",
            "source": section_def.get("source"),
            "generated_at": datetime.utcnow().isoformat(),
        }

    def _generate_auto_section(self, company: str, product: str,
                               section_def: Dict[str, Any]) -> Dict[str, Any]:
        """Template-fill the appendix/data-sources section. No AI call needed."""
        content_parts = [
            "## Data Sources Used in This Memo\n",
            f"**Company:** {company}",
            f"**Product:** {product}",
            f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n",
        ]
        try:
            from core.loader import get_snapshots
            snapshots = get_snapshots(company, product)
            if snapshots:
                content_parts.append("### Tape Snapshots")
                for snap in snapshots:
                    content_parts.append(f"  - {snap['filename']} ({snap.get('date', 'no date')})")
        except Exception:
            pass
        if self._dataroom is not None:
            try:
                catalog = self._dataroom.catalog(company, product)
                if catalog:
                    content_parts.append("\n### Data Room Documents")
                    docs = catalog if isinstance(catalog, list) else catalog.get("documents", [])
                    for doc in docs:
                        name = doc.get("filename", doc.get("name", "unknown"))
                        doc_type = doc.get("type", doc.get("document_type", ""))
                        content_parts.append(f"  - {name} ({doc_type})")
            except Exception:
                pass
        return {
            "key": section_def["key"],
            "title": section_def["title"],
            "content": "\n".join(content_parts),
            "metrics": [],
            "citations": [],
            "generated_by": "auto",
            "source": "auto",
            "generated_at": datetime.utcnow().isoformat(),
        }

    # ── Stage 2+3: parallel structured + auto ───────────────────────────────

    def _generate_parallel(self, company: str, product: str, template_key: str,
                           sections: List[Dict[str, Any]],
                           snapshot: Optional[str], currency: Optional[str],
                           progress_cb: Optional[callable] = None
                           ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Fan out structured + auto sections across a thread pool.

        Returns `(sections, errors)` where `sections` is always len(input)
        (error placeholders fill any slot whose future failed or never
        returned), and `errors` is a list of per-section failure records.

        Defensive against the Stage 2 truncation bug observed 2026-04-18:
        - catches BaseException (SystemExit/GeneratorExit) from any future
          so one bad task can't tear down the as_completed loop
        - backfills None slots with explicit error objects so downstream
          stages always see a full section list in template order
        """
        if not sections:
            return [], []

        max_workers = min(_PARALLEL_CAP, len(sections))
        results: List[Optional[Dict[str, Any]]] = [None] * len(sections)
        parallel_errors: List[Dict[str, Any]] = []

        def _emit_section_error(key: str, err: str, stage: str) -> None:
            """Emit section_error SSE event so UI can render failures."""
            if progress_cb:
                try:
                    progress_cb("section_error",
                                {"key": key, "error": err, "stage": stage})
                except Exception:
                    pass

        def _worker(idx: int, sect: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
            tier = classify_section(sect)
            if progress_cb:
                try:
                    progress_cb("section_start", {"key": sect["key"], "tier": tier})
                except Exception:
                    pass
            try:
                out = self.generate_section(
                    company=company, product=product,
                    template_key=template_key, section_key=sect["key"],
                    tier=tier,
                    prior_sections=[],  # parallel sections don't see each other
                    snapshot=snapshot, currency=currency,
                )
            except Exception as e:
                logger.error("Parallel section '%s' failed: %s", sect["key"], e)
                out = {
                    "key": sect["key"], "title": sect["title"],
                    "content": f"[Section generation failed: {e}]",
                    "metrics": [], "citations": [],
                    "generated_by": "error", "source": sect.get("source"),
                    "error_detail": str(e), "error_stage": "parallel_worker",
                }
                _emit_section_error(sect["key"], str(e), "parallel_worker")
            if progress_cb:
                try:
                    progress_cb("section_done", {"key": sect["key"], "tier": tier})
                except Exception:
                    pass
            return idx, out

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(_worker, i, s) for i, s in enumerate(sections)]
            for fut in concurrent.futures.as_completed(futures):
                try:
                    idx, section = fut.result()
                    results[idx] = section
                except BaseException as e:
                    # Includes SystemExit / GeneratorExit which can leak from
                    # progress_cb when an SSE client disconnects mid-flight.
                    # Log with full traceback; loop continues so remaining
                    # futures still get drained.
                    logger.error(
                        "Future propagated %s in parallel dispatch: %s",
                        type(e).__name__, e, exc_info=True,
                    )
                    parallel_errors.append({
                        "error": str(e),
                        "type": type(e).__name__,
                        "stage": "parallel_future",
                    })

        # Backfill any slots that never got a result (future crashed before
        # returning). Each becomes an explicit error-object section so the
        # memo has a full 12-entry section list and downstream stages can
        # still run citation audit + polish on the sections that succeeded.
        for idx, slot in enumerate(results):
            if slot is None:
                sect = sections[idx]
                results[idx] = {
                    "key": sect["key"], "title": sect["title"],
                    "content": "[Section failed in parallel dispatch — see memo errors]",
                    "metrics": [], "citations": [],
                    "generated_by": "error", "source": sect.get("source"),
                    "error_detail": "no_result_from_pool",
                    "error_stage": "parallel_backfill",
                }
                parallel_errors.append({
                    "section": sect["key"],
                    "error": "no_result_from_pool",
                    "stage": "parallel_backfill",
                })
                _emit_section_error(sect["key"], "no_result_from_pool",
                                    "parallel_backfill")

        return results, parallel_errors

    # ── Stage 4+5: judgment sections with research packs ────────────────────

    def _generate_judgment_sections(self, company: str, product: str, template_key: str,
                                    judgment_sections: List[Dict[str, Any]],
                                    body_sections: List[Dict[str, Any]],
                                    snapshot: Optional[str], currency: Optional[str],
                                    progress_cb: Optional[callable] = None
                                    ) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
        """Sequential generation of ai_guided sections with preceding body context.

        Each judgment section gets a research pack first, then an Opus synthesis call.
        Sequential order preserves coherence — each sees prior judgment sections too.

        Returns:
            (sections_list, packs_by_key, errors) — the synthesized sections,
            the raw research packs keyed by section_key, and a list of
            per-section failure records. One section failing must not block
            subsequent judgment sections.
        """
        from core.memo.agent_research import generate_research_pack

        out: List[Dict[str, Any]] = []
        packs_by_key: Dict[str, Dict[str, Any]] = {}
        errors: List[Dict[str, Any]] = []

        def _emit_section_error(key: str, err: str, stage: str) -> None:
            if progress_cb:
                try:
                    progress_cb("section_error",
                                {"key": key, "error": err, "stage": stage})
                except Exception:
                    pass

        for sect in judgment_sections:
            if progress_cb:
                try:
                    progress_cb("research_start", {"key": sect["key"]})
                except Exception:
                    pass

            # Mind context for research pack
            mind_ctx_str = self._get_mind_context(
                company, product, sect["key"],
                query_text=f"{sect.get('title', '')} {sect.get('guidance', '')}",
            )

            try:
                pack = generate_research_pack(
                    company=company, product=product,
                    section_key=sect["key"],
                    section_title=sect.get("title", sect["key"]),
                    section_guidance=sect.get("guidance", ""),
                    body_so_far=body_sections + out,
                    mind_ctx=mind_ctx_str,
                    max_turns=5,
                )
            except Exception as e:
                logger.warning("Research pack failed for '%s': %s", sect["key"], e)
                pack = None
                errors.append({"section": sect["key"], "error": str(e),
                               "stage": "research_pack"})

            if pack:
                packs_by_key[sect["key"]] = pack

            if progress_cb:
                try:
                    progress_cb("research_done", {"key": sect["key"],
                                                   "has_pack": bool(pack)})
                    progress_cb("section_start", {"key": sect["key"], "tier": "judgment"})
                except Exception:
                    pass

            # Synthesis — judgment tier (Opus) sees body + prior judgment sections.
            # Wrap in try/except so one synthesis failure doesn't block the rest.
            try:
                section = self.generate_section(
                    company=company, product=product,
                    template_key=template_key, section_key=sect["key"],
                    tier="judgment",
                    prior_sections=body_sections + out,
                    research_pack=pack,
                    snapshot=snapshot, currency=currency,
                )
            except Exception as e:
                logger.error("Judgment synthesis failed for '%s': %s",
                             sect["key"], e, exc_info=True)
                section = {
                    "key": sect["key"], "title": sect["title"],
                    "content": f"[Judgment synthesis failed: {e}]",
                    "metrics": [], "citations": [],
                    "generated_by": "error", "source": sect.get("source"),
                    "error_detail": str(e), "error_stage": "judgment_synthesis",
                }
                errors.append({"section": sect["key"], "error": str(e),
                               "stage": "judgment_synthesis"})
                _emit_section_error(sect["key"], str(e), "judgment_synthesis")

            out.append(section)

            if progress_cb:
                try:
                    progress_cb("section_done", {"key": sect["key"], "tier": "judgment"})
                except Exception:
                    pass

        return out, packs_by_key, errors

    # ── Stage 5.5: citation validation ──────────────────────────────────────

    _CITATION_AUDIT_SYSTEM_PROMPT = (
        "You are a citation auditor for an IC memo. Your job is to flag "
        "citations whose source document is not present in the data room "
        "at all, OR whose snippet obviously contradicts the linked source. "
        "\n\nBE CONSERVATIVE — only flag clear mismatches. When in doubt, "
        "trust the citation. A citation is valid if:\n"
        "  - The source name appears in the data room (even approximately)\n"
        "  - The snippet is consistent with the document type\n"
        "  - The snippet is a reasonable factual claim the doc might make\n\n"
        "FLAG a citation only if:\n"
        "  - The source name is clearly fabricated (no match in data room)\n"
        "  - The snippet contradicts available excerpts\n"
        "  - The snippet is suspiciously specific without source-matching content\n"
    )

    def _validate_citations(self, memo: Dict[str, Any],
                            company: str, product: str) -> List[Dict[str, Any]]:
        """Per-section citation audit — parallelized Sonnet calls.

        Splits audit by section so each call sees a bounded set of citations
        and returns a small JSON list of issues. Fixes the failure mode where
        memos with many citations produced truncated JSON (one combined list
        exceeded max_tokens and failed to parse).

        Source excerpts are fetched once and shared across per-section calls
        so dataroom search cost does not scale with section count.

        An "issue" record looks like:
            {section_key, citation_index, source, reason, severity}

        Skips silently if the data room engine is unavailable.
        """
        if self._dataroom is None:
            return []

        # Group citations by section_key
        by_section: Dict[str, List[Tuple[int, Dict[str, Any]]]] = {}
        for s in memo.get("sections", []):
            entries: List[Tuple[int, Dict[str, Any]]] = []
            for i, c in enumerate(s.get("citations") or []):
                if not isinstance(c, dict):
                    continue
                if not c.get("source") and not c.get("snippet"):
                    continue
                entries.append((i, c))
            if entries:
                by_section[s["key"]] = entries

        if not by_section:
            return []

        # Pre-fetch source excerpts once, shared across all section audits.
        unique_sources = {c.get("source", "")
                          for entries in by_section.values()
                          for _, c in entries
                          if c.get("source")}
        source_excerpts: Dict[str, str] = {}
        for src in list(unique_sources)[:30]:  # cap to keep prompt bounded
            try:
                hits = self._dataroom.search(company, product, src, top_k=2)
                if hits:
                    excerpts = []
                    for h in hits[:2]:
                        txt = (h.get("text") or h.get("content") or "")[:300]
                        excerpts.append(txt)
                    source_excerpts[src] = "\n---\n".join(excerpts)
            except Exception as e:
                logger.debug("Citation validation: search failed for '%s': %s", src, e)

        def _audit_section(section_key: str,
                           entries: List[Tuple[int, Dict[str, Any]]]
                           ) -> List[Dict[str, Any]]:
            cit_lines = []
            relevant_sources = set()
            for idx, c in entries:
                cit_lines.append(
                    f"[{section_key}::{idx}] source='{c.get('source', '')}' "
                    f"snippet='{(c.get('snippet') or '')[:200]}'"
                )
                if c.get("source"):
                    relevant_sources.add(c.get("source"))
            citations_block = "\n".join(cit_lines)

            excerpts_block = ""
            if relevant_sources:
                lines = ["\n--- DATA ROOM EXCERPTS (for grounding) ---"]
                for src in relevant_sources:
                    txt = source_excerpts.get(src)
                    if txt:
                        lines.append(f"\n## {src}\n{txt[:500]}")
                excerpts_block = "\n".join(lines)

            user_prompt = (
                "Review these citations. For each one that is clearly "
                "unverifiable, emit an issue. Return strict JSON:\n\n"
                "```json\n"
                '{"issues": [\n'
                '  {"section_key": "...", "citation_index": 0, '
                '"source": "...", "reason": "...", "severity": "low|medium|high"},\n'
                "  ...\n"
                "]}\n"
                "```\n\n"
                "If NO citations are problematic, return: {\"issues\": []}\n\n"
                "## Citations to audit:\n\n"
                f"{citations_block}\n"
                f"{excerpts_block}"
            )

            from core.ai_client import complete
            try:
                resp = complete(
                    tier="structured",  # Sonnet — fast, cheap
                    system=self._CITATION_AUDIT_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_prompt}],
                    max_tokens=_MAX_TOKENS_CITATION_AUDIT,
                    temperature=0.1,  # Deterministic: same input → same flags
                    log_prefix=f"memo.citation_audit.{company}.{section_key}",
                )
            except Exception as e:
                logger.warning("Citation audit failed for section '%s': %s",
                               section_key, e)
                return []

            text = resp.content[0].text if resp.content else ""
            if text.strip().startswith("```"):
                first = text.find("{")
                last = text.rfind("}")
                if 0 <= first < last:
                    text = text[first:last + 1]

            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                logger.warning("Citation audit JSON parse failed for section "
                               "'%s' — treating as no issues", section_key)
                return []

            issues = parsed.get("issues", [])
            if not isinstance(issues, list):
                return []

            out: List[Dict[str, Any]] = []
            for issue in issues:
                if not isinstance(issue, dict):
                    continue
                out.append({
                    "section_key": str(issue.get("section_key", "") or section_key),
                    "citation_index": int(issue.get("citation_index", 0)) if str(issue.get("citation_index", "")).isdigit() else 0,
                    "source": str(issue.get("source", "")),
                    "reason": str(issue.get("reason", "")),
                    "severity": str(issue.get("severity", "medium")).lower(),
                })
            return out

        # Parallel execution across sections
        max_workers = min(_PARALLEL_CAP, len(by_section))
        all_issues: List[Dict[str, Any]] = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(_audit_section, sk, entries)
                       for sk, entries in by_section.items()]
            for fut in concurrent.futures.as_completed(futures):
                try:
                    all_issues.extend(fut.result())
                except BaseException as e:
                    logger.error("Citation audit future crashed: %s",
                                 e, exc_info=True)

        total_citations = sum(len(v) for v in by_section.values())
        logger.info(
            "Citation audit [%s/%s]: %d issues flagged across %d citations "
            "in %d sections",
            company, product, len(all_issues), total_citations, len(by_section),
        )
        return all_issues

    # ── Stage 6: per-section polish pass ────────────────────────────────────

    def _polish_memo(self, memo: Dict[str, Any]) -> Dict[str, Any]:
        """Per-section polish — parallelized Opus 4.7 calls.

        Replaces the previous one-shot all-sections JSON (which hit max_tokens
        truncation on ~40K+ char memos, producing "Unterminated string" parse
        errors and forcing polished=False). Each section now gets its own small
        Opus call with the full memo body as context for cross-section coherence.
        Parallelized at _PARALLEL_CAP concurrency to keep ITPM bounded.

        Preservation invariants unchanged: metrics/citations/assessments pass
        through verbatim — only prose is rewritten. Contradictions and citation
        issues are filtered per-section so each call sees only what's relevant.

        memo["polished"] is True only when all polishable sections succeed. On
        partial failure, successful sections are applied and failed sections
        preserve their pre-polish content; per-section errors are recorded.
        """
        company = memo.get("company", "")
        product = memo.get("product", "")
        template_name = memo.get("template_name", "")

        # Load mind context once (fund + company level) — shared across calls
        mind_ctx = self._get_mind_context(
            company, product, section_key=None,
            query_text="executive summary investment thesis recommendation polish",
        )

        # Collect contradictions from all research packs (deduped by description)
        contradictions: List[Dict[str, Any]] = []
        seen_desc = set()
        for pack in (memo.get("_research_packs") or {}).values():
            for c in pack.get("contradictions", []):
                desc = (c.get("description") or "").strip()
                if desc and desc not in seen_desc:
                    seen_desc.add(desc)
                    contradictions.append(c)

        citation_issues = memo.get("_citation_issues", [])

        # Build full memo body once — shared coherence context for every call
        body_parts = []
        for s in memo.get("sections", []):
            body_parts.append(f"## {s.get('title', s.get('key', ''))}\n")
            body_parts.append((s.get("content") or "").strip())
            metrics = s.get("metrics") or []
            if metrics:
                body_parts.append("\nMetrics in this section:")
                for m in metrics:
                    body_parts.append(
                        f"  - {m.get('label')}: {m.get('value')} "
                        f"[{m.get('assessment', 'neutral')}]"
                    )
            body_parts.append("")
        full_body = "\n".join(body_parts)

        # Eligible sections — skip errored/auto/empty. Note: sections with
        # generated_by unset (e.g. hand-assembled fixtures) are still eligible;
        # only explicit "error" placeholders are excluded.
        polishable = [
            s for s in memo.get("sections", [])
            if (s.get("content") or "").strip()
            and s.get("generated_by") != "error"
            and s.get("source") != _SOURCE_AUTO
        ]
        if not polishable:
            memo["polished"] = False
            memo.setdefault("errors", []).append({
                "section": "polish",
                "error": "no_polishable_sections",
            })
            return memo

        system_prompt = (
            f"You are a senior credit analyst at ACP polishing one section of "
            f"an IC memo for {company}/{product} ({template_name}). Your task "
            "is coherence and tone, not fresh analysis.\n\n"
            "PRESERVE:\n"
            "- All specific numbers and metrics mentioned in this section\n"
            "- All direct quotes from source documents\n"
            "- All risk flags, findings, and per-metric assessments\n\n"
            "IMPROVE:\n"
            "- Cross-section references (this section should align with the rest of the memo)\n"
            "- Tone consistency (institutional, no marketing language)\n"
            "- Resolve any contradictions flagged for this section — per IC "
            "convention, prefer tape data over data room narrative when they "
            "conflict (tape = live observed state; data room = point-in-time "
            "management view). Cite which source is authoritative when resolving.\n"
            "- If this is Executive Summary / Recommendation / Investment Thesis, "
            "ensure it synthesises the body rather than restating it\n\n"
            "DO NOT:\n"
            "- Introduce new metrics or claims\n"
            "- Remove caveats or data gap acknowledgements\n"
            "- Rename or split the section\n\n"
            f"{mind_ctx}"
        )

        # Shared contradiction block — contradictions name other sections by
        # title (e.g. "Credit Quality" vs "Executive Summary") rather than by
        # key, and the per-section polish still needs to resolve them coherently
        # with the rest of the memo, so we include all contradictions in every
        # call. They're rare (0-3 per memo) and cheap to inline.
        contra_block_shared = ""
        if contradictions:
            lines = ["\n## CONTRADICTIONS DETECTED\n",
                     "For each, either RESOLVE (state which source is "
                     "authoritative and why) or FLAG (mark as open IC "
                     "question). Never leave unaddressed."]
            for i, c in enumerate(contradictions, 1):
                sev = (c.get("severity") or "medium").upper()
                a = c.get("section_a", "?")
                b = c.get("section_b", "?")
                lines.append(f"{i}. [{sev}] {c.get('description', '')}")
                lines.append(f"   Sections involved: *{a}* vs *{b}*")
            contra_block_shared = "\n".join(lines)

        def _polish_one(section: Dict[str, Any]) -> Dict[str, Any]:
            """Polish a single section. Returns a result record (never raises)."""
            key = section.get("key", "")
            title = section.get("title", key)
            original = (section.get("content") or "").strip()

            # Citation issues ARE keyed by section_key, so filter per-section
            section_citation_issues = [
                ci for ci in citation_issues if ci.get("section_key") == key
            ]

            contra_block = contra_block_shared

            cit_block = ""
            if section_citation_issues:
                lines = ["\n## CITATIONS FLAGGED BY VALIDATION\n",
                         "If preserving them, qualify the claim (e.g., "
                         "'per management commentary') or remove the citation "
                         "marker. Do NOT invent a new source."]
                for ci in section_citation_issues[:10]:
                    lines.append(
                        f"- Citation #{ci.get('citation_index')}: "
                        f"{ci.get('source')} — {ci.get('reason', 'not found')}"
                    )
                cit_block = "\n".join(lines)

            user_prompt = (
                "Polish the section below. Return strict JSON:\n\n"
                "```json\n"
                '{"content": "polished section text ..."}\n'
                "```\n\n"
                "Return ONLY the JSON object, no surrounding prose.\n"
                f"{contra_block}"
                f"{cit_block}"
                f"\n\n## Section to polish: {title}\n\n"
                f"{original}\n\n"
                "## Full memo body (for coherence — do not restate):\n\n"
                f"{full_body}"
            )

            from core.ai_client import complete
            t_start = time.time()
            try:
                resp = complete(
                    tier="polish",
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    max_tokens=_MAX_TOKENS_POLISH_SECTION,
                    log_prefix=f"memo.polish.{company}.{key}",
                )
            except Exception as e:
                logger.warning("Polish call failed for section '%s': %s", key, e)
                return {"key": key, "content": None, "error": str(e),
                        "tokens_in": 0, "tokens_out": 0, "cache_read": 0,
                        "elapsed": time.time() - t_start, "model": None}

            elapsed_one = time.time() - t_start
            text = resp.content[0].text if resp.content else ""
            if text.strip().startswith("```"):
                first_brace = text.find("{")
                last_brace = text.rfind("}")
                if 0 <= first_brace < last_brace:
                    text = text[first_brace:last_brace + 1]

            meta = getattr(resp, "_laith_metadata", {}) or {}
            tin = resp.usage.input_tokens
            tout = resp.usage.output_tokens
            tcache = meta.get("cache_read_tokens", 0) or 0
            model = meta.get("model")

            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as e:
                logger.warning("Polish JSON parse failed for section '%s': %s",
                               key, e)
                return {"key": key, "content": None,
                        "error": f"JSON parse: {e}",
                        "tokens_in": tin, "tokens_out": tout,
                        "cache_read": tcache, "elapsed": elapsed_one,
                        "model": model}

            new_content = parsed.get("content", "") if isinstance(parsed, dict) else ""
            if not isinstance(new_content, str) or not new_content.strip():
                return {"key": key, "content": None,
                        "error": "empty_content_field",
                        "tokens_in": tin, "tokens_out": tout,
                        "cache_read": tcache, "elapsed": elapsed_one,
                        "model": model}

            return {"key": key, "content": new_content, "error": None,
                    "tokens_in": tin, "tokens_out": tout,
                    "cache_read": tcache, "elapsed": elapsed_one,
                    "model": model}

        # Parallel execution
        max_workers = min(_PARALLEL_CAP, len(polishable))
        results: List[Dict[str, Any]] = []
        start = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(_polish_one, s) for s in polishable]
            for fut in concurrent.futures.as_completed(futures):
                try:
                    results.append(fut.result())
                except BaseException as e:
                    # Defensive: mirror Stage 2's BaseException discipline so
                    # a SystemExit/GeneratorExit in one future can't tear down
                    # the loop and silently skip the rest.
                    logger.error("Polish future crashed: %s", e, exc_info=True)
                    results.append({"key": "?", "content": None,
                                    "error": f"future_crash: {e}",
                                    "tokens_in": 0, "tokens_out": 0,
                                    "cache_read": 0, "elapsed": 0, "model": None})

        elapsed = time.time() - start

        # Apply polished content — preserve metrics/citations verbatim
        polished_by_key = {r["key"]: r["content"] for r in results
                           if r.get("content") and not r.get("error")}
        for section in memo.get("sections", []):
            new_content = polished_by_key.get(section.get("key"))
            if new_content:
                section["pre_polish_content"] = section.get("content", "")
                section["content"] = new_content
                gb = section.get("generated_by", "ai") or "ai"
                if "+polished" not in gb:
                    section["generated_by"] = gb + "+polished"

        # Aggregate metadata
        total_in = sum(r.get("tokens_in", 0) for r in results)
        total_out = sum(r.get("tokens_out", 0) for r in results)
        total_cache = sum(r.get("cache_read", 0) for r in results)
        model_used = next((r["model"] for r in results if r.get("model")), None)
        error_records = [r for r in results if r.get("error")]

        # polished=True iff ALL polishable sections succeeded
        memo["polished"] = (
            len(error_records) == 0
            and len(polished_by_key) == len(polishable)
        )

        for r in error_records:
            memo.setdefault("errors", []).append({
                "section": "polish",
                "section_key": r.get("key"),
                "error": r.get("error", "unknown"),
            })

        memo.setdefault("generation_meta", {})["polish"] = {
            "model_used": model_used,
            "tokens_in": total_in,
            "tokens_out": total_out,
            "cache_read_tokens": total_cache,
            "elapsed_s": round(elapsed, 2),
            "sections_attempted": len(polishable),
            "sections_polished": len(polished_by_key),
            "sections_failed": len(error_records),
        }
        return memo

    # ── Full memo orchestration ─────────────────────────────────────────────

    def generate_full_memo(self, company: str, product: str,
                           template_key: str,
                           custom_sections: Optional[List[str]] = None,
                           snapshot: Optional[str] = None,
                           currency: Optional[str] = None,
                           progress_cb: Optional[callable] = None,
                           polish: bool = True) -> Dict[str, Any]:
        """Hybrid pipeline memo generation.

        Args:
            company, product: scope
            template_key: e.g. 'credit_memo'
            custom_sections: optional list of section keys to include
            snapshot, currency: passthrough
            progress_cb: optional callback(event_type, payload) for streaming updates
            polish: whether to run the Stage 6 polish pass (default True)

        Returns:
            Complete memo dict with id, sections, metadata, generation_meta.
        """
        template = get_template(template_key)
        if not template:
            raise ValueError(f"Unknown template: {template_key}")

        sections = template["sections"]
        if custom_sections:
            sections = [s for s in sections if s["key"] in custom_sections]

        memo_id = str(uuid.uuid4())[:12]
        t0 = time.time()

        # Stage 1 (planning) — partition by tier
        judgment = [s for s in sections if classify_section(s) == "judgment"]
        non_judgment = [s for s in sections if classify_section(s) != "judgment"]

        logger.info(
            "Memo pipeline start: %s/%s template=%s | parallel=%d judgment=%d",
            company, product, template_key, len(non_judgment), len(judgment),
        )
        if progress_cb:
            try:
                progress_cb("pipeline_start", {
                    "memo_id": memo_id,
                    "parallel_sections": len(non_judgment),
                    "judgment_sections": len(judgment),
                })
            except Exception:
                pass

        # Stages 2 + 3 — parallel structured + auto.
        # Returns (sections, errors). Errors are collected for transparency;
        # downstream stages still run on whatever succeeded.
        body_sections, parallel_errors = self._generate_parallel(
            company, product, template_key, non_judgment,
            snapshot, currency, progress_cb=progress_cb,
        )

        # Preserve template order: rebuild sections list in original order,
        # filling judgment sections with placeholders we'll replace in stage 5
        final_sections: List[Dict[str, Any]] = []
        body_by_key = {s["key"]: s for s in body_sections}
        for sect in sections:
            if sect["key"] in body_by_key:
                final_sections.append(body_by_key[sect["key"]])
            else:
                # Placeholder for judgment section; will be filled below
                final_sections.append({"key": sect["key"], "title": sect["title"],
                                       "content": "", "metrics": [], "citations": [],
                                       "source": sect.get("source")})

        # Stages 4 + 5 — judgment sections (sequential). Also collect raw
        # research packs for use by contradiction-aware polish + sidecar save.
        # Per-section failures are captured in judgment_errors; one failing
        # section does not block the rest.
        judgment_results, research_packs, judgment_errors = self._generate_judgment_sections(
            company, product, template_key, judgment, body_sections,
            snapshot, currency, progress_cb=progress_cb,
        )
        judgment_by_key = {s["key"]: s for s in judgment_results}
        for i, sect in enumerate(final_sections):
            if sect["key"] in judgment_by_key:
                final_sections[i] = judgment_by_key[sect["key"]]

        # Build memo object
        title = f"{template['name']} \u2014 {company}"
        if product:
            title += f" {product}"

        # Collect ALL error sources for the memo record:
        #   1. sections with generated_by=="error" (synthesized error objects)
        #   2. parallel_errors (pool-level failures, e.g. GeneratorExit)
        #   3. judgment_errors (research-pack or synthesis failures)
        error_sections = [s for s in final_sections if s.get("generated_by") == "error"]
        all_errors: List[Dict[str, Any]] = []
        for s in error_sections:
            all_errors.append({
                "section": s["key"],
                "error": s.get("error_detail", "generation_failed"),
                "stage": s.get("error_stage", "unknown"),
            })
        all_errors.extend(parallel_errors)
        all_errors.extend(judgment_errors)

        # True only when the whole pipeline produced no usable content — used
        # to mark the memo as status=error and skip polish.
        has_any_content = any(
            (s.get("content") or "").strip()
            and s.get("generated_by") not in ("error", None)
            for s in final_sections
        )

        # Aggregate generation metadata across all sections
        models_used: Dict[str, int] = {}
        total_tokens_in = 0
        total_tokens_out = 0
        total_cache_read = 0
        for s in final_sections:
            m = s.get("generation_meta") or {}
            model = m.get("model_used")
            if model:
                models_used[model] = models_used.get(model, 0) + 1
            total_tokens_in += m.get("tokens_in", 0) or 0
            total_tokens_out += m.get("tokens_out", 0) or 0
            total_cache_read += m.get("cache_read_tokens", 0) or 0

        memo = {
            "id": memo_id,
            "company": company,
            "product": product,
            "template": template_key,
            "template_name": template["name"],
            "title": title,
            "status": "error" if not has_any_content else "draft",
            "sections": final_sections,
            "errors": all_errors,
            "version": 1,
            "created_at": datetime.utcnow().isoformat(),
            "snapshot": snapshot,
            "currency": currency,
            "generation_mode": "hybrid-v1",
            "polished": False,
            "models_used": models_used,
            "generation_meta": {
                "total_tokens_in": total_tokens_in,
                "total_tokens_out": total_tokens_out,
                "total_cache_read_tokens": total_cache_read,
                "elapsed_s": round(time.time() - t0, 2),
                "parallel_cap": _PARALLEL_CAP,
            },
            # Transient: research packs (stripped before main save, written as sidecar).
            "_research_packs": research_packs,
        }

        # Stage 5.5 — citation validation. Runs as long as there's some content
        # to audit; no longer short-circuited by any earlier section failure
        # (that was the 2026-04-18 bug: one Stage 2 error blocked 5.5 + 6).
        if has_any_content:
            if progress_cb:
                try:
                    progress_cb("citation_audit_start", {"memo_id": memo_id})
                except Exception:
                    pass
            try:
                citation_issues = self._validate_citations(memo, company, product)
                if citation_issues:
                    memo["_citation_issues"] = citation_issues
            except Exception as e:
                logger.warning("Citation validation crashed: %s", e)
                citation_issues = []
            if progress_cb:
                try:
                    progress_cb("citation_audit_done", {
                        "memo_id": memo_id,
                        "issues_flagged": len(memo.get("_citation_issues", [])),
                    })
                except Exception:
                    pass

        # Stage 6 — polish. Same gate: any content → run polish.
        if polish and has_any_content:
            if progress_cb:
                try:
                    progress_cb("polish_start", {"memo_id": memo_id})
                except Exception:
                    pass
            memo = self._polish_memo(memo)
            if progress_cb:
                try:
                    progress_cb("polish_done", {"memo_id": memo_id,
                                                 "polished": memo.get("polished")})
                except Exception:
                    pass

        # Terminal-error emit — memo was saved but has no usable content.
        if not has_any_content and progress_cb:
            try:
                progress_cb("pipeline_error", {
                    "memo_id": memo_id,
                    "reason": "all_sections_failed",
                    "error_count": len(all_errors),
                })
            except Exception:
                pass

        memo["generation_meta"]["total_elapsed_s"] = round(time.time() - t0, 2)

        # Cost estimate
        try:
            from core.ai_client import estimate_cost
            cost = 0.0
            for s in memo["sections"]:
                m = s.get("generation_meta") or {}
                if m.get("model_used"):
                    cost += estimate_cost(m["model_used"],
                                          m.get("tokens_in", 0),
                                          m.get("tokens_out", 0),
                                          m.get("cache_read_tokens", 0))
            polish_meta = memo.get("generation_meta", {}).get("polish") or {}
            if polish_meta.get("model_used"):
                cost += estimate_cost(polish_meta["model_used"],
                                      polish_meta.get("tokens_in", 0),
                                      polish_meta.get("tokens_out", 0),
                                      polish_meta.get("cache_read_tokens", 0))
            memo["generation_meta"]["cost_usd_estimate"] = round(cost, 4)
        except Exception:
            pass

        if progress_cb:
            try:
                progress_cb("pipeline_done", {"memo_id": memo_id,
                                              "polished": memo.get("polished"),
                                              "elapsed_s": memo["generation_meta"]["total_elapsed_s"]})
            except Exception:
                pass

        return memo

    # ── Section regeneration (legacy — preserves behaviour for /regenerate) ─

    def regenerate_section(self, memo: Dict[str, Any], section_key: str,
                           snapshot: Optional[str] = None,
                           currency: Optional[str] = None) -> Dict[str, Any]:
        """Regenerate one section in place. Preserves metrics/citations from
        prior sections but rewrites only the target."""
        company = memo["company"]
        product = memo["product"]
        template_key = memo["template"]

        prior: List[Dict[str, Any]] = []
        target_idx = None
        for i, s in enumerate(memo["sections"]):
            if s.get("key") == section_key:
                target_idx = i
                break
            prior.append(s)
        if target_idx is None:
            raise ValueError(f"Section '{section_key}' not in memo")

        # Classify target
        template = get_template(template_key)
        section_def = next((s for s in template["sections"] if s["key"] == section_key), None)
        tier = classify_section(section_def) if section_def else "structured"

        # For judgment regeneration, also build a fresh research pack
        research_pack = None
        if tier == "judgment" and section_def:
            try:
                from core.memo.agent_research import generate_research_pack
                mind_ctx_str = self._get_mind_context(
                    company, product, section_key,
                    query_text=f"{section_def.get('title', '')} {section_def.get('guidance', '')}",
                )
                research_pack = generate_research_pack(
                    company=company, product=product,
                    section_key=section_key,
                    section_title=section_def.get("title", section_key),
                    section_guidance=section_def.get("guidance", ""),
                    body_so_far=prior,
                    mind_ctx=mind_ctx_str,
                    max_turns=5,
                )
            except Exception as e:
                logger.warning("Regen research pack failed: %s", e)

        new_section = self.generate_section(
            company=company, product=product,
            template_key=template_key, section_key=section_key,
            tier=tier,
            prior_sections=prior,
            research_pack=research_pack,
            snapshot=snapshot or memo.get("snapshot"),
            currency=currency or memo.get("currency"),
        )
        memo["sections"][target_idx] = new_section
        memo["version"] = memo.get("version", 1) + 1
        return new_section
