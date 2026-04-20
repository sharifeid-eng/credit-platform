"""
Asset Class Mind — knowledge keyed by analysis_type.

Sits between Master Mind (fund-level) and Company Mind (per-company).
Every company with a given analysis_type shares the same Asset Class Mind;
Klaim and any future healthcare-receivables company both read
healthcare_receivables.jsonl.

Stored in data/_asset_class_mind/{analysis_type}.jsonl — one file per class,
JSONL format (one MindEntry per line, append-only).

Categories:
  - benchmarks        industry benchmark metrics (median PAR, loss rate, DSO)
  - typical_terms     typical facility/product terms (advance rate, tenor, rate)
  - external_research web-search findings about the asset class
  - sector_context    regulatory / macro / sector-news for this asset class
  - peer_comparison   direct competitor comparisons
  - methodology_note  class-specific analytical caveats (feeds back to Framework)

Reuses MindEntry from company_mind so downstream graph/compilation code
works unchanged.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.mind.company_mind import MindEntry, MindContext

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_BASE_DIR = _PROJECT_ROOT / "data" / "_asset_class_mind"

# Valid categories — keep tight, not a free-for-all
_VALID_CATEGORIES = {
    "benchmarks",
    "typical_terms",
    "external_research",
    "sector_context",
    "peer_comparison",
    "methodology_note",
}

# Task-type to category relevance — mirrors CompanyMind._TASK_RELEVANCE
_TASK_RELEVANCE: Dict[str, List[str]] = {
    "commentary":        ["benchmarks", "peer_comparison", "sector_context"],
    "executive_summary": ["benchmarks", "peer_comparison", "sector_context", "methodology_note"],
    "tab_insight":       ["benchmarks", "peer_comparison"],
    "chat":              ["benchmarks", "external_research", "sector_context", "peer_comparison"],
    "memo":              ["benchmarks", "peer_comparison", "sector_context", "external_research"],
    "research_report":   ["benchmarks", "peer_comparison", "sector_context", "external_research"],
    "onboarding":        ["typical_terms", "methodology_note"],
    "validation":        ["methodology_note", "benchmarks"],
    "default":           ["benchmarks", "peer_comparison", "sector_context"],
}

_MAX_ENTRIES_PER_CATEGORY = 4
_MAX_TOTAL_ENTRIES = 12


class AssetClassMind:
    """Per-asset-class institutional knowledge, shared across all companies of that class."""

    def __init__(self, analysis_type: str, base_dir: Optional[Path] = None):
        """
        Args:
            analysis_type: The asset class key (e.g. "healthcare_receivables",
                           "bnpl", "pos_lending", "rnpl", "sme_trade_credit",
                           "klaim", "silq", "ejari_summary", "tamara_summary",
                           "aajil"). Anything the platform uses in config.json
                           as analysis_type is a valid key.
            base_dir: Override storage root (primarily for testing).
        """
        if not analysis_type:
            raise ValueError("analysis_type is required")
        self.analysis_type = analysis_type
        self.base_dir = Path(base_dir) if base_dir else _BASE_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = self.base_dir / f"{analysis_type}.jsonl"

    # ── I/O primitives ───────────────────────────────────────────────────────

    def _load_all(self) -> List[MindEntry]:
        """Load all entries from disk, newest first."""
        if not self.file_path.exists():
            return []
        entries: List[MindEntry] = []
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(MindEntry.from_dict(json.loads(line)))
                    except (json.JSONDecodeError, KeyError):
                        continue
        except OSError as e:
            logger.warning("AssetClassMind._load_all failed for %s: %s", self.analysis_type, e)
            return []
        # Newest first
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries

    def _append(self, entry: MindEntry) -> None:
        """Append one entry to the JSONL file."""
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

    # ── Public API ───────────────────────────────────────────────────────────

    def record(
        self,
        category: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        source: str = "manual",
    ) -> MindEntry:
        """Record a new entry.

        Args:
            category: One of _VALID_CATEGORIES
            content: The knowledge content (plain text)
            metadata: Optional dict — for external_research, include
                      {"citations": [{"url": "...", "title": "...", "retrieved_at": "..."}]}
            source: Provenance marker. Common values: "manual", "web_search",
                    "promoted_from_company", "promoted_from_multiple".
        """
        if category not in _VALID_CATEGORIES:
            raise ValueError(
                f"Unknown category: {category}. Valid: {sorted(_VALID_CATEGORIES)}"
            )
        md = dict(metadata or {})
        md.setdefault("source", source)
        md.setdefault("analysis_type", self.analysis_type)

        entry = MindEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            category=category,
            content=content,
            metadata=md,
            promoted=False,
        )
        self._append(entry)
        return entry

    def list_entries(
        self,
        category: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[MindEntry]:
        """List entries, optionally filtered by category."""
        entries = self._load_all()
        if category:
            entries = [e for e in entries if e.category == category]
        if limit is not None:
            entries = entries[:limit]
        return entries

    def get_context_for_prompt(self, task_type: str) -> MindContext:
        """Assemble a MindContext for the given task type.

        Mirrors CompanyMind.get_context_for_prompt() contract so that
        build_mind_context() can treat Layer 2.5 the same way as L4.
        """
        relevant_cats = _TASK_RELEVANCE.get(task_type, _TASK_RELEVANCE["default"])
        all_entries = self._load_all()
        selected: List[MindEntry] = []
        categories_included: List[str] = []

        for cat in relevant_cats:
            cat_entries = [e for e in all_entries if e.category == cat]
            if not cat_entries:
                continue
            selected.extend(cat_entries[:_MAX_ENTRIES_PER_CATEGORY])
            categories_included.append(cat)
            if len(selected) >= _MAX_TOTAL_ENTRIES:
                break

        selected = selected[:_MAX_TOTAL_ENTRIES]

        if not selected:
            return MindContext(entries=[], formatted="", entry_count=0, categories_included=[])

        header = f"--- Asset Class Knowledge: {self.analysis_type} ({len(selected)} entries) ---"
        lines = [header]
        for e in selected:
            src = e.metadata.get("source", "manual")
            tag = f"[{e.category}·{src}]"
            lines.append(f"{tag} {e.content}")
        formatted = "\n".join(lines)

        return MindContext(
            entries=selected,
            formatted=formatted,
            entry_count=len(selected),
            categories_included=categories_included,
        )


def list_all_asset_classes(base_dir: Optional[Path] = None) -> List[str]:
    """Discover every asset class that has a non-empty JSONL file."""
    base = Path(base_dir) if base_dir else _BASE_DIR
    if not base.exists():
        return []
    return sorted(
        f.stem for f in base.glob("*.jsonl")
        if f.is_file() and f.stat().st_size > 0
    )


__all__ = ["AssetClassMind", "list_all_asset_classes"]
