"""
Aajil SME Trade Credit — Analysis Module
==========================================
Live tape analytics from multi-sheet Excel tape + auxiliary data.
Also supports legacy JSON snapshot parsing for backward compatibility.

Tape structure:
  - Deals sheet (primary): 1 row per loan, ~1,245 rows
  - Current_DPD_New Cohorts: pre-computed DPD rates by quarterly vintage
  - Collections: monthly collections by vintage
  - Payments: instalment-level data with DPD flags

Usage:
    from core.loader import load_aajil_snapshot
    from core.analysis_aajil import compute_aajil_summary
    df, aux = load_aajil_snapshot(filepath)
    result = compute_aajil_summary(df, mult=1, ref_date=None, aux=aux)
"""

import json
import numpy as np
import pandas as pd

# ── Column aliases (Deals sheet) ─────────────────────────────────────────────
C_TXN_ID       = 'Transaction ID'
C_DEAL_TYPE    = 'Deal Type'           # Bullet / EMI
C_INVOICE_DATE = 'Invoice Date'        # disbursement date
C_CUSTOMER_ID  = 'Unique Customer Code'
C_BILL         = 'Bill Notional'       # cost of raw materials
C_MARGIN       = 'Total Margin'        # mark-up
C_ORIG_FEE     = 'Origination Fee'
C_SALE_NOTIONAL = 'Sale Notional'      # Bill + Margin + Fee
C_SALE_VAT     = 'Sale VAT'
C_SALE_TOTAL   = 'Sale Total'          # total disbursed including VAT
C_REALISED     = 'Realised Amount'     # collected
C_RECEIVABLE   = 'Receivable Amount'   # outstanding
C_WRITTEN_OFF  = 'Written Off Amount'
C_WO_VAT       = 'Written Off VAT Recovered Amount'
C_WO_DATE      = 'Write Off Date'
C_STATUS       = 'Realised Status'     # Realised / Accrued / Written Off
C_INSTALLMENTS = 'Total No. of Installments'
C_DUE_INST     = 'Due No of Installments'
C_PAID_INST    = 'Paid No of Installments'
C_OVERDUE_INST = 'Overdue No of Installments'
C_SALE_DUE     = 'Sale Due Amount'
C_SALE_PAID    = 'Sale Paid Amount'
C_SALE_OVERDUE = 'Sale Overdue Amount'
C_MONTHLY_YIELD = 'Monthly Yield %'
C_TOTAL_YIELD  = 'Total Yield %'
C_ADMIN_FEE    = 'Admin Fee %'
C_TENURE       = 'Deal Tenure'
C_INDUSTRY     = 'Customer Industry'
C_PRINCIPAL    = 'Principal Amount'
C_EXPECTED_END = 'Expected Completion'


def _safe(v):
    """Convert numpy/pandas types to JSON-safe Python types."""
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return round(float(v), 4)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, pd.Timestamp):
        return v.strftime('%Y-%m-%d') if not pd.isna(v) else None
    return v


def filter_aajil_by_date(df, as_of_date):
    """Filter deals to Invoice Date <= as_of_date. Returns a copy."""
    if as_of_date is None:
        return df.copy()
    cutoff = pd.to_datetime(as_of_date)
    return df[df[C_INVOICE_DATE] <= cutoff].copy()


def _bucket_industry(series):
    """Group 115+ industries into top-10 + Other + Unknown."""
    filled = series.fillna('Unknown').replace('', 'Unknown')
    counts = filled.value_counts()
    top10 = set(counts.head(10).index) - {'Unknown'}
    return filled.apply(lambda x: x if x in top10 or x == 'Unknown' else 'Other')


