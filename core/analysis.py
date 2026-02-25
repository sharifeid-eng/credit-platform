"""
core/analysis.py
Pure data computation functions — no FastAPI, no I/O.
All functions take a DataFrame + params, return plain Python dicts/lists.
"""
import pandas as pd
import numpy as np


# ── Helpers ──────────────────────────────────────────────────────────────────

def fmt_m(v):
    """Format a number in millions for display."""
    if abs(v) >= 1e6:
        return f"{v / 1e6:.1f}M"
    if abs(v) >= 1e3:
        return f"{v / 1e3:.0f}K"
    return f"{v:.0f}"


def apply_multiplier(config, display_currency):
    """Return the USD conversion multiplier if needed, else 1.0."""
    from core.config import SUPPORTED_CURRENCIES
    if not config:
        return 1.0
    reported = config.get('currency', 'USD')
    rate = SUPPORTED_CURRENCIES.get(reported, 1.0)
    if display_currency == 'USD' and reported != 'USD':
        return rate
    return 1.0


def filter_by_date(df, as_of_date=None):
    """Filter DataFrame to deals on or before as_of_date."""
    if 'Deal date' in df.columns:
        df['Deal date'] = pd.to_datetime(df['Deal date'], errors='coerce')
    if as_of_date and 'Deal date' in df.columns:
        df = df[df['Deal date'] <= pd.to_datetime(as_of_date)]
    return df


def add_month_column(df):
    """Add a 'Month' string column derived from Deal date."""
    if 'Deal date' in df.columns:
        df = df.copy()
        df['Month'] = df['Deal date'].dt.to_period('M').astype(str)
    return df


# ── Portfolio Summary ─────────────────────────────────────────────────────────

def compute_summary(df, config, display_currency, snapshot_date, as_of_date):
    """Compute portfolio-level KPIs."""
    mult = apply_multiplier(config, display_currency)
    reported_currency = config['currency'] if config else 'USD'
    from core.config import SUPPORTED_CURRENCIES
    usd_rate = SUPPORTED_CURRENCIES.get(reported_currency, 1.0)

    total_purchase   = df['Purchase value'].sum() * mult
    total_collected  = df['Collected till date'].sum() * mult
    total_denied     = df['Denied by insurance'].sum() * mult
    total_pending    = df['Pending insurance response'].sum() * mult
    status_counts    = df['Status'].value_counts().to_dict()

    min_date = max_date = None
    if 'Deal date' in df.columns:
        valid = df['Deal date'].dropna()
        if len(valid):
            min_date = valid.min().strftime('%Y-%m-%d')
            max_date = valid.max().strftime('%Y-%m-%d')

    return {
        'snapshot_date':      snapshot_date,
        'as_of_date':         as_of_date or snapshot_date,
        'reported_currency':  reported_currency,
        'display_currency':   display_currency,
        'usd_rate':           usd_rate,
        'total_deals':        len(df),
        'total_purchase_value': float(total_purchase),
        'total_collected':    float(total_collected),
        'total_denied':       float(total_denied),
        'total_pending':      float(total_pending),
        'collection_rate':    float(total_collected / total_purchase * 100) if total_purchase else 0,
        'denial_rate':        float(total_denied    / total_purchase * 100) if total_purchase else 0,
        'pending_rate':       float(total_pending   / total_purchase * 100) if total_purchase else 0,
        'completed_deals':    int(status_counts.get('Completed', 0)),
        'active_deals':       int(status_counts.get('Executed', 0)),
        'status_breakdown':   status_counts,
        'date_range':         {'min': min_date, 'max': max_date},
    }


# ── Deployment ────────────────────────────────────────────────────────────────

def compute_deployment(df, mult):
    """Monthly capital deployed split by new vs repeat business."""
    df = add_month_column(df)
    has_new = 'New business' in df.columns

    agg = {'purchase_value': ('Purchase value', 'sum'), 'deal_count': ('Purchase value', 'count')}
    if has_new:
        agg['new_business'] = ('New business', 'sum')

    monthly = df.groupby('Month').agg(**agg).reset_index()
    monthly['purchase_value'] *= mult

    if has_new:
        monthly['new_business']    *= mult
        monthly['repeat_business']  = monthly['purchase_value'] - monthly['new_business']
    else:
        monthly['new_business']    = monthly['purchase_value']
        monthly['repeat_business'] = 0

    return monthly.to_dict(orient='records')


