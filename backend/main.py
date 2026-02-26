from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import sys, os, pandas as pd
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.loader import get_companies, get_products, get_snapshots, load_snapshot
from core.config import load_config, SUPPORTED_CURRENCIES
from core.analysis import (
    compute_summary, compute_deployment, compute_collection_velocity,
    compute_denial_trend, compute_cohorts, compute_actual_vs_expected,
    compute_ageing, compute_revenue, compute_concentration,
    apply_multiplier, filter_by_date,
)

app = FastAPI(title="ACP Private Credit API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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
    return {'company': company, 'product': product,
            **compute_summary(df, config, disp, sel['date'], as_of_date)}

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
    return {**compute_concentration(df, mult), 'currency': disp}

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

    tab_labels = {
        'deployment':          'Capital Deployment',
        'collection':          'Collection Velocity',
        'denial-trend':        'Denial Rate Trend',
        'ageing':              'Portfolio Ageing & Health',
        'revenue':             'Revenue Analysis',
        'concentration':       'Portfolio Concentration',
        'cohort':              'Cohort Analysis',
        'actual-vs-expected':  'Actual vs Expected',
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