# ═══════════════════════════════════════════════════════════════════════════════
# COMPUTE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def compute_aajil_summary(df, mult=1, ref_date=None, aux=None):
    """Portfolio overview KPIs."""
    n = len(df)
    if n == 0:
        return {'total_deals': 0, 'available': False}

    realised = df[df[C_STATUS] == 'Realised']
    accrued = df[df[C_STATUS] == 'Accrued']
    written_off = df[df[C_STATUS] == 'Written Off']

    total_bill = df[C_BILL].sum() * mult
    total_sale = df[C_SALE_TOTAL].sum() * mult
    total_realised = df[C_REALISED].fillna(0).sum() * mult
    total_receivable = df[C_RECEIVABLE].fillna(0).sum() * mult
    total_wo = df[C_WRITTEN_OFF].fillna(0).sum() * mult
    total_margin = df[C_MARGIN].fillna(0).sum() * mult
    total_fees = df[C_ORIG_FEE].fillna(0).sum() * mult
    total_overdue = df[C_SALE_OVERDUE].fillna(0).sum() * mult

    customers = df[C_CUSTOMER_ID].nunique()
    emi_count = len(df[df[C_DEAL_TYPE] == 'EMI'])
    bullet_count = len(df[df[C_DEAL_TYPE] == 'Bullet'])

    collection_rate = total_realised / (total_realised + total_receivable) if (total_realised + total_receivable) > 0 else 0
    wo_rate = len(written_off) / n if n > 0 else 0

    # Customer HHI
    cust_shares = df.groupby(C_CUSTOMER_ID)[C_BILL].sum()
    total_cust = cust_shares.sum()
    hhi = ((cust_shares / total_cust) ** 2).sum() if total_cust > 0 else 0

    return {
        'total_deals': n,
        'total_bill_notional': _safe(total_bill),
        'total_sale_total': _safe(total_sale),
        'total_realised': _safe(total_realised),
        'total_receivable': _safe(total_receivable),
        'total_written_off': _safe(total_wo),
        'total_margin': _safe(total_margin),
        'total_fees': _safe(total_fees),
        'total_overdue': _safe(total_overdue),
        'total_customers': customers,
        'avg_deals_per_customer': _safe(n / max(customers, 1)),
        'collection_rate': _safe(collection_rate),
        'write_off_rate': _safe(wo_rate),
        'realised_count': len(realised),
        'accrued_count': len(accrued),
        'written_off_count': len(written_off),
        'emi_count': emi_count,
        'bullet_count': bullet_count,
        'emi_pct': _safe(emi_count / n),
        'bullet_pct': _safe(bullet_count / n),
        'avg_tenure': _safe(df[C_TENURE].dropna().mean()),
        'avg_monthly_yield': _safe(df[C_MONTHLY_YIELD].dropna().mean()),
        'avg_total_yield': _safe(df[C_TOTAL_YIELD].dropna().mean()),
        'avg_deal_size': _safe(total_bill / n),
        'hhi_customer': _safe(hhi),
        'date_range': {
            'min': _safe(df[C_INVOICE_DATE].min()),
            'max': _safe(df[C_INVOICE_DATE].max()),
        },
        'analysis_type': 'aajil',
        'available': True,
    }


def compute_aajil_traction(df, mult=1, ref_date=None, aux=None):
    """Monthly disbursement volume and outstanding balance."""
    df_c = df.copy()
    df_c['month'] = df_c[C_INVOICE_DATE].dt.to_period('M')

    # Volume: monthly disbursements
    vol = df_c.groupby('month').agg(
        disbursed=(C_BILL, 'sum'),
        count=(C_TXN_ID, 'count'),
    ).reset_index()
    vol['month_str'] = vol['month'].astype(str)
    vol['disbursed'] = vol['disbursed'] * mult

    volume = [{'date': r['month_str'], 'disbursed_sar': _safe(r['disbursed']),
               'count': int(r['count'])} for _, r in vol.iterrows()]

    # By Deal Type
    vol_by_type = df_c.groupby(['month', C_DEAL_TYPE])[C_BILL].sum().unstack(fill_value=0) * mult
    by_type = []
    for m in vol_by_type.index:
        row = {'date': str(m)}
        for dt in vol_by_type.columns:
            row[dt] = _safe(vol_by_type.loc[m, dt])
        by_type.append(row)

    # Growth stats
    growth = {}
    if len(vol) >= 2:
        last = vol.iloc[-1]['disbursed']
        prev = vol.iloc[-2]['disbursed']
        if prev > 0:
            growth['mom_pct'] = _safe((last - prev) / prev * 100)
    if len(vol) >= 4:
        q_now = vol.iloc[-3:]['disbursed'].sum()
        q_prev = vol.iloc[-6:-3]['disbursed'].sum() if len(vol) >= 6 else 0
        if q_prev > 0:
            growth['qoq_pct'] = _safe((q_now - q_prev) / q_prev * 100)
    if len(vol) >= 13:
        y_now = vol.iloc[-12:]['disbursed'].sum()
        y_prev = vol.iloc[-24:-12]['disbursed'].sum() if len(vol) >= 24 else 0
        if y_prev > 0:
            growth['yoy_pct'] = _safe((y_now - y_prev) / y_prev * 100)

    # Balance: current outstanding per origination month (from single snapshot).
    # Shows how much of each vintage is still outstanding today.
    total_outstanding = df[df[C_STATUS] == 'Accrued'][C_RECEIVABLE].fillna(0).sum() * mult
    bal_by_month = df_c.groupby('month')[C_RECEIVABLE].apply(lambda x: x.fillna(0).sum()).reset_index()
    bal_by_month.columns = ['month', 'receivable']
    # Build cumulative balance: sum of receivable from all months up to each point
    balance_monthly = []
    cum_bal = 0
    for _, r in vol.iterrows():
        m = r['month']
        month_recv = bal_by_month.loc[bal_by_month['month'] == m, 'receivable']
        recv = float(month_recv.iloc[0]) * mult if len(month_recv) > 0 else 0
        cum_bal += recv
        balance_monthly.append({'date': r['month_str'], 'balance_sar': _safe(cum_bal)})

    return {
        'volume_monthly': volume,
        'balance_monthly': balance_monthly,
        'volume_by_deal_type': by_type,
        'total_disbursed': _safe(df[C_BILL].sum() * mult),
        'latest_balance': _safe(total_outstanding),
        'volume_summary_stats': growth,
        'deal_types': sorted(df[C_DEAL_TYPE].dropna().unique().tolist()),
        'available': True,
    }


