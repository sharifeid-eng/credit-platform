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
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return '—'
    if abs(v) >= 1e6:
        return f"{v / 1e6:.1f}M"
    if abs(v) >= 1e3:
        return f"{v / 1e3:.0f}K"
    return f"{v:.0f}"


def apply_multiplier(config, display_currency):
    """Return the USD conversion multiplier if needed, else 1.0."""
    from core.config import get_fx_rates
    if not config:
        return 1.0
    reported = config.get('currency', 'USD')
    rates = get_fx_rates()
    rate = rates.get(reported, 1.0)
    if display_currency == 'USD' and reported != 'USD':
        return rate
    return 1.0


def filter_by_date(df, as_of_date=None):
    """Filter DataFrame to deals on or before as_of_date.

    Returns a copy — never mutates the input DataFrame.
    """
    if 'Deal date' in df.columns:
        df = df.copy()
        df['Deal date'] = pd.to_datetime(df['Deal date'], errors='coerce')
        if as_of_date:
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
    from core.config import get_fx_rates
    usd_rate = get_fx_rates().get(reported_currency, 1.0)

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

    has_forecast = 'Expected till date' in df.columns

    df = add_month_column(df)
    agg_dict = {
        'collected':      ('Collected till date', 'sum'),
        'purchase_value': ('Purchase value', 'sum'),
        'denied':         ('Denied by insurance', 'sum'),
        'pending':        ('Pending insurance response', 'sum'),
    }
    if has_forecast:
        agg_dict['expected_till_date'] = ('Expected till date', 'sum')

    monthly = df.groupby('Month').agg(**agg_dict).reset_index()
    mult_cols = ['collected', 'purchase_value', 'denied', 'pending']
    if has_forecast:
        mult_cols.append('expected_till_date')
    for col in mult_cols:
        monthly[col] *= mult
    monthly['collection_rate'] = (
        monthly['collected'] / monthly['purchase_value'] * 100
    ).round(1)
    if has_forecast:
        monthly['expected_rate'] = (
            monthly['expected_till_date'] / monthly['purchase_value'] * 100
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
        'has_forecast': has_forecast,
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

    monthly['realised_revenue'] = np.where(
        monthly['purchase_value'] > 0,
        monthly['gross_revenue'] * (monthly['collected'] / monthly['purchase_value']),
        0,
    )
    monthly['realised_revenue'] = monthly['realised_revenue'].replace([np.inf, -np.inf], 0)
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

    expected_margin  = (total_pv - total_pp) / total_pp * 100 if total_pp else 0
    capital_recovery = total_collected / total_pp * 100 if total_pp else 0
    fee_yield        = (total_setup + total_other) / total_pv * 100 if total_pv else 0

    completed   = df[df['Status'] == 'Completed']
    comp_pv     = completed['Purchase value'].sum() * mult
    comp_pp     = completed['Purchase price'].sum() * mult
    comp_coll   = completed['Collected till date'].sum() * mult
    comp_denied = completed['Denied by insurance'].sum() * mult
    comp_margin = (comp_coll - comp_pp) / comp_pp * 100 if comp_pp else 0
    comp_loss   = comp_denied / comp_pv * 100 if comp_pv else 0

    summary = {
        'total_deployed':       round(total_pp, 2),
        'total_face_value':     round(total_pv, 2),
        'avg_discount':         round(float(df['Discount'].mean()) * 100, 2),
        'weighted_avg_discount': round(float((df['Discount'] * df['Purchase value']).sum() / df['Purchase value'].sum() * 100), 2) if df['Purchase value'].sum() else 0,
        'expected_margin':      round(expected_margin, 2),
        'realised_margin':      round(comp_margin, 2),
        'capital_recovery':     round(capital_recovery, 2),
        'completed_margin':     round(comp_margin, 2),
        'completed_loss_rate':  round(comp_loss, 2),
        'fee_yield':            round(fee_yield, 2),
        'total_fees':           round(total_setup + total_other, 2),
        'provision_coverage':   round(total_prov / total_denied * 100, 2) if total_denied else 0,
        'total_provisions':     round(total_prov, 2),
        'total_adjustments':    round(total_adj, 2),
    }

    # ── Monthly returns (margin based on completed deals per vintage) ──
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

        # Margin on completed deals only (avoids penalising vintages still collecting)
        comp_grp  = grp[grp['Status'] == 'Completed']
        c_pp      = comp_grp['Purchase price'].sum() * mult
        c_coll    = comp_grp['Collected till date'].sum() * mult
        comp_pct  = round(len(comp_grp) / len(grp) * 100, 1) if len(grp) else 0

        monthly_rows.append({
            'month':             month,
            'deployed':          round(pp, 2),
            'face_value':        round(pv, 2),
            'collected':         round(coll, 2),
            'denied':            round(den, 2),
            'gross_revenue':     round(gr, 2),
            'realised_margin':   round((c_coll - c_pp) / c_pp * 100, 2) if c_pp else 0,
            'expected_margin':   round((pv - pp) / pp * 100, 2) if pp else 0,
            'avg_discount':      round(float(grp['Discount'].mean()) * 100, 2),
            'collection_rate':   round(coll / pv * 100, 1) if pv else 0,
            'completion_pct':    comp_pct,
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
        # Margin on completed deals only
        comp_grp = grp[grp['Status'] == 'Completed']
        c_pp     = comp_grp['Purchase price'].sum() * mult
        c_coll   = comp_grp['Collected till date'].sum() * mult
        discount_bands.append({
            'band':            str(band),
            'deals':           len(grp),
            'face_value':      round(pv, 2),
            'deployed':        round(pp, 2),
            'collected':       round(coll, 2),
            'collection_rate': round(coll / pv * 100, 1) if pv else 0,
            'denial_rate':     round(den / pv * 100, 1) if pv else 0,
            'margin':          round((c_coll - c_pp) / c_pp * 100, 2) if c_pp else 0,
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
            # Margin on completed deals only
            c_pp   = comp['Purchase price'].sum() * mult
            c_coll = comp['Collected till date'].sum() * mult
            new_repeat.append({
                'type':            biz_type,
                'deals':           len(grp),
                'face_value':      round(pv, 2),
                'deployed':        round(pp, 2),
                'collected':       round(coll, 2),
                'collection_rate': round(coll / pv * 100, 1) if pv else 0,
                'denial_rate':     round(den / pv * 100, 1) if pv else 0,
                'margin':          round((c_coll - c_pp) / c_pp * 100, 2) if c_pp else 0,
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

    # DSO Operational — days from expected due date to actual collection
    dso_ops = {'dso_operational_available': False}
    if 'Expected collection days' in df.columns and len(valid) > 0:
        # Direct method: operational delay = true_dso - expected_collection_days per deal
        valid_copy = valid.copy()
        exp_days = valid_copy['Expected collection days'].fillna(0).astype(float)
        valid_copy['dso_operational'] = (valid_copy['true_dso'] - exp_days).clip(lower=0)
        ops_vals = valid_copy['dso_operational']
        ops_coll = valid_copy['Collected till date'] * mult
        ops_total = ops_coll.sum()
        dso_ops = {
            'dso_operational_available': True,
            'dso_operational_method': 'direct',
            'dso_operational_weighted': round(float((ops_vals * ops_coll).sum() / ops_total), 1) if ops_total else 0,
            'dso_operational_median': round(float(ops_vals.median()), 1),
        }
    elif 'Expected till date' in df.columns and has_curves and len(valid) > 0:
        # Proxy method: operational delay = true_dso - (median_term * 0.5)
        if 'Deal date' in valid.columns:
            valid_copy = valid.copy()
            today = pd.Timestamp(as_of_date) if as_of_date else pd.Timestamp.now()
            valid_copy['deal_age'] = (today - valid_copy['Deal date']).dt.days
            median_term = float(valid_copy['deal_age'].median())
            valid_copy['dso_operational'] = (valid_copy['true_dso'] - median_term * 0.5).clip(lower=0)
            ops_vals = valid_copy['dso_operational']
            ops_coll = valid_copy['Collected till date'] * mult
            ops_total = ops_coll.sum()
            dso_ops = {
                'dso_operational_available': True,
                'dso_operational_method': 'proxy',
                'dso_operational_weighted': round(float((ops_vals * ops_coll).sum() / ops_total), 1) if ops_total else 0,
                'dso_operational_median': round(float(ops_vals.median()), 1),
            }

    return {
        'available':       True,
        'weighted_dso':    round(weighted_dso, 1),
        'median_dso':      round(median_dso, 1),
        'p95_dso':         round(p95_dso, 1),
        'total_completed': int(len(completed)),
        'by_vintage':      by_vintage,
        **dso_ops,
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

def _compute_pv_adjusted_lgd(completed, mult, has_prov, annual_rate=0.08):
    """Discount recoveries by time-to-recovery to compute PV-adjusted LGD.

    For each completed deal with material denial (>50% of PV), the recovery
    (collections on defaulted deals) is discounted back to the deal origination
    date using the facility's discount rate.

    PV-adjusted LGD >= nominal LGD because delayed recoveries are worth less.

    Returns LGD ratio (0-1) or None if insufficient data.
    """
    if len(completed) == 0 or 'Deal date' not in completed.columns:
        return None

    pv_col = completed['Purchase value'] * mult
    den_col = completed['Denied by insurance'] * mult if 'Denied by insurance' in completed.columns else pd.Series(0, index=completed.index)
    coll_col = completed['Collected till date'] * mult
    prov_col = completed['Provisions'] * mult if has_prov else pd.Series(0, index=completed.index)

    # Focus on defaulted deals (denial > 50% of PV — matches separation principle)
    defaulted_mask = den_col > (pv_col * 0.5)
    if defaulted_mask.sum() == 0:
        return None

    total_denied = float(den_col[defaulted_mask].sum())
    if total_denied <= 0:
        return None

    # Estimate time-to-recovery in years from deal origination to "now" (snapshot)
    # For completed deals, Deal date → last activity approximated by deal age
    deal_dates = pd.to_datetime(completed.loc[defaulted_mask, 'Deal date'], errors='coerce')
    snapshot_date = deal_dates.max()  # latest deal date as proxy for snapshot
    if pd.isna(snapshot_date):
        return None

    years_to_recovery = ((snapshot_date - deal_dates).dt.days / 365.25).clip(lower=0.01)

    # Discount each deal's recovery to origination-date PV
    recoveries = coll_col[defaulted_mask] + prov_col[defaulted_mask]
    pv_recoveries = recoveries / ((1 + annual_rate) ** years_to_recovery)

    total_pv_recovery = float(pv_recoveries.sum())
    pv_lgd = (total_denied - total_pv_recovery) / total_denied
    return max(0.0, min(1.0, pv_lgd))


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

    # PV-adjusted LGD — discount recoveries by time-to-recovery
    pv_lgd = _compute_pv_adjusted_lgd(completed, mult, has_prov)

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
            'lgd_pv_adjusted':  round(pv_lgd * 100, 2) if pv_lgd is not None else None,
            'ead':              round(ead, 2),
            'el':               round(el_amount, 2),
            'el_rate':          el_rate,
            'completed_deals':  int(len(completed)),
            'denied_amount':    round(total_denied, 2),
            'provisions':       round(total_provisions, 2),
        },
        'by_vintage': by_vintage,
    }


# ── Facility-Mode PD (Markov Chain) ──────────────────────────────────────────

def compute_facility_pd(df, mult, as_of_date=None):
    """Compute probability of default via DPD bucket transition matrix.

    Facility-mode PD measures the probability that a receivable ages from
    its current DPD bucket into ineligibility or default. Uses a Markov
    chain approach: observe transitions between DPD buckets across the
    portfolio, then compute forward cumulative PD.

    DPD buckets: current (0), 1-30, 31-60, 61-90, 91-120, 120+ (default).

    Returns transition matrix, cumulative PD curve, and facility-level PD.
    Returns {'available': False} if DPD computation not possible.
    """
    if 'Expected collection days' not in df.columns and 'Deal date' not in df.columns:
        return {'available': False}

    # Compute DPD per deal
    has_expected = 'Expected collection days' in df.columns
    deal_dates = pd.to_datetime(df['Deal date'], errors='coerce')

    if has_expected:
        exp_days = pd.to_numeric(df['Expected collection days'], errors='coerce').fillna(0)
        today = deal_dates.max()
        if pd.isna(today):
            return {'available': False}
        dpd = ((today - deal_dates).dt.days - exp_days).clip(lower=0)
    else:
        # Estimate DPD from collected vs expected ratio
        pv = df['Purchase value'] * mult
        coll = df['Collected till date'] * mult if 'Collected till date' in df.columns else pd.Series(0, index=df.index)
        exp = df['Expected till date'] * mult if 'Expected till date' in df.columns else pv
        shortfall = (exp - coll).clip(lower=0)
        # Proxy: deals with shortfall > 10% of expected are "behind"
        deal_age = (deal_dates.max() - deal_dates).dt.days.fillna(0)
        behind_mask = shortfall > (exp * 0.1)
        dpd = pd.Series(0, index=df.index)
        dpd[behind_mask] = (deal_age[behind_mask] * (shortfall[behind_mask] / exp[behind_mask].replace(0, 1))).clip(lower=0)

    # Bucket assignment
    buckets = ['current', '1-30', '31-60', '61-90', '91-120', '120+']

    def bucket_idx(d):
        if d <= 0: return 0
        if d <= 30: return 1
        if d <= 60: return 2
        if d <= 90: return 3
        if d <= 120: return 4
        return 5

    df_work = df.copy()
    df_work['_dpd'] = dpd
    df_work['_bucket'] = dpd.apply(bucket_idx)

    # Build distribution
    dist = df_work['_bucket'].value_counts().sort_index()
    total = len(df_work)
    distribution = []
    for i, bname in enumerate(buckets):
        count = int(dist.get(i, 0))
        distribution.append({
            'bucket': bname,
            'count': count,
            'pct': round(count / total * 100, 2) if total else 0,
        })

    # Transition matrix estimation
    # Without multi-snapshot data, estimate from completed deals
    completed = df_work[df_work['Status'] == 'Completed']
    active = df_work[df_work['Status'] == 'Executed']

    # Forward PD: probability an active deal in each bucket eventually defaults
    # Use completed deal outcomes as calibration
    transition_matrix = []
    for i, bname in enumerate(buckets):
        row = {'from_bucket': bname}
        bucket_deals = completed[completed['_bucket'] >= i] if i < 5 else completed[completed['_bucket'] == 5]
        if len(bucket_deals) == 0:
            row['to_default_pct'] = 0
        else:
            # How many deals in this or worse bucket ended up with >50% denial?
            den = bucket_deals['Denied by insurance'] * mult if 'Denied by insurance' in bucket_deals.columns else pd.Series(0, index=bucket_deals.index)
            pv_b = bucket_deals['Purchase value'] * mult
            defaulted = (den > pv_b * 0.5).sum()
            row['to_default_pct'] = round(defaulted / len(bucket_deals) * 100, 2)
        transition_matrix.append(row)

    # Facility-level PD: weighted average across active deal buckets
    facility_pd = 0
    if len(active) > 0:
        for i in range(6):
            bucket_active = active[active['_bucket'] == i]
            if len(bucket_active) > 0 and i < len(transition_matrix):
                weight = len(bucket_active) / len(active)
                facility_pd += weight * transition_matrix[i]['to_default_pct']

    return {
        'available': True,
        'method': 'direct' if has_expected else 'proxy',
        'distribution': distribution,
        'transition_matrix': transition_matrix,
        'facility_pd': round(facility_pd, 2),
        'total_deals': total,
        'active_deals': int(len(active)),
        'completed_deals': int(len(completed)),
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

        # Weighted average deal age for completed deals in this group
        # (approximates DSO — true DSO requires completion timestamps)
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


# ── PAR (Portfolio at Risk) ──────────────────────────────────────────────────

def _build_empirical_benchmark(completed_df, snapshot_date=None):
    """Build empirical expected collection % by deal age bucket from completed deals.

    Groups completed deals by age bucket (30-day intervals), computes the median
    collection percentage (Collected / Purchase value) at each age.
    Returns a sorted list of (max_age_days, expected_collection_pct) tuples.
    """
    if len(completed_df) < 50:
        return None

    cdf = completed_df.copy()
    cdf['coll_pct'] = cdf['Collected till date'] / cdf['Purchase value'].replace(0, float('nan'))
    cdf = cdf.dropna(subset=['coll_pct'])

    if len(cdf) < 50:
        return None

    # Use deal age at completion (or latest snapshot) as the reference
    if 'Deal date' not in cdf.columns:
        return None

    ref = pd.Timestamp(snapshot_date) if snapshot_date else pd.Timestamp.now()
    cdf['deal_age'] = (ref - cdf['Deal date']).dt.days

    # Create 30-day buckets from 0 to 720
    buckets = []
    for cutoff in range(30, 721, 30):
        mask = cdf['deal_age'] <= cutoff
        if mask.sum() >= 10:
            median_pct = cdf.loc[mask, 'coll_pct'].median()
            buckets.append((cutoff, float(median_pct)))

    return buckets if len(buckets) >= 3 else None


def compute_par(df, mult, as_of_date=None):
    """Portfolio at Risk KPIs for Klaim.

    Primary method: Uses 'Expected till date' column to identify deals behind schedule.
    Option C: Derives empirical benchmarks from completed deals if Expected column missing.
    Fallback: Returns available=False when neither approach is viable.

    Returns dual perspective:
        - Active PAR: behind-schedule outstanding / active outstanding (monitoring view)
        - Lifetime PAR: behind-schedule outstanding / total originated (IC view)
    """
    active = df[df['Status'] == 'Executed'].copy()
    if len(active) == 0:
        return {'available': False}

    today = pd.Timestamp(as_of_date) if as_of_date else pd.Timestamp.now()

    # Compute outstanding per deal
    active['outstanding'] = (
        active['Purchase value'] - active['Collected till date'] -
        active.get('Denied by insurance', pd.Series(0, index=active.index))
    ).clip(lower=0) * mult

    total_active_outstanding = float(active['outstanding'].sum())
    total_active_count = len(active)

    # Lifetime denominators — total originated across all deals (all statuses)
    total_originated = float(df['Purchase value'].sum() * mult)
    total_deal_count = len(df)

    if total_active_outstanding <= 0:
        return {'available': False}

    # Method 1: Primary — uses Expected collection days (direct DPD) or
    # Expected till date (shortfall proxy), whichever is available
    has_expected_days = 'Expected collection days' in df.columns
    if has_expected_days or 'Expected till date' in df.columns:

        if has_expected_days:
            # Direct DPD: expected payment date = Deal date + Expected collection days
            # DPD = max(0, today - expected payment date)
            exp_days = active['Expected collection days'].fillna(0).astype(float)
            active['expected_payment_date'] = active['Deal date'] + pd.to_timedelta(exp_days, unit='D')
            active['est_dpd'] = (today - active['expected_payment_date']).dt.days.clip(lower=0)
            # Still compute shortfall for the mask (need outstanding > 0 and behind schedule)
            active['collected'] = active['Collected till date'] * mult
            if 'Expected till date' in df.columns:
                active['expected'] = active['Expected till date'].fillna(0) * mult
                active['shortfall'] = (active['expected'] - active['collected']).clip(lower=0)
            else:
                # Without Expected till date, mark all past-due deals as having shortfall
                active['shortfall'] = (active['est_dpd'] > 0).astype(float)
            par_method = 'direct'
        else:
            # Proxy DPD: shortfall_ratio × deal_age
            active['expected'] = active['Expected till date'].fillna(0) * mult
            active['collected'] = active['Collected till date'] * mult
            active['shortfall'] = (active['expected'] - active['collected']).clip(lower=0)
            active['deal_age'] = (today - active['Deal date']).dt.days
            pv = (active['Purchase value'] * mult).replace(0, float('nan'))
            active['shortfall_ratio'] = active['shortfall'] / pv
            active['shortfall_ratio'] = active['shortfall_ratio'].fillna(0)
            active['est_dpd'] = active['deal_age'] * active['shortfall_ratio']
            par_method = 'proxy'

        def _par_at(threshold_days):
            mask = (
                (active['est_dpd'] >= threshold_days) &
                (active['outstanding'] > 0) &
                (active['shortfall'] > 0)
            )
            amount = float(active.loc[mask, 'outstanding'].sum())
            count = int(mask.sum())
            pct = amount / total_active_outstanding * 100 if total_active_outstanding > 0 else 0
            count_pct = count / total_active_count * 100 if total_active_count > 0 else 0
            return amount, count, pct, count_pct

        par30_amt, par30_ct, par30, par30_ct_pct = _par_at(30)
        par60_amt, par60_ct, par60, par60_ct_pct = _par_at(60)
        par90_amt, par90_ct, par90, par90_ct_pct = _par_at(90)

        # Lifetime PAR: same numerator, denominator = total originated
        lt_par30 = par30_amt / total_originated * 100 if total_originated > 0 else 0
        lt_par60 = par60_amt / total_originated * 100 if total_originated > 0 else 0
        lt_par90 = par90_amt / total_originated * 100 if total_originated > 0 else 0
        lt_par30_ct = par30_ct / total_deal_count * 100 if total_deal_count > 0 else 0
        lt_par60_ct = par60_ct / total_deal_count * 100 if total_deal_count > 0 else 0
        lt_par90_ct = par90_ct / total_deal_count * 100 if total_deal_count > 0 else 0

        return {
            'available': True,
            'method': 'direct' if has_expected_days else 'expected',
            # Active perspective (monitoring) — denominator = active outstanding
            'par30': round(par30, 4),
            'par60': round(par60, 4),
            'par90': round(par90, 4),
            'par30_count': round(par30_ct_pct, 4),
            'par60_count': round(par60_ct_pct, 4),
            'par90_count': round(par90_ct_pct, 4),
            'par30_amount': round(par30_amt, 2),
            'par60_amount': round(par60_amt, 2),
            'par90_amount': round(par90_amt, 2),
            'total_active_outstanding': round(total_active_outstanding, 2),
            'total_active_count': total_active_count,
            # Lifetime perspective (IC view) — denominator = total originated
            'lifetime_par30': round(lt_par30, 4),
            'lifetime_par60': round(lt_par60, 4),
            'lifetime_par90': round(lt_par90, 4),
            'lifetime_par30_count': round(lt_par30_ct, 4),
            'lifetime_par60_count': round(lt_par60_ct, 4),
            'lifetime_par90_count': round(lt_par90_ct, 4),
            'total_originated': round(total_originated, 2),
            'total_deal_count': total_deal_count,
        }

    # Method 2: Option C — Empirical benchmarks from completed deals
    completed = df[df['Status'] == 'Completed'].copy()
    benchmark = _build_empirical_benchmark(completed, snapshot_date=as_of_date)

    if benchmark is not None:
        active['deal_age'] = (today - active['Deal date']).dt.days
        active['coll_pct'] = (active['Collected till date'] * mult) / (active['Purchase value'] * mult).replace(0, float('nan'))
        active['coll_pct'] = active['coll_pct'].fillna(0)

        # For each active deal, find the expected collection % at its age from the benchmark
        def _expected_pct(age):
            for cutoff, pct in benchmark:
                if age <= cutoff:
                    return pct
            return benchmark[-1][1] if benchmark else 1.0

        active['expected_pct'] = active['deal_age'].apply(_expected_pct)
        active['pct_behind'] = active['expected_pct'] - active['coll_pct']

        # PAR: deal is X+ DPD if deal_age > X AND collecting less than 90% of expected benchmark
        def _par_derived(threshold_days):
            mask = (
                (active['deal_age'] > threshold_days) &
                (active['pct_behind'] > 0.10) &  # collecting 10%+ behind benchmark
                (active['outstanding'] > 0)
            )
            amount = float(active.loc[mask, 'outstanding'].sum())
            count = int(mask.sum())
            pct = amount / total_active_outstanding * 100 if total_active_outstanding > 0 else 0
            count_pct = count / total_active_count * 100 if total_active_count > 0 else 0
            return amount, count, pct, count_pct

        par30_amt, par30_ct, par30, par30_ct_pct = _par_derived(30)
        par60_amt, par60_ct, par60, par60_ct_pct = _par_derived(60)
        par90_amt, par90_ct, par90, par90_ct_pct = _par_derived(90)

        # Lifetime PAR: same numerator, denominator = total originated
        lt_par30 = par30_amt / total_originated * 100 if total_originated > 0 else 0
        lt_par60 = par60_amt / total_originated * 100 if total_originated > 0 else 0
        lt_par90 = par90_amt / total_originated * 100 if total_originated > 0 else 0
        lt_par30_ct = par30_ct / total_deal_count * 100 if total_deal_count > 0 else 0
        lt_par60_ct = par60_ct / total_deal_count * 100 if total_deal_count > 0 else 0
        lt_par90_ct = par90_ct / total_deal_count * 100 if total_deal_count > 0 else 0

        return {
            'available': True,
            'method': 'derived',
            # Active perspective (monitoring)
            'par30': round(par30, 4),
            'par60': round(par60, 4),
            'par90': round(par90, 4),
            'par30_count': round(par30_ct_pct, 4),
            'par60_count': round(par60_ct_pct, 4),
            'par90_count': round(par90_ct_pct, 4),
            'par30_amount': round(par30_amt, 2),
            'par60_amount': round(par60_amt, 2),
            'par90_amount': round(par90_amt, 2),
            'total_active_outstanding': round(total_active_outstanding, 2),
            'total_active_count': total_active_count,
            # Lifetime perspective (IC view)
            'lifetime_par30': round(lt_par30, 4),
            'lifetime_par60': round(lt_par60, 4),
            'lifetime_par90': round(lt_par90, 4),
            'lifetime_par30_count': round(lt_par30_ct, 4),
            'lifetime_par60_count': round(lt_par60_ct, 4),
            'lifetime_par90_count': round(lt_par90_ct, 4),
            'total_originated': round(total_originated, 2),
            'total_deal_count': total_deal_count,
        }

    # Fallback: neither method available
    return {'available': False}


# ── DTFC (Days to First Cash) ────────────────────────────────────────────────

def compute_dtfc(df, mult, as_of_date=None):
    """Days to First Cash — time from deal origination to first non-zero collection.

    Leading indicator: deterioration in DTFC precedes collection rate decline.
    Uses collection curve columns when available; otherwise estimates from
    completed deals with positive collections.
    """
    if 'Deal date' not in df.columns:
        return {'available': False}

    today = pd.Timestamp(as_of_date) if as_of_date else pd.Timestamp.now()

    # Method 1: Use collection curve columns (most precise)
    curve_cols = [c for c in df.columns if c.startswith('Actual in ') and 'days' in c]
    if curve_cols:
        # Find the first non-zero curve column per deal
        dtfc_values = []
        for _, row in df.iterrows():
            for col in sorted(curve_cols, key=lambda c: int(''.join(filter(str.isdigit, c)))):
                days = int(''.join(filter(str.isdigit, col)))
                val = row.get(col, 0)
                if pd.notna(val) and val > 0:
                    dtfc_values.append(days)
                    break

        if len(dtfc_values) >= 10:
            dtfc_series = pd.Series(dtfc_values)
            by_vintage = _dtfc_by_vintage(df, curve_cols, today)
            return {
                'available': True,
                'method': 'curves',
                'median_dtfc': round(float(dtfc_series.median()), 1),
                'p90_dtfc': round(float(dtfc_series.quantile(0.9)), 1),
                'mean_dtfc': round(float(dtfc_series.mean()), 1),
                'total_deals': len(dtfc_values),
                'by_vintage': by_vintage,
            }

    # Method 2: Estimate from completed deals (less precise)
    completed = df[(df['Status'] == 'Completed') & (df['Collected till date'] > 0)].copy()
    if len(completed) < 20:
        return {'available': False}

    # Estimate DTFC as a fraction of deal age for completed deals
    # Average deal age at completion is a rough proxy for when first cash arrived
    completed['deal_age'] = (today - completed['Deal date']).dt.days
    # Heuristic: first cash arrives early — estimate as 20% of total deal age
    # This is coarse but better than nothing; curve method is preferred
    completed['est_dtfc'] = completed['deal_age'] * 0.15
    completed['est_dtfc'] = completed['est_dtfc'].clip(lower=7, upper=180)

    return {
        'available': True,
        'method': 'estimated',
        'median_dtfc': round(float(completed['est_dtfc'].median()), 1),
        'p90_dtfc': round(float(completed['est_dtfc'].quantile(0.9)), 1),
        'mean_dtfc': round(float(completed['est_dtfc'].mean()), 1),
        'total_deals': len(completed),
        'by_vintage': [],
    }


def _dtfc_by_vintage(df, curve_cols, today):
    """Helper to compute DTFC by vintage month using curve columns."""
    if 'Deal date' not in df.columns:
        return []

    df = df.copy()
    df['vintage'] = df['Deal date'].dt.to_period('M').astype(str)

    results = []
    for vintage, group in df.groupby('vintage'):
        dtfc_vals = []
        for _, row in group.iterrows():
            for col in sorted(curve_cols, key=lambda c: int(''.join(filter(str.isdigit, c)))):
                days = int(''.join(filter(str.isdigit, col)))
                val = row.get(col, 0)
                if pd.notna(val) and val > 0:
                    dtfc_vals.append(days)
                    break
        if dtfc_vals:
            s = pd.Series(dtfc_vals)
            results.append({
                'vintage': str(vintage),
                'median_dtfc': round(float(s.median()), 1),
                'p90_dtfc': round(float(s.quantile(0.9)), 1),
                'count': len(dtfc_vals),
            })
    return results


# ── Cohort Loss Waterfall ────────────────────────────────────────────────────

def compute_cohort_loss_waterfall(df, mult, as_of_date=None):
    """Per-vintage loss cascade: Originated -> Gross Default -> Recovery -> Net Loss.

    For Klaim: 'default' = deals where denial > 50% of purchase value.
    Recovery = collections on defaulted deals (collected despite significant denial).
    """
    if 'Deal date' not in df.columns:
        return {'available': False}

    df = add_month_column(df)
    vintages = []

    for month, grp in df.groupby('Month'):
        originated = float(grp['Purchase value'].sum() * mult)
        denied = float(grp['Denied by insurance'].sum() * mult) if 'Denied by insurance' in grp.columns else 0

        # Default = deals where denial rate > 50% of purchase value
        pv = grp['Purchase value'] * mult
        den = grp['Denied by insurance'] * mult if 'Denied by insurance' in grp.columns else pd.Series(0, index=grp.index)
        defaulted_mask = den > (pv * 0.5)
        gross_default = float(den[defaulted_mask].sum())

        # Recovery on defaulted deals = any collection on those deals
        coll_on_default = float((grp.loc[defaulted_mask, 'Collected till date'] * mult).sum()) if defaulted_mask.any() else 0

        # Provisions on defaulted deals
        prov_on_default = float((grp.loc[defaulted_mask, 'Provisions'] * mult).sum()) if 'Provisions' in grp.columns and defaulted_mask.any() else 0

        recovery = coll_on_default + prov_on_default
        net_loss = max(0, gross_default - recovery)

        vintages.append({
            'vintage': month,
            'deal_count': int(len(grp)),
            'originated': round(originated, 2),
            'gross_default': round(gross_default, 2),
            'recovery': round(recovery, 2),
            'net_loss': round(net_loss, 2),
            'gross_default_rate': round(gross_default / originated * 100, 4) if originated > 0 else 0,
            'net_loss_rate': round(net_loss / originated * 100, 4) if originated > 0 else 0,
            'recovery_rate': round(recovery / gross_default * 100, 4) if gross_default > 0 else 0,
            'default_count': int(defaulted_mask.sum()),
        })

    # Totals
    t_orig = sum(v['originated'] for v in vintages)
    t_gross = sum(v['gross_default'] for v in vintages)
    t_recov = sum(v['recovery'] for v in vintages)
    t_net = sum(v['net_loss'] for v in vintages)

    return {
        'available': True,
        'vintages': vintages,
        'totals': {
            'originated': round(t_orig, 2),
            'gross_default': round(t_gross, 2),
            'recovery': round(t_recov, 2),
            'net_loss': round(t_net, 2),
            'gross_default_rate': round(t_gross / t_orig * 100, 4) if t_orig > 0 else 0,
            'net_loss_rate': round(t_net / t_orig * 100, 4) if t_orig > 0 else 0,
            'recovery_rate': round(t_recov / t_gross * 100, 4) if t_gross > 0 else 0,
        }
    }


# ── Recovery Analysis Post-Default ───────────────────────────────────────────

def compute_recovery_analysis(df, mult, as_of_date=None):
    """Recovery metrics for defaulted deals (Klaim: denial > 50% of PV)."""
    pv = df['Purchase value'] * mult
    den = df['Denied by insurance'] * mult if 'Denied by insurance' in df.columns else pd.Series(0, index=df.index)
    coll = df['Collected till date'] * mult

    defaulted_mask = den > (pv * 0.5)
    defaulted = df[defaulted_mask].copy()

    if len(defaulted) == 0:
        return {'available': False}

    total_default_amount = float(den[defaulted_mask].sum())
    total_recovery = float(coll[defaulted_mask].sum())
    recovery_rate = total_recovery / total_default_amount * 100 if total_default_amount > 0 else 0

    # By vintage
    defaulted = add_month_column(defaulted)
    by_vintage = []
    for month, grp in defaulted.groupby('Month'):
        g_den = float((grp['Denied by insurance'] * mult).sum())
        g_coll = float((grp['Collected till date'] * mult).sum())
        by_vintage.append({
            'vintage': month,
            'defaults': int(len(grp)),
            'default_amount': round(g_den, 2),
            'recovered': round(g_coll, 2),
            'recovery_rate': round(g_coll / g_den * 100, 4) if g_den > 0 else 0,
        })

    # Worst and best deals
    defaulted['d_amt'] = den[defaulted_mask].values
    defaulted['r_amt'] = coll[defaulted_mask].values
    defaulted['r_rate'] = (defaulted['r_amt'] / defaulted['d_amt'].replace(0, float('nan'))).fillna(0)

    worst = defaulted.nlargest(10, 'd_amt')[['Month', 'd_amt', 'r_amt', 'r_rate']].to_dict('records')
    best = defaulted.nlargest(10, 'r_rate')[['Month', 'd_amt', 'r_amt', 'r_rate']].to_dict('records')

    return {
        'available': True,
        'total_defaults': int(len(defaulted)),
        'total_default_amount': round(total_default_amount, 2),
        'total_recovery': round(total_recovery, 2),
        'recovery_rate': round(recovery_rate, 4),
        'by_vintage': by_vintage,
        'worst_deals': worst,
        'best_recoveries': best,
    }


# ── Vintage Loss Curves ─────────────────────────────────────────────────────

def compute_vintage_loss_curves(df, mult, as_of_date=None):
    """Cumulative loss development curves by vintage — like collection curves but for losses."""
    if 'Deal date' not in df.columns:
        return {'available': False}

    today = pd.Timestamp(as_of_date) if as_of_date else pd.Timestamp.now()
    df = df.copy()
    df['vintage'] = df['Deal date'].dt.to_period('M').astype(str)
    df['months_since_orig'] = ((today - df['Deal date']).dt.days / 30.44).astype(int)

    den = df['Denied by insurance'] * mult if 'Denied by insurance' in df.columns else pd.Series(0, index=df.index)
    pv = df['Purchase value'] * mult

    vintages = []
    for vintage, grp in df.groupby('vintage'):
        if len(grp) < 5:
            continue
        originated = float(grp['Purchase value'].sum() * mult)
        if originated <= 0:
            continue

        max_months = int(grp['months_since_orig'].max())
        points = []
        for m in range(1, min(max_months + 1, 25)):  # cap at 24 months
            deals_at_m = grp[grp['months_since_orig'] >= m]
            cum_denied = float((deals_at_m['Denied by insurance'] * mult).sum()) if 'Denied by insurance' in deals_at_m.columns else 0
            cum_collected = float((deals_at_m['Collected till date'] * mult).sum())
            points.append({
                'months_since_orig': m,
                'cumulative_default_rate': round(cum_denied / originated * 100, 4),
                'cumulative_collection_rate': round(cum_collected / originated * 100, 4),
            })

        vintages.append({
            'vintage': str(vintage),
            'deal_count': int(len(grp)),
            'originated': round(originated, 2),
            'points': points,
        })

    return {
        'available': len(vintages) > 0,
        'vintages': vintages,
    }


# ── Underwriting Drift ───────────────────────────────────────────────────────

def compute_underwriting_drift(df, mult, as_of_date=None):
    """Per monthly cohort: origination quality metrics to detect underwriting changes."""
    if 'Deal date' not in df.columns:
        return {'available': False}

    df = add_month_column(df)
    cohorts = []

    for month, grp in df.groupby('Month'):
        pv = grp['Purchase value'] * mult
        cohort = {
            'Month': month,
            'deal_count': int(len(grp)),
            'avg_deal_size': round(float(pv.mean()), 2),
            'median_deal_size': round(float(pv.median()), 2),
            'total_originated': round(float(pv.sum()), 2),
        }

        if 'Discount' in grp.columns:
            cohort['avg_discount'] = round(float(grp['Discount'].mean()), 4)
        if 'New business' in grp.columns:
            new_count = int(grp['New business'].sum())
            cohort['new_pct'] = round(new_count / len(grp) * 100, 2) if len(grp) > 0 else 0
        if 'Claim count' in grp.columns:
            cohort['avg_claim_count'] = round(float(grp['Claim count'].mean()), 2)
        if 'Product' in grp.columns:
            cohort['product_mix'] = grp['Product'].value_counts(normalize=True).round(4).to_dict()

        # Outcome metrics (only for vintages with enough seasoning)
        completed = grp[grp['Status'] == 'Completed']
        if len(completed) >= 5:
            coll = (completed['Collected till date'] * mult).sum()
            pvcomp = (completed['Purchase value'] * mult).sum()
            cohort['outcome_collection_rate'] = round(float(coll / pvcomp * 100), 4) if pvcomp > 0 else None
            if 'Denied by insurance' in completed.columns:
                denied = (completed['Denied by insurance'] * mult).sum()
                cohort['outcome_denial_rate'] = round(float(denied / pvcomp * 100), 4) if pvcomp > 0 else None

        cohorts.append(cohort)

    # Drift flags — compare last 3 months to prior 6 months
    drift_flags = []
    if len(cohorts) >= 9:
        recent = cohorts[-3:]
        prior = cohorts[-9:-3]
        r_avg_size = sum(c['avg_deal_size'] for c in recent) / 3
        p_avg_size = sum(c['avg_deal_size'] for c in prior) / 6
        if p_avg_size > 0 and abs(r_avg_size - p_avg_size) / p_avg_size > 0.15:
            direction = 'up' if r_avg_size > p_avg_size else 'down'
            drift_flags.append(f'Average deal size {direction} {abs(r_avg_size - p_avg_size) / p_avg_size * 100:.0f}% vs 6M average')

        if all('avg_discount' in c for c in recent + prior):
            r_disc = sum(c['avg_discount'] for c in recent) / 3
            p_disc = sum(c['avg_discount'] for c in prior) / 6
            if p_disc > 0 and abs(r_disc - p_disc) / p_disc > 0.10:
                direction = 'up' if r_disc > p_disc else 'down'
                drift_flags.append(f'Average discount {direction} {abs(r_disc - p_disc) / p_disc * 100:.0f}% vs 6M average')

    return {
        'available': True,
        'cohorts': cohorts,
        'drift_flags': drift_flags,
    }


# ── Segment Analysis ─────────────────────────────────────────────────────────

def compute_segment_analysis(df, mult, as_of_date=None, segment_by='product'):
    """Multi-dimensional performance cuts by different segmentation dimensions."""
    # Determine available dimensions
    available_dims = []
    if 'Product' in df.columns:
        available_dims.append('product')
    if 'Group' in df.columns:
        available_dims.append('provider_size')
    if 'New business' in df.columns:
        available_dims.append('new_repeat')
    available_dims.append('deal_size')  # always available — computed from Purchase value

    if segment_by not in available_dims and segment_by != 'deal_size':
        return {'available': False, 'available_dimensions': available_dims}

    # Determine the segmentation column
    df = df.copy()
    if segment_by == 'product' and 'Product' in df.columns:
        df['_segment'] = df['Product'].fillna('Unknown')
    elif segment_by == 'provider_size' and 'Group' in df.columns:
        # Bucket providers by total originated volume
        group_totals = df.groupby('Group')['Purchase value'].sum()
        def _size_band(g):
            total = group_totals.get(g, 0)
            if total > 5_000_000: return 'Enterprise (>5M)'
            if total > 1_000_000: return 'Large (1M-5M)'
            if total > 200_000:   return 'Medium (200K-1M)'
            return 'Small (<200K)'
        df['_segment'] = df['Group'].apply(_size_band)
    elif segment_by == 'new_repeat' and 'New business' in df.columns:
        df['_segment'] = df['New business'].apply(lambda x: 'New' if x else 'Repeat')
    elif segment_by == 'deal_size':
        pv = df['Purchase value'] * mult
        df['_segment'] = pd.cut(pv, bins=[0, 50000, 200000, 500000, float('inf')],
                                labels=['Small (<50K)', 'Medium (50K-200K)', 'Large (200K-500K)', 'Enterprise (>500K)'])
    else:
        return {'available': False, 'available_dimensions': available_dims}

    segments = []
    for seg, grp in df.groupby('_segment', observed=True):
        originated = float((grp['Purchase value'] * mult).sum())
        outstanding = float(((grp['Purchase value'] - grp['Collected till date'] -
                             grp.get('Denied by insurance', pd.Series(0, index=grp.index))) * mult).clip(lower=0).sum())
        collected = float((grp['Collected till date'] * mult).sum())
        denied = float((grp['Denied by insurance'] * mult).sum()) if 'Denied by insurance' in grp.columns else 0
        active = int((grp['Status'] == 'Executed').sum())

        segments.append({
            'segment': str(seg),
            'count': int(len(grp)),
            'active': active,
            'originated': round(originated, 2),
            'outstanding': round(outstanding, 2),
            'collection_pct': round(collected / originated * 100, 4) if originated > 0 else 0,
            'denial_pct': round(denied / originated * 100, 4) if originated > 0 else 0,
            'avg_discount': round(float(grp['Discount'].mean()), 4) if 'Discount' in grp.columns else None,
        })

    return {
        'available': True,
        'segment_by': segment_by,
        'segments': sorted(segments, key=lambda s: s['originated'], reverse=True),
        'available_dimensions': available_dims,
    }


# ── Collections Timing Waterfall ─────────────────────────────────────────────

def compute_collections_timing(df, mult, as_of_date=None, view='origination_month'):
    """Collections timing distribution by bucket.

    View 'origination_month': for each vintage, how collections distribute across timing buckets.
    View 'payment_month': by payment period, what timing buckets were collected.
    """
    if 'Deal date' not in df.columns:
        return {'available': False}

    # Use collection curve columns for precise timing when available
    curve_cols = sorted(
        [c for c in df.columns if c.startswith('Actual in ') and 'days' in c],
        key=lambda c: int(''.join(filter(str.isdigit, c)))
    )

    if not curve_cols:
        return {'available': False, 'reason': 'No collection curve columns'}

    df = add_month_column(df)
    bucket_labels = []
    for i, col in enumerate(curve_cols):
        days = int(''.join(filter(str.isdigit, col)))
        if i == 0:
            bucket_labels.append(f'0-{days}d')
        else:
            prev_days = int(''.join(filter(str.isdigit, curve_cols[i-1])))
            bucket_labels.append(f'{prev_days+1}-{days}d')

    months = []
    for month, grp in df.groupby('Month'):
        row = {'Month': month, 'deal_count': int(len(grp))}
        total = 0
        for i, col in enumerate(curve_cols):
            val = float(grp[col].fillna(0).sum() * mult)
            if i > 0:
                prev_val = float(grp[curve_cols[i-1]].fillna(0).sum() * mult)
                bucket_val = val - prev_val
            else:
                bucket_val = val
            bucket_val = max(0, bucket_val)
            row[bucket_labels[i]] = round(bucket_val, 2)
            total += bucket_val
        row['total'] = round(total, 2)
        months.append(row)

    # Portfolio distribution
    portfolio_dist = {}
    total_all = sum(m['total'] for m in months)
    if total_all > 0:
        for label in bucket_labels:
            bucket_total = sum(m.get(label, 0) for m in months)
            portfolio_dist[label] = round(bucket_total / total_all * 100, 2)

    return {
        'available': True,
        'view': view,
        'months': months,
        'bucket_labels': bucket_labels,
        'portfolio_distribution': portfolio_dist,
    }


# ── Seasonality ──────────────────────────────────────────────────────────────

def compute_seasonality(df, mult, as_of_date=None):
    """Year-over-year comparison by calendar month."""
    if 'Deal date' not in df.columns:
        return {'available': False}

    df = df.copy()
    df['year'] = df['Deal date'].dt.year
    df['cal_month'] = df['Deal date'].dt.month
    years = sorted(df['year'].dropna().unique().tolist())

    if len(years) < 1 or df['cal_month'].nunique() < 6:
        return {'available': False}

    origination = []
    collection_rate = []

    for m in range(1, 13):
        orig_row = {'month': m}
        coll_row = {'month': m}
        for y in years:
            grp = df[(df['year'] == y) & (df['cal_month'] == m)]
            orig_row[str(y)] = round(float((grp['Purchase value'] * mult).sum()), 2)
            pv = (grp['Purchase value'] * mult).sum()
            co = (grp['Collected till date'] * mult).sum()
            coll_row[str(y)] = round(float(co / pv * 100), 2) if pv > 0 else None
        origination.append(orig_row)
        collection_rate.append(coll_row)

    # Seasonal index — average across years
    # Compute overall average from non-zero months only (avoids deflating index for mid-year starts)
    all_nonzero = [origination[mm-1].get(str(y), 0) for mm in range(1, 13) for y in years
                   if origination[mm-1].get(str(y), 0) > 0]
    overall_avg = sum(all_nonzero) / len(all_nonzero) if all_nonzero else 1

    seasonal_index = []
    for m in range(1, 13):
        vals = [origination[m-1].get(str(y), 0) for y in years]
        vals = [v for v in vals if v > 0]
        avg = sum(vals) / len(vals) if vals else 0
        seasonal_index.append({
            'month': m,
            'index': round(avg / overall_avg, 4) if overall_avg > 0 else 1.0,
        })

    return {
        'available': True,
        'origination': origination,
        'collection_rate': collection_rate,
        'seasonal_index': seasonal_index,
        'years': [int(y) for y in years],
    }


# ── Loss Categorization ─────────────────────────────────────────────────────

def compute_loss_categorization(df, mult, as_of_date=None):
    """Categorize losses by inferred reason code using heuristics."""
    den = df['Denied by insurance'] * mult if 'Denied by insurance' in df.columns else pd.Series(0, index=df.index)
    pv = df['Purchase value'] * mult
    defaulted_mask = den > (pv * 0.5)

    if defaulted_mask.sum() == 0:
        return {'available': False}

    defaulted = df[defaulted_mask].copy()
    defaulted['denied_amt'] = den[defaulted_mask].values

    categories = []
    # Provider-concentrated: if group has 3x avg denial rate
    if 'Group' in defaulted.columns:
        group_rates = df.groupby('Group').apply(
            lambda g: (g['Denied by insurance'].sum() / g['Purchase value'].sum()) if g['Purchase value'].sum() > 0 else 0
        )
        avg_rate = group_rates.mean()
        high_denial_groups = set(group_rates[group_rates > avg_rate * 3].index)
        provider_mask = defaulted['Group'].isin(high_denial_groups)
        provider_amt = float(defaulted.loc[provider_mask, 'denied_amt'].sum())
        if provider_amt > 0:
            categories.append({'category': 'Provider Issue', 'count': int(provider_mask.sum()),
                             'amount': round(provider_amt, 2)})
        remaining = defaulted[~provider_mask]
    else:
        remaining = defaulted

    # Small denials suggest coding errors
    small_mask = remaining['denied_amt'] < 5000 * mult
    if small_mask.sum() > 0:
        categories.append({'category': 'Possible Coding Error', 'count': int(small_mask.sum()),
                         'amount': round(float(remaining.loc[small_mask, 'denied_amt'].sum()), 2)})
    remaining = remaining[~small_mask]

    # Everything else is general credit/underwriting
    if len(remaining) > 0:
        categories.append({'category': 'Credit / Underwriting', 'count': int(len(remaining)),
                         'amount': round(float(remaining['denied_amt'].sum()), 2)})

    total = sum(c['amount'] for c in categories)
    for c in categories:
        c['pct'] = round(c['amount'] / total * 100, 2) if total > 0 else 0

    return {
        'available': True,
        'categories': categories,
        'total_defaults': int(defaulted_mask.sum()),
        'total_amount': round(total, 2),
    }


# ── Methodology Log ──────────────────────────────────────────────────────────

def compute_methodology_log(df, as_of_date=None):
    """Return a log of data corrections/adjustments applied during analysis."""
    adjustments = []

    # Check for excluded columns
    if 'Actual IRR for owner' in df.columns:
        adjustments.append({
            'type': 'column_excluded',
            'description': 'Actual IRR for owner excluded — garbage data (mean ~2.56e44)',
            'column': 'Actual IRR for owner',
            'affected_rows': int(df['Actual IRR for owner'].notna().sum()),
        })

    # Check for negative values clipped
    for col in ['Purchase value', 'Collected till date', 'Pending insurance response']:
        if col in df.columns:
            neg_count = int((df[col] < 0).sum())
            if neg_count > 0:
                adjustments.append({
                    'type': 'negative_values',
                    'description': f'{neg_count} negative values found in {col}',
                    'column': col,
                    'affected_rows': neg_count,
                })

    # Column availability
    expected_cols = ['Purchase value', 'Collected till date', 'Denied by insurance',
                     'Expected till date', 'Expected total', 'Discount',
                     'New business', 'Product', 'Group', 'Owner']
    col_availability = {col: col in df.columns for col in expected_cols}

    # Curve columns
    curve_count = len([c for c in df.columns if c.startswith('Actual in ') and 'days' in c])
    col_availability['Collection curves'] = curve_count > 0

    # Data quality summary
    total_rows = len(df)
    null_rates = {}
    for col in df.columns[:20]:  # first 20 columns
        null_pct = float(df[col].isna().sum() / total_rows * 100) if total_rows > 0 else 0
        if null_pct > 0:
            null_rates[col] = round(null_pct, 2)

    return {
        'adjustments': adjustments,
        'column_availability': col_availability,
        'data_quality_summary': {
            'total_rows': total_rows,
            'null_rates': null_rates,
        },
    }


# ── Separation Principle ─────────────────────────────────────────────────────

def separate_portfolio(df, mult=1):
    """Split DataFrame into clean portfolio and loss portfolio.

    Returns: (clean_df, loss_df)
    - clean_df: active + normally completed deals (denial < 50% of PV)
    - loss_df: defaulted deals (denial > 50% of PV)
    """
    den = df['Denied by insurance'] if 'Denied by insurance' in df.columns else pd.Series(0, index=df.index)
    pv = df['Purchase value']
    loss_mask = den > (pv * 0.5)
    return df[~loss_mask].copy(), df[loss_mask].copy()


# ── HHI Time Series ──────────────────────────────────────────────────────────

def compute_hhi_for_snapshot(df, mult):
    """Compute HHI for a single snapshot — used by the time series endpoint."""
    total = (df['Purchase value'] * mult).sum()
    result = {}

    for col_name, key in [('Group', 'group'), ('Product', 'product')]:
        if col_name not in df.columns:
            result[f'{key}_hhi'] = None
            continue
        shares = df.groupby(col_name)['Purchase value'].sum() * mult / total
        hhi = float((shares ** 2).sum())
        result[f'{key}_hhi'] = round(hhi, 6)

    return result


# ── CDR / CCR ─────────────────────────────────────────────────────────────────

def compute_cdr_ccr(df, mult, as_of_date=None):
    """Conditional Default Rate (CDR) and Conditional Collection Rate (CCR) by vintage.

    Annualizes cumulative default/collection rates by vintage age so that cohorts
    of different maturities are directly comparable on a monthly basis.

        CDR = (Total Denied / Originated) / months_outstanding * 12
        CCR = (Total Collected / Originated) / months_outstanding * 12

    Strips out vintage age effects: a 6-month vintage with 5% cumulative defaults
    has CDR = 10% — higher than a 12-month vintage at 8% (CDR = 8%).
    """
    if 'Deal date' not in df.columns or 'Purchase value' not in df.columns:
        return {'available': False}

    today = pd.Timestamp(as_of_date) if as_of_date else pd.Timestamp.now()
    df = df.copy()
    df['_vintage'] = df['Deal date'].dt.to_period('M')
    has_denial = 'Denied by insurance' in df.columns

    vintages = []
    for vintage, grp in df.groupby('_vintage'):
        originated = float((grp['Purchase value'] * mult).sum())
        if originated <= 0:
            continue

        # Age: months from start of vintage month to as_of_date (min 1)
        months_outstanding = max(((today - vintage.to_timestamp()).days / 30.44), 1.0)

        # Skip vintages with insufficient seasoning (< 3 months) — annualization is misleading
        if months_outstanding < 3:
            continue

        collected = float((grp['Collected till date'] * mult).sum())
        defaulted = float((grp['Denied by insurance'] * mult).sum()) if has_denial else 0.0

        # Annualized conditional rates (expressed as %)
        cdr = (defaulted / originated) / months_outstanding * 12 * 100
        ccr = (collected / originated) / months_outstanding * 12 * 100

        vintages.append({
            'vintage': str(vintage),
            'deal_count': int(len(grp)),
            'originated': round(originated, 2),
            'collected': round(collected, 2),
            'defaulted': round(defaulted, 2),
            'months_outstanding': round(months_outstanding, 1),
            'cdr': round(cdr, 4),
            'ccr': round(ccr, 4),
            'net_spread': round(ccr - cdr, 4),
        })

    if not vintages:
        return {'available': False}

    # Portfolio-level: volume-weighted average age for aggregation
    total_orig = sum(v['originated'] for v in vintages)
    total_coll = sum(v['collected'] for v in vintages)
    total_default = sum(v['defaulted'] for v in vintages)
    avg_months = (
        sum(v['months_outstanding'] * v['originated'] for v in vintages) / total_orig
        if total_orig > 0 else 1.0
    )
    portfolio_cdr = (total_default / total_orig) / avg_months * 12 * 100 if total_orig > 0 else 0.0
    portfolio_ccr = (total_coll / total_orig) / avg_months * 12 * 100 if total_orig > 0 else 0.0

    return {
        'available': True,
        'vintages': vintages,
        'portfolio': {
            'cdr': round(portfolio_cdr, 4),
            'ccr': round(portfolio_ccr, 4),
            'net_spread': round(portfolio_ccr - portfolio_cdr, 4),
            'avg_vintage_age_months': round(avg_months, 1),
        },
    }