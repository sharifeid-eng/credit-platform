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

# Common separator group: matches formal separators (: - =) and natural language
# connectors (of, was, stood at, at, is, reached, approximately).
_SEP = r"(?:\s*(?:of|was|stood\s+at|at|is|reached|approximately|=|:|-)\s*)"
# Strict separator: only formal separators (: - =). Used for confidence "A".
_SEP_STRICT = r"(?:\s*[:\-=]\s*)"

_METRIC_PATTERNS = [
    # PAR metrics — strict separator first (confidence assigned in extraction loop)
    (r"(?i)PAR\s*30\+?\s*[:\-=]\s*([\d.]+)\s*%", "par_30", "METRIC", "%", "A"),
    (r"(?i)PAR\s*60\+?\s*[:\-=]\s*([\d.]+)\s*%", "par_60", "METRIC", "%", "A"),
    (r"(?i)PAR\s*90\+?\s*[:\-=]\s*([\d.]+)\s*%", "par_90", "METRIC", "%", "A"),
    # PAR metrics — natural language ("PAR30+ of 3.2%", "PAR 30+ stood at 3.2%")
    (r"(?i)PAR\s*30\+?" + _SEP + r"([\d.]+)\s*%", "par_30", "METRIC", "%", "B"),
    (r"(?i)PAR\s*60\+?" + _SEP + r"([\d.]+)\s*%", "par_60", "METRIC", "%", "B"),
    (r"(?i)PAR\s*90\+?" + _SEP + r"([\d.]+)\s*%", "par_90", "METRIC", "%", "B"),
    # Collection rate
    (r"(?i)collection\s*rate\s*[:\-=]\s*([\d.]+)\s*%", "collection_rate", "METRIC", "%", "A"),
    (r"(?i)collection\s*rate" + _SEP + r"([\d.]+)\s*%", "collection_rate", "METRIC", "%", "B"),
    # Default rate
    (r"(?i)default\s*rate\s*[:\-=]\s*([\d.]+)\s*%", "default_rate", "METRIC", "%", "A"),
    (r"(?i)default\s*rate" + _SEP + r"([\d.]+)\s*%", "default_rate", "METRIC", "%", "B"),
    # Delinquency rate
    (r"(?i)delinquency\s*rate\s*[:\-=]\s*([\d.]+)\s*%", "delinquency_rate", "METRIC", "%", "A"),
    (r"(?i)delinquency\s*rate" + _SEP + r"([\d.]+)\s*%", "delinquency_rate", "METRIC", "%", "B"),
    # Recovery rate
    (r"(?i)recovery\s*rate\s*[:\-=]\s*([\d.]+)\s*%", "recovery_rate", "METRIC", "%", "A"),
    (r"(?i)recovery\s*rate" + _SEP + r"([\d.]+)\s*%", "recovery_rate", "METRIC", "%", "B"),
    # Dilution rate
    (r"(?i)dilution\s*(?:rate)?\s*[:\-=]\s*([\d.]+)\s*%", "dilution_rate", "METRIC", "%", "A"),
    (r"(?i)dilution\s*(?:rate)?" + _SEP + r"([\d.]+)\s*%", "dilution_rate", "METRIC", "%", "B"),
    # DSO
    (r"(?i)DSO\s*[:\-=]\s*([\d.]+)\s*(?:days)?", "dso", "METRIC", "days", "A"),
    (r"(?i)DSO" + _SEP + r"([\d.]+)\s*(?:days)?", "dso", "METRIC", "days", "B"),
    # HHI
    (r"(?i)HHI\s*[:\-=]\s*([\d.,]+)", "hhi", "METRIC", "", "A"),
    (r"(?i)HHI" + _SEP + r"([\d.,]+)", "hhi", "METRIC", "", "B"),
    # Advance rate
    (r"(?i)advance\s*rate\s*[:\-=]\s*([\d.]+)\s*%", "advance_rate", "METRIC", "%", "A"),
    (r"(?i)advance\s*rate" + _SEP + r"([\d.]+)\s*%", "advance_rate", "METRIC", "%", "B"),
    # Write-off rate
    (r"(?i)write[\s-]?off\s*rate" + _SEP + r"([\d.]+)\s*%", "writeoff_rate", "METRIC", "%", "B"),
    # Loss rate
    (r"(?i)(?:net\s+)?loss\s*rate" + _SEP + r"([\d.]+)\s*%", "loss_rate", "METRIC", "%", "B"),
    # Margin
    (r"(?i)(?:net|gross|realised|realized)\s*margin" + _SEP + r"([\d.]+)\s*%", "margin", "METRIC", "%", "B"),
]

