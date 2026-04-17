"""
AI-powered IC Memo Generator.

Generates memo sections by combining:
  1. Live analytics context (via AnalyticsBridge)
  2. Data room research chunks (via DataRoomEngine.search)
  3. Living Mind institutional memory (via build_mind_context)
  4. Claude API for narrative generation

Each section is generated independently with awareness of prior sections
for coherence. Full memos are built sequentially so later sections can
reference earlier analysis.
"""

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Optional

from .templates import get_template, MEMO_TEMPLATES
from .analytics_bridge import AnalyticsBridge

logger = logging.getLogger(__name__)

# Anthropic client — wrapped in try/except for environments without the SDK
try:
    import anthropic
    _HAS_ANTHROPIC = True
except ImportError:
    _HAS_ANTHROPIC = False
    logger.warning("anthropic SDK not installed; AI generation will be unavailable")

# Model to use for memo generation
_MODEL = "claude-opus-4-6"
_MAX_TOKENS_PER_SECTION = 2000
_MAX_TOKENS_EXEC_SUMMARY = 3000


def _get_anthropic_client():
    """Create an Anthropic client from environment variable."""
    if not _HAS_ANTHROPIC:
        return None
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set; AI generation unavailable")
        return None
    return anthropic.Anthropic(api_key=api_key)


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


def _build_section_user_prompt(section: dict,
                               analytics_text: str,
                               research_text: str,
                               prior_text: str) -> str:
    """Build the user prompt for a specific section."""
    parts = [
        f"## Section: {section['title']}\n",
        f"**Guidance:** {section['guidance']}\n",
    ]

    if analytics_text:
        parts.append(
            f"\n### Analytics Context\n{analytics_text}\n"
        )

    if research_text:
        parts.append(
            f"\n### Data Room Research\n{research_text}\n"
        )

    if prior_text:
        parts.append(
            f"\n### Prior Sections (for coherence)\n{prior_text}\n"
        )

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


def _parse_ai_response(text: str) -> dict:
    """Parse AI response, handling both JSON and plain text."""
    # Strip markdown fences if present
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
        # If JSON parsing fails, treat the whole response as content
        logger.warning("AI response was not valid JSON; using as plain text")
        return {
            "content": text.strip(),
            "metrics": [],
            "citations": [],
        }


