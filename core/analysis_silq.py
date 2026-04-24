"""
SILQ analysis module — BNPL, RBF & RCL POS lending analytics.

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
        import logging
        logging.getLogger('laith.silq').warning(
            f"Column '{C_REPAY_DEADLINE}' missing — DPD defaulting to 0 for all loans. "
            "PAR, covenants, and BB eligibility may be unreliable."
        )
        return pd.Series(0, index=df.index)
    dpd = (ref_date - df[C_REPAY_DEADLINE]).dt.days.clip(lower=0)
    # Closed loans have 0 DPD regardless
    if C_STATUS in df.columns:
        dpd = dpd.where(df[C_STATUS] != 'Closed', 0)
    return dpd


def _ensure_str_shop_id(df):
    """Ensure Shop_ID is string type for safe groupby operations."""
    if C_SHOP_ID in df.columns:
        df[C_SHOP_ID] = df[C_SHOP_ID].astype(str)
    return df


def _safe(val):
    """Convert numpy types to Python natives for JSON serialization.

    NaN and inf are converted to 0 to prevent JSON serialization errors.
    Note: this means 'missing data' and 'genuine zero' are indistinguishable downstream.
    """
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        if np.isnan(val) or np.isinf(val):
            return 0
        return float(val)
    if isinstance(val, (np.bool_,)):
        return bool(val)
    return val


# ── 1. Summary ────────────────────────────────────────────────────────────────

def compute_silq_summary(df, mult=1, ref_date=None):
    df = _ensure_str_shop_id(df)
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

    # GBV-weighted PAR: Outstanding of DPD>X / Total Outstanding of active loans
    active_mask = df[C_STATUS] != 'Closed' if C_STATUS in df.columns else pd.Series(True, index=df.index)
    active_df = df[active_mask]
    active_dpd = _dpd(active_df, ref_date)
    total_active_out = active_df[C_OUTSTANDING].sum() if C_OUTSTANDING in active_df.columns else 0
    par30 = float(active_df.loc[active_dpd > 30, C_OUTSTANDING].sum() / max(total_active_out, 1) * 100) if total_active_out else 0
    par60 = float(active_df.loc[active_dpd > 60, C_OUTSTANDING].sum() / max(total_active_out, 1) * 100) if total_active_out else 0
    par90 = float(active_df.loc[active_dpd > 90, C_OUTSTANDING].sum() / max(total_active_out, 1) * 100) if total_active_out else 0

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
        'total_purchase_value': _safe(total_disbursed),  # alias for landing page compatibility
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
        # P1-8 audit: disambiguate populations on the Overview card —
        # PAR denominator is active_outstanding, total_outstanding is
        # all-statuses. Both are displayed; these fields let the frontend
        # label them correctly without a subtitle hack.
        'par_population': 'active_outstanding',
        'par_confidence': 'A',
        'total_outstanding_population': 'total_originated',
        'collection_rate_population': 'total_originated',
        'hhi_shop_population': 'total_originated',
    }


# ── 2. Delinquency ───────────────────────────────────────────────────────────

def compute_silq_delinquency(df, mult=1, ref_date=None):
    df = _ensure_str_shop_id(df)
    dpd = _dpd(df, ref_date)
    active = df[df[C_STATUS] != 'Closed'] if C_STATUS in df.columns else df
    active_dpd = _dpd(active, ref_date)

    # DPD buckets
    buckets = [
        {'label': 'Current',   'min': 0,  'max': 0},
        {'label': '1-30 DPD',  'min': 1,  'max': 30},
        {'label': '31-60 DPD', 'min': 31, 'max': 60},
        {'label': '61-90 DPD', 'min': 61, 'max': 90},
        {'label': '90+ DPD',   'min': 91, 'max': 99999},
    ]
    total_active_out = active[C_OUTSTANDING].sum() if C_OUTSTANDING in active.columns else 0
    bucket_data = []
    for b in buckets:
        mask = (active_dpd >= b['min']) & (active_dpd <= b['max'])
        count = int(mask.sum())
        amount = float(active.loc[mask, C_OUTSTANDING].sum() * mult) if C_OUTSTANDING in active.columns else 0
        bucket_data.append({
            'label': b['label'],
            'count': count,
            'amount': _safe(amount),
            'pct': _safe(amount / max(total_active_out * mult, 1) * 100) if total_active_out else 0,
        })

    # GBV-weighted PAR metrics
    par30 = float(active.loc[active_dpd > 30, C_OUTSTANDING].sum() / max(total_active_out, 1) * 100) if total_active_out else 0
    par60 = float(active.loc[active_dpd > 60, C_OUTSTANDING].sum() / max(total_active_out, 1) * 100) if total_active_out else 0
    par90 = float(active.loc[active_dpd > 90, C_OUTSTANDING].sum() / max(total_active_out, 1) * 100) if total_active_out else 0

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
            act_out = act[C_OUTSTANDING].sum() if C_OUTSTANDING in act.columns else 0
            monthly.append({
                'Month': str(period),
                'total': int(len(grp)),
                'overdue_count': int((act['_dpd'] > 0).sum()),
                'overdue_rate': _safe(act.loc[act['_dpd'] > 0, C_OUTSTANDING].sum() / max(act_out, 1) * 100) if act_out else 0,
                'par30_rate': _safe(act.loc[act['_dpd'] > 30, C_OUTSTANDING].sum() / max(act_out, 1) * 100) if act_out else 0,
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
    """Collection metrics with P1-3 completed-only dual.

    Returns two parallel views per Framework §17:
      - repayment_rate            — total_originated (all statuses). Confidence A.
      - repayment_rate_realised   — completed_only (Status='Closed'). Confidence A.
    Same dual for by_product. This mirrors compute_silq_yield's
    (margin_rate, realised_margin_rate) pattern — P1-3 audit finding.
    Backwards compat: all existing fields preserved verbatim.
    """
    total_repaid = df[C_REPAID].sum() * mult if C_REPAID in df.columns else 0
    total_collectable = df[C_COLLECTABLE].sum() * mult if C_COLLECTABLE in df.columns else 0
    total_margin = df[C_MARGIN].sum() * mult if C_MARGIN in df.columns else 0
    total_principal = df[C_PRINCIPAL].sum() * mult if C_PRINCIPAL in df.columns else 0

    repayment_rate = (total_repaid / total_collectable * 100) if total_collectable else 0

    # P1-3 dual — completed_only (Closed) view
    if C_STATUS in df.columns:
        closed = df[df[C_STATUS] == 'Closed']
        closed_repaid      = closed[C_REPAID].sum() * mult      if C_REPAID      in closed.columns else 0
        closed_collectable = closed[C_COLLECTABLE].sum() * mult if C_COLLECTABLE in closed.columns else 0
        closed_count       = int(len(closed))
    else:
        closed_repaid = closed_collectable = 0
        closed_count = 0
    repayment_rate_realised = (closed_repaid / closed_collectable * 100) if closed_collectable else 0

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

    # By product type — dual rates
    by_product = []
    if C_PRODUCT in df.columns:
        for prod, grp in df.groupby(C_PRODUCT):
            p_repaid = grp[C_REPAID].sum() * mult if C_REPAID in grp.columns else 0
            p_collectable = grp[C_COLLECTABLE].sum() * mult if C_COLLECTABLE in grp.columns else 0
            # Completed-only sub-aggregate
            if C_STATUS in grp.columns:
                p_closed = grp[grp[C_STATUS] == 'Closed']
                p_closed_repaid      = p_closed[C_REPAID].sum() * mult      if C_REPAID      in p_closed.columns else 0
                p_closed_collectable = p_closed[C_COLLECTABLE].sum() * mult if C_COLLECTABLE in p_closed.columns else 0
                p_closed_count       = int(len(p_closed))
            else:
                p_closed_repaid = p_closed_collectable = 0
                p_closed_count = 0
            by_product.append({
                'product': str(prod),
                'repaid': _safe(p_repaid),
                'collectable': _safe(p_collectable),
                'rate': _safe(p_repaid / p_collectable * 100 if p_collectable else 0),
                'deals': int(len(grp)),
                # P1-3 additions
                'rate_realised': _safe(p_closed_repaid / p_closed_collectable * 100 if p_closed_collectable else 0),
                'realised_count': p_closed_count,
            })

    return {
        'total_repaid': _safe(total_repaid),
        'total_collectable': _safe(total_collectable),
        'total_margin': _safe(total_margin),
        'total_principal': _safe(total_principal),
        'repayment_rate': _safe(repayment_rate),
        # P1-3 additions (dual view)
        'repayment_rate_realised':    _safe(repayment_rate_realised),
        'closed_repaid':              _safe(closed_repaid),
        'closed_collectable':         _safe(closed_collectable),
        'closed_count':               closed_count,
        'repayment_rate_population':          'total_originated',
        'repayment_rate_realised_population': 'completed_only',
        'repayment_rate_confidence':          'A',
        'repayment_rate_realised_confidence': 'A',
        'monthly': monthly,
        'by_product': by_product,
    }


# ── 4. Concentration ─────────────────────────────────────────────────────────

def compute_silq_concentration(df, mult=1):
    df = _ensure_str_shop_id(df)
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

def compute_silq_cohorts(df, mult=1, ref_date=None):
    cohorts = []
    if C_DISB_DATE not in df.columns:
        return {'cohorts': cohorts}

    df2 = df.copy()
    df2['_month'] = df2[C_DISB_DATE].dt.to_period('M')
    df2['_dpd'] = _dpd(df2, ref_date)

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
            'par30_pct': _safe(active.loc[dpd_active > 30, C_OUTSTANDING].sum() / max(active[C_OUTSTANDING].sum(), 1) * 100 if C_OUTSTANDING in active.columns and active[C_OUTSTANDING].sum() > 0 else 0),
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
        if C_STATUS in df2.columns and C_OUTSTANDING in df2.columns:
            total_active_df = df2[df2[C_STATUS] != 'Closed']
            total_active_out = total_active_df[C_OUTSTANDING].sum()
            totals['par30_pct'] = _safe(total_active_df.loc[total_active_df['_dpd'] > 30, C_OUTSTANDING].sum() / max(total_active_out, 1) * 100 if total_active_out else 0)
        else:
            totals['par30_pct'] = 0
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

    # Detect products where margin data is synthetic (sheet lacked Margin Collected)
    margin_not_available = []
    if '_margin_synthetic' in df.columns and C_PRODUCT in df.columns:
        for prod, grp in df.groupby(C_PRODUCT):
            if grp['_margin_synthetic'].all():
                margin_not_available.append(str(prod))

    return {
        'total_margin': _safe(total_margin),
        'total_disbursed': _safe(total_disbursed),
        'margin_rate': _safe(margin_rate),
        'realised_margin_rate': _safe(realised_margin_rate),
        'by_product': by_product,
        'by_tenure': by_tenure,
        'monthly': monthly,
        'margin_not_available': margin_not_available,
    }


# ── 7. Tenure Analysis ───────────────────────────────────────────────────────

def compute_silq_tenure(df, mult=1, ref_date=None):
    # Tenure distribution
    distribution = []
    if C_TENURE in df.columns:
        bins = [0, 5, 10, 15, 20, 30, float('inf')]
        labels = ['1-4w', '5-9w', '10-14w', '15-19w', '20-29w', '30w+']
        df2 = df.copy()
        df2['_tband'] = pd.cut(df2[C_TENURE], bins=bins, labels=labels, right=False)
        df2['_dpd'] = _dpd(df2, ref_date)
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
                'dpd_rate': _safe(active.loc[dpd_active > 0, C_OUTSTANDING].sum() / max(active[C_OUTSTANDING].sum(), 1) * 100 if C_OUTSTANDING in active.columns and active[C_OUTSTANDING].sum() > 0 else 0),
                'par30_rate': _safe(active.loc[dpd_active > 30, C_OUTSTANDING].sum() / max(active[C_OUTSTANDING].sum(), 1) * 100 if C_OUTSTANDING in active.columns and active[C_OUTSTANDING].sum() > 0 else 0),
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

def compute_silq_borrowing_base(df, mult=1, ref_date=None):
    """Compute borrowing base eligibility waterfall."""
    dpd = _dpd(df, ref_date)
    active = df[df[C_STATUS] != 'Closed'].copy() if C_STATUS in df.columns else df.copy()
    active['_dpd'] = _dpd(active, ref_date)

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


# ── 9. Covenants ────────────────────────────────────────────────────────────

def compute_silq_covenants(df, mult=1, ref_date=None):
    """Compute covenant compliance tests from loan tape data.

    Implements covenants from the SILQ KSA facility compliance certificate:
    1. PAR30 ≤ 10% (GBV-weighted)
    2. PAR90 ≤ 5% (GBV-weighted)
    3. Collection Ratio > 33% (3-month rolling average)
    4. Repayment at Term > 95%
    5. LTV ≤ 75% (partial — facility/cash data off-tape)
    """
    if ref_date is None:
        ref_date = pd.Timestamp.now().normalize()
    else:
        ref_date = pd.to_datetime(ref_date)

    test_date_str = ref_date.strftime('%Y-%m-%d')
    covenants = []

    # ── Active loan base for PAR calculations ────────────────────────────
    active = df[df[C_STATUS] != 'Closed'] if C_STATUS in df.columns else df
    active_dpd = _dpd(active, ref_date)
    total_outstanding_active = active[C_OUTSTANDING].sum() * mult if C_OUTSTANDING in active.columns else 0

    # ── Covenant 1: PAR30 ≤ 10% ──────────────────────────────────────────
    # Confidence A — direct DPD from Repayment_Deadline column, outstanding-weighted
    # on the active pool. Population: active_outstanding (Framework §17).
    outstanding_gt30 = active.loc[active_dpd > 30, C_OUTSTANDING].sum() * mult if C_OUTSTANDING in active.columns else 0
    par30_ratio = outstanding_gt30 / total_outstanding_active if total_outstanding_active > 0 else 0
    covenants.append({
        'name': 'PAR 30 Ratio',
        'current': _safe(par30_ratio),
        'threshold': 0.10,
        'compliant': bool(par30_ratio <= 0.10),
        'operator': '<=',
        'format': 'pct',
        'period': test_date_str,
        'available': True,
        'partial': False,
        'method': 'direct',
        'confidence': 'A',
        'population': 'active_outstanding',
        'note': None,
        'breakdown': [
            {'label': 'Outstanding >30 DPD', 'value': _safe(outstanding_gt30)},
            {'label': 'Total Outstanding (active)', 'value': _safe(total_outstanding_active)},
            {'label': 'PAR 30 Ratio', 'value': _safe(par30_ratio), 'bold': True},
        ],
    })

    # ── Covenant 2: PAR90 ≤ 5% ───────────────────────────────────────────
    # Confidence A — same derivation as PAR30. Population: active_outstanding.
    outstanding_gt90 = active.loc[active_dpd > 90, C_OUTSTANDING].sum() * mult if C_OUTSTANDING in active.columns else 0
    par90_ratio = outstanding_gt90 / total_outstanding_active if total_outstanding_active > 0 else 0
    covenants.append({
        'name': 'PAR 90 Ratio',
        'current': _safe(par90_ratio),
        'threshold': 0.05,
        'compliant': bool(par90_ratio <= 0.05),
        'operator': '<=',
        'format': 'pct',
        'period': test_date_str,
        'available': True,
        'partial': False,
        'method': 'direct',
        'confidence': 'A',
        'population': 'active_outstanding',
        'note': None,
        'breakdown': [
            {'label': 'Outstanding >90 DPD', 'value': _safe(outstanding_gt90)},
            {'label': 'Total Outstanding (active)', 'value': _safe(total_outstanding_active)},
            {'label': 'PAR 90 Ratio', 'value': _safe(par90_ratio), 'bold': True},
        ],
    })

    # ── Covenant 3: Collection Ratio > 33% (3-month rolling avg) ─────────
    # Population: specific_filter(maturing in period) — includes ALL loans
    # (active + closed) whose Repayment_Deadline fell in the period window.
    # This is intentional per the SILQ KSA facility cert methodology (Dec 2025
    # cert 95.53% reconciles against this filter). A closed-repaid-in-full loan
    # that matured in-period MUST contribute to the denominator; filtering to
    # active-only would bias the covenant toward delinquent-dominated months.
    # Audit P0-1: this contrasts with Klaim's Collection Ratio, which uses a
    # cumulative approximation (method='cumulative', Confidence C per P0-5) —
    # different covenant definition, not a cross-company inconsistency.
    monthly_ratios = []
    month_labels = []
    if C_REPAY_DEADLINE in df.columns and C_REPAID in df.columns and C_COLLECTABLE in df.columns:
        for i in range(1, 4):  # 1, 2, 3 months back
            month_start = (ref_date - pd.DateOffset(months=i)).replace(day=1)
            month_end = (ref_date - pd.DateOffset(months=i-1)).replace(day=1) - pd.Timedelta(days=1)
            mask = (df[C_REPAY_DEADLINE] >= month_start) & (df[C_REPAY_DEADLINE] <= month_end)
            maturing = df[mask]
            if len(maturing) > 0:
                repaid = maturing[C_REPAID].sum()
                collectable = maturing[C_COLLECTABLE].sum()
                ratio = repaid / collectable if collectable > 0 else 0
                monthly_ratios.append(ratio)
                month_labels.append(month_start.strftime('%b %Y'))
            else:
                monthly_ratios.append(None)
                month_labels.append(month_start.strftime('%b %Y'))

    valid_ratios = [r for r in monthly_ratios if r is not None]
    avg_collection = sum(valid_ratios) / len(valid_ratios) if valid_ratios else 0

    breakdown_coll = []
    for label, ratio in zip(month_labels, monthly_ratios):
        if ratio is not None:
            breakdown_coll.append({'label': f'{label} Collection Ratio', 'value': _safe(ratio)})
        else:
            breakdown_coll.append({'label': f'{label} (no maturing loans)', 'value': 0})
    breakdown_coll.append({'label': '3-Month Average', 'value': _safe(avg_collection), 'bold': True})

    covenants.append({
        'name': 'Collection Ratio (3M Avg)',
        'current': _safe(avg_collection),
        'threshold': 0.33,
        'compliant': bool(avg_collection > 0.33),
        'operator': '>=',
        'format': 'pct',
        'period': f'{month_labels[-1] if month_labels else "N/A"} — {month_labels[0] if month_labels else "N/A"}',
        'available': len(valid_ratios) > 0,
        'partial': False,
        'method': 'direct',
        'confidence': 'A',
        'population': 'specific_filter(maturing in period)',
        'note': f'{len(valid_ratios)} of 3 months have maturing loans' if len(valid_ratios) < 3 else None,
        'breakdown': breakdown_coll,
    })

    # ── Covenant 4: Repayment at Term > 95% ──────────────────────────────
    # Loans whose original term + 3 months ended in the 3 months before ref_date
    # i.e., Repayment_Deadline between ref_date-6mo and ref_date-3mo.
    # Population: specific_filter(matured in 3-6mo window) — same doctrine as
    # Coll Ratio: includes all statuses. A loan that matured 4 months ago AND
    # closed repaid is a textbook "Repayment at Term" success and must count.
    rat_available = False
    rat_ratio = 0
    rat_breakdown = []
    if C_REPAY_DEADLINE in df.columns and C_REPAID in df.columns and C_COLLECTABLE in df.columns:
        window_start = ref_date - pd.DateOffset(months=6)
        window_end = ref_date - pd.DateOffset(months=3)
        mask = (df[C_REPAY_DEADLINE] >= window_start) & (df[C_REPAY_DEADLINE] < window_end)
        qualifying = df[mask]
        if len(qualifying) > 0:
            rat_available = True
            total_repaid = qualifying[C_REPAID].sum() * mult
            total_gbv = qualifying[C_COLLECTABLE].sum() * mult
            rat_ratio = total_repaid / total_gbv if total_gbv > 0 else 0
            rat_breakdown = [
                {'label': f'Qualifying loans ({len(qualifying)})', 'value': _safe(len(qualifying))},
                {'label': 'Total Collections', 'value': _safe(total_repaid)},
                {'label': 'Total GBV (matured)', 'value': _safe(total_gbv)},
                {'label': 'Repayment at Term', 'value': _safe(rat_ratio), 'bold': True},
            ]

    covenants.append({
        'name': 'Repayment at Term',
        'current': _safe(rat_ratio),
        'threshold': 0.95,
        'compliant': bool(rat_ratio >= 0.95) if rat_available else True,
        'operator': '>=',
        'format': 'pct',
        'period': f'{(ref_date - pd.DateOffset(months=6)).strftime("%b %Y")} — {(ref_date - pd.DateOffset(months=3)).strftime("%b %Y")}',
        'available': rat_available,
        'partial': False,
        'method': 'direct',
        'confidence': 'A',
        'population': 'specific_filter(matured in 3-6mo window)',
        'note': 'No qualifying loans in the measurement window' if not rat_available else None,
        'breakdown': rat_breakdown if rat_breakdown else [{'label': 'No qualifying loans', 'value': 0}],
    })

    # ── Covenant 5: LTV ≤ 75% (partial) ──────────────────────────────────
    total_receivables = df[C_OUTSTANDING].sum() * mult if C_OUTSTANDING in df.columns else 0
    covenants.append({
        'name': 'Loan-to-Value Ratio',
        'current': 0,
        'threshold': 0.75,
        'compliant': True,  # Can't determine without facility data
        'operator': '<=',
        'format': 'pct',
        'period': test_date_str,
        'available': False,
        'partial': True,
        'method': 'manual',
        'confidence': 'B',  # manual input once supplied — observed off-tape
        'population': 'manual(facility + cash balances)',
        'note': 'Requires facility amount and cash balances (corporate-level data not in loan tape)',
        'breakdown': [
            {'label': 'Portfolio Receivables (from tape)', 'value': _safe(total_receivables)},
            {'label': 'Facility Amount', 'value': 0, 'note': 'Off-tape'},
            {'label': 'Cash Balances', 'value': 0, 'note': 'Off-tape'},
            {'label': 'LTV Ratio', 'value': 0, 'bold': True, 'note': 'Incomplete'},
        ],
    })

    # ── Summary ───────────────────────────────────────────────────────────
    computable = [c for c in covenants if c['available'] and not c['partial']]
    compliant_count = sum(1 for c in computable if c['compliant'])
    breach_count = sum(1 for c in computable if not c['compliant'])
    partial_count = sum(1 for c in covenants if c['partial'] or not c['available'])

    return {
        'covenants': covenants,
        'compliant_count': compliant_count,
        'breach_count': breach_count,
        'partial_count': partial_count,
        'test_date': test_date_str,
    }


# ── 10. Seasonality ──────────────────────────────────────────────────────────

def compute_silq_seasonality(df, mult=1):
    """YoY seasonal patterns in disbursement and delinquency by calendar month.

    POS lending is inherently seasonal (Ramadan, salary cycles, school season in KSA).
    Returns monthly data by year + seasonal index for deployment volume.
    """
    if C_DISB_DATE not in df.columns:
        return {'available': False}

    df = df.copy()
    df['_disb_dt'] = pd.to_datetime(df[C_DISB_DATE], errors='coerce')
    df = df.dropna(subset=['_disb_dt'])

    if len(df) == 0:
        return {'available': False}

    df['_year'] = df['_disb_dt'].dt.year
    df['_month'] = df['_disb_dt'].dt.month

    years = sorted(df['_year'].unique())

    # Monthly deployment by year
    months = []
    for m in range(1, 13):
        month_data = {'month': m, 'month_name': pd.Timestamp(2020, m, 1).strftime('%b')}
        for y in years:
            mask = (df['_year'] == y) & (df['_month'] == m)
            sub = df[mask]
            month_data[f'volume_{y}'] = _safe(sub[C_DISBURSED].sum() * mult) if C_DISBURSED in sub.columns else 0
            month_data[f'count_{y}'] = int(len(sub))
            # Overdue rate for this cohort
            if C_OVERDUE in sub.columns and C_OUTSTANDING in sub.columns:
                out = sub[C_OUTSTANDING].sum()
                ovd = sub[C_OVERDUE].sum()
                month_data[f'overdue_rate_{y}'] = _safe(ovd / out * 100) if out > 0 else 0
            else:
                month_data[f'overdue_rate_{y}'] = 0
        months.append(month_data)

    # Seasonal index: month avg volume / overall monthly avg
    all_month_vols = []
    for m in range(1, 13):
        vol_sum = sum(months[m-1].get(f'volume_{y}', 0) for y in years)
        n_years = sum(1 for y in years if months[m-1].get(f'count_{y}', 0) > 0)
        avg = vol_sum / max(n_years, 1)
        all_month_vols.append(avg)

    overall_avg = sum(all_month_vols) / max(len([v for v in all_month_vols if v > 0]), 1)
    seasonal_index = []
    for m in range(1, 13):
        idx = all_month_vols[m-1] / overall_avg if overall_avg > 0 else 1.0
        seasonal_index.append({
            'month': m,
            'month_name': pd.Timestamp(2020, m, 1).strftime('%b'),
            'index': _safe(round(idx, 3)),
        })

    return {
        'available': True,
        'months': months,
        'seasonal_index': seasonal_index,
        'years': [int(y) for y in years],
    }


# ── 11. Cohort Loss Waterfall ────────────────────────────────────────────────

def compute_silq_cohort_loss_waterfall(df, mult=1, ref_date=None):
    """Per-vintage loss waterfall: Disbursed -> Overdue -> Write-off progression.

    For SILQ, "default" is defined as DPD > 90 on the active pool (code uses
    this definition). The earlier docstring also mentioned "Status indicates
    write-off" but the code never referenced Status — the DPD > 90 mask
    catches both active-delinquent and closed-unpaid via the _dpd() helper
    which forces DPD=0 on Closed loans. P2-2 audit cleanup: docstring now
    matches implementation.

    For a more complete loss definition (Closed-with-outstanding AND
    DPD > 90), use `separate_silq_portfolio()` and pass the `loss_df`
    directly to downstream analysis — Framework §17 separation primitive.
    Returns per-vintage and portfolio totals.
    """
    if C_DISB_DATE not in df.columns:
        return {'available': False}

    df = df.copy()
    df['_disb_dt'] = pd.to_datetime(df[C_DISB_DATE], errors='coerce')
    df = df.dropna(subset=['_disb_dt'])
    df['_month'] = df['_disb_dt'].dt.to_period('M').astype(str)

    if len(df) == 0:
        return {'available': False}

    dpd = _dpd(df, ref_date)

    vintages = []
    for month, grp in df.groupby('_month'):
        originated = grp[C_DISBURSED].sum() * mult if C_DISBURSED in grp.columns else 0
        outstanding = grp[C_OUTSTANDING].sum() * mult if C_OUTSTANDING in grp.columns else 0
        overdue = grp[C_OVERDUE].sum() * mult if C_OVERDUE in grp.columns else 0

        # Default: DPD > 90 for this vintage
        grp_dpd = dpd.loc[grp.index]
        default_mask = grp_dpd > 90
        gross_default = grp.loc[default_mask, C_OUTSTANDING].sum() * mult if C_OUTSTANDING in grp.columns else 0

        # Recovery: amount repaid on defaulted loans
        recovery = grp.loc[default_mask, C_REPAID].sum() * mult if C_REPAID in grp.columns else 0
        net_loss = max(gross_default - recovery, 0)

        default_rate = gross_default / originated * 100 if originated > 0 else 0
        recovery_rate = recovery / gross_default * 100 if gross_default > 0 else 0
        net_loss_rate = net_loss / originated * 100 if originated > 0 else 0

        vintages.append({
            'vintage': month,
            'deals': len(grp),
            'originated': _safe(originated),
            'outstanding': _safe(outstanding),
            'overdue': _safe(overdue),
            'gross_default': _safe(gross_default),
            'recovery': _safe(recovery),
            'net_loss': _safe(net_loss),
            'default_rate': _safe(round(default_rate, 2)),
            'recovery_rate': _safe(round(recovery_rate, 2)),
            'net_loss_rate': _safe(round(net_loss_rate, 2)),
        })

    # Portfolio totals
    total_originated = sum(v['originated'] for v in vintages)
    total_default = sum(v['gross_default'] for v in vintages)
    total_recovery = sum(v['recovery'] for v in vintages)
    total_net_loss = sum(v['net_loss'] for v in vintages)

    return {
        'available': True,
        'vintages': vintages,
        'totals': {
            'originated': _safe(total_originated),
            'gross_default': _safe(total_default),
            'recovery': _safe(total_recovery),
            'net_loss': _safe(total_net_loss),
            'default_rate': _safe(round(total_default / total_originated * 100, 2)) if total_originated > 0 else 0,
            'recovery_rate': _safe(round(total_recovery / total_default * 100, 2)) if total_default > 0 else 0,
            'net_loss_rate': _safe(round(total_net_loss / total_originated * 100, 2)) if total_originated > 0 else 0,
        },
    }


# ── 12. Underwriting Drift ───────────────────────────────────────────────────

def compute_silq_underwriting_drift(df, mult=1, ref_date=None):
    """Track origination quality metrics by vintage and flag drift from historical norms.

    Per-vintage: avg loan size, avg tenure, product mix, delinquency rate.
    Flags months where metrics deviate >1 stdev from rolling historical mean.
    """
    if C_DISB_DATE not in df.columns:
        return {'available': False}

    df = df.copy()
    df['_disb_dt'] = pd.to_datetime(df[C_DISB_DATE], errors='coerce')
    df = df.dropna(subset=['_disb_dt'])
    df['_month'] = df['_disb_dt'].dt.to_period('M').astype(str)

    if len(df) == 0:
        return {'available': False}

    dpd = _dpd(df, ref_date)

    vintages = []
    for month, grp in df.groupby('_month'):
        avg_loan_size = grp[C_DISBURSED].mean() * mult if C_DISBURSED in grp.columns else 0
        avg_tenure = grp[C_TENURE].mean() if C_TENURE in grp.columns else 0

        grp_dpd = dpd.loc[grp.index]
        delinquency_rate = (grp_dpd > 0).sum() / len(grp) * 100 if len(grp) > 0 else 0

        # Product mix — share of each product type
        product_mix = {}
        if C_PRODUCT in grp.columns:
            mix = grp[C_PRODUCT].value_counts(normalize=True)
            for p, s in mix.items():
                product_mix[p] = _safe(round(s * 100, 1))

        # Collection rate for this vintage
        collectable = grp[C_COLLECTABLE].sum() if C_COLLECTABLE in grp.columns else 0
        repaid = grp[C_REPAID].sum() if C_REPAID in grp.columns else 0
        collection_rate = repaid / collectable * 100 if collectable > 0 else 0

        vintages.append({
            'vintage': month,
            'deals': len(grp),
            'avg_loan_size': _safe(round(avg_loan_size, 2)),
            'avg_tenure': _safe(round(avg_tenure, 1)),
            'delinquency_rate': _safe(round(delinquency_rate, 2)),
            'collection_rate': _safe(round(collection_rate, 2)),
            'product_mix': product_mix,
            'flags': [],
        })

    # Compute drift flags — compare each vintage against rolling mean of prior 6 vintages
    metrics = ['avg_loan_size', 'avg_tenure', 'delinquency_rate', 'collection_rate']
    for i, v in enumerate(vintages):
        if i < 3:  # Need at least 3 prior vintages for meaningful norms
            continue
        prior = vintages[max(0, i-6):i]
        for metric in metrics:
            prior_vals = [p[metric] for p in prior if p[metric] is not None and p[metric] != 0]
            if len(prior_vals) < 3:
                continue
            mean = sum(prior_vals) / len(prior_vals)
            std = (sum((x - mean)**2 for x in prior_vals) / len(prior_vals)) ** 0.5
            if std == 0:
                continue
            z_score = (v[metric] - mean) / std
            if abs(z_score) > 1.0:
                direction = 'up' if z_score > 0 else 'down'
                v['flags'].append({
                    'metric': metric,
                    'direction': direction,
                    'z_score': _safe(round(z_score, 2)),
                    'current': v[metric],
                    'historical_mean': _safe(round(mean, 2)),
                })

    # Historical norms (overall averages)
    historical_norms = {}
    for metric in metrics:
        vals = [v[metric] for v in vintages if v[metric] is not None and v[metric] != 0]
        if vals:
            historical_norms[metric] = _safe(round(sum(vals) / len(vals), 2))

    return {
        'available': True,
        'vintages': vintages,
        'historical_norms': historical_norms,
    }


# ── 13. CDR / CCR ─────────────────────────────────────────────────────────────

def separate_silq_portfolio(df, ref_date=None):
    """Split a SILQ DataFrame into (clean_df, loss_df) per Framework §17.

    Loss definition for SILQ: Status=='Closed' with Outstanding > 0 (written
    off / defaulted — closed but balance not recovered) OR an active loan
    with DPD > 90. Clean portfolio excludes those deals.

    Mirrors the Klaim `separate_portfolio()` primitive (core/analysis.py).
    Use for learning-metric computation — DOES NOT replace the covenant-
    facing active_outstanding population for Borrowing Base / PAR covenants.

    Returns (clean_df, loss_df), both copies of the input.
    """
    if C_STATUS not in df.columns or C_OUTSTANDING not in df.columns:
        # Column availability fallback — nothing to split on.
        return df.copy(), df.iloc[0:0].copy()
    closed_with_balance = (df[C_STATUS] == 'Closed') & (df[C_OUTSTANDING].fillna(0) > 0)
    dpd = _dpd(df, ref_date)
    deep_dpd_active = (df[C_STATUS] != 'Closed') & (dpd > 90)
    loss_mask = closed_with_balance | deep_dpd_active
    return df[~loss_mask].copy(), df[loss_mask].copy()


def classify_silq_deal_stale(df, ref_date=None, ineligibility_days=180):
    """Flag SILQ deals that don't represent live portfolio behaviour.

    Three rules (a deal may satisfy more than one):
      - loss_closed_outstanding: Status == 'Closed' AND Outstanding > 0.
                                 Charge-off: closed on the tape but balance
                                 was never recovered.
      - stuck_active:            Status == 'Active' AND Outstanding < 10% of
                                 Disbursed_Amount AND DPD > 0.
                                 Economically complete (balance near zero)
                                 but the row is still marked Active —
                                 drifts time-based metrics upward every day.
      - deep_dpd_active:         Status == 'Active' AND DPD > 90.
                                 Deep delinquency — expected to resolve as
                                 charge-off or legal recovery.

    `ineligibility_days` default 180 matches typical SILQ loan tenor; kept
    as a parameter for future tuning. Currently only stored on result dict
    (no rule uses it yet — matches `classify_klaim_deal_stale` API shape).

    Framework §17 pattern mirroring Klaim/Aajil equivalents.

    Returns dict of Series (all indexed identically to df):
      - loss_closed_outstanding, stuck_active, deep_dpd_active: per-rule masks
      - any_stale:                                              OR-reduction
      - ineligibility_days:                                     int threshold
    """
    idx = df.index

    def _col(name, default=0.0):
        if name in df.columns:
            return pd.to_numeric(df[name], errors='coerce').fillna(default)
        return pd.Series(default, index=idx, dtype=float)

    outstanding = _col(C_OUTSTANDING)
    disbursed   = _col(C_DISBURSED, default=1.0)
    status      = df[C_STATUS] if C_STATUS in df.columns else pd.Series('', index=idx)
    dpd         = _dpd(df, ref_date)

    has_disbursed = disbursed > 0

    loss_closed_outstanding = (status == 'Closed') & (outstanding > 0)
    stuck_active            = (status == 'Active') & (outstanding < 0.1 * disbursed) & (dpd > 0) & has_disbursed
    deep_dpd_active         = (status == 'Active') & (dpd > 90)
    any_stale               = loss_closed_outstanding | stuck_active | deep_dpd_active

    return {
        'loss_closed_outstanding': loss_closed_outstanding,
        'stuck_active':            stuck_active,
        'deep_dpd_active':         deep_dpd_active,
        'any_stale':               any_stale,
        'ineligibility_days':      int(ineligibility_days),
    }


def compute_silq_operational_wal(df, mult=1, ref_date=None):
    """PV-weighted age across the clean (non-stale) SILQ book.

    Framework §17 Tape-side learning metric. Excludes the zombie tail
    surfaced by classify_silq_deal_stale. Confidence B — the stale filter
    introduces judgement (three classification thresholds).

    Per-deal age:
      - Active:          elapsed = ref_date - Disbursement_Date (days)
      - Closed (clean):  close_age = min(Repayment_Deadline - Disbursement_Date, elapsed)
                         Clipped to elapsed because close_age can exceed
                         elapsed on loans extended beyond their original
                         term — we count only time already experienced.

    Returns:
      {
        'available': bool,
        'operational_wal_days': float,    # clean-book PV-weighted, Confidence B
        'realized_wal_days':    float|None, # closed-clean only, Confidence B
        'method': str,                     # 'direct' (Repayment_Deadline
                                           #   present) or 'elapsed_only'
                                           #   (degraded — no maturity info)
        'confidence': 'B' | 'C',
        'population': 'clean_book',
        'clean_pv':         float,
        'clean_deal_count': int,
        'total_pv':         float,
        'total_deal_count': int,
        'stale_pv':         float,
        'stale_deal_count': int,
      }
    """
    if (C_DISB_DATE not in df.columns
            or C_DISBURSED not in df.columns
            or C_STATUS not in df.columns):
        return {'available': False}
    if len(df) == 0:
        return {'available': False}

    pv = pd.to_numeric(df[C_DISBURSED], errors='coerce').fillna(0) * mult
    total_pv = float(pv.sum())
    if total_pv <= 0:
        return {'available': False}

    ref = pd.Timestamp.now().normalize() if ref_date is None else pd.to_datetime(ref_date)
    df_work = df.copy()
    df_work[C_DISB_DATE] = pd.to_datetime(df_work[C_DISB_DATE], errors='coerce')

    elapsed = (ref - df_work[C_DISB_DATE]).dt.days.clip(lower=0).fillna(0).astype(float)
    age = elapsed.copy()

    has_deadline = C_REPAY_DEADLINE in df_work.columns
    method = 'direct' if has_deadline else 'elapsed_only'

    if has_deadline:
        deadline = pd.to_datetime(df_work[C_REPAY_DEADLINE], errors='coerce')
        close_age_days = (deadline - df_work[C_DISB_DATE]).dt.days
        closed_mask = df_work[C_STATUS] == 'Closed'
        # Only override for closed loans with valid deadline
        valid_closed = closed_mask & deadline.notna()
        age = age.where(~valid_closed, close_age_days.clip(lower=0))

    # Clip to [0, elapsed] — age can never exceed physical elapsed time
    age = np.minimum(np.maximum(age, 0), elapsed)

    stale = classify_silq_deal_stale(df_work, ref_date=ref_date)
    clean_mask = ~stale['any_stale']

    clean_pv  = pv[clean_mask]
    clean_age = age[clean_mask]
    if clean_pv.sum() <= 0:
        return {'available': False}

    operational_wal = float(np.average(clean_age, weights=clean_pv))

    # Realized WAL — closed + clean only
    realized_wal = None
    closed_clean = (df_work[C_STATUS] == 'Closed') & clean_mask
    if closed_clean.any() and has_deadline:
        rpv  = pv[closed_clean]
        rage = age[closed_clean]
        if rpv.sum() > 0:
            realized_wal = round(float(np.average(rage, weights=rpv)), 2)

    confidence = 'B' if has_deadline else 'C'

    return {
        'available':            True,
        'operational_wal_days': round(operational_wal, 2),
        'realized_wal_days':    realized_wal,
        'method':               method,
        'confidence':           confidence,
        'population':           'clean_book',
        'clean_pv':             round(float(clean_pv.sum()), 2),
        'clean_deal_count':     int(clean_mask.sum()),
        'total_pv':             round(total_pv, 2),
        'total_deal_count':     int(len(df_work)),
        'stale_pv':             round(float(pv[stale['any_stale']].sum()), 2),
        'stale_deal_count':     int(stale['any_stale'].sum()),
        'ineligibility_days':   stale['ineligibility_days'],
    }


def compute_silq_cdr_ccr(df, mult=1, ref_date=None):
    """Conditional Default Rate (CDR) and Conditional Collection Rate (CCR) by vintage.

    Annualizes cumulative default/collection rates by vintage age so that cohorts
    of different maturities are directly comparable on a monthly basis.

        CDR = (Outstanding on DPD>90 / Disbursed) / months_outstanding * 12
        CCR = (Amt_Repaid / Disbursed) / months_outstanding * 12
    """
    if C_DISB_DATE not in df.columns or C_DISBURSED not in df.columns:
        return {'available': False}

    today = pd.to_datetime(ref_date) if ref_date else pd.Timestamp.now().normalize()
    df = df.copy()
    df['_disb_dt'] = pd.to_datetime(df[C_DISB_DATE], errors='coerce')
    df = df.dropna(subset=['_disb_dt'])
    df['_vintage'] = df['_disb_dt'].dt.to_period('M')

    if len(df) == 0:
        return {'available': False}

    dpd = _dpd(df, ref_date)

    vintages = []
    for vintage, grp in df.groupby('_vintage'):
        originated = float(grp[C_DISBURSED].sum() * mult)
        if originated <= 0:
            continue

        months_outstanding = max(((today - vintage.to_timestamp()).days / 30.44), 1.0)

        default_mask = dpd.loc[grp.index] > 90
        gross_default = float(grp.loc[default_mask, C_OUTSTANDING].sum() * mult) if C_OUTSTANDING in grp.columns else 0.0
        collected = float(grp[C_REPAID].sum() * mult) if C_REPAID in grp.columns else 0.0

        cdr = (gross_default / originated) / months_outstanding * 12 * 100
        ccr = (collected / originated) / months_outstanding * 12 * 100

        vintages.append({
            'vintage': str(vintage),
            'deal_count': int(len(grp)),
            'originated': _safe(round(originated, 2)),
            'collected': _safe(round(collected, 2)),
            'defaulted': _safe(round(gross_default, 2)),
            'months_outstanding': round(months_outstanding, 1),
            'cdr': _safe(round(cdr, 4)),
            'ccr': _safe(round(ccr, 4)),
            'net_spread': _safe(round(ccr - cdr, 4)),
        })

    if not vintages:
        return {'available': False}

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
            'cdr': _safe(round(portfolio_cdr, 4)),
            'ccr': _safe(round(portfolio_ccr, 4)),
            'net_spread': _safe(round(portfolio_ccr - portfolio_cdr, 4)),
            'avg_vintage_age_months': round(avg_months, 1),
        },
    }
