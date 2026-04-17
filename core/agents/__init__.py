"""
Agent Runtime — Python-native multi-turn tool-use agent framework.

Implements the agent pattern (identity + tools + multi-turn loop + streaming)
using the standard Anthropic Python SDK's tool_use capability. Zero new
dependencies beyond `anthropic>=0.52`.

Architecture:
    AgentRunner   — multi-turn tool-use execution loop with streaming
    AgentSession  — persistent conversation state (JSON files)
    AgentConfig   — identity (AGENT.md) + tools + model + limits
    ToolRegistry  — central tool registration and dispatch

Usage:
    from core.agents import AgentRunner, AgentSession, load_agent_config

    config = load_agent_config("analyst")
    session = AgentSession.create("analyst", metadata={"company": "klaim", ...})
    agent = AgentRunner(config)

    # Non-streaming
    result = await agent.run("What's driving PAR30?", session)

    # Streaming (SSE)
    async for event in agent.stream("What's driving PAR30?", session):
        yield event
"""

from core.agents.config import AgentConfig, load_agent_config
from core.agents.runtime import AgentRunner, AgentResult, StreamEvent, BudgetExceededError
from core.agents.session import AgentSession

__all__ = [
    "AgentRunner",
    "AgentResult",
    "AgentSession",
    "AgentConfig",
    "StreamEvent",
    "BudgetExceededError",
    "load_agent_config",
]
