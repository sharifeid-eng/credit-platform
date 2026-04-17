"""
core/legal_extractor.py
Multi-pass Claude extraction engine for legal documents.

Five-pass architecture:
  Pass 1: Definitions & document structure
  Pass 2: Facility terms + eligibility + advance rates
  Pass 3: Covenants + concentration limits
  Pass 4: Events of default + reporting + waterfall
  Pass 5: Risk assessment (market standard comparison)

Each pass:
  - Prepends definitions glossary as context
  - Sends targeted sections (not full document)
  - Requests JSON matching strict Pydantic schema
  - Requires confidence scores + source citations
  - Instructs Claude to return null when value isn't in text
"""

import os
import json
import time
import logging
from datetime import datetime, timezone

import anthropic

from core.legal_parser import (
    parse_legal_document,
    save_parsed_cache,
    load_extraction_cache,
    save_extraction_cache,
    ParsedDocument,
)
from core.legal_schemas import LegalExtractionResult

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-20250514"  # Fast + accurate for structured extraction
# Use Opus for risk assessment pass where nuance matters
RISK_MODEL = "claude-opus-4-20250514"

_client = None
def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


# ── Main Extraction Function ──────────────────────────────────────────────

def extract_legal_terms(
    file_path: str,
    document_type: str = "credit_agreement",
    refresh: bool = False,
) -> dict:
    """Extract structured legal terms from a PDF facility agreement.

    Returns a dict conforming to LegalExtractionResult schema.
    Results are cached to {file_path}_extracted.json.
    """
    # Check cache
    if not refresh:
        cached = load_extraction_cache(file_path)
        if cached:
            logger.info(f"Returning cached extraction for {file_path}")
            return cached

    # Parse PDF
    parsed = parse_legal_document(file_path)
    save_parsed_cache(file_path, parsed)

    total_input_tokens = 0
    total_output_tokens = 0

    # Pass 1: Definitions & structure
    logger.info("Pass 1/5: Definitions & structure")
    definitions, section_map, t1 = _pass_1_definitions(parsed)
    total_input_tokens += t1[0]
    total_output_tokens += t1[1]

    # Pass 2: Facility terms + eligibility + advance rates
    logger.info("Pass 2/5: Facility terms, eligibility, advance rates")
    facility_terms, eligibility, advance_rates, t2 = _pass_2_facility(parsed, definitions)
    total_input_tokens += t2[0]
    total_output_tokens += t2[1]

    # Pass 3: Covenants + concentration limits
    logger.info("Pass 3/5: Covenants & concentration limits")
    covenants, concentration_limits, t3 = _pass_3_covenants(parsed, definitions)
    total_input_tokens += t3[0]
    total_output_tokens += t3[1]

    # Pass 4: Events of default + reporting + waterfall
    logger.info("Pass 4/5: Events of default, reporting, waterfall")
    eod, reporting, waterfall_normal, waterfall_default, t4 = _pass_4_obligations(parsed, definitions)
    total_input_tokens += t4[0]
    total_output_tokens += t4[1]

    # Pass 5: Risk assessment
    logger.info("Pass 5/5: Risk assessment")
    risk_flags, t5 = _pass_5_risk({
        'facility_terms': facility_terms,
        'eligibility_criteria': eligibility,
        'advance_rates': advance_rates,
        'covenants': covenants,
        'concentration_limits': concentration_limits,
        'events_of_default': eod,
    }, document_type)
    total_input_tokens += t5[0]
    total_output_tokens += t5[1]

    # Compute cost estimate (Sonnet pricing: $3/M input, $15/M output; Opus for pass 5)
    sonnet_input = total_input_tokens - t5[0]
    sonnet_output = total_output_tokens - t5[1]
    cost = (sonnet_input * 3 + sonnet_output * 15) / 1_000_000
    cost += (t5[0] * 15 + t5[1] * 75) / 1_000_000  # Opus for risk pass

    # Compute overall confidence
    all_confidences = []
    if facility_terms.get('confidence'):
        all_confidences.append(facility_terms['confidence'])
    for item_list in [eligibility, advance_rates, covenants, concentration_limits, eod, reporting]:
        for item in item_list:
            if isinstance(item, dict) and 'confidence' in item:
                all_confidences.append(item['confidence'])
    overall_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

    result = {
        'facility_terms': facility_terms,
        'eligibility_criteria': eligibility,
        'advance_rates': advance_rates,
        'concentration_limits': concentration_limits,
        'covenants': covenants,
        'events_of_default': eod,
        'reporting_requirements': reporting,
        'waterfall_normal': waterfall_normal,
        'waterfall_default': waterfall_default,
        'risk_flags': risk_flags,
        'definitions': definitions,
        'section_map': section_map,
        'overall_confidence': round(overall_confidence, 3),
        'extraction_model': MODEL,
        'extraction_cost_usd': round(cost, 4),
        'extracted_at': datetime.now(timezone.utc).isoformat(),
        'document_type': document_type,
        'filename': os.path.basename(file_path),
        'page_count': parsed.page_count,
    }

    # Cache result
    save_extraction_cache(file_path, result)
    logger.info(f"Extraction complete. Cost: ${cost:.4f}, Confidence: {overall_confidence:.1%}")
    return result


