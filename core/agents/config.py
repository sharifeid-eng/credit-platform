"""
Agent Configuration — identity, tools, model, limits.

Each agent is defined by:
    - AGENT.md  — system prompt (the agent's identity)
    - config.json — model, tools, limits, temperature

Agent definitions live in core/agents/definitions/{agent_name}/.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Base directory for agent definitions
_DEFINITIONS_DIR = Path(__file__).parent / "definitions"


@dataclass
class ToolSpec:
    """A tool available to an agent."""

    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable[..., str]

    def to_api_schema(self) -> Dict[str, Any]:
        """Convert to Anthropic API tool schema.

        Anthropic's API requires tool names to match ^[a-zA-Z0-9_-]{1,128}$ —
        no dots allowed. The internal registry uses dotted names (e.g.
        'analytics.get_par_analysis') so glob patterns like 'analytics.*'
        work for config-driven tool assignment. Translate dots to
        underscores at the API boundary only.
        """
        return {
            "name": self.name.replace(".", "_"),
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass
class AgentConfig:
    """Complete agent configuration."""

    name: str
    system_prompt: str
    tools: List[ToolSpec] = field(default_factory=list)
    model: str = "claude-opus-4-6"
    max_turns: int = 15
    max_tokens_per_response: int = 2000
    max_budget_tokens: int = 100_000
    temperature: float = 0.3

    def get_api_tools(self) -> List[Dict[str, Any]]:
        """Return tool schemas for the Anthropic API call."""
        return [t.to_api_schema() for t in self.tools]

    def get_handler(self, tool_name: str) -> Optional[Callable[..., str]]:
        """Look up a tool handler by name.

        Anthropic's API doesn't allow dots in tool names, so to_api_schema()
        translates 'analytics.get_par_analysis' → 'analytics_get_par_analysis'
        on the way out. Claude sends the underscored form back in tool_use
        blocks, but the internal registry is keyed by the dotted form.
        Match against both so dispatch works from either direction.
        """
        for t in self.tools:
            if t.name == tool_name or t.name.replace(".", "_") == tool_name:
                return t.handler
        return None


def load_agent_config(
    agent_name: str,
    *,
    tool_specs: Optional[List[ToolSpec]] = None,
    model_override: Optional[str] = None,
) -> AgentConfig:
    """Load an agent configuration from its definition directory.

    Args:
        agent_name: Name of the agent (matches directory name under definitions/)
        tool_specs: Pre-built tool specs to attach. If None, tools must be
                    attached later via the ToolRegistry.
        model_override: Override model from config.json (e.g. env-var driven).

    Returns:
        AgentConfig ready for AgentRunner.
    """
    agent_dir = _DEFINITIONS_DIR / agent_name

    # Load AGENT.md (system prompt)
    agent_md_path = agent_dir / "AGENT.md"
    if not agent_md_path.exists():
        raise FileNotFoundError(f"Agent identity file not found: {agent_md_path}")
    system_prompt = agent_md_path.read_text(encoding="utf-8").strip()

    # Load config.json (model, limits)
    config_path = agent_dir / "config.json"
    raw: Dict[str, Any] = {}
    if config_path.exists():
        raw = json.loads(config_path.read_text(encoding="utf-8"))

    model = model_override or raw.get("model", os.getenv("AGENT_DEFAULT_MODEL", "claude-opus-4-6"))

    return AgentConfig(
        name=agent_name,
        system_prompt=system_prompt,
        tools=tool_specs or [],
        model=model,
        max_turns=raw.get("max_turns", 15),
        max_tokens_per_response=raw.get("max_tokens_per_response", 2000),
        max_budget_tokens=raw.get("max_budget_tokens", 100_000),
        temperature=raw.get("temperature", 0.3),
    )
