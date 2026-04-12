"""
Tests for Phase 0: Intelligence System Foundation.

Tests the schema, relation index, and event bus that underpin
the entire knowledge graph and learning system.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from core.mind.schema import (
    KnowledgeNode,
    Relation,
    make_node,
    upgrade_entry,
    RELATION_TYPES,
    NODE_TYPES,
    STALENESS_STATES,
)
from core.mind.relation_index import RelationIndex
from core.mind.event_bus import EventBus, Events


# ═══════════════════════════════════════════════════════════════════
# Schema Tests
# ═══════════════════════════════════════════════════════════════════


class TestRelation:
    def test_create_valid_relation(self):
        r = Relation(target_id="abc", relation_type="supports")
        assert r.target_id == "abc"
        assert r.relation_type == "supports"
        assert r.confidence == 1.0
        assert r.created_at  # auto-populated

    def test_invalid_relation_type_raises(self):
        with pytest.raises(ValueError, match="Invalid relation_type"):
            Relation(target_id="abc", relation_type="invalid_type")

    def test_round_trip_dict(self):
        r = Relation(target_id="xyz", relation_type="contradicts", confidence=0.8)
        d = r.to_dict()
        r2 = Relation.from_dict(d)
        assert r2.target_id == r.target_id
        assert r2.relation_type == r.relation_type
        assert r2.confidence == r.confidence


class TestKnowledgeNode:
    def test_create_basic_node(self):
        node = make_node("preferences", "Always show PAR as headline")
        assert node.id
        assert node.category == "preferences"
        assert node.content == "Always show PAR as headline"
        assert node.node_type == "entry"
        assert node.staleness == "fresh"
        assert node.relations == []
        assert node.source_refs == []

    def test_create_with_relations(self):
        node = make_node(
            "findings",
            "PAR30 increased",
            node_type="entity",
            source_refs=["tape_2026-03.csv"],
            relations=[Relation(target_id="old-node", relation_type="supersedes")],
        )
        assert node.node_type == "entity"
        assert len(node.relations) == 1
        assert node.relations[0].relation_type == "supersedes"
        assert node.source_refs == ["tape_2026-03.csv"]

    def test_invalid_node_type_raises(self):
        with pytest.raises(ValueError, match="Invalid node_type"):
            KnowledgeNode(
                id="x", timestamp="t", category="c",
                content="c", node_type="bogus"
            )

    def test_invalid_staleness_raises(self):
        with pytest.raises(ValueError, match="Invalid staleness"):
            KnowledgeNode(
                id="x", timestamp="t", category="c",
                content="c", staleness="bogus"
            )

    def test_round_trip_dict(self):
        node = make_node("corrections", "Fix margin calc", node_type="rule")
        node.add_relation("target-1", "derived_from", 0.9)
        node.source_refs = ["memo_001"]
        node.staleness = "aging"

        d = node.to_dict()
        node2 = KnowledgeNode.from_dict(d)

        assert node2.id == node.id
        assert node2.category == "corrections"
        assert node2.node_type == "rule"
        assert node2.staleness == "aging"
        assert len(node2.relations) == 1
        assert node2.relations[0].target_id == "target-1"
        assert node2.source_refs == ["memo_001"]

    def test_mind_entry_dict_backward_compat(self):
        """Graph fields stored in metadata._graph for JSONL backward compat."""
        node = make_node("findings", "test", node_type="entity")
        node.add_relation("abc", "supports")
        node.source_refs = ["doc_1"]

        d = node.to_mind_entry_dict()
        # Standard MindEntry fields at top level
        assert "id" in d
        assert "category" in d
        assert "content" in d
        assert "promoted" in d
        # Graph fields nested under metadata._graph
        assert "_graph" in d["metadata"]
        assert d["metadata"]["_graph"]["node_type"] == "entity"
        assert len(d["metadata"]["_graph"]["relations"]) == 1
        assert d["metadata"]["_graph"]["source_refs"] == ["doc_1"]

    def test_from_dict_reads_graph_meta(self):
        """Can reconstruct KnowledgeNode from legacy format with _graph metadata."""
        d = {
            "id": "test-id",
            "timestamp": "2026-04-12T00:00:00Z",
            "category": "findings",
            "content": "something",
            "metadata": {
                "source": "test",
                "_graph": {
                    "node_type": "entity",
                    "source_refs": ["doc_1"],
                    "relations": [
                        {"target_id": "abc", "relation_type": "supports", "confidence": 0.9, "created_at": "2026-04-12T00:00:00Z"}
                    ],
                },
            },
            "promoted": False,
        }
        node = KnowledgeNode.from_dict(d)
        assert node.node_type == "entity"
        assert node.source_refs == ["doc_1"]
        assert len(node.relations) == 1
        assert node.relations[0].target_id == "abc"
        # _graph should be stripped from clean metadata
        assert "_graph" not in node.metadata
        assert node.metadata["source"] == "test"

    def test_is_superseded_property(self):
        node = make_node("x", "y")
        assert not node.is_superseded
        assert node.is_active
        node.superseded_by = "newer-id"
        assert node.is_superseded
        assert not node.is_active

    def test_add_relation_method(self):
        node = make_node("x", "y")
        rel = node.add_relation("target", "evidence_for", 0.7)
        assert len(node.relations) == 1
        assert rel.target_id == "target"
        assert rel.confidence == 0.7

    def test_get_relations_filtered(self):
        node = make_node("x", "y")
        node.add_relation("a", "supports")
        node.add_relation("b", "contradicts")
        node.add_relation("c", "supports")
        assert len(node.get_relations("supports")) == 2
        assert len(node.get_relations("contradicts")) == 1
        assert len(node.get_relations()) == 3


class TestUpgradeEntry:
    def test_upgrade_legacy_entry(self):
        """Old MindEntry dict gets graph defaults added."""
        d = {
            "id": "old-id",
            "timestamp": "2026-01-01T00:00:00Z",
            "category": "preferences",
            "content": "old content",
            "metadata": {},
            "promoted": False,
        }
        result = upgrade_entry(d)
        assert result["relations"] == []
        assert result["source_refs"] == []
        assert result["staleness"] == "fresh"
        assert result["superseded_by"] is None
        assert result["node_type"] == "entry"

    def test_upgrade_already_new_format(self):
        """New-format entries pass through unchanged."""
        d = {
            "id": "new-id",
            "node_type": "rule",
            "relations": [{"target_id": "x", "relation_type": "supports"}],
        }
        result = upgrade_entry(d)
        assert result["node_type"] == "rule"
        assert len(result["relations"]) == 1

    def test_upgrade_with_graph_meta(self):
        """Entries with _graph in metadata also pass through."""
        d = {
            "id": "mid-id",
            "metadata": {"_graph": {"node_type": "entity"}},
        }
        result = upgrade_entry(d)
        # Should not add top-level defaults since _graph exists
        assert result["metadata"]["_graph"]["node_type"] == "entity"


# ═══════════════════════════════════════════════════════════════════
# Relation Index Tests
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def tmp_index(tmp_path):
    """Create a RelationIndex backed by a temp directory."""
    return RelationIndex(tmp_path / "relations.json")


class TestRelationIndex:
    def test_add_and_get_relation(self, tmp_index):
        tmp_index.add_relation("A", "B", "supports")
        rels = tmp_index.get_related("A")
        assert len(rels) == 1
        assert rels[0]["target_id"] == "B"
        assert rels[0]["relation_type"] == "supports"

    def test_bidirectional_storage(self, tmp_index):
        tmp_index.add_relation("A", "B", "supports")
        # B should have a reverse relation pointing to A
        rels = tmp_index.get_related("B")
        assert len(rels) == 1
        assert rels[0]["target_id"] == "A"
        assert rels[0].get("_reverse") is True

    def test_exclude_reverse(self, tmp_index):
        tmp_index.add_relation("A", "B", "supports")
        rels = tmp_index.get_related("A", include_reverse=False)
        assert len(rels) == 1  # forward only
        rels = tmp_index.get_related("B", include_reverse=False)
        assert len(rels) == 0  # B has no forward relations

    def test_filter_by_type(self, tmp_index):
        tmp_index.add_relation("A", "B", "supports")
        tmp_index.add_relation("A", "C", "contradicts")
        assert len(tmp_index.get_related("A", relation_type="supports")) == 1
        assert len(tmp_index.get_related("A", relation_type="contradicts")) == 1

    def test_get_contradictions(self, tmp_index):
        tmp_index.add_relation("A", "B", "contradicts")
        tmp_index.add_relation("A", "C", "supports")
        contras = tmp_index.get_contradictions("A")
        assert contras == ["B"]

    def test_get_supporters(self, tmp_index):
        tmp_index.add_relation("A", "B", "supports")
        tmp_index.add_relation("C", "A", "evidence_for")
        supporters = tmp_index.get_supporters("A")
        assert set(supporters) == {"B", "C"}

    def test_get_chain_bfs(self, tmp_index):
        tmp_index.add_relation("A", "B", "supports")
        tmp_index.add_relation("B", "C", "supports")
        tmp_index.add_relation("C", "D", "supports")
        chain = tmp_index.get_chain("A", max_depth=3)
        assert "B" in chain
        assert "C" in chain
        assert "D" in chain

    def test_get_chain_depth_limit(self, tmp_index):
        tmp_index.add_relation("A", "B", "supports")
        tmp_index.add_relation("B", "C", "supports")
        tmp_index.add_relation("C", "D", "supports")
        chain = tmp_index.get_chain("A", max_depth=1)
        assert "B" in chain
        assert "C" not in chain

    def test_deduplication(self, tmp_index):
        tmp_index.add_relation("A", "B", "supports")
        tmp_index.add_relation("A", "B", "supports")  # duplicate
        rels = tmp_index.get_related("A", include_reverse=False)
        assert len(rels) == 1

    def test_remove_relations(self, tmp_index):
        tmp_index.add_relation("A", "B", "supports")
        tmp_index.add_relation("A", "C", "contradicts")
        removed = tmp_index.remove_relations("A")
        assert removed >= 2
        assert tmp_index.get_related("A") == []
        assert tmp_index.get_related("B") == []  # reverse also removed

    def test_count(self, tmp_index):
        assert tmp_index.count() == 0
        tmp_index.add_relation("A", "B", "supports")
        assert tmp_index.count() == 2  # forward + reverse

    def test_node_ids(self, tmp_index):
        tmp_index.add_relation("A", "B", "supports")
        ids = tmp_index.node_ids()
        assert set(ids) == {"A", "B"}

    def test_rebuild_from_entries(self, tmp_index):
        entries = [
            {
                "id": "node1",
                "relations": [
                    {"target_id": "node2", "relation_type": "supports", "confidence": 1.0, "created_at": "2026-01-01"}
                ],
            },
            {
                "id": "node3",
                "metadata": {
                    "_graph": {
                        "relations": [
                            {"target_id": "node1", "relation_type": "contradicts", "confidence": 0.8, "created_at": "2026-01-02"}
                        ]
                    }
                },
            },
        ]
        count = tmp_index.rebuild_from_entries(entries)
        assert count == 2
        assert len(tmp_index.get_related("node1")) > 0

    def test_invalid_relation_type_raises(self, tmp_index):
        with pytest.raises(ValueError):
            tmp_index.add_relation("A", "B", "invalid_type")

    def test_persistence(self, tmp_path):
        """Index survives re-instantiation."""
        path = tmp_path / "relations.json"
        idx1 = RelationIndex(path)
        idx1.add_relation("A", "B", "supports")

        idx2 = RelationIndex(path)
        rels = idx2.get_related("A")
        assert len(rels) == 1


# ═══════════════════════════════════════════════════════════════════
# Event Bus Tests
# ═══════════════════════════════════════════════════════════════════


class TestEventBus:
    def test_publish_and_receive(self):
        bus = EventBus()
        received = []

        @bus.on("test_event")
        def handler(payload):
            received.append(payload)

        bus.publish("test_event", {"key": "value"})
        assert len(received) == 1
        assert received[0]["key"] == "value"

    def test_multiple_listeners(self):
        bus = EventBus()
        results = []

        @bus.on("evt")
        def h1(p):
            results.append("h1")

        @bus.on("evt")
        def h2(p):
            results.append("h2")

        bus.publish("evt")
        assert results == ["h1", "h2"]

    def test_disable_prevents_publishing(self):
        bus = EventBus()
        received = []

        @bus.on("evt")
        def handler(p):
            received.append(True)

        bus.disable()
        count = bus.publish("evt")
        assert count == 0
        assert received == []

    def test_enable_after_disable(self):
        bus = EventBus()
        received = []

        @bus.on("evt")
        def handler(p):
            received.append(True)

        bus.disable()
        bus.publish("evt")
        bus.enable()
        bus.publish("evt")
        assert len(received) == 1

    def test_exception_in_listener_doesnt_block_others(self):
        bus = EventBus()
        results = []

        @bus.on("evt")
        def bad_handler(p):
            raise RuntimeError("boom")

        @bus.on("evt")
        def good_handler(p):
            results.append("ok")

        count = bus.publish("evt")
        assert count == 1  # only good_handler succeeded
        assert results == ["ok"]

    def test_no_listeners_returns_zero(self):
        bus = EventBus()
        assert bus.publish("unknown_event") == 0

    def test_unsubscribe(self):
        bus = EventBus()
        received = []

        def handler(p):
            received.append(True)

        bus.subscribe("evt", handler)
        bus.publish("evt")
        assert len(received) == 1

        bus.unsubscribe("evt", handler)
        bus.publish("evt")
        assert len(received) == 1  # no new invocation

    def test_clear(self):
        bus = EventBus()
        bus.subscribe("evt", lambda p: None)
        bus.clear()
        assert bus.get_listeners("evt") == []
        assert bus.get_event_log() == []

    def test_event_log(self):
        bus = EventBus()
        bus.subscribe("evt", lambda p: None)
        bus.publish("evt", {"a": 1})
        log = bus.get_event_log()
        assert len(log) == 1
        assert log[0]["event_type"] == "evt"
        assert "a" in log[0]["payload_keys"]

    def test_stats(self):
        bus = EventBus()
        bus.subscribe("a", lambda p: None)
        bus.subscribe("b", lambda p: None)
        stats = bus.stats
        assert stats["total_listeners"] == 2
        assert set(stats["event_types"]) == {"a", "b"}

    def test_events_constants(self):
        """Verify all event constants are defined."""
        assert Events.TAPE_INGESTED == "tape_ingested"
        assert Events.DOCUMENT_INGESTED == "document_ingested"
        assert Events.MEMO_EDITED == "memo_edited"
        assert Events.CORRECTION_RECORDED == "correction_recorded"
        assert Events.THESIS_UPDATED == "thesis_updated"
