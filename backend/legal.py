"""
backend/legal.py
Legal Analysis API endpoints.

Document management (upload, list, extract) and compliance comparison
for facility agreements. All endpoints under /companies/{co}/products/{p}/legal/.
"""

import os
import sys
import json
import shutil
import logging
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, UploadFile, File, Query, BackgroundTasks

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.legal_parser import (
    get_legal_dir,
    list_legal_documents,
    load_extraction_cache,
    parse_legal_document,
    save_parsed_cache,
)
from core.legal_extractor import extract_legal_terms
from core.legal_compliance import (
    load_latest_extraction,
    build_compliance_comparison,
    build_legal_context_for_executive_summary,
)
from core.activity_log import log_activity, LEGAL_UPLOAD, LEGAL_EXTRACTION

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Legal Analysis"])


# ── Document Management ───────────────────────────────────────────────────

@router.post("/companies/{company}/products/{product}/legal/upload")
async def upload_legal_document(
    company: str,
    product: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_type: str = Query("credit_agreement", description="credit_agreement|amendment|security_agreement|fee_letter"),
):
    """Upload a legal PDF and trigger background extraction."""
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    legal_dir = get_legal_dir(company, product)
    safe_name = os.path.basename(file.filename)
    if not safe_name or safe_name.startswith('.'):
        raise HTTPException(status_code=400, detail="Invalid filename")
    file_path = os.path.join(legal_dir, safe_name)

    # Save uploaded file
    content = await file.read()
    with open(file_path, 'wb') as f:
        f.write(content)

    file_size = len(content)
    logger.info(f"Uploaded legal document: {file_path} ({file_size} bytes)")
    log_activity(LEGAL_UPLOAD, company, product, f"Uploaded legal doc: {safe_name} ({file_size} bytes)")

    # Trigger background extraction
    background_tasks.add_task(_background_extract, file_path, document_type, company, product)

    return {
        'filename': safe_name,
        'file_path': file_path,
        'file_size': file_size,
        'document_type': document_type,
        'extraction_status': 'processing',
        'message': f'Document uploaded. Extraction started in background.',
    }


def _background_extract(file_path: str, document_type: str, company: str = None, product: str = None):
    """Run extraction in background task."""
    try:
        logger.info(f"Background extraction starting: {file_path}")
        extract_legal_terms(file_path, document_type=document_type, refresh=True)
        logger.info(f"Background extraction complete: {file_path}")
        log_activity(LEGAL_EXTRACTION, company, product, f"Extracted terms from: {os.path.basename(file_path)}")
    except Exception as e:
        logger.error(f"Background extraction failed: {file_path}: {e}")


@router.get("/companies/{company}/products/{product}/legal/documents")
def list_documents(company: str, product: str):
    """List all legal documents for a company/product."""
    docs = list_legal_documents(company, product)
    return {'documents': docs, 'count': len(docs)}


