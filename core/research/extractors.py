"""
Rules-based insight extraction for documents at ingest time.

Extracts structured insights (metrics, covenants, entities, dates, risk flags)
from document text using regex patterns and keyword matching. No AI calls --
this runs at parse time so must be fast and cheap.

Each insight is a dict with:
    category:   metric | covenant | entity | date | risk_flag | facility
    key:        standardised key (e.g. ``par_30_plus``, ``facility_limit``)
    value:      extracted value (string, preserving original formatting)
    context:    surrounding sentence or phrase (~80 chars)
    confidence: A (exact match), B (strong pattern), C (weak/heuristic)
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ── Pattern definitions ──────────────────────────────────────────────────────
#
# Each pattern is a tuple of (compiled regex, category, key, confidence).
# The regex should have a named group ``val`` capturing the metric value
# and optionally ``ctx`` for surrounding context. If ``ctx`` is absent the
# extractor grabs surrounding text automatically.
# ─────────────────────────────────────────────────────────────────────────────

_PCT_NUM = r"[\d]+(?:\.\d+)?%"  # e.g. "3.6%" or "12%"
_MONEY = r"(?:USD|SAR|AED|KWD|EUR|GBP|\$|AED\s?)?\s?[\d,]+(?:\.\d+)?\s?(?:M|m|B|b|K|k|mn|bn)?"

# -- Metric patterns ─────────────────────────────────────────────────────────

_METRIC_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # PAR (Portfolio at Risk)
    (re.compile(
        r"(?:PAR|portfolio\s+at\s+risk)\s*(?:30\+?|30\s*\+)\s*(?:is|was|of|:|\=)?\s*(?P<val>" + _PCT_NUM + r")",
        re.IGNORECASE,
    ), "par_30_plus", "A"),
    (re.compile(
        r"(?:PAR|portfolio\s+at\s+risk)\s*(?:60\+?|60\s*\+)\s*(?:is|was|of|:|\=)?\s*(?P<val>" + _PCT_NUM + r")",
        re.IGNORECASE,
    ), "par_60_plus", "A"),
    (re.compile(
        r"(?:PAR|portfolio\s+at\s+risk)\s*(?:90\+?|90\s*\+)\s*(?:is|was|of|:|\=)?\s*(?P<val>" + _PCT_NUM + r")",
        re.IGNORECASE,
    ), "par_90_plus", "A"),

    # Default / delinquency rates
    (re.compile(
        r"(?:default\s+rate|cumulative\s+default|CDR)\s*(?:is|was|of|:|\=)?\s*(?P<val>" + _PCT_NUM + r")",
        re.IGNORECASE,
    ), "default_rate", "B"),
    (re.compile(
        r"(?:delinquency\s+rate|DPD\s+rate|past\s+due\s+rate)\s*(?:is|was|of|:|\=)?\s*(?P<val>" + _PCT_NUM + r")",
        re.IGNORECASE,
    ), "delinquency_rate", "B"),
    (re.compile(
        r"(?:collection\s+rate|GLR)\s*(?:is|was|of|:|\=)?\s*(?P<val>" + _PCT_NUM + r")",
        re.IGNORECASE,
    ), "collection_rate", "B"),
    (re.compile(
        r"(?:denial\s+rate|dilution\s+rate)\s*(?:is|was|of|:|\=)?\s*(?P<val>" + _PCT_NUM + r")",
        re.IGNORECASE,
    ), "denial_rate", "B"),
    (re.compile(
        r"(?:recovery\s+rate)\s*(?:is|was|of|:|\=)?\s*(?P<val>" + _PCT_NUM + r")",
        re.IGNORECASE,
    ), "recovery_rate", "B"),
    (re.compile(
        r"(?:loss\s+rate|net\s+loss\s+rate|ECL\s+rate)\s*(?:is|was|of|:|\=)?\s*(?P<val>" + _PCT_NUM + r")",
        re.IGNORECASE,
    ), "loss_rate", "B"),
    (re.compile(
        r"(?:net\s+margin|gross\s+margin|realised\s+margin)\s*(?:is|was|of|:|\=)?\s*(?P<val>" + _PCT_NUM + r")",
        re.IGNORECASE,
    ), "margin", "B"),
    (re.compile(
        r"(?:DSO|days\s+sales\s+outstanding)\s*(?:is|was|of|:|\=)?\s*(?P<val>[\d]+(?:\.\d+)?)\s*(?:days)?",
        re.IGNORECASE,
    ), "dso", "B"),
    (re.compile(
        r"(?:HHI|Herfindahl)\s*(?:index)?\s*(?:is|was|of|:|\=)?\s*(?P<val>[\d,]+(?:\.\d+)?)",
        re.IGNORECASE,
    ), "hhi", "B"),

    # Advance rate
    (re.compile(
        r"(?:advance\s+rate)\s*(?:is|was|of|:|\=)?\s*(?P<val>" + _PCT_NUM + r")",
        re.IGNORECASE,
    ), "advance_rate", "B"),
]

# -- Facility patterns ───────────────────────────────────────────────────────

_FACILITY_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(
        r"(?:facility\s+(?:size|limit|amount|commitment))\s*(?:is|was|of|:|\=)?\s*(?P<val>" + _MONEY + r")",
        re.IGNORECASE,
    ), "facility_limit", "A"),
    (re.compile(
        r"(?:tranche\s+(?:size|amount|limit))\s*(?:[\w\s]*?)(?:is|was|of|:|\=)?\s*(?P<val>" + _MONEY + r")",
        re.IGNORECASE,
    ), "tranche_size", "B"),
    (re.compile(
        r"(?:borrowing\s+base)\s*(?:is|was|of|:|\=)?\s*(?P<val>" + _MONEY + r")",
        re.IGNORECASE,
    ), "borrowing_base", "A"),
    (re.compile(
        r"(?:total\s+(?:funded|disbursed|originated))\s*(?:is|was|of|:|\=)?\s*(?P<val>" + _MONEY + r")",
        re.IGNORECASE,
    ), "total_funded", "B"),
]

# -- Covenant patterns ───────────────────────────────────────────────────────

_COVENANT_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(
        r"(?:shall\s+not\s+exceed)\s+(?P<val>" + _PCT_NUM + r"|" + _MONEY + r")",
        re.IGNORECASE,
    ), "covenant_max", "A"),
    (re.compile(
        r"(?:minimum\s+(?:of|at|level)?)\s*(?P<val>" + _PCT_NUM + r"|" + _MONEY + r")",
        re.IGNORECASE,
    ), "covenant_min", "A"),
    (re.compile(
        r"(?:must\s+maintain)\s+(?:a\s+)?(?:minimum\s+)?(?P<val>" + _PCT_NUM + r"|" + _MONEY + r")",
        re.IGNORECASE,
    ), "covenant_maintain", "A"),
    (re.compile(
        r"(?:concentration\s+limit)\s*(?:is|was|of|:|\=)?\s*(?P<val>" + _PCT_NUM + r")",
        re.IGNORECASE,
    ), "concentration_limit", "B"),
    (re.compile(
        r"(?:single\s+(?:borrower|obligor|counterparty)\s+limit)\s*(?:is|was|of|:|\=)?\s*(?P<val>" + _PCT_NUM + r")",
        re.IGNORECASE,
    ), "single_borrower_limit", "A"),
]

# -- Date patterns ───────────────────────────────────────────────────────────

_DATE_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(
        r"(?:maturity\s+date|matures?\s+on)\s*(?:is|:|\=)?\s*(?P<val>\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})",
        re.IGNORECASE,
    ), "maturity_date", "A"),
    (re.compile(
        r"(?:expiry\s+date|expires?\s+on)\s*(?:is|:|\=)?\s*(?P<val>\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})",
        re.IGNORECASE,
    ), "expiry_date", "A"),
    (re.compile(
        r"(?:renewal\s+date|renews?\s+on)\s*(?:is|:|\=)?\s*(?P<val>\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})",
        re.IGNORECASE,
    ), "renewal_date", "B"),
    (re.compile(
        r"(?:closing\s+date|closed\s+on)\s*(?:is|:|\=)?\s*(?P<val>\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})",
        re.IGNORECASE,
    ), "closing_date", "B"),
]

# -- Risk flag patterns ──────────────────────────────────────────────────────

_RISK_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(
        r"(?:breach|breached|breaching)\s+(?:of\s+)?(?:the\s+)?(?P<val>[\w\s]{3,40}?)(?:\s+(?:covenant|limit|threshold|trigger))",
        re.IGNORECASE,
    ), "breach", "A"),
    (re.compile(
        r"(?:trigger\s+(?:level|event|threshold))\s*(?:is|was|of|:|\=)?\s*(?P<val>[^\.\n]{5,60})",
        re.IGNORECASE,
    ), "trigger_event", "B"),
    (re.compile(
        r"(?:warning|caution|concern|deteriorat(?:ing|ed|ion))\s*(?::)?\s*(?P<val>[^\.\n]{5,80})",
        re.IGNORECASE,
    ), "risk_warning", "C"),
    (re.compile(
        r"(?:amortisation\s+(?:event|trigger)|early\s+amortisation)\s*(?P<val>[^\.\n]{0,60})",
        re.IGNORECASE,
    ), "early_amortisation", "A"),
    (re.compile(
        r"(?:event\s+of\s+default)\s*(?P<val>[^\.\n]{0,60})",
        re.IGNORECASE,
    ), "event_of_default", "A"),
]


# ── Document-type specific extraction strategies ─────────────────────────────

# Which pattern groups apply to which document types.
# If a doc_type is not listed, ALL pattern groups are tried.
_DOC_TYPE_STRATEGY: dict[str, list[str]] = {
    "facility_agreement": ["metric", "facility", "covenant", "date", "risk_flag"],
    "investor_report": ["metric", "facility", "risk_flag", "date"],
    "fdd_report": ["metric", "facility"],
    "financial_model": ["metric", "facility", "date"],
    "vintage_cohort": ["metric"],
    "business_plan": ["metric", "date"],
    "loan_tape": ["metric"],
    "credit_memo": ["metric", "facility", "covenant", "risk_flag", "date"],
}

_PATTERN_GROUPS: dict[str, list[tuple[re.Pattern, str, str]]] = {
    "metric": _METRIC_PATTERNS,
    "facility": _FACILITY_PATTERNS,
    "covenant": _COVENANT_PATTERNS,
    "date": _DATE_PATTERNS,
    "risk_flag": _RISK_PATTERNS,
}

# Category labels for each pattern group
_GROUP_CATEGORY: dict[str, str] = {
    "metric": "metric",
    "facility": "facility",
    "covenant": "covenant",
    "date": "date",
    "risk_flag": "risk_flag",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _surrounding_context(text: str, match: re.Match, radius: int = 40) -> str:
    """Extract text surrounding a regex match for context.

    Args:
        text: The full document text.
        match: The regex match object.
        radius: Number of characters of context on each side.

    Returns:
        A string of at most ``2 * radius`` characters centred on the match.
    """
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    ctx = text[start:end].replace("\n", " ").strip()
    # Trim to word boundary
    if start > 0:
        ctx = "..." + ctx
    if end < len(text):
        ctx = ctx + "..."
    return ctx


def _deduplicate(insights: list[dict]) -> list[dict]:
    """Remove duplicate insights with the same key+value pair.

    Keeps the highest-confidence version when duplicates exist.
    """
    seen: dict[tuple[str, str], dict] = {}
    confidence_rank = {"A": 3, "B": 2, "C": 1}

    for ins in insights:
        dup_key = (ins["key"], ins["value"])
        existing = seen.get(dup_key)
        if existing is None:
            seen[dup_key] = ins
        else:
            # Keep higher confidence
            if confidence_rank.get(ins["confidence"], 0) > confidence_rank.get(
                existing["confidence"], 0
            ):
                seen[dup_key] = ins

    return list(seen.values())


# ── Main extraction function ─────────────────────────────────────────────────

def extract_insights(
    doc_text: str,
    doc_type: str,
    filename: str = "",
) -> list[dict]:
    """Extract structured insights from a document at ingest time.

    Uses rules-based extraction (regex patterns and keyword matching) -- no
    AI calls. Different extraction strategies are applied depending on the
    document type.

    Args:
        doc_text: The full text content of the document.
        doc_type: Document type string from the classifier (e.g.
            ``"facility_agreement"``, ``"investor_report"``).
        filename: Original filename (used for logging).

    Returns:
        List of insight dicts, each with keys:
            ``category``, ``key``, ``value``, ``context``, ``confidence``.
    """
    if not doc_text or not doc_text.strip():
        return []

    # Determine which pattern groups to use for this doc type
    strategy = _DOC_TYPE_STRATEGY.get(doc_type)
    if strategy is None:
        # Unknown doc type: try all pattern groups
        strategy = list(_PATTERN_GROUPS.keys())

    insights: list[dict] = []

    for group_name in strategy:
        patterns = _PATTERN_GROUPS.get(group_name, [])
        category = _GROUP_CATEGORY.get(group_name, group_name)

        for pattern, key, confidence in patterns:
            for match in pattern.finditer(doc_text):
                val = match.group("val")
                if not val or not val.strip():
                    continue

                val = val.strip()
                context = _surrounding_context(doc_text, match, radius=40)

                insights.append({
                    "category": category,
                    "key": key,
                    "value": val,
                    "context": context,
                    "confidence": confidence,
                })

    # Entity extraction: simple company/entity name patterns
    insights.extend(_extract_entities(doc_text))

    # De-duplicate
    insights = _deduplicate(insights)

    if insights:
        logger.info(
            "extract_insights: %d insights from %s (%s)",
            len(insights),
            filename or "unknown",
            doc_type,
        )

    return insights


# ── Entity extraction ────────────────────────────────────────────────────────

_ENTITY_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Arranger / underwriter
    (re.compile(
        r"(?:arranged?\s+by|lead\s+arranger|underwriter|bookrunner)\s*(?::)?\s*(?P<val>[A-Z][\w\s&,]+?)(?:\.|,\s+(?:as|in|the)|$)",
        re.IGNORECASE,
    ), "arranger"),
    # Servicer
    (re.compile(
        r"(?:servicer|servicing\s+(?:agent|entity))\s*(?:is|:|\=)?\s*(?P<val>[A-Z][\w\s&,]+?)(?:\.|,\s+(?:as|in|the)|$)",
        re.IGNORECASE,
    ), "servicer"),
    # Trustee
    (re.compile(
        r"(?:trustee|security\s+trustee)\s*(?:is|:|\=)?\s*(?P<val>[A-Z][\w\s&,]+?)(?:\.|,\s+(?:as|in|the)|$)",
        re.IGNORECASE,
    ), "trustee"),
    # Rating
    (re.compile(
        r"(?:rated|rating\s+of)\s*(?P<val>[A-Z]{1,3}[\+\-]?\s*(?:\(sf\))?(?:\s*by\s+[\w&\s]+)?)",
        re.IGNORECASE,
    ), "credit_rating"),
]


def _extract_entities(doc_text: str) -> list[dict]:
    """Extract entity-type insights (arrangers, servicers, trustees, ratings).

    Args:
        doc_text: Full document text.

    Returns:
        List of insight dicts with ``category='entity'``.
    """
    insights: list[dict] = []

    for pattern, key in _ENTITY_PATTERNS:
        for match in pattern.finditer(doc_text):
            val = match.group("val")
            if not val or len(val.strip()) < 3:
                continue
            val = val.strip().rstrip(",").strip()
            # Skip very long matches (likely parsing noise)
            if len(val) > 80:
                continue

            context = _surrounding_context(doc_text, match, radius=40)
            insights.append({
                "category": "entity",
                "key": key,
                "value": val,
                "context": context,
                "confidence": "B",
            })

    return insights
