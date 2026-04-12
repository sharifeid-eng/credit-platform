"""
Knowledge Base Decomposer — Breaks static files into queryable knowledge atoms.

Parses:
- tasks/lessons.md → KnowledgeNodes (type="rule", category="session_lesson")
- CLAUDE.md "Key Architectural Decisions" → KnowledgeNodes (type="entry", category="architectural_decision")

Each entry becomes a linked, searchable node in the knowledge graph.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.mind.schema import KnowledgeNode, make_node


def decompose_lessons(filepath: Path) -> List[KnowledgeNode]:
    """Parse tasks/lessons.md into KnowledgeNodes.

    Expects format:
        ## YYYY-MM-DD — Title
        **Discovery:** ...
        **Rule:** ...
        **Reasoning:** ... (optional)

    Returns:
        List of KnowledgeNodes with category="session_lesson".
    """
    if not filepath.exists():
        return []

    text = filepath.read_text(encoding="utf-8")
    nodes = []

    # Split by ## headers (date-stamped entries)
    sections = re.split(r'^## ', text, flags=re.MULTILINE)

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # Parse header line
        lines = section.split("\n", 1)
        header = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""

        if not body:
            continue

        # Extract date from header
        date_match = re.match(r'(\d{4}-\d{2}-\d{2})', header)
        date_str = date_match.group(1) if date_match else ""
        title = header

        # Extract Discovery and Rule
        discovery = ""
        rule = ""
        reasoning = ""

        disc_match = re.search(r'\*\*Discovery:\*\*\s*(.+?)(?=\*\*|$)', body, re.DOTALL)
        if disc_match:
            discovery = disc_match.group(1).strip()

        rule_match = re.search(r'\*\*Rule:\*\*\s*(.+?)(?=\*\*|$)', body, re.DOTALL)
        if rule_match:
            rule = rule_match.group(1).strip()

        reason_match = re.search(r'\*\*Reasoning:\*\*\s*(.+?)(?=\*\*|$)', body, re.DOTALL)
        if reason_match:
            reasoning = reason_match.group(1).strip()

        # If we couldn't parse structured fields, use the whole body
        content = rule if rule else body[:500]

        # Generate stable ID from content hash (so re-decomposition doesn't create dupes)
        stable_id = f"lesson_{hashlib.md5(content.encode()).hexdigest()[:12]}"

        # Detect topic tags from content
        tags = _extract_tags(content + " " + discovery)

        node = KnowledgeNode(
            id=stable_id,
            timestamp=f"{date_str}T00:00:00Z" if date_str else datetime.now(timezone.utc).isoformat(),
            category="session_lesson",
            content=content,
            metadata={
                "title": title,
                "discovery": discovery[:300],
                "rule": rule[:300],
                "reasoning": reasoning[:300],
                "date": date_str,
                "tags": tags,
                "source_file": str(filepath),
            },
            node_type="rule",
        )
        nodes.append(node)

    return nodes


def decompose_decisions(filepath: Path, section_header: str = "Key Architectural Decisions") -> List[KnowledgeNode]:
    """Parse CLAUDE.md architectural decisions into KnowledgeNodes.

    Looks for bullet points under the specified section header,
    where each bullet describes an architectural decision.

    Returns:
        List of KnowledgeNodes with category="architectural_decision".
    """
    if not filepath.exists():
        return []

    text = filepath.read_text(encoding="utf-8")
    nodes = []

    # Find the section
    pattern = rf'^-\s+\*\*(.+?)\*\*\s*—\s*(.+?)$'
    matches = re.finditer(pattern, text, re.MULTILINE)

    for match in matches:
        key = match.group(1).strip()
        description = match.group(2).strip()

        if len(description) < 10:
            continue

        stable_id = f"decision_{hashlib.md5(key.encode()).hexdigest()[:12]}"
        tags = _extract_tags(key + " " + description)

        node = KnowledgeNode(
            id=stable_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            category="architectural_decision",
            content=f"{key}: {description}",
            metadata={
                "key": key,
                "description": description[:500],
                "tags": tags,
                "source_file": str(filepath),
            },
            node_type="entry",
        )
        nodes.append(node)

    return nodes


def _extract_tags(text: str) -> List[str]:
    """Extract topic tags from text for linking."""
    tags = set()

    # Module/component names
    for module in re.findall(r'`(\w+(?:\.\w+)*)`', text):
        if len(module) > 2:
            tags.add(module.lower())

    # Common topic keywords
    topic_map = {
        "cache": "caching", "caching": "caching",
        "par": "par", "par30": "par", "par60": "par",
        "dso": "dso", "dtfc": "dtfc",
        "mind": "mind", "thesis": "thesis",
        "covenant": "covenants", "covenants": "covenants",
        "collection": "collections", "collections": "collections",
        "denial": "denials", "denials": "denials",
        "migration": "migration", "schema": "schema",
        "margin": "margins", "margins": "margins",
        "database": "database", "db": "database",
        "api": "api", "endpoint": "api",
        "ai": "ai", "claude": "ai",
        "frontend": "frontend", "react": "frontend",
        "test": "testing", "tests": "testing",
    }

    for word in text.lower().split():
        clean = re.sub(r'[^a-z0-9]', '', word)
        if clean in topic_map:
            tags.add(topic_map[clean])

    return sorted(tags)
