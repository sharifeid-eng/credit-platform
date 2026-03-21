"""
SILQ analysis module — BNPL & RBF POS lending analytics.

All computation functions for SILQ's loan tape. Uses native column names:
  Deal ID, Disbursed_Amount (SAR), Outstanding_Amount (SAR), Overdue_Amount (SAR),
  Total_Collectable_Amount (SAR), Tenure, Shop_ID, Shop_Credit_Limit (SAR),
  Repayment_Deadline, Amt_Repaid, Last_Collection_Date, Loan_Age,
  Margin Collected, Principal Collected, Product, Loan_Status,
  Disbursement_Date, Comment
"""

import pandas as pd
import numpy as np
from datetime import datetime


# ── Column aliases ────────────────────────────────────────────────────────────
# Map short names to actual column names (which include currency suffix)
C_DISBURSED = 'Disbursed_Amount (SAR)'
C_OUTSTANDING = 'Outstanding_Amount (SAR)'
C_OVERDUE = 'Overdue_Amount (SAR)'
C_COLLECTABLE = 'Total_Collectable_Amount (SAR)'
C_REPAID = 'Amt_Repaid'
C_MARGIN = 'Margin Collected'
C_PRINCIPAL = 'Principal Collected'
C_SHOP_LIMIT = 'Shop_Credit_Limit (SAR)'
C_DEAL_ID = 'Deal ID'
C_SHOP_ID = 'Shop_ID'
C_TENURE = 'Tenure'
C_STATUS = 'Loan_Status'
C_PRODUCT = 'Product'
C_DISB_DATE = 'Disbursement_Date'
C_REPAY_DEADLINE = 'Repayment_Deadline'
C_LAST_COLL = 'Last_Collection_Date'
C_LOAN_AGE = 'Loan_Age'


def filter_silq_by_date(df, as_of_date):
    """Filter loans to those disbursed on or before as_of_date."""
    if not as_of_date or C_DISB_DATE not in df.columns:
        return df
    cutoff = pd.to_datetime(as_of_date)
    return df[df[C_DISB_DATE] <= cutoff].copy()


def _dpd(df, ref_date=None):
    """Compute Days Past Due for each loan."""
    if ref_date is None:
        ref_date = pd.Timestamp.now().normalize()
    else:
        ref_date = pd.to_datetime(ref_date)
    if C_REPAY_DEADLINE not in df.columns:
        return pd.Series(0, index=df.index)
    dpd = (ref_date - df[C_REPAY_DEADLINE]).dt.days.clip(lower=0)
    # Closed loans have 0 DPD regardless
    if C_STATUS in df.columns:
        dpd = dpd.where(df[C_STATUS] != 'Closed', 0)
    return dpd


def _safe(val):
    """Convert numpy types to Python natives for JSON serialization."""
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val) if not np.isnan(val) else 0
    if isinstance(val, (np.bool_,)):
        return bool(val)
    return val


# ── 1. Summary ────────────────────────────────────────────────────────────────

def compute_silq_summary(df, mult=1):
    total_disbursed = df[C_DISBURSED].sum() * mult if C_DISBURSED in df.columns else 0
    total_outstanding = df[C_OUTSTANDING].sum() * mult if C_OUTSTANDING in df.columns else 0
    total_overdue = df[C_OVERDUE].sum() * mult if C_OVERDUE in df.columns else 0
    total_repaid = df[C_REPAID].sum() * mult if C_REPAID in df.columns else 0
    total_collectable = df[C_COLLECTABLE].sum() * mult if C_COLLECTABLE in df.columns else 0

    n = len(df)
    active = int((df[C_STATUS] != 'Closed').sum()) if C_STATUS in df.columns else n
    closed = int((df[C_STATUS] == 'Closed').sum()) if C_STATUS in df.columns else 0

    collection_rate = (total_repaid / total_collectable * 100) if total_collectable else 0
    overdue_rate = (total_overdue / total_outstanding * 100) if total_outstanding else 0

    dpd = _dpd(df)
    par30 = float((dpd > 30).sum() / max(active, 1) * 100)
    par60 = float((dpd > 60).sum() / max(active, 1) * 100)
    par90 = float((dpd > 90).sum() / max(active, 1) * 100)

    avg_tenure = float(df[C_TENURE].mean()) if C_TENURE in df.columns else 0

    # Product mix
    product_mix = {}
    if C_PRODUCT in df.columns:
        mix = df[C_PRODUCT].value_counts()
        for p, c in mix.items():
            product_mix[p] = int(c)

    # HHI on shops
    hhi_shop = 0
    top_1_shop_pct = 0
    if C_SHOP_ID in df.columns and C_DISBURSED in df.columns:
        shop_totals = df.groupby(C_SHOP_ID)[C_DISBURSED].sum()
        shares = shop_totals / shop_totals.sum()
        hhi_shop = float((shares ** 2).sum())
        top_1_shop_pct = float(shares.max() * 100)

    return {
        'total_deals': n,
        'total_disbursed': _safe(total_disbursed),
        'total_outstanding': _safe(total_outstanding),
        'total_overdue': _safe(total_overdue),
        'total_repaid': _safe(total_repaid),
        'total_collectable': _safe(total_collectable),
        'collection_rate': _safe(collection_rate),
        'overdue_rate': _safe(overdue_rate),
        'active_deals': active,
        'completed_deals': closed,
        'par30': _safe(par30),
        'par60': _safe(par60),
        'par90': _safe(par90),
        'avg_tenure': _safe(avg_tenure),
        'product_mix': product_mix,
        'hhi_shop': _safe(hhi_shop),
        'top_1_shop_pct': _safe(top_1_shop_pct),
    }


