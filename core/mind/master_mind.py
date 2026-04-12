"""
Master Mind — Fund-level institutional memory for ACP.

Captures analytical preferences, cross-company patterns, framework evolution,
IC norms, and writing style that apply across ALL companies and sessions.

Storage: data/_master_mind/ (fund-level, not company-scoped)
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

# Project root is 3 levels up from this file: core/mind/master_mind.py -> project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_MASTER_DIR = _PROJECT_ROOT / "data" / "_master_mind"

# JSONL file names
_FILES = {
    "preferences": "preferences.jsonl",
    "cross_company": "cross_company.jsonl",
    "framework_evolution": "framework_evolution.jsonl",
    "ic_norms": "ic_norms.jsonl",
    "writing_style": "writing_style.jsonl",
}

# Task-type to category relevance mapping (which categories matter for which tasks)
_TASK_RELEVANCE: Dict[str, List[str]] = {
    "commentary": ["preferences", "writing_style", "ic_norms"],
    "executive_summary": ["preferences", "writing_style", "ic_norms", "cross_company"],
    "tab_insight": ["preferences", "writing_style"],
    "chat": ["preferences", "ic_norms"],
    "onboarding": ["cross_company", "framework_evolution", "ic_norms"],
    "research_report": ["preferences", "writing_style", "ic_norms", "cross_company"],
    "memo": ["preferences", "writing_style", "ic_norms"],
    "framework": ["framework_evolution", "preferences"],
    "default": ["preferences", "ic_norms"],
}

# Max entries to include in a prompt context per category
_MAX_ENTRIES_PER_CATEGORY = 5
_MAX_TOTAL_ENTRIES = 20


@dataclass
class MindEntry:
    """A single entry in the mind knowledge base."""

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


class MasterMind:
    """Fund-level knowledge that applies across ALL companies and sessions.

    Captures:
    1. Analytical preferences -- how ACP writes memos, what IC expects
    2. Cross-company patterns -- patterns observed across multiple positions
    3. Framework evolution -- why rules were added, what triggered changes
    4. IC norms -- standard covenant thresholds, acceptable PAR ranges, red lines
    5. Writing style -- consolidated from all memo edits across all companies

    Storage: data/_master_mind/ (fund-level, not company-scoped)
    Format: Append-only JSONL files (one JSON object per line)
    """

    def __init__(self, base_dir: Optional[Path] = None):
        """Initialize MasterMind.

        Args:
            base_dir: Override for the master mind directory.
                      Defaults to data/_master_mind/ relative to project root.
        """
        self.base_dir = Path(base_dir) if base_dir else _MASTER_DIR
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Create directory structure if it doesn't exist."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        (self.base_dir / "onboarding").mkdir(exist_ok=True)

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
        logger.debug("MasterMind: recorded %s entry %s", entry.category, entry.id[:8])

        # Publish event for downstream listeners
        try:
            from core.mind.event_bus import event_bus, Events
            event_bus.publish(Events.MIND_ENTRY_CREATED, {
                "scope": "master",
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
                    logger.warning("MasterMind: skipping malformed line %d in %s: %s", line_num, path.name, e)
        return entries

    # ── Recording methods ──────────────────────────────────────────────

    def record_analytical_preference(self, preference: str, source: str = "") -> MindEntry:
        """Record a universal analytical rule or preference.

        Args:
            preference: The analytical preference (e.g., "Always show lifetime PAR as headline")
            source: Where this came from (e.g., "IC meeting 2026-03", "analyst correction")

        Returns:
            The created MindEntry.
        """
        entry = _make_entry("preferences", preference, {"source": source})
        self._append_entry(entry)
        return entry

    def record_cross_company_pattern(
        self, pattern: str, companies: List[str], evidence: str = ""
    ) -> MindEntry:
        """Record a pattern observed across multiple portfolio companies.

        Args:
            pattern: The cross-company observation
            companies: List of company names where this was observed
            evidence: Supporting data or references

        Returns:
            The created MindEntry.
        """
        entry = _make_entry(
            "cross_company",
            pattern,
            {"companies": companies, "evidence": evidence},
        )
        self._append_entry(entry)
        return entry

    def record_framework_evolution(
        self, change: str, reason: str, date: Optional[str] = None
    ) -> MindEntry:
        """Record why a Framework rule was added or changed.

        Args:
            change: What changed in the framework
            reason: Why it changed (the triggering event)
            date: When it changed (defaults to now)

        Returns:
            The created MindEntry.
        """
        entry = _make_entry(
            "framework_evolution",
            change,
            {"reason": reason, "date": date or datetime.now(timezone.utc).strftime("%Y-%m-%d")},
        )
        self._append_entry(entry)
        return entry

    def record_ic_norm(self, norm: str, category: str = "general") -> MindEntry:
        """Record a standard IC expectation or threshold.

        Args:
            norm: The IC norm (e.g., "PAR 30+ above 5% is a red flag")
            category: Sub-category (e.g., "covenants", "thresholds", "reporting", "general")

        Returns:
            The created MindEntry.
        """
        entry = _make_entry("ic_norms", norm, {"norm_category": category})
        self._append_entry(entry)
        return entry

    def record_writing_style(self, rule: str, source: str = "") -> MindEntry:
        """Record a writing style preference.

        Args:
            rule: The style rule (e.g., "Use basis points not percentages for small spreads")
            source: Where this was observed (e.g., "memo edit", "analyst feedback")

        Returns:
            The created MindEntry.
        """
        entry = _make_entry("writing_style", rule, {"source": source})
        self._append_entry(entry)
        return entry

    def promote_from_company(self, company: str, entry: MindEntry) -> MindEntry:
        """Promote a company-level lesson to fund-level knowledge.

        Creates a new master-level entry referencing the original company entry.

        Args:
            company: The company the entry originated from
            entry: The original CompanyMind entry to promote

        Returns:
            The new fund-level MindEntry.
        """
        # Map company-mind categories to master-mind categories
        category_map = {
            "corrections": "preferences",
            "memo_edits": "writing_style",
            "findings": "cross_company",
            "ic_feedback": "ic_norms",
            "data_quality": "preferences",
            "session_lessons": "preferences",
        }
        master_category = category_map.get(entry.category, "preferences")

        promoted_entry = _make_entry(
            master_category,
            f"[Promoted from {company}] {entry.content}",
            {
                "promoted_from": company,
                "original_id": entry.id,
                "original_category": entry.category,
                "original_timestamp": entry.timestamp,
            },
        )
        self._append_entry(promoted_entry)
        return promoted_entry

    # ── Query methods ──────────────────────────────────────────────────

    def get_context_for_prompt(
        self, task_type: str, company: Optional[str] = None
    ) -> MindContext:
        """Pull relevant fund-level context for an AI prompt.

        Selects entries based on task_type relevance, recency, and consolidation.

        Args:
            task_type: The type of AI task (commentary, executive_summary, chat, etc.)
            company: Optional company name to boost cross-company relevance

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
        scored = self._score_entries(all_entries, task_type, company)

        # Take top entries up to limit
        scored.sort(key=lambda x: x[1], reverse=True)
        selected = [e for e, _ in scored[:_MAX_TOTAL_ENTRIES]]

        # Build formatted string
        formatted = self._format_for_prompt(selected, "Fund-Level Knowledge")

        categories_included = list(set(e.category for e in selected))

        return MindContext(
            entries=selected,
            formatted=formatted,
            entry_count=len(selected),
            categories_included=categories_included,
        )

    def get_peer_context(self, company: str, metric: str) -> str:
        """Get how a company compares to peers on a specific metric.

        Args:
            company: The company being analyzed
            metric: The metric to compare (e.g., "collection_rate", "par_30")

        Returns:
            Formatted context string about peer comparison.
        """
        entries = self._read_entries("cross_company")
        relevant = [
            e for e in entries
            if company.lower() in str(e.metadata.get("companies", [])).lower()
            or metric.lower() in e.content.lower()
        ]

        if not relevant:
            return ""

        lines = [f"## Peer Context for {company} ({metric})"]
        for e in relevant[-5:]:  # Last 5 relevant entries
            companies = e.metadata.get("companies", [])
            lines.append(f"- {e.content} (companies: {', '.join(companies)})")

        return "\n".join(lines)

    def get_universal_style_guide(self) -> str:
        """Return consolidated writing guide from all style entries.

        Reads the auto-generated style_guide.md if it exists,
        otherwise builds from raw entries.

        Returns:
            Markdown-formatted style guide string.
        """
        guide_path = self.base_dir / "style_guide.md"
        if guide_path.exists():
            return guide_path.read_text(encoding="utf-8")

        # Build from raw entries
        entries = self._read_entries("writing_style")
        if not entries:
            return "No writing style preferences recorded yet."

        lines = ["# ACP Writing Style Guide", ""]
        for e in entries:
            source = e.metadata.get("source", "")
            source_note = f" *(from: {source})*" if source else ""
            lines.append(f"- {e.content}{source_note}")

        return "\n".join(lines)

    def get_onboarding_brief(self, asset_class: str) -> str:
        """Get accumulated lessons for onboarding a similar company.

        Args:
            asset_class: The asset class (e.g., "bnpl", "factoring", "rnpl")

        Returns:
            Markdown-formatted onboarding brief.
        """
        # Check for pre-generated brief
        brief_path = self.base_dir / "onboarding" / f"{asset_class.lower()}.md"
        if brief_path.exists():
            return brief_path.read_text(encoding="utf-8")

        # Build from relevant entries
        lines = [f"# Onboarding Brief: {asset_class.upper()}", ""]

        # Pull framework evolution entries related to this asset class
        fw_entries = self._read_entries("framework_evolution")
        relevant_fw = [e for e in fw_entries if asset_class.lower() in e.content.lower()]
        if relevant_fw:
            lines.append("## Framework Lessons")
            for e in relevant_fw[-5:]:
                lines.append(f"- {e.content} (reason: {e.metadata.get('reason', 'N/A')})")
            lines.append("")

        # Pull cross-company patterns
        cc_entries = self._read_entries("cross_company")
        relevant_cc = [
            e for e in cc_entries
            if asset_class.lower() in e.content.lower()
            or asset_class.lower() in str(e.metadata.get("evidence", "")).lower()
        ]
        if relevant_cc:
            lines.append("## Cross-Company Patterns")
            for e in relevant_cc[-5:]:
                lines.append(f"- {e.content}")
            lines.append("")

        # Pull IC norms
        ic_entries = self._read_entries("ic_norms")
        if ic_entries:
            lines.append("## IC Norms to Remember")
            for e in ic_entries[-5:]:
                lines.append(f"- {e.content}")

        if len(lines) <= 2:
            return f"No onboarding lessons recorded for {asset_class} yet."

        return "\n".join(lines)

    def get_codification_candidates(self) -> List[Dict[str, Any]]:
        """Identify entries mature enough to codify into Framework or Methodology.

        Looks for patterns that appear 3+ times or have been promoted from
        multiple companies.

        Returns:
            List of candidate entries with occurrence counts and sources.
        """
        candidates = []

        # Check for repeated preferences
        prefs = self._read_entries("preferences")
        content_counts: Dict[str, List[MindEntry]] = {}
        for e in prefs:
            # Normalize content for grouping (lowercase, strip)
            key = e.content.lower().strip()
            content_counts.setdefault(key, []).append(e)

        for key, entries in content_counts.items():
            if len(entries) >= 3:
                candidates.append({
                    "content": entries[0].content,
                    "category": "preferences",
                    "occurrences": len(entries),
                    "sources": [e.metadata.get("source", "") for e in entries],
                    "first_seen": entries[0].timestamp,
                    "last_seen": entries[-1].timestamp,
                })

        # Check for cross-company patterns with 3+ companies
        cc_entries = self._read_entries("cross_company")
        for e in cc_entries:
            companies = e.metadata.get("companies", [])
            if len(companies) >= 3:
                candidates.append({
                    "content": e.content,
                    "category": "cross_company",
                    "occurrences": len(companies),
                    "sources": companies,
                    "first_seen": e.timestamp,
                    "last_seen": e.timestamp,
                })

        return candidates

    def load_framework_context(self) -> str:
        """Read FRAMEWORK_INDEX.md and extract the Core Principles section.

        Returns a concise ~10-15 line context block for AI prompts.

        Returns:
            Formatted core principles string, or empty string if file not found.
        """
        index_path = _PROJECT_ROOT / "core" / "FRAMEWORK_INDEX.md"
        if not index_path.exists():
            logger.warning("MasterMind: FRAMEWORK_INDEX.md not found at %s", index_path)
            return ""

        text = index_path.read_text(encoding="utf-8")

        # Extract "Core Principles" section
        lines = text.split("\n")
        in_section = False
        result_lines = ["## ACP Analysis Framework — Core Principles"]

        for line in lines:
            if "## Core Principles" in line:
                in_section = True
                continue
            if in_section:
                # Stop at the next section header
                if line.startswith("## ") or line.startswith("---"):
                    break
                stripped = line.strip()
                if stripped:
                    result_lines.append(stripped)

        if len(result_lines) <= 1:
            # Fallback: return a minimal set of principles
            return (
                "## ACP Analysis Framework -- Core Principles\n"
                "1. Graceful degradation -- hide when unavailable, never estimate without labeling\n"
                "2. Denominator discipline -- every rate declares total/active/eligible\n"
                "3. Completed-only margins -- never include active deals in margin calculations\n"
                "4. Separation principle -- loss portfolio isolated from performance metrics\n"
                "5. Confidence grading -- A (observed), B (inferred), C (derived)\n"
                "6. Three clocks -- Origination Age, Contractual DPD, Operational Delay\n"
                "7. Asset-class-centric -- methodology organized by asset class, not company name"
            )

        return "\n".join(result_lines)

    def load_methodology_context(self, company: str, product: str) -> str:
        """Load methodology for a company/product and extract key formulas and caveats.

        Lazy-imports from core.metric_registry and core.config to avoid circular deps.

        Args:
            company: Company name (e.g., "klaim")
            product: Product name (e.g., "UAE_healthcare")

        Returns:
            Concise methodology context string (~10-15 lines).
        """
        try:
            from core.config import load_config
            from core.metric_registry import get_methodology
        except ImportError:
            logger.warning("MasterMind: could not import metric_registry or config")
            return ""

        try:
            config = load_config(company, product)
            analysis_type = config.get("analysis_type", company)
        except Exception:
            analysis_type = company

        try:
            methodology = get_methodology(analysis_type)
        except Exception as e:
            logger.warning("MasterMind: get_methodology(%s) failed: %s", analysis_type, e)
            return ""

        sections = methodology.get("sections", [])
        if not sections:
            return ""

        lines = [f"## Methodology Summary ({analysis_type})"]

        # Extract key formulas from each section (limit to ~15 lines total)
        line_budget = 14
        for sec in sections:
            if line_budget <= 0:
                break
            title = sec.get("title", sec.get("id", "Unknown"))
            level = sec.get("level")
            level_tag = f" [L{level}]" if level else ""

            # Pull first metric formula if available
            metrics = sec.get("metrics", [])
            if metrics:
                m = metrics[0]
                formula = m.get("formula", "")
                name = m.get("name", title)
                if formula:
                    lines.append(f"- {name}{level_tag}: {formula}")
                    line_budget -= 1

            # Pull first note as a caveat
            notes = sec.get("notes", [])
            if notes and line_budget > 0:
                lines.append(f"  Caveat: {notes[0]}")
                line_budget -= 1

        return "\n".join(lines)

    # ── Consolidation ──────────────────────────────────────────────────

    def consolidate(self) -> Dict[str, Any]:
        """Periodic consolidation of entries into higher-order patterns.

        Groups similar entries, counts occurrences, and creates summary patterns.
        Also scans all company mind directories to find cross-company patterns.

        Returns:
            Consolidation report with counts and new patterns found.
        """
        report = {"timestamp": datetime.now(timezone.utc).isoformat(), "categories": {}, "new_patterns": []}

        for category in _FILES:
            entries = self._read_entries(category)
            report["categories"][category] = {
                "total_entries": len(entries),
                "unique_entries": len(set(e.content.lower().strip() for e in entries)),
            }

        # Scan company mind directories for cross-company patterns
        data_dir = _PROJECT_ROOT / "data"
        company_lessons: Dict[str, List[str]] = {}

        if data_dir.exists():
            for company_dir in data_dir.iterdir():
                if not company_dir.is_dir() or company_dir.name.startswith("_"):
                    continue
                for product_dir in company_dir.iterdir():
                    if not product_dir.is_dir():
                        continue
                    mind_dir = product_dir / "mind"
                    if not mind_dir.exists():
                        continue
                    # Read session lessons
                    lessons_path = mind_dir / "session_lessons.jsonl"
                    if lessons_path.exists():
                        with open(lessons_path, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if not line:
                                    continue
                                try:
                                    d = json.loads(line)
                                    content = d.get("content", "").lower().strip()
                                    company_lessons.setdefault(content, []).append(company_dir.name)
                                except (json.JSONDecodeError, KeyError):
                                    pass

        # Find lessons appearing in 2+ companies
        for content, companies in company_lessons.items():
            unique_companies = list(set(companies))
            if len(unique_companies) >= 2:
                report["new_patterns"].append({
                    "content": content,
                    "companies": unique_companies,
                    "occurrences": len(unique_companies),
                })

        # Write consolidated report
        consolidated_path = self.base_dir / "consolidated.json"
        with open(consolidated_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # Auto-generate style guide
        self._generate_style_guide()

        logger.info("MasterMind: consolidation complete. %d cross-company patterns found.", len(report["new_patterns"]))
        return report

    def _generate_style_guide(self) -> None:
        """Auto-generate style_guide.md from writing_style entries."""
        entries = self._read_entries("writing_style")
        if not entries:
            return

        lines = [
            "# ACP Writing Style Guide",
            "",
            f"*Auto-generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d')} "
            f"from {len(entries)} recorded preferences.*",
            "",
        ]

        # Group by source
        by_source: Dict[str, List[MindEntry]] = {}
        for e in entries:
            source = e.metadata.get("source", "general")
            by_source.setdefault(source, []).append(e)

        for source, source_entries in sorted(by_source.items()):
            lines.append(f"## From: {source}")
            for e in source_entries:
                lines.append(f"- {e.content}")
            lines.append("")

        guide_path = self.base_dir / "style_guide.md"
        guide_path.write_text("\n".join(lines), encoding="utf-8")

    # ── Internal scoring ───────────────────────────────────────────────

    def _score_entries(
        self, entries: List[MindEntry], task_type: str, company: Optional[str] = None
    ) -> List[tuple]:
        """Score entries by relevance for the given task and company.

        Scoring factors:
        - Recency: newer entries score higher
        - Task relevance: entries from categories matching task_type score higher
        - Company relevance: cross-company entries mentioning this company score higher

        Returns:
            List of (entry, score) tuples.
        """
        relevant_categories = set(_TASK_RELEVANCE.get(task_type, _TASK_RELEVANCE["default"]))
        now = datetime.now(timezone.utc)

        scored = []
        for entry in entries:
            score = 0.0

            # Recency: entries from the last 7 days get full score, decaying over 90 days
            try:
                ts = datetime.fromisoformat(entry.timestamp.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                age_days = (now - ts).total_seconds() / 86400
                recency_score = max(0.0, 1.0 - (age_days / 90.0))
            except (ValueError, TypeError):
                recency_score = 0.5

            score += recency_score * 3.0  # Weight recency at 3x

            # Category relevance
            if entry.category in relevant_categories:
                score += 5.0

            # Company relevance (for cross-company entries)
            if company and entry.category == "cross_company":
                companies = entry.metadata.get("companies", [])
                if company.lower() in [c.lower() for c in companies]:
                    score += 3.0

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
            "preferences": "Analytical Preferences",
            "cross_company": "Cross-Company Patterns",
            "framework_evolution": "Framework Evolution",
            "ic_norms": "IC Norms & Expectations",
            "writing_style": "Writing Style",
        }

        for cat, cat_entries in by_category.items():
            label = category_labels.get(cat, cat.replace("_", " ").title())
            lines.append(f"### {label}")
            for e in cat_entries[:_MAX_ENTRIES_PER_CATEGORY]:
                lines.append(f"- {e.content}")
            lines.append("")

        return "\n".join(lines)