# ── Collection Velocity ───────────────────────────────────────────────────────

AGEING_BUCKETS = [
    ('0-30 days',    0,   30),
    ('31-60 days',   31,  60),
    ('61-90 days',   61,  90),
    ('91-120 days',  91,  120),
    ('121-180 days', 121, 180),
    ('181+ days',    181, 99999),
]

def compute_collection_velocity(df, mult, as_of_date=None):
    """Collection breakdown by days outstanding + monthly rates."""
    today = pd.Timestamp(as_of_date) if as_of_date else pd.Timestamp.now()
    completed = df[df['Status'] == 'Completed'].copy()
    completed['days_outstanding'] = (today - completed['Deal date']).dt.days

    buckets = []
    for label, lo, hi in AGEING_BUCKETS:
        sub = completed[(completed['days_outstanding'] >= lo) & (completed['days_outstanding'] <= hi)]
        buckets.append({
            'bucket':         label,
            'deal_count':     int(len(sub)),
            'collected':      float(sub['Collected till date'].sum() * mult),
            'purchase_value': float(sub['Purchase value'].sum() * mult),
        })

    df = add_month_column(df)
    monthly = df.groupby('Month').agg(
        collected      = ('Collected till date', 'sum'),
        purchase_value = ('Purchase value', 'sum'),
        denied         = ('Denied by insurance', 'sum'),
        pending        = ('Pending insurance response', 'sum'),
    ).reset_index()
    for col in ['collected', 'purchase_value', 'denied', 'pending']:
        monthly[col] *= mult
    monthly['collection_rate'] = (
        monthly['collected'] / monthly['purchase_value'] * 100
    ).round(1)

    return {'buckets': buckets, 'monthly': monthly.to_dict(orient='records')}


# ── Denial Trend ──────────────────────────────────────────────────────────────

def compute_denial_trend(df, mult):
    """Monthly denial and collection rates with 3M rolling average."""
    df = add_month_column(df)
    monthly = df.groupby('Month').agg(
        purchase_value = ('Purchase value', 'sum'),
        denied         = ('Denied by insurance', 'sum'),
        collected      = ('Collected till date', 'sum'),
        deal_count     = ('Purchase value', 'count'),
    ).reset_index()
    monthly['purchase_value'] *= mult
    monthly['denied']         *= mult
    monthly['collected']      *= mult
    monthly['denial_rate']    = (monthly['denied']    / monthly['purchase_value'] * 100).round(2)
    monthly['collection_rate']= (monthly['collected'] / monthly['purchase_value'] * 100).round(2)
    monthly['denial_rate_3m_avg'] = monthly['denial_rate'].rolling(3, min_periods=1).mean().round(2)
    return monthly.to_dict(orient='records')


# ── Cohort Analysis ───────────────────────────────────────────────────────────

def compute_cohorts(df, mult):
    """Vintage cohort analysis by deal origination month."""
    df = add_month_column(df)
    cohorts = []

    for month, grp in df.groupby('Month'):
        total     = len(grp)
        completed = len(grp[grp['Status'] == 'Completed'])
        pv        = grp['Purchase value'].sum() * mult
        collected = grp['Collected till date'].sum() * mult
        denied    = grp['Denied by insurance'].sum() * mult
        pending   = grp['Pending insurance response'].sum() * mult

        row = {
            'month':            month,
            'total_deals':      int(total),
            'completed_deals':  int(completed),
            'completion_rate':  round(completed / total * 100, 1) if total else 0,
            'purchase_value':   round(pv, 2),
            'collected':        round(collected, 2),
            'denied':           round(denied, 2),
            'pending':          round(pending, 2),
            'collection_rate':  round(collected / pv * 100, 1) if pv else 0,
            'denial_rate':      round(denied    / pv * 100, 1) if pv else 0,
        }

        if 'Expected IRR' in grp.columns:
            irr = pd.to_numeric(grp['Expected IRR'], errors='coerce')
            row['avg_expected_irr'] = round(float(irr.mean()) * 100, 1) if not irr.isna().all() else None

        if 'Actual IRR' in grp.columns:
            irr = pd.to_numeric(grp['Actual IRR'], errors='coerce')
            irr = irr[irr < 10]  # filter outliers >1000%
            row['avg_actual_irr'] = round(float(irr.mean()) * 100, 1) if not irr.isna().all() else None

        cohorts.append(row)

    return cohorts


