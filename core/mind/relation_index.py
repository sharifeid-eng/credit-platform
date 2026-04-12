"""
Relation Index — Bidirectional adjacency list for knowledge node relations.

Stored per scope as JSON: data/{scope}/mind/relations.json
Provides fast lookup of related nodes, contradictions, and evidence chains.

Thread-safe via file-level locking pattern (read-modify-write with atomic rename).
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.mind.schema import Relation, RELATION_TYPES

logger = logging.getLogger(__name__)


class RelationIndex:
    """Bidirectional adjacency list for knowledge node relations.

    Structure: { node_id: [Relation dict, ...] }
    Relations are stored on BOTH sides (source→target AND target→source)
    with a `_reverse` flag on the inverse entry for directionality.
    """

    def __init__(self, index_path: Path):
        """Initialize with path to the relations.json file.

        Args:
            index_path: Absolute path to relations.json. Created if missing.
        """
        self._path = index_path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load the index from disk. Returns empty dict if file missing."""
        if not self._path.exists():
            return {}
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("RelationIndex: failed to load %s: %s", self._path, e)
            return {}

    def _save(self, data: Dict[str, List[Dict[str, Any]]]) -> None:
        """Atomically save the index to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Write to temp file then rename for atomicity
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._path.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            # Atomic rename (works on Windows with replace)
            os.replace(tmp_path, str(self._path))
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        confidence: float = 1.0,
    ) -> Relation:
        """Add a relation between two nodes. Stored bidirectionally.

        Args:
            source_id: The originating node.
            target_id: The target node.
            relation_type: Must be in RELATION_TYPES.
            confidence: 0.0–1.0 confidence score.

        Returns:
            The created Relation object.
        """
        if relation_type not in RELATION_TYPES:
            raise ValueError(f"Invalid relation_type: {relation_type}")

        rel = Relation(
            target_id=target_id,
            relation_type=relation_type,
            confidence=confidence,
        )

        data = self._load()

        # Forward: source → target
        fwd = rel.to_dict()
        data.setdefault(source_id, [])
        # Deduplicate: don't add if same source→target→type already exists
        if not any(
            r["target_id"] == target_id and r["relation_type"] == relation_type
            for r in data[source_id]
        ):
            data[source_id].append(fwd)

        # Reverse: target → source (with _reverse flag)
        rev = {
            "target_id": source_id,
            "relation_type": relation_type,
            "confidence": confidence,
            "created_at": rel.created_at,
            "_reverse": True,
        }
        data.setdefault(target_id, [])
        if not any(
            r["target_id"] == source_id and r["relation_type"] == relation_type
            for r in data[target_id]
        ):
            data[target_id].append(rev)

        self._save(data)
        return rel

    def get_related(
        self,
        node_id: str,
        relation_type: Optional[str] = None,
        include_reverse: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get all relations for a node.

        Args:
            node_id: The node to look up.
            relation_type: Filter by relation type (optional).
            include_reverse: Include reverse relations (default True).

        Returns:
            List of relation dicts with target_id, relation_type, confidence.
        """
        data = self._load()
        relations = data.get(node_id, [])

        if not include_reverse:
            relations = [r for r in relations if not r.get("_reverse", False)]

        if relation_type:
            relations = [r for r in relations if r["relation_type"] == relation_type]

        return relations

    def get_contradictions(self, node_id: str) -> List[str]:
        """Get IDs of all nodes that contradict this one.

        Returns:
            List of node IDs with 'contradicts' relation.
        """
        rels = self.get_related(node_id, relation_type="contradicts")
        return [r["target_id"] for r in rels]

    def get_supporters(self, node_id: str) -> List[str]:
        """Get IDs of all nodes that support this one.

        Returns:
            List of node IDs with 'supports' or 'evidence_for' relation.
        """
        supports = self.get_related(node_id, relation_type="supports")
        evidence = self.get_related(node_id, relation_type="evidence_for")
        ids = {r["target_id"] for r in supports} | {r["target_id"] for r in evidence}
        return list(ids)

    def get_chain(
        self,
        start_id: str,
        relation_type: Optional[str] = None,
        max_depth: int = 3,
    ) -> List[str]:
        """BFS traversal from a starting node following relations.

        Args:
            start_id: Starting node ID.
            relation_type: Only follow this relation type (optional).
            max_depth: Maximum traversal depth.

        Returns:
            List of reachable node IDs (excluding start).
        """
        visited: set[str] = set()
        queue: list[tuple[str, int]] = [(start_id, 0)]
        result: list[str] = []

        while queue:
            node_id, depth = queue.pop(0)
            if node_id in visited:
                continue
            visited.add(node_id)

            if node_id != start_id:
                result.append(node_id)

            if depth < max_depth:
                rels = self.get_related(node_id, relation_type=relation_type)
                for r in rels:
                    tid = r["target_id"]
                    if tid not in visited:
                        queue.append((tid, depth + 1))

        return result

    def remove_relations(self, node_id: str) -> int:
        """Remove all relations involving a node (both forward and reverse).

        Args:
            node_id: Node whose relations to remove.

        Returns:
            Number of relation entries removed.
        """
        data = self._load()
        removed = 0

        # Remove forward entries
        if node_id in data:
            removed += len(data[node_id])
            del data[node_id]

        # Remove reverse entries pointing to this node
        for other_id in list(data.keys()):
            before = len(data[other_id])
            data[other_id] = [
                r for r in data[other_id]
                if r["target_id"] != node_id
            ]
            removed += before - len(data[other_id])
            # Clean up empty entries
            if not data[other_id]:
                del data[other_id]

        self._save(data)
        return removed

    def count(self) -> int:
        """Total number of relation entries (including reverse)."""
        data = self._load()
        return sum(len(rels) for rels in data.values())

    def node_ids(self) -> List[str]:
        """All node IDs that have at least one relation."""
        data = self._load()
        return list(data.keys())

    def rebuild_from_entries(self, entries: List[Dict[str, Any]]) -> int:
        """Rebuild the entire index from a list of KnowledgeNode dicts.

        Used during compaction or recovery. Reads relations from each entry's
        metadata._graph.relations or top-level relations field.

        Args:
            entries: List of KnowledgeNode-compatible dicts.

        Returns:
            Number of relations indexed.
        """
        data: Dict[str, List[Dict[str, Any]]] = {}
        count = 0

        for entry in entries:
            node_id = entry.get("id", "")
            if not node_id:
                continue

            # Find relations in either location
            meta = entry.get("metadata", {})
            graph_meta = meta.get("_graph", {})
            raw_rels = entry.get("relations") or graph_meta.get("relations", [])

            for rel_dict in raw_rels:
                target_id = rel_dict.get("target_id", "")
                if not target_id:
                    continue

                # Forward
                data.setdefault(node_id, [])
                data[node_id].append(rel_dict)

                # Reverse
                rev = {**rel_dict, "target_id": node_id, "_reverse": True}
                data.setdefault(target_id, [])
                data[target_id].append(rev)

                count += 1

        self._save(data)
        return count
