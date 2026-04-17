"""
Morning Briefing Generator — Proactive intelligence for session start.

Generates a prioritized briefing with:
1. Since Last Session — what changed
2. Priority Actions — ranked by urgency
3. Cross-Company Patterns — from intelligence engine
4. Thesis Alerts — weakening/broken pillars
5. Learning Summary — auto-generated rules
6. Recommended Actions — specific, actionable items

Urgency scoring:
- IC meeting < 3 days + stale tape = CRITICAL
- Broken thesis pillar = HIGH
- Stale tape > 30 days = MEDIUM
- Unresolved contradictions = MEDIUM
- Aging mind entries = LOW

No AI calls — pure file I/O + computation. Target: < 3 seconds.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class BriefingItem:
    """A single item in the morning briefing."""

    title: str
    description: str
    severity: str = "info"     # info | medium | high | critical
    company: str = ""
    action: str = ""           # suggested action
    link: str = ""             # URL/route to navigate to

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "company": self.company,
            "action": self.action,
            "link": self.link,
        }


@dataclass
class Briefing:
    """Complete morning briefing."""

    since_last_session: List[BriefingItem] = field(default_factory=list)
    priority_actions: List[BriefingItem] = field(default_factory=list)
    cross_company_patterns: List[Dict[str, Any]] = field(default_factory=list)
    thesis_alerts: List[Dict[str, Any]] = field(default_factory=list)
    learning_summary: Dict[str, Any] = field(default_factory=dict)
    agent_activity: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    generated_at: str = ""

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "since_last_session": [i.to_dict() for i in self.since_last_session],
            "priority_actions": [i.to_dict() for i in self.priority_actions],
            "cross_company_patterns": self.cross_company_patterns,
            "thesis_alerts": self.thesis_alerts,
            "learning_summary": self.learning_summary,
            "agent_activity": self.agent_activity,
            "recommendations": self.recommendations,
            "generated_at": self.generated_at,
        }


def generate_morning_briefing(data_dir: Optional[Path] = None) -> Briefing:
    """Generate a complete morning briefing.

    Reads from existing files only — no API calls, no AI.

    Returns:
        Briefing object with all sections populated.
    """
    data_dir = data_dir or (_PROJECT_ROOT / "data")
    briefing = Briefing()

    # Load analyst context
    from core.mind.analyst import load_analyst_context
    ctx = load_analyst_context()
    last_session = _parse_timestamp(ctx.last_session_at)

    # Discover companies
    companies = _discover_companies(data_dir)

    # 1. Since Last Session
    briefing.since_last_session = _build_since_last_session(
        companies, last_session, data_dir
    )

    # 2. Priority Actions
    briefing.priority_actions = _build_priority_actions(
        companies, ctx, data_dir
    )

    # 3. Cross-Company Patterns
    try:
        from core.mind.intelligence import IntelligenceEngine
        engine = IntelligenceEngine(data_dir)
        patterns = engine.detect_cross_company_patterns()
        briefing.cross_company_patterns = [p.to_dict() for p in patterns[:5]]
    except Exception as e:
        logger.warning("Pattern detection failed: %s", e)

    # 4. Thesis Alerts
    briefing.thesis_alerts = _build_thesis_alerts(companies, data_dir)

    # 5. Learning Summary
    briefing.learning_summary = _build_learning_summary(companies, data_dir, last_session)

    # 6. Agent Activity
    briefing.agent_activity = _build_agent_activity(last_session)

    # 7. Recommendations
    briefing.recommendations = _build_recommendations(briefing)

    return briefing


def _parse_timestamp(ts: str) -> Optional[datetime]:
    """Parse an ISO timestamp, returning None on failure."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _discover_companies(data_dir: Path) -> List[Dict[str, str]]:
    """Find all company/product pairs."""
    companies = []
    if not data_dir.exists():
        return companies
    for co_dir in data_dir.iterdir():
        if not co_dir.is_dir() or co_dir.name.startswith("_"):
            continue
        for prod_dir in co_dir.iterdir():
            if not prod_dir.is_dir():
                continue
            companies.append({
                "company": co_dir.name,
                "product": prod_dir.name,
                "path": str(prod_dir),
            })
    return companies


