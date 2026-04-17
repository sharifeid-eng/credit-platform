"""Tests for core.memo.agent_research — research pack parsing + format helper."""

from __future__ import annotations

import json

import pytest

from core.memo import agent_research


# ── Parser robustness ───────────────────────────────────────────────────────

class TestParsePack:
    def test_strict_json(self):
        raw = json.dumps({
            "key_metrics": [{"label": "PAR30", "value": "3.2%", "source": "tape"}],
            "quotes": [],
            "contradictions": [],
            "recommended_stance": "Invest",
            "supporting_evidence": ["solid collection rate"],
        })
        pack = agent_research._parse_pack(raw)
        assert pack["recommended_stance"] == "Invest"
        assert len(pack["key_metrics"]) == 1
        assert pack["supporting_evidence"] == ["solid collection rate"]

    def test_json_fenced(self):
        raw = "Some preamble text\n\n```json\n" + json.dumps({
            "recommended_stance": "Pass",
        }) + "\n```\nTrailing commentary"
        pack = agent_research._parse_pack(raw)
        assert pack["recommended_stance"] == "Pass"

    def test_brute_force_substring(self):
        raw = 'Here is the pack: {"recommended_stance":"Monitor","key_metrics":[]} thanks'
        pack = agent_research._parse_pack(raw)
        assert pack["recommended_stance"] == "Monitor"

    def test_garbage_returns_empty_pack(self):
        pack = agent_research._parse_pack("No JSON in this text whatsoever")
        assert pack == agent_research.EMPTY_PACK

    def test_empty_string_returns_empty_pack(self):
        pack = agent_research._parse_pack("")
        assert pack == agent_research.EMPTY_PACK

    def test_invalid_stance_is_discarded(self):
        raw = json.dumps({"recommended_stance": "Definitely Invest Big Time"})
        pack = agent_research._parse_pack(raw)
        assert pack["recommended_stance"] == "Monitor"  # default


class TestNormalizePack:
    def test_filters_non_dict_metrics(self):
        obj = {"key_metrics": [{"label": "a"}, "not a dict", {"label": "b"}]}
        pack = agent_research._normalize_pack(obj)
        assert len(pack["key_metrics"]) == 2

    def test_caps_list_sizes(self):
        obj = {"key_metrics": [{"label": f"m{i}"} for i in range(20)]}
        pack = agent_research._normalize_pack(obj)
        assert len(pack["key_metrics"]) == 10  # capped at 10

    def test_stance_must_be_valid(self):
        pack = agent_research._normalize_pack({"recommended_stance": "Invest"})
        assert pack["recommended_stance"] == "Invest"
        pack = agent_research._normalize_pack({"recommended_stance": "bogus"})
        assert pack["recommended_stance"] == "Monitor"


# ── Format helper ───────────────────────────────────────────────────────────

class TestFormatPackForPrompt:
    def test_empty_pack_returns_empty_string(self):
        assert agent_research.format_pack_for_prompt(agent_research.EMPTY_PACK) == ""

    def test_metric_rendering(self):
        pack = {
            "key_metrics": [{"label": "PAR30", "value": "3%", "significance": "healthy", "source": "tape"}],
            "quotes": [],
            "contradictions": [],
            "recommended_stance": "Invest",
            "supporting_evidence": [],
        }
        out = agent_research.format_pack_for_prompt(pack)
        assert "PAR30" in out
        assert "3%" in out
        assert "Invest" in out

    def test_quote_rendering(self):
        pack = {
            "key_metrics": [],
            "quotes": [{"text": "strong growth", "source_doc": "HSBC.pdf", "page_or_section": "p.5"}],
            "contradictions": [],
            "recommended_stance": "Invest",
            "supporting_evidence": [],
        }
        out = agent_research.format_pack_for_prompt(pack)
        assert "strong growth" in out
        assert "HSBC.pdf" in out

    def test_contradiction_rendering(self):
        pack = {
            "key_metrics": [],
            "quotes": [],
            "contradictions": [{"description": "mismatch", "section_a": "A", "section_b": "B", "severity": "high"}],
            "recommended_stance": "Pass",
            "supporting_evidence": [],
        }
        out = agent_research.format_pack_for_prompt(pack)
        assert "mismatch" in out
        assert "HIGH" in out


# ── End-to-end smoke (mocked) ───────────────────────────────────────────────

class TestGenerateResearchPack:
    def test_returns_empty_pack_on_agent_error(self, monkeypatch):
        """Agent errors should degrade gracefully to EMPTY_PACK, not raise."""
        def _fail(*args, **kwargs):
            raise RuntimeError("agent crashed")
        monkeypatch.setattr("core.agents.internal._run_agent_sync", _fail)
        pack = agent_research.generate_research_pack(
            company="X", product="Y",
            section_key="exec_summary", section_title="Executive Summary",
            section_guidance="Summarise",
            body_so_far=[],
            mind_ctx="",
            max_turns=3,
        )
        assert pack == agent_research.EMPTY_PACK

    def test_parses_agent_output(self, monkeypatch):
        agent_response = json.dumps({
            "key_metrics": [{"label": "Collection Rate", "value": "87%"}],
            "quotes": [],
            "contradictions": [],
            "recommended_stance": "Conditional Invest",
            "supporting_evidence": ["top quartile"],
        })
        monkeypatch.setattr("core.agents.internal._run_agent_sync",
                            lambda *a, **k: agent_response)
        pack = agent_research.generate_research_pack(
            company="X", product="Y",
            section_key="exec_summary", section_title="Executive Summary",
            section_guidance="Summarise",
            body_so_far=[],
            mind_ctx="",
            max_turns=3,
        )
        assert pack["recommended_stance"] == "Conditional Invest"
        assert pack["key_metrics"][0]["label"] == "Collection Rate"