# ── Pass 1: Definitions & Structure ───────────────────────────────────────

def _pass_1_definitions(parsed: ParsedDocument) -> tuple[dict, dict, tuple[int, int]]:
    """Extract defined terms glossary and document structure map."""

    # Use definitions section if found, otherwise first 20% of document
    context = parsed.definitions_text
    if not context or len(context) < 200:
        # Fallback: first 20% of document
        cutoff = len(parsed.markdown) // 5
        context = parsed.markdown[:cutoff]

    prompt = """Analyze this legal document section and extract:

1. **Defined Terms**: Every term that is formally defined (appears in quotes or bold with "means" or "shall mean"). Return as a JSON object mapping term → definition.

2. **Document Structure**: The high-level section/article map. Return as a JSON object mapping section number/letter → section title.

Return ONLY valid JSON in this exact format:
```json
{
  "definitions": {
    "Eligible Receivable": "means a Receivable that satisfies all of the Eligibility Criteria...",
    "Advance Rate": "means, with respect to...",
    ...
  },
  "section_map": {
    "Article I": "Definitions and Interpretation",
    "Article II": "The Facility",
    "Schedule A": "Eligibility Criteria",
    ...
  }
}
```

Rules:
- Include ALL defined terms, even common ones
- Definitions should be concise (1-2 sentences max)
- If a term is not formally defined, do NOT include it
- Section map should cover all top-level articles/schedules/exhibits"""

    response, tokens = _call_claude(context, prompt)
    data = _parse_json_response(response)

    definitions = data.get('definitions', {})
    section_map = data.get('section_map', {})
    return definitions, section_map, tokens


# ── Pass 2: Facility Terms + Eligibility + Advance Rates ──────────────────