def _build_since_last_session(
    companies: List[Dict], last_session: Optional[datetime], data_dir: Path
) -> List[BriefingItem]:
    """What changed since last session."""
    items = []

    if not last_session:
        items.append(BriefingItem(
            title="First Session",
            description="Welcome! This is your first session with the intelligence system.",
            severity="info",
        ))
        return items

    days_since = (datetime.now(timezone.utc) - last_session).days

    if days_since > 0:
        items.append(BriefingItem(
            title=f"{days_since} day(s) since last session",
            description=f"Last session: {last_session.strftime('%Y-%m-%d %H:%M UTC')}",
            severity="info",
        ))

    # Check activity log for recent events
    activity_path = data_dir.parent / "reports" / "activity_log.jsonl"
    if activity_path.exists():
        new_events = 0
        try:
            with open(activity_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        ts = _parse_timestamp(event.get("timestamp", ""))
                        if ts and ts > last_session:
                            new_events += 1
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass

        if new_events > 0:
            items.append(BriefingItem(
                title=f"{new_events} platform events since last session",
                description="AI calls, tape loads, document ingestions, etc.",
                severity="info",
            ))

    return items


def _build_priority_actions(
    companies: List[Dict], ctx: Any, data_dir: Path
) -> List[BriefingItem]:
    """Build prioritized action items."""
    items = []
    now = datetime.now(timezone.utc)

    for co in companies:
        company = co["company"]
        product = co["product"]
        co_path = Path(co["path"])

        # Check tape freshness
        tapes = list(co_path.glob("*.csv")) + list(co_path.glob("*.xlsx"))
        if tapes:
            latest = max(tapes, key=lambda f: f.stat().st_mtime)
            days_old = (now - datetime.fromtimestamp(
                latest.stat().st_mtime, tz=timezone.utc
            )).days
            if days_old > 60:
                items.append(BriefingItem(
                    title=f"{company}: tape {days_old}d stale",
                    description=f"Latest tape is {days_old} days old. Request updated tape.",
                    severity="high" if days_old > 90 else "medium",
                    company=company,
                    action=f"Request updated tape for {company}",
                ))
            elif days_old > 30:
                items.append(BriefingItem(
                    title=f"{company}: tape {days_old}d old",
                    description="Approaching staleness threshold.",
                    severity="medium",
                    company=company,
                ))

        # Check IC proximity
        ic_dates = getattr(ctx, "upcoming_ic_dates", {})
        if company in ic_dates:
            try:
                ic_date = datetime.fromisoformat(ic_dates[company])
                days_until = (ic_date - now).days
                if 0 <= days_until <= 3:
                    items.append(BriefingItem(
                        title=f"{company}: IC meeting in {days_until}d",
                        description=f"IC meeting on {ic_date.strftime('%Y-%m-%d')}. Prepare materials.",
                        severity="critical",
                        company=company,
                        action=f"Run /ic-prep {company}",
                    ))
            except (ValueError, TypeError):
                pass

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "info": 3}
    items.sort(key=lambda x: severity_order.get(x.severity, 3))
    return items


def _build_thesis_alerts(
    companies: List[Dict], data_dir: Path
) -> List[Dict[str, Any]]:
    """Check all theses for drift alerts."""
    alerts = []
    for co in companies:
        thesis_path = Path(co["path"]).parent / "mind" / "thesis.json"
        if not thesis_path.exists():
            continue
        try:
            with open(thesis_path, "r", encoding="utf-8") as f:
                thesis_data = json.load(f)
            for pillar in thesis_data.get("pillars", []):
                if pillar.get("status") in ("weakening", "broken"):
                    alerts.append({
                        "company": co["company"],
                        "pillar": pillar.get("claim", ""),
                        "status": pillar.get("status"),
                        "last_value": pillar.get("last_value"),
                        "threshold": pillar.get("threshold"),
                        "conviction_score": pillar.get("conviction_score", 0),
                    })
        except (json.JSONDecodeError, OSError):
            continue
    return alerts


def _build_learning_summary(
    companies: List[Dict], data_dir: Path, last_session: Optional[datetime]
) -> Dict[str, Any]:
    """Summarize learning rules generated since last session."""
    total_rules = 0
    new_rules = 0

    for co in companies:
        mind_dir = Path(co["path"]).parent / "mind"
        for jsonl_file in mind_dir.glob("*.jsonl"):
            try:
                with open(jsonl_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if '"node_type": "rule"' in line or '"auto_generated": true' in line:
                            total_rules += 1
                            if last_session:
                                try:
                                    d = json.loads(line.strip())
                                    ts = _parse_timestamp(d.get("timestamp", ""))
                                    if ts and ts > last_session:
                                        new_rules += 1
                                except (json.JSONDecodeError, KeyError):
                                    pass
            except OSError:
                continue

    return {
        "total_rules": total_rules,
        "new_since_last_session": new_rules,
    }


def _build_agent_activity(last_session: Optional[datetime]) -> Dict[str, Any]:
    """Summarize agent session activity since last analyst login."""
    sessions_dir = _PROJECT_ROOT / "data" / "_agent_sessions"
    if not sessions_dir.exists():
        return {"total_sessions": 0, "sessions": []}

    import json
    cutoff = last_session.timestamp() if last_session else 0
    recent = []

    for path in sessions_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("last_active", 0) > cutoff:
                recent.append({
                    "agent": data.get("agent_name", "?"),
                    "company": data.get("metadata", {}).get("company", "?"),
                    "product": data.get("metadata", {}).get("product", "?"),
                    "turns": data.get("turn_count", 0),
                    "tokens": data.get("total_input_tokens", 0) + data.get("total_output_tokens", 0),
                })
        except Exception:
            continue

    recent.sort(key=lambda s: s.get("tokens", 0), reverse=True)

    return {
        "total_sessions": len(recent),
        "total_tokens": sum(s.get("tokens", 0) for s in recent),
        "sessions": recent[:10],
    }


def _build_recommendations(briefing: Briefing) -> List[str]:
    """Generate actionable recommendations from the briefing data."""
    recs = []

    critical = [a for a in briefing.priority_actions if a.severity == "critical"]
    if critical:
        recs.append(f"URGENT: {len(critical)} critical action(s) require immediate attention.")

    broken = [a for a in briefing.thesis_alerts if a.get("status") == "broken"]
    if broken:
        companies = list(set(a.get("company", "") for a in broken))
        recs.append(f"Review broken thesis pillars for: {', '.join(companies)}")

    patterns = briefing.cross_company_patterns
    if patterns:
        recs.append(f"{len(patterns)} cross-company pattern(s) detected. Run /emerge for details.")

    if briefing.learning_summary.get("new_since_last_session", 0) > 0:
        n = briefing.learning_summary["new_since_last_session"]
        recs.append(f"{n} learning rule(s) auto-generated. Run /learn to review.")

    if not recs:
        recs.append("No urgent items. Good time for framework audit or deep work.")

    return recs