_COVENANT_PATTERNS = [
    (r"(?i)(?:covenant|limit|trigger).*?(?:PAR|portfolio.at.risk)\s*(?:30)?\s*(?:shall|must|not.exceed|<=?|maximum)\s*([\d.]+)\s*%", "covenant_par_30", "COVENANT", "%", "A"),
    (r"(?i)(?:covenant|limit|trigger).*?collection\s*(?:rate|ratio)\s*(?:shall|must|not.below|>=?|minimum)\s*([\d.]+)\s*%", "covenant_collection_rate", "COVENANT", "%", "A"),
    (r"(?i)(?:PAR|portfolio.at.risk)\s*(?:30)?\s*(?:shall|must|not.exceed|<=?|maximum)\s*([\d.]+)\s*%", "covenant_par_30", "COVENANT", "%", "A"),
    (r"(?i)concentration\s*limit\s*[:\-=]\s*([\d.]+)\s*%", "concentration_limit", "COVENANT", "%", "A"),
    (r"(?i)single\s*(?:borrower|obligor)\s*limit\s*[:\-=]\s*([\d.]+)\s*%", "single_borrower_limit", "COVENANT", "%", "A"),
    (r"(?i)covenant\s+(?:states?\s+)?(?:that\s+)?(?:PAR|collection|concentration|single)\s*.*?(?:not\s+exceed|shall\s+not|must\s+not|<=?|maximum)\s*([\d.]+)\s*%", "covenant_generic", "COVENANT", "%", "A"),
]

_FACILITY_PATTERNS = [
    # Strict separator facility terms
    (r"(?i)facility\s*(?:limit|size|amount)\s*[:\-=]\s*[\$\£\€]?\s*([\d,.]+)\s*(?:M|million|m)?", "facility_limit", "FACILITY_TERM", "currency", "A"),
    (r"(?i)(?:maturity|tenor)\s*[:\-=]\s*(\d+)\s*(?:months?|years?|yrs?)", "maturity", "FACILITY_TERM", "months", "A"),
    (r"(?i)(?:interest|profit)\s*rate\s*[:\-=]\s*([\d.]+)\s*%", "interest_rate", "FACILITY_TERM", "%", "A"),
    # Natural language facility terms ("facility of $2.375 billion", "total commitment of SAR 100M")
    (r"(?i)facility" + _SEP + r"[\$\£\€]?\s*([\d,.]+)\s*(?:billion|million|M|B|m|b)", "facility_limit", "FACILITY_TERM", "currency", "B"),
    (r"(?i)(?:total\s+)?(?:commitment|exposure|limit)" + _SEP + r"[\$\£\€]?\s*([\d,.]+)\s*(?:billion|million|M|B|m|b)", "facility_limit", "FACILITY_TERM", "currency", "B"),
    # Currency amounts in narrative: "$2.375 billion", "SAR 381M", "AED 50.4M", "USD 100 million"
    (r"(?i)(?:USD|SAR|AED|EUR|GBP)\s+([\d,.]+)\s*(?:billion|million|M|B|K|m|b|k)\b", "currency_amount", "FACILITY_TERM", "currency", "B"),
    (r"\$\s*([\d,.]+)\s*(?:billion|million|M|B|K|m|b|k)\b", "currency_amount_usd", "FACILITY_TERM", "currency", "B"),
]

