from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import sys, os, json, re, subprocess, tempfile, pandas as pd
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.loader import get_companies, get_products, get_snapshots, load_snapshot, load_silq_snapshot
from core.config import load_config, SUPPORTED_CURRENCIES
from core.analysis import (
    compute_summary, compute_deployment, compute_deployment_by_product,
    compute_collection_velocity,
    compute_denial_trend, compute_cohorts, compute_actual_vs_expected,
    compute_ageing, compute_revenue, compute_concentration,
    compute_returns_analysis, apply_multiplier, filter_by_date,
    compute_dso, compute_hhi, compute_denial_funnel,
    compute_stress_test, compute_expected_loss, compute_loss_triangle,
    compute_group_performance,
    compute_collection_curves, compute_owner_breakdown, compute_vat_summary,
    compute_par, compute_dtfc,
    compute_cohort_loss_waterfall, compute_recovery_analysis,
    compute_vintage_loss_curves, compute_underwriting_drift,
    compute_segment_analysis, compute_collections_timing,
    compute_seasonality, compute_loss_categorization,
    compute_methodology_log, compute_hhi_for_snapshot,
)
from core.migration import compute_roll_rates
from core.validation import validate_tape
from core.consistency import run_consistency_check
from core.reporter import generate_ai_analysis, save_pdf_report
from core.analysis_ejari import parse_ejari_workbook
from core.analysis_silq import (
    compute_silq_summary, compute_silq_delinquency, compute_silq_collections,
    compute_silq_concentration, compute_silq_cohorts, compute_silq_yield,
    compute_silq_tenure, compute_silq_borrowing_base, compute_silq_covenants,
    compute_silq_seasonality, compute_silq_cohort_loss_waterfall, compute_silq_underwriting_drift,
    filter_silq_by_date,
)
from core.validation_silq import validate_silq_tape
from core.portfolio import (
    compute_borrowing_base as portfolio_borrowing_base,
    compute_concentration_limits as portfolio_concentration_limits,
    compute_covenants as portfolio_covenants,
    compute_portfolio_flow,
    compute_klaim_borrowing_base,
    compute_klaim_concentration_limits,
    compute_klaim_covenants,
)
from core.database import engine, get_db
from core.db_loader import has_db_data, load_from_db, get_facility_config as db_facility_config
from backend.integration import router as integration_router
from fastapi import Depends
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    if engine:
        try:
            from sqlalchemy import text as sa_text
            with engine.connect() as conn:
                conn.execute(sa_text("SELECT 1"))
            print("[Laith] Database connected.")
        except Exception as e:
            print(f"[Laith] Database connection failed: {e}. Running in tape-only mode.")
    else:
        print("[Laith] No DATABASE_URL configured. Running in tape-only mode.")
    yield


app = FastAPI(title="ACP Private Credit API", lifespan=lifespan)
app.include_router(integration_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _load(company, product, snapshot):
    """Load and return the selected snapshot DataFrame + snapshot metadata."""
    snaps = get_snapshots(company, product)
    if not snaps:
        raise HTTPException(status_code=404, detail="No snapshots found")
    sel = next((s for s in snaps if s['filename'] == snapshot or s['date'] == snapshot), snaps[-1])
    return load_snapshot(sel['filepath']), sel

def _currency(company, product, requested):
    config = load_config(company, product)
    return config, requested or (config['currency'] if config else 'USD')

def _integrity_dir(company, product):
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'reports', f'{company}_{product}')
    os.makedirs(base, exist_ok=True)
    return base

def _integrity_path(company, product, snap_old, snap_new, suffix=''):
    # Sanitize snapshot names for filenames (replace problematic chars)
    safe_old = snap_old.replace('/', '_').replace('\\', '_')
    safe_new = snap_new.replace('/', '_').replace('\\', '_')
    return os.path.join(_integrity_dir(company, product), f'{safe_old}__vs__{safe_new}{suffix}.json')

def _extract_questions(text):
    """Extract numbered questions from AI analysis text."""
    questions = []
    in_questions = False
    for line in text.split('\n'):
        stripped = line.strip()
        if 'QUESTIONS FOR THE COMPANY' in stripped.upper():
            in_questions = True
            continue
        if in_questions:
            # Stop at next section header
            if stripped and (stripped.isupper() and len(stripped) > 10) or stripped.startswith('4.') and 'RECOMMENDED' in stripped.upper():
                break
            # Extract numbered questions
            m = re.match(r'^\d+[\.\)]\s*(.+)', stripped)
            if m:
                questions.append(m.group(1).strip())
    return questions

def _get_analysis_type(company, product):
    """Return the analysis_type from config, defaulting to 'klaim'."""
    config = load_config(company, product)
    return (config or {}).get('analysis_type', 'klaim')

def _resolve_snapshot(company, product, snapshot):
    """Resolve the selected snapshot metadata dict."""
    snaps = get_snapshots(company, product)
    if not snaps:
        raise HTTPException(status_code=404, detail="No snapshots found")
    return next((s for s in snaps if s['filename'] == snapshot or s['date'] == snapshot), snaps[-1])

def _silq_load(company, product, snapshot, as_of_date, currency):
    """Load SILQ data (multi-sheet) with currency multiplier applied.
    Returns (df, sel, config, disp, mult, commentary_text, ref_date)."""
    sel = _resolve_snapshot(company, product, snapshot)
    df, commentary_text = load_silq_snapshot(sel['filepath'])
    df = filter_silq_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    # DPD reference date: as-of date if set, otherwise snapshot date
    ref_date = pd.to_datetime(as_of_date) if as_of_date else pd.to_datetime(sel['date'])
    return df, sel, config, disp, mult, commentary_text, ref_date

# ── Framework endpoint ─────────────────────────────────────────────────────────

@app.get("/framework")
def get_framework():
    """Return the analysis framework markdown document."""
    framework_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'core', 'ANALYSIS_FRAMEWORK.md')
    try:
        with open(framework_path, 'r', encoding='utf-8') as f:
            return {'content': f.read()}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Framework document not found")

# ── FX rates endpoint ──────────────────────────────────────────────────────────

@app.get("/fx-rates")
def get_fx_rates_endpoint():
    """Return current FX rates and source (live or fallback)."""
    from core.config import get_fx_rates, get_fx_source
    return {'rates': get_fx_rates(), 'source': get_fx_source()}

# ── Company / Product / Snapshot endpoints ────────────────────────────────────

@app.get("/companies")
def list_companies():
    return [
        {'name': co, 'products': ps,
         'total_snapshots': sum(len(get_snapshots(co, p)) for p in ps)}
        for co in get_companies()
        for ps in [get_products(co)]
    ]

@app.get("/companies/{company}/products")
def list_products(company: str):
    ps = get_products(company)
    if not ps:
        raise HTTPException(status_code=404, detail=f"No products found for {company}")
    return ps

@app.get("/companies/{company}/products/{product}/snapshots")
def list_snapshots(company: str, product: str):
    return [{'filename': s['filename'], 'date': s['date']}
            for s in get_snapshots(company, product)]

@app.get("/companies/{company}/products/{product}/config")
def get_product_config(company: str, product: str):
    config = load_config(company, product)
    if not config:
        return {'currency': 'USD', 'description': '', 'usd_rate': 1.0, 'configured': False}
    return {**config, 'configured': True}

@app.get("/companies/{company}/products/{product}/date-range")
def get_date_range(company: str, product: str, snapshot: Optional[str] = None):
    at = _get_analysis_type(company, product)
    if at == 'silq':
        sel = _resolve_snapshot(company, product, snapshot)
        df, _ = load_silq_snapshot(sel['filepath'])
    else:
        df, sel = _load(company, product, snapshot)
    date_col = 'Disbursement_Date' if at == 'silq' else 'Deal date'
    if date_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"No {date_col} column found")
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    df = df.dropna(subset=[date_col])
    data_max = df[date_col].max().strftime('%Y-%m-%d')
    snap_date = sel['date']
    # Use snapshot date as upper bound if it's later than the data's max date
    effective_max = max(data_max, snap_date) if snap_date else data_max
    return {
        'min_date':      df[date_col].min().strftime('%Y-%m-%d'),
        'max_date':      effective_max,
        'snapshot_date': snap_date,
    }

# ── Summary ───────────────────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/summary")
def get_summary(company: str, product: str,
                snapshot: Optional[str] = None,
                as_of_date: Optional[str] = None,
                currency: Optional[str] = None):
    at = _get_analysis_type(company, product)
    if at == 'ejari_summary':
        return {'company': company, 'product': product, 'display_currency': 'USD',
                'total_deals': 0, 'total_purchase_value': 0, 'total_collected': 0,
                'total_denied': 0, 'total_pending': 0, 'total_expected': 0,
                'collection_rate': 0, 'denial_rate': 0, 'pending_rate': 0,
                'active_deals': 0, 'completed_deals': 0, 'avg_discount': 0,
                'dso_available': False, 'hhi_group': 0, 'top_1_group_pct': 0,
                'analysis_type': 'ejari_summary'}
    if at == 'silq':
        df, sel, config, disp, mult, commentary_text, ref_date = _silq_load(company, product, snapshot, as_of_date, currency)
        if not len(df):
            raise HTTPException(status_code=400, detail="No deals found for selected date range")
        summary = compute_silq_summary(df, mult, ref_date=ref_date)
        return {'company': company, 'product': product, 'display_currency': disp,
                'portfolio_commentary': commentary_text, **summary}

    df, sel  = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    if not len(df):
        raise HTTPException(status_code=400, detail="No deals found for selected date range")
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    summary  = compute_summary(df, config, disp, sel['date'], as_of_date)
    # Enrich with DSO and HHI
    dso_data = compute_dso(df, mult, as_of_date)
    hhi_data = compute_hhi(df, mult)
    summary['dso_available'] = dso_data.get('available', False)
    summary['dso']          = dso_data['weighted_dso']
    summary['median_dso']   = dso_data['median_dso']
    summary['hhi_group']    = hhi_data.get('group', {}).get('hhi', 0)
    summary['hhi_product']  = hhi_data.get('product', {}).get('hhi', 0)
    summary['top_1_group_pct'] = hhi_data.get('group', {}).get('top_1_pct', 0)
    return {'company': company, 'product': product, **summary}

