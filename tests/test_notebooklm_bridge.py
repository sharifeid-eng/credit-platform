"""
Tests for the NotebookLM bridge, dual engine, and synthesizer.

These tests mock the notebooklm library to verify our bridge code works
correctly against the real API shapes (AskResult, ChatReference, Notebook,
Source dataclasses) without requiring actual NLM authentication.
"""

import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Mock notebooklm types matching real v0.3.4 API ──────────────────────────

@dataclass
class MockNotebook:
    id: str
    title: str
    created_at: object = None
    sources_count: int = 0
    is_owner: bool = True


@dataclass
class MockSource:
    id: str
    title: str = None
    url: str = None
    status: int = 2  # READY
    @property
    def is_ready(self): return self.status == 2
    @property
    def is_processing(self): return self.status == 1
    @property
    def is_error(self): return self.status == 3
    @property
    def kind(self): return "text"


@dataclass
class MockAskResult:
    answer: str
    conversation_id: str
    turn_number: int
    is_follow_up: bool = False
    references: list = field(default_factory=list)
    raw_response: str = ""


@dataclass
class MockChatReference:
    source_id: str
    citation_number: int = None
    cited_text: str = None
    start_char: int = None
    end_char: int = None
    chunk_id: str = None


# ── NotebookLMEngine tests ──────────────────────────────────────────────────

class TestNotebookLMEngineInit:
    """Test engine initialization and availability probing."""

    def test_unavailable_when_no_library(self):
        """Engine gracefully handles missing notebooklm package."""
        with patch.dict(sys.modules, {"notebooklm": None}):
            from core.research.notebooklm_bridge import NotebookLMEngine
            # Force re-check by creating a fresh instance
            engine = NotebookLMEngine.__new__(NotebookLMEngine)
            engine._python_module = None
            result = engine._try_python_import()
            assert result is False

    def test_status_dict_structure(self):
        """get_status returns all expected keys."""
        from core.research.notebooklm_bridge import NotebookLMEngine
        engine = NotebookLMEngine.__new__(NotebookLMEngine)
        engine._use_python = False
        engine._use_cli = False
        engine._authenticated = False
        engine.available = False
        engine._notebook_ids = {}
        status = engine.get_status()
        assert "library_installed" in status
        assert "authenticated" in status
        assert "available" in status
        assert "notebooks_cached" in status
        assert "integration_method" in status


class TestNotebookLMEnginePersistence:
    """Test sidecar JSON persistence for notebook IDs and synced sources."""

    def test_save_and_load_state(self, tmp_path):
        """State persists to JSON and loads back correctly."""
        from core.research.notebooklm_bridge import NotebookLMEngine

        engine = NotebookLMEngine.__new__(NotebookLMEngine)
        engine._use_python = False
        engine._use_cli = False
        engine._authenticated = False
        engine.available = False
        engine._notebook_ids = {}
        engine._synced_sources = {}

        # Patch data root to temp dir
        with patch("core.research.notebooklm_bridge._DATA_ROOT", tmp_path):
            # Create directory structure
            (tmp_path / "test_co" / "test_prod" / "dataroom").mkdir(parents=True)

            state = {
                "notebook_id": "nb_123",
                "synced_sources": {"doc1": "src_456"},
            }
            engine._save_state("test_co", "test_prod", state)

            loaded = engine._load_state("test_co", "test_prod")
            assert loaded["notebook_id"] == "nb_123"
            assert loaded["synced_sources"]["doc1"] == "src_456"

    def test_load_missing_state_returns_empty(self, tmp_path):
        """Loading from non-existent path returns empty dict."""
        from core.research.notebooklm_bridge import NotebookLMEngine

        engine = NotebookLMEngine.__new__(NotebookLMEngine)
        engine._use_python = False
        engine._use_cli = False
        engine._authenticated = False
        engine.available = False
        engine._notebook_ids = {}
        engine._synced_sources = {}

        with patch("core.research.notebooklm_bridge._DATA_ROOT", tmp_path):
            loaded = engine._load_state("nonexistent", "product")
            assert loaded == {}


