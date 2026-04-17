"""Tests for the 5 memo pipeline enhancements:

  #1 analytics.get_metric_trend tool registration
  #2 Citation validation pass
  #3 Research pack sidecar storage
  #4 Thesis recording to Company Mind
  #5 Contradiction handling in polish pass
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.memo import agent_research
from core.memo.agent_research import (
    EMPTY_PACK,
    record_memo_thesis_to_mind,
)
from core.memo.generator import MemoGenerator
from core.memo.storage import MemoStorage
from core.memo.templates import MEMO_TEMPLATES


# ── #1: Trend tool registration + behaviour ─────────────────────────────────

class TestMetricTrendTool:
    def test_tool_is_registered(self):
        # Import the module to trigger registration
        import core.agents.tools.analytics  # noqa: F401
        from core.agents.tools import registry
        assert "analytics.get_metric_trend" in registry.tool_names()

    def test_unknown_metric_returns_helpful_message(self, monkeypatch):
        import core.agents.tools.analytics as mod
        result = mod._get_metric_trend("TestCo", "KSA", metric="not_a_metric")
        assert "Unknown metric" in result
        assert "collection_rate" in result  # lists valid options

    def test_summary_only_type_returns_note(self, monkeypatch):
        import core.agents.tools.analytics as mod
        # Force ejari_summary detection
        monkeypatch.setattr(mod, "detect_analysis_type",
                            lambda co, p: "ejari_summary")
        # get_snapshots returns something so the early-return fires
        monkeypatch.setattr("core.loader.get_snapshots",
                            lambda co, p: [{"filename": "x.ods", "filepath": "x.ods", "date": "2026-01-01"}])
        result = mod._get_metric_trend("Ejari", "RNPL", metric="collection_rate")
        assert "pre-computed summaries" in result or "raw tape" in result

    def test_no_snapshots_returns_note(self, monkeypatch):
        import core.agents.tools.analytics as mod
        monkeypatch.setattr("core.loader.get_snapshots", lambda co, p: [])
        result = mod._get_metric_trend("Fake", "KSA", metric="collection_rate")
        assert "No snapshots" in result


# ── #2: Citation validation pass ────────────────────────────────────────────

class TestCitationValidation:
    def test_empty_memo_returns_no_issues(self):
        gen = MemoGenerator()
        memo = {"sections": [{"key": "exec_summary", "citations": []}]}
        issues = gen._validate_citations(memo, "TestCo", "KSA")
        assert issues == []

    def test_no_dataroom_returns_no_issues(self, monkeypatch):
        gen = MemoGenerator()
        gen._dataroom = None  # simulate missing data room engine
        memo = {"sections": [{"key": "exec_summary",
                              "citations": [{"source": "x.pdf", "snippet": "..."}]}]}
        issues = gen._validate_citations(memo, "TestCo", "KSA")
        assert issues == []

    def test_parses_issues_from_sonnet_response(self, monkeypatch):
        gen = MemoGenerator()
        gen._dataroom = MagicMock()
        gen._dataroom.search.return_value = [
            {"source_file": "x.pdf", "text": "sample", "score": 0.8},
        ]

        fake_response = MagicMock()
        fake_response.content = [MagicMock(text=json.dumps({
            "issues": [
                {"section_key": "exec_summary", "citation_index": 0,
                 "source": "fake.pdf", "reason": "not in data room",
                 "severity": "high"},
            ]
        }))]
        fake_response.usage = MagicMock(input_tokens=100, output_tokens=50,
                                        cache_read_input_tokens=0, cache_creation_input_tokens=0)
        fake_response._laith_metadata = {"tier": "structured", "model": "sonnet", "elapsed_s": 0.1}

        monkeypatch.setattr("core.ai_client.complete", lambda **kw: fake_response)

        memo = {
            "sections": [{
                "key": "exec_summary",
                "citations": [{"source": "fake.pdf", "snippet": "some claim"}]
            }]
        }
        issues = gen._validate_citations(memo, "TestCo", "KSA")
        assert len(issues) == 1
        assert issues[0]["section_key"] == "exec_summary"
        assert issues[0]["severity"] == "high"

    def test_handles_malformed_json_from_validator(self, monkeypatch):
        gen = MemoGenerator()
        gen._dataroom = MagicMock()
        gen._dataroom.search.return_value = [{"source_file": "x.pdf", "text": "s"}]

        fake_response = MagicMock()
        fake_response.content = [MagicMock(text="this is not json at all")]
        fake_response.usage = MagicMock(input_tokens=50, output_tokens=20,
                                        cache_read_input_tokens=0, cache_creation_input_tokens=0)
        fake_response._laith_metadata = {"tier": "structured", "model": "sonnet", "elapsed_s": 0.1}

        monkeypatch.setattr("core.ai_client.complete", lambda **kw: fake_response)

        memo = {
            "sections": [{
                "key": "exec_summary",
                "citations": [{"source": "x.pdf", "snippet": "claim"}]
            }]
        }
        issues = gen._validate_citations(memo, "TestCo", "KSA")
        assert issues == []  # Graceful degradation — no issues rather than crash


# ── #3: Research pack sidecar storage ───────────────────────────────────────

class TestResearchPackSidecar:
    def test_save_writes_sidecar_file(self, tmp_path, monkeypatch):
        # Point MemoStorage at tmp_path
        storage = MemoStorage(base_dir=tmp_path)

        memo = {
            "id": "memo-abc123",
            "company": "TestCo",
            "product": "KSA",
            "template": "credit_memo",
            "template_name": "Credit Memo",
            "title": "Test Memo",
            "status": "draft",
            "sections": [],
            "_research_packs": {
                "exec_summary": {
                    "recommended_stance": "Invest",
                    "key_metrics": [{"label": "PAR30", "value": "3%"}],
                    "contradictions": [],
                    "quotes": [],
                    "supporting_evidence": ["strong"],
                }
            },
        }
        storage.save(memo)

        sidecar = tmp_path / "TestCo_KSA" / "memo-abc123" / "research_packs.json"
        assert sidecar.exists()
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        assert "exec_summary" in data
        assert data["exec_summary"]["recommended_stance"] == "Invest"

    def test_save_strips_transient_fields_from_version_json(self, tmp_path):
        storage = MemoStorage(base_dir=tmp_path)
        memo = {
            "id": "memo-xyz",
            "company": "TestCo", "product": "KSA",
            "template": "credit_memo", "template_name": "Credit Memo",
            "title": "Test", "status": "draft", "sections": [],
            "_research_packs": {"exec_summary": {"recommended_stance": "Pass"}},
            "_citation_issues": [{"section_key": "x", "citation_index": 0}],
        }
        storage.save(memo)

        v1 = tmp_path / "TestCo_KSA" / "memo-xyz" / "v1.json"
        saved = json.loads(v1.read_text(encoding="utf-8"))
        assert "_research_packs" not in saved
        assert "_citation_issues" not in saved

    def test_sidecar_only_written_on_first_save(self, tmp_path):
        """Second save (e.g., after analyst edit) should not overwrite packs."""
        storage = MemoStorage(base_dir=tmp_path)
        memo = {
            "id": "memo-multi",
            "company": "TestCo", "product": "KSA",
            "template": "credit_memo", "template_name": "Credit Memo",
            "title": "Test", "status": "draft", "sections": [],
            "_research_packs": {"exec_summary": {"recommended_stance": "Invest"}},
        }
        storage.save(memo)
        sidecar = tmp_path / "TestCo_KSA" / "memo-multi" / "research_packs.json"
        original_mtime = sidecar.stat().st_mtime

        # Re-save with different packs — original sidecar should persist
        memo2 = {**memo, "_research_packs": {"exec_summary": {"recommended_stance": "Pass"}}}
        memo2.pop("version", None)
        storage.save(memo2)

        # Sidecar mtime unchanged (we preserve the original audit trail)
        assert sidecar.stat().st_mtime == original_mtime
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        assert data["exec_summary"]["recommended_stance"] == "Invest"


# ── #4: Thesis recording to Company Mind ────────────────────────────────────

class TestThesisRecording:
    def test_returns_none_without_packs(self):
        memo = {"id": "m1", "company": "TestCo", "product": "KSA", "title": "Test"}
        result = record_memo_thesis_to_mind(memo, research_packs={})
        assert result is None

    def test_returns_none_with_invalid_stance(self):
        memo = {"id": "m1", "company": "TestCo", "product": "KSA", "title": "Test"}
        packs = {"exec_summary": {"recommended_stance": "Maybe"}}
        result = record_memo_thesis_to_mind(memo, research_packs=packs)
        assert result is None  # "Maybe" is not a valid stance

    def test_records_finding_to_company_mind(self, monkeypatch):
        recorded = []

        class FakeEntry:
            id = "mind-entry-1"

        class FakeCompanyMind:
            def __init__(self, company, product):
                self.company = company
                self.product = product

            def record_research_finding(self, finding, confidence="medium", source_docs=None):
                recorded.append({
                    "finding": finding,
                    "confidence": confidence,
                    "source_docs": source_docs or [],
                    "company": self.company,
                    "product": self.product,
                })
                return FakeEntry()

        monkeypatch.setattr("core.mind.company_mind.CompanyMind", FakeCompanyMind)

        memo = {
            "id": "memo-42",
            "company": "TestCo",
            "product": "KSA",
            "title": "Credit Memo — TestCo KSA",
        }
        packs = {
            "investment_thesis": {
                "recommended_stance": "Conditional Invest",
                "key_metrics": [{"label": "PAR30", "value": "3.2%"}],
                "supporting_evidence": ["Top-quartile collection"],
                "contradictions": [],
                "quotes": [],
            }
        }
        entry_id = record_memo_thesis_to_mind(memo, research_packs=packs)
        assert entry_id == "mind-entry-1"
        assert len(recorded) == 1
        assert recorded[0]["company"] == "TestCo"
        assert recorded[0]["product"] == "KSA"
        assert "Conditional Invest" in recorded[0]["finding"]
        assert "PAR30" in recorded[0]["finding"]
        assert "memo:memo-42" in recorded[0]["source_docs"]

    def test_prefers_investment_thesis_over_exec_summary(self, monkeypatch):
        recorded = []

        class FakeEntry:
            id = "e1"

        class FakeCompanyMind:
            def __init__(self, company, product):
                pass
            def record_research_finding(self, finding, **kw):
                recorded.append(finding)
                return FakeEntry()

        monkeypatch.setattr("core.mind.company_mind.CompanyMind", FakeCompanyMind)

        memo = {"id": "m", "company": "C", "product": "P", "title": "T"}
        packs = {
            "exec_summary": {"recommended_stance": "Monitor",
                             "key_metrics": [], "supporting_evidence": [],
                             "contradictions": [], "quotes": []},
            "investment_thesis": {"recommended_stance": "Invest",
                                  "key_metrics": [], "supporting_evidence": [],
                                  "contradictions": [], "quotes": []},
        }
        record_memo_thesis_to_mind(memo, research_packs=packs)
        # Should use investment_thesis (higher priority)
        assert "Invest" in recorded[0]
        assert "investment_thesis" in recorded[0]

    def test_failure_does_not_raise(self, monkeypatch):
        """CompanyMind failure must not break memo save."""
        def _raise(*a, **kw):
            raise RuntimeError("mind crashed")
        monkeypatch.setattr("core.mind.company_mind.CompanyMind", _raise)

        memo = {"id": "m", "company": "C", "product": "P", "title": "T"}
        packs = {"exec_summary": {"recommended_stance": "Invest",
                                  "key_metrics": [], "supporting_evidence": [],
                                  "contradictions": [], "quotes": []}}
        result = record_memo_thesis_to_mind(memo, research_packs=packs)
        assert result is None  # graceful degradation


# ── #5: Contradiction handling in polish pass ───────────────────────────────

class TestContradictionHandlingInPolish:
    def test_contradictions_injected_into_user_prompt(self, monkeypatch):
        """When research packs contain contradictions, polish prompt must surface them."""
        captured_prompts = []

        def _fake_complete(*, tier, system, messages, max_tokens, **kwargs):
            captured_prompts.append({
                "tier": tier,
                "system": system,
                "user": messages[-1]["content"] if messages else "",
            })
            fake_resp = MagicMock()
            fake_resp.content = [MagicMock(text=json.dumps({"sections": []}))]
            fake_resp.usage = MagicMock(input_tokens=100, output_tokens=50,
                                        cache_read_input_tokens=0, cache_creation_input_tokens=0)
            fake_resp._laith_metadata = {"tier": tier, "model": "opus", "elapsed_s": 0.1}
            return fake_resp

        monkeypatch.setattr("core.ai_client.complete", _fake_complete)
        monkeypatch.setattr("core.mind.build_mind_context",
                            lambda **kw: MagicMock(is_empty=True, formatted="", total_entries=0))

        gen = MemoGenerator()
        memo = {
            "id": "m1",
            "company": "TestCo",
            "product": "KSA",
            "template_name": "Credit Memo",
            "sections": [
                {"key": "exec_summary", "title": "Executive Summary",
                 "content": "Strong performance", "metrics": [], "citations": []}
            ],
            "_research_packs": {
                "exec_summary": {
                    "recommended_stance": "Invest",
                    "key_metrics": [], "quotes": [],
                    "supporting_evidence": [],
                    "contradictions": [
                        {"description": "Tape says PAR30=3%, report says 5%",
                         "section_a": "Credit Quality", "section_b": "Executive Summary",
                         "severity": "high"},
                    ],
                },
            },
        }

        gen._polish_memo(memo)

        # Polish call was made with our contradictions surfaced
        assert captured_prompts
        polish_prompt = captured_prompts[0]["user"]
        assert "CONTRADICTIONS DETECTED" in polish_prompt
        assert "PAR30=3%" in polish_prompt
        assert "HIGH" in polish_prompt
        # Also test that the system prompt has contradiction-resolution guidance
        sys = captured_prompts[0]["system"]
        sys_text = sys[0]["text"] if isinstance(sys, list) else sys
        assert "authoritative" in sys_text.lower() or "resolve" in sys_text.lower()

    def test_no_contradictions_yields_no_contradictions_block(self, monkeypatch):
        captured = []
        def _fake_complete(**kw):
            captured.append(kw["messages"][-1]["content"])
            fake = MagicMock()
            fake.content = [MagicMock(text=json.dumps({"sections": []}))]
            fake.usage = MagicMock(input_tokens=50, output_tokens=20,
                                   cache_read_input_tokens=0, cache_creation_input_tokens=0)
            fake._laith_metadata = {"tier": "polish", "model": "opus", "elapsed_s": 0.1}
            return fake

        monkeypatch.setattr("core.ai_client.complete", _fake_complete)
        monkeypatch.setattr("core.mind.build_mind_context",
                            lambda **kw: MagicMock(is_empty=True, formatted="", total_entries=0))

        gen = MemoGenerator()
        memo = {
            "id": "m", "company": "C", "product": "P", "template_name": "Credit Memo",
            "sections": [{"key": "exec_summary", "title": "T", "content": "x", "metrics": [], "citations": []}],
            "_research_packs": {},
        }
        gen._polish_memo(memo)
        assert "CONTRADICTIONS DETECTED" not in captured[0]

    def test_citation_issues_surfaced_in_polish(self, monkeypatch):
        captured = []
        def _fake_complete(**kw):
            captured.append(kw["messages"][-1]["content"])
            fake = MagicMock()
            fake.content = [MagicMock(text=json.dumps({"sections": []}))]
            fake.usage = MagicMock(input_tokens=50, output_tokens=20,
                                   cache_read_input_tokens=0, cache_creation_input_tokens=0)
            fake._laith_metadata = {"tier": "polish", "model": "opus", "elapsed_s": 0.1}
            return fake

        monkeypatch.setattr("core.ai_client.complete", _fake_complete)
        monkeypatch.setattr("core.mind.build_mind_context",
                            lambda **kw: MagicMock(is_empty=True, formatted="", total_entries=0))

        gen = MemoGenerator()
        memo = {
            "id": "m", "company": "C", "product": "P", "template_name": "Credit Memo",
            "sections": [{"key": "exec_summary", "title": "T", "content": "x", "metrics": [], "citations": []}],
            "_citation_issues": [
                {"section_key": "exec_summary", "citation_index": 0,
                 "source": "fake.pdf", "reason": "not in data room", "severity": "high"},
            ],
        }
        gen._polish_memo(memo)
        assert "CITATIONS FLAGGED BY VALIDATION" in captured[0]
        assert "fake.pdf" in captured[0]