# ── 2. Delinquency ───────────────────────────────────────────────────────────

def compute_silq_delinquency(df, mult=1):
    dpd = _dpd(df)
    active = df[df[C_STATUS] != 'Closed'] if C_STATUS in df.columns else df
    active_dpd = _dpd(active)

    # DPD buckets
    buckets = [
        {'label': 'Current',   'min': 0,  'max': 0},
        {'label': '1-30 DPD',  'min': 1,  'max': 30},
        {'label': '31-60 DPD', 'min': 31, 'max': 60},
        {'label': '61-90 DPD', 'min': 61, 'max': 90},
        {'label': '90+ DPD',   'min': 91, 'max': 99999},
    ]
    bucket_data = []
    for b in buckets:
        mask = (active_dpd >= b['min']) & (active_dpd <= b['max'])
        count = int(mask.sum())
        amount = float(active.loc[mask, C_OUTSTANDING].sum() * mult) if C_OUTSTANDING in active.columns else 0
        bucket_data.append({
            'label': b['label'],
            'count': count,
            'amount': _safe(amount),
            'pct': _safe(count / max(len(active), 1) * 100),
        })

    # PAR metrics
    n_active = max(len(active), 1)
    par30 = float((active_dpd > 30).sum() / n_active * 100)
    par60 = float((active_dpd > 60).sum() / n_active * 100)
    par90 = float((active_dpd > 90).sum() / n_active * 100)

    # Monthly delinquency trend (by disbursement month)
    monthly = []
    if C_DISB_DATE in df.columns and C_STATUS in df.columns:
        df2 = df.copy()
        df2['_dpd'] = dpd
        df2['_month'] = df2[C_DISB_DATE].dt.to_period('M')
        for period, grp in df2.groupby('_month'):
            act = grp[grp[C_STATUS] != 'Closed']
            if len(act) == 0:
                continue
            monthly.append({
                'Month': str(period),
                'total': int(len(grp)),
                'overdue_count': int((act['_dpd'] > 0).sum()),
                'overdue_rate': _safe((act['_dpd'] > 0).sum() / len(act) * 100),
                'par30_rate': _safe((act['_dpd'] > 30).sum() / len(act) * 100),
            })

    # Top overdue shops
    top_shops = []
    if C_SHOP_ID in df.columns and C_OVERDUE in df.columns:
        shop_overdue = df[df[C_OVERDUE] > 0].groupby(C_SHOP_ID).agg(
            overdue=(C_OVERDUE, 'sum'),
            count=(C_DEAL_ID, 'count')
        ).sort_values('overdue', ascending=False).head(10)
        for shop_id, row in shop_overdue.iterrows():
            top_shops.append({
                'shop_id': _safe(shop_id),
                'overdue': _safe(row['overdue'] * mult),
                'count': int(row['count']),
            })

    return {
        'buckets': bucket_data,
        'par30': _safe(par30),
        'par60': _safe(par60),
        'par90': _safe(par90),
        'monthly': monthly,
        'top_shops': top_shops,
    }


# ── 3. Collections ───────────────────────────────────────────────────────────

