"""
Knowledge Node Schema — Extended mind entry model with typed relations.

Builds on the existing MindEntry dataclass by adding:
- Typed relations between nodes (supports, contradicts, supersedes, etc.)
- Source references (doc_ids, tape filenames, memo_ids)
- Staleness tracking (fresh → aging → stale → superseded)
- Node type classification (entry, rule, thesis_pillar, entity, pattern)

Backward compatible: old MindEntry JSONL entries are lazily upgraded on read
via upgrade_entry(). No batch migration needed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------
# Relation types — typed edges between knowledge nodes
# --------------------------------------------------------------------------

RELATION_TYPES = frozenset({
    "supports",       # evidence strengthening another node
    "contradicts",    # conflicting information
    "supersedes",     # newer version replaces older
    "relates_to",     # thematic connection
    "derived_from",   # auto-generated from another entry (e.g., rule from correction)
    "evidence_for",   # data point supporting a claim
})

# Node types
NODE_TYPES = frozenset({
    "entry",          # standard mind entry (legacy default)
    "rule",           # auto-generated learning rule from corrections
    "thesis_pillar",  # investment thesis component
    "entity",         # extracted entity (covenant, metric, counterparty)
    "pattern",        # cross-company detected pattern
})

# Staleness states
STALENESS_STATES = frozenset({
    "fresh",          # recently created or reinforced
    "aging",          # no supporting evidence for 30-60 days
    "stale",          # no supporting evidence for 60+ days
    "superseded",     # replaced by a newer node
})


@dataclass
class Relation:
    """A typed directional edge between two knowledge nodes."""

    target_id: str
    relation_type: str       # must be in RELATION_TYPES
    confidence: float = 1.0  # 0.0–1.0
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if self.relation_type not in RELATION_TYPES:
            raise ValueError(
                f"Invalid relation_type '{self.relation_type}'. "
                f"Must be one of: {sorted(RELATION_TYPES)}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "confidence": self.confidence,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> Relation:
        return cls(
            target_id=d["target_id"],
            relation_type=d["relation_type"],
            confidence=d.get("confidence", 1.0),
            created_at=d.get("created_at", ""),
        )


@dataclass
class KnowledgeNode:
    """Extended mind entry with relations, source tracking, and staleness.

    Superset of MindEntry. Old entries upgraded transparently via upgrade_entry().
    """

    # --- Core fields (same as MindEntry) ---
    id: str
    timestamp: str
    category: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    promoted: bool = False

    # --- New fields ---
    relations: List[Relation] = field(default_factory=list)
    source_refs: List[str] = field(default_factory=list)
    staleness: str = "fresh"
    superseded_by: Optional[str] = None
    node_type: str = "entry"

    def __post_init__(self):
        if self.node_type not in NODE_TYPES:
            raise ValueError(
                f"Invalid node_type '{self.node_type}'. "
                f"Must be one of: {sorted(NODE_TYPES)}"
            )
        if self.staleness not in STALENESS_STATES:
            raise ValueError(
                f"Invalid staleness '{self.staleness}'. "
                f"Must be one of: {sorted(STALENESS_STATES)}"
            )

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "id": self.id,
            "timestamp": self.timestamp,
            "category": self.category,
            "content": self.content,
            "metadata": self.metadata,
            "promoted": self.promoted,
            "relations": [r.to_dict() for r in self.relations],
            "source_refs": self.source_refs,
            "staleness": self.staleness,
            "superseded_by": self.superseded_by,
            "node_type": self.node_type,
        }
        return d

    def to_mind_entry_dict(self) -> Dict[str, Any]:
        """Export in legacy MindEntry format (for backward-compatible JSONL writing).

        New fields stored inside metadata["_graph"] so existing code ignores them
        but they survive round-trips through JSONL.
        """
        d = {
            "id": self.id,
            "timestamp": self.timestamp,
            "category": self.category,
            "content": self.content,
            "metadata": {**self.metadata},
            "promoted": self.promoted,
        }
        # Store graph fields in metadata sub-key for backward compat
        graph_meta = {}
        if self.relations:
            graph_meta["relations"] = [r.to_dict() for r in self.relations]
        if self.source_refs:
            graph_meta["source_refs"] = self.source_refs
        if self.staleness != "fresh":
            graph_meta["staleness"] = self.staleness
        if self.superseded_by:
            graph_meta["superseded_by"] = self.superseded_by
        if self.node_type != "entry":
            graph_meta["node_type"] = self.node_type
        if graph_meta:
            d["metadata"]["_graph"] = graph_meta
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> KnowledgeNode:
        """Create from a dict — handles both new and legacy MindEntry formats."""
        # Check for graph metadata stored in legacy format
        metadata = d.get("metadata", {})
        graph_meta = metadata.get("_graph", {})

        # Strip _graph from metadata copy to avoid nesting
        clean_metadata = {k: v for k, v in metadata.items() if k != "_graph"}

        # Parse relations from either top-level or graph_meta
        raw_relations = d.get("relations") or graph_meta.get("relations", [])
        relations = [Relation.from_dict(r) for r in raw_relations]

        return cls(
            id=d.get("id", str(uuid.uuid4())),
            timestamp=d.get("timestamp", datetime.now(timezone.utc).isoformat()),
            category=d.get("category", "unknown"),
            content=d.get("content", ""),
            metadata=clean_metadata,
            promoted=d.get("promoted", False),
            relations=relations,
            source_refs=d.get("source_refs") or graph_meta.get("source_refs", []),
            staleness=d.get("staleness") or graph_meta.get("staleness", "fresh"),
            superseded_by=d.get("superseded_by") or graph_meta.get("superseded_by"),
            node_type=d.get("node_type") or graph_meta.get("node_type", "entry"),
        )

    @property
    def is_superseded(self) -> bool:
        return self.superseded_by is not None

    @property
    def is_active(self) -> bool:
        return not self.is_superseded and self.staleness != "superseded"

    def add_relation(self, target_id: str, relation_type: str,
                     confidence: float = 1.0) -> Relation:
        """Add a relation to another node. Returns the created Relation."""
        rel = Relation(
            target_id=target_id,
            relation_type=relation_type,
            confidence=confidence,
        )
        self.relations.append(rel)
        return rel

    def get_relations(self, relation_type: Optional[str] = None) -> List[Relation]:
        """Get relations, optionally filtered by type."""
        if relation_type is None:
            return list(self.relations)
        return [r for r in self.relations if r.relation_type == relation_type]


# --------------------------------------------------------------------------
# Migration helper
# --------------------------------------------------------------------------

def upgrade_entry(d: Dict[str, Any]) -> Dict[str, Any]:
    """Upgrade a legacy MindEntry dict to KnowledgeNode-compatible format.

    Non-destructive: adds missing fields with defaults. Existing new-format
    dicts pass through unchanged.

    Called lazily by _read_entries() — no batch migration needed.
    """
    # Already has new fields? Pass through.
    if "node_type" in d or "_graph" in d.get("metadata", {}):
        return d

    # Add defaults for new fields
    d.setdefault("relations", [])
    d.setdefault("source_refs", [])
    d.setdefault("staleness", "fresh")
    d.setdefault("superseded_by", None)
    d.setdefault("node_type", "entry")
    return d


def make_node(
    category: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    node_type: str = "entry",
    source_refs: Optional[List[str]] = None,
    relations: Optional[List[Relation]] = None,
) -> KnowledgeNode:
    """Factory function to create a new KnowledgeNode with auto-generated id/timestamp."""
    return KnowledgeNode(
        id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        category=category,
        content=content,
        metadata=metadata or {},
        relations=relations or [],
        source_refs=source_refs or [],
        node_type=node_type,
    )
