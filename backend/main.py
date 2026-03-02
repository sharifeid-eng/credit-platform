from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import sys, os, json, re, pandas as pd
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.loader import get_companies, get_products, get_snapshots, load_snapshot
from core.config import load_config, SUPPORTED_CURRENCIES
from core.analysis import (
    compute_summary, compute_deployment, compute_collection_velocity,
    compute_denial_trend, compute_cohorts, compute_actual_vs_expected,
    compute_ageing, compute_revenue, compute_concentration,
    compute_returns_analysis, apply_multiplier, filter_by_date,
    compute_dso, compute_hhi, compute_denial_funnel,
    compute_stress_test, compute_expected_loss, compute_loss_triangle,
    compute_group_performance,
)
from core.migration import compute_roll_rates
from core.validation import validate_tape
from core.consistency import run_consistency_check
from core.reporter import generate_ai_analysis, save_pdf_report
app = FastAPI(title="ACP Private Credit API")

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
    df, sel = _load(company, product, snapshot)
    if 'Deal date' not in df.columns:
        raise HTTPException(status_code=400, detail="No Deal date column found")
    df['Deal date'] = pd.to_datetime(df['Deal date'], errors='coerce')
    df = df.dropna(subset=['Deal date'])
    return {
        'min_date':      df['Deal date'].min().strftime('%Y-%m-%d'),
        'max_date':      df['Deal date'].max().strftime('%Y-%m-%d'),
        'snapshot_date': sel['date'],
    }

# ── Summary ───────────────────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/summary")
def get_summary(company: str, product: str,
                snapshot: Optional[str] = None,
                as_of_date: Optional[str] = None,
                currency: Optional[str] = None):
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
    return {**compute_revenue(df, mult), 'currency': disp}

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
    # Enrich with HHI
    result['hhi'] = compute_hhi(df, mult)
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

@app.get("/companies/{company}/products/{product}/validate")
def validate_snapshot(company: str, product: str,
                      snapshot: Optional[str] = None):
    """Run data quality checks on a single tape."""
    df, sel = _load(company, product, snapshot)
    result  = validate_tape(df)
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
    old_df, old_sel = _load(company, product, snapshot_old)
    new_df, new_sel = _load(company, product, snapshot_new)

    validation_old = validate_tape(old_df)
    validation_new = validate_tape(new_df)
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
        'as_of_date':   as_of_date or sel['date'],
    }

@app.get("/companies/{company}/products/{product}/ai-tab-insight")
def get_tab_insight(company: str, product: str,
                    tab: str,
                    snapshot: Optional[str] = None,
                    as_of_date: Optional[str] = None,
                    currency: Optional[str] = None):
    """Generate a short AI insight for a specific dashboard tab."""
    df, sel  = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)

    # Build tab-specific data context
    tab_data = {}
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
        'denial-trend':        'Denial Rate Trend',
        'ageing':              'Portfolio Ageing & Health',
        'revenue':             'Revenue Analysis',
        'concentration':       'Portfolio Concentration',
        'cohort':              'Cohort Analysis',
        'actual-vs-expected':  'Actual vs Expected',
        'returns':             'Returns Analysis',
        'risk-migration':      'Risk & Migration Analysis',
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
        deal_count     = ('Purchase value', 'count'),
    ).reset_index()
    monthly['collection_rate'] = (monthly['collected'] / monthly['purchase_value'] * 100).round(1)
    monthly['denial_rate']     = (monthly['denied']    / monthly['purchase_value'] * 100).round(1)

    group_ctx = ""
    if 'Group' in df.columns:
        top = df.groupby('Group')['Purchase value'].sum().sort_values(ascending=False).head(10)
        group_ctx = f"\nTop groups by purchase value: {top.to_dict()}"

    system = f"""You are an expert credit analyst assistant for ACP Private Credit, 
analyzing the {company.upper()} - {product.replace('_', ' ').title()} loan portfolio.

PORTFOLIO DATA (as of {as_of_date or sel['date']}, currency: {disp}):
- Total Deals: {s['total_deals']:,}
- Purchase Value: {disp} {s['total_purchase_value']/1e6:.2f}M
- Collection Rate: {s['collection_rate']:.1f}%
- Denial Rate: {s['denial_rate']:.1f}%
- Pending Response: {disp} {s['total_pending']/1e6:.2f}M
- Deal Status: {s['status_breakdown']}

MONTHLY PERFORMANCE (last 12 months):
{monthly.tail(12).to_string(index=False)}
{group_ctx}

Answer questions precisely with specific numbers. Be concise but thorough."""

    msgs = [{"role": h['role'], "content": h['content']}
            for h in request.get('history', [])[-6:]]
    msgs.append({"role": "user", "content": request.get('question', '')})

    resp = _ai_client().messages.create(
        model="claude-opus-4-6", max_tokens=1000,
        system=system, messages=msgs
    )
    return {'answer': resp.content[0].text, 'question': request.get('question', '')}