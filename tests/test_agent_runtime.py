"""
Tests for the Agent Runtime Framework.

Tests cover:
- AgentConfig loading
- AgentSession lifecycle (create, save, load, expire, delete)
- ToolRegistry (register, get, patterns)
- AgentRunner (mocked Claude API)
- StreamEvent SSE formatting
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agents.config import AgentConfig, ToolSpec, load_agent_config
from core.agents.runtime import AgentRunner, AgentResult, StreamEvent, BudgetExceededError
from core.agents.session import AgentSession
from core.agents.tools import ToolRegistry


# ── AgentConfig Tests ────────────────────────────────────────────────────

class TestAgentConfig:
    def test_config_creation(self):
        config = AgentConfig(name="test", system_prompt="You are a test agent.")
        assert config.name == "test"
        assert config.model == "claude-opus-4-6"
        assert config.max_turns == 15
        assert config.temperature == 0.3

    def test_config_with_tools(self):
        tool = ToolSpec(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object", "properties": {"x": {"type": "string"}}},
            handler=lambda x: f"result: {x}",
        )
        config = AgentConfig(name="test", system_prompt="test", tools=[tool])
        assert len(config.get_api_tools()) == 1
        assert config.get_api_tools()[0]["name"] == "test_tool"
        assert config.get_handler("test_tool") is not None
        assert config.get_handler("nonexistent") is None

    def test_load_agent_config(self):
        config = load_agent_config("analyst")
        assert config.name == "analyst"
        assert "analyst" in config.system_prompt.lower() or "credit" in config.system_prompt.lower()
        assert config.max_turns == 15
        assert config.model == "claude-opus-4-6"

    def test_load_agent_config_all_agents(self):
        for agent in ["analyst", "memo_writer", "compliance_monitor", "onboarding"]:
            config = load_agent_config(agent)
            assert config.name == agent
            assert len(config.system_prompt) > 50, f"{agent} AGENT.md is too short"

    def test_load_nonexistent_agent(self):
        with pytest.raises(FileNotFoundError):
            load_agent_config("nonexistent_agent")


# ── AgentSession Tests ───────────────────────────────────────────────────

class TestAgentSession:
    def test_create_session(self):
        session = AgentSession.create("analyst", metadata={"company": "klaim"})
        assert session.agent_name == "analyst"
        assert session.metadata["company"] == "klaim"
        assert session.turn_count == 0
        assert len(session.session_id) == 12

    def test_session_messages(self):
        session = AgentSession.create("analyst")
        session.add_user_message("Hello")
        assert len(session.messages) == 1
        assert session.messages[0]["role"] == "user"

        session.add_assistant_message([{"type": "text", "text": "Hi!"}])
        assert len(session.messages) == 2

    def test_session_tool_results(self):
        session = AgentSession.create("analyst")
        session.add_tool_result("tool_123", "result data")
        assert len(session.messages) == 1
        assert session.messages[0]["role"] == "user"
        content = session.messages[0]["content"]
        assert content[0]["type"] == "tool_result"
        assert content[0]["tool_use_id"] == "tool_123"

    def test_session_usage_tracking(self):
        session = AgentSession.create("analyst")
        session.record_usage(100, 50)
        assert session.total_input_tokens == 100
        assert session.total_output_tokens == 50
        assert session.total_tokens == 150

        session.record_usage(200, 100)
        assert session.total_tokens == 450

    def test_session_save_and_load(self, tmp_path):
        with patch("core.agents.session._SESSIONS_DIR", tmp_path):
            session = AgentSession.create("analyst", metadata={"company": "klaim"})
            session.add_user_message("test question")
            session.record_usage(100, 50)
            session.save()

            loaded = AgentSession.load(session.session_id)
            assert loaded is not None
            assert loaded.agent_name == "analyst"
            assert loaded.metadata["company"] == "klaim"
            assert len(loaded.messages) == 1
            assert loaded.total_tokens == 150

    def test_session_expiry(self, tmp_path):
        with patch("core.agents.session._SESSIONS_DIR", tmp_path):
            with patch("core.agents.session._EXPIRY_HOURS", 0):  # Expire immediately
                session = AgentSession.create("analyst")
                session.last_active = time.time() - 3600  # 1 hour ago
                session.save()

                loaded = AgentSession.load(session.session_id)
                assert loaded is None  # Expired

    def test_session_delete(self, tmp_path):
        with patch("core.agents.session._SESSIONS_DIR", tmp_path):
            session = AgentSession.create("analyst")
            session.save()
            assert (tmp_path / f"{session.session_id}.json").exists()

            session.delete()
            assert not (tmp_path / f"{session.session_id}.json").exists()

    def test_session_list_recent(self, tmp_path):
        with patch("core.agents.session._SESSIONS_DIR", tmp_path):
            for i in range(3):
                s = AgentSession.create("analyst", metadata={"i": i})
                s.save()

            recent = AgentSession.list_recent(limit=10)
            assert len(recent) == 3

    def test_cleanup_expired(self, tmp_path):
        with patch("core.agents.session._SESSIONS_DIR", tmp_path), \
             patch("core.agents.session._EXPIRY_HOURS", 1):
            # Write an expired session file directly (save() overwrites last_active)
            data = {
                "session_id": "expired123",
                "agent_name": "analyst",
                "messages": [],
                "metadata": {},
                "created_at": time.time() - 7200,
                "last_active": time.time() - 7200,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "turn_count": 0,
            }
            (tmp_path / "expired123.json").write_text(json.dumps(data))

            removed = AgentSession.cleanup_expired()
            assert removed == 1


# ── ToolRegistry Tests ───────────────────────────────────────────────────

class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        reg.register("test.tool", "A tool", {"type": "object"}, lambda: "ok")
        assert reg.get("test.tool") is not None
        assert reg.get("nonexistent") is None

    def test_pattern_matching(self):
        reg = ToolRegistry()
        reg.register("analytics.summary", "Sum", {}, lambda: "")
        reg.register("analytics.par", "PAR", {}, lambda: "")
        reg.register("mind.context", "Ctx", {}, lambda: "")
        reg.register("computation.run", "Run", {}, lambda: "")

        matched = reg.get_by_patterns(["analytics.*"])
        assert len(matched) == 2

        matched = reg.get_by_patterns(["analytics.*", "mind.*"])
        assert len(matched) == 3

        matched = reg.get_by_patterns(["computation.run"])
        assert len(matched) == 1

    def test_all_tools(self):
        reg = ToolRegistry()
        reg.register("a", "A", {}, lambda: "")
        reg.register("b", "B", {}, lambda: "")
        assert len(reg.all_tools()) == 2
        assert set(reg.tool_names()) == {"a", "b"}


# ── StreamEvent Tests ────────────────────────────────────────────────────

class TestStreamEvent:
    def test_sse_format(self):
        event = StreamEvent("text", {"delta": "Hello"})
        sse = event.to_sse()
        assert sse.startswith("event: text\n")
        assert '"delta": "Hello"' in sse
        assert sse.endswith("\n\n")

    def test_tool_call_event(self):
        event = StreamEvent("tool_call", {"tool": "get_par", "description": "Analyzing PAR..."})
        sse = event.to_sse()
        assert "tool_call" in sse
        assert "get_par" in sse

    def test_done_event(self):
        event = StreamEvent("done", {"total_input_tokens": 500, "total_output_tokens": 200})
        sse = event.to_sse()
        assert '"total_input_tokens": 500' in sse


# ── AgentRunner Tests (mocked API) ──────────────────────────────────────

class TestAgentRunner:
    def _make_config(self, tools=None):
        return AgentConfig(
            name="test",
            system_prompt="You are a test agent.",
            tools=tools or [],
            max_turns=5,
            max_budget_tokens=10000,
        )

    def test_tool_execution(self):
        tool = ToolSpec(
            name="greet",
            description="Greet someone",
            input_schema={"type": "object", "properties": {"name": {"type": "string"}}},
            handler=lambda name: f"Hello, {name}!",
        )
        runner = AgentRunner(self._make_config([tool]))
        result = runner._execute_tool("greet", {"name": "World"})
        assert result == "Hello, World!"

    def test_tool_memoization(self):
        call_count = 0
        def counting_handler(x="default"):
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"

        tool = ToolSpec("counter", "Count", {"type": "object", "properties": {"x": {"type": "string"}}}, counting_handler)
        runner = AgentRunner(self._make_config([tool]))

        r1 = runner._execute_tool("counter", {"x": "a"})
        r2 = runner._execute_tool("counter", {"x": "a"})  # Same args — memoized
        r3 = runner._execute_tool("counter", {"x": "b"})  # Different args

        assert r1 == r2  # Memoized
        assert r1 != r3  # Different
        assert call_count == 2  # Only 2 actual calls

    def test_tool_error_handling(self):
        def failing_handler():
            raise ValueError("something broke")

        tool = ToolSpec("fail", "Fail", {"type": "object", "properties": {}}, failing_handler)
        runner = AgentRunner(self._make_config([tool]))
        result = runner._execute_tool("fail", {})
        assert "Tool error" in result
        assert "ValueError" in result

    def test_unknown_tool(self):
        runner = AgentRunner(self._make_config())
        result = runner._execute_tool("nonexistent", {})
        assert "Unknown tool" in result

    def test_tool_result_truncation(self):
        tool = ToolSpec("big", "Big", {"type": "object", "properties": {}}, lambda: "x" * 20000)
        runner = AgentRunner(self._make_config([tool]))
        result = runner._execute_tool("big", {})
        assert len(result) <= 15100  # 15000 + truncation message
        assert "truncated" in result

    def test_budget_check(self):
        config = self._make_config()
        config.max_budget_tokens = 100
        runner = AgentRunner(config)
        session = AgentSession.create("test")
        session.record_usage(80, 30)  # Over budget

        with pytest.raises(BudgetExceededError):
            runner._check_budget(session)

    def test_per_prefix_timeout_override(self):
        """external.* tools get the extended timeout, everything else the default."""
        assert AgentRunner._timeout_for_tool("external.web_search") == 180
        assert AgentRunner._timeout_for_tool("external.anything") == 180
        assert AgentRunner._timeout_for_tool("analytics.get_par_analysis") == 30
        assert AgentRunner._timeout_for_tool("memo.generate") == 30
        assert AgentRunner._timeout_for_tool("noprefix") == 30

    def test_per_prefix_timeout_applied_at_runtime(self):
        """The resolved per-tool timeout is passed to thread.join, not the default."""
        import threading
        from unittest.mock import patch

        # A tool that never finishes — forces the timeout branch.
        def hangs(**_):
            import time
            time.sleep(10)
            return "never"

        tool = ToolSpec(
            name="external.hangs",
            description="always hangs",
            input_schema={"type": "object", "properties": {}},
            handler=hangs,
        )
        runner = AgentRunner(self._make_config([tool]))

        # Intercept Thread.join and record the timeout it was called with,
        # then return immediately (pretend the thread is still alive).
        seen = {}
        real_join = threading.Thread.join

        def fake_join(self, timeout=None):
            seen["timeout"] = timeout
            # Don't actually wait — just return. thread.is_alive() remains True.

        with patch.object(threading.Thread, "join", fake_join):
            result = runner._execute_tool("external.hangs", {})

        assert seen.get("timeout") == 180, f"Expected 180s timeout, got {seen.get('timeout')}"
        assert "Timed out after 180s" in result


# ── Global tool registration test ────────────────────────────────────────

class TestGlobalToolRegistration:
    def test_all_tools_registered(self):
        from core.agents.tools import register_all_tools, registry
        register_all_tools()
        names = registry.tool_names()
        assert len(names) >= 40, f"Expected 40+ tools, got {len(names)}"

        # Spot check key tools
        assert "analytics.get_portfolio_summary" in names
        assert "analytics.get_par_analysis" in names
        assert "dataroom.search" in names
        assert "mind.query_knowledge_base" in names
        assert "computation.run" in names
        assert "compliance.check_covenants" in names
        assert "portfolio.list_companies" in names
        assert "memo.get_templates" in names

    def test_analyst_tool_resolution(self):
        from core.agents.tools import register_all_tools, build_tools_for_agent
        register_all_tools()
        tools = build_tools_for_agent("analyst")
        # Analyst has analytics.*, dataroom.*, mind.*, portfolio.*, computation.*
        assert len(tools) >= 30

    def test_compliance_tool_resolution(self):
        from core.agents.tools import register_all_tools, build_tools_for_agent
        register_all_tools()
        tools = build_tools_for_agent("compliance_monitor")
        tool_names = [t.name for t in tools]
        assert "compliance.check_covenants" in tool_names
        assert "analytics.get_par_analysis" in tool_names
        assert "mind.record_finding" in tool_names

    def test_memo_writer_has_external_tools(self):
        """Memo writer should expose external.* so memo drafts can cite web
        research alongside data-room sources. Locks in D5 from session 27."""
        from core.agents.tools import register_all_tools, build_tools_for_agent
        register_all_tools()
        tools = build_tools_for_agent("memo_writer")
        tool_names = [t.name for t in tools]
        assert "external.web_search" in tool_names, (
            "memo_writer config.json is missing the external.* pattern. "
            "Without it, the agent can't trigger pending-review web research "
            "during memo drafts."
        )
        # Also covers the other primary tool categories memo_writer relies on
        assert any(n.startswith("memo.") for n in tool_names)
        assert any(n.startswith("analytics.") for n in tool_names)
        assert any(n.startswith("dataroom.") for n in tool_names)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