def compute_aajil_delinquency(df, mult=1, ref_date=None, aux=None):
    """DPD distribution and rolling default rates."""
    # From Deals sheet: overdue installment counts
    active = df[df[C_STATUS] == 'Accrued'].copy()
    total_active = active[C_RECEIVABLE].fillna(0).sum() * mult

    # Overdue No of Installments can be fractional (proportional overdue).
    # Round to nearest integer for bucketing.
    overdue_raw = active[C_OVERDUE_INST].fillna(0)
    overdue = overdue_raw.round().astype(int)
    overdue_amt = active[C_SALE_OVERDUE].fillna(0) * mult

    buckets = [
        {'bucket': 'Current', 'count': int((overdue == 0).sum()),
         'balance': _safe(active.loc[overdue == 0, C_RECEIVABLE].fillna(0).sum() * mult)},
        {'bucket': '1 inst overdue', 'count': int((overdue == 1).sum()),
         'balance': _safe(active.loc[overdue == 1, C_RECEIVABLE].fillna(0).sum() * mult)},
        {'bucket': '2 inst overdue', 'count': int((overdue == 2).sum()),
         'balance': _safe(active.loc[overdue == 2, C_RECEIVABLE].fillna(0).sum() * mult)},
        {'bucket': '3+ inst overdue', 'count': int((overdue >= 3).sum()),
         'balance': _safe(active.loc[overdue >= 3, C_RECEIVABLE].fillna(0).sum() * mult)},
    ]

    # PAR metrics (using rounded overdue installment count)
    par_1 = active.loc[overdue >= 1, C_SALE_OVERDUE].fillna(0).sum() * mult
    par_2 = active.loc[overdue >= 2, C_SALE_OVERDUE].fillna(0).sum() * mult
    par_3 = active.loc[overdue >= 3, C_SALE_OVERDUE].fillna(0).sum() * mult

    # By Deal Type
    by_type = []
    for dt in df[C_DEAL_TYPE].dropna().unique():
        sub = active[active[C_DEAL_TYPE] == dt]
        ov = sub[C_OVERDUE_INST].fillna(0)
        n_overdue = (ov > 0).sum()
        by_type.append({
            'deal_type': dt,
            'active_count': len(sub),
            'overdue_count': int(n_overdue),
            'overdue_pct': _safe(n_overdue / max(len(sub), 1)),
            'overdue_balance': _safe(sub[C_SALE_OVERDUE].fillna(0).sum() * mult),
        })

    # Pre-computed DPD cohorts from aux sheet
    dpd_time_series = None
    if aux and aux.get('dpd_cohorts') is not None:
        dpd_time_series = _parse_dpd_cohorts(aux['dpd_cohorts'], mult)

    return {
        'buckets': buckets,
        'total_active_balance': _safe(total_active),
        'total_overdue_balance': _safe(overdue_amt.sum()),
        'par_1_inst': _safe(par_1 / total_active if total_active > 0 else 0),
        'par_2_inst': _safe(par_2 / total_active if total_active > 0 else 0),
        'par_3_inst': _safe(par_3 / total_active if total_active > 0 else 0),
        'by_deal_type': by_type,
        'dpd_time_series': dpd_time_series,
        'available': True,
    }


def _parse_dpd_cohorts(raw_df, mult=1):
    """Parse the Current_DPD_New Cohorts sheet into structured DPD time series.
    The sheet has quarterly cohorts as columns (2022-05 through 2026-03)
    and rows for Amount Deployed, DPD30+/60+/90+/180+ amounts and percentages."""
    try:
        # Row structure (from exploration):
        # Row 0: Quarter labels
        # Row 1: empty or header
        # Row 2: Amount Deployed
        # Row 3: DPD30+ amounts
        # Row 4: DPD30+ percentages
        # Row 5: DPD60+ amounts (approx)
        # etc.
        # This is a complex layout — extract what we can
        result = {}
        # Get the monthly date columns (starting from column 1)
        dates = []
        for c in raw_df.columns[1:]:
            val = raw_df.iloc[0, c] if isinstance(c, int) else None
            if val is not None and str(val).strip():
                dates.append(str(val).strip())

        # For now, return the raw shape info for the dashboard to use
        result['shape'] = list(raw_df.shape)
        result['available'] = True
        return result
    except Exception:
        return {'available': False}


def compute_aajil_collections(df, mult=1, ref_date=None, aux=None):
    """Collection rates per vintage and monthly collections."""
    df_c = df.copy()
    df_c['vintage'] = df_c[C_INVOICE_DATE].dt.to_period('M')

    # Per-vintage collection rate
    vintages = df_c.groupby('vintage').agg(
        originated=(C_BILL, 'sum'),
        realised=(C_REALISED, lambda x: x.fillna(0).sum()),
        receivable=(C_RECEIVABLE, lambda x: x.fillna(0).sum()),
        count=(C_TXN_ID, 'count'),
    ).reset_index()
    vintages['originated'] *= mult
    vintages['realised'] *= mult
    vintages['receivable'] *= mult
    vintages['collection_rate'] = vintages['realised'] / vintages['originated'].replace(0, np.nan)

    monthly = [{'date': str(r['vintage']),
                'originated': _safe(r['originated']),
                'collected': _safe(r['realised']),
                'outstanding': _safe(r['receivable']),
                'collection_rate': _safe(r['collection_rate']),
                'count': int(r['count'])}
               for _, r in vintages.iterrows()]

    total_originated = df[C_BILL].sum() * mult
    total_collected = df[C_REALISED].fillna(0).sum() * mult
    overall_rate = total_collected / total_originated if total_originated > 0 else 0

    return {
        'monthly': monthly,
        'total_originated': _safe(total_originated),
        'total_collected': _safe(total_collected),
        'overall_rate': _safe(overall_rate),
        'available': True,
    }