class MemoGenerator:
    """Generates memo sections using AI with analytics + research context."""

    def __init__(self):
        """Initialize the generator with its dependencies."""
        self.bridge = AnalyticsBridge()
        self._client = _get_anthropic_client()
        self._dataroom = None
        self._mind_available = False

        # Lazy-load DataRoomEngine
        try:
            from core.dataroom import DataRoomEngine
            self._dataroom = DataRoomEngine()
        except Exception as e:
            logger.warning("DataRoomEngine not available: %s", e)

        # Check if mind module is available
        try:
            from core.mind import build_mind_context
            self._mind_available = True
        except Exception as e:
            logger.warning("Mind module not available: %s", e)

    # ── Research context ────────────────────────────────────────────────────

    def _get_research_chunks(self, company: str, product: str,
                             section: dict,
                             top_k: int = 5) -> str:
        """Search the data room for relevant chunks for a section.

        Returns formatted text with source attribution.
        """
        if self._dataroom is None:
            return ""

        # Build search query from section title + guidance keywords
        query = f"{section['title']} {section['guidance']}"

        try:
            results = self._dataroom.search(company, product, query, top_k=top_k)
        except Exception as e:
            logger.warning("Data room search failed for '%s': %s",
                           section["key"], e)
            return ""

        if not results:
            return ""

        parts = []
        for i, hit in enumerate(results, 1):
            source = hit.get("source_file", hit.get("doc_id", "unknown"))
            text = hit.get("text", hit.get("content", ""))
            score = hit.get("score", 0)
            # Truncate long chunks
            if len(text) > 600:
                text = text[:600] + "..."
            parts.append(f"[{i}] Source: {source} (relevance: {score:.2f})\n{text}")

        return "\n\n".join(parts)

    # ── Mind context ────────────────────────────────────────────────────────

    def _get_mind_context(self, company: str, product: str,
                          section_key: str) -> str:
        """Load living mind context for the AI prompt."""
        if not self._mind_available:
            return ""

        try:
            from core.mind import build_mind_context
            ctx = build_mind_context(
                company=company,
                product=product,
                task_type="memo",
                section_key=section_key,
            )
            if ctx.is_empty:
                return ""
            return (
                "### Institutional Knowledge\n"
                f"{ctx.formatted}\n"
            )
        except Exception as e:
            logger.warning("Mind context failed: %s", e)
            return ""

    # ── Section generation ──────────────────────────────────────────────────

    def generate_section(self, company: str, product: str,
                         template_key: str, section_key: str,
                         analytics_context: Optional[dict] = None,
                         research_chunks: Optional[str] = None,
                         prior_sections: Optional[list] = None,
                         snapshot: Optional[str] = None,
                         currency: Optional[str] = None) -> dict:
        """Generate one memo section.

        Args:
            company: Company identifier.
            product: Product identifier.
            template_key: Which template (credit_memo, monitoring_update, etc.).
            section_key: Which section within the template.
            analytics_context: Pre-computed analytics (if None, will be fetched).
            research_chunks: Pre-searched research text (if None, will be searched).
            prior_sections: List of already-generated sections (for coherence).
            snapshot: Optional specific snapshot filename.
            currency: Optional display currency override.

        Returns:
            Dict with key, title, content, metrics, citations, generated_by.
        """
        template = get_template(template_key)
        if not template:
            raise ValueError(f"Unknown template: {template_key}")

        # Find the section definition
        section_def = None
        for s in template["sections"]:
            if s["key"] == section_key:
                section_def = s
                break
        if not section_def:
            raise ValueError(
                f"Unknown section '{section_key}' in template '{template_key}'"
            )

        # Get analytics context if not provided
        if analytics_context is None and section_def["source"] in (
            "analytics", "mixed"
        ):
            analytics_context = self.bridge.get_section_context(
                company, product, section_key,
                snapshot=snapshot, currency=currency,
            )

        # Get research chunks if not provided
        if research_chunks is None and section_def["source"] in (
            "dataroom", "mixed"
        ):
            research_chunks = self._get_research_chunks(
                company, product, section_def
            )

        # Format analytics for the prompt
        analytics_text = ""
        if analytics_context and analytics_context.get("available"):
            # Include both formatted text and raw metrics
            analytics_text = analytics_context.get("text", "")
            metrics = analytics_context.get("metrics", [])
            if metrics:
                bullet_lines = []
                for m in metrics:
                    bullet_lines.append(
                        f"- {m['label']}: {m['value']} "
                        f"({m.get('assessment', 'neutral')})"
                    )
                analytics_text += "\n\nMetrics:\n" + "\n".join(bullet_lines)

        # Format prior sections for coherence
        prior_text = ""
        if prior_sections:
            summaries = []
            for ps in prior_sections[-3:]:  # Last 3 sections for context
                title = ps.get("title", "")
                content = ps.get("content", "")
                # Take first 200 chars of each prior section
                summary = content[:200] + "..." if len(content) > 200 else content
                summaries.append(f"**{title}:** {summary}")
            prior_text = "\n\n".join(summaries)

        # Auto-generated sections (appendix)
        if section_def["source"] == "auto":
            return self._generate_auto_section(
                company, product, section_def,
                analytics_context, research_chunks,
            )

        # If no AI client, generate a structured placeholder
        if self._client is None:
            return self._generate_placeholder_section(
                section_def, analytics_context, research_chunks,
            )

        # Build prompts
        mind_context = self._get_mind_context(company, product, section_key)
        system_prompt = _build_section_system_prompt(
            company, product, template["name"], mind_context,
        )
        user_prompt = _build_section_user_prompt(
            section_def, analytics_text,
            research_chunks or "", prior_text,
        )

        # Call Claude API
        max_tokens = (
            _MAX_TOKENS_EXEC_SUMMARY
            if section_key == "exec_summary"
            else _MAX_TOKENS_PER_SECTION
        )

        try:
            response = self._client.messages.create(
                model=_MODEL,
                max_tokens=max_tokens,
                system=[{
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=[{"role": "user", "content": user_prompt}],
            )
            ai_text = response.content[0].text
            parsed = _parse_ai_response(ai_text)
        except Exception as e:
            logger.error("Claude API call failed for section '%s': %s",
                         section_key, e)
            return self._generate_placeholder_section(
                section_def, analytics_context, research_chunks,
            )

        return {
            "key": section_def["key"],
            "title": section_def["title"],
            "content": parsed["content"],
            "metrics": parsed["metrics"],
            "citations": parsed["citations"],
            "generated_by": "ai",
            "source": section_def["source"],
            "generated_at": datetime.utcnow().isoformat(),
        }

    # ── Full memo generation ────────────────────────────────────────────────

    def generate_full_memo(self, company: str, product: str,
                           template_key: str,
                           custom_sections: Optional[list] = None,
                           snapshot: Optional[str] = None,
                           currency: Optional[str] = None) -> dict:
        """Generate all sections of a memo sequentially.

        Sections are generated in order so later sections can reference
        earlier analysis for coherence.

        Args:
            company: Company identifier.
            product: Product identifier.
            template_key: Which template to use.
            custom_sections: Optional list of section keys to generate
                (if None, generates all sections in the template).
            snapshot: Optional specific snapshot filename.
            currency: Optional display currency override.

        Returns:
            Complete memo dict with id, sections, metadata.
        """
        template = get_template(template_key)
        if not template:
            raise ValueError(f"Unknown template: {template_key}")

        memo_id = str(uuid.uuid4())[:12]
        sections_to_generate = template["sections"]

        if custom_sections:
            sections_to_generate = [
                s for s in template["sections"]
                if s["key"] in custom_sections
            ]

        generated_sections = []
        errors = []

        for section_def in sections_to_generate:
            logger.info("Generating section: %s", section_def["key"])
            try:
                section = self.generate_section(
                    company=company,
                    product=product,
                    template_key=template_key,
                    section_key=section_def["key"],
                    prior_sections=generated_sections,
                    snapshot=snapshot,
                    currency=currency,
                )
                generated_sections.append(section)
            except Exception as e:
                logger.error("Failed to generate section '%s': %s",
                             section_def["key"], e)
                errors.append({
                    "section": section_def["key"],
                    "error": str(e),
                })
                # Add a placeholder so subsequent sections have context
                generated_sections.append({
                    "key": section_def["key"],
                    "title": section_def["title"],
                    "content": f"[Section generation failed: {e}]",
                    "metrics": [],
                    "citations": [],
                    "generated_by": "error",
                    "source": section_def["source"],
                })

        # Build the memo title
        title = f"{template['name']} \u2014 {company}"
        if product:
            title += f" {product}"

        return {
            "id": memo_id,
            "company": company,
            "product": product,
            "template": template_key,
            "template_name": template["name"],
            "title": title,
            "status": "draft",
            "sections": generated_sections,
            "errors": errors,
            "version": 1,
            "created_at": datetime.utcnow().isoformat(),
            "snapshot": snapshot,
            "currency": currency,
        }

    # ── Section regeneration ────────────────────────────────────────────────

    def regenerate_section(self, memo: dict, section_key: str,
                           snapshot: Optional[str] = None,
                           currency: Optional[str] = None) -> dict:
        """Regenerate one section while preserving the rest.

        Updates the memo dict in place and returns the regenerated section.
        """
        company = memo["company"]
        product = memo["product"]
        template_key = memo["template"]

        # Find prior sections (everything before the target section)
        prior = []
        for s in memo["sections"]:
            if s["key"] == section_key:
                break
            prior.append(s)

        new_section = self.generate_section(
            company=company,
            product=product,
            template_key=template_key,
            section_key=section_key,
            prior_sections=prior,
            snapshot=snapshot or memo.get("snapshot"),
            currency=currency or memo.get("currency"),
        )

        # Replace in the memo
        for i, s in enumerate(memo["sections"]):
            if s["key"] == section_key:
                memo["sections"][i] = new_section
                break

        # Bump version
        memo["version"] = memo.get("version", 1) + 1

        return new_section

    # ── Placeholder generation (no AI) ──────────────────────────────────────

    def _generate_placeholder_section(self, section_def: dict,
                                      analytics_context: Optional[dict],
                                      research_chunks: Optional[str]) -> dict:
        """Generate a structured placeholder when AI is unavailable.

        Fills in whatever data is available from analytics and research.
        """
        content_parts = []

        if analytics_context and analytics_context.get("available"):
            content_parts.append(analytics_context.get("text", ""))
            metrics = analytics_context.get("metrics", [])
            if metrics:
                content_parts.append("\nKey Metrics:")
                for m in metrics:
                    content_parts.append(
                        f"  - {m['label']}: {m['value']}"
                    )

        if research_chunks:
            content_parts.append(
                "\nData Room Sources:\n" + research_chunks[:500]
            )

        if not content_parts:
            content_parts.append(
                f"[Placeholder: {section_def['title']}]\n"
                f"{section_def['guidance']}\n\n"
                "AI generation unavailable. Fill in manually or regenerate "
                "when the ANTHROPIC_API_KEY is configured."
            )

        return {
            "key": section_def["key"],
            "title": section_def["title"],
            "content": "\n".join(content_parts),
            "metrics": (
                analytics_context.get("metrics", [])
                if analytics_context else []
            ),
            "citations": [],
            "generated_by": "placeholder",
            "source": section_def["source"],
            "generated_at": datetime.utcnow().isoformat(),
        }

    def _generate_auto_section(self, company: str, product: str,
                               section_def: dict,
                               analytics_context: Optional[dict],
                               research_chunks: Optional[str]) -> dict:
        """Generate auto-populated sections (e.g., appendix/data sources)."""
        content_parts = [
            "## Data Sources Used in This Memo\n",
            f"**Company:** {company}",
            f"**Product:** {product}",
            f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n",
        ]

        # List snapshots used
        try:
            from core.loader import get_snapshots
            snapshots = get_snapshots(company, product)
            if snapshots:
                content_parts.append("### Tape Snapshots")
                for snap in snapshots:
                    content_parts.append(
                        f"  - {snap['filename']} ({snap.get('date', 'no date')})"
                    )
        except Exception:
            pass

        # List data room documents
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
