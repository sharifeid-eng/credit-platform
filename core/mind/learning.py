"""
Learning Engine — Closed-loop learning from analyst corrections.

Parses the semantic difference between AI output and analyst corrections
to auto-generate learning rules. Rules are stored as KnowledgeNodes with
node_type="rule" and can be promoted to methodology-level (Layer 3)
after sufficient validation.

Key behaviors:
- analyze_correction() → extracts a natural-language rule from a diff
- extract_patterns() → groups recent corrections by type, surfaces codification candidates
- get_correction_frequency() → tracks how often each correction type occurs
- Rules have last_triggered timestamps and decay after 90 days of disuse
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.mind.schema import KnowledgeNode, Relation, make_node

logger = logging.getLogger(__name__)


# Correction classification categories
CORRECTION_TYPES = {
    "tone_shift",            # positive→cautious, cautious→critical, etc.
    "metric_relabel",        # changed a metric name or unit
    "threshold_override",    # analyst disagrees with AI's threshold interpretation
    "methodology_correction",  # wrong formula or calculation approach
    "data_caveat",           # AI missed a data limitation
    "formatting",            # structural/style changes
    "factual_error",         # AI stated something incorrect
    "missing_context",       # AI omitted important context
    "other",
}

# Tone words for detecting tone shifts
_POSITIVE_WORDS = {"strong", "healthy", "excellent", "robust", "solid", "good", "positive", "favorable"}
_CAUTIOUS_WORDS = {"moderate", "acceptable", "adequate", "fair", "reasonable"}
_NEGATIVE_WORDS = {"weak", "poor", "concerning", "deteriorating", "critical", "alarming", "risk", "caution", "cautious"}


class LearningRule:
    """A rule auto-generated from analyst corrections."""

    def __init__(
        self,
        category: str,
        rule_text: str,
        trigger_condition: str = "",
        examples: Optional[List[Dict[str, str]]] = None,
        confidence: float = 0.7,
        source_correction_ids: Optional[List[str]] = None,
    ):
        self.id = str(uuid.uuid4())
        self.category = category
        self.rule_text = rule_text
        self.trigger_condition = trigger_condition
        self.examples = examples or []
        self.confidence = confidence
        self.source_correction_ids = source_correction_ids or []
        self.created_at = datetime.now(timezone.utc).isoformat()

    def to_knowledge_node(self) -> KnowledgeNode:
        """Convert to a KnowledgeNode for storage in the mind system."""
        relations = []
        for cid in self.source_correction_ids:
            relations.append(Relation(
                target_id=cid,
                relation_type="derived_from",
                confidence=self.confidence,
            ))

        return make_node(
            category="corrections",  # stored in corrections.jsonl
            content=self.rule_text,
            metadata={
                "rule_category": self.category,
                "trigger_condition": self.trigger_condition,
                "examples": self.examples,
                "confidence": self.confidence,
                "auto_generated": True,
                "last_triggered": None,
                "trigger_count": 0,
            },
            node_type="rule",
            relations=relations,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "rule_text": self.rule_text,
            "trigger_condition": self.trigger_condition,
            "examples": self.examples,
            "confidence": self.confidence,
            "source_correction_ids": self.source_correction_ids,
            "created_at": self.created_at,
        }


class LearningEngine:
    """Analyzes corrections and extracts learning rules."""

    def analyze_correction(
        self,
        original: str,
        corrected: str,
        context: str = "",
    ) -> Optional[LearningRule]:
        """Analyze a single correction and extract a learning rule.

        Args:
            original: The AI-generated text.
            corrected: The analyst's corrected version.
            context: Additional context (section name, metric values, etc.).

        Returns:
            A LearningRule if a meaningful pattern is detected, else None.
        """
        if not original or not corrected:
            return None

        # Calculate change magnitude
        orig_words = original.lower().split()
        corr_words = corrected.lower().split()
        if not orig_words:
            return None

        # Simple diff: words added and removed
        orig_set = set(orig_words)
        corr_set = set(corr_words)
        added = corr_set - orig_set
        removed = orig_set - corr_set
        change_pct = len(added | removed) / max(len(orig_set | corr_set), 1)

        # Skip trivial changes (<5%)
        if change_pct < 0.05:
            return None

        # Classify the correction type
        correction_type, details = self._classify_correction(
            original, corrected, added, removed, context
        )

        # Generate rule text
        rule_text = self._generate_rule(correction_type, details, context)
        if not rule_text:
            return None

        trigger_condition = details.get("trigger", "")

        return LearningRule(
            category=correction_type,
            rule_text=rule_text,
            trigger_condition=trigger_condition,
            examples=[{
                "original_excerpt": original[:200],
                "corrected_excerpt": corrected[:200],
            }],
            confidence=min(0.9, 0.5 + change_pct),  # higher change = higher confidence
        )

    def _classify_correction(
        self,
        original: str,
        corrected: str,
        added: set,
        removed: set,
        context: str,
    ) -> Tuple[str, Dict[str, Any]]:
        """Classify a correction into a type with details."""
        orig_lower = original.lower()
        corr_lower = corrected.lower()

        # Check for tone shift
        orig_positive = len(_POSITIVE_WORDS & set(orig_lower.split()))
        orig_negative = len(_NEGATIVE_WORDS & set(orig_lower.split()))
        corr_positive = len(_POSITIVE_WORDS & set(corr_lower.split()))
        corr_negative = len(_NEGATIVE_WORDS & set(corr_lower.split()))

        if orig_positive > orig_negative and corr_negative > corr_positive:
            return "tone_shift", {
                "from": "positive",
                "to": "cautious/negative",
                "trigger": context,
            }
        if orig_negative > orig_positive and corr_positive > corr_negative:
            return "tone_shift", {
                "from": "negative",
                "to": "positive",
                "trigger": context,
            }

        # Check for metric/number changes
        orig_numbers = set(re.findall(r'\d+\.?\d*%?', original))
        corr_numbers = set(re.findall(r'\d+\.?\d*%?', corrected))
        if orig_numbers != corr_numbers and orig_numbers and corr_numbers:
            return "threshold_override", {
                "original_values": list(orig_numbers),
                "corrected_values": list(corr_numbers),
                "trigger": context,
            }

        # Check for data caveat additions
        caveat_words = {"however", "note that", "caveat", "limitation", "caution", "importantly"}
        if any(w in corr_lower for w in caveat_words) and not any(w in orig_lower for w in caveat_words):
            return "data_caveat", {
                "added_caveats": [w for w in caveat_words if w in corr_lower and w not in orig_lower],
                "trigger": context,
            }

        # Check for factual corrections (complete sentence replacement)
        if change_pct > 0.5:
            return "factual_error", {"trigger": context}

        # Check for missing context (significant additions)
        if len(added) > len(removed) * 2:
            return "missing_context", {"trigger": context}

        # Default
        return "other", {"trigger": context}

    def _generate_rule(
        self,
        correction_type: str,
        details: Dict[str, Any],
        context: str,
    ) -> str:
        """Generate a natural-language rule from the correction classification."""
        trigger = details.get("trigger", "this context")

        if correction_type == "tone_shift":
            from_tone = details.get("from", "unknown")
            to_tone = details.get("to", "unknown")
            return f"When analyzing {trigger}, use {to_tone} tone instead of {from_tone}. The analyst corrected the assessment direction."

        if correction_type == "threshold_override":
            orig_vals = details.get("original_values", [])
            corr_vals = details.get("corrected_values", [])
            return f"In {trigger}, the correct values are {', '.join(corr_vals)} (AI used {', '.join(orig_vals)}). Verify metric values against source data."

        if correction_type == "data_caveat":
            caveats = details.get("added_caveats", [])
            return f"When discussing {trigger}, include caveats about data limitations. Analyst added: {', '.join(caveats)}."

        if correction_type == "factual_error":
            return f"AI made a factual error in {trigger}. Cross-check assertions against source data before stating."

        if correction_type == "missing_context":
            return f"AI output for {trigger} was missing important context. Include more background information."

        if correction_type == "methodology_correction":
            return f"The methodology used for {trigger} was incorrect. Review the calculation approach."

        return f"Analyst corrected AI output in {trigger}. Review and adjust approach."

    def extract_patterns(
        self,
        corrections: List[Dict[str, Any]],
        min_count: int = 3,
    ) -> List[LearningRule]:
        """Group recent corrections and extract codification candidates.

        Args:
            corrections: List of correction dicts from company mind.
            min_count: Minimum occurrences to surface as a pattern.

        Returns:
            List of LearningRules from detected patterns.
        """
        # Group by correction type
        type_groups: Dict[str, List[Dict]] = defaultdict(list)

        for corr in corrections:
            meta = corr.get("metadata", {})
            graph_meta = meta.get("_graph", {})
            node_type = graph_meta.get("node_type") or corr.get("node_type", "entry")

            # Skip existing rules
            if node_type == "rule":
                continue

            # Classify based on content
            content = corr.get("content", "")
            original = meta.get("original", "")
            corrected = meta.get("corrected", "")

            if original and corrected:
                rule = self.analyze_correction(original, corrected, content[:100])
                if rule:
                    type_groups[rule.category].append({
                        "correction": corr,
                        "rule": rule,
                    })

        # Extract patterns from groups with enough occurrences
        patterns = []
        for category, items in type_groups.items():
            if len(items) >= min_count:
                # Merge examples from all corrections
                examples = []
                source_ids = []
                for item in items:
                    examples.extend(item["rule"].examples)
                    source_ids.append(item["correction"].get("id", ""))

                pattern_rule = LearningRule(
                    category=category,
                    rule_text=f"Pattern detected: {len(items)} corrections of type '{category}'. "
                              f"This is a systematic issue — consider codifying as a permanent rule.",
                    trigger_condition=f"Detected across {len(items)} corrections",
                    examples=examples[:5],  # cap examples
                    confidence=min(0.95, 0.6 + len(items) * 0.05),
                    source_correction_ids=[sid for sid in source_ids if sid],
                )
                patterns.append(pattern_rule)

        return patterns

    def get_correction_frequency(
        self,
        corrections: List[Dict[str, Any]],
        days: int = 30,
    ) -> Dict[str, Any]:
        """Analyze correction frequency by type and topic.

        Args:
            corrections: List of correction dicts.
            days: Look-back window in days.

        Returns:
            Dict with frequency analysis.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        recent = []
        for c in corrections:
            try:
                ts = datetime.fromisoformat(c.get("timestamp", "").replace("Z", "+00:00"))
                if ts >= cutoff:
                    recent.append(c)
            except (ValueError, TypeError):
                recent.append(c)  # include if can't parse date

        type_counts: Counter = Counter()
        for corr in recent:
            meta = corr.get("metadata", {})
            original = meta.get("original", "")
            corrected = meta.get("corrected", "")
            if original and corrected:
                rule = self.analyze_correction(original, corrected)
                if rule:
                    type_counts[rule.category] += 1

        return {
            "total_corrections": len(recent),
            "period_days": days,
            "by_type": dict(type_counts.most_common()),
            "codification_candidates": [
                t for t, c in type_counts.items() if c >= 3
            ],
        }
