"""Tests for the hybrid memo generation pipeline (core.memo.generator).

These tests mock the AI calls and assert:
- Section tier classification uses template metadata correctly
- Parallel fan-out for structured sections preserves template order
- Judgment sections run sequentially with body context
- Polish pass is invoked and preserves metrics/citations
- Generation metadata is recorded per section and at memo level
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from core.memo import generator as gen_module
from core.memo.generator import MemoGenerator, classify_section
from core.memo.templates import MEMO_TEMPLATES


# ── Tier classification ─────────────────────────────────────────────────────

class TestClassifySection:
    def test_auto_source_is_auto_tier(self):
        assert classify_section({"source": "auto", "ai_guided": False}) == "auto"

    def test_ai_guided_is_judgment(self):
        assert classify_section({"source": "mixed", "ai_guided": True}) == "judgment"

    def test_default_is_structured(self):
        assert classify_section({"source": "analytics", "ai_guided": False}) == "structured"
        assert classify_section({"source": "dataroom", "ai_guided": False}) == "structured"
        assert classify_section({"source": "mixed", "ai_guided": False}) == "structured"

    def test_credit_memo_has_expected_distribution(self):
        tmpl = MEMO_TEMPLATES["credit_memo"]
        tiers = [classify_section(s) for s in tmpl["sections"]]
        assert tiers.count("judgment") == 2   # exec_summary + investment_thesis
        assert tiers.count("auto") == 1       # appendix
        assert tiers.count("structured") == len(tmpl["sections"]) - 3


# ── Full pipeline (all stages mocked) ───────────────────────────────────────

def _fake_claude_response(content_json: dict, input_tokens=500, output_tokens=400,
                          model="claude-sonnet-4-6"):
    """Build a mock Anthropic Message that looks like a section response."""
    resp = MagicMock()
    resp.content = [MagicMock(text=json.dumps(content_json))]
    resp.usage = MagicMock(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
    )
    resp._laith_metadata = {
        "tier": "structured",
        "model": model,
        "elapsed_s": 0.1,
        "cache_read_tokens": 0,
        "cache_created_tokens": 0,
    }
    return resp


class TestGenerateFullMemo:
    @pytest.fixture
    def mock_bridge(self):
        bridge = MagicMock()
        bridge.get_section_context.return_value = {
            "available": True,
            "text": "mock analytics",
            "metrics": [{"label": "PAR30", "value": "3%", "assessment": "healthy"}],
        }
        return bridge

    @pytest.fixture
    def mock_dataroom(self):
        dr = MagicMock()
        dr.search.return_value = [
            {"source_file": "doc.pdf", "text": "sample chunk", "score": 0.9},
        ]
        dr.catalog.return_value = {"documents": [{"filename": "doc.pdf", "type": "pdf"}]}
        return dr

    def test_full_credit_memo_generates_all_sections(self, mock_bridge, mock_dataroom,
                                                     monkeypatch):
        """End-to-end: all 12 sections present, models recorded, polish applied."""
        # Patch the bridge and dataroom on the generator
        monkeypatch.setattr("core.memo.generator.AnalyticsBridge",
                            lambda: mock_bridge)
        monkeypatch.setattr("core.dataroom.DataRoomEngine", lambda: mock_dataroom)

        # Patch mind context to be a no-op
        monkeypatch.setattr("core.mind.build_mind_context",
                            lambda **kw: MagicMock(
                                is_empty=True, formatted="", total_entries=0))

        # Patch complete() to return a section-shaped response
        def _fake_complete(*, tier, system, messages, max_tokens, **kwargs):
            # Polish pass returns different schema
            if "polish" in (kwargs.get("log_prefix") or "") or tier == "polish":
                return _fake_claude_response({
                    "sections": [
                        {"key": s["key"], "content": f"polished {s['key']}"}
                        for s in MEMO_TEMPLATES["credit_memo"]["sections"]
                    ],
                })
            return _fake_claude_response({
                "content": "Section body text with [PAR30: 3%] metric.",
                "metrics": [{"label": "PAR30", "value": "3%", "assessment": "healthy"}],
                "citations": [{"index": 1, "source": "doc.pdf", "snippet": "..."}],
            }, model={
                "auto": "claude-haiku-4-5",
                "structured": "claude-sonnet-4-6",
                "judgment": "claude-opus-4-7",
            }.get(tier, "claude-sonnet-4-6"))

        monkeypatch.setattr("core.memo.generator.complete", _fake_complete, raising=False)
        # complete() is imported at call time inside generator methods —
        # patch the module-level import in ai_client
        monkeypatch.setattr("core.ai_client.complete", _fake_complete)

        # Skip research packs (short-circuit to EMPTY_PACK)
        from core.memo import agent_research
        monkeypatch.setattr(agent_research, "generate_research_pack",
                            lambda **kw: dict(agent_research.EMPTY_PACK))

        gen = MemoGenerator()
        memo = gen.generate_full_memo(
            company="TestCo", product="KSA",
            template_key="credit_memo",
            polish=True,
        )

        # All 12 sections present, in template order
        expected_keys = [s["key"] for s in MEMO_TEMPLATES["credit_memo"]["sections"]]
        actual_keys = [s["key"] for s in memo["sections"]]
        assert actual_keys == expected_keys

        # Generation mode and polish metadata recorded
        assert memo["generation_mode"] == "hybrid-v1"
        assert memo["polished"] is True
        assert memo["generation_meta"]["total_tokens_in"] > 0

        # Models used tallied across sections
        assert len(memo["models_used"]) >= 1

        # Cost estimate present
        assert "cost_usd_estimate" in memo["generation_meta"]

    def test_polish_disabled_skips_polish(self, mock_bridge, mock_dataroom, monkeypatch):
        monkeypatch.setattr("core.memo.generator.AnalyticsBridge", lambda: mock_bridge)
        monkeypatch.setattr("core.dataroom.DataRoomEngine", lambda: mock_dataroom)
        monkeypatch.setattr("core.mind.build_mind_context",
                            lambda **kw: MagicMock(is_empty=True, formatted="", total_entries=0))

        def _fake_complete(**kwargs):
            return _fake_claude_response({
                "content": "body", "metrics": [], "citations": [],
            })
        monkeypatch.setattr("core.ai_client.complete", _fake_complete)

        from core.memo import agent_research
        monkeypatch.setattr(agent_research, "generate_research_pack",
                            lambda **kw: dict(agent_research.EMPTY_PACK))

        gen = MemoGenerator()
        memo = gen.generate_full_memo(
            company="TestCo", product="KSA",
            template_key="credit_memo",
            polish=False,
        )
        assert memo["polished"] is False
        # No polish metadata
        assert "polish" not in memo.get("generation_meta", {})

    def test_progress_callback_receives_events(self, mock_bridge, mock_dataroom, monkeypatch):
        monkeypatch.setattr("core.memo.generator.AnalyticsBridge", lambda: mock_bridge)
        monkeypatch.setattr("core.dataroom.DataRoomEngine", lambda: mock_dataroom)
        monkeypatch.setattr("core.mind.build_mind_context",
                            lambda **kw: MagicMock(is_empty=True, formatted="", total_entries=0))

        def _fake_complete(**kwargs):
            return _fake_claude_response({
                "content": "body", "metrics": [], "citations": [],
            })
        monkeypatch.setattr("core.ai_client.complete", _fake_complete)

        from core.memo import agent_research
        monkeypatch.setattr(agent_research, "generate_research_pack",
                            lambda **kw: dict(agent_research.EMPTY_PACK))

        events = []
        def cb(event_type, payload):
            events.append((event_type, payload))

        gen = MemoGenerator()
        gen.generate_full_memo(
            company="TestCo", product="KSA",
            template_key="credit_memo",
            polish=False,
            progress_cb=cb,
        )

        event_types = [e[0] for e in events]
        assert "pipeline_start" in event_types
        assert "section_start" in event_types
        assert "section_done" in event_types
        assert "pipeline_done" in event_types

    def test_parallel_failure_does_not_truncate_pipeline(self, mock_bridge,
                                                          mock_dataroom, monkeypatch):
        """Regression: a BaseException escaping a Stage 2 worker must not
        short-circuit the pipeline (2026-04-18 bug where ~9 of 12 sections
        were missing and downstream stages silently skipped). The defensive
        layer catches the exception, backfills the slot with an error
        placeholder, and lets citation audit + polish run on the rest.

        We simulate the production failure mode by making one section's
        `generate_section` raise `SystemExit` — a BaseException that bypasses
        the inner `except Exception` in `_worker`, reaches `fut.result()`,
        and is caught by the new `except BaseException` in the `as_completed`
        loop.
        """
        monkeypatch.setattr("core.memo.generator.AnalyticsBridge", lambda: mock_bridge)
        monkeypatch.setattr("core.dataroom.DataRoomEngine", lambda: mock_dataroom)
        monkeypatch.setattr("core.mind.build_mind_context",
                            lambda **kw: MagicMock(
                                is_empty=True, formatted="", total_entries=0))

        # Normal complete() for everything that does get called
        def _fake_complete(*, tier, system, messages, max_tokens, **kwargs):
            if tier == "polish":
                return _fake_claude_response({
                    "sections": [
                        {"key": s["key"], "content": f"polished {s['key']}"}
                        for s in MEMO_TEMPLATES["credit_memo"]["sections"]
                    ],
                })
            return _fake_claude_response({
                "content": "Section body text.",
                "metrics": [], "citations": [],
            })
        monkeypatch.setattr("core.ai_client.complete", _fake_complete)

        from core.memo import agent_research
        monkeypatch.setattr(agent_research, "generate_research_pack",
                            lambda **kw: dict(agent_research.EMPTY_PACK))

        target_key = "portfolio_analytics"

        gen = MemoGenerator()

        # Wrap generate_section so calls for the target key raise SystemExit,
        # which bypasses the `except Exception` inside _worker.
        real_generate_section = gen.generate_section
        def _flaky_generate_section(*args, **kwargs):
            if kwargs.get("section_key") == target_key:
                raise SystemExit(f"simulated worker kill on {target_key}")
            return real_generate_section(*args, **kwargs)
        monkeypatch.setattr(gen, "generate_section", _flaky_generate_section)

        events = []
        def cb(event_type, payload):
            events.append((event_type, payload))

        memo = gen.generate_full_memo(
            company="TestCo", product="KSA",
            template_key="credit_memo",
            polish=True,
            progress_cb=cb,
        )

        # All 12 sections present in template order — no silent truncation
        expected_keys = [s["key"] for s in MEMO_TEMPLATES["credit_memo"]["sections"]]
        assert [s["key"] for s in memo["sections"]] == expected_keys

        # The targeted section is a backfilled error placeholder.
        # Note: polish appends "+polished" to generated_by, so match by prefix.
        error_section_keys = {s["key"] for s in memo["sections"]
                              if (s.get("generated_by") or "").startswith("error")}
        assert target_key in error_section_keys

        # Every other section has real content
        good_sections = [s for s in memo["sections"]
                         if not (s.get("generated_by") or "").startswith("error")]
        assert len(good_sections) >= 10
        assert all(s.get("content") for s in good_sections)

        # Downstream stages still ran — polish applied despite the error
        assert memo["polished"] is True, \
            "Polish must run as long as SOME section has content"

        # Errors recorded with stage attribution
        assert len(memo["errors"]) >= 1
        error_stages = {e.get("stage") for e in memo["errors"]}
        assert error_stages & {"parallel_future", "parallel_backfill"}, \
            f"Expected parallel_future or parallel_backfill stage; got {error_stages}"

        # section_error SSE event emitted for the backfilled slot
        event_types = [e[0] for e in events]
        assert "section_error" in event_types, \
            f"Expected section_error event; got unique: {set(event_types)}"

    def test_section_order_matches_template(self, mock_bridge, mock_dataroom, monkeypatch):
        """Parallel fan-out must not scramble section order."""
        monkeypatch.setattr("core.memo.generator.AnalyticsBridge", lambda: mock_bridge)
        monkeypatch.setattr("core.dataroom.DataRoomEngine", lambda: mock_dataroom)
        monkeypatch.setattr("core.mind.build_mind_context",
                            lambda **kw: MagicMock(is_empty=True, formatted="", total_entries=0))

        # Make different sections take different times — stress-tests ordering
        call_count = {"n": 0}
        def _fake_complete(**kwargs):
            import time
            call_count["n"] += 1
            # Alternate slow/fast calls
            if call_count["n"] % 2 == 0:
                time.sleep(0.05)
            return _fake_claude_response({
                "content": f"body {call_count['n']}",
                "metrics": [], "citations": [],
            })
        monkeypatch.setattr("core.ai_client.complete", _fake_complete)

        from core.memo import agent_research
        monkeypatch.setattr(agent_research, "generate_research_pack",
                            lambda **kw: dict(agent_research.EMPTY_PACK))

        gen = MemoGenerator()
        memo = gen.generate_full_memo(
            company="TestCo", product="KSA",
            template_key="credit_memo",
            polish=False,
        )
        expected_keys = [s["key"] for s in MEMO_TEMPLATES["credit_memo"]["sections"]]
        assert [s["key"] for s in memo["sections"]] == expected_keys
