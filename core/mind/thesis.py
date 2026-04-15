"""
Thesis Tracker — Per-company investment thesis with drift detection.

Stores structured investment theses with measurable pillars that can be
automatically checked against live tape data. When a metric breaches a
pillar threshold, the system generates a DriftAlert.

Storage:
    data/{company}/mind/thesis.json     — current thesis (mutable)
    data/{company}/mind/thesis_log.jsonl — append-only change log

Conviction Score: 0-100 per company, based on pillar evidence strength,
recency, contradictions, and trend consistency.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class ThesisPillar:
    """A single measurable claim in an investment thesis."""

    id: str
    claim: str                                    # "Collection rate will remain above 85%"
    metric_key: Optional[str] = None              # "collection_rate" — links to computed metric
    threshold: Optional[float] = None             # 0.85
    direction: Optional[str] = None               # "above" | "below" | "stable"
    evidence_node_ids: List[str] = field(default_factory=list)
    status: str = "holding"                       # holding | strengthening | weakening | broken | retired
    conviction_score: int = 50                    # 0-100
    created_at: str = ""
    last_checked: str = ""
    last_value: Optional[float] = None            # most recent observed value
    notes: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if self.direction and self.direction not in ("above", "below", "stable"):
            raise ValueError(f"Invalid direction: {self.direction}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "claim": self.claim,
            "metric_key": self.metric_key,
            "threshold": self.threshold,
            "direction": self.direction,
            "evidence_node_ids": self.evidence_node_ids,
            "status": self.status,
            "conviction_score": self.conviction_score,
            "created_at": self.created_at,
            "last_checked": self.last_checked,
            "last_value": self.last_value,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> ThesisPillar:
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            claim=d.get("claim", ""),
            metric_key=d.get("metric_key"),
            threshold=d.get("threshold"),
            direction=d.get("direction"),
            evidence_node_ids=d.get("evidence_node_ids", []),
            status=d.get("status", "holding"),
            conviction_score=d.get("conviction_score", 50),
            created_at=d.get("created_at", ""),
            last_checked=d.get("last_checked", ""),
            last_value=d.get("last_value"),
            notes=d.get("notes", ""),
        )


@dataclass
class DriftAlert:
    """Alert when a thesis pillar's metric has drifted."""

    pillar_id: str
    claim: str
    metric_key: str
    expected: float
    actual: float
    direction: str
    severity: str           # "info" | "warning" | "critical"
    recommendation: str
    previous_status: str
    new_status: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pillar_id": self.pillar_id,
            "claim": self.claim,
            "metric_key": self.metric_key,
            "expected": self.expected,
            "actual": self.actual,
            "direction": self.direction,
            "severity": self.severity,
            "recommendation": self.recommendation,
            "previous_status": self.previous_status,
            "new_status": self.new_status,
        }