_DATE_PATTERNS = [
    (r"(?i)(?:maturity|expiry)\s*date\s*[:\-=]\s*(\d{1,2}[\s/\-]\w+[\s/\-]\d{4})", "maturity_date", "DATE_EVENT", "date", "A"),
    (r"(?i)(?:closing|effective)\s*date\s*[:\-=]\s*(\d{1,2}[\s/\-]\w+[\s/\-]\d{4})", "closing_date", "DATE_EVENT", "date", "A"),
    # Natural language date patterns ("maturity date of 15 March 2027")
    (r"(?i)(?:maturity|expiry)\s*date" + _SEP + r"(\d{1,2}[\s/\-]\w+[\s/\-]\d{4})", "maturity_date", "DATE_EVENT", "date", "B"),
    (r"(?i)(?:closing|effective|execution)\s*date" + _SEP + r"(\d{1,2}[\s/\-]\w+[\s/\-]\d{4})", "closing_date", "DATE_EVENT", "date", "B"),
    # ISO-style dates in context ("effective date: 2026-03-15")
    (r"(?i)(?:maturity|expiry|closing|effective)\s*date\s*[:\-=]\s*(\d{4}[\-/]\d{1,2}[\-/]\d{1,2})", "date_event", "DATE_EVENT", "date", "A"),
]

_RISK_PATTERNS = [
    (r"(?i)(breach(?:ed|ing)?)\s+(?:of\s+)?(?:covenant|limit|threshold)", "covenant_breach", "RISK_FLAG", "", "A"),
    (r"(?i)(event\s+of\s+default|EOD)", "event_of_default", "RISK_FLAG", "", "A"),
    (r"(?i)(material\s+adverse\s+(?:change|effect))", "mac_event", "RISK_FLAG", "", "A"),
    # Additional risk flags common in investor reports
    (r"(?i)(cross[\s-]?default)", "cross_default", "RISK_FLAG", "", "B"),
    (r"(?i)(acceleration\s+(?:event|notice|clause))", "acceleration_event", "RISK_FLAG", "", "B"),
    (r"(?i)(insolvency|liquidation|winding[\s-]?up)\s+(?:event|proceeding|petition|risk)", "insolvency_risk", "RISK_FLAG", "", "B"),
    (r"(?i)(regulatory\s+(?:action|breach|non[\s-]?compliance|sanction))", "regulatory_risk", "RISK_FLAG", "", "B"),
]

