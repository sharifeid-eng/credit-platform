"""
Intelligence Engine — Cross-company pattern detection.

Scans all company mind entries for:
- Same metric trending in same direction across 2+ companies
- Same risk flag in 2+ companies within 30 days
- Same covenant type under pressure across companies

Scoring: companies_affected × severity × recency.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.mind.schema import KnowledgeNode, upgrade_entry

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class Pattern:
    """A cross-company detected pattern."""

    pattern_type: str          # "metric_trend" | "risk_convergence" | "covenant_pressure"
    description: str
    companies_affected: List[str]
    metric_key: str = ""
    severity: str = "info"     # info | warning | critical
    evidence_node_ids: List[str] = field(default_factory=list)
    score: float = 0.0
    detected_at: str = ""

    def __post_init__(self):
        if not self.detected_at:
            self.detected_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_type": self.pattern_type,
            "description": self.description,
            "companies_affected": self.companies_affected,
            "metric_key": self.metric_key,
            "severity": self.severity,
            "evidence_node_ids": self.evidence_node_ids,
            "score": self.score,
            "detected_at": self.detected_at,
        }


class IntelligenceEngine:
    """Cross-company pattern detection and intelligence."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or (_PROJECT_ROOT / "data")

    def _get_all_companies(self) -> List[Dict[str, str]]:
        """Discover all company/product pairs from data directory."""
        companies = []
        if not self.data_dir.exists():
            return companies
        for co_dir in self.data_dir.iterdir():
            if not co_dir.is_dir() or co_dir.name.startswith("_"):
                continue
            mind_dir = co_dir / "mind"
            if mind_dir.exists():
                companies.append({
                    "company": co_dir.name,
                    "product": "",
                    "mind_dir": str(mind_dir),
                })
        return companies

    def _load_entity_nodes(self, mind_dir: Path) -> List[KnowledgeNode]:
        """Load entity nodes from a mind directory."""
        nodes = []
        entity_path = mind_dir / "entities.jsonl"
        if not entity_path.exists():
            return nodes
        try:
            with open(entity_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        upgrade_entry(d)
                        nodes.append(KnowledgeNode.from_dict(d))
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
        except OSError:
            pass
        return nodes

    def _load_all_mind_entries(self, mind_dir: Path) -> List[KnowledgeNode]:
        """Load all JSONL entries from a mind directory."""
        nodes = []
        if not mind_dir.exists():
            return nodes
        for jsonl_file in mind_dir.glob("*.jsonl"):
            try:
                with open(jsonl_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            d = json.loads(line)
                            upgrade_entry(d)
                            nodes.append(KnowledgeNode.from_dict(d))
                        except (json.JSONDecodeError, KeyError, ValueError):
                            continue
            except OSError:
                continue
        return nodes

    def detect_cross_company_patterns(
        self,
        lookback_days: int = 30,
    ) -> List[Pattern]:
        """Scan all companies for cross-company patterns.

        Returns:
            List of Pattern objects, sorted by score.
        """
        companies = self._get_all_companies()
        if len(companies) < 2:
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        patterns: List[Pattern] = []

        # Collect recent entity nodes by company
        company_entities: Dict[str, List[KnowledgeNode]] = {}
        for co in companies:
            key = f"{co['company']}/{co['product']}"
            mind_dir = Path(co["mind_dir"])
            entities = self._load_entity_nodes(mind_dir)
            # Filter to recent
            recent = []
            for e in entities:
                try:
                    ts = datetime.fromisoformat(e.timestamp.replace("Z", "+00:00"))
                    if ts >= cutoff:
                        recent.append(e)
                except (ValueError, TypeError):
                    recent.append(e)
            if recent:
                company_entities[key] = recent

        # Detect metric trends across companies
        patterns.extend(self._detect_metric_trends(company_entities))

        # Detect risk flag convergence
        patterns.extend(self._detect_risk_convergence(company_entities))

        # Detect covenant pressure
        patterns.extend(self._detect_covenant_pressure(company_entities))

        # Sort by score
        patterns.sort(key=lambda p: p.score, reverse=True)
        return patterns

    def _detect_metric_trends(
        self, company_entities: Dict[str, List[KnowledgeNode]]
    ) -> List[Pattern]:
        """Find same metric moving in same direction across companies."""
        # Group by metric key across companies
        metric_by_company: Dict[str, Dict[str, List[KnowledgeNode]]] = defaultdict(dict)

        for company_key, nodes in company_entities.items():
            for node in nodes:
                entity_key = node.metadata.get("entity_key", "")
                if entity_key and node.metadata.get("entity_type") == "METRIC":
                    if company_key not in metric_by_company[entity_key]:
                        metric_by_company[entity_key][company_key] = []
                    metric_by_company[entity_key][company_key].append(node)

        patterns = []
        for metric_key, by_company in metric_by_company.items():
            if len(by_company) < 2:
                continue

            # Check for supersession patterns (value changed)
            companies_with_changes = []
            for company_key, nodes in by_company.items():
                # If there are multiple nodes, values have changed
                if len(nodes) >= 2:
                    companies_with_changes.append(company_key)

            if len(companies_with_changes) >= 2:
                severity = "warning" if len(companies_with_changes) >= 3 else "info"
                score = len(companies_with_changes) * 2.0
                patterns.append(Pattern(
                    pattern_type="metric_trend",
                    description=f"Metric '{metric_key}' is changing across {len(companies_with_changes)} companies: {', '.join(companies_with_changes)}",
                    companies_affected=companies_with_changes,
                    metric_key=metric_key,
                    severity=severity,
                    score=score,
                ))

        return patterns

    def _detect_risk_convergence(
        self, company_entities: Dict[str, List[KnowledgeNode]]
    ) -> List[Pattern]:
        """Find same risk flags appearing across multiple companies."""
        risk_by_company: Dict[str, List[str]] = defaultdict(list)

        for company_key, nodes in company_entities.items():
            for node in nodes:
                if node.metadata.get("entity_type") == "RISK_FLAG":
                    risk_key = node.metadata.get("entity_key", "")
                    if risk_key:
                        risk_by_company[risk_key].append(company_key)

        patterns = []
        for risk_key, companies in risk_by_company.items():
            unique = list(set(companies))
            if len(unique) >= 2:
                patterns.append(Pattern(
                    pattern_type="risk_convergence",
                    description=f"Risk flag '{risk_key}' detected in {len(unique)} companies: {', '.join(unique)}",
                    companies_affected=unique,
                    metric_key=risk_key,
                    severity="warning" if len(unique) >= 3 else "info",
                    score=len(unique) * 3.0,
                ))

        return patterns

    def _detect_covenant_pressure(
        self, company_entities: Dict[str, List[KnowledgeNode]]
    ) -> List[Pattern]:
        """Find same covenant types under pressure across companies."""
        covenant_by_company: Dict[str, List[str]] = defaultdict(list)

        for company_key, nodes in company_entities.items():
            for node in nodes:
                if node.metadata.get("entity_type") == "COVENANT":
                    cov_key = node.metadata.get("entity_key", "")
                    if cov_key:
                        covenant_by_company[cov_key].append(company_key)

        patterns = []
        for cov_key, companies in covenant_by_company.items():
            unique = list(set(companies))
            if len(unique) >= 2:
                patterns.append(Pattern(
                    pattern_type="covenant_pressure",
                    description=f"Covenant '{cov_key}' active across {len(unique)} companies: {', '.join(unique)}",
                    companies_affected=unique,
                    metric_key=cov_key,
                    severity="info",
                    score=len(unique) * 1.5,
                ))

        return patterns

    def save_patterns(self, patterns: List[Pattern]) -> None:
        """Save detected patterns to master mind directory."""
        patterns_path = self.data_dir / "_master_mind" / "patterns.json"
        patterns_path.parent.mkdir(parents=True, exist_ok=True)
        with open(patterns_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "patterns": [p.to_dict() for p in patterns],
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "count": len(patterns),
                },
                f, indent=2, ensure_ascii=False,
            )

    def load_patterns(self) -> List[Pattern]:
        """Load previously saved patterns."""
        patterns_path = self.data_dir / "_master_mind" / "patterns.json"
        if not patterns_path.exists():
            return []
        try:
            with open(patterns_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [
                Pattern(**p) for p in data.get("patterns", [])
            ]
        except (json.JSONDecodeError, OSError, TypeError):
            return []