# ── Actual vs Expected ────────────────────────────────────────────────────────

def compute_actual_vs_expected(df, mult):
    """Cumulative collected vs expected with performance ratio."""
    df = add_month_column(df)
    monthly = df.groupby('Month').agg(
        collected      = ('Collected till date', 'sum'),
        expected       = ('Expected total', 'sum'),
        purchase_value = ('Purchase value', 'sum'),
    ).reset_index()
    for col in ['collected', 'expected', 'purchase_value']:
        monthly[col] *= mult

    monthly['cumulative_collected'] = monthly['collected'].cumsum()
    monthly['cumulative_expected']  = monthly['expected'].cumsum()
    monthly['cumulative_purchase']  = monthly['purchase_value'].cumsum()
    monthly['performance_ratio']    = (
        monthly['cumulative_collected'] / monthly['cumulative_expected'] * 100
    ).round(1)

    total_collected = float(df['Collected till date'].sum() * mult)
    total_expected  = float(df['Expected total'].sum() * mult)

    return {
        'data':                monthly.to_dict(orient='records'),
        'total_collected':     total_collected,
        'total_expected':      total_expected,
        'overall_performance': round(total_collected / total_expected * 100, 1) if total_expected else 0,
    }


# ── Ageing ────────────────────────────────────────────────────────────────────

EXTENDED_AGEING_BUCKETS = [
    ('0-30 days',    0,   30),
    ('31-60 days',   31,  60),
    ('61-90 days',   61,  90),
    ('91-120 days',  91,  120),
    ('121-180 days', 121, 180),
    ('181-365 days', 181, 365),
    ('365+ days',    366, 99999),
]

HEALTH_COLORS = {
    'Healthy': '#4ADE80',
    'Watch':   '#F59E0B',
    'Delayed': '#F97316',
    'Poor':    '#EF4444',
}

def classify_health(days):
    if pd.isna(days):   return 'Unknown'
    if days <= 60:      return 'Healthy'
    if days <= 90:      return 'Watch'
    if days <= 120:     return 'Delayed'
    return 'Poor'

def compute_ageing(df, mult, as_of_date=None):
    """Active deal health + ageing bucket breakdown."""
    today  = pd.Timestamp(as_of_date) if as_of_date else pd.Timestamp.now()
    active = df[df['Status'] == 'Executed'].copy()
    active['days_outstanding'] = (today - active['Deal date']).dt.days
    active['health']           = active['days_outstanding'].apply(classify_health)

    ageing = []
    for label, lo, hi in EXTENDED_AGEING_BUCKETS:
        sub = active[(active['days_outstanding'] >= lo) & (active['days_outstanding'] <= hi)]
        ageing.append({
            'bucket':         label,
            'deal_count':     int(len(sub)),
            'pending_value':  float(sub['Pending insurance response'].sum() * mult),
            'purchase_value': float(sub['Purchase value'].sum() * mult),
        })

    health_summary = []
    for status, color in HEALTH_COLORS.items():
        sub = active[active['health'] == status]
        health_summary.append({
            'status':     status,
            'deal_count': int(len(sub)),
            'value':      float(sub['Purchase value'].sum() * mult),
            'percentage': round(len(sub) / len(active) * 100, 1) if len(active) else 0,
            'color':      color,
        })

    df2 = add_month_column(active)
    monthly = df2.groupby('Month').agg(
        deal_count     = ('Purchase value', 'count'),
        purchase_value = ('Purchase value', 'sum'),
        pending        = ('Pending insurance response', 'sum'),
    ).reset_index()
    monthly['purchase_value'] *= mult
    monthly['pending']        *= mult

    return {
        'ageing_buckets':    ageing,
        'health_summary':    health_summary,
        'monthly_active':    monthly.to_dict(orient='records'),
        'total_active_deals':int(len(active)),
        'total_active_value':float(active['Purchase value'].sum() * mult),
    }


# ── Revenue ───────────────────────────────────────────────────────────────────

