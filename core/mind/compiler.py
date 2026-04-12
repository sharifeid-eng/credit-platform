"""
Knowledge Compiler — Incremental compilation of entities into knowledge nodes.

The heart of the "compounding" behavior: one new document or tape produces
10-15 knowledge node updates (create, supersede, reinforce, or contradict).

Workflow:
1. Entity extractor produces ExtractedEntity objects
2. Compiler searches existing nodes for matching keys
3. For each entity:
   - Value changed → create new node with 'supersedes' relation
   - Same value, new evidence → add 'evidence_for' relation
   - Contradicts existing → add 'contradicts' relation
   - New entity → create fresh node
4. Returns CompilationReport

Cross-reference: after compilation, scan for same entity types across documents
to detect discrepancies (e.g., different covenant thresholds in different agreements).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.mind.schema import KnowledgeNode, Relation, make_node
from core.mind.relation_index import RelationIndex
from core.mind.entity_extractor import ExtractedEntity

logger = logging.getLogger(__name__)


@dataclass
class CompilationDetail:
    """Detail about a single compilation action."""
    action: str          # "created" | "superseded" | "reinforced" | "contradicted"
    entity_key: str
    entity_type: str
    old_value: Any = None
    new_value: Any = None
    node_id: str = ""
    related_node_id: str = ""


@dataclass
class CompilationReport:
    """Report from a compilation run."""
    source_doc_id: str
    company: str
    product: str
    created: int = 0
    superseded: int = 0
    reinforced: int = 0
    contradictions: int = 0
    skipped: int = 0
    details: List[CompilationDetail] = field(default_factory=list)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    @property
    def total_actions(self) -> int:
        return self.created + self.superseded + self.reinforced + self.contradictions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_doc_id": self.source_doc_id,
            "company": self.company,
            "product": self.product,
            "created": self.created,
            "superseded": self.superseded,
            "reinforced": self.reinforced,
            "contradictions": self.contradictions,
            "skipped": self.skipped,
            "total_actions": self.total_actions,
            "details": [
                {"action": d.action, "key": d.entity_key, "type": d.entity_type,
                 "old": d.old_value, "new": d.new_value}
                for d in self.details
            ],
            "timestamp": self.timestamp,
        }


class KnowledgeCompiler:
    """Compiles extracted entities into the knowledge graph."""

    def __init__(self, mind_dir: Path):
        """Initialize compiler for a company/product mind directory.

        Args:
            mind_dir: Path to mind/ directory (e.g., data/klaim/UAE_healthcare/mind/)
        """
        self.mind_dir = Path(mind_dir)
        self.mind_dir.mkdir(parents=True, exist_ok=True)
        self.index = RelationIndex(self.mind_dir / "relations.json")

    def _load_entity_nodes(self) -> Dict[str, KnowledgeNode]:
        """Load all entity-type nodes, keyed by entity key."""
        from core.mind.schema import upgrade_entry
        nodes: Dict[str, KnowledgeNode] = {}
        # Entity nodes are stored in a dedicated JSONL file
        entity_path = self.mind_dir / "entities.jsonl"
        if not entity_path.exists():
            return nodes
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
                        if node.is_active:
                            # Key by entity_key from metadata
                            entity_key = node.metadata.get("entity_key", "")
                            if entity_key:
                                nodes[entity_key] = node
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
        except OSError:
            pass
        return nodes

    def _save_entity_node(self, node: KnowledgeNode) -> None:
        """Append an entity node to entities.jsonl."""
        entity_path = self.mind_dir / "entities.jsonl"
        d = node.to_mind_entry_dict()
        d["metadata"]["entity_key"] = node.metadata.get("entity_key", "")
        with open(entity_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    def _save_report(self, report: CompilationReport) -> None:
        """Append compilation report to log."""
        log_path = self.mind_dir / "compilation_log.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(report.to_dict(), ensure_ascii=False) + "\n")

    def compile(
        self,
        entities: List[ExtractedEntity],
        source_doc_id: str,
        company: str,
        product: str,
    ) -> CompilationReport:
        """Compile extracted entities into the knowledge graph.

        For each entity:
        - If no existing node with this key: create new
        - If existing node has same value: reinforce with evidence_for relation
        - If existing node has different value: supersede
        - If value contradicts (opposite direction): create contradicts relation

        Args:
            entities: List of extracted entities.
            source_doc_id: ID of the source document/tape.
            company: Company slug.
            product: Product slug.

        Returns:
            CompilationReport with action counts and details.
        """
        report = CompilationReport(
            source_doc_id=source_doc_id,
            company=company,
            product=product,
        )

        existing = self._load_entity_nodes()

        for entity in entities:
            if not entity.key:
                report.skipped += 1
                continue

            existing_node = existing.get(entity.key)

            if existing_node is None:
                # New entity — create
                node = self._create_entity_node(entity, source_doc_id)
                self._save_entity_node(node)
                existing[entity.key] = node
                report.created += 1
                report.details.append(CompilationDetail(
                    action="created",
                    entity_key=entity.key,
                    entity_type=entity.entity_type,
                    new_value=entity.value,
                    node_id=node.id,
                ))

            elif self._values_match(existing_node, entity):
                # Same value — reinforce with evidence_for
                self.index.add_relation(
                    source_id=source_doc_id,
                    target_id=existing_node.id,
                    relation_type="evidence_for",
                    confidence=_confidence_to_float(entity.confidence),
                )
                report.reinforced += 1
                report.details.append(CompilationDetail(
                    action="reinforced",
                    entity_key=entity.key,
                    entity_type=entity.entity_type,
                    old_value=existing_node.metadata.get("value"),
                    new_value=entity.value,
                    node_id=existing_node.id,
                ))

            else:
                # Value changed — supersede or contradict
                old_value = existing_node.metadata.get("value")
                if self._is_contradiction(existing_node, entity):
                    # Contradicts
                    new_node = self._create_entity_node(entity, source_doc_id)
                    self._save_entity_node(new_node)
                    self.index.add_relation(
                        source_id=new_node.id,
                        target_id=existing_node.id,
                        relation_type="contradicts",
                        confidence=_confidence_to_float(entity.confidence),
                    )
                    report.contradictions += 1
                    report.details.append(CompilationDetail(
                        action="contradicted",
                        entity_key=entity.key,
                        entity_type=entity.entity_type,
                        old_value=old_value,
                        new_value=entity.value,
                        node_id=new_node.id,
                        related_node_id=existing_node.id,
                    ))
                else:
                    # Supersede — create new, mark old
                    new_node = self._create_entity_node(entity, source_doc_id)
                    new_node.add_relation(
                        existing_node.id, "supersedes",
                        _confidence_to_float(entity.confidence),
                    )
                    self._save_entity_node(new_node)
                    self.index.add_relation(
                        source_id=new_node.id,
                        target_id=existing_node.id,
                        relation_type="supersedes",
                    )
                    # Mark old as superseded (in-memory; log tracks lineage)
                    existing[entity.key] = new_node
                    report.superseded += 1
                    report.details.append(CompilationDetail(
                        action="superseded",
                        entity_key=entity.key,
                        entity_type=entity.entity_type,
                        old_value=old_value,
                        new_value=entity.value,
                        node_id=new_node.id,
                        related_node_id=existing_node.id,
                    ))

        self._save_report(report)
        logger.info(
            "Compilation complete for %s/%s from %s: %d created, %d superseded, "
            "%d reinforced, %d contradictions",
            company, product, source_doc_id,
            report.created, report.superseded, report.reinforced, report.contradictions,
        )
        return report

    def cross_reference(self, company: str, product: str) -> List[Dict[str, Any]]:
        """Scan all entities for cross-document discrepancies.

        Finds cases where the same entity key appears with different values
        from different source documents.

        Returns:
            List of discrepancy dicts.
        """
        entity_path = self.mind_dir / "entities.jsonl"
        if not entity_path.exists():
            return []

        # Group by entity_key
        from collections import defaultdict
        from core.mind.schema import upgrade_entry

        by_key: Dict[str, List[Dict]] = defaultdict(list)
        try:
            with open(entity_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        upgrade_entry(d)
                        key = d.get("metadata", {}).get("entity_key", "")
                        if key:
                            by_key[key].append(d)
                    except (json.JSONDecodeError, KeyError):
                        continue
        except OSError:
            return []

        discrepancies = []
        for key, nodes in by_key.items():
            if len(nodes) < 2:
                continue
            values = set()
            for n in nodes:
                v = n.get("metadata", {}).get("value")
                if v is not None:
                    values.add(str(v))
            if len(values) > 1:
                discrepancies.append({
                    "entity_key": key,
                    "values": list(values),
                    "source_count": len(nodes),
                    "sources": [
                        n.get("metadata", {}).get("source_doc_id", "unknown")
                        for n in nodes
                    ],
                })

        return discrepancies

    def _create_entity_node(
        self, entity: ExtractedEntity, source_doc_id: str
    ) -> KnowledgeNode:
        """Create a KnowledgeNode from an extracted entity."""
        return make_node(
            category=entity.entity_type.lower(),
            content=f"{entity.key}: {entity.value} ({entity.context[:100]})",
            metadata={
                "entity_key": entity.key,
                "entity_type": entity.entity_type,
                "value": entity.value,
                "unit": entity.unit,
                "confidence": entity.confidence,
                "source_doc_id": source_doc_id,
                "section_heading": entity.section_heading,
            },
            node_type="entity",
            source_refs=[source_doc_id],
        )

    def _values_match(self, node: KnowledgeNode, entity: ExtractedEntity) -> bool:
        """Check if an existing node's value matches the new entity."""
        old_val = node.metadata.get("value")
        if old_val is None:
            return False
        try:
            return abs(float(old_val) - float(entity.value)) < 0.001
        except (ValueError, TypeError):
            return str(old_val) == str(entity.value)

    def _is_contradiction(self, node: KnowledgeNode, entity: ExtractedEntity) -> bool:
        """Determine if a value change represents a contradiction vs supersession.

        Contradictions are when values from the SAME time period differ.
        Supersessions are when values from DIFFERENT time periods differ (natural evolution).

        For now, use a simple heuristic: different source documents within the same
        entity type = potential contradiction. Same source updated = supersession.
        """
        old_source = node.metadata.get("source_doc_id", "")
        new_source = entity.source_doc_id

        # Different documents referencing the same metric = potential contradiction
        if old_source and new_source and old_source != new_source:
            # Check if they're both document-sourced (not tape-derived)
            if not old_source.endswith(".csv") and not new_source.endswith(".csv"):
                return True

        return False


def _confidence_to_float(grade: str) -> float:
    """Convert A/B/C confidence grade to float."""
    return {"A": 0.95, "B": 0.75, "C": 0.55}.get(grade, 0.75)