def compute_aajil_cohorts(df, mult=1, ref_date=None, aux=None):
    """Vintage cohort analysis — quarterly cohorts with DPD rates by MoB."""
    df_c = df.copy()
    df_c['vintage_q'] = df_c[C_INVOICE_DATE].dt.to_period('Q')

    # Build cohort summary from Deals sheet
    cohorts = df_c.groupby('vintage_q').agg(
        originated=(C_BILL, 'sum'),
        count=(C_TXN_ID, 'count'),
        realised=(C_REALISED, lambda x: x.fillna(0).sum()),
        written_off_count=(C_STATUS, lambda x: (x == 'Written Off').sum()),
        overdue_count=(C_OVERDUE_INST, lambda x: (x.fillna(0) > 0).sum()),
    ).reset_index()

    cohort_list = []
    for _, r in cohorts.iterrows():
        cohort_list.append({
            'cohort': str(r['vintage_q']),
            'original_balance': _safe(r['originated'] * mult),
            'count': int(r['count']),
            'realised': _safe(r['realised'] * mult),
            'written_off_count': int(r['written_off_count']),
            'overdue_count': int(r['overdue_count']),
            'collection_rate': _safe(r['realised'] / r['originated'] if r['originated'] > 0 else 0),
        })

    return {
        'cohorts': cohort_list,
        'dpd_threshold': 30,
        'measurement': 'Original Balance',
        'cohort_type': 'quarterly',
        'available': True,
    }


def compute_aajil_concentration(df, mult=1, ref_date=None, aux=None):
    """Customer and industry concentration."""
    # Customer concentration
    cust = df.groupby(C_CUSTOMER_ID).agg(
        volume=(C_BILL, 'sum'),
        count=(C_TXN_ID, 'count'),
    ).sort_values('volume', ascending=False).reset_index()
    cust['volume'] *= mult
    total = cust['volume'].sum()
    cust['share'] = cust['volume'] / total if total > 0 else 0
    cust['cumulative'] = cust['share'].cumsum()

    top_customers = []
    for _, r in cust.head(15).iterrows():
        top_customers.append({
            'customer_id': str(int(r[C_CUSTOMER_ID])) if pd.notna(r[C_CUSTOMER_ID]) else 'Unknown',
            'volume': _safe(r['volume']),
            'count': int(r['count']),
            'share': _safe(r['share']),
            'cumulative': _safe(r['cumulative']),
        })

    hhi_customer = (cust['share'] ** 2).sum() if total > 0 else 0

    # Industry concentration
    ind = df.copy()
    ind['industry_bucket'] = _bucket_industry(ind[C_INDUSTRY])
    ind_agg = ind.groupby('industry_bucket').agg(
        volume=(C_BILL, 'sum'),
        count=(C_TXN_ID, 'count'),
    ).sort_values('volume', ascending=False).reset_index()
    ind_agg['volume'] *= mult
    ind_total = ind_agg['volume'].sum()
    ind_agg['share'] = ind_agg['volume'] / ind_total if ind_total > 0 else 0

    industries = [{'industry': r['industry_bucket'], 'volume': _safe(r['volume']),
                   'count': int(r['count']), 'share': _safe(r['share'])}
                  for _, r in ind_agg.iterrows()]

    # Deal type mix
    dt_mix = df.groupby(C_DEAL_TYPE)[C_BILL].sum() * mult
    dt_total = dt_mix.sum()
    deal_type_mix = [{'deal_type': dt, 'volume': _safe(v), 'share': _safe(v / dt_total if dt_total > 0 else 0)}
                     for dt, v in dt_mix.items()]

    return {
        'top_customers': top_customers,
        'hhi_customer': _safe(hhi_customer),
        'top5_share': _safe(cust.head(5)['share'].sum()),
        'top10_share': _safe(cust.head(10)['share'].sum()),
        'industries': industries,
        'deal_type_mix': deal_type_mix,
        'total_customers': int(cust[C_CUSTOMER_ID].nunique()),
        'industry_unknown_pct': _safe(len(df[df[C_INDUSTRY].isna()]) / len(df)),
        'available': True,
    }


def compute_aajil_underwriting(df, mult=1, ref_date=None, aux=None):
    """Underwriting drift — deal characteristics by vintage."""
    df_c = df.copy()
    df_c['vintage_q'] = df_c[C_INVOICE_DATE].dt.to_period('Q')

    vintages = df_c.groupby('vintage_q').agg(
        avg_deal_size=(C_BILL, 'mean'),
        median_deal_size=(C_BILL, 'median'),
        avg_tenure=(C_TENURE, 'mean'),
        avg_yield=(C_TOTAL_YIELD, 'mean'),
        avg_monthly_yield=(C_MONTHLY_YIELD, 'mean'),
        emi_pct=(C_DEAL_TYPE, lambda x: (x == 'EMI').mean()),
        count=(C_TXN_ID, 'count'),
    ).reset_index()

    drift = []
    for _, r in vintages.iterrows():
        drift.append({
            'vintage': str(r['vintage_q']),
            'avg_deal_size': _safe(r['avg_deal_size'] * mult),
            'median_deal_size': _safe(r['median_deal_size'] * mult),
            'avg_tenure': _safe(r['avg_tenure']),
            'avg_yield': _safe(r['avg_yield']),
            'avg_monthly_yield': _safe(r['avg_monthly_yield']),
            'emi_pct': _safe(r['emi_pct']),
            'count': int(r['count']),
        })

    return {
        'vintages': drift,
        'available': True,
    }