def compute_revenue(df, mult):
    """Realised vs unrealised revenue + fees."""
    df = add_month_column(df)
    has_setup       = 'Setup fee'    in df.columns
    has_other       = 'Other fee'    in df.columns
    has_gross       = 'Gross revenue' in df.columns

    agg = {
        'gross_revenue': ('Gross revenue' if has_gross else 'Purchase value', 'sum'),
        'collected':     ('Collected till date', 'sum'),
        'purchase_value':('Purchase value', 'sum'),
    }
    if has_setup: agg['setup_fees'] = ('Setup fee',  'sum')
    if has_other: agg['other_fees'] = ('Other fee',  'sum')

    monthly = df.groupby('Month').agg(**agg).reset_index()
    for col in ['gross_revenue', 'collected', 'purchase_value']:
        monthly[col] *= mult
    if has_setup: monthly['setup_fees'] *= mult
    else:         monthly['setup_fees']  = 0
    if has_other: monthly['other_fees'] *= mult
    else:         monthly['other_fees']  = 0

    monthly['realised_revenue']   = (
        monthly['gross_revenue'] * (monthly['collected'] / monthly['purchase_value'])
    ).fillna(0)
    monthly['unrealised_revenue'] = monthly['gross_revenue'] - monthly['realised_revenue']
    monthly['gross_margin']       = (
        monthly['gross_revenue'] / monthly['purchase_value'] * 100
    ).round(2)

    total_pv      = float(df['Purchase value'].sum() * mult)
    total_gross   = float(df['Gross revenue'].sum()  * mult) if has_gross else 0
    total_setup   = float(df['Setup fee'].sum()       * mult) if has_setup else 0
    total_other   = float(df['Other fee'].sum()       * mult) if has_other else 0

    return {
        'monthly': monthly.to_dict(orient='records'),
        'totals': {
            'gross_revenue': total_gross,
            'setup_fees':    total_setup,
            'other_fees':    total_other,
            'total_income':  total_gross + total_setup + total_other,
            'gross_margin':  round(total_gross / total_pv * 100, 2) if total_pv else 0,
        },
    }


# ── Concentration ─────────────────────────────────────────────────────────────

def compute_concentration(df, mult):
    """Group, product, discount concentration + top deals."""
    result = {}
    total = df['Purchase value'].sum() * mult

    if 'Group' in df.columns:
        g = df.groupby('Group').agg(
            purchase_value = ('Purchase value', 'sum'),
            deal_count     = ('Purchase value', 'count'),
            collected      = ('Collected till date', 'sum'),
            denied         = ('Denied by insurance', 'sum'),
        ).reset_index()
        g['purchase_value'] *= mult
        g['collected']      *= mult
        g['denied']         *= mult
        g['collection_rate']= (g['collected'] / g['purchase_value'] * 100).round(1)
        g['denial_rate']    = (g['denied']    / g['purchase_value'] * 100).round(1)
        g['percentage']     = (g['purchase_value'] / total * 100).round(1)
        result['group']     = g.sort_values('purchase_value', ascending=False).head(15).to_dict(orient='records')

    if 'Product' in df.columns:
        p = df.groupby('Product').agg(
            purchase_value = ('Purchase value', 'sum'),
            deal_count     = ('Purchase value', 'count'),
        ).reset_index()
        p['purchase_value'] *= mult
        p['percentage']      = (p['purchase_value'] / total * 100).round(1)
        result['product']    = p.sort_values('purchase_value', ascending=False).to_dict(orient='records')

    if 'Discount' in df.columns:
        df2 = df.copy()
        df2['discount_pct'] = pd.to_numeric(df2['Discount'], errors='coerce')
        d = df2.groupby('discount_pct').agg(
            deal_count     = ('Purchase value', 'count'),
            purchase_value = ('Purchase value', 'sum'),
        ).reset_index()
        d['purchase_value'] *= mult
        result['discount']   = d.dropna().to_dict(orient='records')

    cols = [c for c in ['Deal date', 'Status', 'Purchase value',
                         'Discount', 'Collected till date', 'Denied by insurance']
            if c in df.columns]
    top = df.nlargest(10, 'Purchase value')[cols].copy()
    top['Purchase value'] *= mult
    if 'Collected till date'  in top.columns: top['Collected till date']  *= mult
    if 'Deal date'            in top.columns: top['Deal date']             = top['Deal date'].astype(str)
    result['top_deals'] = top.to_dict(orient='records')

    return result