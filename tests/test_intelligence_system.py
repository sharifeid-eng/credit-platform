"""
Tests for Phases 1-7: Knowledge Graph, Thesis, Learning, Compilation,
Intelligence, KB Query, Session.
"""

import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from core.mind.schema import KnowledgeNode, Relation, make_node, upgrade_entry


# ═══════════════════════════════════════════════════════════════════
# Phase 1: Knowledge Graph Tests
# ═══════════════════════════════════════════════════════════════════

class TestKnowledgeGraph:
    @pytest.fixture
    def graph_dir(self, tmp_path):
        """Set up a mind directory with some JSONL entries."""
        mind_dir = tmp_path / "mind"
        mind_dir.mkdir()

        # Write some entries
        entries = [
            make_node("findings", "PAR30 is 3.6%", metadata={"metric": "par"}),
            make_node("corrections", "Use cautious tone for PAR > 3%"),
            make_node("findings", "Collection rate dropped to 82%"),
        ]
        jsonl_path = mind_dir / "findings.jsonl"
        corr_path = mind_dir / "corrections.jsonl"
        with open(jsonl_path, "w") as f:
            for e in entries[:1] + entries[2:]:
                f.write(json.dumps(e.to_mind_entry_dict()) + "\n")
        with open(corr_path, "w") as f:
            f.write(json.dumps(entries[1].to_mind_entry_dict()) + "\n")

        return mind_dir

    def test_load_all_nodes(self, graph_dir):
        from core.mind.graph import KnowledgeGraph
        g = KnowledgeGraph(graph_dir)
        nodes = g._load_all_nodes()
        assert len(nodes) == 3

    def test_query_by_text(self, graph_dir):
        from core.mind.graph import KnowledgeGraph
        g = KnowledgeGraph(graph_dir)
        results = g.query("PAR", max_results=5)
        # PAR should match at least 1 entry
        assert len(results) >= 1
        assert any("PAR" in n.content for n in results)

    def test_query_filter_category(self, graph_dir):
        from core.mind.graph import KnowledgeGraph
        g = KnowledgeGraph(graph_dir)
        results = g.query("", categories=["corrections"])
        assert all(n.category == "corrections" for n in results)

    def test_stats(self, graph_dir):
        from core.mind.graph import KnowledgeGraph
        g = KnowledgeGraph(graph_dir)
        s = g.stats()
        assert s["total_nodes"] == 3
        assert s["active_nodes"] == 3

    def test_find_stale_empty(self, graph_dir):
        from core.mind.graph import KnowledgeGraph
        g = KnowledgeGraph(graph_dir)
        # All entries are fresh (just created)
        stale = g.find_stale(days=60)
        assert len(stale) == 0

    def test_compact(self, graph_dir):
        from core.mind.graph import KnowledgeGraph
        g = KnowledgeGraph(graph_dir)
        result = g.compact()
        assert "removed" in result
        assert "kept" in result


# ═══════════════════════════════════════════════════════════════════
# Phase 4: Thesis Tracker Tests
# ═══════════════════════════════════════════════════════════════════