# ── Chart endpoints ───────────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/deployment")
def get_deployment_chart(company: str, product: str,
                         snapshot: Optional[str] = None,
                         as_of_date: Optional[str] = None,
                         currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {'data': compute_deployment(df, mult), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/deployment-by-product")
def get_deployment_by_product(company: str, product: str,
                               snapshot: Optional[str] = None,
                               as_of_date: Optional[str] = None,
                               currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {**compute_deployment_by_product(df, mult), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/collection-velocity")
def get_collection_velocity(company: str, product: str,
                             snapshot: Optional[str] = None,
                             as_of_date: Optional[str] = None,
                             currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {**compute_collection_velocity(df, mult, as_of_date), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/collection-curves")
def get_collection_curves(company: str, product: str,
                           snapshot: Optional[str] = None,
                           as_of_date: Optional[str] = None,
                           currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {**compute_collection_curves(df, mult), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/denial-trend")
def get_denial_trend(company: str, product: str,
                     snapshot: Optional[str] = None,
                     as_of_date: Optional[str] = None,
                     currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {'data': compute_denial_trend(df, mult), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/cohort")
def get_cohort_analysis(company: str, product: str,
                         snapshot: Optional[str] = None,
                         as_of_date: Optional[str] = None,
                         currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {'cohorts': compute_cohorts(df, mult), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/actual-vs-expected")
def get_actual_vs_expected(company: str, product: str,
                            snapshot: Optional[str] = None,
                            as_of_date: Optional[str] = None,
                            currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {**compute_actual_vs_expected(df, mult), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/ageing")
def get_ageing(company: str, product: str,
               snapshot: Optional[str] = None,
               as_of_date: Optional[str] = None,
               currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {**compute_ageing(df, mult, as_of_date), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/revenue")
def get_revenue(company: str, product: str,
                snapshot: Optional[str] = None,
                as_of_date: Optional[str] = None,
                currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    result = compute_revenue(df, mult)
    result['vat'] = compute_vat_summary(df, mult)
    return {**result, 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/concentration")
def get_concentration(company: str, product: str,
                       snapshot: Optional[str] = None,
                       as_of_date: Optional[str] = None,
                       currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    result   = compute_concentration(df, mult)
    # Enrich with HHI and Owner breakdown
    result['hhi']   = compute_hhi(df, mult)
    result['owner'] = compute_owner_breakdown(df, mult)
    return {**result, 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/returns-analysis")
def get_returns_analysis(company: str, product: str,
                         snapshot: Optional[str] = None,
                         as_of_date: Optional[str] = None,
                         currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {**compute_returns_analysis(df, mult), 'currency': disp}

# ── New analytics endpoints ───────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/dso")
def get_dso(company: str, product: str,
            snapshot: Optional[str] = None,
            as_of_date: Optional[str] = None,
            currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {**compute_dso(df, mult, as_of_date), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/denial-funnel")
def get_denial_funnel(company: str, product: str,
                      snapshot: Optional[str] = None,
                      as_of_date: Optional[str] = None,
                      currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {**compute_denial_funnel(df, mult), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/stress-test")
def get_stress_test(company: str, product: str,
                    snapshot: Optional[str] = None,
                    as_of_date: Optional[str] = None,
                    currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {**compute_stress_test(df, mult), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/expected-loss")
def get_expected_loss(company: str, product: str,
                      snapshot: Optional[str] = None,
                      as_of_date: Optional[str] = None,
                      currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {**compute_expected_loss(df, mult), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/loss-triangle")
def get_loss_triangle(company: str, product: str,
                      snapshot: Optional[str] = None,
                      as_of_date: Optional[str] = None,
                      currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {**compute_loss_triangle(df, mult), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/group-performance")
def get_group_performance(company: str, product: str,
                          snapshot: Optional[str] = None,
                          as_of_date: Optional[str] = None,
                          currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {**compute_group_performance(df, mult, as_of_date), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/risk-migration")
def get_risk_migration(company: str, product: str,
                       snapshot: Optional[str] = None,
                       compare_snapshot: Optional[str] = None,
                       as_of_date: Optional[str] = None,
                       currency: Optional[str] = None):
    """Roll-rate migration analysis comparing two snapshots."""
    snaps = get_snapshots(company, product)
    if len(snaps) < 2:
        return {'error': 'Need at least 2 snapshots for migration analysis',
                'available_snapshots': len(snaps)}

    # Default: compare second-to-last vs last snapshot
    if not snapshot:
        snapshot = snaps[-1]['filename']
    if not compare_snapshot:
        # Find the snapshot before the selected one
        sel_idx = next((i for i, s in enumerate(snaps) if s['filename'] == snapshot or s['date'] == snapshot), len(snaps) - 1)
        if sel_idx > 0:
            compare_snapshot = snaps[sel_idx - 1]['filename']
        else:
            return {'error': 'No earlier snapshot to compare against'}

    # Load both snapshots
    old_sel = next((s for s in snaps if s['filename'] == compare_snapshot or s['date'] == compare_snapshot), None)
    new_sel = next((s for s in snaps if s['filename'] == snapshot or s['date'] == snapshot), None)
    if not old_sel or not new_sel:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    old_df = load_snapshot(old_sel['filepath'])
    new_df = load_snapshot(new_sel['filepath'])

    if as_of_date:
        old_df = filter_by_date(old_df, as_of_date)
        new_df = filter_by_date(new_df, as_of_date)

    result = compute_roll_rates(old_df, new_df, old_sel['date'], new_sel['date'])

    # Also compute stress test & EL on the new snapshot for the Risk tab
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    result['stress_test']    = compute_stress_test(new_df, mult)
    result['expected_loss']  = compute_expected_loss(new_df, mult)
    result['currency']       = disp
    result['old_snapshot']   = old_sel['date']
    result['new_snapshot']   = new_sel['date']

    return result

# ── PAR (Portfolio at Risk) ───────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/par")
def get_par(company: str, product: str,
            snapshot: Optional[str] = None, currency: Optional[str] = None,
            as_of_date: Optional[str] = None):
    """Portfolio at Risk KPIs."""
    df, sel = _load(company, product, snapshot)
    df = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    return compute_par(df, mult, as_of_date=as_of_date or sel['date'])

# ── DTFC (Days to First Cash) ────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/dtfc")
def get_dtfc(company: str, product: str,
             snapshot: Optional[str] = None, currency: Optional[str] = None,
             as_of_date: Optional[str] = None):
    """Days to First Cash — leading indicator."""
    df, sel = _load(company, product, snapshot)
    df = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    return compute_dtfc(df, mult, as_of_date=as_of_date or sel['date'])

# ── Cohort Loss Waterfall ────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/cohort-loss-waterfall")
def get_cohort_loss_waterfall(company: str, product: str,
                              snapshot: Optional[str] = None, currency: Optional[str] = None,
                              as_of_date: Optional[str] = None):
    df, sel = _load(company, product, snapshot)
    df = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    return compute_cohort_loss_waterfall(df, mult, as_of_date=as_of_date or sel['date'])

# ── Recovery Analysis ────────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/recovery-analysis")
def get_recovery_analysis(company: str, product: str,
                          snapshot: Optional[str] = None, currency: Optional[str] = None,
                          as_of_date: Optional[str] = None):
    df, sel = _load(company, product, snapshot)
    df = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    return compute_recovery_analysis(df, mult, as_of_date=as_of_date or sel['date'])

# ── Vintage Loss Curves ─────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/vintage-loss-curves")
def get_vintage_loss_curves(company: str, product: str,
                            snapshot: Optional[str] = None, currency: Optional[str] = None,
                            as_of_date: Optional[str] = None):
    df, sel = _load(company, product, snapshot)
    df = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    return compute_vintage_loss_curves(df, mult, as_of_date=as_of_date or sel['date'])

# ── Underwriting Drift ──────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/underwriting-drift")
def get_underwriting_drift(company: str, product: str,
                           snapshot: Optional[str] = None, currency: Optional[str] = None,
                           as_of_date: Optional[str] = None):
    df, sel = _load(company, product, snapshot)
    df = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    return compute_underwriting_drift(df, mult, as_of_date=as_of_date or sel['date'])

# ── Segment Analysis ─────────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/segment-analysis")
def get_segment_analysis(company: str, product: str,
                         snapshot: Optional[str] = None, currency: Optional[str] = None,
                         as_of_date: Optional[str] = None, segment_by: str = 'product'):
    df, sel = _load(company, product, snapshot)
    df = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    return compute_segment_analysis(df, mult, as_of_date=as_of_date or sel['date'], segment_by=segment_by)

# ── Collections Timing ───────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/collections-timing")
def get_collections_timing(company: str, product: str,
                           snapshot: Optional[str] = None, currency: Optional[str] = None,
                           as_of_date: Optional[str] = None, view: str = 'origination_month'):
    df, sel = _load(company, product, snapshot)
    df = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    return compute_collections_timing(df, mult, as_of_date=as_of_date or sel['date'], view=view)

# ── Seasonality ──────────────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/seasonality")
def get_seasonality(company: str, product: str,
                    snapshot: Optional[str] = None, currency: Optional[str] = None,
                    as_of_date: Optional[str] = None):
    df, sel = _load(company, product, snapshot)
    df = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    return compute_seasonality(df, mult, as_of_date=as_of_date or sel['date'])

# ── Loss Categorization ─────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/loss-categorization")
def get_loss_categorization(company: str, product: str,
                            snapshot: Optional[str] = None, currency: Optional[str] = None,
                            as_of_date: Optional[str] = None):
    df, sel = _load(company, product, snapshot)
    df = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    return compute_loss_categorization(df, mult, as_of_date=as_of_date or sel['date'])

# ── Methodology Log ──────────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/methodology-log")
def get_methodology_log(company: str, product: str,
                        snapshot: Optional[str] = None,
                        as_of_date: Optional[str] = None):
    df, sel = _load(company, product, snapshot)
    df = filter_by_date(df, as_of_date)
    return compute_methodology_log(df, as_of_date=as_of_date or sel['date'])

# ── HHI Time Series ─────────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/hhi-timeseries")
def get_hhi_timeseries(company: str, product: str, currency: Optional[str] = None):
    """Compute HHI across ALL snapshots for time series view."""
    snaps = get_snapshots(company, product)
    if len(snaps) < 2:
        return {'available': False, 'reason': 'Need at least 2 snapshots'}

    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)

    points = []
    for snap in snaps:
        try:
            snap_df = load_snapshot(snap['filepath'])
            hhi = compute_hhi_for_snapshot(snap_df, mult)
            points.append({
                'date': snap['date'],
                'group_hhi': hhi.get('group_hhi'),
                'product_hhi': hhi.get('product_hhi'),
            })
        except Exception:
            continue

    if len(points) < 2:
        return {'available': False, 'reason': 'Insufficient valid snapshots'}

    # Trend detection
    group_vals = [p['group_hhi'] for p in points if p['group_hhi'] is not None]
    trend = 'stable'
    warning = None
    if len(group_vals) >= 2:
        if group_vals[-1] > group_vals[0] * 1.10:
            trend = 'increasing'
            warning = f'Group HHI increased from {group_vals[0]:.4f} to {group_vals[-1]:.4f}'
        elif group_vals[-1] < group_vals[0] * 0.90:
            trend = 'decreasing'

    return {
        'available': True,
        'points': points,
        'trend': trend,
        'warning': warning,
    }

# ── Ejari summary endpoint ────────────────────────────────────────────────────

_ejari_cache = {}

@app.get("/companies/{company}/products/{product}/ejari-summary")
def get_ejari_summary(company: str, product: str, snapshot: Optional[str] = None):
    """Return parsed Ejari ODS workbook as structured JSON (read-only summary)."""
    sel = _resolve_snapshot(company, product, snapshot)
    filepath = sel['filepath']
    if filepath not in _ejari_cache:
        _ejari_cache[filepath] = parse_ejari_workbook(filepath)
    return _ejari_cache[filepath]

# ── SILQ chart endpoints ─────────────────────────────────────────────────────

SILQ_CHART_MAP = {
    'delinquency':        compute_silq_delinquency,
    'collections':        compute_silq_collections,
    'concentration':      compute_silq_concentration,
    'cohort':             compute_silq_cohorts,
    'yield-margins':      compute_silq_yield,
    'tenure':             compute_silq_tenure,
    'borrowing-base':     compute_silq_borrowing_base,
    'covenants':          compute_silq_covenants,
    'seasonality':        compute_silq_seasonality,
    'loss-waterfall':     compute_silq_cohort_loss_waterfall,
    'underwriting-drift': compute_silq_underwriting_drift,
}

@app.get("/companies/{company}/products/{product}/charts/silq/{chart_name}")
def get_silq_chart(company: str, product: str, chart_name: str,
                   snapshot: Optional[str] = None,
                   as_of_date: Optional[str] = None,
                   currency: Optional[str] = None):
    """Generic SILQ chart endpoint — dispatches to the right compute function."""
    fn = SILQ_CHART_MAP.get(chart_name)
    if not fn:
        raise HTTPException(status_code=404, detail=f"Unknown SILQ chart: {chart_name}")
    df, sel, config, disp, mult, _, ref_date = _silq_load(company, product, snapshot, as_of_date, currency)
    # Pass ref_date to functions that accept it (for DPD calculations)
    import inspect
    if 'ref_date' in inspect.signature(fn).parameters:
        result = fn(df, mult, ref_date=ref_date)
    else:
        result = fn(df, mult)
    return {**result, 'currency': disp}

@app.get("/companies/{company}/products/{product}/validate")
def validate_snapshot(company: str, product: str,
                      snapshot: Optional[str] = None):
    """Run data quality checks on a single tape."""
    at = _get_analysis_type(company, product)
    if at == 'silq':
        sel = _resolve_snapshot(company, product, snapshot)
        df, _ = load_silq_snapshot(sel['filepath'])
    else:
        df, sel = _load(company, product, snapshot)
    result = validate_silq_tape(df) if at == 'silq' else validate_tape(df)
    result['snapshot'] = sel['date']
    result['filename'] = sel['filename']
    return result

# ── Data Integrity endpoints ──────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/integrity/cached")
def get_integrity_cached(company: str, product: str,
                         snapshot_old: str, snapshot_new: str):
    """Check if integrity results are already cached."""
    path = _integrity_path(company, product, snapshot_old, snapshot_new)
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {"cached": False}

@app.get("/companies/{company}/products/{product}/integrity")
def run_integrity_checks(company: str, product: str,
                         snapshot_old: str, snapshot_new: str):
    """Run validation + consistency checks on two snapshots."""
    at = _get_analysis_type(company, product)
    if at == 'silq':
        old_sel = _resolve_snapshot(company, product, snapshot_old)
        new_sel = _resolve_snapshot(company, product, snapshot_new)
        old_df, _ = load_silq_snapshot(old_sel['filepath'])
        new_df, _ = load_silq_snapshot(new_sel['filepath'])
    else:
        old_df, old_sel = _load(company, product, snapshot_old)
        new_df, new_sel = _load(company, product, snapshot_new)

    validate_fn = validate_silq_tape if at == 'silq' else validate_tape
    validation_old = validate_fn(old_df)
    validation_new = validate_fn(new_df)
    consistency    = run_consistency_check(old_df, new_df, old_sel['date'], new_sel['date'])

    result = {
        "validation_old": validation_old,
        "validation_new": validation_new,
        "consistency":    consistency,
        "snapshot_old":   old_sel['date'],
        "snapshot_new":   new_sel['date'],
        "ran_at":         datetime.now().isoformat(),
    }

    # Cache to disk
    path = _integrity_path(company, product, snapshot_old, snapshot_new)
    with open(path, 'w') as f:
        json.dump(result, f, indent=2, default=str)

    return result

@app.post("/companies/{company}/products/{product}/integrity/report")
def generate_integrity_report(company: str, product: str, request: dict):
    """Generate AI analysis report from cached integrity results."""
    snapshot_old = request.get('snapshot_old')
    snapshot_new = request.get('snapshot_new')
    if not snapshot_old or not snapshot_new:
        raise HTTPException(status_code=400, detail="snapshot_old and snapshot_new are required")

    # Load cached integrity results
    cached_path = _integrity_path(company, product, snapshot_old, snapshot_new)
    if not os.path.exists(cached_path):
        raise HTTPException(status_code=404, detail="Must run integrity checks first")

    with open(cached_path, 'r') as f:
        cached = json.load(f)

    # Build checks list for reporter
    checks = [{
        "old_label": cached['snapshot_old'],
        "new_label": cached['snapshot_new'],
        "report":    cached['consistency'],
    }]

    # Generate AI analysis and PDF
    analysis_text = generate_ai_analysis(company, product, checks)
    pdf_path      = save_pdf_report(company, product, analysis_text, checks)
    questions     = _extract_questions(analysis_text)

    report = {
        "analysis_text": analysis_text,
        "questions":     questions,
        "pdf_path":      pdf_path,
        "generated_at":  datetime.now().isoformat(),
    }

    # Cache report JSON
    report_path = _integrity_path(company, product, snapshot_old, snapshot_new, '_report')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    return report

@app.get("/companies/{company}/products/{product}/integrity/report")
def get_integrity_report_cached(company: str, product: str,
                                snapshot_old: str, snapshot_new: str):
    """Return cached AI integrity report if available."""
    path = _integrity_path(company, product, snapshot_old, snapshot_new, '_report')
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {"cached": False}

@app.post("/companies/{company}/products/{product}/integrity/notes")
def save_integrity_notes(company: str, product: str, request: dict):
    """Save analyst notes/answers for integrity questions."""
    snapshot_old = request.get('snapshot_old')
    snapshot_new = request.get('snapshot_new')
    notes        = request.get('notes', {})
    if not snapshot_old or not snapshot_new:
        raise HTTPException(status_code=400, detail="snapshot_old and snapshot_new are required")

    path = _integrity_path(company, product, snapshot_old, snapshot_new, '_notes')
    with open(path, 'w') as f:
        json.dump({"notes": notes, "saved_at": datetime.now().isoformat()}, f, indent=2)

    return {"saved": True}

@app.get("/companies/{company}/products/{product}/integrity/notes")
def get_integrity_notes(company: str, product: str,
                        snapshot_old: str, snapshot_new: str):
    """Return saved analyst notes for an integrity check pair."""
    path = _integrity_path(company, product, snapshot_old, snapshot_new, '_notes')
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {"notes": {}}

# ── AI endpoints ──────────────────────────────────────────────────────────────

def _ai_client():
    import anthropic
    from dotenv import load_dotenv
    load_dotenv()
    return anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

@app.get("/companies/{company}/products/{product}/ai-commentary")
def get_ai_commentary(company: str, product: str,
                      snapshot: Optional[str] = None,
                      as_of_date: Optional[str] = None,
                      currency: Optional[str] = None):
    at = _get_analysis_type(company, product)

    if at == 'silq':
        df, sel, config, disp, mult, commentary_text, ref_date = _silq_load(company, product, snapshot, as_of_date, currency)
        s = compute_silq_summary(df, mult, ref_date=ref_date)
        d = compute_silq_delinquency(df, mult, ref_date=ref_date)
        c = compute_silq_collections(df, mult)

        commentary_ctx = ''
        if commentary_text:
            commentary_ctx = f"\nANALYST PORTFOLIO COMMENTARY (from tape):\n{commentary_text}\n"

        prompt = f"""You are a senior analyst at ACP Private Credit, analyzing SILQ's POS lending portfolio (BNPL, RBF & RCL loans) in KSA.
Data as of: {as_of_date or sel['date']}  |  Currency: {disp}

PORTFOLIO SNAPSHOT:
- Total Loans: {s['total_deals']:,} ({s['active_deals']} active, {s['completed_deals']} closed)
- Total Disbursed: {disp} {s['total_disbursed']/1e6:.1f}M
- Outstanding: {disp} {s['total_outstanding']/1e6:.1f}M
- Collection Rate: {s['collection_rate']:.1f}% (repaid vs collectable)
- Overdue Rate: {s['overdue_rate']:.1f}% of outstanding
- PAR30: {s['par30']:.1f}%, PAR60: {s['par60']:.1f}%, PAR90: {s['par90']:.1f}%
- Product Mix: {s['product_mix']}
- Avg Tenure: {s['avg_tenure']:.0f} weeks

DPD BUCKETS:
{[f"{b['label']}: {b['count']} loans ({b['pct']:.1f}%), {disp} {b['amount']/1e6:.2f}M" for b in d['buckets']]}

COLLECTION BY PRODUCT:
{[f"{p['product']}: {p['rate']:.1f}% collection rate, {p['deals']} deals" for p in c['by_product']]}
{commentary_ctx}
Write a concise portfolio commentary in 3 sections:
1. PORTFOLIO HEALTH (2-3 sentences) — overall collection and delinquency performance.
2. KEY OBSERVATIONS (3-4 bullets) — most important data points for an investment committee.
3. WATCH ITEMS (2-3 bullets) — areas that warrant monitoring. Be direct about concerns.

Professional tone, suitable for an investment committee memo. Be specific and data-driven."""
    else:
        df, sel  = _load(company, product, snapshot)
        df       = filter_by_date(df, as_of_date)
        config, disp = _currency(company, product, currency)
        mult     = apply_multiplier(config, disp)
        s        = compute_summary(df, config, disp, sel['date'], as_of_date)

        from core.analysis import add_month_column
        monthly  = add_month_column(df).groupby('Month').agg(
            purchase_value = ('Purchase value', 'sum'),
            collected      = ('Collected till date', 'sum'),
            denied         = ('Denied by insurance', 'sum'),
        ).reset_index().tail(6).to_dict(orient='records')

        prompt = f"""You are a senior analyst at ACP Private Credit, a private credit fund specializing in asset-backed lending.

You are analyzing the loan portfolio for {company.upper()} - {product.replace('_', ' ').title()}.
Data as of: {as_of_date or sel['date']}  |  Currency: {disp}

PORTFOLIO SNAPSHOT:
- Total Deals: {s['total_deals']:,}
- Purchase Value: {disp} {s['total_purchase_value']/1e6:.1f}M
- Total Collected: {disp} {s['total_collected']/1e6:.1f}M
- Collection Rate: {s['collection_rate']:.1f}%
- Denial Rate: {s['denial_rate']:.1f}%
- Pending Response: {disp} {s['total_pending']/1e6:.1f}M ({s['pending_rate']:.1f}% of portfolio)
- Deal Status: {s['status_breakdown']}

LAST 6 MONTHS ACTIVITY:
{monthly}

Write a concise portfolio commentary in 3 sections:
1. PORTFOLIO HEALTH (2-3 sentences) — overall collection performance and trends.
2. KEY OBSERVATIONS (3-4 bullets) — most important data points for an investment committee.
3. WATCH ITEMS (2-3 bullets) — areas that warrant monitoring. Be direct about concerns.

Professional tone, suitable for an investment committee memo. Be specific and data-driven."""

    msg = _ai_client().messages.create(
        model="claude-opus-4-6", max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    return {
        'commentary':   msg.content[0].text,
        'generated_at': datetime.now().isoformat(),
        'as_of_date':   as_of_date or sel.get('date', ''),
    }


# ── AI Executive Summary ─────────────────────────────────────────────────────

def _build_klaim_full_context(df, mult, as_of_date, config, disp, snapshot_date):
    """Build comprehensive analytics context from ALL Klaim compute functions."""
    from core.analysis import add_month_column
    sections = []

    # 1. Summary
    try:
        s = compute_summary(df, config, disp, snapshot_date, as_of_date)
        sections.append(f"PORTFOLIO SUMMARY: {s['total_deals']:,} deals, {disp} {s['total_purchase_value']/1e6:.1f}M originated, "
                       f"Collection Rate {s['collection_rate']:.1f}%, Denial Rate {s['denial_rate']:.1f}%, "
                       f"Pending {s['pending_rate']:.1f}%, Active {s['active_deals']}, Completed {s['completed_deals']}")
    except Exception:
        pass

    # 2. PAR (dual perspective)
    try:
        par = compute_par(df, mult, as_of_date)
        if par.get('available'):
            sections.append(f"PAR (Lifetime): 30+={par['lifetime_par30']:.2f}%, 60+={par['lifetime_par60']:.2f}%, 90+={par['lifetime_par90']:.2f}% "
                           f"| PAR (Active Outstanding): 30+={par['par30']:.1f}%, 60+={par['par60']:.1f}%, 90+={par['par90']:.1f}%")
    except Exception:
        pass

    # 3. DTFC
    try:
        dtfc = compute_dtfc(df, mult, as_of_date)
        if dtfc.get('available'):
            sections.append(f"DTFC: Median {dtfc['median_dtfc']:.0f}d, P90 {dtfc['p90_dtfc']:.0f}d ({dtfc['method']})")
    except Exception:
        pass

    # 4. DSO
    try:
        dso = compute_dso(df, mult, as_of_date)
        if dso.get('available'):
            sections.append(f"DSO: Weighted {dso['weighted_dso']:.0f}d, Median {dso['median_dso']:.0f}d, P95 {dso['p95_dso']:.0f}d")
    except Exception:
        pass

    # 5. Collection velocity
    try:
        cv = compute_collection_velocity(df, mult, as_of_date)
        recent = cv['monthly'][-3:] if cv.get('monthly') else []
        if recent:
            rates = ', '.join([f"{m.get('Month','?')}: {m.get('rate',0):.1f}%" for m in recent])
            sections.append(f"COLLECTION VELOCITY (last 3M): {rates} | Avg days to collect: {cv.get('avg_days',0):.0f}")
    except Exception:
        pass

    # 6. Denial trend
    try:
        dt = compute_denial_trend(df, mult)
        recent = dt[-3:] if dt else []
        if recent:
            rates = ', '.join([f"{m.get('Month','?')}: {m.get('denial_rate',0):.1f}%" for m in recent])
            sections.append(f"DENIAL TREND (last 3M): {rates}")
    except Exception:
        pass

    # 7. Ageing
    try:
        ag = compute_ageing(df, mult, as_of_date)
        health = {h['status']: h for h in ag.get('health_summary', [])}
        sections.append(f"AGEING: Outstanding {disp} {ag.get('total_outstanding',0)/1e6:.1f}M | "
                       f"Healthy {health.get('Healthy',{}).get('percentage',0):.0f}%, "
                       f"Watch {health.get('Watch',{}).get('percentage',0):.0f}%, "
                       f"Delayed {health.get('Delayed',{}).get('percentage',0):.0f}%, "
                       f"Poor {health.get('Poor',{}).get('percentage',0):.0f}%")
    except Exception:
        pass

    # 8. Concentration
    try:
        conc = compute_concentration(df, mult)
        hhi = conc.get('hhi', {})
        top_groups = conc.get('group', [])[:3]
        top_str = ', '.join([f"{g.get('Group','?')} ({g.get('share',0):.1f}%)" for g in top_groups])
        sections.append(f"CONCENTRATION: HHI={hhi.get('hhi',0):.4f} ({hhi.get('label','?')}), Top groups: {top_str}")
    except Exception:
        pass

    # 9. Returns
    try:
        ret = compute_returns_analysis(df, mult)
        rs = ret.get('summary', {})
        sections.append(f"RETURNS: Realised Margin {rs.get('realised_margin',0):.2f}%, "
                       f"Capital Recovery {rs.get('capital_recovery',0):.2f}%, "
                       f"Avg Discount {rs.get('avg_discount',0):.2f}%")
    except Exception:
        pass

    # 10. Expected Loss
    try:
        el = compute_expected_loss(df, mult)
        p = el.get('portfolio', {})
        sections.append(f"EXPECTED LOSS MODEL: PD={p.get('pd',0):.2f}%, LGD={p.get('lgd',0):.2f}%, "
                       f"EL Rate={p.get('el_rate',0):.4f}%")
    except Exception:
        pass

    # 11. Stress test
    try:
        st = compute_stress_test(df, mult)
        scenarios = st.get('scenarios', [])
        if scenarios:
            worst = scenarios[-1]
            sections.append(f"STRESS TEST: Worst scenario ({worst.get('scenario','')}): "
                           f"collection drops to {worst.get('stressed_rate',0):.1f}%")
    except Exception:
        pass

    # 12. Cohort loss waterfall
    try:
        clw = compute_cohort_loss_waterfall(df, mult)
        totals = clw.get('totals', {})
        sections.append(f"LOSS WATERFALL: Default rate {totals.get('default_rate',0):.2f}%, "
                       f"Recovery rate {totals.get('recovery_rate',0):.2f}%, "
                       f"Net loss rate {totals.get('net_loss_rate',0):.2f}%")
    except Exception:
        pass

    # 13. Recovery analysis
    try:
        ra = compute_recovery_analysis(df, mult)
        sections.append(f"RECOVERY: Portfolio recovery rate {ra.get('portfolio_recovery_rate',0):.1f}%")
    except Exception:
        pass

    # 14. Underwriting drift
    try:
        ud = compute_underwriting_drift(df, mult, as_of_date)
        flagged = [v for v in ud.get('vintages', []) if v.get('flags')]
        if flagged:
            sections.append(f"UNDERWRITING DRIFT: {len(flagged)} vintages flagged with drift out of {len(ud.get('vintages',[]))}")
        else:
            sections.append(f"UNDERWRITING DRIFT: No vintages flagged — origination quality stable")
    except Exception:
        pass

    # 15. Seasonality
    try:
        sn = compute_seasonality(df, mult)
        idx = sn.get('seasonal_index', [])
        if idx:
            peak = max(idx, key=lambda x: x.get('index', 0))
            trough = min(idx, key=lambda x: x.get('index', 0))
            sections.append(f"SEASONALITY: Peak month={peak.get('month','?')} (index {peak.get('index',0):.2f}), "
                           f"Trough month={trough.get('month','?')} (index {trough.get('index',0):.2f})")
    except Exception:
        pass

    # 16. Segment analysis
    try:
        sa = compute_segment_analysis(df, mult)
        dims = sa.get('dimensions', [])
        sections.append(f"SEGMENTS: Available dimensions: {', '.join(dims)}")
    except Exception:
        pass

    # 17. HHI time series (load all snapshots)
    try:
        hhi_ts = compute_hhi_for_snapshot(df, mult)
        sections.append(f"HHI (current snapshot): {hhi_ts.get('hhi',0):.4f}")
    except Exception:
        pass

    # 18. Group performance
    try:
        gp = compute_group_performance(df, mult)
        top3 = gp[:3] if gp else []
        if top3:
            top_str = ', '.join([f"{g.get('Group','?')}: coll={g.get('collection_rate',0):.1f}% den={g.get('denial_rate',0):.1f}%" for g in top3])
            sections.append(f"TOP PROVIDERS: {top_str}")
    except Exception:
        pass

    # 19. Cohorts (recent)
    try:
        cohorts = compute_cohorts(df, mult)
        recent = cohorts[-3:] if cohorts else []
        if recent:
            coh_str = ', '.join([f"{c.get('month','?')}: {c.get('deals',0)} deals, coll={c.get('collection_rate',0):.1f}%" for c in recent])
            sections.append(f"RECENT COHORTS: {coh_str}")
    except Exception:
        pass

    # 20. Loss categorization
    try:
        lc = compute_loss_categorization(df, mult)
        cats = lc.get('categories', [])
        if cats:
            cat_str = ', '.join([f"{c.get('category','?')}: {c.get('pct',0):.0f}%" for c in cats])
            sections.append(f"LOSS CATEGORIES: {cat_str}")
    except Exception:
        pass

    return '\n'.join(sections)


def _build_silq_full_context(df, mult, ref_date, config, disp):
    """Build comprehensive analytics context from ALL SILQ compute functions."""
    sections = []

    try:
        s = compute_silq_summary(df, mult, ref_date=ref_date)
        sections.append(f"PORTFOLIO: {s['total_deals']:,} loans, {disp} {s['total_disbursed']/1e6:.1f}M disbursed, "
                       f"Outstanding {disp} {s['total_outstanding']/1e6:.1f}M, "
                       f"Collection {s['collection_rate']:.1f}%, Overdue {s['overdue_rate']:.1f}%, "
                       f"PAR30={s['par30']:.1f}%, PAR60={s['par60']:.1f}%, PAR90={s['par90']:.1f}%")
    except Exception:
        pass

    try:
        d = compute_silq_delinquency(df, mult, ref_date=ref_date)
        buckets = d.get('buckets', [])
        if buckets:
            bk_str = ', '.join([f"{b['label']}: {b['count']} ({b['pct']:.1f}%)" for b in buckets])
            sections.append(f"DPD BUCKETS: {bk_str}")
        top_shops = d.get('top_overdue_shops', [])[:3]
        if top_shops:
            sh_str = ', '.join([f"{s.get('shop','?')}: {disp} {s.get('overdue',0)/1e3:.0f}K" for s in top_shops])
            sections.append(f"TOP OVERDUE SHOPS: {sh_str}")
    except Exception:
        pass

    try:
        c = compute_silq_collections(df, mult)
        bp = c.get('by_product', [])
        if bp:
            bp_str = ', '.join([f"{p['product']}: {p['rate']:.1f}%" for p in bp])
            sections.append(f"COLLECTIONS BY PRODUCT: {bp_str}")
    except Exception:
        pass

    try:
        conc = compute_silq_concentration(df, mult)
        top_shops = conc.get('shops', [])[:3]
        shop_strs = [f"{s.get('shop','?')} ({s.get('share',0):.1f}%)" for s in top_shops]
        sections.append(f"CONCENTRATION: HHI={conc.get('hhi',0):.4f}, Top shops: {', '.join(shop_strs)}")
    except Exception:
        pass

    try:
        coh = compute_silq_cohorts(df, mult, ref_date=ref_date)
        recent = coh[-3:] if isinstance(coh, list) else coh.get('cohorts', [])[-3:]
        if recent:
            coh_str = ', '.join([f"{c.get('month','?')}: {c.get('loans',0)} loans, coll={c.get('collection_rate',0):.1f}%" for c in recent])
            sections.append(f"RECENT COHORTS: {coh_str}")
    except Exception:
        pass

    try:
        y = compute_silq_yield(df, mult)
        bp = y.get('by_product', [])
        if bp:
            bp_str = ', '.join([f"{p.get('product','?')}: margin={p.get('margin',0):.1f}%" for p in bp])
            sections.append(f"YIELD BY PRODUCT: {bp_str}")
    except Exception:
        pass

    try:
        t = compute_silq_tenure(df, mult, ref_date=ref_date)
        bands = t.get('tenure_bands', [])
        if bands:
            tb_str = ', '.join([f"{b.get('band','?')}: {b.get('count',0)} loans" for b in bands[:4]])
            sections.append(f"TENURE DISTRIBUTION: {tb_str}")
    except Exception:
        pass

    return '\n'.join(sections)


@app.get("/companies/{company}/products/{product}/ai-executive-summary")
def get_executive_summary(company: str, product: str,
                          snapshot: Optional[str] = None,
                          as_of_date: Optional[str] = None,
                          currency: Optional[str] = None):
    """AI Executive Summary — holistic analysis of ALL computed metrics.

    Returns top 5-10 findings ranked by business impact with severity levels.
    """
    at = _get_analysis_type(company, product)

    if at == 'ejari_summary':
        return {'findings': [], 'message': 'Executive summary not available for read-only summary data.'}

    if at == 'silq':
        df, sel, config, disp, mult, _, ref_date = _silq_load(company, product, snapshot, as_of_date, currency)
        context = _build_silq_full_context(df, mult, ref_date, config, disp)
        company_desc = "SILQ POS lending portfolio (BNPL, RBF, RCL) in KSA"
        n_metrics = len([l for l in context.split('\n') if l.strip()])
    else:
        df, sel = _load(company, product, snapshot)
        df = filter_by_date(df, as_of_date)
        config, disp = _currency(company, product, currency)
        mult = apply_multiplier(config, disp)
        context = _build_klaim_full_context(df, mult, as_of_date or sel['date'], config, disp, sel['date'])
        company_desc = f"{company.upper()} healthcare claims factoring portfolio in UAE"
        n_metrics = len([l for l in context.split('\n') if l.strip()])

    prompt = f"""You are a senior analyst at ACP Private Credit preparing an executive summary for the investment committee.

Company: {company_desc}
Data as of: {as_of_date or sel.get('date', '')}  |  Currency: {disp if 'disp' in dir() else 'N/A'}

COMPREHENSIVE ANALYTICS ({n_metrics} sections):
{context}

Based on ALL the data above, identify the TOP 5-10 MOST IMPORTANT FINDINGS for the investment committee. Rank by business impact.

For each finding, respond in this exact JSON format:
[
  {{
    "rank": 1,
    "severity": "critical" or "warning" or "positive",
    "title": "Short title (max 10 words)",
    "explanation": "2-3 sentences explaining why this matters and what action to take.",
    "data_points": ["Key number 1", "Key number 2"],
    "tab": "relevant-tab-slug"
  }}
]

Rules:
- "critical": immediate IC attention needed (deteriorating metrics, covenant risk, concentration breaches)
- "warning": should be monitored (emerging trends, drift signals)
- "positive": good news worth highlighting (improving metrics, strong performance)
- Tab slugs: overview, actual-vs-expected, deployment, collection, denial-trend, ageing, revenue, portfolio-tab, cohort-analysis, returns, risk-migration, loss-waterfall, recovery-analysis, underwriting-drift, segment-analysis, seasonality
- For SILQ tabs: overview, delinquency, collections, concentration, cohort-analysis, yield-margins, tenure, covenants
- Be specific with numbers. No vague statements.
- Return ONLY the JSON array, no other text."""

    msg = _ai_client().messages.create(
        model="claude-opus-4-6", max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    # Parse the JSON response
    response_text = msg.content[0].text.strip()
    # Handle potential markdown code block wrapping
    if response_text.startswith('```'):
        response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
        response_text = re.sub(r'\s*```$', '', response_text)

    try:
        findings = json.loads(response_text)
    except json.JSONDecodeError:
        findings = [{'rank': 1, 'severity': 'warning', 'title': 'Summary generated',
                     'explanation': response_text, 'data_points': [], 'tab': 'overview'}]

    return {
        'findings': findings,
        'generated_at': datetime.now().isoformat(),
        'as_of_date': as_of_date or sel.get('date', ''),
        'context_coverage': n_metrics,
    }


@app.get("/companies/{company}/products/{product}/ai-tab-insight")
def get_tab_insight(company: str, product: str,
                    tab: str,
                    snapshot: Optional[str] = None,
                    as_of_date: Optional[str] = None,
                    currency: Optional[str] = None):
    """Generate a short AI insight for a specific dashboard tab."""
    at = _get_analysis_type(company, product)

    if at == 'silq':
        df, sel, config, disp, mult, _, ref_date = _silq_load(company, product, snapshot, as_of_date, currency)
    else:
        df, sel  = _load(company, product, snapshot)
        df       = filter_by_date(df, as_of_date)
        config, disp = _currency(company, product, currency)
        mult     = apply_multiplier(config, disp)
        ref_date = None

    # Build tab-specific data context
    tab_data = {}
    if at == 'silq':
        if tab == 'delinquency':
            tab_data = compute_silq_delinquency(df, mult, ref_date=ref_date)
        elif tab == 'collections':
            tab_data = compute_silq_collections(df, mult)
        elif tab == 'concentration':
            conc = compute_silq_concentration(df, mult)
            tab_data = {'top_shops': conc['shops'][:5], 'hhi': conc['hhi'], 'product_mix': conc['product_mix']}
        elif tab == 'cohort':
            tab_data = compute_silq_cohorts(df, mult, ref_date=ref_date)
        elif tab == 'yield-margins':
            tab_data = compute_silq_yield(df, mult)
        elif tab == 'tenure':
            tab_data = compute_silq_tenure(df, mult, ref_date=ref_date)
    else:
        if tab == 'deployment':
            tab_data = {'monthly_deployment': compute_deployment(df, mult)[-12:]}
        elif tab == 'collection':
            cv = compute_collection_velocity(df, mult, as_of_date)
            tab_data = {'buckets': cv['buckets'], 'recent_monthly': cv['monthly'][-12:]}
        elif tab == 'denial-trend':
            tab_data = {'denial_trend': compute_denial_trend(df, mult)[-12:]}
        elif tab == 'ageing':
            ag = compute_ageing(df, mult, as_of_date)
            tab_data = {'health_summary': ag['health_summary'], 'ageing_buckets': ag['ageing_buckets']}
        elif tab == 'revenue':
            rev = compute_revenue(df, mult)
            tab_data = {'totals': rev['totals'], 'recent_monthly': rev['monthly'][-12:]}
        elif tab == 'concentration':
            conc = compute_concentration(df, mult)
            tab_data = {'top_groups': conc.get('group', [])[:5], 'top_deals': conc.get('top_deals', [])[:5]}
        elif tab == 'cohort':
            tab_data = {'cohorts': compute_cohorts(df, mult)[-12:]}
        elif tab == 'actual-vs-expected':
            ave = compute_actual_vs_expected(df, mult)
            tab_data = {'overall_performance': ave['overall_performance'],
                        'total_collected': ave['total_collected'],
                        'total_expected': ave['total_expected'],
                        'recent': ave['data'][-6:]}
        elif tab == 'returns':
            ret = compute_returns_analysis(df, mult)
            tab_data = {'summary': ret['summary'], 'recent_monthly': ret['monthly'][-12:]}
        elif tab == 'risk-migration':
            el = compute_expected_loss(df, mult)
            st = compute_stress_test(df, mult)
            tab_data = {'expected_loss': el['portfolio'], 'stress_scenarios': st['scenarios']}

    tab_labels = {
        'deployment':          'Capital Deployment',
        'collection':          'Collection Velocity',
        'collection-velocity': 'Collection Velocity',
        'denial-trend':        'Denial Rate Trend',
        'ageing':              'Portfolio Ageing & Health',
        'revenue':             'Revenue Analysis',
        'concentration':       'Portfolio Concentration',
        'cohort':              'Cohort Analysis',
        'actual-vs-expected':  'Actual vs Expected',
        'returns':             'Returns Analysis',
        'risk-migration':      'Risk & Migration Analysis',
        'delinquency':         'Delinquency Analysis',
        'collections':         'Collections Analysis',
        'yield-margins':       'Yield & Margins',
        'tenure':              'Tenure Analysis',
    }

    prompt = f"""You are a senior credit analyst at ACP Private Credit reviewing the {tab_labels.get(tab, tab)} view for {company.upper()} ({product.replace('_', ' ').title()}) as of {as_of_date or sel['date']}.

DATA:
{tab_data}

Write 2-3 sentences of sharp, data-driven insight specifically about what this view shows. 
Call out the single most important trend or concern visible in this data.
Be direct and specific — no generic commentary. No headers, just prose."""

    msg = _ai_client().messages.create(
        model="claude-opus-4-6", max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    return {'insight': msg.content[0].text, 'tab': tab}

@app.post("/companies/{company}/products/{product}/chat")
def chat_with_data(company: str, product: str, request: dict,
                   snapshot: Optional[str] = None,
                   as_of_date: Optional[str] = None,
                   currency: Optional[str] = None):
    # Allow snapshot/currency from body (frontend sends them there) or query params
    snap = snapshot or request.get('snapshot')
    cur  = currency or request.get('currency')
    aod  = as_of_date or request.get('as_of_date')
    at = _get_analysis_type(company, product)

    if at == 'silq':
        return _silq_chat(company, product, request, snap, aod, cur)

    df, sel  = _load(company, product, snap)
    df       = filter_by_date(df, aod)
    config, disp = _currency(company, product, cur)
    mult     = apply_multiplier(config, disp)
    s        = compute_summary(df, config, disp, sel['date'], aod)

    from core.analysis import add_month_column
    monthly  = add_month_column(df).groupby('Month').agg(
        purchase_value = ('Purchase value', 'sum'),
        collected      = ('Collected till date', 'sum'),
        denied         = ('Denied by insurance', 'sum'),
        deal_count     = ('Purchase value', 'count'),
    ).reset_index()
    monthly['collection_rate'] = (monthly['collected'] / monthly['purchase_value'] * 100).round(1)
    monthly['denial_rate']     = (monthly['denied']    / monthly['purchase_value'] * 100).round(1)

    # ── Enriched context sections (each wrapped so failures are silently skipped) ──

    group_perf_ctx = ""
    try:
        gp = compute_group_performance(df, mult, aod)
        top_groups = gp['groups'][:8]
        rows = []
        for g in top_groups:
            rows.append(f"  {g['group']}: {g['deal_count']} deals, "
                        f"coll {g['collection_rate']}%, denial {g['denial_rate']}%, "
                        f"DSO {g['dso']:.0f}d")
        if rows:
            group_perf_ctx = "\nGROUP PERFORMANCE (top 8 providers):\n" + "\n".join(rows)
    except Exception:
        pass

    ageing_ctx = ""
    try:
        ag = compute_ageing(df, mult, aod)
        health = {h['status']: f"{h['percentage']}% ({h['deal_count']})" for h in ag['health_summary']}
        ageing_ctx = (f"\nACTIVE PORTFOLIO HEALTH ({ag['total_active_deals']} active deals):\n"
                      f"  {', '.join(f'{k}: {v}' for k, v in health.items())}")
    except Exception:
        pass

    dso_ctx = ""
    try:
        dso = compute_dso(df, mult, aod)
        dso_ctx = (f"\nDSO (Days Sales Outstanding, completed deals):\n"
                   f"  Weighted avg: {dso['weighted_dso']:.0f} days, "
                   f"Median: {dso['median_dso']:.0f} days, "
                   f"P95: {dso['p95_dso']:.0f} days")
    except Exception:
        pass

    # compute_returns_analysis mutates df, so pass a copy
    ret = None
    try:
        ret = compute_returns_analysis(df.copy(), mult)
    except Exception:
        pass

    returns_ctx = ""
    if ret:
        try:
            rs = ret['summary']
            returns_ctx = (f"\nRETURNS & MARGINS:\n"
                           f"  Avg discount: {rs['avg_discount']:.1f}%, "
                           f"Wgt avg discount: {rs['weighted_avg_discount']:.1f}%\n"
                           f"  Expected margin: {rs['expected_margin']:.1f}%, "
                           f"Realised margin: {rs['realised_margin']:.1f}%, "
                           f"Completed margin: {rs['completed_margin']:.1f}%\n"
                           f"  Fee yield: {rs['fee_yield']:.2f}%, "
                           f"Completed loss rate: {rs['completed_loss_rate']:.1f}%")
        except Exception:
            pass

    discount_ctx = ""
    if ret and ret.get('discount_bands'):
        try:
            band_rows = []
            for b in ret['discount_bands']:
                band_rows.append(f"  {b['band']}: {b['deals']} deals, "
                                 f"coll {b['collection_rate']}%, "
                                 f"denial {b['denial_rate']}%, "
                                 f"margin {b['margin']:.1f}%")
            discount_ctx = "\nDISCOUNT BAND PERFORMANCE:\n" + "\n".join(band_rows)
        except Exception:
            pass

    new_repeat_ctx = ""
    if ret and ret.get('new_vs_repeat'):
        try:
            nr_rows = []
            for seg in ret['new_vs_repeat']:
                nr_rows.append(f"  {seg['type']}: {seg['deals']} deals, "
                               f"coll {seg['collection_rate']}%, "
                               f"denial {seg['denial_rate']}%, "
                               f"margin {seg['margin']:.1f}%")
            new_repeat_ctx = "\nNEW vs REPEAT BUSINESS:\n" + "\n".join(nr_rows)
        except Exception:
            pass

    hhi_ctx = ""
    try:
        hhi = compute_hhi(df, mult)
        parts = []
        for key in ['group', 'product']:
            if key in hhi:
                h = hhi[key]
                label = 'Provider' if key == 'group' else 'Product'
                parts.append(f"  {label}: HHI={h['hhi']:.4f}, "
                             f"Top1={h['top_1_pct']}%, Top5={h['top_5_pct']}% "
                             f"({h['count']} unique)")
        if parts:
            hhi_ctx = "\nCONCENTRATION (HHI):\n" + "\n".join(parts)
    except Exception:
        pass

    # ── New enrichment sections (collection curves, IRR, owner) ──

    irr_ctx = ""
    if ret and ret['summary'].get('has_irr'):
        try:
            rs = ret['summary']
            irr_ctx = (f"\nIRR ANALYSIS:\n"
                       f"  Avg Expected IRR: {rs['avg_expected_irr']:.1f}%, "
                       f"Avg Actual IRR: {rs['avg_actual_irr']:.1f}%\n"
                       f"  IRR Spread: {rs['irr_spread']:+.1f}%, "
                       f"Median Actual IRR: {rs['median_actual_irr']:.1f}%")
        except Exception:
            pass

    collection_speed_ctx = ""
    try:
        curves = compute_collection_curves(df, mult)
        if curves.get('available'):
            agg = curves['aggregate']['points']
            speed_rows = []
            for pt in agg:
                if pt['days'] in [90, 180, 360]:
                    speed_rows.append(f"  {pt['days']}d: Expected {pt['expected_pct']:.1f}%, "
                                      f"Actual {pt['actual_pct']:.1f}%, "
                                      f"Accuracy {pt['accuracy']:.0f}%")
            if speed_rows:
                collection_speed_ctx = "\nCOLLECTION SPEED (% of PV collected by interval):\n" + "\n".join(speed_rows)
    except Exception:
        pass

    owner_ctx = ""
    try:
        owner_data = compute_owner_breakdown(df, mult)
        if owner_data.get('available'):
            owner_rows = []
            for o in owner_data['owners']:
                owner_rows.append(f"  {o['owner']}: {o['deal_count']} deals, "
                                  f"{o['percentage']:.1f}% of portfolio, "
                                  f"coll {o['collection_rate']:.1f}%, "
                                  f"denial {o['denial_rate']:.1f}%")
            if owner_rows:
                owner_ctx = "\nOWNER/SPV BREAKDOWN:\n" + "\n".join(owner_rows)
    except Exception:
        pass

    system = f"""You are an expert credit analyst assistant for ACP Private Credit,
analyzing the {company.upper()} - {product.replace('_', ' ').title()} loan portfolio.

PORTFOLIO SUMMARY (as of {aod or sel['date']}, currency: {disp}):
- Total Deals: {s['total_deals']:,} ({s['active_deals']} active, {s['completed_deals']} completed)
- Purchase Value: {disp} {s['total_purchase_value']/1e6:.2f}M
- Collection Rate: {s['collection_rate']:.1f}%
- Denial Rate: {s['denial_rate']:.1f}%
- Pending Response: {disp} {s['total_pending']/1e6:.2f}M ({s['pending_rate']:.1f}%)

MONTHLY PERFORMANCE (last 12 months):
{monthly.tail(12).to_string(index=False)}
{group_perf_ctx}{ageing_ctx}{dso_ctx}{returns_ctx}{discount_ctx}{new_repeat_ctx}{hhi_ctx}{irr_ctx}{collection_speed_ctx}{owner_ctx}

INSTRUCTIONS:
- Answer questions precisely with specific numbers from the data above. Be concise but thorough.
- When a question requires deal-level detail, individual deal lookups, or data not available in your context, provide the best answer you can from what is available and note that for more granular detail the analyst should consult the full loan tape or reach out to the deal team.
- Do not fabricate numbers. If a metric is not in your context, say so."""

    msgs = [{"role": ("assistant" if h.get('role') == 'ai' else h.get('role', 'user')),
             "content": h.get('content') or h.get('text', '')}
            for h in request.get('history', [])[-6:]]
    msgs.append({"role": "user", "content": request.get('question', '')})

    resp = _ai_client().messages.create(
        model="claude-opus-4-6", max_tokens=1000,
        system=system, messages=msgs
    )
    return {'answer': resp.content[0].text, 'question': request.get('question', '')}


def _silq_chat(company, product, request, snap, aod, cur):
    """SILQ-specific data chat with enriched context."""
    df, sel, config, disp, mult, commentary_text, ref_date = _silq_load(company, product, snap, aod, cur)
    s = compute_silq_summary(df, mult, ref_date=ref_date)
    d = compute_silq_delinquency(df, mult, ref_date=ref_date)
    c = compute_silq_collections(df, mult)
    conc = compute_silq_concentration(df, mult)
    y = compute_silq_yield(df, mult)
    t = compute_silq_tenure(df, mult)

    commentary_ctx = ''
    if commentary_text:
        commentary_ctx = f"\nANALYST PORTFOLIO COMMENTARY (from tape):\n{commentary_text}\n"

    system = f"""You are an expert credit analyst assistant for ACP Private Credit,
analyzing the SILQ POS lending portfolio (BNPL, RBF & RCL loans) in KSA.

PORTFOLIO SUMMARY (as of {aod or sel['date']}, currency: {disp}):
- Total Loans: {s['total_deals']:,} ({s['active_deals']} active, {s['completed_deals']} closed)
- Total Disbursed: {disp} {s['total_disbursed']/1e6:.2f}M
- Outstanding: {disp} {s['total_outstanding']/1e6:.2f}M
- Total Overdue: {disp} {s['total_overdue']/1e6:.2f}M
- Collection Rate: {s['collection_rate']:.1f}%
- PAR30: {s['par30']:.1f}%, PAR60: {s['par60']:.1f}%, PAR90: {s['par90']:.1f}%
- Product Mix: {s['product_mix']}
- Avg Tenure: {s['avg_tenure']:.0f} weeks

DPD BUCKETS:
{chr(10).join(f"  {b['label']}: {b['count']} loans ({b['pct']:.1f}%), {disp} {b['amount']/1e6:.2f}M" for b in d['buckets'])}

COLLECTION BY PRODUCT:
{chr(10).join(f"  {p['product']}: {p['rate']:.1f}% rate, {p['deals']} deals, {disp} {p['repaid']/1e6:.2f}M repaid" for p in c['by_product'])}

TOP SHOPS BY DISBURSEMENT:
{chr(10).join(f"  Shop {sh['shop_id']}: {sh['share']:.1f}% share, {sh['deals']} deals" for sh in conc['shops'][:8])}

SHOP CONCENTRATION: HHI = {conc['hhi']:.4f}

YIELD & MARGINS:
  Portfolio margin rate: {y['margin_rate']:.2f}%
  Realised margin (closed only): {y['realised_margin_rate']:.2f}%
  By product: {[f"{p['product']}: {p['margin_rate']:.2f}%" for p in y['by_product']]}

TENURE ANALYSIS:
  Avg: {t['avg_tenure']:.0f} weeks, Median: {t['median_tenure']:.0f} weeks
  By product: {[f"{p['product']}: avg {p['avg_tenure']:.0f}w" for p in t['by_product']]}
{commentary_ctx}
INSTRUCTIONS:
- Answer questions precisely with specific numbers from the data above. Be concise but thorough.
- When a question requires deal-level detail or data not in your context, provide the best answer you can and note limitations.
- Do not fabricate numbers. If a metric is not in your context, say so."""

    msgs = [{
        "role": ("assistant" if h.get('role') == 'ai' else h.get('role', 'user')),
        "content": h.get('content') or h.get('text', '')
    } for h in request.get('history', [])[-6:]]
    msgs.append({"role": "user", "content": request.get('question', '')})

    resp = _ai_client().messages.create(
        model="claude-opus-4-6", max_tokens=1000,
        system=system, messages=msgs
    )
    return {'answer': resp.content[0].text, 'question': request.get('question', '')}
# ── Portfolio Analytics endpoints ─────────────────────────────────────────────

def _facility_params_path(company, product):
    """Path to stored facility parameters JSON."""
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..',
        'data', company, product, 'facility_params.json'
    )

def _load_facility_params(company, product):
    """Load saved facility params or return empty dict."""
    path = _facility_params_path(company, product)
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {}

def _portfolio_load(company, product, snapshot, as_of_date, currency, db=None):
    """Load data for portfolio computation. Tries DB first, falls back to tape.

    When DB has invoices for this company/product, loads from database.
    Otherwise loads from tape file (CSV/Excel) as before.
    """
    config = load_config(company, product)
    analysis_type = config.get('analysis_type', '') if config else ''
    disp = currency or (config['currency'] if config else 'USD')
    mult = apply_multiplier(config, disp)

    # Try database first
    if db and has_db_data(db, company, product):
        df = load_from_db(db, company, product)
        sel = {'date': datetime.now().strftime('%Y-%m-%d'), 'filename': 'database', 'source': 'database'}
        ref_date = as_of_date or sel['date']
        # Merge DB facility config with file-based params
        facility_params = _load_facility_params(company, product)
        facility_params.update(db_facility_config(db, company, product))
    else:
        # Fall back to tape file
        snaps = get_snapshots(company, product)
        if not snaps:
            raise HTTPException(status_code=404, detail="No snapshots found")
        sel = next((s for s in snaps if s['filename'] == snapshot or s['date'] == snapshot), snaps[-1])

        if analysis_type == 'silq':
            df, _ = load_silq_snapshot(sel['filepath'])
            if as_of_date:
                df = filter_silq_by_date(df, as_of_date)
        else:
            df = load_snapshot(sel['filepath'])
            if as_of_date:
                df = filter_by_date(df, as_of_date)

        ref_date = as_of_date or sel['date']
        facility_params = _load_facility_params(company, product)

    if config and 'usd_rate' in config:
        facility_params.setdefault('usd_rate', config['usd_rate'])

    return df, sel, config, disp, mult, ref_date, facility_params, analysis_type


@app.get("/companies/{company}/products/{product}/portfolio/borrowing-base")
def get_portfolio_borrowing_base(company: str, product: str,
                                  snapshot: Optional[str] = None,
                                  as_of_date: Optional[str] = None,
                                  currency: Optional[str] = None,
                                  db: Session = Depends(get_db)):
    df, sel, config, disp, mult, ref_date, fp, atype = _portfolio_load(
        company, product, snapshot, as_of_date, currency, db=db)
    if atype == 'silq':
        result = portfolio_borrowing_base(df, mult, ref_date, fp)
    else:
        result = compute_klaim_borrowing_base(df, mult, ref_date, fp)
    return {**result, 'currency': disp, 'snapshot': sel['date']}


@app.get("/companies/{company}/products/{product}/portfolio/concentration-limits")
def get_portfolio_concentration_limits(company: str, product: str,
                                        snapshot: Optional[str] = None,
                                        as_of_date: Optional[str] = None,
                                        currency: Optional[str] = None,
                                        db: Session = Depends(get_db)):
    df, sel, config, disp, mult, ref_date, fp, atype = _portfolio_load(
        company, product, snapshot, as_of_date, currency, db=db)
    if atype == 'silq':
        result = portfolio_concentration_limits(df, mult, ref_date, fp)
    else:
        result = compute_klaim_concentration_limits(df, mult, ref_date, fp)
    return {**result, 'currency': disp, 'snapshot': sel['date']}


@app.get("/companies/{company}/products/{product}/portfolio/covenants")
def get_portfolio_covenants(company: str, product: str,
                             snapshot: Optional[str] = None,
                             as_of_date: Optional[str] = None,
                             currency: Optional[str] = None,
                             db: Session = Depends(get_db)):
    df, sel, config, disp, mult, ref_date, fp, atype = _portfolio_load(
        company, product, snapshot, as_of_date, currency, db=db)
    if atype == 'silq':
        result = portfolio_covenants(df, mult, ref_date, fp)
    else:
        result = compute_klaim_covenants(df, mult, ref_date, fp)
    return {**result, 'currency': disp, 'snapshot': sel['date']}


@app.get("/companies/{company}/products/{product}/portfolio/flow")
def get_portfolio_flow(company: str, product: str,
                        snapshot: Optional[str] = None,
                        as_of_date: Optional[str] = None,
                        currency: Optional[str] = None,
                        db: Session = Depends(get_db)):
    df, sel, config, disp, mult, ref_date, fp, atype = _portfolio_load(
        company, product, snapshot, as_of_date, currency, db=db)
    result = compute_portfolio_flow(df, mult)
    return {**result, 'currency': disp, 'snapshot': sel['date']}


@app.get("/companies/{company}/products/{product}/portfolio/facility-params")
def get_facility_params(company: str, product: str):
    return _load_facility_params(company, product)


@app.post("/companies/{company}/products/{product}/portfolio/facility-params")
def save_facility_params(company: str, product: str, request: dict):
    """Save facility parameters (facility_limit, facility_drawn, cash_balance, etc.)."""
    allowed_keys = {
        'facility_limit', 'facility_drawn', 'cash_balance',
        'equity_injection', 'advance_rate',
        'advance_rates_by_product', 'advance_rates_by_region',
        'approved_recipients',
        'single_payer_limit', 'wal_threshold_days',
        'net_cash_burn', 'net_cash_burn_3m_avg',
    }
    params = {k: v for k, v in request.items() if k in allowed_keys}
    params['updated_at'] = datetime.now().isoformat()

    path = _facility_params_path(company, product)
    with open(path, 'w') as f:
        json.dump(params, f, indent=2)

    return {'saved': True, 'params': params}


# ── Portfolio Dashboard Data endpoints ───────────────────────────────────────

@app.get("/companies/{company}/products/{product}/portfolio/invoices")
def get_portfolio_invoices(company: str, product: str,
                           page: int = 1, per_page: int = 50,
                           status: Optional[str] = None,
                           eligible: Optional[str] = None,
                           db: Session = Depends(get_db)):
    """List invoices for dashboard view with eligibility info."""
    from core.models import Invoice, Payment, Product, Organization
    from sqlalchemy import func as sqfunc

    if db is None:
        return {'invoices': [], 'total': 0, 'page': page, 'per_page': per_page}

    # Find product
    prod = (db.query(Product).join(Organization)
            .filter(Organization.name == company, Product.name == product).first())
    if not prod:
        return {'invoices': [], 'total': 0, 'page': page, 'per_page': per_page}

    q = db.query(Invoice).filter(Invoice.product_id == prod.id)
    if status:
        q = q.filter(Invoice.status == status.lower())

    total = q.count()
    rows = q.order_by(Invoice.invoice_date.desc()).offset((page - 1) * per_page).limit(per_page).all()

    invoices = []
    today = datetime.now().date()
    for inv in rows:
        # Compute collected amount
        collected = db.query(sqfunc.coalesce(sqfunc.sum(Payment.payment_amount), 0)).filter(
            Payment.invoice_id == inv.id).scalar()

        # Simple eligibility: not past due >90 days, status not denied
        days_overdue = (today - inv.due_date).days if inv.due_date and inv.due_date < today else 0
        is_eligible = inv.status not in ('paid', 'denied') and days_overdue <= 90
        ineligible_reason = None
        if not is_eligible:
            if inv.status in ('paid', 'denied'):
                ineligible_reason = f'Status: {inv.status}'
            elif days_overdue > 90:
                ineligible_reason = f'Past due: {days_overdue} days'

        invoices.append({
            'id': str(inv.id),
            'invoice_number': inv.invoice_number,
            'customer_name': inv.customer_name,
            'payer_name': inv.payer_name,
            'amount_due': float(inv.amount_due),
            'collected': float(collected),
            'currency': inv.currency,
            'status': inv.status,
            'invoice_date': str(inv.invoice_date) if inv.invoice_date else None,
            'due_date': str(inv.due_date) if inv.due_date else None,
            'days_overdue': days_overdue,
            'eligible': is_eligible,
            'ineligible_reason': ineligible_reason,
        })

    # Filter by eligibility if requested
    if eligible == 'true':
        invoices = [i for i in invoices if i['eligible']]
        total = len(invoices)
    elif eligible == 'false':
        invoices = [i for i in invoices if not i['eligible']]
        total = len(invoices)

    return {'invoices': invoices, 'total': total, 'page': page, 'per_page': per_page}


@app.get("/companies/{company}/products/{product}/portfolio/payments")
def get_portfolio_payments(company: str, product: str,
                           page: int = 1, per_page: int = 50,
                           payment_type: Optional[str] = None,
                           db: Session = Depends(get_db)):
    """List payments for dashboard view."""
    from core.models import Invoice, Payment, Product, Organization

    if db is None:
        return {'payments': [], 'total': 0, 'page': page, 'per_page': per_page}

    prod = (db.query(Product).join(Organization)
            .filter(Organization.name == company, Product.name == product).first())
    if not prod:
        return {'payments': [], 'total': 0, 'page': page, 'per_page': per_page}

    q = (db.query(Payment, Invoice.invoice_number)
         .join(Invoice, Payment.invoice_id == Invoice.id)
         .filter(Invoice.product_id == prod.id))
    if payment_type:
        q = q.filter(Payment.payment_type == payment_type.upper())

    total = q.count()
    rows = q.order_by(Payment.payment_date.desc()).offset((page - 1) * per_page).limit(per_page).all()

    payments = []
    for pay, inv_number in rows:
        payments.append({
            'id': str(pay.id),
            'invoice_id': str(pay.invoice_id),
            'invoice_number': inv_number,
            'payment_type': pay.payment_type,
            'payment_amount': float(pay.payment_amount),
            'currency': pay.currency,
            'payment_date': str(pay.payment_date) if pay.payment_date else None,
            'transaction_id': pay.transaction_id,
        })

    return {'payments': payments, 'total': total, 'page': page, 'per_page': per_page}


@app.get("/companies/{company}/products/{product}/portfolio/bank-statements")
def get_portfolio_bank_statements(company: str, product: str,
                                   page: int = 1, per_page: int = 50,
                                   db: Session = Depends(get_db)):
    """List bank statements for dashboard view."""
    from core.models import BankStatement, Organization

    if db is None:
        return {'statements': [], 'total': 0, 'page': page, 'per_page': per_page,
                'summary': {'cash_balance': 0, 'collection_balance': 0, 'last_upload': None}}

    org = db.query(Organization).filter_by(name=company).first()
    if not org:
        return {'statements': [], 'total': 0, 'page': page, 'per_page': per_page,
                'summary': {'cash_balance': 0, 'collection_balance': 0, 'last_upload': None}}

    q = db.query(BankStatement).filter(BankStatement.org_id == org.id)
    total = q.count()
    rows = q.order_by(BankStatement.statement_date.desc()).offset((page - 1) * per_page).limit(per_page).all()

    # Compute summary from latest statements per account type
    from sqlalchemy import func as sqfunc
    cash = (db.query(sqfunc.coalesce(BankStatement.balance, 0))
            .filter(BankStatement.org_id == org.id, BankStatement.account_type == 'cash-account')
            .order_by(BankStatement.statement_date.desc()).first())
    collection = (db.query(sqfunc.coalesce(BankStatement.balance, 0))
                  .filter(BankStatement.org_id == org.id, BankStatement.account_type == 'collection')
                  .order_by(BankStatement.statement_date.desc()).first())
    last = (db.query(sqfunc.max(BankStatement.statement_date))
            .filter(BankStatement.org_id == org.id).scalar())

    statements = [{
        'id': str(bs.id),
        'balance': float(bs.balance),
        'currency': bs.currency,
        'account_type': bs.account_type,
        'statement_date': str(bs.statement_date),
        'created_at': str(bs.created_at) if bs.created_at else None,
    } for bs in rows]

    return {
        'statements': statements,
        'total': total,
        'page': page,
        'per_page': per_page,
        'summary': {
            'cash_balance': float(cash[0]) if cash else 0,
            'collection_balance': float(collection[0]) if collection else 0,
            'last_upload': str(last) if last else None,
        },
    }


@app.get("/companies/{company}/products/{product}/portfolio/covenant-dates")
def get_portfolio_covenant_dates(company: str, product: str,
                                  db: Session = Depends(get_db)):
    """Return available covenant test dates (snapshot dates)."""
    snaps = get_snapshots(company, product)
    dates = [s['date'] for s in snaps]
    # Also add today if DB has data
    if db:
        from core.db_loader import has_db_data
        if has_db_data(db, company, product):
            today = datetime.now().strftime('%Y-%m-%d')
            if today not in dates:
                dates.insert(0, today)
    return {'dates': sorted(dates, reverse=True)}


# ── PDF Report Generation ─────────────────────────────────────────────────────

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

@app.post("/companies/{company}/products/{product}/generate-report")
def generate_pdf_report(company: str, product: str, request: dict = {}):
    """Generate a full dashboard PDF report and stream it back to the browser."""
    timestamp = datetime.now().strftime("%Y-%m-%d")
    filename = f"Laith_{company.upper()}_Report_{timestamp}.pdf"

    script_path = os.path.join(PROJECT_ROOT, 'generate_report.py')
    if not os.path.exists(script_path):
        raise HTTPException(status_code=500, detail="Report generator script not found")

    # Generate into a temp file — FastAPI will clean up after response is sent
    tmp = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    tmp.close()

    cmd = [
        sys.executable, script_path,
        '--company', company,
        '--product', product,
        '--output', tmp.name,
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=180, cwd=PROJECT_ROOT,
        )
        if result.returncode != 0:
            os.unlink(tmp.name)
            detail = result.stderr[:2000] if result.stderr else "Report generation failed"
            raise HTTPException(status_code=500, detail=detail)
        if not os.path.exists(tmp.name) or os.path.getsize(tmp.name) == 0:
            os.unlink(tmp.name)
            raise HTTPException(status_code=500, detail="Report file was not created")
    except subprocess.TimeoutExpired:
        os.unlink(tmp.name)
        raise HTTPException(status_code=504, detail="Report generation timed out (>3 min)")

    from starlette.background import BackgroundTask
    return FileResponse(
        tmp.name,
        media_type='application/pdf',
        filename=filename,
        background=BackgroundTask(os.unlink, tmp.name),
    )