def compute_aajil_yield(df, mult=1, ref_date=None, aux=None):
    """Revenue decomposition and yield analysis."""
    total_margin = df[C_MARGIN].fillna(0).sum() * mult
    total_fees = df[C_ORIG_FEE].fillna(0).sum() * mult
    total_bill = df[C_BILL].sum() * mult
    total_revenue = total_margin + total_fees

    # Distribution of yields
    yields = df[C_TOTAL_YIELD].dropna()
    monthly_yields = df[C_MONTHLY_YIELD].dropna()

    # By Deal Type
    by_type = []
    for dt in df[C_DEAL_TYPE].dropna().unique():
        sub = df[df[C_DEAL_TYPE] == dt]
        by_type.append({
            'deal_type': dt,
            'avg_total_yield': _safe(sub[C_TOTAL_YIELD].dropna().mean()),
            'avg_monthly_yield': _safe(sub[C_MONTHLY_YIELD].dropna().mean()),
            'total_margin': _safe(sub[C_MARGIN].fillna(0).sum() * mult),
            'total_fees': _safe(sub[C_ORIG_FEE].fillna(0).sum() * mult),
            'count': len(sub),
        })

    # By vintage
    df_c = df.copy()
    df_c['vintage_q'] = df_c[C_INVOICE_DATE].dt.to_period('Q')
    by_vintage = df_c.groupby('vintage_q').agg(
        avg_yield=(C_TOTAL_YIELD, 'mean'),
        margin=(C_MARGIN, lambda x: x.fillna(0).sum()),
        fees=(C_ORIG_FEE, lambda x: x.fillna(0).sum()),
        bill=(C_BILL, 'sum'),
    ).reset_index()
    vintage_yield = [{'vintage': str(r['vintage_q']),
                      'avg_yield': _safe(r['avg_yield']),
                      'margin_rate': _safe(r['margin'] / r['bill'] if r['bill'] > 0 else 0)}
                     for _, r in by_vintage.iterrows()]

    return {
        'total_margin': _safe(total_margin),
        'total_fees': _safe(total_fees),
        'total_revenue': _safe(total_revenue),
        'revenue_over_gmv': _safe(total_revenue / total_bill if total_bill > 0 else 0),
        'avg_total_yield': _safe(yields.mean()),
        'median_total_yield': _safe(yields.median()),
        'avg_monthly_yield': _safe(monthly_yields.mean()),
        'yield_distribution': {
            'min': _safe(yields.min()),
            'p25': _safe(yields.quantile(0.25)) if len(yields) > 0 else None,
            'median': _safe(yields.median()),
            'p75': _safe(yields.quantile(0.75)) if len(yields) > 0 else None,
            'max': _safe(yields.max()),
        },
        'by_deal_type': by_type,
        'by_vintage': vintage_yield,
        'available': True,
    }


def compute_aajil_loss_waterfall(df, mult=1, ref_date=None, aux=None):
    """Loss waterfall: Originated → Realised → Accrued → Written Off."""
    total_originated = df[C_BILL].sum() * mult
    total_realised = df[df[C_STATUS] == 'Realised'][C_BILL].sum() * mult
    total_accrued = df[df[C_STATUS] == 'Accrued'][C_BILL].sum() * mult
    total_wo_originated = df[df[C_STATUS] == 'Written Off'][C_BILL].sum() * mult
    total_wo_amount = df[C_WRITTEN_OFF].fillna(0).sum() * mult
    total_wo_vat_recovered = df[C_WO_VAT].fillna(0).sum() * mult

    wo_deals = df[df[C_STATUS] == 'Written Off']

    # Per-vintage loss
    df_c = df.copy()
    df_c['vintage_q'] = df_c[C_INVOICE_DATE].dt.to_period('Q')
    by_vintage = df_c.groupby('vintage_q').agg(
        originated=(C_BILL, 'sum'),
        wo_count=(C_STATUS, lambda x: (x == 'Written Off').sum()),
        wo_amount=(C_WRITTEN_OFF, lambda x: x.fillna(0).sum()),
    ).reset_index()
    vintage_loss = [{'vintage': str(r['vintage_q']),
                     'originated': _safe(r['originated'] * mult),
                     'written_off': _safe(r['wo_amount'] * mult),
                     'wo_count': int(r['wo_count']),
                     'loss_rate': _safe(r['wo_amount'] / r['originated'] if r['originated'] > 0 else 0)}
                    for _, r in by_vintage.iterrows()]

    return {
        'waterfall': [
            {'stage': 'Originated', 'amount': _safe(total_originated), 'count': len(df)},
            {'stage': 'Realised (Collected)', 'amount': _safe(total_realised), 'count': len(df[df[C_STATUS] == 'Realised'])},
            {'stage': 'Accrued (Active)', 'amount': _safe(total_accrued), 'count': len(df[df[C_STATUS] == 'Accrued'])},
            {'stage': 'Written Off', 'amount': _safe(total_wo_originated), 'count': len(wo_deals)},
        ],
        'written_off_amount': _safe(total_wo_amount),
        'vat_recovered': _safe(total_wo_vat_recovered),
        'net_loss': _safe(total_wo_amount - total_wo_vat_recovered),
        'gross_loss_rate': _safe(total_wo_originated / total_originated if total_originated > 0 else 0),
        'by_vintage': vintage_loss,
        'available': True,
    }


