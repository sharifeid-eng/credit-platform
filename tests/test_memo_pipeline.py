"""Tests for the hybrid memo generation pipeline (core.memo.generator).

These tests mock the AI calls and assert:
- Section tier classification uses template metadata correctly
- Parallel fan-out for structured sections preserves template order
- Judgment sections run sequentially with body context
- Polish pass is invoked and preserves metrics/citations
- Generation metadata is recorded per section and at memo level
- Citation audit failures synthesize an _audit_failed marker (not silent [])
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
            log_prefix = kwargs.get("log_prefix") or ""
            # Per-section polish: returns {"content": "..."} for a single section
            if tier == "polish" or log_prefix.startswith("memo.polish."):
                section_key = log_prefix.rsplit(".", 1)[-1] if "." in log_prefix else "unknown"
                return _fake_claude_response({"content": f"polished {section_key}"})
            # Per-section citation audit: returns {"issues": []} for a single section
            if log_prefix.startswith("memo.citation_audit."):
                return _fake_claude_response({"issues": []})
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
            log_prefix = kwargs.get("log_prefix") or ""
            if tier == "polish" or log_prefix.startswith("memo.polish."):
                section_key = log_prefix.rsplit(".", 1)[-1] if "." in log_prefix else "unknown"
                return _fake_claude_response({"content": f"polished {section_key}"})
            if log_prefix.startswith("memo.citation_audit."):
                return _fake_claude_response({"issues": []})
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

    def test_polish_runs_per_section(self, mock_bridge, mock_dataroom, monkeypatch):
        """Per-section polish (2026-04-19 fix): each polishable section should
        receive its own Opus call producing distinct content, pre_polish_content
        should be recorded, generated_by should end with +polished, and the
        generation_meta['polish'] block should tally attempted/polished/failed.
        """
        monkeypatch.setattr("core.memo.generator.AnalyticsBridge", lambda: mock_bridge)
        monkeypatch.setattr("core.dataroom.DataRoomEngine", lambda: mock_dataroom)
        monkeypatch.setattr("core.mind.build_mind_context",
                            lambda **kw: MagicMock(
                                is_empty=True, formatted="", total_entries=0))

        polish_calls: list[str] = []

        def _fake_complete(*, tier, system, messages, max_tokens, **kwargs):
            log_prefix = kwargs.get("log_prefix") or ""
            if tier == "polish" or log_prefix.startswith("memo.polish."):
                section_key = log_prefix.rsplit(".", 1)[-1] if "." in log_prefix else "unknown"
                polish_calls.append(section_key)
                return _fake_claude_response(
                    {"content": f"POLISHED_{section_key}_text"}
                )
            if log_prefix.startswith("memo.citation_audit."):
                return _fake_claude_response({"issues": []})
            return _fake_claude_response({
                "content": "Raw body with metric [PAR30: 3%].",
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
            polish=True,
        )

        # Polishable sections = all except those with source="auto" (appendix)
        polishable_keys = [
            s["key"] for s in MEMO_TEMPLATES["credit_memo"]["sections"]
            if s.get("source") != "auto"
        ]

        # Each polishable key was polished exactly once — distinct calls, not one-shot
        assert sorted(polish_calls) == sorted(polishable_keys), (
            f"Expected one polish call per polishable section; "
            f"got {sorted(polish_calls)} vs {sorted(polishable_keys)}"
        )

        # Each polishable section has materially different content post-polish,
        # plus pre_polish_content recorded and +polished flag on generated_by.
        by_key = {s["key"]: s for s in memo["sections"]}
        for k in polishable_keys:
            sect = by_key[k]
            assert sect["content"] == f"POLISHED_{k}_text", \
                f"Section {k} content not replaced by polish output"
            assert sect.get("pre_polish_content"), \
                f"Section {k} missing pre_polish_content"
            assert sect["content"] != sect["pre_polish_content"], \
                f"Section {k} post-polish content matches pre-polish (no-op)"
            gb = sect.get("generated_by", "")
            assert "+polished" in gb, \
                f"Section {k} generated_by missing +polished flag: {gb}"

        # Auto section (appendix) untouched by polish
        appendix = by_key["appendix"]
        assert "+polished" not in (appendix.get("generated_by") or ""), \
            "Auto (appendix) section should not be polished"
        assert "pre_polish_content" not in appendix

        assert memo["polished"] is True
        polish_meta = memo["generation_meta"]["polish"]
        assert polish_meta["sections_attempted"] == len(polishable_keys)
        assert polish_meta["sections_polished"] == len(polishable_keys)
        assert polish_meta["sections_failed"] == 0

    def test_partial_polish_failure_preserves_memo(self, mock_bridge, mock_dataroom,
                                                    monkeypatch):
        """Partial polish failure (2026-04-19 fix): if one section's polish call
        fails, the failed section retains pre-polish content, other sections are
        still polished, memo['polished'] is False, and the error is recorded
        per-section in generation_meta['polish']['sections_failed'].
        """
        monkeypatch.setattr("core.memo.generator.AnalyticsBridge", lambda: mock_bridge)
        monkeypatch.setattr("core.dataroom.DataRoomEngine", lambda: mock_dataroom)
        monkeypatch.setattr("core.mind.build_mind_context",
                            lambda **kw: MagicMock(
                                is_empty=True, formatted="", total_entries=0))

        failing_key = "credit_quality"

        def _fake_complete(*, tier, system, messages, max_tokens, **kwargs):
            log_prefix = kwargs.get("log_prefix") or ""
            if tier == "polish" or log_prefix.startswith("memo.polish."):
                section_key = log_prefix.rsplit(".", 1)[-1] if "." in log_prefix else "unknown"
                if section_key == failing_key:
                    raise RuntimeError(f"simulated polish failure on {failing_key}")
                return _fake_claude_response(
                    {"content": f"POLISHED_{section_key}_text"}
                )
            if log_prefix.startswith("memo.citation_audit."):
                return _fake_claude_response({"issues": []})
            return _fake_claude_response({
                "content": "Pre-polish body text.",
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
            polish=True,
        )

        polishable_keys = [
            s["key"] for s in MEMO_TEMPLATES["credit_memo"]["sections"]
            if s.get("source") != "auto"
        ]
        by_key = {s["key"]: s for s in memo["sections"]}

        # The failing section retains pre-polish content — no +polished flag
        failed_sect = by_key[failing_key]
        assert failed_sect["content"] == "Pre-polish body text.", \
            "Failed section should retain pre-polish content verbatim"
        assert "+polished" not in (failed_sect.get("generated_by") or ""), \
            "Failed section should not be flagged +polished"
        assert "pre_polish_content" not in failed_sect, \
            "Failed section should not have pre_polish_content set (never replaced)"

        # Every other polishable section succeeded
        other_keys = [k for k in polishable_keys if k != failing_key]
        for k in other_keys:
            sect = by_key[k]
            assert sect["content"] == f"POLISHED_{k}_text", \
                f"Section {k} should have been polished despite {failing_key} failure"
            assert "+polished" in (sect.get("generated_by") or "")

        # polished=False because not ALL polishable sections succeeded
        assert memo["polished"] is False

        # Error recorded with section_key attribution
        polish_errors = [e for e in memo.get("errors", [])
                         if e.get("section") == "polish"]
        assert len(polish_errors) == 1, \
            f"Expected exactly 1 polish error; got {polish_errors}"
        assert polish_errors[0].get("section_key") == failing_key

        # generation_meta tallies
        polish_meta = memo["generation_meta"]["polish"]
        assert polish_meta["sections_attempted"] == len(polishable_keys)
        assert polish_meta["sections_polished"] == len(other_keys)
        assert polish_meta["sections_failed"] == 1


# ── Citation audit failure-mode regression (Mode 6 Red Team Finding E#5) ───
#
# Bug: _validate_citations returned [] on JSON parse failure or AI exception.
# That's INDISTINGUISHABLE from a genuine "no issues found" — fabricated
# citations slipped through to polished memo with no signal to the analyst.
# Fix: synthesize an _audit_failed marker so polish + downstream callers can
# distinguish "audit ran clean" from "audit failed to verify".

class TestCitationAuditFailureMarker:

    def _memo_with_citations(self):
        return {
            "sections": [
                {
                    "key": "section_a",
                    "content": "Sample section content",
                    "citations": [
                        {"source": "doc.pdf", "snippet": "claim 1"},
                        {"source": "doc.pdf", "snippet": "claim 2"},
                    ],
                }
            ]
        }

    def _make_generator_with_dataroom(self):
        gen = MemoGenerator()
        gen._dataroom = MagicMock()
        gen._dataroom.search.return_value = []  # no excerpts → simpler path
        return gen

    def test_parse_failure_emits_audit_failed_marker(self, monkeypatch):
        """Malformed JSON from the audit AI must surface as an _audit_failed
        sentinel — NOT silently as 'no issues found'."""
        gen = self._make_generator_with_dataroom()
        bad_resp = MagicMock()
        bad_resp.content = [MagicMock(text="this is { not valid json at all")]
        monkeypatch.setattr("core.ai_client.complete", lambda **kw: bad_resp)
        memo = self._memo_with_citations()
        issues = gen._validate_citations(memo, company="klaim", product="UAE_healthcare")
        assert len(issues) > 0, "Parse failure must NOT return empty list"
        assert any(issue.get("_audit_failed") for issue in issues), (
            "Parse failure must emit a sentinel _audit_failed=True issue so polish "
            "+ analyst can see the audit didn't run"
        )

    def test_complete_exception_emits_audit_failed_marker(self, monkeypatch):
        """AI call exception (rate limit, network, model 503) must also surface
        as _audit_failed, not silent []."""
        gen = self._make_generator_with_dataroom()
        def _raise(**kw):
            raise RuntimeError("Anthropic API: 503 Service Unavailable")
        monkeypatch.setattr("core.ai_client.complete", _raise)
        memo = self._memo_with_citations()
        issues = gen._validate_citations(memo, company="klaim", product="UAE_healthcare")
        assert any(issue.get("_audit_failed") for issue in issues), (
            "Exception path must emit a sentinel _audit_failed=True issue"
        )

    def test_clean_audit_returns_empty_no_false_marker(self, monkeypatch):
        """Positive case: when audit returns valid `{"issues": []}`, no false
        _audit_failed sentinel — clean audits look clean."""
        gen = self._make_generator_with_dataroom()
        clean_resp = MagicMock()
        clean_resp.content = [MagicMock(text='{"issues": []}')]
        monkeypatch.setattr("core.ai_client.complete", lambda **kw: clean_resp)
        memo = self._memo_with_citations()
        issues = gen._validate_citations(memo, company="klaim", product="UAE_healthcare")
        assert issues == [], (
            f"Clean audit must return [] — no false sentinel. Got: {issues}"
        )

    def test_real_issues_returned_as_normal(self, monkeypatch):
        """Positive case: real flagged issues come through with their fields."""
        gen = self._make_generator_with_dataroom()
        real_resp = MagicMock()
        real_resp.content = [MagicMock(text=(
            '{"issues": [{"section_key": "section_a", "citation_index": 0, '
            '"source": "doc.pdf", "reason": "Claim not in source", "severity": "high"}]}'
        ))]
        monkeypatch.setattr("core.ai_client.complete", lambda **kw: real_resp)
        memo = self._memo_with_citations()
        issues = gen._validate_citations(memo, company="klaim", product="UAE_healthcare")
        assert len(issues) == 1
        assert issues[0]["reason"] == "Claim not in source"
        assert issues[0]["severity"] == "high"
        # NO false _audit_failed marker on real issues
        assert not issues[0].get("_audit_failed")
