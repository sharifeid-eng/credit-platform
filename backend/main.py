from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.loader import get_companies, get_products, get_snapshots, load_snapshot
from core.config import load_config, SUPPORTED_CURRENCIES

app = FastAPI(title="ACP Private Credit API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_multiplier(config, display_currency):
    if not config:
        return 1.0
    reported = config.get('currency', 'USD')
    rate = SUPPORTED_CURRENCIES.get(reported, 1.0)
    if display_currency == 'USD' and reported != 'USD':
        return rate
    return 1.0

def filter_df(df, as_of_date=None):
    if 'Deal date' in df.columns:
        df['Deal date'] = pd.to_datetime(df['Deal date'], errors='coerce')
    if as_of_date and 'Deal date' in df.columns:
        cutoff = pd.to_datetime(as_of_date)
        df = df[df['Deal date'] <= cutoff]
    return df

@app.get("/companies")
def list_companies():
    companies = get_companies()
    result = []
    for company in companies:
        products = get_products(company)
        total_snapshots = sum(len(get_snapshots(company, p)) for p in products)
        result.append({
            'name': company,
            'products': products,
            'total_snapshots': total_snapshots
        })
    return result

@app.get("/companies/{company}/products")
def list_products(company: str):
    products = get_products(company)
    if not products:
        raise HTTPException(status_code=404, detail=f"No products found for {company}")
    return products

@app.get("/companies/{company}/products/{product}/snapshots")
def list_snapshots(company: str, product: str):
    snapshots = get_snapshots(company, product)
    return [{'filename': s['filename'], 'date': s['date']} for s in snapshots]

@app.get("/companies/{company}/products/{product}/config")
def get_product_config(company: str, product: str):
    config = load_config(company, product)
    if not config:
        return {'currency': 'USD', 'description': '', 'usd_rate': 1.0, 'configured': False}
    return {**config, 'configured': True}

@app.get("/companies/{company}/products/{product}/date-range")
def get_date_range(company: str, product: str, snapshot: Optional[str] = None):
    snapshots = get_snapshots(company, product)
    if not snapshots:
        raise HTTPException(status_code=404, detail="No snapshots found")
    selected = next((s for s in snapshots if s['date'] == snapshot), snapshots[-1])
    df = load_snapshot(selected['filepath'])
    if 'Deal date' not in df.columns:
        raise HTTPException(status_code=400, detail="No Deal date column found")
    df['Deal date'] = pd.to_datetime(df['Deal date'], errors='coerce')
    df = df.dropna(subset=['Deal date'])
    return {
        'min_date': df['Deal date'].min().strftime('%Y-%m-%d'),
        'max_date': df['Deal date'].max().strftime('%Y-%m-%d'),
        'snapshot_date': selected['date']
    }

@app.get("/companies/{company}/products/{product}/summary")
def get_summary(
    company: str, product: str,
    snapshot: Optional[str] = None,
    as_of_date: Optional[str] = None,
    currency: Optional[str] = None
):
    snapshots = get_snapshots(company, product)
    if not snapshots:
        raise HTTPException(status_code=404, detail="No snapshots found")
    selected = next((s for s in snapshots if s['date'] == snapshot), snapshots[-1])
    df = load_snapshot(selected['filepath'])
    df = filter_df(df, as_of_date)
    if len(df) == 0:
        raise HTTPException(status_code=400, detail="No deals found for selected date range")

    config = load_config(company, product)
    reported_currency = config['currency'] if config else 'USD'
    usd_rate = SUPPORTED_CURRENCIES.get(reported_currency, 1.0)
    display_currency = currency if currency else reported_currency
    multiplier = get_multiplier(config, display_currency)

    total_purchase = df['Purchase value'].sum() * multiplier
    total_collected = df['Collected till date'].sum() * multiplier
    total_denied = df['Denied by insurance'].sum() * multiplier
    total_pending = df['Pending insurance response'].sum() * multiplier
    status_counts = df['Status'].value_counts().to_dict()

    min_date = max_date = None
    if 'Deal date' in df.columns:
        valid = df['Deal date'].dropna()
        if len(valid):
            min_date = valid.min().strftime('%Y-%m-%d')
            max_date = valid.max().strftime('%Y-%m-%d')

    return {
        'company': company, 'product': product,
        'snapshot_date': selected['date'],
        'as_of_date': as_of_date or selected['date'],
        'reported_currency': reported_currency,
        'display_currency': display_currency,
        'usd_rate': usd_rate,
        'total_deals': len(df),
        'total_purchase_value': float(total_purchase),
        'total_collected': float(total_collected),
        'total_denied': float(total_denied),
        'total_pending': float(total_pending),
        'collection_rate': float(total_collected / total_purchase * 100) if total_purchase > 0 else 0,
        'denial_rate': float(total_denied / total_purchase * 100) if total_purchase > 0 else 0,
        'pending_rate': float(total_pending / total_purchase * 100) if total_purchase > 0 else 0,
        'completed_deals': int(status_counts.get('Completed', 0)),
        'active_deals': int(status_counts.get('Executed', 0)),
        'status_breakdown': status_counts,
        'date_range': {'min': min_date, 'max': max_date}
    }

@app.get("/companies/{company}/products/{product}/charts/deployment")
def get_deployment_chart(
    company: str, product: str,
    snapshot: Optional[str] = None,
    as_of_date: Optional[str] = None,
    currency: Optional[str] = None
):
    """Monthly capital deployed, split by new vs repeat business"""
    snapshots = get_snapshots(company, product)
    if not snapshots:
        raise HTTPException(status_code=404, detail="No snapshots found")
    selected = next((s for s in snapshots if s['date'] == snapshot), snapshots[-1])
    df = load_snapshot(selected['filepath'])
    df = filter_df(df, as_of_date)

    config = load_config(company, product)
    multiplier = get_multiplier(config, currency or (config['currency'] if config else 'USD'))

    if 'Deal date' not in df.columns:
        raise HTTPException(status_code=400, detail="No Deal date column found")

    df['Month'] = df['Deal date'].dt.to_period('M').astype(str)

    has_new_business = 'New business' in df.columns

    monthly = df.groupby('Month').agg(
        purchase_value=('Purchase value', 'sum'),
        new_business=('New business', 'sum') if has_new_business else ('Purchase value', 'sum'),
        deal_count=('Purchase value', 'count')
    ).reset_index()

    monthly['purchase_value'] = monthly['purchase_value'] * multiplier
    monthly['new_business'] = monthly['new_business'] * multiplier

    if has_new_business:
        monthly['repeat_business'] = monthly['purchase_value'] - monthly['new_business']
    else:
        monthly['repeat_business'] = 0

    return {
        'data': monthly.to_dict(orient='records'),
        'currency': currency or (config['currency'] if config else 'USD')
    }

@app.get("/companies/{company}/products/{product}/charts/collection-velocity")
def get_collection_velocity(
    company: str, product: str,
    snapshot: Optional[str] = None,
    as_of_date: Optional[str] = None,
    currency: Optional[str] = None
):
    """Collection breakdown by days since purchase"""
    snapshots = get_snapshots(company, product)
    if not snapshots:
        raise HTTPException(status_code=404, detail="No snapshots found")
    selected = next((s for s in snapshots if s['date'] == snapshot), snapshots[-1])
    df = load_snapshot(selected['filepath'])
    df = filter_df(df, as_of_date)

    config = load_config(company, product)
    multiplier = get_multiplier(config, currency or (config['currency'] if config else 'USD'))

    # Calculate days to collect for completed deals
    if 'Deal date' not in df.columns or 'Collected till date' not in df.columns:
        raise HTTPException(status_code=400, detail="Required columns missing")

    completed = df[df['Status'] == 'Completed'].copy()
    today = pd.Timestamp(as_of_date) if as_of_date else pd.Timestamp.now()

    completed['days_outstanding'] = (today - completed['Deal date']).dt.days

    buckets = [
        ('0-30 days', 0, 30),
        ('31-60 days', 31, 60),
        ('61-90 days', 61, 90),
        ('91-120 days', 91, 120),
        ('121-180 days', 121, 180),
        ('181+ days', 181, 99999),
    ]

    result = []
    for label, low, high in buckets:
        mask = (completed['days_outstanding'] >= low) & (completed['days_outstanding'] <= high)
        subset = completed[mask]
        result.append({
            'bucket': label,
            'deal_count': int(len(subset)),
            'collected': float(subset['Collected till date'].sum() * multiplier),
            'purchase_value': float(subset['Purchase value'].sum() * multiplier),
        })

    # Also get monthly breakdown
    df['Month'] = df['Deal date'].dt.to_period('M').astype(str)
    monthly_collected = df.groupby('Month').agg(
        collected=('Collected till date', 'sum'),
        purchase_value=('Purchase value', 'sum'),
        denied=('Denied by insurance', 'sum'),
        pending=('Pending insurance response', 'sum'),
    ).reset_index()

    monthly_collected['collected'] *= multiplier
    monthly_collected['purchase_value'] *= multiplier
    monthly_collected['denied'] *= multiplier
    monthly_collected['pending'] *= multiplier
    monthly_collected['collection_rate'] = (
        monthly_collected['collected'] / monthly_collected['purchase_value'] * 100
    ).round(1)

    return {
        'buckets': result,
        'monthly': monthly_collected.to_dict(orient='records'),
        'currency': currency or (config['currency'] if config else 'USD')
    }

@app.get("/companies/{company}/products/{product}/charts/denial-trend")
def get_denial_trend(
    company: str, product: str,
    snapshot: Optional[str] = None,
    as_of_date: Optional[str] = None,
    currency: Optional[str] = None
):
    """Monthly denial rate trend"""
    snapshots = get_snapshots(company, product)
    if not snapshots:
        raise HTTPException(status_code=404, detail="No snapshots found")
    selected = next((s for s in snapshots if s['date'] == snapshot), snapshots[-1])
    df = load_snapshot(selected['filepath'])
    df = filter_df(df, as_of_date)

    config = load_config(company, product)
    multiplier = get_multiplier(config, currency or (config['currency'] if config else 'USD'))

    df['Month'] = df['Deal date'].dt.to_period('M').astype(str)

    monthly = df.groupby('Month').agg(
        purchase_value=('Purchase value', 'sum'),
        denied=('Denied by insurance', 'sum'),
        collected=('Collected till date', 'sum'),
        deal_count=('Purchase value', 'count')
    ).reset_index()

    monthly['purchase_value'] *= multiplier
    monthly['denied'] *= multiplier
    monthly['collected'] *= multiplier
    monthly['denial_rate'] = (monthly['denied'] / monthly['purchase_value'] * 100).round(2)
    monthly['collection_rate'] = (monthly['collected'] / monthly['purchase_value'] * 100).round(2)

    # Rolling 3-month average denial rate
    monthly['denial_rate_3m_avg'] = monthly['denial_rate'].rolling(3, min_periods=1).mean().round(2)

    return {
        'data': monthly.to_dict(orient='records'),
        'currency': currency or (config['currency'] if config else 'USD')
    }

@app.get("/companies/{company}/products/{product}/charts/cohort")
def get_cohort_analysis(
    company: str, product: str,
    snapshot: Optional[str] = None,
    as_of_date: Optional[str] = None,
    currency: Optional[str] = None
):
    """Vintage cohort analysis by deal month"""
    snapshots = get_snapshots(company, product)
    if not snapshots:
        raise HTTPException(status_code=404, detail="No snapshots found")
    selected = next((s for s in snapshots if s['date'] == snapshot), snapshots[-1])
    df = load_snapshot(selected['filepath'])
    df = filter_df(df, as_of_date)

    config = load_config(company, product)
    multiplier = get_multiplier(config, currency or (config['currency'] if config else 'USD'))

    df['Month'] = df['Deal date'].dt.to_period('M').astype(str)

    cohorts = []
    for month, group in df.groupby('Month'):
        total = len(group)
        completed = len(group[group['Status'] == 'Completed'])
        purchase_value = group['Purchase value'].sum() * multiplier
        collected = group['Collected till date'].sum() * multiplier
        denied = group['Denied by insurance'].sum() * multiplier
        pending = group['Pending insurance response'].sum() * multiplier

        collection_rate = (collected / purchase_value * 100) if purchase_value > 0 else 0
        denial_rate = (denied / purchase_value * 100) if purchase_value > 0 else 0
        completion_rate = (completed / total * 100) if total > 0 else 0

        # IRR calculation if columns exist
        avg_expected_irr = None
        avg_actual_irr = None
        if 'Expected IRR' in group.columns:
            irr_data = pd.to_numeric(group['Expected IRR'], errors='coerce')
            avg_expected_irr = float(irr_data.mean()) if not irr_data.isna().all() else None
        if 'Actual IRR' in group.columns:
            irr_data = pd.to_numeric(group['Actual IRR'], errors='coerce')
            # Filter outliers > 1000%
            irr_data = irr_data[irr_data < 10]
            avg_actual_irr = float(irr_data.mean()) if not irr_data.isna().all() else None

        cohort = {
            'month': month,
            'total_deals': int(total),
            'completed_deals': int(completed),
            'completion_rate': round(completion_rate, 1),
            'purchase_value': round(purchase_value, 2),
            'collected': round(collected, 2),
            'denied': round(denied, 2),
            'pending': round(pending, 2),
            'collection_rate': round(collection_rate, 1),
            'denial_rate': round(denial_rate, 1),
        }

        if avg_expected_irr is not None:
            cohort['avg_expected_irr'] = round(avg_expected_irr * 100, 1)
        if avg_actual_irr is not None:
            cohort['avg_actual_irr'] = round(avg_actual_irr * 100, 1)

        cohorts.append(cohort)

    return {
        'cohorts': cohorts,
        'currency': currency or (config['currency'] if config else 'USD')
    }

@app.get("/companies/{company}/products/{product}/ai-commentary")
def get_ai_commentary(
    company: str, product: str,
    snapshot: Optional[str] = None,
    as_of_date: Optional[str] = None,
    currency: Optional[str] = None
):
    """Generate AI commentary on the current portfolio state"""
    import anthropic
    from dotenv import load_dotenv
    load_dotenv()

    snapshots = get_snapshots(company, product)
    if not snapshots:
        raise HTTPException(status_code=404, detail="No snapshots found")
    selected = next((s for s in snapshots if s['date'] == snapshot), snapshots[-1])
    df = load_snapshot(selected['filepath'])
    df = filter_df(df, as_of_date)

    config = load_config(company, product)
    reported_currency = config['currency'] if config else 'USD'
    multiplier = get_multiplier(config, currency or reported_currency)
    display_currency = currency or reported_currency

    # Build stats for AI
    total_purchase = df['Purchase value'].sum() * multiplier
    total_collected = df['Collected till date'].sum() * multiplier
    total_denied = df['Denied by insurance'].sum() * multiplier
    total_pending = df['Pending insurance response'].sum() * multiplier
    collection_rate = total_collected / total_purchase * 100 if total_purchase > 0 else 0
    denial_rate = total_denied / total_purchase * 100 if total_purchase > 0 else 0
    status_counts = df['Status'].value_counts().to_dict()

    df['Month'] = df['Deal date'].dt.to_period('M').astype(str)
    monthly = df.groupby('Month').agg(
        purchase_value=('Purchase value', 'sum'),
        collected=('Collected till date', 'sum'),
        denied=('Denied by insurance', 'sum'),
    ).reset_index().tail(6)

    monthly_summary = monthly.to_dict(orient='records')

    prompt = f"""You are a senior analyst at ACP Private Credit, a private credit fund specializing in asset-backed lending.

You are analyzing the loan portfolio for {company.upper()} - {product.replace('_', ' ').title()}.
Data as of: {as_of_date or selected['date']}
Currency: {display_currency}

PORTFOLIO SNAPSHOT:
- Total Deals: {len(df):,}
- Purchase Value: {display_currency} {total_purchase/1e6:.1f}M
- Total Collected: {display_currency} {total_collected/1e6:.1f}M
- Collection Rate: {collection_rate:.1f}%
- Denial Rate: {denial_rate:.1f}%
- Pending Response: {display_currency} {total_pending/1e6:.1f}M ({total_pending/total_purchase*100:.1f}% of portfolio)
- Deal Status: {status_counts}

LAST 6 MONTHS ACTIVITY:
{monthly_summary}

Write a concise but insightful portfolio commentary in 3 sections:

1. PORTFOLIO HEALTH (2-3 sentences)
Overall assessment of collection performance, denial rates, and any trends worth noting.

2. KEY OBSERVATIONS (3-4 bullet points)
The most important data points an investment committee should know. Be specific with numbers.

3. WATCH ITEMS (2-3 bullet points)
Areas that warrant monitoring or follow-up. Be direct about concerns.

Write in a professional tone suitable for an investment committee memo. Be specific and data-driven."""

    client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    return {
        'commentary': message.content[0].text,
        'generated_at': datetime.now().isoformat(),
        'as_of_date': as_of_date or selected['date']
    }

@app.get("/companies/{company}/products/{product}/charts/actual-vs-expected")
def get_actual_vs_expected(
    company: str, product: str,
    snapshot: Optional[str] = None,
    as_of_date: Optional[str] = None,
    currency: Optional[str] = None
):
    """Cumulative collected vs expected over time"""
    snapshots = get_snapshots(company, product)
    if not snapshots:
        raise HTTPException(status_code=404, detail="No snapshots found")
    selected = next((s for s in snapshots if s['date'] == snapshot), snapshots[-1])
    df = load_snapshot(selected['filepath'])
    df = filter_df(df, as_of_date)

    config = load_config(company, product)
    multiplier = get_multiplier(config, currency or (config['currency'] if config else 'USD'))

    df['Month'] = df['Deal date'].dt.to_period('M').astype(str)

    monthly = df.groupby('Month').agg(
        collected=('Collected till date', 'sum'),
        expected=('Expected total', 'sum'),
        purchase_value=('Purchase value', 'sum'),
    ).reset_index()

    monthly['collected'] *= multiplier
    monthly['expected'] *= multiplier
    monthly['purchase_value'] *= multiplier

    # Cumulative sums
    monthly['cumulative_collected'] = monthly['collected'].cumsum()
    monthly['cumulative_expected'] = monthly['expected'].cumsum()
    monthly['cumulative_purchase'] = monthly['purchase_value'].cumsum()

    # Performance ratio
    monthly['performance_ratio'] = (
        monthly['cumulative_collected'] / monthly['cumulative_expected'] * 100
    ).round(1)

    return {
        'data': monthly.to_dict(orient='records'),
        'currency': currency or (config['currency'] if config else 'USD'),
        'total_collected': float(df['Collected till date'].sum() * multiplier),
        'total_expected': float(df['Expected total'].sum() * multiplier),
        'overall_performance': round(
            df['Collected till date'].sum() / df['Expected total'].sum() * 100, 1
        ) if df['Expected total'].sum() > 0 else 0
    }

@app.get("/companies/{company}/products/{product}/charts/ageing")
def get_ageing(
    company: str, product: str,
    snapshot: Optional[str] = None,
    as_of_date: Optional[str] = None,
    currency: Optional[str] = None
):
    """Portfolio ageing and health breakdown"""
    snapshots = get_snapshots(company, product)
    if not snapshots:
        raise HTTPException(status_code=404, detail="No snapshots found")
    selected = next((s for s in snapshots if s['date'] == snapshot), snapshots[-1])
    df = load_snapshot(selected['filepath'])
    df = filter_df(df, as_of_date)

    config = load_config(company, product)
    multiplier = get_multiplier(config, currency or (config['currency'] if config else 'USD'))

    today = pd.Timestamp(as_of_date) if as_of_date else pd.Timestamp.now()

    # Only look at active/executed deals
    active = df[df['Status'] == 'Executed'].copy()
    active['days_outstanding'] = (today - active['Deal date']).dt.days

    # Health classification based on days outstanding
    def classify_health(days):
        if pd.isna(days):
            return 'Unknown'
        elif days <= 60:
            return 'Healthy'
        elif days <= 90:
            return 'Watch'
        elif days <= 120:
            return 'Delayed'
        else:
            return 'Poor'

    active['health'] = active['days_outstanding'].apply(classify_health)

    # Ageing buckets for all active deals
    ageing_buckets = [
        ('0-30 days', 0, 30),
        ('31-60 days', 31, 60),
        ('61-90 days', 61, 90),
        ('91-120 days', 91, 120),
        ('121-180 days', 121, 180),
        ('181-365 days', 181, 365),
        ('365+ days', 366, 99999),
    ]

    ageing = []
    for label, low, high in ageing_buckets:
        mask = (active['days_outstanding'] >= low) & (active['days_outstanding'] <= high)
        subset = active[mask]
        ageing.append({
            'bucket': label,
            'deal_count': int(len(subset)),
            'pending_value': float(subset['Pending insurance response'].sum() * multiplier),
            'purchase_value': float(subset['Purchase value'].sum() * multiplier),
        })

    # Health summary
    health_summary = []
    health_colors = {
        'Healthy': '#4ADE80',
        'Watch': '#F59E0B',
        'Delayed': '#F97316',
        'Poor': '#EF4444',
        'Unknown': '#64748B'
    }

    for health_status in ['Healthy', 'Watch', 'Delayed', 'Poor']:
        subset = active[active['health'] == health_status]
        total_active_value = active['Purchase value'].sum()
        value = subset['Purchase value'].sum() * multiplier
        health_summary.append({
            'status': health_status,
            'deal_count': int(len(subset)),
            'value': float(value),
            'percentage': round(len(subset) / len(active) * 100, 1) if len(active) > 0 else 0,
            'color': health_colors[health_status]
        })

    # Monthly ageing trend
    df['Month'] = df['Deal date'].dt.to_period('M').astype(str)
    monthly_active = active.groupby('Month').agg(
        deal_count=('Purchase value', 'count'),
        purchase_value=('Purchase value', 'sum'),
        pending=('Pending insurance response', 'sum'),
    ).reset_index()
    monthly_active['purchase_value'] *= multiplier
    monthly_active['pending'] *= multiplier

    return {
        'ageing_buckets': ageing,
        'health_summary': health_summary,
        'monthly_active': monthly_active.to_dict(orient='records'),
        'total_active_deals': int(len(active)),
        'total_active_value': float(active['Purchase value'].sum() * multiplier),
        'currency': currency or (config['currency'] if config else 'USD')
    }

@app.get("/companies/{company}/products/{product}/charts/revenue")
def get_revenue(
    company: str, product: str,
    snapshot: Optional[str] = None,
    as_of_date: Optional[str] = None,
    currency: Optional[str] = None
):
    """Revenue analysis - realised vs unrealised, fees"""
    snapshots = get_snapshots(company, product)
    if not snapshots:
        raise HTTPException(status_code=404, detail="No snapshots found")
    selected = next((s for s in snapshots if s['date'] == snapshot), snapshots[-1])
    df = load_snapshot(selected['filepath'])
    df = filter_df(df, as_of_date)

    config = load_config(company, product)
    multiplier = get_multiplier(config, currency or (config['currency'] if config else 'USD'))

    df['Month'] = df['Deal date'].dt.to_period('M').astype(str)

    # Revenue columns
    has_setup_fee = 'Setup fee' in df.columns
    has_other_fee = 'Other fee' in df.columns
    has_gross_revenue = 'Gross revenue' in df.columns

    monthly = df.groupby('Month').agg(
        gross_revenue=('Gross revenue', 'sum') if has_gross_revenue else ('Purchase value', 'sum'),
        collected=('Collected till date', 'sum'),
        purchase_value=('Purchase value', 'sum'),
        setup_fees=('Setup fee', 'sum') if has_setup_fee else ('Purchase value', 'sum'),
        other_fees=('Other fee', 'sum') if has_other_fee else ('Purchase value', 'sum'),
    ).reset_index()

    monthly['gross_revenue'] *= multiplier
    monthly['collected'] *= multiplier
    monthly['purchase_value'] *= multiplier

    if has_setup_fee:
        monthly['setup_fees'] *= multiplier
    else:
        monthly['setup_fees'] = 0

    if has_other_fee:
        monthly['other_fees'] *= multiplier
    else:
        monthly['other_fees'] = 0

    # Realised vs unrealised
    monthly['realised_revenue'] = (
        monthly['gross_revenue'] * (monthly['collected'] / monthly['purchase_value'])
    ).fillna(0)
    monthly['unrealised_revenue'] = monthly['gross_revenue'] - monthly['realised_revenue']

    # Gross margin
    monthly['gross_margin'] = (
        monthly['gross_revenue'] / monthly['purchase_value'] * 100
    ).round(2)

    # Totals
    total_gross_revenue = float(df['Gross revenue'].sum() * multiplier) if has_gross_revenue else 0
    total_setup_fees = float(df['Setup fee'].sum() * multiplier) if has_setup_fee else 0
    total_other_fees = float(df['Other fee'].sum() * multiplier) if has_other_fee else 0
    total_purchase = float(df['Purchase value'].sum() * multiplier)

    return {
        'monthly': monthly.to_dict(orient='records'),
        'totals': {
            'gross_revenue': total_gross_revenue,
            'setup_fees': total_setup_fees,
            'other_fees': total_other_fees,
            'total_income': total_gross_revenue + total_setup_fees + total_other_fees,
            'gross_margin': round(total_gross_revenue / total_purchase * 100, 2) if total_purchase > 0 else 0
        },
        'currency': currency or (config['currency'] if config else 'USD')
    }

@app.get("/companies/{company}/products/{product}/charts/concentration")
def get_concentration(
    company: str, product: str,
    snapshot: Optional[str] = None,
    as_of_date: Optional[str] = None,
    currency: Optional[str] = None
):
    """Insurer and customer concentration analysis"""
    snapshots = get_snapshots(company, product)
    if not snapshots:
        raise HTTPException(status_code=404, detail="No snapshots found")
    selected = next((s for s in snapshots if s['date'] == snapshot), snapshots[-1])
    df = load_snapshot(selected['filepath'])
    df = filter_df(df, as_of_date)

    config = load_config(company, product)
    multiplier = get_multiplier(config, currency or (config['currency'] if config else 'USD'))

    result = {}

    # Group concentration
    if 'Group' in df.columns:
        group_conc = df.groupby('Group').agg(
            purchase_value=('Purchase value', 'sum'),
            deal_count=('Purchase value', 'count'),
            collected=('Collected till date', 'sum'),
            denied=('Denied by insurance', 'sum'),
        ).reset_index()
        group_conc['purchase_value'] *= multiplier
        group_conc['collected'] *= multiplier
        group_conc['denied'] *= multiplier
        group_conc['collection_rate'] = (
            group_conc['collected'] / group_conc['purchase_value'] * 100
        ).round(1)
        group_conc['denial_rate'] = (
            group_conc['denied'] / group_conc['purchase_value'] * 100
        ).round(1)
        total = group_conc['purchase_value'].sum()
        group_conc['percentage'] = (group_conc['purchase_value'] / total * 100).round(1)
        group_conc = group_conc.sort_values('purchase_value', ascending=False)
        result['group'] = group_conc.head(15).to_dict(orient='records')

    # Product concentration
    if 'Product' in df.columns:
        product_conc = df.groupby('Product').agg(
            purchase_value=('Purchase value', 'sum'),
            deal_count=('Purchase value', 'count'),
        ).reset_index()
        product_conc['purchase_value'] *= multiplier
        total = product_conc['purchase_value'].sum()
        product_conc['percentage'] = (product_conc['purchase_value'] / total * 100).round(1)
        product_conc = product_conc.sort_values('purchase_value', ascending=False)
        result['product'] = product_conc.to_dict(orient='records')

    # Discount distribution
    if 'Discount' in df.columns:
        df['discount_pct'] = pd.to_numeric(df['Discount'], errors='coerce')
        discount_dist = df.groupby('discount_pct').agg(
            deal_count=('Purchase value', 'count'),
            purchase_value=('Purchase value', 'sum'),
        ).reset_index()
        discount_dist['purchase_value'] *= multiplier
        result['discount'] = discount_dist.dropna().to_dict(orient='records')

    # Top 10 deals
    top_deals = df.nlargest(10, 'Purchase value')[[
        col for col in ['Deal date', 'Status', 'Purchase value',
                       'Discount', 'Collected till date', 'Denied by insurance']
        if col in df.columns
    ]].copy()
    top_deals['Purchase value'] *= multiplier
    if 'Collected till date' in top_deals.columns:
        top_deals['Collected till date'] *= multiplier
    if 'Deal date' in top_deals.columns:
        top_deals['Deal date'] = top_deals['Deal date'].astype(str)
    result['top_deals'] = top_deals.to_dict(orient='records')

    result['currency'] = currency or (config['currency'] if config else 'USD')
    return result

@app.post("/companies/{company}/products/{product}/chat")
def chat_with_data(
    company: str, product: str,
    request: dict,
    snapshot: Optional[str] = None,
    as_of_date: Optional[str] = None,
    currency: Optional[str] = None
):
    """Chat with the data - answer questions about the portfolio"""
    import anthropic
    from dotenv import load_dotenv
    load_dotenv()

    snapshots = get_snapshots(company, product)
    if not snapshots:
        raise HTTPException(status_code=404, detail="No snapshots found")
    selected = next((s for s in snapshots if s['date'] == snapshot), snapshots[-1])
    df = load_snapshot(selected['filepath'])
    df = filter_df(df, as_of_date)

    config = load_config(company, product)
    reported_currency = config['currency'] if config else 'USD'
    multiplier = get_multiplier(config, currency or reported_currency)
    display_currency = currency or reported_currency

    # Build comprehensive data context
    total_purchase = df['Purchase value'].sum() * multiplier
    total_collected = df['Collected till date'].sum() * multiplier
    total_denied = df['Denied by insurance'].sum() * multiplier
    total_pending = df['Pending insurance response'].sum() * multiplier
    status_counts = df['Status'].value_counts().to_dict()

    # Monthly summary for context
    df['Month'] = df['Deal date'].dt.to_period('M').astype(str)
    monthly = df.groupby('Month').agg(
        purchase_value=('Purchase value', 'sum'),
        collected=('Collected till date', 'sum'),
        denied=('Denied by insurance', 'sum'),
        deal_count=('Purchase value', 'count'),
    ).reset_index()
    monthly['collection_rate'] = (monthly['collected'] / monthly['purchase_value'] * 100).round(1)
    monthly['denial_rate'] = (monthly['denied'] / monthly['purchase_value'] * 100).round(1)

    # Group breakdown if available
    group_context = ""
    if 'Group' in df.columns:
        groups = df.groupby('Group')['Purchase value'].sum().sort_values(ascending=False).head(10)
        group_context = f"\nTop groups by purchase value: {groups.to_dict()}"

    system_prompt = f"""You are an expert credit analyst assistant for ACP Private Credit, 
analyzing the {company.upper()} - {product.replace('_', ' ').title()} loan portfolio.

PORTFOLIO DATA (as of {as_of_date or selected['date']}, currency: {display_currency}):
- Total Deals: {len(df):,}
- Purchase Value: {display_currency} {total_purchase/1e6:.2f}M
- Total Collected: {display_currency} {total_collected/1e6:.2f}M  
- Collection Rate: {total_collected/total_purchase*100:.1f}%
- Total Denied: {display_currency} {total_denied/1e6:.2f}M
- Denial Rate: {total_denied/total_purchase*100:.1f}%
- Pending Response: {display_currency} {total_pending/1e6:.2f}M
- Deal Status: {status_counts}

MONTHLY PERFORMANCE (last 12 months):
{monthly.tail(12).to_string(index=False)}
{group_context}

You have access to detailed loan-level data. Answer questions precisely and reference 
specific numbers. If asked about trends, reference the monthly data above.
Be concise but thorough. Format numbers clearly with currency symbols.
If you need data that wasn't provided in context, say so clearly."""

    question = request.get('question', '')
    history = request.get('history', [])

    messages = []
    for h in history[-6:]:  # Keep last 6 exchanges for context
        messages.append({"role": h['role'], "content": h['content']})
    messages.append({"role": "user", "content": question})

    client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1000,
        system=system_prompt,
        messages=messages
    )

    return {
        'answer': response.content[0].text,
        'question': question
    }