def _pass_2_facility(parsed: ParsedDocument, definitions: dict) -> tuple[dict, list, list, tuple[int, int]]:
    """Extract facility terms, eligibility criteria, and advance rates."""

    # Find relevant sections
    relevant_keys = []
    for key in parsed.sections:
        if any(kw in key for kw in ['FACILIT', 'ELIGIB', 'ADVANCE', 'BORROW', 'COMMITMENT',
                                     'SCHEDULE_A', 'CRITERIA', 'PURCHASE', 'RECEIVABLE']):
            relevant_keys.append(key)

    context_parts = [_definitions_context(definitions)]
    for key in relevant_keys:
        context_parts.append(f"--- SECTION: {key} ---\n{parsed.sections[key][:5000]}")

    # If no relevant sections found, use broader content
    if not relevant_keys:
        context_parts.append(parsed.markdown[:15000])

    # Add any extracted tables that look like rate schedules
    for tbl in parsed.tables:
        if any(kw in ' '.join(tbl.headers).lower() for kw in ['rate', 'advance', 'eligible', 'criteria']):
            context_parts.append(f"\n--- TABLE (page {tbl.page}) ---\nHeaders: {tbl.headers}\nRows: {json.dumps(tbl.rows[:20])}")

    context = '\n\n'.join(context_parts)

    prompt = """Extract facility terms, eligibility criteria, and advance rates from this credit/facility agreement.

Return ONLY valid JSON in this exact format:
```json
{
  "facility_terms": {
    "facility_type": "revolving",
    "facility_limit": 50000000,
    "currency": "AED",
    "maturity_date": "2027-06-30",
    "commitment_period_end": "2026-12-31",
    "effective_date": "2025-06-01",
    "parties": ["Klaim Technology FZE", "ACP Fund Ltd"],
    "governing_law": "DIFC Law",
    "interest_rate_description": "SOFR + 3.50% margin",
    "section_ref": "Article II",
    "confidence": 0.95
  },
  "eligibility_criteria": [
    {
      "name": "Maximum Aging",
      "description": "Receivable must not be older than 365 days from invoice date",
      "parameter": "ineligibility_age_days",
      "value": 365,
      "section_ref": "Schedule A, Section 2(a)",
      "page": 45,
      "confidence": 0.95
    },
    {
      "name": "Minimum Amount",
      "description": "Receivable face value must exceed AED 1,000",
      "parameter": "min_receivable_amount",
      "value": 1000,
      "section_ref": "Schedule A, Section 2(c)",
      "page": 45,
      "confidence": 0.90
    }
  ],
  "advance_rates": [
    {
      "category": "default",
      "rate": 0.90,
      "condition": "Default advance rate for all eligible receivables",
      "section_ref": "Article II, Section 2.03",
      "confidence": 0.95
    },
    {
      "category": "UAE",
      "rate": 0.90,
      "condition": "UAE-domiciled payer receivables",
      "section_ref": "Schedule B",
      "confidence": 0.90
    },
    {
      "category": "Non-UAE",
      "rate": 0.85,
      "condition": "Non-UAE payer receivables",
      "section_ref": "Schedule B",
      "confidence": 0.85
    }
  ]
}
```

IMPORTANT rules:
- `parameter` must be one of: ineligibility_age_days, min_receivable_amount, max_receivable_amount, cross_default_threshold_pct, excluded_debtor_types, excluded_receivable_types
- `category` for advance rates must be one of: default, UAE, Non-UAE, by_product, by_rating
- Confidence: 1.0 = exact number stated, 0.8 = inferred from context, 0.5 = uncertain
- If a value is NOT in the document, set it to null — do NOT guess
- Include ALL eligibility criteria you can find, even if they seem minor
- Include section references and page numbers where possible"""

    response, tokens = _call_claude(context, prompt)
    data = _parse_json_response(response)

    return (
        data.get('facility_terms', {}),
        data.get('eligibility_criteria', []),
        data.get('advance_rates', []),
        tokens,
    )


# ── Pass 3: Covenants + Concentration Limits ─────────────────────────────