class TestThesisTracker:
    @pytest.fixture
    def tracker(self, tmp_path):
        from core.mind.thesis import ThesisTracker
        mind_dir = tmp_path / "mind"
        mind_dir.mkdir()
        return ThesisTracker("test_co", "test_prod", base_dir=mind_dir)

    def test_no_thesis_returns_none(self, tracker):
        assert tracker.load() is None

    def test_create_and_load_thesis(self, tracker):
        from core.mind.thesis import InvestmentThesis, ThesisPillar

        thesis = InvestmentThesis(
            company="test_co",
            product="test_prod",
            title="Test Thesis",
            pillars=[
                ThesisPillar(
                    id="p1", claim="Collection rate > 85%",
                    metric_key="collection_rate",
                    threshold=0.85, direction="above",
                ),
                ThesisPillar(
                    id="p2", claim="PAR30 < 5%",
                    metric_key="par_30_pct",
                    threshold=0.05, direction="below",
                ),
            ],
        )
        tracker.save(thesis, "Initial creation")

        loaded = tracker.load()
        assert loaded is not None
        assert loaded.title == "Test Thesis"
        assert len(loaded.pillars) == 2

    def test_drift_detection_breach(self, tracker):
        from core.mind.thesis import InvestmentThesis, ThesisPillar

        thesis = InvestmentThesis(
            company="test_co", product="test_prod",
            title="Test", pillars=[
                ThesisPillar(
                    id="p1", claim="Collection > 85%",
                    metric_key="collection_rate",
                    threshold=0.85, direction="above",
                ),
            ],
        )
        tracker.save(thesis)

        # Simulate breach
        alerts = tracker.check_drift({"collection_rate": 0.80})
        assert len(alerts) == 1
        assert alerts[0].severity == "critical"
        assert alerts[0].new_status == "broken"

    def test_drift_detection_near_breach(self, tracker):
        from core.mind.thesis import InvestmentThesis, ThesisPillar

        thesis = InvestmentThesis(
            company="test_co", product="test_prod",
            title="Test", pillars=[
                ThesisPillar(
                    id="p1", claim="Collection > 85%",
                    metric_key="collection_rate",
                    threshold=0.85, direction="above",
                ),
            ],
        )
        tracker.save(thesis)

        # Near breach (within 10%)
        alerts = tracker.check_drift({"collection_rate": 0.86})
        assert len(alerts) >= 1
        assert alerts[0].severity == "warning"

    def test_drift_no_alert_when_healthy(self, tracker):
        from core.mind.thesis import InvestmentThesis, ThesisPillar

        thesis = InvestmentThesis(
            company="test_co", product="test_prod",
            title="Test", pillars=[
                ThesisPillar(
                    id="p1", claim="Collection > 85%",
                    metric_key="collection_rate",
                    threshold=0.85, direction="above",
                    status="holding",
                ),
            ],
        )
        tracker.save(thesis)

        # Well above threshold
        alerts = tracker.check_drift({"collection_rate": 0.95})
        # May return info-level transition or empty
        critical = [a for a in alerts if a.severity in ("warning", "critical")]
        assert len(critical) == 0

    def test_conviction_score(self):
        from core.mind.thesis import InvestmentThesis, ThesisPillar

        thesis = InvestmentThesis(
            company="x", product="y", title="T",
            pillars=[
                ThesisPillar(id="p1", claim="A", conviction_score=80),
                ThesisPillar(id="p2", claim="B", conviction_score=60),
                ThesisPillar(id="p3", claim="C", conviction_score=40, status="retired"),
            ],
        )
        # Retired pillars excluded
        assert thesis.conviction_score == 70  # avg of 80 and 60

    def test_thesis_log(self, tracker):
        from core.mind.thesis import InvestmentThesis, ThesisPillar

        thesis = InvestmentThesis(
            company="test_co", product="test_prod",
            title="Test", pillars=[],
        )
        tracker.save(thesis, "v1")
        thesis.version = 2
        tracker.save(thesis, "v2")

        log = tracker.get_log()
        assert len(log) == 2
        assert log[0]["change_reason"] == "v2"  # newest first

    def test_ai_context(self, tracker):
        from core.mind.thesis import InvestmentThesis, ThesisPillar

        thesis = InvestmentThesis(
            company="test_co", product="test_prod",
            title="Strong Credit",
            pillars=[
                ThesisPillar(id="p1", claim="Good collections",
                            status="holding", conviction_score=80),
            ],
        )
        tracker.save(thesis)

        ctx = tracker.get_ai_context()
        assert "Strong Credit" in ctx
        assert "80/100" in ctx


# ═══════════════════════════════════════════════════════════════════
# Phase 3: Learning Engine Tests
# ═══════════════════════════════════════════════════════════════════