def compute_silq_collections(df, mult=1):
    total_repaid = df[C_REPAID].sum() * mult if C_REPAID in df.columns else 0
    total_collectable = df[C_COLLECTABLE].sum() * mult if C_COLLECTABLE in df.columns else 0
    total_margin = df[C_MARGIN].sum() * mult if C_MARGIN in df.columns else 0
    total_principal = df[C_PRINCIPAL].sum() * mult if C_PRINCIPAL in df.columns else 0

    repayment_rate = (total_repaid / total_collectable * 100) if total_collectable else 0

    # Monthly collection trend
    monthly = []
    if C_DISB_DATE in df.columns:
        df2 = df.copy()
        df2['_month'] = df2[C_DISB_DATE].dt.to_period('M')
        for period, grp in df2.groupby('_month'):
            m_repaid = grp[C_REPAID].sum() * mult if C_REPAID in grp.columns else 0
            m_collectable = grp[C_COLLECTABLE].sum() * mult if C_COLLECTABLE in grp.columns else 0
            m_margin = grp[C_MARGIN].sum() * mult if C_MARGIN in grp.columns else 0
            m_principal = grp[C_PRINCIPAL].sum() * mult if C_PRINCIPAL in grp.columns else 0
            monthly.append({
                'Month': str(period),
                'repaid': _safe(m_repaid),
                'collectable': _safe(m_collectable),
                'margin': _safe(m_margin),
                'principal': _safe(m_principal),
                'rate': _safe(m_repaid / m_collectable * 100 if m_collectable else 0),
                'deals': int(len(grp)),
            })

    # By product type
    by_product = []
    if C_PRODUCT in df.columns:
        for prod, grp in df.groupby(C_PRODUCT):
            p_repaid = grp[C_REPAID].sum() * mult if C_REPAID in grp.columns else 0
            p_collectable = grp[C_COLLECTABLE].sum() * mult if C_COLLECTABLE in grp.columns else 0
            by_product.append({
                'product': str(prod),
                'repaid': _safe(p_repaid),
                'collectable': _safe(p_collectable),
                'rate': _safe(p_repaid / p_collectable * 100 if p_collectable else 0),
                'deals': int(len(grp)),
            })

    return {
        'total_repaid': _safe(total_repaid),
        'total_collectable': _safe(total_collectable),
        'total_margin': _safe(total_margin),
        'total_principal': _safe(total_principal),
        'repayment_rate': _safe(repayment_rate),
        'monthly': monthly,
        'by_product': by_product,
    }


# ── 4. Concentration ─────────────────────────────────────────────────────────

def compute_silq_concentration(df, mult=1):
    # Shop concentration
    shops = []
    hhi = 0
    if C_SHOP_ID in df.columns and C_DISBURSED in df.columns:
        shop_totals = df.groupby(C_SHOP_ID)[C_DISBURSED].sum().sort_values(ascending=False)
        total = shop_totals.sum()
        shares = shop_totals / total if total else shop_totals
        hhi = float((shares ** 2).sum())
        for shop_id, val in shop_totals.head(15).items():
            shops.append({
                'shop_id': _safe(shop_id),
                'disbursed': _safe(val * mult),
                'share': _safe(val / total * 100 if total else 0),
                'deals': int((df[C_SHOP_ID] == shop_id).sum()),
            })

    # Credit limit utilization
    utilization = []
    if C_SHOP_ID in df.columns and C_OUTSTANDING in df.columns and C_SHOP_LIMIT in df.columns:
        shop_util = df.groupby(C_SHOP_ID).agg(
            outstanding=(C_OUTSTANDING, 'sum'),
            limit=(C_SHOP_LIMIT, 'first'),
        )
        shop_util['util_pct'] = (shop_util['outstanding'] / shop_util['limit'] * 100).clip(0, 100)
        for shop_id, row in shop_util.sort_values('util_pct', ascending=False).head(15).iterrows():
            utilization.append({
                'shop_id': _safe(shop_id),
                'outstanding': _safe(row['outstanding'] * mult),
                'limit': _safe(row['limit'] * mult),
                'util_pct': _safe(row['util_pct']),
            })

    # Product mix
    product_mix = []
    if C_PRODUCT in df.columns and C_DISBURSED in df.columns:
        prod_totals = df.groupby(C_PRODUCT).agg(
            disbursed=(C_DISBURSED, 'sum'),
            count=(C_DEAL_ID, 'count'),
        )
        total_disb = prod_totals['disbursed'].sum()
        for prod, row in prod_totals.iterrows():
            product_mix.append({
                'product': str(prod),
                'disbursed': _safe(row['disbursed'] * mult),
                'count': int(row['count']),
                'share': _safe(row['disbursed'] / total_disb * 100 if total_disb else 0),
            })

    # Loan size distribution
    size_dist = []
    if C_DISBURSED in df.columns:
        bins = [0, 50_000, 100_000, 200_000, 500_000, 1_000_000, float('inf')]
        labels = ['<50K', '50-100K', '100-200K', '200-500K', '500K-1M', '>1M']
        df2 = df.copy()
        df2['_size_band'] = pd.cut(df2[C_DISBURSED], bins=bins, labels=labels, right=False)
        for label, grp in df2.groupby('_size_band', observed=True):
            size_dist.append({
                'band': str(label),
                'count': int(len(grp)),
                'total': _safe(grp[C_DISBURSED].sum() * mult),
            })

    return {
        'shops': shops,
        'hhi': _safe(hhi),
        'utilization': utilization,
        'product_mix': product_mix,
        'size_distribution': size_dist,
    }


