"""
Tool Registry — central registration and dispatch for agent tools.

Tools are plain Python functions that return strings. Each tool is registered
with a name, handler function, and JSON schema for the Anthropic API.

Usage:
    from core.agents.tools import registry, build_tools_for_agent

    # Build tool specs for an agent based on its config.json "tools" patterns
    tool_specs = build_tools_for_agent("analyst")
"""

from __future__ import annotations

import fnmatch
import logging
from typing import Any, Callable, Dict, List, Optional

from core.agents.config import ToolSpec

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry for all agent tools."""

    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}

    def register(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: Callable[..., str],
    ) -> None:
        """Register a tool."""
        self._tools[name] = ToolSpec(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=handler,
        )

    def get(self, name: str) -> Optional[ToolSpec]:
        """Look up a tool by name."""
        return self._tools.get(name)

    def get_by_patterns(self, patterns: List[str]) -> List[ToolSpec]:
        """Get tools matching glob patterns.

        Patterns like "analytics.*" match all tools starting with "analytics.".
        A plain name like "computation" matches exactly.
        """
        matched = []
        seen = set()
        for pattern in patterns:
            # Normalize pattern: "analytics.*" → matches "analytics.get_par_analysis" etc.
            # Use fnmatch for glob matching
            for name, spec in self._tools.items():
                if name not in seen and fnmatch.fnmatch(name, pattern):
                    matched.append(spec)
                    seen.add(name)
        return matched

    def all_tools(self) -> List[ToolSpec]:
        """Return all registered tools."""
        return list(self._tools.values())

    def tool_names(self) -> List[str]:
        """Return all registered tool names."""
        return list(self._tools.keys())


# Global registry instance
registry = ToolRegistry()


def build_tools_for_agent(agent_name: str) -> List[ToolSpec]:
    """Build the tool list for an agent based on its config.json.

    Reads config.json "tools" field (list of patterns like ["analytics.*", "mind.*"])
    and returns matching ToolSpec objects from the registry.
    """
    import json
    from pathlib import Path

    config_path = Path(__file__).parent.parent / "definitions" / agent_name / "config.json"
    if not config_path.exists():
        logger.warning("No config.json for agent %s, returning all tools", agent_name)
        return registry.all_tools()

    config = json.loads(config_path.read_text(encoding="utf-8"))
    patterns = config.get("tools", ["*"])

    tools = registry.get_by_patterns(patterns)
    logger.info("Agent %s: resolved %d tools from %d patterns", agent_name, len(tools), len(patterns))
    return tools


def register_all_tools() -> None:
    """Import all tool modules to trigger registration.

    Call this once at app startup (in main.py lifespan).
    """
    # Import each module — their module-level code calls registry.register()
    from core.agents.tools import analytics  # noqa: F401
    from core.agents.tools import dataroom  # noqa: F401
    from core.agents.tools import mind  # noqa: F401
    from core.agents.tools import memo  # noqa: F401
    from core.agents.tools import portfolio  # noqa: F401
    from core.agents.tools import compliance  # noqa: F401
    from core.agents.tools import computation  # noqa: F401

    logger.info("Registered %d agent tools", len(registry.tool_names()))