_COUNTERPARTY_PATTERNS = [
    # Investment banks / arrangers / trustees
    (r"(?i)\b(Goldman\s*Sachs)\b", "goldman_sachs", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(Citibank|Citigroup|Citi(?:corp)?)\b", "citi", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(HSBC)\b", "hsbc", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(JP\s*Morgan|JPMorgan)\b", "jpmorgan", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(Morgan\s*Stanley)\b", "morgan_stanley", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(Apollo\s*(?:Global)?(?:\s*Management)?)\b", "apollo", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(Deutsche\s*Bank)\b", "deutsche_bank", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(BNP\s*Paribas)\b", "bnp_paribas", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(Standard\s*Chartered)\b", "standard_chartered", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(Barclays)\b", "barclays", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(UBS)\b", "ubs", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(Credit\s*Suisse)\b", "credit_suisse", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(Nomura)\b", "nomura", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(Atlas\s*(?:Capital|SP))\b", "atlas", "COUNTERPARTY", "", "B"),
    # Audit / advisory firms
    (r"(?i)\b(Deloitte)\b", "deloitte", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(PwC|PricewaterhouseCoopers)\b", "pwc", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(KPMG)\b", "kpmg", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(Ernst\s*&?\s*Young|EY)\b", "ey", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(Grant\s*Thornton)\b", "grant_thornton", "COUNTERPARTY", "", "B"),
    # Rating agencies
    (r"(?i)\b(Moody'?s(?:\s+Investors\s+Service)?)\b", "moodys", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(S&P|Standard\s*(?:&|and)\s*Poor'?s)\b", "sp", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(Fitch\s*(?:Ratings)?)\b", "fitch", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(DBRS(?:\s+Morningstar)?)\b", "dbrs", "COUNTERPARTY", "", "B"),
    # Insurance companies (relevant to Klaim healthcare receivables)
    (r"(?i)\b(Daman\s*(?:Health)?(?:\s*Insurance)?)\b", "daman", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(Oman\s*Insurance)\b", "oman_insurance", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(AXA\s*(?:Insurance|Gulf)?)\b", "axa", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(Allianz)\b", "allianz", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(MetLife)\b", "metlife", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(ADNIC|Abu\s*Dhabi\s*National\s*Insurance)\b", "adnic", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(Sukoon\s*(?:Insurance)?)\b", "sukoon", "COUNTERPARTY", "", "B"),
    # Legal / trustees
    (r"(?i)\b(Clifford\s*Chance)\b", "clifford_chance", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(Allen\s*(?:&|and)\s*Overy)\b", "allen_overy", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(Linklaters)\b", "linklaters", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(White\s*(?:&|and)\s*Case)\b", "white_case", "COUNTERPARTY", "", "B"),
    (r"(?i)\b(Latham\s*(?:&|and)\s*Watkins)\b", "latham_watkins", "COUNTERPARTY", "", "B"),
]

_THRESHOLD_PATTERNS = [
    # "must not exceed 5%", "shall not exceed 10%"
    (r"(?i)(?:must|shall)\s+not\s+exceed\s+([\d.]+)\s*%", "threshold_max_pct", "THRESHOLD", "%", "A"),
    # "shall not be less than 85%", "must not fall below 90%"
    (r"(?i)(?:must|shall)\s+not\s+(?:be\s+less\s+than|fall\s+below)\s+([\d.]+)\s*%", "threshold_min_pct", "THRESHOLD", "%", "A"),
    # "minimum of 90%", "minimum collection rate of 85%"
    (r"(?i)minimum\s+(?:of\s+)?([\d.]+)\s*%", "threshold_min_pct", "THRESHOLD", "%", "B"),
    # "maximum of 5%", "maximum PAR of 7%"
    (r"(?i)maximum\s+(?:of\s+)?([\d.]+)\s*%", "threshold_max_pct", "THRESHOLD", "%", "B"),
    # "not to exceed [amount]" with currency
    (r"(?i)not\s+to\s+exceed\s+(?:USD|SAR|AED|EUR|GBP|\$)\s*([\d,.]+)\s*(?:million|billion|M|B|m|b|K|k)?", "threshold_max_amount", "THRESHOLD", "currency", "A"),
    # "at least [amount]" with currency or percentage
    (r"(?i)at\s+least\s+([\d.]+)\s*%", "threshold_min_pct", "THRESHOLD", "%", "B"),
    (r"(?i)at\s+least\s+(?:USD|SAR|AED|EUR|GBP|\$)\s*([\d,.]+)\s*(?:million|billion|M|B|m|b|K|k)?", "threshold_min_amount", "THRESHOLD", "currency", "B"),
    # "threshold of X%", "limit of X%"
    (r"(?i)(?:threshold|trigger|limit)\s+of\s+([\d.]+)\s*%", "threshold_pct", "THRESHOLD", "%", "B"),
    (r"(?i)(?:threshold|trigger|limit)\s+of\s+(?:USD|SAR|AED|EUR|GBP|\$)\s*([\d,.]+)\s*(?:million|billion|M|B|m|b|K|k)?", "threshold_amount", "THRESHOLD", "currency", "B"),
    # "cap of X%", "floor of X%"
    (r"(?i)(?:cap)\s+of\s+([\d.]+)\s*%", "threshold_max_pct", "THRESHOLD", "%", "B"),
    (r"(?i)(?:floor)\s+of\s+([\d.]+)\s*%", "threshold_min_pct", "THRESHOLD", "%", "B"),
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
    # Track (entity_type, key, value) to skip duplicate extractions from
    # overlapping strict/natural-language patterns on the same span.
    seen: set = set()

    all_patterns = (
        _METRIC_PATTERNS + _COVENANT_PATTERNS +
        _FACILITY_PATTERNS + _DATE_PATTERNS + _RISK_PATTERNS +
        _COUNTERPARTY_PATTERNS + _THRESHOLD_PATTERNS
    )

    for entry in all_patterns:
        pattern, key, entity_type, unit, confidence = entry

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

            # Deduplicate: if a strict pattern (A) already matched this
            # exact (type, key, value), skip the looser B-confidence match.
            dedup_key = (entity_type, key, parsed_value)
            if dedup_key in seen:
                # Keep the higher-confidence (A) version already recorded.
                continue
            seen.add(dedup_key)

            entities.append(ExtractedEntity(
                entity_type=entity_type,
                key=key,
                value=parsed_value,
                context=context,
                confidence=confidence,
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