# ── 5. Cohorts ────────────────────────────────────────────────────────────────

def compute_silq_cohorts(df, mult=1):
    cohorts = []
    if C_DISB_DATE not in df.columns:
        return {'cohorts': cohorts}

    df2 = df.copy()
    df2['_month'] = df2[C_DISB_DATE].dt.to_period('M')
    df2['_dpd'] = _dpd(df2)

    for period, grp in df2.groupby('_month'):
        disbursed = grp[C_DISBURSED].sum() * mult if C_DISBURSED in grp.columns else 0
        repaid = grp[C_REPAID].sum() * mult if C_REPAID in grp.columns else 0
        outstanding = grp[C_OUTSTANDING].sum() * mult if C_OUTSTANDING in grp.columns else 0
        overdue = grp[C_OVERDUE].sum() * mult if C_OVERDUE in grp.columns else 0
        margin = grp[C_MARGIN].sum() * mult if C_MARGIN in grp.columns else 0
        collectable = grp[C_COLLECTABLE].sum() * mult if C_COLLECTABLE in grp.columns else 0

        n = len(grp)
        active = grp[grp[C_STATUS] != 'Closed'] if C_STATUS in grp.columns else grp
        n_active = len(active)
        dpd_active = grp.loc[active.index, '_dpd'] if len(active) > 0 else pd.Series(dtype=float)

        cohorts.append({
            'vintage': str(period),
            'deals': n,
            'disbursed': _safe(disbursed),
            'repaid': _safe(repaid),
            'outstanding': _safe(outstanding),
            'overdue': _safe(overdue),
            'margin': _safe(margin),
            'collection_pct': _safe(repaid / collectable * 100 if collectable else 0),
            'overdue_pct': _safe(overdue / outstanding * 100 if outstanding else 0),
            'active': n_active,
            'closed': n - n_active,
            'par30_pct': _safe((dpd_active > 30).sum() / max(n_active, 1) * 100),
            'avg_tenure': _safe(grp[C_TENURE].mean() if C_TENURE in grp.columns else 0),
        })

    # Totals row
    if cohorts:
        totals = {
            'vintage': 'Total',
            'deals': sum(c['deals'] for c in cohorts),
            'disbursed': _safe(sum(c['disbursed'] for c in cohorts)),
            'repaid': _safe(sum(c['repaid'] for c in cohorts)),
            'outstanding': _safe(sum(c['outstanding'] for c in cohorts)),
            'overdue': _safe(sum(c['overdue'] for c in cohorts)),
            'margin': _safe(sum(c['margin'] for c in cohorts)),
        }
        tot_coll = df[C_COLLECTABLE].sum() * mult if C_COLLECTABLE in df.columns else 0
        totals['collection_pct'] = _safe(totals['repaid'] / tot_coll * 100 if tot_coll else 0)
        totals['overdue_pct'] = _safe(totals['overdue'] / totals['outstanding'] * 100 if totals['outstanding'] else 0)
        totals['active'] = sum(c['active'] for c in cohorts)
        totals['closed'] = sum(c['closed'] for c in cohorts)
        totals['par30_pct'] = _safe(df2.loc[df2[C_STATUS] != 'Closed', '_dpd'].gt(30).sum() / max(totals['active'], 1) * 100 if C_STATUS in df2.columns else 0)
        totals['avg_tenure'] = _safe(df[C_TENURE].mean() if C_TENURE in df.columns else 0)
        cohorts.append(totals)

    return {'cohorts': cohorts}


