"""
core/legal_compliance.py
Compliance comparison engine: extracted legal terms vs live portfolio metrics.

Bridges legal document extraction with portfolio analytics by:
1. Comparing covenant thresholds (document vs hardcoded vs live value)
2. Comparing advance rates and eligibility criteria
3. Computing breach distance (% headroom to threshold)
4. Generating compliance summary for executive summary integration
"""

import os
import json
import logging

from core.legal_parser import get_legal_dir, load_extraction_cache
from core.legal_schemas import extraction_to_facility_params

logger = logging.getLogger(__name__)


# ── 3-Tier Facility Params ────────────────────────────────────────────────

def load_legal_facility_params(company: str, product: str) -> dict:
    """Load facility params from the latest extracted legal document.

    Returns dict compatible with facility_params.json structure,
    or empty dict if no documents extracted.
    """
    extraction = load_latest_extraction(company, product)
    if not extraction:
        return {}

    from core.legal_schemas import LegalExtractionResult
    try:
        result = LegalExtractionResult(**extraction)
        return extraction_to_facility_params(result)
    except Exception as e:
        logger.warning(f"Failed to convert extraction to facility params: {e}")
        # Fallback: try direct conversion from dict
        return _extraction_dict_to_params(extraction)


def load_latest_extraction(company: str, product: str) -> dict | None:
    """Load and merge all extraction results for a company/product.

    Multi-document facilities (MMA + MRPA + Fee Letter + Qard) each contribute
    different fields. This merges them: lists are concatenated, dicts are merged
    (later docs override on conflict), and the primary credit_agreement provides
    the base facility_terms.
    """
    legal_dir = get_legal_dir(company, product)
    if not os.path.exists(legal_dir):
        return None

    extractions = []
    for fname in sorted(os.listdir(legal_dir)):
        if not fname.endswith('_extracted.json'):
            continue
        fpath = os.path.join(legal_dir, fname)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            extractions.append(data)
        except (json.JSONDecodeError, IOError):
            continue

    if not extractions:
        return None

    if len(extractions) == 1:
        return extractions[0]

    # Merge: start with the primary credit_agreement, layer others on top
    primary = next((e for e in extractions if e.get('document_type') == 'credit_agreement'), extractions[0])
    merged = dict(primary)  # shallow copy

    # List fields: concatenate from all documents (dedup by name, prefer later extraction)
    list_fields = [
        'covenants', 'eligibility_criteria', 'advance_rates', 'concentration_limits',
        'events_of_default', 'reporting_requirements', 'risk_flags',
        'waterfall_normal', 'waterfall_default',
    ]
    for field in list_fields:
        # Build a map of name -> (item, extracted_at) across all documents,
        # preferring the entry from the document with the later extracted_at timestamp.
        named_items: dict[str, tuple[dict, str]] = {}
        unnamed_items: list = []
        for ext in extractions:
            ext_ts = ext.get('extracted_at', '')
            for item in ext.get(field, []):
                if isinstance(item, dict):
                    item_name = item.get('name', '')
                    if item_name:
                        existing_ts = named_items.get(item_name, (None, ''))[1]
                        if item_name not in named_items or ext_ts > existing_ts:
                            named_items[item_name] = (item, ext_ts)
                    else:
                        unnamed_items.append(item)
                else:
                    unnamed_items.append(item)
        combined = [entry[0] for entry in named_items.values()] + unnamed_items
        merged[field] = combined

    # Dict fields: merge (primary wins on conflict)
    dict_fields = ['facility_terms', 'definitions', 'section_map']
    for field in dict_fields:
        base = dict(primary.get(field, {}))
        for ext in extractions:
            if ext is primary:
                continue
            for k, v in ext.get(field, {}).items():
                if k not in base or not base[k]:
                    base[k] = v
        merged[field] = base

    # Track all source documents
    merged['source_documents'] = [
        {'filename': e.get('filename', ''), 'document_type': e.get('document_type', ''),
         'extracted_at': e.get('extracted_at', ''), 'confidence': e.get('overall_confidence', 0)}
        for e in extractions
    ]

    return merged