def _pass_3_covenants(parsed: ParsedDocument, definitions: dict) -> tuple[list, list, tuple[int, int]]:
    """Extract financial covenants and concentration limits."""

    relevant_keys = []
    for key in parsed.sections:
        if any(kw in key for kw in ['COVENANT', 'CONCENTRAT', 'LIMIT', 'FINANCIAL',
                                     'COMPLIANCE', 'RESTRICT', 'THRESHOLD', 'TRIGGER']):
            relevant_keys.append(key)

    context_parts = [_definitions_context(definitions)]
    for key in relevant_keys:
        context_parts.append(f"--- SECTION: {key} ---\n{parsed.sections[key][:5000]}")

    if not relevant_keys:
        # Search full doc for covenant-related content
        for key, content in parsed.sections.items():
            if any(kw in content.lower() for kw in ['covenant', 'concentration', 'par 30', 'par 60',
                                                     'collection ratio', 'loan to value']):
                context_parts.append(f"--- SECTION: {key} ---\n{content[:5000]}")

    for tbl in parsed.tables:
        if any(kw in ' '.join(tbl.headers).lower() for kw in ['covenant', 'limit', 'threshold', 'concentration']):
            context_parts.append(f"\n--- TABLE (page {tbl.page}) ---\nHeaders: {tbl.headers}\nRows: {json.dumps(tbl.rows[:20])}")

    context = '\n\n'.join(context_parts)

    prompt = """Extract financial covenants and concentration limits from this credit agreement.

Return ONLY valid JSON:
```json
{
  "covenants": [
    {
      "name": "PAR 30 Ratio",
      "covenant_type": "maintenance",
      "metric": "par30_limit",
      "threshold": 0.10,
      "direction": "<=",
      "test_frequency": "monthly",
      "cure_period_days": 30,
      "equity_cure_allowed": false,
      "section_ref": "Article VI, Section 6.01(a)",
      "confidence": 0.95
    },
    {
      "name": "Collection Ratio (3M Rolling)",
      "covenant_type": "maintenance",
      "metric": "collection_ratio_limit",
      "threshold": 0.33,
      "direction": ">=",
      "test_frequency": "monthly",
      "cure_period_days": null,
      "equity_cure_allowed": false,
      "section_ref": "Article VI, Section 6.01(c)",
      "confidence": 0.90
    }
  ],
  "concentration_limits": [
    {
      "name": "Single Payer",
      "limit_type": "single_payer",
      "threshold_pct": 0.10,
      "tiered": null,
      "n_value": null,
      "section_ref": "Article V, Section 5.03",
      "confidence": 0.90
    },
    {
      "name": "Single Borrower",
      "limit_type": "single_borrower",
      "threshold_pct": 0.20,
      "tiered": [
        {"facility_min": 0, "facility_max": 10000000, "limit_pct": 0.20},
        {"facility_min": 10000000, "facility_max": 20000000, "limit_pct": 0.15},
        {"facility_min": 20000000, "facility_max": null, "limit_pct": 0.10}
      ],
      "n_value": null,
      "section_ref": "Article V, Section 5.03(a)",
      "confidence": 0.85
    }
  ]
}
```

IMPORTANT rules:
- `metric` for covenants must map to facility_params keys: par30_limit, par60_limit, collection_ratio_limit, paid_vs_due_limit, cash_ratio_limit, wal_threshold_days, ltv_limit
- `limit_type` must be one of: single_borrower, single_payer, single_customer, single_receivable, top_n, geographic, sector, extended_age
- `direction` is from the borrower's compliance perspective: "<=" means value must stay at or below threshold
- Include tiered limits when thresholds vary by facility size
- If a value is NOT in the document, do NOT guess — omit the entry entirely
- Confidence: 1.0 = exact number stated, 0.8 = inferred, 0.5 = uncertain"""

    response, tokens = _call_claude(context, prompt)
    data = _parse_json_response(response)

    return (
        data.get('covenants', []),
        data.get('concentration_limits', []),
        tokens,
    )


# ── Pass 4: Events of Default + Reporting + Waterfall ─────────────────────

