"""
Knowledge Base Query — Unified search across all knowledge stores.

Searches:
- Mind entries (master + company)
- Decomposed lessons
- Decomposed architectural decisions
- Entity nodes from compilation

Supports filters: category, company, date_range, node_type, tags.
Ranking: text relevance + graph connectivity + recency.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.mind.schema import KnowledgeNode

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class SearchResult:
    """A single search result."""

    node: KnowledgeNode
    score: float
    match_context: str = ""  # why this matched
    source: str = ""         # "mind" | "lesson" | "decision" | "entity"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.node.id,
            "content": self.node.content[:300],
            "category": self.node.category,
            "node_type": self.node.node_type,
            "timestamp": self.node.timestamp,
            "score": round(self.score, 2),
            "match_context": self.match_context,
            "source": self.source,
            "metadata": {
                k: v for k, v in self.node.metadata.items()
                if k not in ("_graph",)
            },
        }


class KnowledgeBaseQuery:
    """Unified knowledge base search engine."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or (_PROJECT_ROOT / "data")
        self._lessons_cache: Optional[List[KnowledgeNode]] = None
        self._decisions_cache: Optional[List[KnowledgeNode]] = None

    def search(
        self,
        query: str,
        categories: Optional[List[str]] = None,
        company: Optional[str] = None,
        node_types: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        max_results: int = 20,
    ) -> List[SearchResult]:
        """Search across all knowledge stores.

        Args:
            query: Search text (keywords).
            categories: Filter by category.
            company: Filter by company.
            node_types: Filter by node type.
            tags: Filter by tags (from metadata).
            max_results: Maximum results to return.

        Returns:
            List of SearchResults sorted by relevance.
        """
        all_results: List[SearchResult] = []
        query_words = set(query.lower().split()) if query else set()

        # 1. Search mind entries
        all_results.extend(self._search_mind_entries(query_words, company))

        # 2. Search decomposed lessons
        all_results.extend(self._search_lessons(query_words))

        # 3. Search decomposed decisions
        all_results.extend(self._search_decisions(query_words))

        # 4. Search entity nodes
        all_results.extend(self._search_entities(query_words, company))

        # Apply filters
        if categories:
            all_results = [r for r in all_results if r.node.category in categories]
        if node_types:
            all_results = [r for r in all_results if r.node.node_type in node_types]
        if tags:
            tag_set = set(tags)
            all_results = [
                r for r in all_results
                if tag_set & set(r.node.metadata.get("tags", []))
            ]

        # Sort by score
        all_results.sort(key=lambda r: r.score, reverse=True)
        return all_results[:max_results]

    def _search_mind_entries(
        self, query_words: set, company: Optional[str]
    ) -> List[SearchResult]:
        """Search mind JSONL files."""
        import json
        from core.mind.schema import upgrade_entry

        results = []
        search_dirs = []

        # Master mind
        master_dir = self.data_dir / "_master_mind"
        if master_dir.exists():
            search_dirs.append(("master", master_dir))

        # Company minds
        if company:
            for prod_dir in (self.data_dir / company).iterdir() if (self.data_dir / company).exists() else []:
                mind_dir = prod_dir / "mind"
                if mind_dir.exists():
                    search_dirs.append((f"{company}/{prod_dir.name}", mind_dir))
        else:
            for co_dir in self.data_dir.iterdir():
                if not co_dir.is_dir() or co_dir.name.startswith("_"):
                    continue
                for prod_dir in co_dir.iterdir():
                    mind_dir = prod_dir / "mind"
                    if mind_dir.exists():
                        search_dirs.append((f"{co_dir.name}/{prod_dir.name}", mind_dir))

        for source_label, mind_dir in search_dirs:
            for jsonl_file in mind_dir.glob("*.jsonl"):
                if jsonl_file.name == "compilation_log.jsonl":
                    continue
                if jsonl_file.name == "thesis_log.jsonl":
                    continue
                try:
                    with open(jsonl_file, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                d = json.loads(line)
                                upgrade_entry(d)
                                node = KnowledgeNode.from_dict(d)
                                score = self._score_node(node, query_words)
                                if score > 0:
                                    results.append(SearchResult(
                                        node=node,
                                        score=score,
                                        source=f"mind:{source_label}",
                                    ))
                            except (json.JSONDecodeError, KeyError, ValueError):
                                continue
                except OSError:
                    continue

        return results

    def _search_lessons(self, query_words: set) -> List[SearchResult]:
        """Search decomposed lessons."""
        if self._lessons_cache is None:
            from core.mind.kb_decomposer import decompose_lessons
            lessons_path = _PROJECT_ROOT / "tasks" / "lessons.md"
            self._lessons_cache = decompose_lessons(lessons_path)

        results = []
        for node in self._lessons_cache:
            score = self._score_node(node, query_words)
            if score > 0:
                results.append(SearchResult(
                    node=node,
                    score=score,
                    source="lesson",
                ))
        return results

    def _search_decisions(self, query_words: set) -> List[SearchResult]:
        """Search decomposed architectural decisions."""
        if self._decisions_cache is None:
            from core.mind.kb_decomposer import decompose_decisions
            claude_md = _PROJECT_ROOT / "CLAUDE.md"
            self._decisions_cache = decompose_decisions(claude_md)

        results = []
        for node in self._decisions_cache:
            score = self._score_node(node, query_words)
            if score > 0:
                results.append(SearchResult(
                    node=node,
                    score=score,
                    source="decision",
                ))
        return results

    def _search_entities(
        self, query_words: set, company: Optional[str]
    ) -> List[SearchResult]:
        """Search entity nodes from compilation."""
        import json
        from core.mind.schema import upgrade_entry

        results = []
        search_dirs = []

        if company:
            co_dir = self.data_dir / company
            if co_dir.exists():
                for prod_dir in co_dir.iterdir():
                    entity_path = prod_dir / "mind" / "entities.jsonl"
                    if entity_path.exists():
                        search_dirs.append((f"{company}/{prod_dir.name}", entity_path))
        else:
            for co_dir in self.data_dir.iterdir():
                if not co_dir.is_dir() or co_dir.name.startswith("_"):
                    continue
                for prod_dir in co_dir.iterdir():
                    entity_path = prod_dir / "mind" / "entities.jsonl"
                    if entity_path.exists():
                        search_dirs.append((f"{co_dir.name}/{prod_dir.name}", entity_path))

        for source_label, entity_path in search_dirs:
            try:
                with open(entity_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            d = json.loads(line)
                            upgrade_entry(d)
                            node = KnowledgeNode.from_dict(d)
                            score = self._score_node(node, query_words)
                            if score > 0:
                                results.append(SearchResult(
                                    node=node,
                                    score=score,
                                    source=f"entity:{source_label}",
                                ))
                        except (json.JSONDecodeError, KeyError, ValueError):
                            continue
            except OSError:
                continue

        return results

    def _score_node(self, node: KnowledgeNode, query_words: set) -> float:
        """Score a node against query words."""
        if not query_words:
            return 1.0  # no query = return everything with base score

        score = 0.0

        # Content match
        content_words = set(node.content.lower().split())
        overlap = len(query_words & content_words)
        score += overlap * 3.0

        # Metadata match (tags, key, title)
        meta_text = " ".join(str(v) for v in node.metadata.values() if isinstance(v, str))
        meta_words = set(meta_text.lower().split())
        meta_overlap = len(query_words & meta_words)
        score += meta_overlap * 2.0

        # Tag match
        tags = set(node.metadata.get("tags", []))
        tag_overlap = len(query_words & tags)
        score += tag_overlap * 4.0

        # Recency bonus (slight)
        try:
            node_dt = datetime.fromisoformat(node.timestamp.replace("Z", "+00:00"))
            days_old = (datetime.now(timezone.utc) - node_dt).days
            score += max(0, 1.0 - (days_old / 365))
        except (ValueError, TypeError):
            pass

        return score
