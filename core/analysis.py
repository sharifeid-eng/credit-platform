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

    # Summary stats for completed deals
    avg_days = 0
    median_days = 0
    total_completed = len(completed)
    if total_completed:
        days = completed['days_outstanding']
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

    # Monthly breakdown by health status (for stacked bar chart over time)
    monthly_health = []
    for month, grp in df2.groupby('Month'):
        row = {'Month': month}
        for status in ['Healthy', 'Watch', 'Delayed', 'Poor']:
            sub = grp[grp['health'] == status]
            row[status] = float(sub['Purchase value'].sum() * mult)
        row['total'] = float(grp['Purchase value'].sum() * mult)
        monthly_health.append(row)

    return {
        'ageing_buckets':    ageing,
        'health_summary':    health_summary,
        'monthly_active':    monthly.to_dict(orient='records'),
        'monthly_health':    monthly_health,
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

    return {
        'summary':        summary,
        'monthly':        monthly_rows,
        'discount_bands': discount_bands,
        'new_vs_repeat':  new_repeat,
    }


# ── DSO (Days Sales Outstanding) ─────────────────────────────────────────────

def compute_dso(df, mult, as_of_date=None):
    """Weighted average days to collect on completed deals + DSO by vintage."""
    today = pd.Timestamp(as_of_date) if as_of_date else pd.Timestamp.now()
    completed = df[df['Status'] == 'Completed'].copy()

    if completed.empty:
        return {
            'weighted_dso': 0, 'median_dso': 0, 'p95_dso': 0,
            'total_completed': 0, 'by_vintage': [],
        }

    completed['days_outstanding'] = (today - completed['Deal date']).dt.days
    collected = completed['Collected till date'] * mult
    days = completed['days_outstanding']

    total_collected = collected.sum()
    weighted_dso = float((days * collected).sum() / total_collected) if total_collected else 0
    median_dso = float(days.median())
    p95_dso = float(days.quantile(0.95))

    # DSO by vintage month
    completed = add_month_column(completed)
    by_vintage = []
    for month, grp in completed.groupby('Month'):
        g_coll = grp['Collected till date'] * mult
        g_days = (today - grp['Deal date']).dt.days
        g_total = g_coll.sum()
        by_vintage.append({
            'month':        month,
            'weighted_dso': round(float((g_days * g_coll).sum() / g_total), 1) if g_total else 0,
            'median_dso':   round(float(g_days.median()), 1),
            'deal_count':   int(len(grp)),
            'collected':    round(float(g_total), 2),
        })

    return {
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