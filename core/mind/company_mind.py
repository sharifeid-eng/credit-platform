"""
Company Mind — Per-company knowledge graph for the Laith credit platform.

Captures corrections, memo edits, research findings, IC feedback,
data quality notes, and session lessons for a specific company/product.

Storage: data/{company}/{product}/mind/
Format: Append-only JSONL files (one JSON object per line)
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Project root is 3 levels up from this file: core/mind/company_mind.py -> project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# JSONL file names
_FILES = {
    "corrections": "corrections.jsonl",
    "memo_edits": "memo_edits.jsonl",
    "findings": "findings.jsonl",
    "ic_feedback": "ic_feedback.jsonl",
    "data_quality": "data_quality.jsonl",
    "session_lessons": "session_lessons.jsonl",
}

# Task-type to category relevance mapping
_TASK_RELEVANCE: Dict[str, List[str]] = {
    "commentary": ["corrections", "findings", "data_quality"],
    "executive_summary": ["corrections", "findings", "ic_feedback", "data_quality"],
    "tab_insight": ["corrections", "findings", "data_quality"],
    "chat": ["findings", "data_quality", "corrections"],
    "memo": ["corrections", "memo_edits", "ic_feedback", "findings"],
    "research_report": ["findings", "ic_feedback", "data_quality", "corrections"],
    "onboarding": ["data_quality", "session_lessons"],
    "validation": ["data_quality", "corrections"],
    "default": ["corrections", "findings", "data_quality"],
}

# Max entries to include per category and total
_MAX_ENTRIES_PER_CATEGORY = 5
_MAX_TOTAL_ENTRIES = 15


@dataclass
class MindEntry:
    """A single entry in the company mind knowledge base."""

    id: str
    timestamp: str
    category: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    promoted: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "category": self.category,
            "content": self.content,
            "metadata": self.metadata,
            "promoted": self.promoted,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> MindEntry:
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            timestamp=d.get("timestamp", datetime.now(timezone.utc).isoformat()),
            category=d.get("category", "unknown"),
            content=d.get("content", ""),
            metadata=d.get("metadata", {}),
            promoted=d.get("promoted", False),
        )


@dataclass
class MindContext:
    """Context package returned by get_context_for_prompt()."""

    entries: List[MindEntry]
    formatted: str
    entry_count: int
    categories_included: List[str]


def _make_entry(category: str, content: str, metadata: Optional[Dict] = None) -> MindEntry:
    """Create a new MindEntry with auto-generated id and timestamp."""
    return MindEntry(
        id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        category=category,
        content=content,
        metadata=metadata or {},
        promoted=False,
    )


class CompanyMind:
    """Per-company knowledge that accumulates over sessions.

    Captures:
    1. Corrections -- analyst overrides of AI outputs
    2. Memo edits -- diffs between AI draft and analyst final version
    3. Research findings -- key conclusions worth remembering
    4. IC feedback -- what IC asked about or pushed back on
    5. Data quality notes -- known issues with specific tapes or documents
    6. Session lessons -- errors and patterns from tasks/lessons.md

    Storage: data/{company}/{product}/mind/
    Format: Append-only JSONL files (one JSON object per line)
    """

    def __init__(self, company: str, product: str, base_dir: Optional[Path] = None):
        """Initialize CompanyMind for a specific company/product.

        Args:
            company: Company name (e.g., "klaim")
            product: Product name (e.g., "UAE_healthcare")
            base_dir: Override for the mind directory.
                      Defaults to data/{company}/{product}/mind/
        """
        self.company = company
        self.product = product
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            self.base_dir = _PROJECT_ROOT / "data" / company / product / "mind"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Create directory structure if it doesn't exist."""
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _jsonl_path(self, category: str) -> Path:
        """Get the JSONL file path for a category."""
        filename = _FILES.get(category)
        if not filename:
            raise ValueError(f"Unknown category: {category}. Valid: {list(_FILES.keys())}")
        return self.base_dir / filename

    def _append_entry(self, entry: MindEntry, graph_meta: Optional[Dict] = None) -> None:
        """Append a single entry to its category's JSONL file.

        Args:
            entry: The MindEntry to append.
            graph_meta: Optional graph metadata (relations, source_refs, node_type)
                        stored in metadata._graph for backward-compatible JSONL.
        """
        d = entry.to_dict()
        if graph_meta:
            d["metadata"]["_graph"] = graph_meta
        path = self._jsonl_path(entry.category)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
        logger.debug(
            "CompanyMind[%s/%s]: recorded %s entry %s",
            self.company, self.product, entry.category, entry.id[:8],
        )

        # Publish event for downstream listeners
        try:
            from core.mind.event_bus import event_bus, Events
            event_bus.publish(Events.MIND_ENTRY_CREATED, {
                "scope": "company",
                "company": self.company,
                "product": self.product,
                "entry_id": entry.id,
                "category": entry.category,
                "content": entry.content,
            })
        except Exception:
            pass  # Event bus not critical — never block writes

    def _read_entries(self, category: str) -> List[MindEntry]:
        """Read all entries from a category's JSONL file.

        Lazily upgrades old-format entries with graph metadata defaults.
        """
        from core.mind.schema import upgrade_entry

        path = self._jsonl_path(category)
        if not path.exists():
            return []
        entries = []
        with open(path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    upgrade_entry(d)  # adds graph defaults if missing (no rewrite)
                    entries.append(MindEntry.from_dict(d))
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(
                        "CompanyMind[%s/%s]: skipping malformed line %d in %s: %s",
                        self.company, self.product, line_num, path.name, e,
                    )
        return entries

    # ── Recording methods ──────────────────────────────────────────────

    def record_correction(
        self, category: str, original: str, corrected: str, reason: str = ""
    ) -> MindEntry:
        """Record an analyst correction to AI output.

        Args:
            category: What was corrected (e.g., "metric_label", "threshold", "interpretation")
            original: The original AI output
            corrected: The analyst's correction
            reason: Why the correction was made

        Returns:
            The created MindEntry.
        """
        entry = _make_entry(
            "corrections",
            f"{category}: changed '{original}' to '{corrected}'",
            {
                "correction_category": category,
                "original": original,
                "corrected": corrected,
                "reason": reason,
            },
        )
        self._append_entry(entry)
        return entry

    def record_memo_edit(
        self, memo_id: str, section_key: str, ai_version: str, analyst_version: str
    ) -> MindEntry:
        """Record a diff between AI draft and analyst final version of a memo section.

        Args:
            memo_id: Identifier for the memo (e.g., "exec_summary_2026-03")
            section_key: Which section was edited (e.g., "portfolio_overview", "risk_assessment")
            ai_version: The original AI-generated text
            analyst_version: The analyst's final edited text

        Returns:
            The created MindEntry.
        """
        # Compute a simple diff summary
        ai_words = set(ai_version.lower().split())
        analyst_words = set(analyst_version.lower().split())
        added = analyst_words - ai_words
        removed = ai_words - analyst_words

        entry = _make_entry(
            "memo_edits",
            f"Memo {memo_id}, section '{section_key}': analyst edited AI draft",
            {
                "memo_id": memo_id,
                "section_key": section_key,
                "ai_version": ai_version,
                "analyst_version": analyst_version,
                "words_added": len(added),
                "words_removed": len(removed),
                "ai_length": len(ai_version),
                "analyst_length": len(analyst_version),
            },
        )
        self._append_entry(entry)
        return entry

    def record_research_finding(
        self, finding: str, confidence: str = "medium", source_docs: Optional[List[str]] = None
    ) -> MindEntry:
        """Record a key research conclusion worth remembering.

        Args:
            finding: The research finding/conclusion
            confidence: Confidence level ("high", "medium", "low")
            source_docs: List of source document references

        Returns:
            The created MindEntry.
        """
        entry = _make_entry(
            "findings",
            finding,
            {
                "confidence": confidence,
                "source_docs": source_docs or [],
            },
        )
        self._append_entry(entry)
        return entry

    def record_ic_feedback(self, feedback: str, memo_id: Optional[str] = None) -> MindEntry:
        """Record IC feedback, questions, or pushback.

        Args:
            feedback: The IC feedback or question
            memo_id: Optional memo that triggered this feedback

        Returns:
            The created MindEntry.
        """
        meta: Dict[str, Any] = {}
        if memo_id:
            meta["memo_id"] = memo_id
        entry = _make_entry("ic_feedback", feedback, meta)
        self._append_entry(entry)
        return entry

    def record_data_quality_note(self, note: str, tape_or_doc: str = "") -> MindEntry:
        """Record a known data quality issue with a specific tape or document.

        Args:
            note: Description of the data quality issue
            tape_or_doc: The tape filename or document reference

        Returns:
            The created MindEntry.
        """
        entry = _make_entry(
            "data_quality",
            note,
            {"tape_or_doc": tape_or_doc},
        )
        self._append_entry(entry)
        return entry

    def record_session_lesson(self, lesson: str, category: str = "general") -> MindEntry:
        """Record a lesson learned from a session.

        Args:
            lesson: The lesson or pattern identified
            category: Sub-category (e.g., "data", "analysis", "presentation", "general")

        Returns:
            The created MindEntry.
        """
        entry = _make_entry(
            "session_lessons",
            lesson,
            {"lesson_category": category},
        )
        self._append_entry(entry)
        return entry

    # ── Query methods ──────────────────────────────────────────────────

    def get_context_for_prompt(
        self, task_type: str, section_key: Optional[str] = None
    ) -> MindContext:
        """Pull relevant company-level context for an AI prompt.

        Selects entries based on task_type relevance, recency, and section match.

        Args:
            task_type: The type of AI task (commentary, executive_summary, chat, etc.)
            section_key: Optional section to boost relevance for (e.g., "collection")

        Returns:
            MindContext with selected entries and a formatted prompt string.
        """
        relevant_categories = _TASK_RELEVANCE.get(task_type, _TASK_RELEVANCE["default"])

        # Collect entries from relevant categories
        all_entries: List[MindEntry] = []
        for cat in relevant_categories:
            entries = self._read_entries(cat)
            all_entries.extend(entries)

        if not all_entries:
            return MindContext(entries=[], formatted="", entry_count=0, categories_included=[])

        # Score and rank entries
        scored = self._score_entries(all_entries, task_type, section_key)

        # Take top entries up to limit
        scored.sort(key=lambda x: x[1], reverse=True)
        selected = [e for e, _ in scored[:_MAX_TOTAL_ENTRIES]]

        # Build formatted string
        header = f"Company Knowledge: {self.company}/{self.product}"
        formatted = self._format_for_prompt(selected, header)

        categories_included = list(set(e.category for e in selected))

        return MindContext(
            entries=selected,
            formatted=formatted,
            entry_count=len(selected),
            categories_included=categories_included,
        )

    def get_company_profile(self) -> Dict[str, Any]:
        """Build a synthesized view of everything known about this company.

        Reads all categories, counts entries, identifies key themes,
        and returns a structured profile.

        Returns:
            Dictionary with company profile data.
        """
        profile: Dict[str, Any] = {
            "company": self.company,
            "product": self.product,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "categories": {},
            "key_findings": [],
            "data_quality_issues": [],
            "ic_concerns": [],
            "correction_patterns": [],
        }

        for category in _FILES:
            entries = self._read_entries(category)
            profile["categories"][category] = {
                "count": len(entries),
                "latest": entries[-1].timestamp if entries else None,
            }

        # Extract key findings (high confidence)
        findings = self._read_entries("findings")
        for f in findings:
            if f.metadata.get("confidence") == "high":
                profile["key_findings"].append(f.content)

        # Extract active data quality issues
        dq = self._read_entries("data_quality")
        for d in dq[-10:]:  # Last 10 issues
            profile["data_quality_issues"].append({
                "note": d.content,
                "tape_or_doc": d.metadata.get("tape_or_doc", ""),
                "date": d.timestamp,
            })

        # Extract IC concerns
        ic = self._read_entries("ic_feedback")
        for i in ic[-5:]:  # Last 5 IC items
            profile["ic_concerns"].append(i.content)

        # Identify correction patterns
        corrections = self._read_entries("corrections")
        correction_cats: Dict[str, int] = {}
        for c in corrections:
            cat = c.metadata.get("correction_category", "unknown")
            correction_cats[cat] = correction_cats.get(cat, 0) + 1
        profile["correction_patterns"] = [
            {"category": k, "count": v} for k, v in sorted(correction_cats.items(), key=lambda x: -x[1])
        ]

        # Write profile to disk
        profile_path = self.base_dir / "profile.json"
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)

        return profile

    def get_improvement_log(self) -> List[Dict[str, Any]]:
        """Build a timeline of quality improvements from corrections and lessons.

        Returns:
            Chronologically sorted list of improvement events.
        """
        events = []

        corrections = self._read_entries("corrections")
        for c in corrections:
            events.append({
                "type": "correction",
                "timestamp": c.timestamp,
                "content": c.content,
                "category": c.metadata.get("correction_category", ""),
            })

        lessons = self._read_entries("session_lessons")
        for l in lessons:
            events.append({
                "type": "lesson",
                "timestamp": l.timestamp,
                "content": l.content,
                "category": l.metadata.get("lesson_category", ""),
            })

        # Sort chronologically
        events.sort(key=lambda x: x["timestamp"])
        return events

    # ── Consolidation ──────────────────────────────────────────────────

    def consolidate(self) -> Dict[str, Any]:
        """Summarize accumulated entries into higher-order patterns.

        Groups similar entries, counts occurrences, and writes a consolidated report.

        Returns:
            Consolidation report.
        """
        report: Dict[str, Any] = {
            "company": self.company,
            "product": self.product,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "categories": {},
            "correction_themes": [],
            "recurring_findings": [],
        }

        for category in _FILES:
            entries = self._read_entries(category)
            report["categories"][category] = {
                "total_entries": len(entries),
                "date_range": {
                    "first": entries[0].timestamp if entries else None,
                    "last": entries[-1].timestamp if entries else None,
                },
            }

        # Identify correction themes (repeated correction categories)
        corrections = self._read_entries("corrections")
        correction_cats: Dict[str, int] = {}
        for c in corrections:
            cat = c.metadata.get("correction_category", "unknown")
            correction_cats[cat] = correction_cats.get(cat, 0) + 1
        report["correction_themes"] = [
            {"category": k, "count": v}
            for k, v in sorted(correction_cats.items(), key=lambda x: -x[1])
            if v >= 2
        ]

        # Identify recurring findings
        findings = self._read_entries("findings")
        finding_contents: Dict[str, int] = {}
        for f in findings:
            key = f.content.lower().strip()[:100]  # Normalize and truncate for grouping
            finding_contents[key] = finding_contents.get(key, 0) + 1
        report["recurring_findings"] = [
            {"content": k, "occurrences": v}
            for k, v in sorted(finding_contents.items(), key=lambda x: -x[1])
            if v >= 2
        ]

        # Generate per-company style guide from memo edits
        self._generate_company_style_guide()

        # Write consolidated report
        consolidated_path = self.base_dir / "consolidated.json"
        with open(consolidated_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(
            "CompanyMind[%s/%s]: consolidation complete. %d correction themes, %d recurring findings.",
            self.company, self.product,
            len(report["correction_themes"]),
            len(report["recurring_findings"]),
        )
        return report

    def _generate_company_style_guide(self) -> None:
        """Auto-generate a per-company style guide from memo edits and corrections."""
        memo_edits = self._read_entries("memo_edits")
        corrections = self._read_entries("corrections")

        if not memo_edits and not corrections:
            return

        lines = [
            f"# {self.company}/{self.product} -- Style Guide",
            "",
            f"*Auto-generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d')} "
            f"from {len(memo_edits)} memo edits and {len(corrections)} corrections.*",
            "",
        ]

        if corrections:
            lines.append("## Correction Patterns")
            # Group by correction category
            by_cat: Dict[str, List[MindEntry]] = {}
            for c in corrections:
                cat = c.metadata.get("correction_category", "general")
                by_cat.setdefault(cat, []).append(c)

            for cat, cat_entries in sorted(by_cat.items()):
                lines.append(f"### {cat.replace('_', ' ').title()}")
                for c in cat_entries[-3:]:  # Last 3 per category
                    reason = c.metadata.get("reason", "")
                    reason_note = f" -- {reason}" if reason else ""
                    lines.append(f"- {c.content}{reason_note}")
                lines.append("")

        if memo_edits:
            lines.append("## Memo Edit Patterns")
            # Summarize editing tendencies
            total_added = sum(e.metadata.get("words_added", 0) for e in memo_edits)
            total_removed = sum(e.metadata.get("words_removed", 0) for e in memo_edits)
            lines.append(f"- Across {len(memo_edits)} edits: +{total_added} words added, -{total_removed} words removed")

            # Show which sections get edited most
            section_counts: Dict[str, int] = {}
            for e in memo_edits:
                sec = e.metadata.get("section_key", "unknown")
                section_counts[sec] = section_counts.get(sec, 0) + 1
            if section_counts:
                lines.append("- Most-edited sections:")
                for sec, count in sorted(section_counts.items(), key=lambda x: -x[1])[:5]:
                    lines.append(f"  - {sec}: {count} edits")
            lines.append("")

        guide_path = self.base_dir / "style_guide.md"
        guide_path.write_text("\n".join(lines), encoding="utf-8")

    # ── Internal scoring ───────────────────────────────────────────────

    def _score_entries(
        self, entries: List[MindEntry], task_type: str, section_key: Optional[str] = None
    ) -> List[tuple]:
        """Score entries by relevance for the given task and section.

        Scoring factors:
        - Recency: newer entries score higher
        - Task relevance: entries from categories matching task_type score higher
        - Section match: entries referencing the current section score higher
        - High-confidence findings score higher

        Returns:
            List of (entry, score) tuples.
        """
        relevant_categories = set(_TASK_RELEVANCE.get(task_type, _TASK_RELEVANCE["default"]))
        now = datetime.now(timezone.utc)

        scored = []
        for entry in entries:
            score = 0.0

            # Recency: entries from the last 7 days get full score, decaying over 60 days
            try:
                ts = datetime.fromisoformat(entry.timestamp.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                age_days = (now - ts).total_seconds() / 86400
                recency_score = max(0.0, 1.0 - (age_days / 60.0))
            except (ValueError, TypeError):
                recency_score = 0.5

            score += recency_score * 3.0

            # Category relevance
            if entry.category in relevant_categories:
                score += 5.0

            # Section match (for memo edits and corrections)
            if section_key:
                entry_section = entry.metadata.get("section_key", "")
                correction_cat = entry.metadata.get("correction_category", "")
                if section_key.lower() in entry_section.lower() or section_key.lower() in correction_cat.lower():
                    score += 4.0
                # Also check if the content mentions the section
                if section_key.lower() in entry.content.lower():
                    score += 2.0

            # High-confidence findings get a boost
            if entry.category == "findings" and entry.metadata.get("confidence") == "high":
                score += 3.0

            # IC feedback always gets a boost (IC concerns are important)
            if entry.category == "ic_feedback":
                score += 2.0

            scored.append((entry, score))

        return scored

    def _format_for_prompt(self, entries: List[MindEntry], header: str) -> str:
        """Format selected entries as a prompt context block.

        Args:
            entries: The selected entries to format.
            header: Section header for the context block.

        Returns:
            Formatted string ready for inclusion in an AI prompt.
        """
        if not entries:
            return ""

        lines = [f"## {header}", ""]

        # Group by category for readability
        by_category: Dict[str, List[MindEntry]] = {}
        for e in entries:
            by_category.setdefault(e.category, []).append(e)

        category_labels = {
            "corrections": "Past Corrections (apply these)",
            "memo_edits": "Memo Edit Patterns",
            "findings": "Key Research Findings",
            "ic_feedback": "IC Feedback & Concerns",
            "data_quality": "Known Data Quality Issues",
            "session_lessons": "Session Lessons",
        }

        for cat, cat_entries in by_category.items():
            label = category_labels.get(cat, cat.replace("_", " ").title())
            lines.append(f"### {label}")
            for e in cat_entries[:_MAX_ENTRIES_PER_CATEGORY]:
                # Add context-specific formatting
                if cat == "corrections":
                    reason = e.metadata.get("reason", "")
                    if reason:
                        lines.append(f"- {e.content} (reason: {reason})")
                    else:
                        lines.append(f"- {e.content}")
                elif cat == "data_quality":
                    tape = e.metadata.get("tape_or_doc", "")
                    if tape:
                        lines.append(f"- [{tape}] {e.content}")
                    else:
                        lines.append(f"- {e.content}")
                elif cat == "findings":
                    confidence = e.metadata.get("confidence", "")
                    if confidence:
                        lines.append(f"- [{confidence}] {e.content}")
                    else:
                        lines.append(f"- {e.content}")
                else:
                    lines.append(f"- {e.content}")
            lines.append("")

        return "\n".join(lines)