def _extraction_dict_to_params(extraction: dict) -> dict:
    """Fallback: convert extraction dict directly to facility params."""
    params = {}
    sources = {}

    # Facility limit
    ft = extraction.get('facility_terms', {})
    if ft.get('facility_limit'):
        params['facility_limit'] = ft['facility_limit']
        sources['facility_limit'] = 'document'

    # Advance rates
    for ar in extraction.get('advance_rates', []):
        cat = ar.get('category', '')
        rate = ar.get('rate')
        if rate is None:
            continue
        if cat == 'default':
            params['advance_rate'] = rate
            sources['advance_rate'] = 'document'
        elif cat in ('UAE', 'Non-UAE'):
            params.setdefault('advance_rates_by_region', {})
            params['advance_rates_by_region'][cat] = rate
            sources['advance_rates_by_region'] = 'document'

    # Eligibility
    for ec in extraction.get('eligibility_criteria', []):
        param = ec.get('parameter')
        val = ec.get('value')
        if param and val is not None:
            try:
                params[param] = float(val) if isinstance(val, (int, float, str)) else val
                sources[param] = 'document'
            except (ValueError, TypeError):
                pass

    # Concentration limits
    limit_key_map = {
        'single_borrower': 'single_borrower_limit',
        'single_payer': 'single_payer_limit',
        'single_customer': 'single_customer_limit',
        'single_receivable': 'single_receivable_limit',
        'top_n': 'top10_limit',
        'extended_age': 'extended_age_limit',
    }
    for cl in extraction.get('concentration_limits', []):
        lt = cl.get('limit_type', '')
        key = limit_key_map.get(lt)
        if key:
            params[key] = cl.get('threshold_pct')
            sources[key] = 'document'

    # Covenants
    for cov in extraction.get('covenants', []):
        metric = cov.get('metric')
        threshold = cov.get('threshold')
        if metric and threshold is not None:
            params[metric] = threshold
            sources[metric] = 'document'

    params['_sources'] = sources
    return params


def merge_facility_params(company: str, product: str, manual_params: dict) -> dict:
    """Merge facility params with 3-tier priority:
    1. Manual overrides (highest priority)
    2. Document-extracted values (baseline)
    3. Hardcoded defaults (in compute functions — not merged here)

    Returns merged params dict with _sources tracking.
    """
    # Tier 1: Document-extracted baseline
    doc_params = load_legal_facility_params(company, product)
    sources = doc_params.pop('_sources', {})

    # Tier 2: Manual overrides take precedence
    merged = {**doc_params}
    for k, v in manual_params.items():
        if k.startswith('_'):
            continue
        if v is not None and v != '':
            merged[k] = v
            sources[k] = 'manual'

    merged['_sources'] = sources
    return merged


# ── Compliance Comparison ─────────────────────────────────────────────────

def build_compliance_comparison(
    extraction: dict,
    live_covenants: list[dict] | None = None,
    live_bb: dict | None = None,
    live_concentration: dict | None = None,
) -> dict:
    """Compare extracted document terms against live portfolio metrics.

    Args:
        extraction: Full extraction result dict
        live_covenants: Output of compute_klaim_covenants() or similar
        live_bb: Output of compute_klaim_borrowing_base() or similar
        live_concentration: Output of compute_klaim_concentration_limits() or similar

    Returns structured comparison with breach distances and discrepancies.
    """
    covenant_comparison = _compare_covenants(extraction, live_covenants)
    advance_rate_comparison = _compare_advance_rates(extraction, live_bb)
    concentration_comparison = _compare_concentration(extraction, live_concentration)
    eligibility_comparison = _compare_eligibility(extraction, live_bb)

    # Summary
    all_items = covenant_comparison + concentration_comparison
    compliant_count = sum(1 for x in all_items if x.get('compliant', True))
    breach_count = sum(1 for x in all_items if not x.get('compliant', True))
    near_breach = sum(1 for x in all_items
                      if x.get('compliant', True)
                      and x.get('breach_distance_pct') is not None
                      and x['breach_distance_pct'] < 20)
    discrepancies = sum(1 for x in all_items if x.get('discrepancy', False))

    return {
        'covenant_comparison': covenant_comparison,
        'advance_rate_comparison': advance_rate_comparison,
        'concentration_comparison': concentration_comparison,
        'eligibility_comparison': eligibility_comparison,
        'summary': {
            'total_terms_compared': len(all_items),
            'compliant': compliant_count,
            'breaches': breach_count,
            'near_breaches': near_breach,
            'discrepancies': discrepancies,
        },
        'document_info': {
            'filename': extraction.get('filename', ''),
            'extracted_at': extraction.get('extracted_at', ''),
            'overall_confidence': extraction.get('overall_confidence', 0),
        },
    }