def _pass_4_obligations(parsed: ParsedDocument, definitions: dict) -> tuple[list, list, list, list, tuple[int, int]]:
    """Extract events of default, reporting requirements, and payment waterfall."""

    relevant_keys = []
    for key in parsed.sections:
        if any(kw in key for kw in ['DEFAULT', 'EVENT', 'REPORT', 'WATERFALL', 'PAYMENT',
                                     'PRIORITY', 'APPLICATION', 'REMEDIES', 'NOTICE',
                                     'INFORMATION', 'OBLIGATION']):
            relevant_keys.append(key)

    context_parts = [_definitions_context(definitions)]
    for key in relevant_keys:
        context_parts.append(f"--- SECTION: {key} ---\n{parsed.sections[key][:5000]}")

    if not relevant_keys:
        context_parts.append(parsed.markdown[-15000:])  # Last portion often has defaults

    context = '\n\n'.join(context_parts)

    prompt = """Extract events of default, reporting requirements, and payment waterfall from this credit agreement.

Return ONLY valid JSON:
```json
{
  "events_of_default": [
    {
      "trigger": "Failure to pay principal or interest within 5 business days of due date",
      "section_ref": "Article VII, Section 7.01(a)",
      "cure_period_days": 5,
      "severity": "payment",
      "confidence": 0.95
    },
    {
      "trigger": "Breach of any financial covenant that is not cured within 30 days of notice",
      "section_ref": "Article VII, Section 7.01(c)",
      "cure_period_days": 30,
      "severity": "covenant",
      "confidence": 0.90
    }
  ],
  "reporting_requirements": [
    {
      "name": "Borrowing Base Certificate",
      "frequency": "monthly",
      "due_days_after_period": 15,
      "description": "Certified BBC showing eligible receivables, advance rate, and borrowing base calculation",
      "confidence": 0.90
    },
    {
      "name": "Annual Audited Financial Statements",
      "frequency": "annual",
      "due_days_after_period": 120,
      "description": "Audited financial statements for the fiscal year",
      "confidence": 0.85
    }
  ],
  "waterfall_normal": [
    {"priority": 1, "description": "Agent fees and expenses", "applies_in": "both"},
    {"priority": 2, "description": "Accrued interest on the loans", "applies_in": "normal"},
    {"priority": 3, "description": "Principal repayment of loans", "applies_in": "normal"},
    {"priority": 4, "description": "Residual to the Borrower", "applies_in": "normal"}
  ],
  "waterfall_default": [
    {"priority": 1, "description": "Agent fees and expenses", "applies_in": "both"},
    {"priority": 2, "description": "All outstanding principal and accrued interest", "applies_in": "default"},
    {"priority": 3, "description": "Breakage costs and make-whole amounts", "applies_in": "default"}
  ]
}
```

IMPORTANT rules:
- `severity` must be one of: payment, covenant, cross_default, mac (material adverse change), operational
- `frequency` must be one of: monthly, quarterly, annual, per_draw, ad_hoc
- Include ALL events of default, even cross-default and MAC clauses
- Waterfall must distinguish normal vs default application of proceeds
- If waterfall is not detailed in the document, return empty arrays
- Do NOT guess — omit entries you cannot find in the text"""

    response, tokens = _call_claude(context, prompt)
    data = _parse_json_response(response)

    return (
        data.get('events_of_default', []),
        data.get('reporting_requirements', []),
        data.get('waterfall_normal', []),
        data.get('waterfall_default', []),
        tokens,
    )


# ── Pass 5: Risk Assessment ──────────────────────────────────────────────