@router.get("/companies/{company}/products/{product}/legal/documents/{filename}")
def get_document(company: str, product: str, filename: str):
    """Get document details including extraction results."""
    legal_dir = get_legal_dir(company, product)
    file_path = os.path.join(legal_dir, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Document not found: {filename}")

    extraction = load_extraction_cache(file_path)

    return {
        'filename': filename,
        'file_size': os.path.getsize(file_path),
        'extracted': extraction is not None,
        'extraction_status': 'completed' if extraction else 'pending',
        'extraction': extraction,
    }


@router.post("/companies/{company}/products/{product}/legal/documents/{filename}/re-extract")
def re_extract_document(
    company: str,
    product: str,
    filename: str,
    background_tasks: BackgroundTasks,
    document_type: str = Query("credit_agreement"),
):
    """Re-run extraction on an existing document (e.g., after prompt improvements)."""
    legal_dir = get_legal_dir(company, product)
    file_path = os.path.join(legal_dir, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Document not found: {filename}")

    background_tasks.add_task(_background_extract, file_path, document_type)

    return {
        'filename': filename,
        'extraction_status': 'processing',
        'message': 'Re-extraction started in background.',
    }


@router.delete("/companies/{company}/products/{product}/legal/documents/{filename}")
def delete_document(company: str, product: str, filename: str):
    """Delete a legal document and its cached extraction.

    TODO: Add admin-only authorization check (e.g. Depends(require_admin) from
    cf_auth.py). Currently protected only by Cloudflare Access middleware at the
    network layer — any authenticated user can delete legal documents.
    """
    legal_dir = get_legal_dir(company, product)
    file_path = os.path.join(legal_dir, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Document not found: {filename}")

    os.remove(file_path)

    # Remove cached files
    for suffix in ['_extracted.json', '_markdown.md']:
        cache_path = os.path.splitext(file_path)[0] + suffix
        if os.path.exists(cache_path):
            os.remove(cache_path)

    return {'deleted': filename}


# ── Extracted Terms ───────────────────────────────────────────────────────

@router.get("/companies/{company}/products/{product}/legal/facility-terms")
def get_facility_terms(company: str, product: str):
    """Get extracted facility terms from the latest credit agreement."""
    extraction = load_latest_extraction(company, product)
    if not extraction:
        return {'available': False, 'message': 'No legal documents extracted yet'}

    return {
        'available': True,
        'facility_terms': extraction.get('facility_terms', {}),
        'document': {
            'filename': extraction.get('filename', ''),
            'extracted_at': extraction.get('extracted_at', ''),
            'confidence': extraction.get('overall_confidence', 0),
        },
    }


@router.get("/companies/{company}/products/{product}/legal/eligibility")
def get_eligibility(company: str, product: str):
    """Get extracted eligibility criteria and advance rates."""
    extraction = load_latest_extraction(company, product)
    if not extraction:
        return {'available': False}

    return {
        'available': True,
        'eligibility_criteria': extraction.get('eligibility_criteria', []),
        'advance_rates': extraction.get('advance_rates', []),
        'document': {
            'filename': extraction.get('filename', ''),
            'extracted_at': extraction.get('extracted_at', ''),
        },
    }


@router.get("/companies/{company}/products/{product}/legal/covenants-extracted")
def get_covenants_extracted(company: str, product: str):
    """Get extracted covenant thresholds and concentration limits."""
    extraction = load_latest_extraction(company, product)
    if not extraction:
        return {'available': False}

    return {
        'available': True,
        'covenants': extraction.get('covenants', []),
        'concentration_limits': extraction.get('concentration_limits', []),
        'document': {
            'filename': extraction.get('filename', ''),
            'extracted_at': extraction.get('extracted_at', ''),
        },
    }


@router.get("/companies/{company}/products/{product}/legal/events-of-default")
def get_events_of_default(company: str, product: str):
    """Get extracted events of default with severity classification."""
    extraction = load_latest_extraction(company, product)
    if not extraction:
        return {'available': False}

    return {
        'available': True,
        'events_of_default': extraction.get('events_of_default', []),
        'document': {
            'filename': extraction.get('filename', ''),
            'extracted_at': extraction.get('extracted_at', ''),
        },
    }


@router.get("/companies/{company}/products/{product}/legal/reporting")
def get_reporting_requirements(company: str, product: str):
    """Get extracted reporting obligations + payment schedule."""
    extraction = load_latest_extraction(company, product)
    if not extraction:
        return {'available': False}

    # Load payment schedule if available
    payment_schedule = None
    legal_dir = get_legal_dir(company, product)
    schedule_path = os.path.join(legal_dir, 'payment_schedule.json')
    if os.path.exists(schedule_path):
        with open(schedule_path, 'r') as f:
            payment_schedule = json.load(f)

    return {
        'available': True,
        'reporting_requirements': extraction.get('reporting_requirements', []),
        'waterfall_normal': extraction.get('waterfall_normal', []),
        'waterfall_default': extraction.get('waterfall_default', []),
        'payment_schedule': payment_schedule,
        'document': {
            'filename': extraction.get('filename', ''),
            'extracted_at': extraction.get('extracted_at', ''),
        },
    }


@router.get("/companies/{company}/products/{product}/legal/risk-flags")
def get_risk_flags(company: str, product: str):
    """Get AI-generated risk assessment flags."""
    extraction = load_latest_extraction(company, product)
    if not extraction:
        return {'available': False}

    return {
        'available': True,
        'risk_flags': extraction.get('risk_flags', []),
        'document': {
            'filename': extraction.get('filename', ''),
            'extracted_at': extraction.get('extracted_at', ''),
        },
    }


# ── Compliance Comparison ─────────────────────────────────────────────────

@router.get("/companies/{company}/products/{product}/legal/compliance-comparison")
def get_compliance_comparison(
    company: str,
    product: str,
    snapshot: Optional[str] = None,
    as_of_date: Optional[str] = None,
    currency: Optional[str] = None,
):
    """Compare extracted document terms against live portfolio metrics.

    Returns side-by-side comparison: document thresholds vs live values,
    breach distances, and discrepancies from hardcoded defaults.
    """
    extraction = load_latest_extraction(company, product)
    if not extraction:
        return {'available': False, 'message': 'No legal documents extracted'}

    # Import here to avoid circular imports
    from backend.main import _portfolio_load
    from core.portfolio import (
        compute_klaim_covenants, compute_klaim_concentration_limits,
        compute_klaim_borrowing_base,
    )

    try:
        df, sel, config, disp, mult, ref_date, fp, atype = _portfolio_load(
            company, product, snapshot, as_of_date, currency
        )

        live_covs = compute_klaim_covenants(df, mult, ref_date, fp)
        live_conc = compute_klaim_concentration_limits(df, mult, ref_date, fp)
        live_bb = compute_klaim_borrowing_base(df, mult, ref_date, fp)

        comparison = build_compliance_comparison(
            extraction,
            live_covenants=live_covs.get('covenants', []),
            live_bb=live_bb,
            live_concentration=live_conc,
        )
        return {**comparison, 'available': True}

    except Exception as e:
        logger.warning(f"Failed to compute compliance comparison: {e}")
        # Return extraction-only comparison without live data
        comparison = build_compliance_comparison(extraction)
        return {**comparison, 'available': True, 'live_data_error': str(e)}


@router.get("/companies/{company}/products/{product}/legal/amendment-diff")
def get_amendment_diff(
    company: str,
    product: str,
    filename_old: str = Query(..., description="Older document filename"),
    filename_new: str = Query(..., description="Newer document filename"),
):
    """Compare two document versions and return material changes."""
    legal_dir = get_legal_dir(company, product)

    old_path = os.path.join(legal_dir, filename_old)
    new_path = os.path.join(legal_dir, filename_new)

    old_ext = load_extraction_cache(old_path)
    new_ext = load_extraction_cache(new_path)

    if not old_ext:
        raise HTTPException(status_code=404, detail=f"No extraction for: {filename_old}")
    if not new_ext:
        raise HTTPException(status_code=404, detail=f"No extraction for: {filename_new}")

    changes = _compute_diff(old_ext, new_ext)
    return {
        'old_document': filename_old,
        'new_document': filename_new,
        'changes': changes,
        'material_change_count': sum(1 for c in changes if c.get('material', False)),
    }


def _compute_diff(old: dict, new: dict) -> list[dict]:
    """Compute differences between two extraction results."""
    changes = []

    # Compare facility terms
    old_ft = old.get('facility_terms', {})
    new_ft = new.get('facility_terms', {})
    for key in set(list(old_ft.keys()) + list(new_ft.keys())):
        if key in ('confidence', 'section_ref'):
            continue
        old_val = old_ft.get(key)
        new_val = new_ft.get(key)
        if old_val != new_val:
            changes.append({
                'section': 'Facility Terms',
                'field': key,
                'old_value': str(old_val) if old_val is not None else None,
                'new_value': str(new_val) if new_val is not None else None,
                'material': key in ('facility_limit', 'maturity_date', 'interest_rate_description'),
            })

    # Compare advance rates
    old_rates = {ar.get('category'): ar.get('rate') for ar in old.get('advance_rates', [])}
    new_rates = {ar.get('category'): ar.get('rate') for ar in new.get('advance_rates', [])}
    for cat in set(list(old_rates.keys()) + list(new_rates.keys())):
        if old_rates.get(cat) != new_rates.get(cat):
            changes.append({
                'section': 'Advance Rates',
                'field': cat,
                'old_value': str(old_rates.get(cat)),
                'new_value': str(new_rates.get(cat)),
                'material': True,
            })

    # Compare covenants
    old_covs = {c.get('metric'): c.get('threshold') for c in old.get('covenants', []) if c.get('metric')}
    new_covs = {c.get('metric'): c.get('threshold') for c in new.get('covenants', []) if c.get('metric')}
    for metric in set(list(old_covs.keys()) + list(new_covs.keys())):
        if old_covs.get(metric) != new_covs.get(metric):
            changes.append({
                'section': 'Covenants',
                'field': metric,
                'old_value': str(old_covs.get(metric)),
                'new_value': str(new_covs.get(metric)),
                'material': True,
            })

    # Compare concentration limits
    old_cls = {c.get('limit_type'): c.get('threshold_pct') for c in old.get('concentration_limits', [])}
    new_cls = {c.get('limit_type'): c.get('threshold_pct') for c in new.get('concentration_limits', [])}
    for lt in set(list(old_cls.keys()) + list(new_cls.keys())):
        if old_cls.get(lt) != new_cls.get(lt):
            changes.append({
                'section': 'Concentration Limits',
                'field': lt,
                'old_value': str(old_cls.get(lt)),
                'new_value': str(new_cls.get(lt)),
                'material': True,
            })

    return changes