class TestNotebookLMEngineQuery:
    """Test query result parsing."""

    def test_query_returns_empty_when_unavailable(self):
        """Query gracefully returns empty when engine is not available."""
        from core.research.notebooklm_bridge import NotebookLMEngine

        engine = NotebookLMEngine.__new__(NotebookLMEngine)
        engine.available = False
        engine._use_python = False
        engine._use_cli = False

        result = engine.query("nb_123", "What is the PAR rate?")
        assert result["answer"] == ""
        assert result["available"] is False
        assert result["engine"] == "notebooklm"
        assert result["references"] == []

    def test_query_returns_empty_when_no_notebook(self):
        """Query returns empty when notebook_id is None."""
        from core.research.notebooklm_bridge import NotebookLMEngine

        engine = NotebookLMEngine.__new__(NotebookLMEngine)
        engine.available = True
        engine._use_python = True
        engine._use_cli = False

        result = engine.query(None, "What is the PAR rate?")
        assert result["answer"] == ""
        assert result["available"] is False


# ── Synthesizer tests ────────────────────────────────────────────────────────

class TestSynthesizerNLMConversion:
    """Test that synthesizer correctly converts NLM reference formats."""

    def test_convert_chatreference_dicts(self):
        """Converts NLM ChatReference-style dicts to standard citations."""
        from core.research.synthesizer import ResearchSynthesizer

        synth = ResearchSynthesizer()
        nlm_refs = [
            {
                "source_id": "src_001",
                "citation_number": 1,
                "cited_text": "The PAR 30+ rate is 3.6%",
                "start_char": 100,
                "end_char": 130,
                "chunk_id": "chunk_abc",
            },
            {
                "source_id": "src_002",
                "citation_number": 2,
                "cited_text": "Collection rate trending down",
            },
        ]

        converted = synth._convert_nlm_sources(nlm_refs)

        assert len(converted) == 2
        assert converted[0]["doc_id"] == "src_001"
        assert converted[0]["index"] == 1
        assert converted[0]["cited_text"] == "The PAR 30+ rate is 3.6%"
        assert converted[0]["origin"] == "notebooklm"
        assert converted[1]["doc_id"] == "src_002"
        assert converted[1]["snippet"] == "Collection rate trending down"

    def test_convert_plain_strings(self):
        """Handles legacy plain string sources."""
        from core.research.synthesizer import ResearchSynthesizer

        synth = ResearchSynthesizer()
        converted = synth._convert_nlm_sources(["Source text one", "Source text two"])
        assert len(converted) == 2
        assert converted[0]["snippet"] == "Source text one"
        assert converted[0]["origin"] == "notebooklm"

    def test_convert_empty_list(self):
        """Empty list returns empty."""
        from core.research.synthesizer import ResearchSynthesizer
        synth = ResearchSynthesizer()
        assert synth._convert_nlm_sources([]) == []

    def test_synthesize_nlm_only_when_claude_empty(self):
        """When Claude returns empty, NLM answer passes through."""
        from core.research.synthesizer import ResearchSynthesizer

        synth = ResearchSynthesizer()
        result = synth.synthesize(
            claude_result={"answer": "", "citations": []},
            nlm_result={
                "answer": "NLM found that PAR is 3.6%",
                "sources": [{"source_id": "s1", "cited_text": "PAR data"}],
            },
            question="What is PAR?",
        )
        assert result["engine"] == "notebooklm"
        assert "PAR" in result["answer"]

    def test_synthesize_claude_only_when_nlm_empty(self):
        """When NLM returns empty, Claude answer passes through."""
        from core.research.synthesizer import ResearchSynthesizer

        synth = ResearchSynthesizer()
        result = synth.synthesize(
            claude_result={"answer": "Claude says PAR is 3.6%", "citations": []},
            nlm_result={"answer": "", "sources": []},
            question="What is PAR?",
        )
        assert result["engine"] == "claude"
        assert "Claude" in result["answer"]


# ── DualResearchEngine tests ────────────────────────────────────────────────

