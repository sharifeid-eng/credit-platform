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
    total_expected   = df['Expected total'].sum() * mult if 'Expected total' in df.columns else 0
    avg_discount     = float(df['Discount'].mean()) if 'Discount' in df.columns and len(df) else 0
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
        'total_expected':     float(total_expected),
        'avg_discount':       round(avg_discount, 4),
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


def compute_deployment_by_product(df, mult):
    """Monthly capital deployed split by product type."""
    df = add_month_column(df)
    if 'Product' not in df.columns:
        return {'monthly': [], 'products': []}

    products = sorted(df['Product'].dropna().unique().tolist())
    monthly = df.groupby('Month').agg(total=('Purchase value', 'sum')).reset_index()
    monthly['total'] *= mult

    # Pivot by product
    for prod in products:
        sub = df[df['Product'] == prod].groupby('Month')['Purchase value'].sum() * mult
        monthly = monthly.merge(
            sub.rename(prod).reset_index(),
            on='Month', how='left',
        )
        monthly[prod] = monthly[prod].fillna(0)

    return {'monthly': monthly.to_dict(orient='records'), 'products': products}


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
    """Collection breakdown by days to collect + monthly rates."""
    today = pd.Timestamp(as_of_date) if as_of_date else pd.Timestamp.now()
    completed = df[df['Status'] == 'Completed'].copy()

    # Use curve-based collection time when available (accurate),
    # else fall back to deal age from today (less accurate).
    has_curves = 'Actual in 30 days' in completed.columns
    if has_curves and len(completed) > 0:
        completed['days_to_collect'] = completed.apply(_estimate_dso_from_curves, axis=1)
        # For deals where curve-based DSO couldn't be computed, fall back to deal age
        fallback = completed['days_to_collect'].isna()
        completed.loc[fallback, 'days_to_collect'] = (today - completed.loc[fallback, 'Deal date']).dt.days
    else:
        completed['days_to_collect'] = (today - completed['Deal date']).dt.days

    buckets = []
    for label, lo, hi in AGEING_BUCKETS:
        sub = completed[(completed['days_to_collect'] >= lo) & (completed['days_to_collect'] <= hi)]
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

    # Summary stats for completed deals
    avg_days = 0
    median_days = 0
    total_completed = len(completed)
    if total_completed:
        days = completed['days_to_collect']
        collected_vals = completed['Collected till date'] * mult
        total_coll = collected_vals.sum()
        avg_days = float((days * collected_vals).sum() / total_coll) if total_coll else 0
        median_days = float(days.median())

    return {
        'buckets': buckets,
        'monthly': monthly.to_dict(orient='records'),
        'avg_days': round(avg_days, 0),
        'median_days': round(median_days, 0),
        'total_completed': total_completed,
        'curve_based': has_curves,
    }


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
        pp        = grp['Purchase price'].sum() * mult
        collected = grp['Collected till date'].sum() * mult
        denied    = grp['Denied by insurance'].sum() * mult
        pending   = grp['Pending insurance response'].sum() * mult

        row = {
            'month':            month,
            'total_deals':      int(total),
            'completed_deals':  int(completed),
            'completion_rate':  round(completed / total * 100, 1) if total else 0,
            'purchase_value':   round(pv, 2),
            'purchase_price':   round(pp, 2),
            'collected':        round(collected, 2),
            'denied':           round(denied, 2),
            'pending':          round(pending, 2),
            'collection_rate':  round(collected / pv * 100, 1) if pv else 0,
            'denial_rate':      round(denied    / pv * 100, 1) if pv else 0,
            # Calculated margins (always available)
            'expected_margin':  round((pv - pp) / pp * 100, 2) if pp else 0,
            'realised_margin':  round((collected - pp) / pp * 100, 2) if pp else 0,
        }

        if 'Expected IRR' in grp.columns:
            irr = pd.to_numeric(grp['Expected IRR'], errors='coerce')
            row['avg_expected_irr'] = round(float(irr.mean()) * 100, 1) if not irr.isna().all() else None

        if 'Actual IRR' in grp.columns:
            irr = pd.to_numeric(grp['Actual IRR'], errors='coerce')
            irr = irr[irr < 10]  # filter outliers >1000%
            row['avg_actual_irr'] = round(float(irr.mean()) * 100, 1) if not irr.isna().all() else None

        # Collection speed columns (from curve data)
        if 'Actual in 90 days' in grp.columns:
            pv_raw = grp['Purchase value'].sum()
            if pv_raw > 0:
                row['collected_90d_pct']  = round(grp['Actual in 90 days'].sum()  / pv_raw * 100, 1)
                row['collected_180d_pct'] = round(grp['Actual in 180 days'].sum() / pv_raw * 100, 1)
                row['collected_360d_pct'] = round(grp['Actual in 360 days'].sum() / pv_raw * 100, 1)
            else:
                row['collected_90d_pct']  = None
                row['collected_180d_pct'] = None
                row['collected_360d_pct'] = None

        cohorts.append(row)

    return cohorts