def _pass_5_risk(extracted_terms: dict, document_type: str) -> tuple[list, tuple[int, int]]:
    """AI risk assessment comparing extracted terms against market standards."""

    context = f"""Document type: {document_type}

Extracted terms from facility agreement:

FACILITY: {json.dumps(extracted_terms.get('facility_terms', {}), indent=2, default=str)}

ELIGIBILITY: {json.dumps(extracted_terms.get('eligibility_criteria', []), indent=2, default=str)}

ADVANCE RATES: {json.dumps(extracted_terms.get('advance_rates', []), indent=2, default=str)}

COVENANTS: {json.dumps(extracted_terms.get('covenants', []), indent=2, default=str)}

CONCENTRATION LIMITS: {json.dumps(extracted_terms.get('concentration_limits', []), indent=2, default=str)}

EVENTS OF DEFAULT: {json.dumps(extracted_terms.get('events_of_default', []), indent=2, default=str)}"""

    prompt = """You are a private credit legal analyst. Review the extracted terms from this facility agreement and identify risk flags.

Compare against market standards for asset-backed lending / receivables purchase facilities:

**Market standard benchmarks:**
- Advance rates: typically 80-90% for investment-grade receivables, 70-85% for sub-investment-grade
- Single borrower concentration: typically 5-15% depending on facility size
- PAR thresholds: PAR30 ≤7-10%, PAR60/90 ≤3-5%
- Collection ratio: typically ≥25-35% rolling 3-month
- Aging cutoff: typically 90-180 days for consumer, 180-365 for insurance
- Cure periods: typically 15-30 days for covenant breaches, 5 days for payment defaults
- Dilution reserve: typically 1-5% of eligible pool

Identify:
1. **Missing provisions** that should be present (e.g., no dilution reserve, no MAC clause)
2. **Below-market protections** (e.g., thresholds more lenient than typical)
3. **Unusual terms** (e.g., atypical structure, uncommon restrictions)
4. **Concentration risk** (e.g., high single-borrower limits)

Return ONLY valid JSON:
```json
{
  "risk_flags": [
    {
      "category": "missing_provision",
      "description": "No dilution reserve provision found. Market standard is 1-5% reserve against non-credit losses.",
      "severity": "high",
      "recommendation": "Add a dilution reserve of at least 2% of eligible receivables"
    },
    {
      "category": "below_market",
      "description": "PAR30 threshold at 10% is above market standard of 7%. This provides less early warning.",
      "severity": "medium",
      "recommendation": "Consider tightening to 7% or adding a step-down trigger at 7%"
    }
  ]
}
```

Rules:
- `category` must be one of: missing_provision, below_market, unusual_term, deviation
- `severity` must be one of: high, medium, low
- Only flag genuine concerns — do not manufacture risks
- If the facility is well-structured with no notable issues, return an empty array
- Be specific with market comparisons (cite typical ranges)"""

    response, tokens = _call_claude(context, prompt, model=RISK_MODEL)
    data = _parse_json_response(response)

    return data.get('risk_flags', []), tokens


# ── Helpers ───────────────────────────────────────────────────────────────

def _definitions_context(definitions: dict) -> str:
    """Build definitions context prefix for extraction passes."""
    if not definitions:
        return ""
    lines = ["--- DEFINED TERMS (from the agreement) ---"]
    for term, defn in sorted(definitions.items()):
        lines.append(f'"{term}" means {defn}')
    return '\n'.join(lines[:100])  # Cap at 100 terms


def _call_claude(context: str, prompt: str, model: str = None) -> tuple[str, tuple[int, int]]:
    """Call Claude API via the central client with retry + caching.

    The optional `model` arg is interpreted as a tier hint:
      - `RISK_MODEL` (Opus) → tier="judgment"
      - anything else       → tier="research" (Sonnet)
    """
    # Truncate context if too long (keep under 100K tokens ~= 400K chars)
    max_chars = 400_000
    if len(context) > max_chars:
        context = context[:max_chars] + "\n\n[... truncated for length ...]"

    # Map legacy model constants to tiers — preserves Sonnet/Opus split
    tier = "judgment" if (model == RISK_MODEL) else "research"

    from core.ai_client import complete as _ai_complete
    response = _ai_complete(
        tier=tier,
        max_tokens=4096,
        system=(
            "You are a legal document analysis expert specializing in private "
            "credit and asset-backed lending facilities. Extract information "
            "precisely from the provided document text. Return only valid "
            "JSON — no markdown fences, no explanatory text outside the JSON."
        ),
        messages=[{
            "role": "user",
            "content": f"{context}\n\n---\n\n{prompt}",
        }],
        log_prefix="legal_extract",
    )

    text = response.content[0].text if response.content else "{}"
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens

    return text, (input_tokens, output_tokens)


def _parse_json_response(text: str) -> dict:
    """Parse JSON from Claude response, handling markdown fences."""
    # Strip markdown code fences if present
    text = text.strip()
    if text.startswith('```'):
        # Remove first line (```json or ```)
        lines = text.split('\n')
        text = '\n'.join(lines[1:])
    if text.endswith('```'):
        text = text[:-3].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON response: {e}")
        # Try to find JSON object in the text
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        return {}
