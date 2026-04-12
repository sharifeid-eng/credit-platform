"""
Session State Tracker — Tracks events during the current session.

Listens to the event bus and records what happened during this session.
Persisted to reports/session_state.json for delta comparisons.

Used by the morning briefing to show "Since your last session: ..."
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_STATE_PATH = _PROJECT_ROOT / "reports" / "session_state.json"


@dataclass
class SessionState:
    """Tracks what happened during the current session."""

    started_at: str = ""
    ended_at: str = ""
    tapes_loaded: List[str] = field(default_factory=list)
    documents_ingested: List[str] = field(default_factory=list)
    ai_calls: int = 0
    corrections_recorded: int = 0
    rules_generated: int = 0
    thesis_checks: int = 0
    companies_touched: List[str] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        if not self.started_at:
            self.started_at = datetime.now(timezone.utc).isoformat()

    def record_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Record an event that happened during this session."""
        company = payload.get("company", "")
        if company and company not in self.companies_touched:
            self.companies_touched.append(company)

        if event_type == "tape_ingested":
            tape = payload.get("snapshot", "unknown")
            self.tapes_loaded.append(tape)
        elif event_type == "document_ingested":
            doc = payload.get("filename", payload.get("doc_id", "unknown"))
            self.documents_ingested.append(doc)
        elif event_type == "correction_recorded":
            self.corrections_recorded += 1
        elif event_type == "thesis_updated":
            self.thesis_checks += 1
        elif event_type == "mind_entry_created":
            meta = payload.get("metadata", {})
            if meta.get("auto_generated"):
                self.rules_generated += 1

        self.events.append({
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "company": company,
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "tapes_loaded": self.tapes_loaded,
            "documents_ingested": self.documents_ingested,
            "ai_calls": self.ai_calls,
            "corrections_recorded": self.corrections_recorded,
            "rules_generated": self.rules_generated,
            "thesis_checks": self.thesis_checks,
            "companies_touched": self.companies_touched,
            "event_count": len(self.events),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> SessionState:
        return cls(
            started_at=d.get("started_at", ""),
            ended_at=d.get("ended_at", ""),
            tapes_loaded=d.get("tapes_loaded", []),
            documents_ingested=d.get("documents_ingested", []),
            ai_calls=d.get("ai_calls", 0),
            corrections_recorded=d.get("corrections_recorded", 0),
            rules_generated=d.get("rules_generated", 0),
            thesis_checks=d.get("thesis_checks", 0),
            companies_touched=d.get("companies_touched", []),
        )

    @property
    def summary(self) -> str:
        """Human-readable session summary."""
        parts = []
        if self.tapes_loaded:
            parts.append(f"{len(self.tapes_loaded)} tape(s) loaded")
        if self.documents_ingested:
            parts.append(f"{len(self.documents_ingested)} document(s) ingested")
        if self.corrections_recorded:
            parts.append(f"{self.corrections_recorded} correction(s)")
        if self.rules_generated:
            parts.append(f"{self.rules_generated} rule(s) auto-generated")
        if self.thesis_checks:
            parts.append(f"{self.thesis_checks} thesis check(s)")
        if self.companies_touched:
            parts.append(f"Companies: {', '.join(self.companies_touched)}")
        return "; ".join(parts) if parts else "No significant activity"


# Global session state (created fresh each app launch)
_current_session: Optional[SessionState] = None


def get_current_session() -> SessionState:
    """Get or create the current session state."""
    global _current_session
    if _current_session is None:
        _current_session = SessionState()
    return _current_session


def save_session_state(path: Optional[Path] = None) -> None:
    """Save current session state to disk."""
    p = path or _STATE_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    session = get_current_session()
    session.ended_at = datetime.now(timezone.utc).isoformat()
    with open(p, "w", encoding="utf-8") as f:
        json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)


def load_last_session(path: Optional[Path] = None) -> Optional[SessionState]:
    """Load the previous session state from disk."""
    p = path or _STATE_PATH
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return SessionState.from_dict(json.load(f))
    except (json.JSONDecodeError, OSError):
        return None


def get_delta_since_last() -> Dict[str, Any]:
    """Compare current session with last saved session."""
    last = load_last_session()
    current = get_current_session()

    if not last:
        return {
            "has_previous": False,
            "message": "No previous session found.",
        }

    return {
        "has_previous": True,
        "last_session_at": last.started_at,
        "last_session_ended": last.ended_at,
        "last_summary": last.summary,
        "current_summary": current.summary,
        "days_since": _days_between(last.ended_at, current.started_at),
    }


def _days_between(ts1: str, ts2: str) -> int:
    """Calculate days between two ISO timestamps."""
    try:
        dt1 = datetime.fromisoformat(ts1.replace("Z", "+00:00"))
        dt2 = datetime.fromisoformat(ts2.replace("Z", "+00:00"))
        return abs((dt2 - dt1).days)
    except (ValueError, TypeError):
        return 0