def compute_aajil_customer_segments(df, mult=1, ref_date=None, aux=None):
    """Segmentation by Deal Type, Industry, and customer size."""
    segments = {}

    # By Deal Type
    dt_segs = []
    for dt in ['EMI', 'Bullet']:
        sub = df[df[C_DEAL_TYPE] == dt]
        if len(sub) == 0:
            continue
        dt_segs.append({
            'segment': dt,
            'count': len(sub),
            'volume': _safe(sub[C_BILL].sum() * mult),
            'avg_deal_size': _safe(sub[C_BILL].mean() * mult),
            'avg_tenure': _safe(sub[C_TENURE].dropna().mean()),
            'collection_rate': _safe(sub[C_REALISED].fillna(0).sum() / (sub[C_REALISED].fillna(0).sum() + sub[C_RECEIVABLE].fillna(0).sum()) if (sub[C_REALISED].fillna(0).sum() + sub[C_RECEIVABLE].fillna(0).sum()) > 0 else 0),
            'overdue_pct': _safe((sub[C_OVERDUE_INST].fillna(0) > 0).mean()),
            'avg_yield': _safe(sub[C_TOTAL_YIELD].dropna().mean()),
            'wo_count': int((sub[C_STATUS] == 'Written Off').sum()),
        })
    segments['by_deal_type'] = dt_segs

    # By Industry (bucketed)
    df_c = df.copy()
    df_c['industry_bucket'] = _bucket_industry(df_c[C_INDUSTRY])
    ind_segs = []
    for ind in df_c['industry_bucket'].unique():
        sub = df_c[df_c['industry_bucket'] == ind]
        ind_segs.append({
            'segment': ind,
            'count': len(sub),
            'volume': _safe(sub[C_BILL].sum() * mult),
            'avg_deal_size': _safe(sub[C_BILL].mean() * mult),
            'collection_rate': _safe(sub[C_REALISED].fillna(0).sum() / max(sub[C_REALISED].fillna(0).sum() + sub[C_RECEIVABLE].fillna(0).sum(), 1)),
        })
    ind_segs.sort(key=lambda x: x['volume'] or 0, reverse=True)
    segments['by_industry'] = ind_segs

    # By customer size tier
    cust_vol = df.groupby(C_CUSTOMER_ID)[C_BILL].sum()
    tier_bins = [0, 500_000, 2_000_000, 5_000_000, float('inf')]
    tier_labels = ['Small (<500K)', 'Medium (500K-2M)', 'Large (2M-5M)', 'Enterprise (5M+)']
    cust_tiers = pd.cut(cust_vol, bins=tier_bins, labels=tier_labels)
    tier_segs = []
    for tier in tier_labels:
        custs_in_tier = cust_tiers[cust_tiers == tier].index
        sub = df[df[C_CUSTOMER_ID].isin(custs_in_tier)]
        tier_segs.append({
            'segment': tier,
            'customer_count': len(custs_in_tier),
            'deal_count': len(sub),
            'volume': _safe(sub[C_BILL].sum() * mult),
        })
    segments['by_customer_size'] = tier_segs

    return {
        'segments': segments,
        'available': True,
    }


