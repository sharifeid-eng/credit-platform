"""
Entity Extractor — Extracts structured entities from documents and tape summaries.

Extends the existing regex-based extraction in core/research/extractors.py
with typed entities that feed into the Knowledge Compiler.

Entity types: COVENANT, METRIC, RISK_FLAG, COUNTERPARTY, DATE_EVENT,
THRESHOLD, FACILITY_TERM.

Also extracts from tape summary data (not just documents):
PAR changes, collection rate trends, covenant proximity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExtractedEntity:
    """A structured entity extracted from a document or tape."""

    entity_type: str       # COVENANT | METRIC | RISK_FLAG | COUNTERPARTY | DATE_EVENT | THRESHOLD | FACILITY_TERM
    key: str               # normalized key (e.g., "par_30", "collection_rate")
    value: Any             # the extracted value
    context: str = ""      # surrounding text (~100 chars)
    confidence: str = "B"  # A (high) | B (medium) | C (low)
    source_doc_id: str = ""
    section_heading: str = ""
    unit: str = ""         # %, days, currency, ratio

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "key": self.key,
            "value": self.value,
            "context": self.context,
            "confidence": self.confidence,
            "source_doc_id": self.source_doc_id,
            "section_heading": self.section_heading,
            "unit": self.unit,
        }


# --------------------------------------------------------------------------
# Regex patterns for entity extraction
# --------------------------------------------------------------------------

_METRIC_PATTERNS = [
    (r"(?i)PAR\s*30\+?\s*[:\-=]\s*([\d.]+)\s*%", "par_30", "METRIC", "%"),
    (r"(?i)PAR\s*60\+?\s*[:\-=]\s*([\d.]+)\s*%", "par_60", "METRIC", "%"),
    (r"(?i)PAR\s*90\+?\s*[:\-=]\s*([\d.]+)\s*%", "par_90", "METRIC", "%"),
    (r"(?i)collection\s*rate\s*[:\-=]\s*([\d.]+)\s*%", "collection_rate", "METRIC", "%"),
    (r"(?i)default\s*rate\s*[:\-=]\s*([\d.]+)\s*%", "default_rate", "METRIC", "%"),
    (r"(?i)delinquency\s*rate\s*[:\-=]\s*([\d.]+)\s*%", "delinquency_rate", "METRIC", "%"),
    (r"(?i)recovery\s*rate\s*[:\-=]\s*([\d.]+)\s*%", "recovery_rate", "METRIC", "%"),
    (r"(?i)DSO\s*[:\-=]\s*([\d.]+)\s*(?:days)?", "dso", "METRIC", "days"),
    (r"(?i)HHI\s*[:\-=]\s*([\d.,]+)", "hhi", "METRIC", ""),
    (r"(?i)advance\s*rate\s*[:\-=]\s*([\d.]+)\s*%", "advance_rate", "METRIC", "%"),
    (r"(?i)dilution\s*(?:rate)?\s*[:\-=]\s*([\d.]+)\s*%", "dilution_rate", "METRIC", "%"),
]

_COVENANT_PATTERNS = [
    (r"(?i)(?:covenant|limit|trigger).*?(?:PAR|portfolio.at.risk)\s*(?:30)?\s*(?:shall|must|not.exceed|<=?|maximum)\s*([\d.]+)\s*%", "covenant_par_30", "COVENANT", "%"),
    (r"(?i)(?:covenant|limit|trigger).*?collection\s*(?:rate|ratio)\s*(?:shall|must|not.below|>=?|minimum)\s*([\d.]+)\s*%", "covenant_collection_rate", "COVENANT", "%"),
    (r"(?i)(?:PAR|portfolio.at.risk)\s*(?:30)?\s*(?:shall|must|not.exceed|<=?|maximum)\s*([\d.]+)\s*%", "covenant_par_30", "COVENANT", "%"),
    (r"(?i)concentration\s*limit\s*[:\-=]\s*([\d.]+)\s*%", "concentration_limit", "COVENANT", "%"),
    (r"(?i)single\s*(?:borrower|obligor)\s*limit\s*[:\-=]\s*([\d.]+)\s*%", "single_borrower_limit", "COVENANT", "%"),
    (r"(?i)covenant\s+(?:states?\s+)?(?:that\s+)?(?:PAR|collection|concentration|single)\s*.*?(?:not\s+exceed|shall\s+not|must\s+not|<=?|maximum)\s*([\d.]+)\s*%", "covenant_generic", "COVENANT", "%"),
]

_FACILITY_PATTERNS = [
    (r"(?i)facility\s*(?:limit|size|amount)\s*[:\-=]\s*[\$\£\€]?\s*([\d,.]+)\s*(?:M|million|m)?", "facility_limit", "FACILITY_TERM", "currency"),
    (r"(?i)(?:maturity|tenor)\s*[:\-=]\s*(\d+)\s*(?:months?|years?|yrs?)", "maturity", "FACILITY_TERM", "months"),
    (r"(?i)(?:interest|profit)\s*rate\s*[:\-=]\s*([\d.]+)\s*%", "interest_rate", "FACILITY_TERM", "%"),
]

_DATE_PATTERNS = [
    (r"(?i)(?:maturity|expiry)\s*date\s*[:\-=]\s*(\d{1,2}[\s/\-]\w+[\s/\-]\d{4})", "maturity_date", "DATE_EVENT", "date"),
    (r"(?i)(?:closing|effective)\s*date\s*[:\-=]\s*(\d{1,2}[\s/\-]\w+[\s/\-]\d{4})", "closing_date", "DATE_EVENT", "date"),
]

_RISK_PATTERNS = [
    (r"(?i)(breach(?:ed|ing)?)\s+(?:of\s+)?(?:covenant|limit|threshold)", "covenant_breach", "RISK_FLAG", ""),
    (r"(?i)(event\s+of\s+default|EOD)", "event_of_default", "RISK_FLAG", ""),
    (r"(?i)(material\s+adverse\s+(?:change|effect))", "mac_event", "RISK_FLAG", ""),
]


def extract_entities_from_text(
    text: str,
    source_doc_id: str = "",
    section_heading: str = "",
) -> List[ExtractedEntity]:
    """Extract structured entities from text using regex patterns.

    Args:
        text: The text to extract from.
        source_doc_id: ID of the source document.
        section_heading: Section within the document.

    Returns:
        List of ExtractedEntity objects.
    """
    entities: List[ExtractedEntity] = []

    all_patterns = (
        _METRIC_PATTERNS + _COVENANT_PATTERNS +
        _FACILITY_PATTERNS + _DATE_PATTERNS + _RISK_PATTERNS
    )

    for pattern, key, entity_type, unit in all_patterns:
        for match in re.finditer(pattern, text):
            value = match.group(1)
            # Get surrounding context
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 50)
            context = text[start:end].strip()

            # Try to parse numeric values
            try:
                parsed_value = float(value.replace(",", ""))
            except (ValueError, TypeError):
                parsed_value = value

            entities.append(ExtractedEntity(
                entity_type=entity_type,
                key=key,
                value=parsed_value,
                context=context,
                confidence="B",
                source_doc_id=source_doc_id,
                section_heading=section_heading,
                unit=unit,
            ))

    return entities


def extract_entities_from_metrics(
    metrics: Dict[str, Any],
    source_ref: str = "",
) -> List[ExtractedEntity]:
    """Extract entities from computed tape/portfolio metrics.

    Args:
        metrics: Dict of metric_key → value from summary/PAR/etc endpoints.
        source_ref: Reference to source tape filename.

    Returns:
        List of ExtractedEntity objects with high confidence.
    """
    entities: List[ExtractedEntity] = []

    # Map of metric keys we care about
    metric_map = {
        "collection_rate": ("collection_rate", "METRIC", "%"),
        "denial_rate": ("denial_rate", "METRIC", "%"),
        "pending_rate": ("pending_rate", "METRIC", "%"),
        "avg_discount": ("avg_discount", "METRIC", "%"),
        "total_purchase_value": ("total_purchase_value", "METRIC", "currency"),
        "total_deals": ("total_deals", "METRIC", "count"),
        "active_deals": ("active_deals", "METRIC", "count"),
    }

    # PAR metrics
    for par_key in ("par_30_pct", "par_60_pct", "par_90_pct"):
        metric_map[par_key] = (par_key.replace("_pct", ""), "METRIC", "%")

    # DSO
    for dso_key in ("weighted_dso", "median_dso"):
        metric_map[dso_key] = (dso_key, "METRIC", "days")

    for key, value in metrics.items():
        if key in metric_map and value is not None:
            norm_key, entity_type, unit = metric_map[key]
            try:
                float_val = float(value)
            except (ValueError, TypeError):
                continue

            entities.append(ExtractedEntity(
                entity_type=entity_type,
                key=norm_key,
                value=float_val,
                context=f"Computed from tape: {key}={value}",
                confidence="A",  # computed values are high confidence
                source_doc_id=source_ref,
                unit=unit,
            ))

    return entities
