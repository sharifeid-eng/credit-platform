"""
Agent Runner — multi-turn tool-use execution loop with streaming.

This is the core engine that implements the agent pattern:
1. Send message to Claude with tool definitions
2. If Claude responds with tool_use → execute tools → send results back → repeat
3. If Claude responds with text → yield to user → done

Supports both synchronous (run) and streaming (stream) execution.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

logger = logging.getLogger(__name__)


class BudgetExceededError(Exception):
    """Raised when token budget is exhausted."""
    pass


class MaxTurnsExceededError(Exception):
    """Raised when max tool-use turns exhausted."""
    pass


@dataclass
class StreamEvent:
    """Event emitted during agent streaming."""

    type: str  # thinking, tool_call, tool_result, text, done, error, budget_warning
    data: Dict[str, Any] = field(default_factory=dict)

    def to_sse(self) -> str:
        """Format as SSE event string."""
        return f"event: {self.type}\ndata: {json.dumps(self.data, default=str)}\n\n"


@dataclass
class AgentResult:
    """Final result of a non-streaming agent run."""

    text: str
    tool_calls_made: List[Dict[str, Any]] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    turns_used: int = 0
    stopped_reason: str = "end_turn"  # end_turn, max_turns, budget_exceeded, error


# Human-readable descriptions for tool calls shown in frontend
_TOOL_DESCRIPTIONS = {
    "get_portfolio_summary": "Loading portfolio summary...",
    "get_par_analysis": "Analyzing Portfolio at Risk...",
    "get_cohort_analysis": "Analyzing vintage cohorts...",
    "get_dso_analysis": "Computing Days Sales Outstanding...",
    "get_dtfc_analysis": "Computing Days to First Cash...",
    "get_ageing_breakdown": "Checking portfolio ageing...",
    "get_concentration": "Analyzing concentration risk...",
    "get_returns_analysis": "Analyzing returns and margins...",
    "get_collection_velocity": "Checking collection velocity...",
    "get_denial_trend": "Analyzing denial trends...",
    "get_deployment": "Loading deployment history...",
    "get_group_performance": "Analyzing provider performance...",
    "get_stress_test": "Running stress scenarios...",
    "get_covenants": "Checking covenant compliance...",
    "get_cdr_ccr": "Computing CDR/CCR rates...",
    "get_segment_analysis": "Analyzing segments...",
    "get_underwriting_drift": "Checking underwriting drift...",
    "get_loss_waterfall": "Analyzing loss waterfall...",
    "search_dataroom": "Searching data room...",
    "get_document_text": "Reading document...",
    "list_dataroom_documents": "Listing data room documents...",
    "get_analytics_snapshots": "Loading analytics timeline...",
    "query_knowledge_base": "Querying knowledge base...",
    "get_mind_context": "Loading institutional context...",
    "get_thesis": "Loading investment thesis...",
    "check_thesis_drift": "Checking thesis drift...",
    "get_company_profile": "Loading company profile...",
    "record_finding": "Recording finding...",
    "get_cross_company_patterns": "Detecting cross-company patterns...",
    "get_memo_templates": "Loading memo templates...",
    "get_prior_memos": "Loading prior memos...",
    "get_section_analytics": "Pulling section analytics...",
    "get_section_research": "Searching for section research...",
    "list_snapshots": "Listing available snapshots...",
    "compare_snapshots": "Comparing snapshots...",
    "get_product_config": "Loading product config...",
    "list_companies": "Listing companies...",
    "check_all_covenants": "Running full covenant check...",
    "get_facility_params": "Loading facility parameters...",
    "get_covenant_history": "Loading covenant history...",
    "run_computation": "Running computation...",
}


class AgentRunner:
    """Multi-turn tool-use agent execution engine.

    Usage:
        config = load_agent_config("analyst")
        agent = AgentRunner(config)
        session = AgentSession.create("analyst", metadata={...})

        # Streaming
        async for event in agent.stream("What's driving PAR30?", session):
            yield event.to_sse()

        # Synchronous
        result = await agent.run("What's driving PAR30?", session)
    """

    # Per-session limits
    MAX_TOOL_CALLS_PER_SESSION = 50
    TOOL_TIMEOUT_SECONDS = 30

    def __init__(self, config):
        """Initialize with an AgentConfig."""
        from core.agents.config import AgentConfig
        self._config: AgentConfig = config
        self._client = None
        self._tool_call_memos: Dict[str, str] = {}  # memoize tool results per session
        self._session_tool_calls: int = 0  # track total tool calls in session

    def _get_client(self):
        """Lazy-init Anthropic client."""
        if self._client is None:
            import anthropic
            from dotenv import load_dotenv
            load_dotenv(override=True)
            self._client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        return self._client

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Execute a tool by name with memoization, timeout, and session limits."""
        # Session tool call limit
        self._session_tool_calls += 1
        if self._session_tool_calls > self.MAX_TOOL_CALLS_PER_SESSION:
            return f"Error: Session tool call limit reached ({self.MAX_TOOL_CALLS_PER_SESSION}). End your analysis with what you have."

        # Build memo key from tool name + sorted args
        memo_key = f"{tool_name}:{json.dumps(tool_input, sort_keys=True, default=str)}"
        if memo_key in self._tool_call_memos:
            logger.debug("Tool %s: returning memoized result", tool_name)
            self._session_tool_calls -= 1  # Don't count memoized hits
            return self._tool_call_memos[memo_key]

        handler = self._config.get_handler(tool_name)
        if handler is None:
            return f"Error: Unknown tool '{tool_name}'"

        try:
            # Execute with timeout
            import signal
            import threading

            result_container = [None]
            error_container = [None]

            def _run():
                try:
                    result_container[0] = handler(**tool_input)
                except Exception as e:
                    error_container[0] = e

            thread = threading.Thread(target=_run, daemon=True)
            thread.start()
            thread.join(timeout=self.TOOL_TIMEOUT_SECONDS)

            if thread.is_alive():
                logger.warning("Tool %s timed out after %ds", tool_name, self.TOOL_TIMEOUT_SECONDS)
                return f"Tool error ({tool_name}): Timed out after {self.TOOL_TIMEOUT_SECONDS}s"

            if error_container[0] is not None:
                raise error_container[0]

            result = result_container[0]
            if not isinstance(result, str):
                result = json.dumps(result, default=str, indent=2)
            # Truncate very long results to avoid context overflow
            if len(result) > 15_000:
                result = result[:15_000] + "\n\n... [truncated — result too long]"
            self._tool_call_memos[memo_key] = result
            return result
        except Exception as e:
            error_msg = f"Tool error ({tool_name}): {type(e).__name__}: {e}"
            logger.error(error_msg, exc_info=True)
            return error_msg

    def _check_budget(self, session, phase: str = "") -> None:
        """Raise if budget exhausted."""
        if session.total_tokens >= self._config.max_budget_tokens:
            raise BudgetExceededError(
                f"Token budget exhausted ({session.total_tokens:,} / "
                f"{self._config.max_budget_tokens:,} tokens used){' during ' + phase if phase else ''}"
            )

    # ── Non-streaming execution ──────────────────────────────────────────

    async def run(self, user_message: str, session) -> AgentResult:
        """Execute agent non-streaming. Returns final result."""
        from core.agents.session import AgentSession

        tool_calls_made = []
        session.add_user_message(user_message)
        session.turn_count += 1

        turn = 0
        stopped_reason = "end_turn"

        while turn < self._config.max_turns:
            turn += 1
            self._check_budget(session, f"turn {turn}")

            response = self._get_client().messages.create(
                model=self._config.model,
                max_tokens=self._config.max_tokens_per_response,
                system=[{
                    "type": "text",
                    "text": self._config.system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }],
                tools=self._config.get_api_tools(),
                messages=session.messages,
                temperature=self._config.temperature,
            )

            session.record_usage(
                response.usage.input_tokens,
                response.usage.output_tokens,
            )

            # Store assistant response
            content_blocks = [_content_block_to_dict(b) for b in response.content]
            session.add_assistant_message(content_blocks)

            # Check for tool use
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if not tool_uses:
                # No tools → extract text and return
                text_parts = [b.text for b in response.content if b.type == "text"]
                session.save()
                return AgentResult(
                    text="\n".join(text_parts),
                    tool_calls_made=tool_calls_made,
                    total_input_tokens=session.total_input_tokens,
                    total_output_tokens=session.total_output_tokens,
                    turns_used=turn,
                    stopped_reason="end_turn",
                )

            # Execute tools
            for tool_use in tool_uses:
                result = self._execute_tool(tool_use.name, tool_use.input)
                tool_calls_made.append({
                    "tool": tool_use.name,
                    "input": tool_use.input,
                    "result_preview": result[:200],
                })
                session.add_tool_result(tool_use.id, result)

        # Max turns reached
        session.save()
        text_parts = []
        if session.messages and session.messages[-1].get("role") == "assistant":
            content = session.messages[-1].get("content", [])
            if isinstance(content, list):
                text_parts = [b.get("text", "") for b in content if b.get("type") == "text"]
        return AgentResult(
            text="\n".join(text_parts) or "[Agent reached maximum turns without final response]",
            tool_calls_made=tool_calls_made,
            total_input_tokens=session.total_input_tokens,
            total_output_tokens=session.total_output_tokens,
            turns_used=turn,
            stopped_reason="max_turns",
        )

    # ── Streaming execution ──────────────────────────────────────────────

    async def stream(self, user_message: str, session) -> AsyncIterator[StreamEvent]:
        """Execute agent with SSE streaming.

        Yields StreamEvent objects as the agent thinks, calls tools, and responds.
        """
        from core.agents.session import AgentSession

        session.add_user_message(user_message)
        session.turn_count += 1

        turn = 0
        consecutive_errors = 0

        while turn < self._config.max_turns:
            turn += 1

            # Budget check
            try:
                self._check_budget(session, f"turn {turn}")
            except BudgetExceededError as e:
                yield StreamEvent("error", {"message": str(e)})
                session.save()
                return

            # Budget warning at 80%
            if session.total_tokens > self._config.max_budget_tokens * 0.8:
                yield StreamEvent("budget_warning", {
                    "used": session.total_tokens,
                    "limit": self._config.max_budget_tokens,
                    "pct": round(session.total_tokens / self._config.max_budget_tokens * 100),
                })

            # Call Claude with streaming
            try:
                text_chunks: List[str] = []
                tool_uses: List[Dict[str, Any]] = []
                current_tool: Optional[Dict[str, Any]] = None
                input_tokens = 0
                output_tokens = 0

                with self._get_client().messages.stream(
                    model=self._config.model,
                    max_tokens=self._config.max_tokens_per_response,
                    system=[{
                        "type": "text",
                        "text": self._config.system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }],
                    tools=self._config.get_api_tools(),
                    messages=session.messages,
                    temperature=self._config.temperature,
                ) as stream:
                    for event in stream:
                        if hasattr(event, "type"):
                            if event.type == "content_block_start":
                                block = event.content_block
                                if hasattr(block, "type") and block.type == "tool_use":
                                    current_tool = {
                                        "id": block.id,
                                        "name": block.name,
                                        "input_json": "",
                                    }
                                    desc = _TOOL_DESCRIPTIONS.get(block.name, f"Using {block.name}...")
                                    yield StreamEvent("tool_call", {
                                        "tool": block.name,
                                        "description": desc,
                                    })

                            elif event.type == "content_block_delta":
                                delta = event.delta
                                if hasattr(delta, "type"):
                                    if delta.type == "text_delta":
                                        text_chunks.append(delta.text)
                                        yield StreamEvent("text", {"delta": delta.text})
                                    elif delta.type == "input_json_delta" and current_tool:
                                        current_tool["input_json"] += delta.partial_json

                            elif event.type == "content_block_stop":
                                if current_tool:
                                    try:
                                        parsed_input = json.loads(current_tool["input_json"]) if current_tool["input_json"] else {}
                                    except json.JSONDecodeError:
                                        parsed_input = {}
                                    tool_uses.append({
                                        "id": current_tool["id"],
                                        "name": current_tool["name"],
                                        "input": parsed_input,
                                    })
                                    current_tool = None

                            elif event.type == "message_delta":
                                if hasattr(event, "usage") and event.usage:
                                    output_tokens = getattr(event.usage, "output_tokens", 0)

                            elif event.type == "message_start":
                                if hasattr(event, "message") and hasattr(event.message, "usage"):
                                    input_tokens = getattr(event.message.usage, "input_tokens", 0)

                # Record usage
                session.record_usage(input_tokens, output_tokens)

                # Build content blocks for session history
                content_blocks = []
                if text_chunks:
                    content_blocks.append({"type": "text", "text": "".join(text_chunks)})
                for tu in tool_uses:
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tu["id"],
                        "name": tu["name"],
                        "input": tu["input"],
                    })
                if content_blocks:
                    session.add_assistant_message(content_blocks)

                # If no tool calls, we're done
                if not tool_uses:
                    yield StreamEvent("done", {
                        "total_input_tokens": session.total_input_tokens,
                        "total_output_tokens": session.total_output_tokens,
                        "turns_used": turn,
                        "session_id": session.session_id,
                    })
                    session.save()
                    return

                # Execute tools
                consecutive_errors = 0
                for tu in tool_uses:
                    result = self._execute_tool(tu["name"], tu["input"])
                    is_error = result.startswith("Tool error") or result.startswith("Error:")
                    if is_error:
                        consecutive_errors += 1
                    else:
                        consecutive_errors = 0

                    yield StreamEvent("tool_result", {
                        "tool": tu["name"],
                        "preview": result[:300],
                        "is_error": is_error,
                    })

                    session.add_tool_result(tu["id"], result, is_error=is_error)

                    if consecutive_errors >= 3:
                        yield StreamEvent("error", {
                            "message": "3 consecutive tool errors — stopping to avoid loop"
                        })
                        session.save()
                        return

            except BudgetExceededError as e:
                yield StreamEvent("error", {"message": str(e)})
                session.save()
                return
            except Exception as e:
                logger.error("Agent stream error: %s", e, exc_info=True)
                yield StreamEvent("error", {"message": f"Agent error: {type(e).__name__}: {e}"})
                session.save()
                return

        # Max turns exhausted
        yield StreamEvent("error", {
            "message": f"Agent reached maximum turns ({self._config.max_turns}) without completing"
        })
        yield StreamEvent("done", {
            "total_input_tokens": session.total_input_tokens,
            "total_output_tokens": session.total_output_tokens,
            "turns_used": turn,
            "session_id": session.session_id,
            "stopped_reason": "max_turns",
        })
        session.save()


def _content_block_to_dict(block) -> Dict[str, Any]:
    """Convert an Anthropic ContentBlock to a plain dict for JSON serialization."""
    if block.type == "text":
        return {"type": "text", "text": block.text}
    elif block.type == "tool_use":
        return {
            "type": "tool_use",
            "id": block.id,
            "name": block.name,
            "input": block.input,
        }
    return {"type": block.type}