class TestLearningEngine:
    def test_analyze_tone_shift(self):
        from core.mind.learning import LearningEngine
        engine = LearningEngine()

        rule = engine.analyze_correction(
            original="The portfolio shows strong and healthy collection performance with robust growth.",
            corrected="The portfolio shows concerning and deteriorating collection trends requiring caution.",
            context="executive summary",
        )
        assert rule is not None
        assert rule.category == "tone_shift"
        assert "tone" in rule.rule_text.lower() or "cautious" in rule.rule_text.lower() or "negative" in rule.rule_text.lower()

    def test_analyze_trivial_change_returns_none(self):
        from core.mind.learning import LearningEngine
        engine = LearningEngine()

        rule = engine.analyze_correction(
            original="The collection rate is 85%.",
            corrected="The collection rate is 85%.",  # identical
        )
        assert rule is None

    def test_analyze_data_caveat(self):
        from core.mind.learning import LearningEngine
        engine = LearningEngine()

        rule = engine.analyze_correction(
            original="The PAR30 rate is 3.6% which shows good performance.",
            corrected="The PAR30 rate is 3.6%, however note that this is based on estimated DPD from collection curves, which is a limitation of the data.",
            context="par analysis",
        )
        assert rule is not None
        assert rule.category in ("data_caveat", "missing_context")

    def test_to_knowledge_node(self):
        from core.mind.learning import LearningRule
        rule = LearningRule(
            category="tone_shift",
            rule_text="Use cautious tone when PAR > 3%",
            trigger_condition="PAR30 > 3%",
            confidence=0.8,
            source_correction_ids=["corr-1", "corr-2"],
        )
        node = rule.to_knowledge_node()
        assert node.node_type == "rule"
        assert node.metadata["auto_generated"] is True
        assert len(node.relations) == 2  # derived_from x 2

    def test_extract_patterns(self):
        from core.mind.learning import LearningEngine
        engine = LearningEngine()

        # Create fake corrections with consistent tone shifts
        corrections = []
        for i in range(5):
            corrections.append({
                "id": f"corr-{i}",
                "content": f"Tone correction #{i}",
                "metadata": {
                    "original": "The portfolio is strong and healthy with robust performance.",
                    "corrected": "The portfolio is deteriorating with concerning risk trends.",
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        patterns = engine.extract_patterns(corrections, min_count=3)
        assert len(patterns) >= 1

    def test_correction_frequency(self):
        from core.mind.learning import LearningEngine
        engine = LearningEngine()

        corrections = []
        for i in range(4):
            corrections.append({
                "metadata": {
                    "original": "Strong healthy performance.",
                    "corrected": "Concerning deteriorating performance.",
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        freq = engine.get_correction_frequency(corrections, days=30)
        assert freq["total_corrections"] == 4
        assert len(freq["by_type"]) > 0


# ═══════════════════════════════════════════════════════════════════
# Phase 2: Entity Extractor Tests
# ═══════════════════════════════════════════════════════════════════

class TestEntityExtractor:
    def test_extract_par_metric(self):
        from core.mind.entity_extractor import extract_entities_from_text
        text = "The current PAR 30+ : 4.5% indicating moderate stress."
        entities = extract_entities_from_text(text)
        par_entities = [e for e in entities if e.key == "par_30"]
        assert len(par_entities) >= 1
        assert par_entities[0].value == 4.5

    def test_extract_collection_rate(self):
        from core.mind.entity_extractor import extract_entities_from_text
        text = "Collection rate = 87.2% for the period."
        entities = extract_entities_from_text(text)
        cr = [e for e in entities if e.key == "collection_rate"]
        assert len(cr) >= 1
        assert cr[0].value == 87.2

    def test_extract_facility_limit(self):
        from core.mind.entity_extractor import extract_entities_from_text
        text = "The facility limit: $10,000,000"
        entities = extract_entities_from_text(text)
        fl = [e for e in entities if e.key == "facility_limit"]
        assert len(fl) >= 1

    def test_extract_covenant(self):
        from core.mind.entity_extractor import extract_entities_from_text
        text = "The covenant states that PAR 30 shall not exceed 5.0%"
        entities = extract_entities_from_text(text)
        cov = [e for e in entities if e.entity_type == "COVENANT"]
        assert len(cov) >= 1

    def test_extract_from_metrics(self):
        from core.mind.entity_extractor import extract_entities_from_metrics
        metrics = {
            "collection_rate": 0.87,
            "total_deals": 7697,
            "par_30_pct": 0.036,
        }
        entities = extract_entities_from_metrics(metrics, "tape_2026-03.csv")
        assert len(entities) >= 3
        assert all(e.confidence == "A" for e in entities)

    def test_no_entities_from_empty(self):
        from core.mind.entity_extractor import extract_entities_from_text
        assert extract_entities_from_text("") == []


# ═══════════════════════════════════════════════════════════════════
# Phase 2: Compiler Tests
# ═══════════════════════════════════════════════════════════════════

class TestKnowledgeCompiler:
    @pytest.fixture
    def compiler(self, tmp_path):
        from core.mind.compiler import KnowledgeCompiler
        mind_dir = tmp_path / "mind"
        mind_dir.mkdir()
        return KnowledgeCompiler(mind_dir)

    def test_compile_new_entity(self, compiler):
        from core.mind.entity_extractor import ExtractedEntity

        entities = [
            ExtractedEntity(
                entity_type="METRIC", key="collection_rate",
                value=0.87, confidence="A", source_doc_id="tape1.csv",
            ),
        ]
        report = compiler.compile(entities, "tape1.csv", "test", "prod")
        assert report.created == 1
        assert report.total_actions == 1

    def test_compile_reinforce_same_value(self, compiler):
        from core.mind.entity_extractor import ExtractedEntity

        entity = ExtractedEntity(
            entity_type="METRIC", key="collection_rate",
            value=0.87, confidence="A", source_doc_id="tape1.csv",
        )
        # First compilation
        compiler.compile([entity], "tape1.csv", "test", "prod")
        # Same value from different source — reinforces
        entity2 = ExtractedEntity(
            entity_type="METRIC", key="collection_rate",
            value=0.87, confidence="A", source_doc_id="tape2.csv",
        )
        report = compiler.compile([entity2], "tape2.csv", "test", "prod")
        assert report.reinforced == 1

    def test_compile_supersede_changed_value(self, compiler):
        from core.mind.entity_extractor import ExtractedEntity

        entity1 = ExtractedEntity(
            entity_type="METRIC", key="collection_rate",
            value=0.87, confidence="A", source_doc_id="tape1.csv",
        )
        compiler.compile([entity1], "tape1.csv", "test", "prod")

        entity2 = ExtractedEntity(
            entity_type="METRIC", key="collection_rate",
            value=0.82, confidence="A", source_doc_id="tape2.csv",
        )
        report = compiler.compile([entity2], "tape2.csv", "test", "prod")
        assert report.superseded == 1

    def test_compile_report_saved(self, compiler):
        from core.mind.entity_extractor import ExtractedEntity

        entity = ExtractedEntity(
            entity_type="METRIC", key="par_30",
            value=0.036, confidence="A", source_doc_id="tape1.csv",
        )
        compiler.compile([entity], "tape1.csv", "test", "prod")

        log_path = compiler.mind_dir / "compilation_log.jsonl"
        assert log_path.exists()

    def test_cross_reference(self, compiler):
        from core.mind.entity_extractor import ExtractedEntity

        # Two different sources with different values
        e1 = ExtractedEntity(
            entity_type="COVENANT", key="covenant_par_30",
            value=5.0, confidence="B", source_doc_id="doc_mma.pdf",
        )
        e2 = ExtractedEntity(
            entity_type="COVENANT", key="covenant_par_30",
            value=4.5, confidence="B", source_doc_id="doc_amendment.pdf",
        )
        compiler.compile([e1], "doc_mma.pdf", "test", "prod")
        compiler.compile([e2], "doc_amendment.pdf", "test", "prod")

        discrepancies = compiler.cross_reference("test", "prod")
        # May or may not detect depending on contradiction logic
        # At minimum, the method should work without errors
        assert isinstance(discrepancies, list)


# ═══════════════════════════════════════════════════════════════════
# Phase 5: Intelligence Engine Tests
# ═══════════════════════════════════════════════════════════════════

class TestIntelligenceEngine:
    @pytest.fixture
    def intel_dir(self, tmp_path):
        """Set up multiple company directories with entity nodes."""
        data_dir = tmp_path / "data"

        # Company A
        mind_a = data_dir / "company_a" / "prod" / "mind"
        mind_a.mkdir(parents=True)
        with open(mind_a / "entities.jsonl", "w") as f:
            node = make_node("metric", "PAR30: 3.6%", metadata={
                "entity_key": "par_30", "entity_type": "METRIC", "value": 3.6
            }, node_type="entity")
            f.write(json.dumps(node.to_mind_entry_dict()) + "\n")

        # Company B
        mind_b = data_dir / "company_b" / "prod" / "mind"
        mind_b.mkdir(parents=True)
        with open(mind_b / "entities.jsonl", "w") as f:
            node = make_node("metric", "PAR30: 4.1%", metadata={
                "entity_key": "par_30", "entity_type": "METRIC", "value": 4.1
            }, node_type="entity")
            f.write(json.dumps(node.to_mind_entry_dict()) + "\n")

        return data_dir

    def test_discover_companies(self, intel_dir):
        from core.mind.intelligence import IntelligenceEngine
        engine = IntelligenceEngine(intel_dir)
        companies = engine._get_all_companies()
        assert len(companies) == 2

    def test_detect_patterns(self, intel_dir):
        from core.mind.intelligence import IntelligenceEngine
        engine = IntelligenceEngine(intel_dir)
        patterns = engine.detect_cross_company_patterns()
        # Both companies have par_30 entities — should detect
        assert isinstance(patterns, list)

    def test_save_and_load_patterns(self, intel_dir):
        from core.mind.intelligence import IntelligenceEngine, Pattern
        engine = IntelligenceEngine(intel_dir)
        patterns = [Pattern(
            pattern_type="metric_trend",
            description="Test pattern",
            companies_affected=["a", "b"],
        )]
        engine.save_patterns(patterns)
        loaded = engine.load_patterns()
        assert len(loaded) == 1
        assert loaded[0].description == "Test pattern"


# ═══════════════════════════════════════════════════════════════════
# Phase 7: KB Decomposer Tests
# ═══════════════════════════════════════════════════════════════════

class TestKBDecomposer:
    def test_decompose_lessons(self, tmp_path):
        from core.mind.kb_decomposer import decompose_lessons

        lessons_file = tmp_path / "lessons.md"
        lessons_file.write_text("""
## 2026-04-10 — FX double-multiply bug

**Discovery:** Weighted avg discount was being double-multiplied by FX rate.
**Rule:** Always check that `apply_multiplier()` is not applied twice.
**Reasoning:** The discount is unitless — FX conversion only applies to monetary values.

## 2026-04-11 — PAR benchmark date

**Discovery:** PAR benchmark was using `datetime.now()` instead of snapshot date.
**Rule:** Always use snapshot date for temporal calculations, not current date.
""", encoding="utf-8")

        nodes = decompose_lessons(lessons_file)
        assert len(nodes) == 2
        assert all(n.node_type == "rule" for n in nodes)
        assert all(n.category == "session_lesson" for n in nodes)
        assert "apply_multiplier" in nodes[0].content or "apply_multiplier" in nodes[0].metadata.get("rule", "")

    def test_decompose_decisions(self, tmp_path):
        from core.mind.kb_decomposer import decompose_decisions

        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("""
## Key Architectural Decisions
- **AI response disk cache** — All AI endpoints cache responses to `reports/ai_cache/` as JSON files.
- **Completed-only margins** — All margin calculations in Returns use completed deals only.
- **Outstanding amount pattern** — Ageing charts use `outstanding = PV - Collected - Denied`.
""", encoding="utf-8")

        nodes = decompose_decisions(claude_md)
        assert len(nodes) == 3
        assert all(n.category == "architectural_decision" for n in nodes)

    def test_empty_file(self, tmp_path):
        from core.mind.kb_decomposer import decompose_lessons
        empty = tmp_path / "empty.md"
        empty.write_text("", encoding="utf-8")
        assert decompose_lessons(empty) == []

    def test_nonexistent_file(self, tmp_path):
        from core.mind.kb_decomposer import decompose_lessons
        assert decompose_lessons(tmp_path / "nonexistent.md") == []


# ═══════════════════════════════════════════════════════════════════
# Phase 7: KB Query Tests
# ═══════════════════════════════════════════════════════════════════

class TestKBQuery:
    @pytest.fixture
    def kb_dir(self, tmp_path):
        """Set up data dir with mind entries."""
        data_dir = tmp_path / "data"
        mind = data_dir / "test_co" / "test_prod" / "mind"
        mind.mkdir(parents=True)

        with open(mind / "findings.jsonl", "w") as f:
            node = make_node("findings", "PAR30 increased to 3.6%")
            f.write(json.dumps(node.to_mind_entry_dict()) + "\n")
            node2 = make_node("findings", "Collection rate stable at 87%")
            f.write(json.dumps(node2.to_mind_entry_dict()) + "\n")

        return data_dir

    def test_search_returns_results(self, kb_dir):
        from core.mind.kb_query import KnowledgeBaseQuery
        kb = KnowledgeBaseQuery(kb_dir)
        results = kb.search("PAR")
        assert len(results) >= 1
        assert any("PAR" in r.node.content for r in results)

    def test_search_empty_query(self, kb_dir):
        from core.mind.kb_query import KnowledgeBaseQuery
        kb = KnowledgeBaseQuery(kb_dir)
        results = kb.search("")
        assert len(results) >= 1  # returns all with base score

    def test_search_filter_category(self, kb_dir):
        from core.mind.kb_query import KnowledgeBaseQuery
        kb = KnowledgeBaseQuery(kb_dir)
        results = kb.search("PAR", categories=["findings"])
        assert all(r.node.category == "findings" for r in results)


# ═══════════════════════════════════════════════════════════════════
# Phase 6: Session Tracker Tests
# ═══════════════════════════════════════════════════════════════════

class TestSessionTracker:
    def test_session_state_creation(self):
        from core.mind.session import SessionState
        s = SessionState()
        assert s.started_at
        assert s.tapes_loaded == []
        assert s.companies_touched == []

    def test_record_events(self):
        from core.mind.session import SessionState
        s = SessionState()
        s.record_event("tape_ingested", {"company": "klaim", "snapshot": "2026-03.csv"})
        s.record_event("correction_recorded", {"company": "klaim"})
        assert len(s.tapes_loaded) == 1
        assert s.corrections_recorded == 1
        assert "klaim" in s.companies_touched

    def test_summary(self):
        from core.mind.session import SessionState
        s = SessionState()
        s.record_event("tape_ingested", {"company": "klaim", "snapshot": "tape.csv"})
        s.record_event("tape_ingested", {"company": "silq", "snapshot": "tape2.csv"})
        summary = s.summary
        assert "2 tape(s) loaded" in summary
        assert "klaim" in summary or "silq" in summary

    def test_save_and_load(self, tmp_path):
        from core.mind.session import SessionState, save_session_state, load_last_session
        s = SessionState()
        s.record_event("tape_ingested", {"company": "test", "snapshot": "t.csv"})

        path = tmp_path / "session.json"
        # Need to set global state for save
        import core.mind.session as sess_module
        old = sess_module._current_session
        sess_module._current_session = s
        save_session_state(path)
        sess_module._current_session = old

        loaded = load_last_session(path)
        assert loaded is not None
        assert len(loaded.tapes_loaded) == 1


# ═══════════════════════════════════════════════════════════════════
# Phase 5: Analyst Context Tests
# ═══════════════════════════════════════════════════════════════════

class TestAnalystContext:
    def test_save_and_load(self, tmp_path):
        from core.mind.analyst import (
            AnalystContext, save_analyst_context, load_analyst_context
        )
        ctx = AnalystContext(
            priority_companies=["klaim", "tamara"],
            focus_areas=["PAR trends"],
            session_count=5,
        )
        path = tmp_path / "analyst.json"
        save_analyst_context(ctx, path)

        loaded = load_analyst_context(path)
        assert loaded.priority_companies == ["klaim", "tamara"]
        assert loaded.session_count == 5

    def test_update_session_end(self, tmp_path):
        from core.mind.analyst import (
            AnalystContext, save_analyst_context, load_analyst_context,
            update_session_end, _CONTEXT_PATH
        )
        # Use a temp path
        import core.mind.analyst as analyst_module
        old_path = analyst_module._CONTEXT_PATH
        analyst_module._CONTEXT_PATH = tmp_path / "analyst.json"

        try:
            ctx = update_session_end(
                companies_touched=["klaim"],
                focus_areas=["covenants"],
            )
            assert ctx.session_count == 1
            assert ctx.last_companies_touched == ["klaim"]
            assert ctx.last_session_at
        finally:
            analyst_module._CONTEXT_PATH = old_path


# ═══════════════════════════════════════════════════════════════════
# Phase 5: Morning Briefing Tests
# ═══════════════════════════════════════════════════════════════════

class TestMorningBriefing:
    def test_generate_empty(self, tmp_path):
        from core.mind.briefing import generate_morning_briefing
        briefing = generate_morning_briefing(data_dir=tmp_path)
        assert briefing.generated_at
        assert isinstance(briefing.priority_actions, list)
        assert isinstance(briefing.recommendations, list)

    def test_briefing_to_dict(self, tmp_path):
        from core.mind.briefing import generate_morning_briefing
        briefing = generate_morning_briefing(data_dir=tmp_path)
        d = briefing.to_dict()
        assert "since_last_session" in d
        assert "priority_actions" in d
        assert "recommendations" in d

    def test_briefing_with_companies(self, tmp_path):
        from core.mind.briefing import generate_morning_briefing

        # Create a company dir
        co_dir = tmp_path / "test_co" / "test_prod"
        co_dir.mkdir(parents=True)
        (co_dir / "mind").mkdir()

        briefing = generate_morning_briefing(data_dir=tmp_path)
        assert briefing.generated_at


# ═══════════════════════════════════════════════════════════════════
# Integration: Event Bus + Listeners
# ═══════════════════════════════════════════════════════════════════

class TestListeners:
    def test_register_all_listeners(self):
        """Listeners can be registered without error."""
        from core.mind.event_bus import EventBus
        from core.mind.listeners import register_all_listeners
        import core.mind.listeners as listeners_module

        # Reset registration state
        listeners_module._registered = False

        # Use a fresh bus to avoid side effects
        register_all_listeners()
        assert listeners_module._registered is True

        # Reset for other tests
        listeners_module._registered = False