@dataclass
class InvestmentThesis:
    """Per-company structured investment thesis."""

    company: str
    product: str
    title: str
    status: str = "active"              # active | under_review | archived
    pillars: List[ThesisPillar] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    version: int = 1

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> Dict[str, Any]:
        return {
            "company": self.company,
            "product": self.product,
            "title": self.title,
            "status": self.status,
            "pillars": [p.to_dict() for p in self.pillars],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> InvestmentThesis:
        return cls(
            company=d.get("company", ""),
            product=d.get("product", ""),
            title=d.get("title", ""),
            status=d.get("status", "active"),
            pillars=[ThesisPillar.from_dict(p) for p in d.get("pillars", [])],
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            version=d.get("version", 1),
        )

    @property
    def conviction_score(self) -> int:
        """Aggregate conviction score across all active pillars (0-100)."""
        active = [p for p in self.pillars if p.status != "retired"]
        if not active:
            return 0
        return round(sum(p.conviction_score for p in active) / len(active))

    @property
    def active_pillars(self) -> List[ThesisPillar]:
        return [p for p in self.pillars if p.status != "retired"]

    @property
    def weakening_pillars(self) -> List[ThesisPillar]:
        return [p for p in self.pillars if p.status == "weakening"]

    @property
    def broken_pillars(self) -> List[ThesisPillar]:
        return [p for p in self.pillars if p.status == "broken"]


class ThesisTracker:
    """Manages investment theses for companies with drift detection."""

    def __init__(self, company: str, product: str, base_dir: Optional[Path] = None):
        self.company = company
        self.product = product
        if base_dir:
            self.mind_dir = Path(base_dir)
        else:
            self.mind_dir = _PROJECT_ROOT / "data" / company / "mind"
        self.mind_dir.mkdir(parents=True, exist_ok=True)

    @property
    def _thesis_path(self) -> Path:
        return self.mind_dir / "thesis.json"

    @property
    def _log_path(self) -> Path:
        return self.mind_dir / "thesis_log.jsonl"

    def load(self) -> Optional[InvestmentThesis]:
        """Load the current thesis. Returns None if none exists."""
        if not self._thesis_path.exists():
            return None
        try:
            with open(self._thesis_path, "r", encoding="utf-8") as f:
                return InvestmentThesis.from_dict(json.load(f))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("ThesisTracker: failed to load thesis: %s", e)
            return None

    def save(self, thesis: InvestmentThesis, change_reason: str = "") -> None:
        """Save thesis and append to change log."""
        thesis.updated_at = datetime.now(timezone.utc).isoformat()

        with open(self._thesis_path, "w", encoding="utf-8") as f:
            json.dump(thesis.to_dict(), f, indent=2, ensure_ascii=False)

        # Append to log
        log_entry = {
            "timestamp": thesis.updated_at,
            "version": thesis.version,
            "change_reason": change_reason,
            "conviction_score": thesis.conviction_score,
            "pillar_statuses": {p.id: p.status for p in thesis.pillars},
            "title": thesis.title,
        }
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        # Publish event
        try:
            from core.mind.event_bus import event_bus, Events
            event_bus.publish(Events.THESIS_UPDATED, {
                "company": self.company,
                "product": self.product,
                "conviction_score": thesis.conviction_score,
                "change_reason": change_reason,
            })
        except Exception:
            pass

    def check_drift(
        self,
        latest_metrics: Dict[str, float],
    ) -> List[DriftAlert]:
        """Check thesis pillars against latest metrics for drift.

        Args:
            latest_metrics: Dict of metric_key → current value
                           (e.g., {"collection_rate": 0.82, "par_30_pct": 0.05})

        Returns:
            List of DriftAlerts for pillars that have drifted.
        """
        thesis = self.load()
        if not thesis:
            return []

        alerts = []
        now = datetime.now(timezone.utc).isoformat()

        for pillar in thesis.active_pillars:
            if not pillar.metric_key or pillar.threshold is None or not pillar.direction:
                continue

            actual = latest_metrics.get(pillar.metric_key)
            if actual is None:
                continue

            previous_status = pillar.status
            pillar.last_checked = now
            pillar.last_value = actual

            # Determine if breached
            breached = False
            near_breach = False
            headroom = 0.0

            if pillar.direction == "above":
                headroom = (actual - pillar.threshold) / max(abs(pillar.threshold), 0.001)
                breached = actual < pillar.threshold
                near_breach = 0 <= headroom < 0.10  # within 10%
            elif pillar.direction == "below":
                headroom = (pillar.threshold - actual) / max(abs(pillar.threshold), 0.001)
                breached = actual > pillar.threshold
                near_breach = 0 <= headroom < 0.10
            elif pillar.direction == "stable":
                deviation = abs(actual - pillar.threshold) / max(abs(pillar.threshold), 0.001)
                breached = deviation > 0.20  # >20% deviation
                near_breach = 0.10 < deviation <= 0.20

            # Status transitions
            if breached:
                new_status = "broken"
                severity = "critical"
                pillar.conviction_score = max(0, pillar.conviction_score - 30)
            elif near_breach:
                new_status = "weakening"
                severity = "warning"
                pillar.conviction_score = max(0, pillar.conviction_score - 10)
            else:
                # Healthy — strengthen if previously weakening
                if previous_status in ("weakening", "broken"):
                    new_status = "holding"
                    severity = "info"
                    pillar.conviction_score = min(100, pillar.conviction_score + 5)
                elif previous_status == "holding":
                    new_status = "strengthening" if headroom > 0.20 else "holding"
                    severity = "info" if new_status != previous_status else ""
                    pillar.conviction_score = min(100, pillar.conviction_score + 2)
                else:
                    new_status = previous_status
                    severity = ""

            pillar.status = new_status

            # Only alert on meaningful transitions
            if new_status != previous_status or severity in ("warning", "critical"):
                direction_word = "above" if pillar.direction == "above" else "below"
                if breached:
                    rec = f"Thesis pillar breached. Actual {actual:.2%} vs threshold {pillar.threshold:.2%}. Review thesis."
                elif near_breach:
                    rec = f"Approaching threshold. Actual {actual:.2%}, threshold {pillar.threshold:.2%}. Monitor closely."
                else:
                    rec = f"Recovering. Actual {actual:.2%} now meets threshold {pillar.threshold:.2%}."

                alerts.append(DriftAlert(
                    pillar_id=pillar.id,
                    claim=pillar.claim,
                    metric_key=pillar.metric_key,
                    expected=pillar.threshold,
                    actual=actual,
                    direction=pillar.direction,
                    severity=severity,
                    recommendation=rec,
                    previous_status=previous_status,
                    new_status=new_status,
                ))

        # Save updated statuses
        if alerts:
            thesis.version += 1
            self.save(thesis, change_reason=f"Drift check: {len(alerts)} alerts")

        return alerts

    def get_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Read thesis evolution log (newest first)."""
        if not self._log_path.exists():
            return []
        entries = []
        try:
            with open(self._log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except OSError:
            pass
        entries.reverse()
        return entries[:limit]

    def get_ai_context(self) -> str:
        """Format thesis for AI prompt injection (Layer 5)."""
        thesis = self.load()
        if not thesis:
            return ""

        lines = [f"## Investment Thesis: {thesis.title}"]
        lines.append(f"Conviction: {thesis.conviction_score}/100 | Status: {thesis.status}")

        for p in thesis.active_pillars:
            status_icon = {
                "holding": "=",
                "strengthening": "+",
                "weakening": "!",
                "broken": "X",
            }.get(p.status, "?")
            line = f"  [{status_icon}] {p.claim}"
            if p.last_value is not None and p.threshold is not None:
                line += f" (actual: {p.last_value:.2%}, threshold: {p.threshold:.2%})"
            lines.append(line)

        broken = thesis.broken_pillars
        if broken:
            lines.append(f"ALERT: {len(broken)} broken pillar(s) — thesis under pressure")

        return "\n".join(lines)
