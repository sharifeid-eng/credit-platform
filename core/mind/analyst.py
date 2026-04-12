"""
Analyst Context Store — Persistent analyst profile for intelligent briefings.

Stores the analyst's current state: last session, priority companies,
upcoming IC dates, focus areas, recent correction patterns.

Updated by /eod command and session_end events.
Read by morning briefing and operator center.
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
_CONTEXT_PATH = _PROJECT_ROOT / "data" / "_master_mind" / "analyst_context.json"


@dataclass
class AnalystContext:
    """Persistent analyst profile."""

    last_session_at: str = ""
    priority_companies: List[str] = field(default_factory=list)
    upcoming_ic_dates: Dict[str, str] = field(default_factory=dict)  # company → date
    focus_areas: List[str] = field(default_factory=list)
    recent_corrections_summary: str = ""
    session_count: int = 0
    last_companies_touched: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "last_session_at": self.last_session_at,
            "priority_companies": self.priority_companies,
            "upcoming_ic_dates": self.upcoming_ic_dates,
            "focus_areas": self.focus_areas,
            "recent_corrections_summary": self.recent_corrections_summary,
            "session_count": self.session_count,
            "last_companies_touched": self.last_companies_touched,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> AnalystContext:
        return cls(
            last_session_at=d.get("last_session_at", ""),
            priority_companies=d.get("priority_companies", []),
            upcoming_ic_dates=d.get("upcoming_ic_dates", {}),
            focus_areas=d.get("focus_areas", []),
            recent_corrections_summary=d.get("recent_corrections_summary", ""),
            session_count=d.get("session_count", 0),
            last_companies_touched=d.get("last_companies_touched", []),
        )


def load_analyst_context(path: Optional[Path] = None) -> AnalystContext:
    """Load analyst context from disk."""
    p = path or _CONTEXT_PATH
    if not p.exists():
        return AnalystContext()
    try:
        with open(p, "r", encoding="utf-8") as f:
            return AnalystContext.from_dict(json.load(f))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load analyst context: %s", e)
        return AnalystContext()


def save_analyst_context(ctx: AnalystContext, path: Optional[Path] = None) -> None:
    """Save analyst context to disk."""
    p = path or _CONTEXT_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(ctx.to_dict(), f, indent=2, ensure_ascii=False)


def update_session_end(
    companies_touched: Optional[List[str]] = None,
    focus_areas: Optional[List[str]] = None,
    corrections_summary: str = "",
) -> AnalystContext:
    """Update analyst context at end of session."""
    ctx = load_analyst_context()
    ctx.last_session_at = datetime.now(timezone.utc).isoformat()
    ctx.session_count += 1
    if companies_touched:
        ctx.last_companies_touched = companies_touched
    if focus_areas:
        ctx.focus_areas = focus_areas
    if corrections_summary:
        ctx.recent_corrections_summary = corrections_summary
    save_analyst_context(ctx)
    return ctx