# ── Actual vs Expected ────────────────────────────────────────────────────────

def compute_actual_vs_expected(df, mult):
    """Cumulative collected vs forecast vs expected total.

    Three lines:
    - Collected: actual collections to date
    - Forecast: expected collections by now (Expected till date) — pacing metric
    - Expected Total: full lifetime expected — ceiling reference
    """
    has_forecast = 'Expected till date' in df.columns
    df = add_month_column(df)

    agg_dict = {
        'collected':      ('Collected till date', 'sum'),
        'expected':       ('Expected total', 'sum'),
        'purchase_value': ('Purchase value', 'sum'),
    }
    if has_forecast:
        agg_dict['forecast'] = ('Expected till date', 'sum')

    monthly = df.groupby('Month').agg(**agg_dict).reset_index()

    apply_cols = ['collected', 'expected', 'purchase_value']
    if has_forecast:
        apply_cols.append('forecast')
    for col in apply_cols:
        monthly[col] *= mult

    monthly['cumulative_collected'] = monthly['collected'].cumsum()
    monthly['cumulative_expected']  = monthly['expected'].cumsum()
    monthly['cumulative_purchase']  = monthly['purchase_value'].cumsum()
    if has_forecast:
        monthly['cumulative_forecast'] = monthly['forecast'].cumsum()

    monthly['performance_ratio'] = (
        monthly['cumulative_collected'] / monthly['cumulative_expected'] * 100
    ).round(1)

    total_collected = float(df['Collected till date'].sum() * mult)
    total_expected  = float(df['Expected total'].sum() * mult)
    total_forecast  = float(df['Expected till date'].sum() * mult) if has_forecast else None

    # Pacing = collected vs forecast (time-based); recovery = collected vs expected total
    pacing_pct = round(total_collected / total_forecast * 100, 1) if total_forecast else None

    return {
        'data':                monthly.to_dict(orient='records'),
        'total_collected':     total_collected,
        'total_expected':      total_expected,
        'total_forecast':      total_forecast,
        'has_forecast':        has_forecast,
        'overall_performance': round(total_collected / total_expected * 100, 1) if total_expected else 0,
        'pacing_pct':          pacing_pct,
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
    """Active deal health + ageing bucket breakdown.

    Uses outstanding amount (Purchase value - Collected - Denied) as the
    primary size metric rather than face value, so the chart reflects
    actual risk exposure not total deal size.
    """
    today  = pd.Timestamp(as_of_date) if as_of_date else pd.Timestamp.now()
    active = df[df['Status'] == 'Executed'].copy()
    active['days_outstanding'] = (today - active['Deal date']).dt.days
    active['health']           = active['days_outstanding'].apply(classify_health)

    # Outstanding = face value minus what's already been collected or denied
    active['outstanding'] = (
        active['Purchase value']
        - active['Collected till date'].fillna(0)
        - active['Denied by insurance'].fillna(0)
    ).clip(lower=0)

    ageing = []
    for label, lo, hi in EXTENDED_AGEING_BUCKETS:
        sub = active[(active['days_outstanding'] >= lo) & (active['days_outstanding'] <= hi)]
        ageing.append({
            'bucket':         label,
            'deal_count':     int(len(sub)),
            'outstanding':    float(sub['outstanding'].sum() * mult),
            'purchase_value': float(sub['Purchase value'].sum() * mult),
        })

    total_outstanding = float(active['outstanding'].sum() * mult)

    health_summary = []
    for status, color in HEALTH_COLORS.items():
        sub = active[active['health'] == status]
        out = float(sub['outstanding'].sum() * mult)
        health_summary.append({
            'status':     status,
            'deal_count': int(len(sub)),
            'value':      out,
            'face_value': float(sub['Purchase value'].sum() * mult),
            'percentage': round(out / total_outstanding * 100, 1) if total_outstanding else 0,
            'color':      color,
        })

    df2 = add_month_column(active)

    # Monthly breakdown by health status (for stacked bar chart over time)
    monthly_health = []
    for month, grp in df2.groupby('Month'):
        row = {'Month': month}
        for status in ['Healthy', 'Watch', 'Delayed', 'Poor']:
            sub = grp[grp['health'] == status]
            row[status] = float(sub['outstanding'].sum() * mult)
        row['total'] = float(grp['outstanding'].sum() * mult)
        monthly_health.append(row)

    return {
        'ageing_buckets':     ageing,
        'health_summary':     health_summary,
        'monthly_health':     monthly_health,
        'total_active_deals': int(len(active)),
        'total_active_value': float(active['Purchase value'].sum() * mult),
        'total_outstanding':  total_outstanding,
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

def compute_returns_analysis(df, mult):
    """Returns analysis: margins, discount performance, fee income, provisions."""
    df = add_month_column(df)

    has_setup = 'Setup fee' in df.columns
    has_other = 'Other fee' in df.columns
    has_prov  = 'Provisions' in df.columns
    has_adj   = 'Adjustments' in df.columns

    # ── Portfolio-level summary ──
    total_pv        = df['Purchase value'].sum() * mult
    total_pp        = df['Purchase price'].sum() * mult
    total_collected = df['Collected till date'].sum() * mult
    total_denied    = df['Denied by insurance'].sum() * mult
    total_pending   = df['Pending insurance response'].sum() * mult
    total_gross_rev = df['Gross revenue'].sum() * mult if 'Gross revenue' in df.columns else 0
    total_setup     = df['Setup fee'].sum() * mult if has_setup else 0
    total_other     = df['Other fee'].sum() * mult if has_other else 0
    total_prov      = df['Provisions'].sum() * mult if has_prov else 0
    total_adj       = df['Adjustments'].sum() * mult if has_adj else 0

    realised_margin = (total_collected - total_pp) / total_pp * 100 if total_pp else 0
    expected_margin = (total_pv - total_pp) / total_pp * 100 if total_pp else 0
    fee_yield       = (total_setup + total_other) / total_pv * 100 if total_pv else 0

    completed = df[df['Status'] == 'Completed']
    comp_pv   = completed['Purchase value'].sum() * mult
    comp_pp   = completed['Purchase price'].sum() * mult
    comp_coll = completed['Collected till date'].sum() * mult
    comp_denied = completed['Denied by insurance'].sum() * mult
    comp_margin = (comp_coll - comp_pp) / comp_pp * 100 if comp_pp else 0
    comp_loss   = comp_denied / comp_pv * 100 if comp_pv else 0

    summary = {
        'total_deployed':       round(total_pp, 2),
        'total_face_value':     round(total_pv, 2),
        'avg_discount':         round(float(df['Discount'].mean()) * 100, 2),
        'weighted_avg_discount': round(float((df['Discount'] * df['Purchase value']).sum() / total_pv * mult * 100), 2) if total_pv else 0,
        'expected_margin':      round(expected_margin, 2),
        'realised_margin':      round(realised_margin, 2),
        'completed_margin':     round(comp_margin, 2),
        'completed_loss_rate':  round(comp_loss, 2),
        'fee_yield':            round(fee_yield, 2),
        'total_fees':           round(total_setup + total_other, 2),
        'provision_coverage':   round(total_prov / total_denied * 100, 2) if total_denied else 0,
        'total_provisions':     round(total_prov, 2),
        'total_adjustments':    round(total_adj, 2),
    }

    # ── Monthly returns ──
    monthly_rows = []
    for month, grp in df.groupby('Month'):
        pv   = grp['Purchase value'].sum() * mult
        pp   = grp['Purchase price'].sum() * mult
        coll = grp['Collected till date'].sum() * mult
        den  = grp['Denied by insurance'].sum() * mult
        gr   = grp['Gross revenue'].sum() * mult if 'Gross revenue' in grp.columns else 0
        sf   = grp['Setup fee'].sum() * mult if has_setup else 0
        of_  = grp['Other fee'].sum() * mult if has_other else 0
        prov = grp['Provisions'].sum() * mult if has_prov else 0

        monthly_rows.append({
            'month':             month,
            'deployed':          round(pp, 2),
            'face_value':        round(pv, 2),
            'collected':         round(coll, 2),
            'denied':            round(den, 2),
            'gross_revenue':     round(gr, 2),
            'realised_margin':   round((coll - pp) / pp * 100, 2) if pp else 0,
            'expected_margin':   round((pv - pp) / pp * 100, 2) if pp else 0,
            'avg_discount':      round(float(grp['Discount'].mean()) * 100, 2),
            'collection_rate':   round(coll / pv * 100, 1) if pv else 0,
            'fee_income':        round(sf + of_, 2),
            'provisions':        round(prov, 2),
        })

    # ── Discount band analysis ──
    df['discount_band'] = pd.cut(
        df['Discount'],
        bins=[0, 0.04, 0.06, 0.08, 0.10, 0.15, 1.0],
        labels=['≤4%', '4-6%', '6-8%', '8-10%', '10-15%', '>15%'],
        include_lowest=True,
    )
    discount_bands = []
    for band, grp in df.groupby('discount_band', observed=True):
        pv   = grp['Purchase value'].sum() * mult
        pp   = grp['Purchase price'].sum() * mult
        coll = grp['Collected till date'].sum() * mult
        den  = grp['Denied by insurance'].sum() * mult
        discount_bands.append({
            'band':            str(band),
            'deals':           len(grp),
            'face_value':      round(pv, 2),
            'deployed':        round(pp, 2),
            'collected':       round(coll, 2),
            'collection_rate': round(coll / pv * 100, 1) if pv else 0,
            'denial_rate':     round(den / pv * 100, 1) if pv else 0,
            'margin':          round((coll - pp) / pp * 100, 2) if pp else 0,
            'avg_discount':    round(float(grp['Discount'].mean()) * 100, 2),
        })

# ── New vs Repeat ──
    new_repeat = []
    if 'New business' in df.columns:
        # Map to binary: any truthy value = "New", falsy (NaN/empty/0) = "Repeat"
        df['_biz_type'] = df['New business'].apply(
            lambda x: 'New' if pd.notna(x) and x != '' and x != 0 else 'Repeat'
        )
        for biz_type, grp in df.groupby('_biz_type'):
            pv   = grp['Purchase value'].sum() * mult
            pp   = grp['Purchase price'].sum() * mult
            coll = grp['Collected till date'].sum() * mult
            den  = grp['Denied by insurance'].sum() * mult
            comp = grp[grp['Status'] == 'Completed']
            new_repeat.append({
                'type':            biz_type,
                'deals':           len(grp),
                'face_value':      round(pv, 2),
                'deployed':        round(pp, 2),
                'collected':       round(coll, 2),
                'collection_rate': round(coll / pv * 100, 1) if pv else 0,
                'denial_rate':     round(den / pv * 100, 1) if pv else 0,
                'margin':          round((coll - pp) / pp * 100, 2) if pp else 0,
                'completion_rate': round(len(comp) / len(grp) * 100, 1) if len(grp) else 0,
            })
        df.drop(columns=['_biz_type'], inplace=True)

    # ── IRR Analysis (only when tape has IRR columns) ──
    has_irr = 'Expected IRR' in df.columns and 'Actual IRR' in df.columns
    summary['has_irr'] = has_irr

    irr_by_vintage = []
    irr_distribution = []

    if has_irr:
        # Filter outliers: |Actual IRR| >= 10 (1000%)
        valid_irr = df[df['Actual IRR'].between(-10, 10, inclusive='neither')].copy()

        avg_exp_irr = float(valid_irr['Expected IRR'].mean() * 100)
        avg_act_irr = float(valid_irr['Actual IRR'].mean() * 100)
        med_act_irr = float(valid_irr['Actual IRR'].median() * 100)

        summary['avg_expected_irr'] = round(avg_exp_irr, 2)
        summary['avg_actual_irr']   = round(avg_act_irr, 2)
        summary['irr_spread']       = round(avg_act_irr - avg_exp_irr, 2)
        summary['median_actual_irr']= round(med_act_irr, 2)

        # IRR by vintage
        valid_irr = add_month_column(valid_irr)
        for month, grp in valid_irr.groupby('Month'):
            exp = float(grp['Expected IRR'].mean() * 100)
            act = float(grp['Actual IRR'].mean() * 100)
            irr_by_vintage.append({
                'month':            month,
                'avg_expected_irr': round(exp, 2),
                'avg_actual_irr':   round(act, 2),
                'spread':           round(act - exp, 2),
                'deal_count':       int(len(grp)),
            })

        # IRR distribution histogram
        act_irr_pct = valid_irr['Actual IRR'] * 100
        bins = [0, 10, 20, 30, 40, 50, 60, 80, 100, 200, float('inf')]
        labels = ['0-10%', '10-20%', '20-30%', '30-40%', '40-50%',
                  '50-60%', '60-80%', '80-100%', '100-200%', '>200%']
        binned = pd.cut(act_irr_pct, bins=bins, labels=labels, right=False)
        for bucket, count in binned.value_counts().sort_index().items():
            if count > 0:
                irr_distribution.append({'bucket': str(bucket), 'count': int(count)})

    return {
        'summary':          summary,
        'monthly':          monthly_rows,
        'discount_bands':   discount_bands,
        'new_vs_repeat':    new_repeat,
        'irr_by_vintage':   irr_by_vintage,
        'irr_distribution': irr_distribution,
    }


# ── DSO (Days Sales Outstanding) ─────────────────────────────────────────────

CURVE_INTERVALS = [30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330, 360, 390]


def _estimate_dso_from_curves(row):
    """Estimate true DSO for a single deal using collection curve columns.

    Finds the first 30-day interval where actual collection reaches ≥90%
    of the deal's total collected amount, then interpolates.
    Returns NaN if data is insufficient.
    """
    total_collected = row.get('Collected till date', 0)
    if total_collected <= 0:
        return np.nan

    target = total_collected * 0.90
    prev_days = 0
    prev_val = 0

    for days in CURVE_INTERVALS:
        col = f'Actual in {days} days'
        val = row.get(col, 0) or 0
        if val >= target:
            # Interpolate between prev_days and days
            if val == prev_val:
                return float(days)
            fraction = (target - prev_val) / (val - prev_val)
            return float(prev_days + fraction * (days - prev_days))
        prev_days = days
        prev_val = val

    # Never reached 90% within 390 days
    return np.nan


def compute_dso(df, mult, as_of_date=None):
    """Weighted average days to collect on completed deals + DSO by vintage.

    Uses collection curve columns (Actual in X days) when available for
    accurate DSO. Returns available=False when curves are missing so the
    frontend can hide rather than show inaccurate estimates.
    """
    has_curves = 'Actual in 30 days' in df.columns
    completed = df[df['Status'] == 'Completed'].copy()

    if completed.empty:
        return {
            'available': has_curves,
            'weighted_dso': 0, 'median_dso': 0, 'p95_dso': 0,
            'total_completed': 0, 'by_vintage': [],
        }

    if not has_curves:
        # No curve data — return unavailable so frontend hides DSO
        return {
            'available': False,
            'weighted_dso': 0, 'median_dso': 0, 'p95_dso': 0,
            'total_completed': int(len(completed)),
            'by_vintage': [],
        }

    # Curve-based DSO — accurate measurement
    completed['true_dso'] = completed.apply(_estimate_dso_from_curves, axis=1)
    valid = completed.dropna(subset=['true_dso'])

    if valid.empty:
        return {
            'available': True,
            'weighted_dso': 0, 'median_dso': 0, 'p95_dso': 0,
            'total_completed': int(len(completed)),
            'by_vintage': [],
        }

    collected_vals = valid['Collected till date'] * mult
    days_vals = valid['true_dso']
    total_coll = collected_vals.sum()

    weighted_dso = float((days_vals * collected_vals).sum() / total_coll) if total_coll else 0
    median_dso = float(days_vals.median())
    p95_dso = float(days_vals.quantile(0.95))

    # DSO by vintage month
    valid = add_month_column(valid)
    by_vintage = []
    for month, grp in valid.groupby('Month'):
        g_coll = grp['Collected till date'] * mult
        g_days = grp['true_dso']
        g_total = g_coll.sum()
        by_vintage.append({
            'month':        month,
            'weighted_dso': round(float((g_days * g_coll).sum() / g_total), 1) if g_total else 0,
            'median_dso':   round(float(g_days.median()), 1),
            'deal_count':   int(len(grp)),
            'collected':    round(float(g_total), 2),
        })

    return {
        'available':       True,
        'weighted_dso':    round(weighted_dso, 1),
        'median_dso':      round(median_dso, 1),
        'p95_dso':         round(p95_dso, 1),
        'total_completed': int(len(completed)),
        'by_vintage':      by_vintage,
    }


# ── HHI (Herfindahl-Hirschman Index) ─────────────────────────────────────────

def compute_hhi(df, mult):
    """HHI concentration indices on Group and Product + top-N exposure caps."""
    total = df['Purchase value'].sum() * mult
    result = {}

    for col_name, key in [('Group', 'group'), ('Product', 'product')]:
        if col_name not in df.columns:
            continue
        agg = df.groupby(col_name)['Purchase value'].sum() * mult
        shares = agg / total
        hhi = float((shares ** 2).sum())
        sorted_shares = shares.sort_values(ascending=False)
        result[key] = {
            'hhi':       round(hhi, 4),
            'top_1_pct': round(float(sorted_shares.iloc[0]) * 100, 1) if len(sorted_shares) >= 1 else 0,
            'top_5_pct': round(float(sorted_shares.head(5).sum()) * 100, 1) if len(sorted_shares) >= 5 else round(float(sorted_shares.sum()) * 100, 1),
            'top_10_pct': round(float(sorted_shares.head(10).sum()) * 100, 1) if len(sorted_shares) >= 10 else round(float(sorted_shares.sum()) * 100, 1),
            'count':      int(len(sorted_shares)),
            'max_name':   str(sorted_shares.index[0]) if len(sorted_shares) >= 1 else '',
            'max_value':  round(float(agg.max()), 2) if len(agg) else 0,
        }

    return result


# ── Denial Funnel ─────────────────────────────────────────────────────────────

def compute_denial_funnel(df, mult):
    """Resolution pipeline: Total → Collected → Pending → Denied → Provisioned."""
    total_pv    = df['Purchase value'].sum() * mult
    collected   = df['Collected till date'].sum() * mult
    pending     = df['Pending insurance response'].sum() * mult
    denied      = df['Denied by insurance'].sum() * mult
    provisions  = df['Provisions'].sum() * mult if 'Provisions' in df.columns else 0
    # Unresolved = total - collected - denied - pending
    unresolved  = max(total_pv - collected - denied - pending, 0)

    stages = [
        {'stage': 'Total Portfolio',  'amount': round(total_pv, 2),   'pct': 100.0},
        {'stage': 'Collected',        'amount': round(collected, 2),  'pct': round(collected / total_pv * 100, 1) if total_pv else 0},
        {'stage': 'Pending Response', 'amount': round(pending, 2),   'pct': round(pending / total_pv * 100, 1) if total_pv else 0},
        {'stage': 'Denied',           'amount': round(denied, 2),    'pct': round(denied / total_pv * 100, 1) if total_pv else 0},
        {'stage': 'Provisioned',      'amount': round(provisions, 2),'pct': round(provisions / total_pv * 100, 1) if total_pv else 0},
    ]

    # Net loss = denied - provisions (unrecovered)
    net_loss = denied - provisions
    recovery_rate = round(provisions / denied * 100, 1) if denied else 0

    return {
        'stages':        stages,
        'net_loss':      round(net_loss, 2),
        'recovery_rate': recovery_rate,
        'unresolved':    round(unresolved, 2),
    }


# ── Stress Testing ───────────────────────────────────────────────────────────

def compute_stress_test(df, mult):
    """Provider/group shock simulation across multiple scenarios."""
    if 'Group' not in df.columns:
        return {'scenarios': [], 'error': 'No Group column available'}

    total_pv = df['Purchase value'].sum() * mult
    total_collected = df['Collected till date'].sum() * mult
    base_collection_rate = round(total_collected / total_pv * 100, 1) if total_pv else 0

    group_exposure = df.groupby('Group').agg(
        purchase_value = ('Purchase value', 'sum'),
        collected      = ('Collected till date', 'sum'),
    ).sort_values('purchase_value', ascending=False)
    group_exposure['purchase_value'] *= mult
    group_exposure['collected'] *= mult

    scenarios = []
    configs = [
        ('Top 1 provider — 50% haircut',  1, 0.50),
        ('Top 3 providers — 30% haircut', 3, 0.30),
        ('Top 5 providers — 20% haircut', 5, 0.20),
    ]

    for label, top_n, haircut_pct in configs:
        top_groups = group_exposure.head(top_n)
        affected_pv = top_groups['purchase_value'].sum()
        affected_collected = top_groups['collected'].sum()
        loss = affected_collected * haircut_pct

        stressed_collected = total_collected - loss
        stressed_rate = round(stressed_collected / total_pv * 100, 1) if total_pv else 0

        scenarios.append({
            'scenario':              label,
            'affected_groups':       list(top_groups.index[:top_n]),
            'affected_exposure':     round(affected_pv, 2),
            'affected_pct':          round(affected_pv / total_pv * 100, 1) if total_pv else 0,
            'collection_loss':       round(loss, 2),
            'base_collection_rate':  base_collection_rate,
            'stressed_collection_rate': stressed_rate,
            'rate_impact':           round(stressed_rate - base_collection_rate, 1),
            'portfolio_value_retained': round((total_pv - loss) / total_pv * 100, 1) if total_pv else 0,
        })

    return {
        'base_portfolio_value':     round(total_pv, 2),
        'base_collection_rate':     base_collection_rate,
        'total_groups':             int(len(group_exposure)),
        'scenarios':                scenarios,
    }


# ── Expected Loss Model ──────────────────────────────────────────────────────

def compute_expected_loss(df, mult):
    """EL = PD × LGD × Exposure derived from completed deal outcomes."""
    df = add_month_column(df)
    has_prov = 'Provisions' in df.columns

    # Portfolio-level EL
    completed = df[df['Status'] == 'Completed']
    total_completed_pv = completed['Purchase value'].sum() * mult
    total_denied = completed['Denied by insurance'].sum() * mult
    total_provisions = completed['Provisions'].sum() * mult if has_prov else 0

    # PD = probability a completed deal has material denial (>1% of PV)
    if len(completed):
        denied_deals = completed[completed['Denied by insurance'] > completed['Purchase value'] * 0.01]
        pd_rate = len(denied_deals) / len(completed)
    else:
        pd_rate = 0

    # LGD = (denied - recovered/provisioned) / denied
    if total_denied > 0:
        lgd = (total_denied - total_provisions) / total_denied
    else:
        lgd = 0

    # EAD (Exposure at Default) — active deals
    active = df[df['Status'] == 'Executed']
    ead = active['Purchase value'].sum() * mult

    el_amount = pd_rate * lgd * ead
    el_rate = round(el_amount / ead * 100, 2) if ead else 0

    # By vintage
    by_vintage = []
    for month, grp in df.groupby('Month'):
        comp = grp[grp['Status'] == 'Completed']
        act = grp[grp['Status'] == 'Executed']
        comp_pv = comp['Purchase value'].sum() * mult
        comp_denied = comp['Denied by insurance'].sum() * mult
        comp_prov = comp['Provisions'].sum() * mult if has_prov else 0

        v_pd = 0
        if len(comp):
            v_denied_deals = comp[comp['Denied by insurance'] > comp['Purchase value'] * 0.01]
            v_pd = len(v_denied_deals) / len(comp)

        v_lgd = (comp_denied - comp_prov) / comp_denied if comp_denied else 0
        v_ead = act['Purchase value'].sum() * mult
        v_el = v_pd * v_lgd * v_ead

        by_vintage.append({
            'month':      month,
            'pd':         round(v_pd * 100, 2),
            'lgd':        round(v_lgd * 100, 2),
            'ead':        round(v_ead, 2),
            'el':         round(v_el, 2),
            'el_rate':    round(v_el / v_ead * 100, 2) if v_ead else 0,
            'completed':  int(len(comp)),
            'active':     int(len(act)),
        })

    return {
        'portfolio': {
            'pd':               round(pd_rate * 100, 2),
            'lgd':              round(lgd * 100, 2),
            'ead':              round(ead, 2),
            'el':               round(el_amount, 2),
            'el_rate':          el_rate,
            'completed_deals':  int(len(completed)),
            'denied_amount':    round(total_denied, 2),
            'provisions':       round(total_provisions, 2),
        },
        'by_vintage': by_vintage,
    }


# ── Loss Development Triangle ────────────────────────────────────────────────

def compute_loss_triangle(df, mult):
    """Denial development triangle by vintage age (months since origination)."""
    df = add_month_column(df)

    # For each vintage, compute cumulative denial rate
    # Since we only have one snapshot, we use deal age as a proxy for development
    # Group deals by vintage month and age bucket (months since origination)
    if 'Deal date' not in df.columns:
        return {'triangle': [], 'vintages': []}

    today = df['Deal date'].max()  # use latest deal date as reference
    df2 = df.copy()
    df2['months_since_orig'] = ((today - df2['Deal date']).dt.days / 30.44).astype(int)

    triangle = []
    for month, grp in df2.groupby('Month'):
        pv = grp['Purchase value'].sum() * mult
        denied = grp['Denied by insurance'].sum() * mult
        collected = grp['Collected till date'].sum() * mult
        pending = grp['Pending insurance response'].sum() * mult
        avg_age = grp['months_since_orig'].mean()

        triangle.append({
            'vintage':          month,
            'deal_count':       int(len(grp)),
            'purchase_value':   round(pv, 2),
            'denial_rate':      round(denied / pv * 100, 2) if pv else 0,
            'collection_rate':  round(collected / pv * 100, 2) if pv else 0,
            'pending_rate':     round(pending / pv * 100, 2) if pv else 0,
            'loss_rate':        round(denied / pv * 100, 2) if pv else 0,
            'avg_age_months':   round(avg_age, 1),
            'resolved_pct':     round((collected + denied) / pv * 100, 1) if pv else 0,
        })

    return {'triangle': triangle}


# ── Group / Provider Performance ──────────────────────────────────────────────

def compute_group_performance(df, mult, as_of_date=None):
    """Per-group metrics: collection rate, denial rate, DSO, deal count, pending %."""
    if 'Group' not in df.columns:
        return {'groups': []}

    today = pd.Timestamp(as_of_date) if as_of_date else pd.Timestamp.now()
    groups = []

    for name, grp in df.groupby('Group'):
        pv        = grp['Purchase value'].sum() * mult
        collected = grp['Collected till date'].sum() * mult
        denied    = grp['Denied by insurance'].sum() * mult
        pending   = grp['Pending insurance response'].sum() * mult
        total     = len(grp)
        completed = grp[grp['Status'] == 'Completed']
        active    = grp[grp['Status'] == 'Executed']

        # DSO for completed deals in this group
        dso = 0
        if len(completed):
            comp_days = (today - completed['Deal date']).dt.days
            comp_coll = completed['Collected till date'] * mult
            dso_total = comp_coll.sum()
            dso = float((comp_days * comp_coll).sum() / dso_total) if dso_total else 0

        groups.append({
            'group':           str(name),
            'deal_count':      int(total),
            'purchase_value':  round(pv, 2),
            'collected':       round(collected, 2),
            'denied':          round(denied, 2),
            'pending':         round(pending, 2),
            'collection_rate': round(collected / pv * 100, 1) if pv else 0,
            'denial_rate':     round(denied / pv * 100, 1) if pv else 0,
            'pending_rate':    round(pending / pv * 100, 1) if pv else 0,
            'completion_rate': round(len(completed) / total * 100, 1) if total else 0,
            'active_deals':    int(len(active)),
            'dso':             round(dso, 1),
        })

    groups.sort(key=lambda x: x['purchase_value'], reverse=True)

    return {'groups': groups}


# ── Collection Curves ────────────────────────────────────────────────────────

def compute_collection_curves(df, mult):
    """Expected vs actual collection curves at 30-day intervals by vintage.

    Uses 'Expected in X days' and 'Actual in X days' columns (cumulative amounts).
    Returns available=False when columns are missing.
    """
    if 'Expected in 30 days' not in df.columns:
        return {'available': False, 'curves': [], 'aggregate': {'points': []}}

    df = add_month_column(df)
    intervals = CURVE_INTERVALS

    # Per-vintage curves
    curves = []
    for month, grp in df.groupby('Month'):
        total_pv = grp['Purchase value'].sum()
        if total_pv <= 0:
            continue

        points = []
        for days in intervals:
            exp_col = f'Expected in {days} days'
            act_col = f'Actual in {days} days'
            exp_val = grp[exp_col].sum() if exp_col in grp.columns else 0
            act_val = grp[act_col].sum() if act_col in grp.columns else 0

            points.append({
                'days':         days,
                'expected_pct': round(exp_val / total_pv * 100, 1),
                'actual_pct':   round(act_val / total_pv * 100, 1),
            })

        curves.append({
            'month':          month,
            'total_deals':    int(len(grp)),
            'purchase_value': round(total_pv * mult, 2),
            'points':         points,
        })

    # Portfolio-wide aggregate curve
    total_pv = df['Purchase value'].sum()
    agg_points = []
    for days in intervals:
        exp_col = f'Expected in {days} days'
        act_col = f'Actual in {days} days'
        exp_val = df[exp_col].sum() if exp_col in df.columns else 0
        act_val = df[act_col].sum() if act_col in df.columns else 0

        accuracy = round(act_val / exp_val * 100, 1) if exp_val > 0 else 0

        agg_points.append({
            'days':         days,
            'expected_pct': round(exp_val / total_pv * 100, 1) if total_pv else 0,
            'actual_pct':   round(act_val / total_pv * 100, 1) if total_pv else 0,
            'accuracy':     accuracy,
        })

    return {
        'available':  True,
        'curves':     curves,
        'aggregate':  {'points': agg_points},
    }


# ── Owner / SPV Breakdown ───────────────────────────────────────────────────

def compute_owner_breakdown(df, mult):
    """Capital deployment and performance by Owner (SPV entity).

    Uses 'Collected till date by owner' when available for accurate
    per-owner attribution, falling back to 'Collected till date'.
    """
    if 'Owner' not in df.columns:
        return {'available': False, 'owners': []}

    has_owner_collected = 'Collected till date by owner' in df.columns
    coll_col = 'Collected till date by owner' if has_owner_collected else 'Collected till date'
    total_pv = df['Purchase value'].sum() * mult

    owners = []
    for name, grp in df.groupby('Owner'):
        pv        = grp['Purchase value'].sum() * mult
        collected = grp[coll_col].sum() * mult
        denied    = grp['Denied by insurance'].sum() * mult
        pending   = grp['Pending insurance response'].sum() * mult

        owners.append({
            'owner':           str(name),
            'deal_count':      int(len(grp)),
            'purchase_value':  round(pv, 2),
            'collected':       round(collected, 2),
            'denied':          round(denied, 2),
            'pending':         round(pending, 2),
            'collection_rate': round(collected / pv * 100, 1) if pv else 0,
            'denial_rate':     round(denied / pv * 100, 1) if pv else 0,
            'percentage':      round(pv / total_pv * 100, 1) if total_pv else 0,
        })

    owners.sort(key=lambda x: x['purchase_value'], reverse=True)

    return {
        'available': True,
        'owners':    owners,
        'uses_owner_collected': has_owner_collected,
    }


# ── VAT Analysis ─────────────────────────────────────────────────────────────

def compute_vat_summary(df, mult):
    """VAT summary for revenue tab enrichment."""
    has_vat_assets = 'VAT on purchased assets' in df.columns
    has_vat_fees   = 'VAT on fees' in df.columns

    if not has_vat_assets and not has_vat_fees:
        return {'available': False}

    vat_assets = df['VAT on purchased assets'].sum() * mult if has_vat_assets else 0
    vat_fees   = df['VAT on fees'].sum() * mult if has_vat_fees else 0
    total_vat  = vat_assets + vat_fees

    return {
        'available':  True,
        'vat_assets': round(vat_assets, 2),
        'vat_fees':   round(vat_fees, 2),
        'total_vat':  round(total_vat, 2),
    }