def compute_aajil_seasonality(df, mult=1, ref_date=None, aux=None):
    """YoY monthly origination patterns."""
    df_c = df.copy()
    df_c['year'] = df_c[C_INVOICE_DATE].dt.year
    df_c['month'] = df_c[C_INVOICE_DATE].dt.month

    monthly = df_c.groupby(['year', 'month']).agg(
        volume=(C_BILL, 'sum'),
        count=(C_TXN_ID, 'count'),
    ).reset_index()
    monthly['volume'] *= mult

    # Pivot for YoY comparison
    years = sorted(monthly['year'].unique())
    months_data = []
    for m in range(1, 13):
        row = {'month': m, 'month_name': pd.Timestamp(2020, m, 1).strftime('%b')}
        for y in years:
            val = monthly[(monthly['year'] == y) & (monthly['month'] == m)]['volume']
            row[str(int(y))] = _safe(val.iloc[0]) if len(val) > 0 else None
        months_data.append(row)

    # Seasonal index
    month_avg = df_c.groupby('month')[C_BILL].sum() * mult
    overall_avg = month_avg.mean()
    seasonal_index = [{'month': m, 'index': _safe(month_avg.get(m, 0) / overall_avg if overall_avg > 0 else 0)}
                      for m in range(1, 13)]

    return {
        'months': months_data,
        'years': [str(int(y)) for y in years],
        'seasonal_index': seasonal_index,
        'available': True,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
# STATIC QUALITATIVE DATA (from investor deck — not in tape)
# ═══════════════════════════════════════════════════════════════════════════════

AAJIL_QUALITATIVE_DATA = {
    "company_overview": {
        "name": "Aajil", "parent": "Buildnow", "founded": 2022,
        "sector": "SME lending — industrial raw materials trade credit",
        "country": "Saudi Arabia", "currency": "SAR", "employees": 64,
        "credit_as_pct_revenue": "2.5% - 5.0%", "pn_coverage": 1.0,
        "avg_tenor_months": 4.5, "max_tenor_months": 6,
        "repayment_structure": "Instalments",
        "credit_deployment_hours": 24,
        "investors": ["SIC", "Khawrizmi Ventures", "RAED", "Arbah Capital", "STV", "Al-Raedah Finance", "JOA Capital"],
    },
    "customer_types": [
        {"type": "Manufacturer", "description": "Industrial manufacturers purchasing raw materials", "color": "#5B8DEF",
         "min_gross_margin": 0.06, "min_net_margin": 0.01, "min_current_ratio": 0.8},
        {"type": "Contractor", "description": "Construction and project-based contractors", "color": "#C9A84C",
         "min_gross_margin": 0.07, "min_net_margin": 0.01, "min_current_ratio": 0.8},
        {"type": "Wholesale Trader", "description": "Wholesale trading companies", "color": "#2DD4BF",
         "min_gross_margin": 0.07, "min_net_margin": 0.01, "min_current_ratio": 0.8},
    ],
    "sales_channels": [
        {"channel": "Performance Marketing", "pct": 34, "color": "#5B8DEF"},
        {"channel": "Outbound Prospecting", "pct": 33, "color": "#C9A84C"},
        {"channel": "Referral Networks", "pct": 25, "color": "#2DD4BF"},
        {"channel": "Field Sales", "pct": 8, "color": "#F06060"},
    ],
    "trust_score_system": {
        "scores": [
            {"score": 5, "label": "Green", "description": "Good history, enablement-first approach", "color": "#2DD4BF"},
            {"score": 4, "label": "Amber", "description": "Minor delays, tighter timelines", "color": "#C9A84C"},
            {"score": 3, "label": "Red", "description": "Repeated issues, bank statement required", "color": "#F06060"},
            {"score": 2, "label": "Critical", "description": "Severe default risk, 48h payment deadline", "color": "#D32F2F"},
            {"score": 1, "label": "Critical", "description": "Extreme risk, immediate escalation", "color": "#B71C1C"},
        ],
        "collections_phases": [
            {"phase": "Preventive", "dpd_range": "-15 to 0", "description": "Proactive reminders, payment facilitation", "color": "#2DD4BF"},
            {"phase": "Active", "dpd_range": "1 to 60", "description": "Personal calls, site visits, escalation", "color": "#C9A84C"},
            {"phase": "Legal", "dpd_range": "60+", "description": "PN enforcement, SIMAH classification, asset recovery", "color": "#F06060"},
        ],
    },
    "underwriting": {
        "stages": ["Sales Screening", "Risk Assessment", "Credit Report", "Credit Decision Committee"],
        "stages_enriched": [
            {"name": "Sales Screening", "number": 1, "color": "#5B8DEF"},
            {"name": "Risk Assessment", "number": 2, "color": "#2DD4BF"},
            {"name": "Credit Report", "number": 3, "color": "#C9A84C"},
            {"name": "Credit Decision Committee", "number": 4, "color": "#F06060"},
        ],
        "min_revenue_sar": 5000000, "max_leverage": 0.50,
        "non_cdc_approval_limit_sar": 400000,
        "disqualification_rules": [
            "Revenue below SAR 5M in last 12 months",
            "Revenue variance >10% between bank/VAT sources",
            "Continuous revenue decline >20%/year for 3 consecutive years",
            "Leverage >50% with current ratio <1.0",
            "Funded exposure >30% of revenue",
            "Active legal cases (company or personal)",
            "Past due obligations without proof of payment",
        ],
    },
    "risk_mitigation": [
        {"factor": "Minimal Exposure", "detail": "Credit at 2.5-5.0% of client revenue"},
        {"factor": "Diversification", "detail": "Multiple sectors: manufacturer, contractor, trader"},
        {"factor": "Asset-Based", "detail": "Purchasing raw materials directly, not disbursing cash"},
        {"factor": "Short Duration", "detail": "4-5 month avg tenor, max 6 months"},
        {"factor": "Robust Collections", "detail": "Automated messages, site visits, calls, legal"},
        {"factor": "Promissory Notes", "detail": "100% PN coverage for each issuance"},
        {"factor": "Credit Assessment", "detail": "Technical, financial, and legal assessment"},
        {"factor": "Instalments", "detail": "Instalment repayment, not bullet at maturity"},
    ],
    "dpd_reassessment": [
        {"dpd_range": "1-10", "policy": "Eligible for standard reassessment"},
        {"dpd_range": "11-29 (compliant)", "policy": "New facility if trust score >= 80 AND bank confirms liquidity shortfall"},
        {"dpd_range": "11-29 (non-compliant)", "policy": "Trust score < 80: disqualified"},
        {"dpd_range": "30+ (first facility)", "policy": "Suspended min 2 quarters, full reassessment required"},
        {"dpd_range": "30+ (wilful)", "policy": "Permanently disqualified if cash >= 150% of past due"},
    ],
    "technology": {
        "platforms": ["R-Square (deal orchestration)", "C-Square (credit intelligence)", "Basirah (AI document intelligence)"],
        "stack": ["FastAPI", "Django", "PostgreSQL", "BigQuery", "Docker", "Kubernetes", "Redis", "Celery", "Sentry"],
        "ai_tools": ["Claude", "OpenAI", "Gemini", "Google AI Studio", "Neo4j"],
    },
    "data_notes": [
        "Loan tape from Cascade Debt (Apr 13, 2026) — 1,245 deals across 7 sheets",
        "Company overview/underwriting/trust scores from investor deck (Mar 2026)",
        "Customer Industry missing for 39% of deals — bucketed into top-10 + Other + Unknown",
        "Deal Types: EMI (instalment, 51%) and Bullet (single payment, 49%)",
        "Trust score system (1-5) is Aajil's proprietary collections prioritization model",
        "Buildnow is the parent company; Aajil is the product/brand name",
        "DPD calculated from overdue instalment counts (not explicit days past due)",
        "Written Off: 19 deals (1.5%), all from Sep 2025 - Feb 2026",
    ],
}


# ═══════════════════════════════════════════════════════════════════════════════
# LEGACY JSON SUPPORT (backward compat)
# ═══════════════════════════════════════════════════════════════════════════════

def parse_aajil_data(filepath):
    """Load and enrich a pre-processed Aajil JSON snapshot (legacy)."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    _enrich_overview(data)
    _enrich_traction(data)
    _enrich_customer_segments_json(data)
    _enrich_trust_scores(data)
    _enrich_underwriting_json(data)
    return data


def _enrich_overview(data):
    co = data.get('company_overview', {})
    overview = {
        'total_customers': co.get('total_customers', 0),
        'total_transactions': co.get('total_transactions', 0),
        'aum_sar': co.get('aum_sar', 0),
        'gmv_sar': co.get('gmv_sar', 0),
        'dpd60_plus_rate': co.get('dpd60_plus_rate', 0),
        'pn_coverage': co.get('pn_coverage', 0),
        'employees': co.get('employees', 0),
    }
    milestones = data.get('gmv_milestones', [])
    if len(milestones) >= 2:
        latest, prev = milestones[-1], milestones[-2]
        if prev['gmv_sar'] > 0:
            overview['gmv_yoy_growth'] = round((latest['gmv_sar'] - prev['gmv_sar']) / prev['gmv_sar'] * 100, 1)
    data['overview'] = overview


def _enrich_traction(data):
    traction = data.get('traction', {})
    if traction.get('volume_monthly'):
        return  # Already has Cascade data


def _enrich_customer_segments_json(data):
    colors = {'Manufacturer': '#5B8DEF', 'Contractor': '#C9A84C', 'Wholesale Trader': '#2DD4BF'}
    for ct in data.get('customer_types', []):
        ct['color'] = colors.get(ct['type'], '#8494A7')
    channel_colors = {'Performance Marketing': '#5B8DEF', 'Outbound Prospecting': '#C9A84C',
                      'Referral Networks': '#2DD4BF', 'Field Sales': '#F06060'}
    for sc in data.get('sales_channels', []):
        sc['color'] = channel_colors.get(sc['channel'], '#8494A7')


def _enrich_trust_scores(data):
    score_colors = {5: '#2DD4BF', 4: '#C9A84C', 3: '#F06060', 2: '#D32F2F', 1: '#B71C1C'}
    ts = data.get('trust_score_system', {})
    for s in ts.get('scores', []):
        s['color'] = score_colors.get(s['score'], '#8494A7')
    phase_colors = {'Preventive': '#2DD4BF', 'Active': '#C9A84C', 'Legal': '#F06060'}
    for p in ts.get('collections_phases', []):
        p['color'] = phase_colors.get(p['phase'], '#8494A7')


def _enrich_underwriting_json(data):
    uw = data.get('underwriting', {})
    stage_colors = ['#5B8DEF', '#2DD4BF', '#C9A84C', '#F06060']
    stages = uw.get('stages', [])
    uw['stages_enriched'] = [
        {'name': s, 'number': i + 1, 'color': stage_colors[i] if i < len(stage_colors) else '#8494A7'}
        for i, s in enumerate(stages)
    ]


def get_aajil_summary(data):
    """Return summary KPIs for the landing page card (from JSON)."""
    co = data.get('company_overview', {})
    return {
        'total_purchase_value': co.get('aum_sar', 0),
        'face_value_label': 'AUM (Outstanding)',
        'total_deals': co.get('total_transactions', 0),
        'deals_label': 'Credit Transactions',
        'collection_rate': 1.0 - co.get('dpd60_plus_rate', 0),
        'total_collected': co.get('gmv_sar', 0),
        'total_customers': co.get('total_customers', 0),
    }