# ── 6. Yield & Margins ───────────────────────────────────────────────────────

def compute_silq_yield(df, mult=1):
    total_margin = df[C_MARGIN].sum() * mult if C_MARGIN in df.columns else 0
    total_disbursed = df[C_DISBURSED].sum() * mult if C_DISBURSED in df.columns else 0
    margin_rate = (total_margin / total_disbursed * 100) if total_disbursed else 0

    # Completed-only margin
    closed = df[df[C_STATUS] == 'Closed'] if C_STATUS in df.columns else df
    closed_margin = closed[C_MARGIN].sum() * mult if C_MARGIN in closed.columns else 0
    closed_disbursed = closed[C_DISBURSED].sum() * mult if C_DISBURSED in closed.columns else 0
    realised_margin_rate = (closed_margin / closed_disbursed * 100) if closed_disbursed else 0

    # By product type
    by_product = []
    if C_PRODUCT in df.columns:
        for prod, grp in df.groupby(C_PRODUCT):
            m = grp[C_MARGIN].sum() * mult if C_MARGIN in grp.columns else 0
            d = grp[C_DISBURSED].sum() * mult if C_DISBURSED in grp.columns else 0
            by_product.append({
                'product': str(prod),
                'margin': _safe(m),
                'disbursed': _safe(d),
                'margin_rate': _safe(m / d * 100 if d else 0),
                'deals': int(len(grp)),
            })

    # By tenure band
    by_tenure = []
    if C_TENURE in df.columns:
        bins = [0, 5, 10, 15, 20, 30, float('inf')]
        labels = ['1-4w', '5-9w', '10-14w', '15-19w', '20-29w', '30w+']
        df2 = df.copy()
        df2['_tband'] = pd.cut(df2[C_TENURE], bins=bins, labels=labels, right=False)
        for label, grp in df2.groupby('_tband', observed=True):
            m = grp[C_MARGIN].sum() * mult if C_MARGIN in grp.columns else 0
            d = grp[C_DISBURSED].sum() * mult if C_DISBURSED in grp.columns else 0
            by_tenure.append({
                'band': str(label),
                'margin': _safe(m),
                'disbursed': _safe(d),
                'margin_rate': _safe(m / d * 100 if d else 0),
                'deals': int(len(grp)),
            })

    # Monthly margin trend
    monthly = []
    if C_DISB_DATE in df.columns:
        df3 = df.copy()
        df3['_month'] = df3[C_DISB_DATE].dt.to_period('M')
        for period, grp in df3.groupby('_month'):
            m = grp[C_MARGIN].sum() * mult if C_MARGIN in grp.columns else 0
            d = grp[C_DISBURSED].sum() * mult if C_DISBURSED in grp.columns else 0
            monthly.append({
                'Month': str(period),
                'margin': _safe(m),
                'disbursed': _safe(d),
                'margin_rate': _safe(m / d * 100 if d else 0),
            })

    return {
        'total_margin': _safe(total_margin),
        'total_disbursed': _safe(total_disbursed),
        'margin_rate': _safe(margin_rate),
        'realised_margin_rate': _safe(realised_margin_rate),
        'by_product': by_product,
        'by_tenure': by_tenure,
        'monthly': monthly,
    }


# ── 7. Tenure Analysis ───────────────────────────────────────────────────────

