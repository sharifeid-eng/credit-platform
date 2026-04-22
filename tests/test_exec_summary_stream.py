"""SSE streaming regression tests for the Executive Summary endpoint.

Pins the SSE event contract that the frontend depends on:
- Cache hits stream start → cached → result → done immediately (no agent run)
- Agent path forwards runtime events (tool_call, tool_result, text) as-is,
  then intercepts the runtime's `done`, parses the accumulated text, emits
  our structured `result`, and finishes with a single terminal `done`
- Unparseable agent text falls back to a single "warning" finding so the
  UI never renders an empty result

These tests do NOT verify heartbeat timing (20s cadence) — that cadence
is shared with memo_generate_stream which is already battle-tested in
production (session 26.2). Verifying it would require fake clocks and
would add flakiness without catching anything a smoke test wouldn't.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


class _FakeStreamEvent:
    """Stand-in for core.agents.runtime.StreamEvent."""

    def __init__(self, type_: str, data: dict = None):
        self.type = type_
        self.data = data or {}

    def to_sse(self) -> str:
        return f"event: {self.type}\ndata: {json.dumps(self.data)}\n\n"


def _parse_sse(body: str):
    """Return a list of (event_type, data_dict) tuples from an SSE body.

    Drops heartbeat comment lines (": keepalive") per SSE spec.
    """
    out = []
    for raw in body.split("\n\n"):
        raw = raw.strip("\n")
        if not raw:
            continue
        # Comment-only event (heartbeat)
        if all(line.startswith(":") for line in raw.split("\n")):
            continue
        event_type = "message"
        data_lines = []
        for line in raw.split("\n"):
            if line.startswith("event: "):
                event_type = line[7:].strip()
            elif line.startswith("data: "):
                data_lines.append(line[6:])
        if data_lines:
            payload = "\n".join(data_lines)
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                data = {"_raw": payload}
            out.append((event_type, data))
    return out


# ── Shared monkeypatches ─────────────────────────────────────────────────────

def _patch_common(monkeypatch):
    """Silence all the helpers the endpoint calls before it reaches streaming logic."""
    monkeypatch.setattr(
        "backend.main._resolve_snapshot",
        lambda co, p, s: {"filename": "test.csv", "date": "2026-04-15"},
    )
    monkeypatch.setattr("backend.main._check_backdated", lambda a, b: None)
    # Unique but predictable path — tests that write to cache will intercept this.
    monkeypatch.setattr(
        "backend.main._ai_cache_key",
        lambda *a, **k: "/tmp/__exec_summary_stream_test__.json",
    )
    monkeypatch.setattr("backend.main._get_analysis_type", lambda co, p: "aajil")
    monkeypatch.setattr("backend.main.log_activity", lambda *a, **k: None)

    # Layer 2.5 citations — always empty in tests; the assert is only about event shape.
    fake_mind = MagicMock()
    fake_mind.asset_class_sources = []
    monkeypatch.setattr("backend.main.build_mind_context", lambda *a, **k: fake_mind)


def _patch_agent(monkeypatch, events):
    """Replace AgentRunner with one whose .stream() yields the given events.

    The endpoint imports AgentRunner locally inside _stream(), so patching
    the module attribute catches the import on every request.
    """
    async def fake_stream(prompt, session):
        for e in events:
            yield e

    mock_runner = MagicMock()
    mock_runner.stream = fake_stream

    mock_config = MagicMock()
    mock_config.max_turns = 20

    monkeypatch.setattr(
        "core.agents.runtime.AgentRunner",
        lambda config: mock_runner,
    )
    monkeypatch.setattr(
        "core.agents.config.load_agent_config",
        lambda *a, **k: mock_config,
    )
    monkeypatch.setattr(
        "core.agents.tools.build_tools_for_agent",
        lambda name: [],
    )

    mock_session = MagicMock()
    mock_session.session_id = "test-session"
    mock_session.delete = MagicMock()
    monkeypatch.setattr(
        "core.agents.session.AgentSession.create",
        classmethod(lambda cls, *a, **k: mock_session),
    )


# ── Tests ────────────────────────────────────────────────────────────────────

class TestCacheHit:
    def test_cache_hit_streams_result_immediately(self, monkeypatch):
        _patch_common(monkeypatch)

        fake_payload = {
            "narrative": {
                "sections": [{"title": "Ov", "content": "p", "conclusion": "c", "metrics": []}],
                "summary_table": [],
                "bottom_line": "verdict",
            },
            "findings": [{
                "rank": 1, "severity": "positive", "title": "cached-title",
                "explanation": "e", "data_points": [], "tab": "overview",
            }],
            "generated_at": "2026-04-22T00:00:00",
            "asset_class_sources": [],
            "cached": True,
        }
        monkeypatch.setattr("backend.main._ai_cache_get", lambda path: fake_payload)

        with client.stream(
            "GET",
            "/companies/Aajil/products/KSA/ai-executive-summary/stream",
        ) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")
            body = b"".join(resp.iter_bytes()).decode("utf-8")

        events = _parse_sse(body)
        types = [t for t, _ in events]

        # Contract: exactly these four events, in this order
        assert types == ["start", "cached", "result", "done"]

        # The cached payload round-trips to the client verbatim
        result_data = dict(events)["result"]
        assert result_data["findings"][0]["title"] == "cached-title"
        assert result_data["narrative"]["bottom_line"] == "verdict"

        # The done event signals cache-hit so the UI can flag it
        done_data = dict(events)["done"]
        assert done_data["from_cache"] is True
        assert done_data["ok"] is True


class TestAgentPath:
    def test_agent_events_forward_and_result_is_parsed(self, monkeypatch):
        _patch_common(monkeypatch)
        # Cache miss forces agent run
        monkeypatch.setattr("backend.main._ai_cache_get", lambda path: None)

        write_calls = []
        monkeypatch.setattr(
            "backend.main._ai_cache_put",
            lambda path, data: write_calls.append((path, data)),
        )

        agent_output = {
            "narrative": {
                "sections": [{"title": "Overview", "content": "live para"}],
                "summary_table": [],
                "bottom_line": "Proceed",
            },
            "findings": [{
                "rank": 1, "severity": "positive", "title": "agent-result",
                "explanation": "ok", "data_points": [], "tab": "overview",
            }],
        }
        # Split the JSON across two text chunks to exercise accumulation
        serialized = json.dumps(agent_output)
        mid = len(serialized) // 2

        _patch_agent(monkeypatch, [
            _FakeStreamEvent("tool_call", {
                "tool": "get_portfolio_summary",
                "description": "Fetch portfolio KPIs",
            }),
            _FakeStreamEvent("tool_result", {
                "tool": "get_portfolio_summary",
                "preview": "ok",
                "is_error": False,
            }),
            _FakeStreamEvent("text", {"delta": serialized[:mid]}),
            _FakeStreamEvent("text", {"delta": serialized[mid:]}),
            _FakeStreamEvent("done", {
                "total_input_tokens": 1234,
                "total_output_tokens": 567,
                "turns_used": 2,
                "session_id": "sess-x",
            }),
        ])

        with client.stream(
            "GET",
            "/companies/Aajil/products/KSA/ai-executive-summary/stream?refresh=true",
        ) as resp:
            assert resp.status_code == 200
            body = b"".join(resp.iter_bytes()).decode("utf-8")

        events = _parse_sse(body)
        types = [t for t, _ in events]

        # Ordering: start first, tool + text events pass through, result, done
        assert types[0] == "start"
        assert types[-1] == "done"
        assert "tool_call" in types
        assert "tool_result" in types
        assert types.count("text") == 2
        assert types.count("result") == 1

        # CRITICAL: only ONE terminal done event. The runtime's done is
        # intercepted and replaced with our structured result + a single
        # outer done. Two done events would confuse the client.
        assert types.count("done") == 1

        # result lands AFTER the last text so the UI's stage label
        # transitions correctly (text → "Writing narrative & findings"
        # → result → done).
        result_idx = types.index("result")
        last_text_idx = len(types) - 1 - list(reversed(types)).index("text")
        assert result_idx > last_text_idx, "result must come after the final text chunk"

        # Payload shape matches the sync endpoint
        result_data = next(d for t, d in events if t == "result")
        assert result_data["findings"][0]["title"] == "agent-result"
        assert result_data["narrative"]["bottom_line"] == "Proceed"
        assert result_data["mode"] == "agent"
        # analytics_coverage key always present in the payload (null when
        # agent didn't emit one) so the frontend destructure is predictable.
        assert "analytics_coverage" in result_data

        # Terminal done carries the runtime's token counts for cost tracking
        done_data = next(d for t, d in events if t == "done")
        assert done_data["ok"] is True
        assert done_data["turns_used"] == 2
        assert done_data["total_input_tokens"] == 1234
        assert done_data["total_output_tokens"] == 567

        # Side effect: the parsed payload got written to the cache
        assert len(write_calls) == 1
        cached_payload = write_calls[0][1]
        assert cached_payload["findings"][0]["title"] == "agent-result"

    def test_unparseable_text_falls_back_to_warning_finding(self, monkeypatch):
        _patch_common(monkeypatch)
        monkeypatch.setattr("backend.main._ai_cache_get", lambda path: None)
        monkeypatch.setattr("backend.main._ai_cache_put", lambda path, data: None)

        _patch_agent(monkeypatch, [
            _FakeStreamEvent("text", {"delta": "this is not JSON"}),
            _FakeStreamEvent("done", {
                "total_input_tokens": 10, "total_output_tokens": 5,
                "turns_used": 1, "session_id": "s",
            }),
        ])

        with client.stream(
            "GET",
            "/companies/Aajil/products/KSA/ai-executive-summary/stream?refresh=true",
        ) as resp:
            assert resp.status_code == 200
            body = b"".join(resp.iter_bytes()).decode("utf-8")

        events = _parse_sse(body)
        result = next(d for t, d in events if t == "result")

        # Contract: parse failure still produces a renderable result —
        # narrative is null, findings has one warning entry with the
        # raw text as explanation. Frontend relies on findings being
        # a non-empty list.
        assert result["narrative"] is None
        assert len(result["findings"]) == 1
        assert result["findings"][0]["severity"] == "warning"
        assert "not JSON" in result["findings"][0]["explanation"]

    def test_analytics_coverage_flows_through_stream(self, monkeypatch):
        """End-to-end: agent emits analytics_coverage → it lands in result_payload
        → frontend receives it. Aajil is the primary use case (PAR/DSO/covenant
        tools unavailable), but any company with partial tool coverage benefits."""
        _patch_common(monkeypatch)
        monkeypatch.setattr("backend.main._ai_cache_get", lambda path: None)
        write_calls = []
        monkeypatch.setattr(
            "backend.main._ai_cache_put",
            lambda path, data: write_calls.append((path, data)),
        )

        agent_output = {
            "narrative": {
                "sections": [{"title": "Overview", "content": "p"}],
                "summary_table": [],
                "bottom_line": "b",
            },
            "analytics_coverage": (
                "PAR, DSO, and covenant modules are unavailable for aajil — "
                "limits forward-trajectory and headroom monitoring."
            ),
            "findings": [{"rank": 1, "severity": "positive", "title": "t",
                          "explanation": "e", "data_points": [], "tab": "overview"}],
        }

        _patch_agent(monkeypatch, [
            _FakeStreamEvent("text", {"delta": json.dumps(agent_output)}),
            _FakeStreamEvent("done", {
                "total_input_tokens": 100, "total_output_tokens": 50,
                "turns_used": 1, "session_id": "s",
            }),
        ])

        with client.stream(
            "GET",
            "/companies/Aajil/products/KSA/ai-executive-summary/stream?refresh=true",
        ) as resp:
            assert resp.status_code == 200
            body = b"".join(resp.iter_bytes()).decode("utf-8")

        events = _parse_sse(body)
        result = next(d for t, d in events if t == "result")

        assert result["analytics_coverage"] is not None
        assert "PAR, DSO" in result["analytics_coverage"]
        assert "aajil" in result["analytics_coverage"]

        # And it survives the cache round-trip so subsequent views see it too.
        assert len(write_calls) == 1
        cached = write_calls[0][1]
        assert cached["analytics_coverage"] == result["analytics_coverage"]

    def test_agent_error_event_is_forwarded(self, monkeypatch):
        _patch_common(monkeypatch)
        monkeypatch.setattr("backend.main._ai_cache_get", lambda path: None)
        monkeypatch.setattr("backend.main._ai_cache_put", lambda path, data: None)

        _patch_agent(monkeypatch, [
            _FakeStreamEvent("error", {"message": "budget exceeded"}),
            # Agent streams bail without done on hard errors — the
            # endpoint should still emit a terminal `done` with ok=False
            # so the client's onDone callback fires reliably.
        ])

        with client.stream(
            "GET",
            "/companies/Aajil/products/KSA/ai-executive-summary/stream?refresh=true",
        ) as resp:
            assert resp.status_code == 200
            body = b"".join(resp.iter_bytes()).decode("utf-8")

        events = _parse_sse(body)
        types = [t for t, _ in events]

        assert "error" in types
        assert types[-1] == "done"
        error_data = next(d for t, d in events if t == "error")
        assert "budget exceeded" in error_data["message"]

        done_data = next(d for t, d in events if t == "done")
        assert done_data["ok"] is False

        # Terminal done must carry the runtime error message — otherwise the
        # frontend's onDone fallback clobbers onError's real message with a
        # generic "Stream ended without a result" because d.error was empty.
        # (Regression for 2026-04-22 user report after max_tokens bump.)
        assert done_data.get("error"), (
            "terminal done must propagate runtime StreamEvent('error') message"
        )
        assert "budget exceeded" in done_data["error"]


# ── Parser helper tests ─────────────────────────────────────────────────────

class TestParseAgentExecSummaryResponse:
    """Covers `_parse_agent_exec_summary_response`.

    The helper backs both the sync and SSE Executive Summary paths; the
    Aajil regression (session 2026-04-22) where the agent dumped markdown
    with a conversational preamble ("I now have comprehensive data…")
    caused `json.loads()` to fail and the result was wrapped as a
    single POSITIVE "Agent Summary" finding showing raw `**bold**`
    syntax in the UI. These tests pin each extraction path the helper
    now handles.
    """

    def _call(self, text):
        from backend.main import _parse_agent_exec_summary_response
        return _parse_agent_exec_summary_response(text)

    def test_clean_json_parses(self):
        payload = {
            "narrative": {"sections": [{"title": "T", "content": "c"}],
                          "summary_table": [], "bottom_line": "v"},
            "findings": [{"rank": 1, "severity": "positive", "title": "t",
                          "explanation": "e", "data_points": [], "tab": "overview"}],
        }
        narr, finds, coverage, ok = self._call(json.dumps(payload))
        assert ok is True
        assert narr["bottom_line"] == "v"
        assert finds[0]["title"] == "t"
        # No analytics_coverage in payload → None (not empty string)
        assert coverage is None

    def test_json_fence_stripped(self):
        payload = {"narrative": {"bottom_line": "ok"}, "findings": []}
        fenced = "```json\n" + json.dumps(payload) + "\n```"
        narr, finds, coverage, ok = self._call(fenced)
        assert ok is True
        assert narr["bottom_line"] == "ok"

    def test_conversational_preamble_skipped(self):
        """The Aajil bug: agent prepends 'I now have comprehensive data across
        all dimensions. Let me compile the executive summary.' before the JSON.
        Helper must recover by extracting the outermost {…} substring."""
        payload = {"narrative": {"bottom_line": "verdict"},
                   "findings": [{"rank": 1, "severity": "positive", "title": "t",
                                 "explanation": "e", "data_points": [], "tab": "overview"}]}
        text = (
            "I now have comprehensive data across all dimensions. "
            "Let me compile the executive summary.\n\n"
            + json.dumps(payload)
        )
        narr, finds, coverage, ok = self._call(text)
        assert ok is True, "extraction should succeed despite preamble"
        assert narr["bottom_line"] == "verdict"
        assert finds[0]["title"] == "t"

    def test_closing_prose_stripped(self):
        """Trailing prose after the JSON must not break extraction."""
        payload = {"narrative": {"bottom_line": "v"}, "findings": []}
        text = json.dumps(payload) + "\n\nLet me know if you need more detail."
        narr, finds, coverage, ok = self._call(text)
        assert ok is True
        assert narr["bottom_line"] == "v"

    def test_legacy_list_shape_accepted(self):
        """Pre-narrative format returned a bare findings list — still supported."""
        findings_list = [{"rank": 1, "severity": "positive", "title": "t",
                          "explanation": "e", "data_points": [], "tab": "overview"}]
        narr, finds, coverage, ok = self._call(json.dumps(findings_list))
        assert ok is True
        assert narr is None
        assert len(finds) == 1
        assert coverage is None

    def test_completely_unparseable_falls_back(self):
        """Pure markdown with no {…} substring → warning fallback with raw text."""
        text = "## Portfolio Overview\n\n**Collection rate:** 87.3%\n\n| Metric | Value |\n|---|---|"
        narr, finds, coverage, ok = self._call(text)
        assert ok is False
        assert narr is None
        assert len(finds) == 1
        assert finds[0]["severity"] == "warning"
        assert finds[0]["title"] == "Summary generated (unparsed)"
        # Raw text preserved for analyst debugging
        assert "Portfolio Overview" in finds[0]["explanation"]
        assert coverage is None

    def test_empty_string_fallback(self):
        narr, finds, coverage, ok = self._call("")
        assert ok is False
        assert narr is None
        assert finds == []  # Empty input produces no warning finding either
        assert coverage is None

    def test_severity_never_positive_on_failure(self):
        """Regression for the session 2026-04-22 bug — the sync endpoint
        used to mislabel parse failures as severity='positive' with title
        'Agent Summary', which rendered as a teal POSITIVE card misleading
        the analyst into thinking the markdown dump was a success. Parse
        failures must always produce severity='warning'."""
        narr, finds, coverage, ok = self._call("not JSON at all, just prose")
        assert ok is False
        assert finds[0]["severity"] == "warning"
        assert finds[0]["title"] != "Agent Summary"

    def test_analytics_coverage_passed_through(self):
        """New field introduced 2026-04-22 to move tool-gap / undefined-thesis
        concerns OUT of the ranked findings list and INTO a dedicated callout.
        Parser must pass the string through verbatim so the frontend can render
        it as a monitoring caveat between Bottom Line and Key Findings."""
        payload = {
            "narrative": {"bottom_line": "v"},
            "analytics_coverage": (
                "PAR, DSO, and covenant compliance modules are unavailable for "
                "this analysis type. No formal investment thesis is defined."
            ),
            "findings": [],
        }
        narr, finds, coverage, ok = self._call(json.dumps(payload))
        assert ok is True
        assert coverage is not None
        assert "PAR, DSO" in coverage
        assert "investment thesis" in coverage

    def test_analytics_coverage_empty_string_stripped(self):
        """Empty or whitespace-only analytics_coverage must be normalised to
        None so the frontend doesn't render a placeholder callout block."""
        for empty in ("", "   ", "\n\n", "  \t  "):
            payload = {"narrative": {"bottom_line": "v"},
                       "analytics_coverage": empty, "findings": []}
            _, _, coverage, ok = self._call(json.dumps(payload))
            assert ok is True
            assert coverage is None, f"empty={empty!r} should normalise to None"

    def test_analytics_coverage_non_string_ignored(self):
        """Defensive: if the agent returns a list/object/number in this field
        (mis-interpreting the schema), we drop it rather than leaking shape
        mismatches to the frontend."""
        for bogus in ([], {}, 42, True, None):
            payload = {"narrative": {"bottom_line": "v"},
                       "analytics_coverage": bogus, "findings": []}
            _, _, coverage, ok = self._call(json.dumps(payload))
            assert ok is True
            assert coverage is None, f"non-string={bogus!r} should normalise to None"
