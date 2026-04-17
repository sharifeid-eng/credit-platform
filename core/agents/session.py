"""
Agent Session — persistent conversation state.

Sessions store the full Anthropic message history so agents can maintain
multi-turn context. Stored as JSON files in data/_agent_sessions/.

Sessions auto-expire after AGENT_SESSION_EXPIRY_HOURS (default 24).
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SESSIONS_DIR = Path("data/_agent_sessions")
_EXPIRY_HOURS = int(os.getenv("AGENT_SESSION_EXPIRY_HOURS", "24"))


@dataclass
class AgentSession:
    """Persistent agent conversation state."""

    session_id: str
    agent_name: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    last_active: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    turn_count: int = 0

    # ── Factory ──────────────────────────────────────────────────────────

    @classmethod
    def create(
        cls,
        agent_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "AgentSession":
        """Create a new session."""
        now = time.time()
        return cls(
            session_id=uuid.uuid4().hex[:12],
            agent_name=agent_name,
            metadata=metadata or {},
            created_at=now,
            last_active=now,
        )

    # ── Persistence ──────────────────────────────────────────────────────

    def _path(self) -> Path:
        return _SESSIONS_DIR / f"{self.session_id}.json"

    def save(self) -> None:
        """Persist session to disk."""
        self.last_active = time.time()
        _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "session_id": self.session_id,
            "agent_name": self.agent_name,
            "messages": self.messages,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "last_active": self.last_active,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "turn_count": self.turn_count,
        }
        self._path().write_text(json.dumps(data, default=str), encoding="utf-8")

    @classmethod
    def load(cls, session_id: str) -> Optional["AgentSession"]:
        """Load session from disk. Returns None if not found or expired."""
        path = _SESSIONS_DIR / f"{session_id}.json"
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load session %s: %s", session_id, e)
            return None

        # Check expiry
        last_active = data.get("last_active", 0)
        if time.time() - last_active > _EXPIRY_HOURS * 3600:
            logger.info("Session %s expired, removing", session_id)
            path.unlink(missing_ok=True)
            return None

        return cls(
            session_id=data["session_id"],
            agent_name=data["agent_name"],
            messages=data.get("messages", []),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", 0),
            last_active=last_active,
            total_input_tokens=data.get("total_input_tokens", 0),
            total_output_tokens=data.get("total_output_tokens", 0),
            turn_count=data.get("turn_count", 0),
        )

    def delete(self) -> None:
        """Remove session from disk."""
        self._path().unlink(missing_ok=True)

    # ── Message management ───────────────────────────────────────────────

    def add_user_message(self, text: str) -> None:
        """Append a user message to history."""
        self.messages.append({"role": "user", "content": text})

    def add_assistant_message(self, content: List[Dict[str, Any]]) -> None:
        """Append an assistant message (may contain text + tool_use blocks)."""
        self.messages.append({"role": "assistant", "content": content})

    def add_tool_result(self, tool_use_id: str, result: str, is_error: bool = False) -> None:
        """Append a tool_result message."""
        block = {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": result,
        }
        if is_error:
            block["is_error"] = True

        # Tool results are grouped: if last message is already tool results, append
        if self.messages and self.messages[-1].get("role") == "user":
            last_content = self.messages[-1].get("content", [])
            if isinstance(last_content, list) and last_content and last_content[0].get("type") == "tool_result":
                last_content.append(block)
                return

        self.messages.append({"role": "user", "content": [block]})

    def record_usage(self, input_tokens: int, output_tokens: int) -> None:
        """Track token usage."""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    # ── Cleanup ──────────────────────────────────────────────────────────

    @classmethod
    def cleanup_expired(cls) -> int:
        """Remove all expired sessions. Returns count removed."""
        if not _SESSIONS_DIR.exists():
            return 0

        removed = 0
        cutoff = time.time() - _EXPIRY_HOURS * 3600
        for path in _SESSIONS_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("last_active", 0) < cutoff:
                    path.unlink()
                    removed += 1
            except (json.JSONDecodeError, OSError):
                path.unlink(missing_ok=True)
                removed += 1

        if removed:
            logger.info("Cleaned up %d expired agent sessions", removed)
        return removed

    @classmethod
    def list_recent(cls, limit: int = 20) -> List[Dict[str, Any]]:
        """List recent sessions (summary only, no messages)."""
        if not _SESSIONS_DIR.exists():
            return []

        sessions = []
        for path in _SESSIONS_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                sessions.append({
                    "session_id": data["session_id"],
                    "agent_name": data["agent_name"],
                    "metadata": data.get("metadata", {}),
                    "created_at": data.get("created_at", 0),
                    "last_active": data.get("last_active", 0),
                    "turn_count": data.get("turn_count", 0),
                    "total_tokens": data.get("total_input_tokens", 0) + data.get("total_output_tokens", 0),
                })
            except (json.JSONDecodeError, OSError):
                continue

        sessions.sort(key=lambda s: s["last_active"], reverse=True)
        return sessions[:limit]