def _compare_covenants(extraction: dict, live_covenants: list[dict] | None) -> list[dict]:
    """Compare extracted covenants against live portfolio covenant test results."""
    if not live_covenants:
        return []

    results = []
    for doc_cov in extraction.get('covenants', []):
        doc_metric = doc_cov.get('metric', '')
        doc_threshold = doc_cov.get('threshold')
        doc_direction = doc_cov.get('direction', '<=')
        doc_name = doc_cov.get('name', '')

        # Find matching live covenant
        live_match = None
        for lc in live_covenants:
            live_name = lc.get('name', '').lower()
            if doc_metric and doc_metric.replace('_limit', '') in live_name.lower().replace(' ', '_'):
                live_match = lc
                break
            # Fuzzy match on name
            if doc_name.lower()[:10] in live_name.lower() or live_name.lower()[:10] in doc_name.lower():
                live_match = lc
                break

        if not live_match:
            results.append({
                'name': doc_name,
                'doc_threshold': doc_threshold,
                'doc_direction': doc_direction,
                'live_value': None,
                'compliant': None,
                'breach_distance_pct': None,
                'hardcoded_threshold': None,
                'discrepancy': False,
                'source_confidence': doc_cov.get('confidence', 0),
                'matched': False,
            })
            continue

        live_value = live_match.get('current')
        live_threshold = live_match.get('threshold')
        live_compliant = live_match.get('compliant', True)

        # Compute breach distance
        breach_dist = None
        if doc_threshold and live_value is not None:
            if doc_direction in ('<=', '<'):
                breach_dist = round(((doc_threshold - live_value) / doc_threshold) * 100, 1) if doc_threshold != 0 else None
            elif doc_direction in ('>=', '>'):
                breach_dist = round(((live_value - doc_threshold) / doc_threshold) * 100, 1) if doc_threshold != 0 else None

        # Check discrepancy between document and hardcoded
        discrepancy = False
        if doc_threshold is not None and live_threshold is not None:
            discrepancy = abs(doc_threshold - live_threshold) > 0.001

        results.append({
            'name': doc_name,
            'doc_threshold': doc_threshold,
            'doc_direction': doc_direction,
            'live_value': live_value,
            'compliant': live_compliant if breach_dist is None else (breach_dist >= 0 if breach_dist is not None else None),
            'breach_distance_pct': breach_dist,
            'hardcoded_threshold': live_threshold,
            'discrepancy': discrepancy,
            'source_confidence': doc_cov.get('confidence', 0),
            'matched': True,
        })

    return results


def _compare_advance_rates(extraction: dict, live_bb: dict | None) -> list[dict]:
    """Compare extracted advance rates against live borrowing base computation."""
    results = []
    if not live_bb:
        return results

    # Try to find advance rate info in BB output
    live_advance_rate = None
    for step in live_bb.get('waterfall', []):
        label = step.get('label', '').lower()
        if 'advance rate' in label:
            # Extract rate from label like "Advance Rate Discount (90%)"
            import re
            m = re.search(r'(\d+(?:\.\d+)?)\s*%', label)
            if m:
                live_advance_rate = float(m.group(1)) / 100

    for doc_ar in extraction.get('advance_rates', []):
        result = {
            'category': doc_ar.get('category', ''),
            'doc_rate': doc_ar.get('rate'),
            'live_rate': live_advance_rate,
            'matches': None,
            'confidence': doc_ar.get('confidence', 0),
        }
        if result['doc_rate'] is not None and live_advance_rate is not None:
            result['matches'] = abs(result['doc_rate'] - live_advance_rate) < 0.01
        results.append(result)

    return results