class TestDualResearchEngine:
    """Test the dual engine orchestration."""

    def test_nlm_status_when_not_initialized(self):
        """get_nlm_status works before NLM is probed."""
        from core.research.dual_engine import DualResearchEngine

        engine = DualResearchEngine.__new__(DualResearchEngine)
        engine.nlm_engine = None
        engine._nlm_checked = False
        engine.claude_engine = MagicMock()
        engine.synthesizer = MagicMock()

        # Mock the init to avoid real NLM probing
        with patch.object(DualResearchEngine, '_try_init_nlm'):
            engine._nlm_checked = True
            status = engine.get_nlm_status()
            assert status["available"] is False

    def test_query_returns_nlm_metadata(self):
        """Query result includes NLM availability and conversation fields."""
        from core.research.dual_engine import DualResearchEngine

        engine = DualResearchEngine.__new__(DualResearchEngine)
        engine._nlm_checked = True
        engine.nlm_engine = None
        engine.synthesizer = MagicMock()

        # Mock Claude engine
        engine.claude_engine = MagicMock()
        engine.claude_engine.query.return_value = {
            "answer": "Claude says yes",
            "citations": [],
            "engine": "claude",
            "chunks_searched": 5,
            "mind_context_used": False,
        }

        result = engine.query("klaim", "UAE_healthcare", "test question")

        assert result["engine"] == "claude"
        assert result["nlm_available"] is False
        assert result["nlm_references"] == []
        assert result["nlm_conversation_id"] is None
        assert result["nlm_answer"] is None


# ── Citation merging tests ───────────────────────────────────────────────────

class TestCitationMerging:
    """Test that merged citations preserve origin tags."""

    def test_merged_citations_have_origin_tags(self):
        """Both Claude and NLM citations get origin tags."""
        from core.research.synthesizer import ResearchSynthesizer

        synth = ResearchSynthesizer()
        combined = synth._merge_citations(
            claude_citations=[
                {"index": 1, "doc_id": "d1", "filename": "report.pdf", "snippet": "text"},
            ],
            nlm_sources=[
                {"source_id": "s1", "citation_number": 1, "cited_text": "nlm text"},
            ],
        )

        assert len(combined) == 2
        assert combined[0]["origin"] == "claude"
        assert combined[1]["origin"] == "notebooklm"
        # Re-numbered sequentially
        assert combined[0]["index"] == 1
        assert combined[1]["index"] == 2


# ── NLM Warning tests ────────────────────────────────────────────────────────

class TestNLMWarning:
    """Test that NLM unavailability produces actionable warnings."""

    def test_get_warning_returns_none_when_available(self):
        from core.research.notebooklm_bridge import NotebookLMEngine
        engine = NotebookLMEngine.__new__(NotebookLMEngine)
        engine.available = True
        assert engine.get_warning() is None

    def test_get_warning_returns_auth_code_when_installed(self):
        from core.research.notebooklm_bridge import NotebookLMEngine
        engine = NotebookLMEngine.__new__(NotebookLMEngine)
        engine.available = False
        engine._use_python = True
        engine._use_cli = False
        warning = engine.get_warning()
        assert warning["code"] == "nlm_auth_expired"
        assert "notebooklm login" in warning["fix"]

    def test_get_warning_returns_not_installed_code(self):
        from core.research.notebooklm_bridge import NotebookLMEngine
        engine = NotebookLMEngine.__new__(NotebookLMEngine)
        engine.available = False
        engine._use_python = False
        engine._use_cli = False
        warning = engine.get_warning()
        assert warning["code"] == "nlm_not_installed"
        assert "pip install" in warning["fix"]

    def test_dual_engine_query_includes_warning_when_unavailable(self):
        from core.research.dual_engine import DualResearchEngine
        engine = DualResearchEngine.__new__(DualResearchEngine)
        engine._nlm_checked = True
        engine.nlm_engine = None
        engine.synthesizer = MagicMock()
        engine.claude_engine = MagicMock()
        engine.claude_engine.query.return_value = {
            "answer": "Claude answer",
            "citations": [],
            "engine": "claude",
            "chunks_searched": 3,
            "mind_context_used": False,
        }
        result = engine.query("klaim", "UAE_healthcare", "test")
        assert result["nlm_warning"] is not None
        assert result["nlm_warning"]["code"] == "nlm_not_installed"

    def test_dual_engine_query_no_warning_when_nlm_disabled(self):
        from core.research.dual_engine import DualResearchEngine
        engine = DualResearchEngine.__new__(DualResearchEngine)
        engine._nlm_checked = True
        engine.nlm_engine = None
        engine.synthesizer = MagicMock()
        engine.claude_engine = MagicMock()
        engine.claude_engine.query.return_value = {
            "answer": "Claude answer",
            "citations": [],
            "engine": "claude",
            "chunks_searched": 3,
            "mind_context_used": False,
        }
        result = engine.query("klaim", "UAE_healthcare", "test",
                              use_notebooklm=False)
        assert result.get("nlm_warning") is None