def compute_silq_tenure(df, mult=1):
    # Tenure distribution
    distribution = []
    if C_TENURE in df.columns:
        bins = [0, 5, 10, 15, 20, 30, float('inf')]
        labels = ['1-4w', '5-9w', '10-14w', '15-19w', '20-29w', '30w+']
        df2 = df.copy()
        df2['_tband'] = pd.cut(df2[C_TENURE], bins=bins, labels=labels, right=False)
        df2['_dpd'] = _dpd(df2)
        for label, grp in df2.groupby('_tband', observed=True):
            disbursed = grp[C_DISBURSED].sum() * mult if C_DISBURSED in grp.columns else 0
            repaid = grp[C_REPAID].sum() * mult if C_REPAID in grp.columns else 0
            collectable = grp[C_COLLECTABLE].sum() * mult if C_COLLECTABLE in grp.columns else 0
            margin = grp[C_MARGIN].sum() * mult if C_MARGIN in grp.columns else 0
            active = grp[grp[C_STATUS] != 'Closed'] if C_STATUS in grp.columns else grp
            dpd_active = grp.loc[active.index, '_dpd']
            distribution.append({
                'band': str(label),
                'count': int(len(grp)),
                'disbursed': _safe(disbursed),
                'collection_rate': _safe(repaid / collectable * 100 if collectable else 0),
                'dpd_rate': _safe((dpd_active > 0).sum() / max(len(active), 1) * 100),
                'par30_rate': _safe((dpd_active > 30).sum() / max(len(active), 1) * 100),
                'margin_rate': _safe(margin / disbursed * 100 if disbursed else 0),
                'avg_tenure': _safe(grp[C_TENURE].mean()),
            })

    # By product
    by_product = []
    if C_PRODUCT in df.columns and C_TENURE in df.columns:
        for prod, grp in df.groupby(C_PRODUCT):
            by_product.append({
                'product': str(prod),
                'avg_tenure': _safe(grp[C_TENURE].mean()),
                'median_tenure': _safe(grp[C_TENURE].median()),
                'min_tenure': _safe(grp[C_TENURE].min()),
                'max_tenure': _safe(grp[C_TENURE].max()),
                'count': int(len(grp)),
            })

    avg = float(df[C_TENURE].mean()) if C_TENURE in df.columns else 0
    median = float(df[C_TENURE].median()) if C_TENURE in df.columns else 0

    return {
        'distribution': distribution,
        'by_product': by_product,
        'avg_tenure': _safe(avg),
        'median_tenure': _safe(median),
    }


# ── 8. Borrowing Base ────────────────────────────────────────────────────────

def compute_silq_borrowing_base(df, mult=1):
    """Compute borrowing base eligibility waterfall."""
    dpd = _dpd(df)
    active = df[df[C_STATUS] != 'Closed'].copy() if C_STATUS in df.columns else df.copy()
    active['_dpd'] = _dpd(active)

    total_ar = active[C_OUTSTANDING].sum() * mult if C_OUTSTANDING in active.columns else 0

    # Ineligible: DPD > 60
    inelig_dpd = active.loc[active['_dpd'] > 60, C_OUTSTANDING].sum() * mult if C_OUTSTANDING in active.columns else 0

    # Ineligible: single shop > 20% concentration
    inelig_conc = 0
    if C_SHOP_ID in active.columns and C_OUTSTANDING in active.columns and total_ar > 0:
        shop_out = active.groupby(C_SHOP_ID)[C_OUTSTANDING].sum() * mult
        over_limit = shop_out[shop_out / total_ar > 0.20]
        if len(over_limit) > 0:
            inelig_conc = float((over_limit - total_ar * 0.20).clip(lower=0).sum())

    total_ineligible = inelig_dpd + inelig_conc
    eligible = max(total_ar - total_ineligible, 0)
    advance_rate = 0.80
    borrowing_base = eligible * advance_rate

    waterfall = [
        {'label': 'Total Outstanding A/R', 'value': _safe(total_ar), 'type': 'total'},
        {'label': 'Ineligible (DPD > 60)', 'value': _safe(-inelig_dpd), 'type': 'deduction'},
        {'label': 'Ineligible (Concentration)', 'value': _safe(-inelig_conc), 'type': 'deduction'},
        {'label': 'Eligible A/R', 'value': _safe(eligible), 'type': 'subtotal'},
        {'label': f'Advance Rate ({advance_rate:.0%})', 'value': _safe(-eligible * (1 - advance_rate)), 'type': 'deduction'},
        {'label': 'Borrowing Base', 'value': _safe(borrowing_base), 'type': 'result'},
    ]

    # Eligibility by product
    by_product = []
    if C_PRODUCT in active.columns and C_OUTSTANDING in active.columns:
        for prod, grp in active.groupby(C_PRODUCT):
            p_total = grp[C_OUTSTANDING].sum() * mult
            p_inelig = grp.loc[grp['_dpd'] > 60, C_OUTSTANDING].sum() * mult
            p_elig = max(p_total - p_inelig, 0)
            by_product.append({
                'product': str(prod),
                'total': _safe(p_total),
                'ineligible': _safe(p_inelig),
                'eligible': _safe(p_elig),
                'elig_pct': _safe(p_elig / p_total * 100 if p_total else 0),
            })

    return {
        'waterfall': waterfall,
        'total_ar': _safe(total_ar),
        'eligible': _safe(eligible),
        'borrowing_base': _safe(borrowing_base),
        'advance_rate': advance_rate,
        'by_product': by_product,
    }
