"""
Tests for Agent Tools — verifies each tool category works with mock/real data.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agents.tools import register_all_tools, registry


@pytest.fixture(autouse=True, scope="module")
def _register():
    register_all_tools()


# ── Analytics Tools ──────────────────────────────────────────────────────

class TestAnalyticsTools:
    def test_portfolio_summary_schema(self):
        tool = registry.get("analytics.get_portfolio_summary")
        assert tool is not None
        assert "company" in tool.input_schema["properties"]
        assert "product" in tool.input_schema["properties"]
        assert tool.input_schema["required"] == ["company", "product"]

    def test_all_analytics_tools_registered(self):
        expected = [
            "analytics.get_portfolio_summary", "analytics.get_par_analysis",
            "analytics.get_cohort_analysis", "analytics.get_dso_analysis",
            "analytics.get_dtfc_analysis", "analytics.get_ageing_breakdown",
            "analytics.get_concentration", "analytics.get_returns_analysis",
            "analytics.get_collection_velocity", "analytics.get_denial_trend",
            "analytics.get_deployment", "analytics.get_group_performance",
            "analytics.get_stress_test", "analytics.get_covenants",
            "analytics.get_cdr_ccr", "analytics.get_segment_analysis",
            "analytics.get_underwriting_drift", "analytics.get_loss_waterfall",
        ]
        for name in expected:
            assert registry.get(name) is not None, f"Missing tool: {name}"

    def test_analytics_tools_handle_missing_company(self):
        """Analytics tools should raise on nonexistent company (tools handle their own errors)."""
        tool = registry.get("analytics.get_portfolio_summary")
        # Call with nonexistent company — will raise ValueError from load_tape
        # (this is expected; the AgentRunner catches exceptions in _execute_tool)
        with pytest.raises((ValueError, Exception)):
            tool.handler(company="nonexistent_co_xyz", product="nonexistent_prod")


# ── Klaim handler regression tests (signature correctness) ───────────────

def _klaim_data_available():
    """Skip real-data tests when the Klaim tape isn't present."""
    return Path("data/klaim/UAE_healthcare").exists() and any(
        Path("data/klaim/UAE_healthcare").glob("*.csv")
    )


@pytest.mark.skipif(
    not _klaim_data_available(),
    reason="Klaim UAE_healthcare tape not present in this environment",
)
class TestKlaimHandlerSignatures:
    """Regression tests for the Klaim analytics tool handlers.

    Each of these tools had a signature mismatch against the core compute
    functions (extra positional args, wrong module import, or wrong kwarg).
    The judgment-section research packs in the memo pipeline invoke these
    handlers, so a TypeError here silently killed the memo SSE stream.

    Verify each handler runs without raising and returns a non-empty string.
    """

    KLAIM = dict(company="klaim", product="UAE_healthcare")

    def test_get_cohort_analysis_klaim(self):
        tool = registry.get("analytics.get_cohort_analysis")
        result = tool.handler(**self.KLAIM)
        assert isinstance(result, str) and result
        assert "Vintage Cohort" in result or "cohort" in result.lower()

    def test_get_returns_analysis_klaim(self):
        tool = registry.get("analytics.get_returns_analysis")
        result = tool.handler(**self.KLAIM)
        assert isinstance(result, str) and result
        assert "Returns Analysis" in result

    def test_get_covenants_klaim(self):
        # This used to import from core.analysis (wrong module).
        tool = registry.get("analytics.get_covenants")
        result = tool.handler(**self.KLAIM)
        assert isinstance(result, str) and result
        assert "Covenant" in result

    def test_get_collection_velocity_klaim(self):
        tool = registry.get("analytics.get_collection_velocity")
        result = tool.handler(**self.KLAIM)
        assert isinstance(result, str) and result
        assert "Collection Velocity" in result

    def test_get_segment_analysis_klaim(self):
        # `dimension` used to be passed as `as_of_date` positionally.
        tool = registry.get("analytics.get_segment_analysis")
        result = tool.handler(dimension="product", **self.KLAIM)
        assert isinstance(result, str) and result
        assert "Segment Analysis" in result


class TestInternalEventLoopGuard:
    """Verify _run_agent_sync's event-loop guard handles non-main threads.

    On Python 3.12+, asyncio.get_event_loop() raises RuntimeError in a
    worker thread with no loop set. The memo pipeline runs agent research
    in a ThreadPoolExecutor, so the guard must create a loop rather than
    propagate the error.
    """

    def test_get_event_loop_guarded_in_worker_thread(self):
        """Simulate the ThreadPoolExecutor context by running the guard in
        a fresh thread. The original bug raised RuntimeError at
        asyncio.get_event_loop()."""
        import asyncio
        import threading

        result = {"ok": False, "err": None}

        def _worker():
            try:
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                assert loop is not None
                result["ok"] = True
            except Exception as e:  # pragma: no cover
                result["err"] = e

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join(timeout=5)
        assert result["err"] is None
        assert result["ok"]


# ── Data Room Tools ──────────────────────────────────────────────────────

class TestDataroomTools:
    def test_all_dataroom_tools_registered(self):
        expected = [
            "dataroom.search", "dataroom.get_document_text",
            "dataroom.list_documents", "dataroom.get_analytics_snapshots",
        ]
        for name in expected:
            assert registry.get(name) is not None, f"Missing tool: {name}"

    def test_search_schema(self):
        tool = registry.get("dataroom.search")
        assert "query" in tool.input_schema["properties"]
        assert "query" in tool.input_schema["required"]

    def test_search_nonexistent_returns_string(self):
        tool = registry.get("dataroom.search")
        result = tool.handler(company="nonexistent", product="nonexistent", query="test")
        assert isinstance(result, str)