def _compare_concentration(extraction: dict, live_conc: dict | None) -> list[dict]:
    """Compare extracted concentration limits against live values."""
    results = []
    if not live_conc:
        return results

    live_limits = live_conc.get('limits', [])

    for doc_cl in extraction.get('concentration_limits', []):
        doc_name = doc_cl.get('name', '')
        doc_threshold = doc_cl.get('threshold_pct')

        # Find matching live limit
        live_match = None
        for ll in live_limits:
            if doc_name.lower()[:8] in ll.get('name', '').lower():
                live_match = ll
                break

        if not live_match:
            results.append({
                'name': doc_name,
                'doc_limit': doc_threshold,
                'live_current': None,
                'live_limit': None,
                'compliant': None,
                'headroom': None,
                'discrepancy': False,
                'confidence': doc_cl.get('confidence', 0),
            })
            continue

        live_current = live_match.get('current')
        live_limit = live_match.get('limit_pct') or live_match.get('threshold')

        headroom = None
        if doc_threshold and live_current is not None:
            headroom = round((doc_threshold - live_current) / doc_threshold * 100, 1) if doc_threshold != 0 else None

        results.append({
            'name': doc_name,
            'doc_limit': doc_threshold,
            'live_current': live_current,
            'live_limit': live_limit,
            'compliant': live_current <= doc_threshold if (live_current is not None and doc_threshold is not None) else None,
            'headroom': headroom,
            'discrepancy': abs(doc_threshold - live_limit) > 0.001 if (doc_threshold is not None and live_limit is not None) else False,
            'confidence': doc_cl.get('confidence', 0),
        })

    return results


def _compare_eligibility(extraction: dict, live_bb: dict | None) -> list[dict]:
    """Compare extracted eligibility criteria against what the live BB applies."""
    results = []
    for ec in extraction.get('eligibility_criteria', []):
        results.append({
            'criterion': ec.get('name', ''),
            'doc_value': ec.get('value'),
            'parameter': ec.get('parameter'),
            'description': ec.get('description', ''),
            'confidence': ec.get('confidence', 0),
        })
    return results


# ── Executive Summary Context ─────────────────────────────────────────────

def build_legal_context_for_executive_summary(company: str, product: str) -> str | None:
    """Build legal compliance context string for the AI executive summary.

    Returns a text block describing legal compliance status, or None if
    no legal documents have been extracted.
    """
    extraction = load_latest_extraction(company, product)
    if not extraction:
        return None

    parts = []
    ft = extraction.get('facility_terms', {})
    parts.append(f"LEGAL COMPLIANCE: Document '{extraction.get('filename', 'unknown')}' "
                 f"(effective {ft.get('effective_date', 'unknown')}). "
                 f"Overall extraction confidence: {extraction.get('overall_confidence', 0):.0%}.")

    # Covenants summary
    covs = extraction.get('covenants', [])
    if covs:
        parts.append(f"{len(covs)} financial covenants extracted: "
                     + ', '.join(c.get('name', '') for c in covs) + '.')

    # Concentration limits summary
    cls = extraction.get('concentration_limits', [])
    if cls:
        parts.append(f"{len(cls)} concentration limits: "
                     + ', '.join(c.get('name', '') for c in cls) + '.')

    # Risk flags
    flags = extraction.get('risk_flags', [])
    if flags:
        high = [f for f in flags if f.get('severity') == 'high']
        med = [f for f in flags if f.get('severity') == 'medium']
        flag_summary = []
        if high:
            flag_summary.append(f"{len(high)} high-severity")
        if med:
            flag_summary.append(f"{len(med)} medium-severity")
        parts.append(f"Risk flags: {', '.join(flag_summary)}. "
                     + '; '.join(f.get('description', '')[:80] for f in flags[:3]) + '.')

    return ' '.join(parts)