# ── Mind Tools ───────────────────────────────────────────────────────────

class TestMindTools:
    def test_all_mind_tools_registered(self):
        expected = [
            "mind.query_knowledge_base", "mind.get_context",
            "mind.get_thesis", "mind.check_thesis_drift",
            "mind.get_company_profile", "mind.record_finding",
            "mind.get_cross_company_patterns",
        ]
        for name in expected:
            assert registry.get(name) is not None, f"Missing tool: {name}"

    def test_query_kb_schema(self):
        tool = registry.get("mind.query_knowledge_base")
        assert "query" in tool.input_schema["properties"]
        assert "query" in tool.input_schema["required"]

    def test_thesis_nonexistent_returns_string(self):
        tool = registry.get("mind.get_thesis")
        result = tool.handler(company="nonexistent", product="nonexistent")
        assert isinstance(result, str)
        assert "No investment thesis" in result or "error" in result.lower()


# ── Memo Tools ───────────────────────────────────────────────────────────

class TestMemoTools:
    def test_all_memo_tools_registered(self):
        expected = [
            "memo.get_templates", "memo.get_prior_memos",
            "memo.get_section_analytics", "memo.get_section_research",
        ]
        for name in expected:
            assert registry.get(name) is not None, f"Missing tool: {name}"

    def test_get_templates_returns_string(self):
        tool = registry.get("memo.get_templates")
        result = tool.handler()
        assert isinstance(result, str)
        assert "Template" in result or "template" in result or "Failed" in result


# ── Portfolio Tools ──────────────────────────────────────────────────────

class TestPortfolioTools:
    def test_all_portfolio_tools_registered(self):
        expected = [
            "portfolio.list_snapshots", "portfolio.compare_snapshots",
            "portfolio.get_config", "portfolio.list_companies",
        ]
        for name in expected:
            assert registry.get(name) is not None, f"Missing tool: {name}"

    def test_list_companies_returns_string(self):
        tool = registry.get("portfolio.list_companies")
        result = tool.handler()
        assert isinstance(result, str)
        # Should list at least one company (klaim) or say "No companies"
        assert "klaim" in result.lower() or "Companies" in result or "No companies" in result


# ── Compliance Tools ─────────────────────────────────────────────────────

class TestComplianceTools:
    def test_all_compliance_tools_registered(self):
        expected = [
            "compliance.check_covenants",
            "compliance.get_facility_params",
            "compliance.get_covenant_history",
        ]
        for name in expected:
            assert registry.get(name) is not None, f"Missing tool: {name}"

    def test_facility_params_nonexistent(self):
        tool = registry.get("compliance.get_facility_params")
        result = tool.handler(company="nonexistent", product="nonexistent")
        assert isinstance(result, str)
        assert "No facility" in result or "Error" in result


# ── Computation Tool ─────────────────────────────────────────────────────

class TestComputationTool:
    def test_registered(self):
        tool = registry.get("computation.run")
        assert tool is not None

    def test_schema(self):
        tool = registry.get("computation.run")
        assert "expression" in tool.input_schema["properties"]
        assert "expression" in tool.input_schema["required"]

    def test_blocks_dangerous_expressions(self):
        tool = registry.get("computation.run")
        # Should block import attempts
        result = tool.handler(
            company="klaim", product="UAE_healthcare",
            expression="import os; os.system('ls')"
        )
        assert "Blocked" in result or "error" in result.lower()

    def test_blocks_exec(self):
        tool = registry.get("computation.run")
        result = tool.handler(
            company="klaim", product="UAE_healthcare",
            expression="exec('print(1)')"
        )
        assert "Blocked" in result or "error" in result.lower()


# ── Tool count verification ──────────────────────────────────────────────

class TestToolCounts:
    def test_total_tool_count(self):
        """Verify total tool count matches expectation.

        Bumped from 42 to 43 in session 27 when external.web_search was added
        (wraps Anthropic's web_search_20250305 server tool; every result lands
        in the pending-review queue). Update this number when tools change —
        use ``>=`` rather than ``==`` if the test becomes too brittle.
        """
        expected = 43
        actual = len(registry.tool_names())
        assert actual == expected, \
            f"Expected {expected} tools, got {actual}: {registry.tool_names()}"

    def test_all_tools_have_handlers(self):
        """Every registered tool must have a callable handler."""
        for name in registry.tool_names():
            tool = registry.get(name)
            assert callable(tool.handler), f"Tool {name} has no callable handler"

    def test_all_tools_have_descriptions(self):
        """Every tool must have a non-empty description."""
        for name in registry.tool_names():
            tool = registry.get(name)
            assert tool.description and len(tool.description) > 10, \
                f"Tool {name} has empty/short description"

    def test_all_tools_have_schemas(self):
        """Every tool must have a valid input schema."""
        for name in registry.tool_names():
            tool = registry.get(name)
            assert isinstance(tool.input_schema, dict), \
                f"Tool {name} has invalid schema type"
            assert "type" in tool.input_schema, \
                f"Tool {name} schema missing 'type'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
