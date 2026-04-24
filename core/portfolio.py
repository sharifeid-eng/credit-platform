"""
core/portfolio.py
Portfolio Analytics computation engine — supports both SILQ and Klaim.

SILQ: borrowing base, tiered concentration limits (loan docs), 5 covenants
Klaim: borrowing base (receivables), 5 concentration limits, 6 covenants
       (matching Creditit platform: BB waterfall, payer/customer/receivable
        limits, PAR30/60, collection ratio, paid vs due, WAL, cash balance)

All functions are pure (no I/O). They take a DataFrame + params, return dicts.
"""

import pandas as pd
import numpy as np

from core.analysis_silq import (
    _dpd, _safe, _ensure_str_shop_id, filter_silq_by_date,
    C_DISBURSED, C_OUTSTANDING, C_OVERDUE, C_COLLECTABLE,
    C_REPAID, C_MARGIN, C_PRINCIPAL, C_SHOP_LIMIT,
    C_DEAL_ID, C_SHOP_ID, C_TENURE, C_STATUS, C_PRODUCT,
    C_DISB_DATE, C_REPAY_DEADLINE, C_LAST_COLL, C_LOAN_AGE,
)
from core.analysis import filter_by_date, method_to_confidence


# ── Concentration limit tiers (from loan documents) ─────────────────────────
# Single financing recipient limit scales with facility size (in USD)
CONC_TIERS = [
    (10_000_000,  0.20),   # drawn ≤ $10M  → 20%
    (20_000_000,  0.15),   # $10M < drawn ≤ $20M → 15%
    (float('inf'), 0.10),  # drawn > $20M → 10%
]
APPROVED_RECIPIENT_LIMIT = 0.15  # 15% regardless of facility size


def _conc_threshold(facility_drawn_usd):
    """Return the single-borrower concentration threshold for a given facility size."""
    for cap, pct in CONC_TIERS:
        if facility_drawn_usd <= cap:
            return pct
    return CONC_TIERS[-1][1]


# ── 1. Borrowing Base ───────────────────────────────────────────────────────

def compute_borrowing_base(df, mult=1, ref_date=None, facility_params=None):
    """Compute enhanced borrowing base eligibility waterfall.

    facility_params (optional dict):
        facility_limit: Total facility limit (SAR)
        facility_drawn: Current drawn amount (SAR)
        cash_balance:   Cash on hand (SAR)
        advance_rate:   Override advance rate (default 0.80)
        advance_rates_by_product: dict of product → rate
        approved_recipients: list of Shop_ID strings
    """
    if facility_params is None:
        facility_params = {}

    df = _ensure_str_shop_id(df)
    active = df[df[C_STATUS] != 'Closed'].copy() if C_STATUS in df.columns else df.copy()
    active['_dpd'] = _dpd(active, ref_date)

    total_ar = active[C_OUTSTANDING].sum() * mult if C_OUTSTANDING in active.columns else 0

    # ── Ineligible: DPD > 60 ────────────────────────────────────────────
    inelig_dpd = 0
    if C_OUTSTANDING in active.columns:
        inelig_dpd = float(active.loc[active['_dpd'] > 60, C_OUTSTANDING].sum() * mult)

    # ── Ineligible: concentration excess (tiered per loan docs) ─────────
    facility_drawn = facility_params.get('facility_drawn', 0)
    # Convert to USD for tier lookup (SAR → USD at 0.2667)
    usd_rate = facility_params.get('usd_rate', 0.2667)
    facility_drawn_usd = facility_drawn * usd_rate
    threshold_pct = _conc_threshold(facility_drawn_usd)
    approved = set(str(s) for s in facility_params.get('approved_recipients', []))

    inelig_conc = 0
    breaching_shops = []
    if C_SHOP_ID in active.columns and C_OUTSTANDING in active.columns and total_ar > 0:
        shop_out = active.groupby(C_SHOP_ID)[C_OUTSTANDING].sum() * mult
        for shop_id, amount in shop_out.items():
            shop_limit = APPROVED_RECIPIENT_LIMIT if str(shop_id) in approved else threshold_pct
            max_allowed = total_ar * shop_limit
            if amount > max_allowed:
                excess = amount - max_allowed
                inelig_conc += excess
                breaching_shops.append({
                    'shop_id': _safe(shop_id),
                    'outstanding': _safe(amount),
                    'limit_pct': _safe(shop_limit),
                    'max_allowed': _safe(max_allowed),
                    'excess': _safe(excess),
                })

    total_ineligible = inelig_dpd + inelig_conc
    eligible = max(total_ar - total_ineligible, 0)

    # ── Advance rate ────────────────────────────────────────────────────
    default_advance = facility_params.get('advance_rate', 0.80)
    borrowing_base = eligible * default_advance

    # ── Waterfall ───────────────────────────────────────────────────────
    waterfall = [
        {'label': 'Total Outstanding A/R',     'value': _safe(total_ar),        'type': 'total'},
        {'label': 'Ineligible (DPD > 60)',     'value': _safe(-inelig_dpd),     'type': 'deduction'},
        {'label': 'Ineligible (Concentration)', 'value': _safe(-inelig_conc),    'type': 'deduction'},
    ]
    waterfall.extend([
        {'label': 'Eligible A/R',              'value': _safe(eligible),        'type': 'subtotal'},
        {'label': f'Advance Rate ({default_advance:.0%})',
         'value': _safe(-eligible * (1 - default_advance)),                     'type': 'deduction'},
        {'label': 'Borrowing Base',            'value': _safe(borrowing_base),  'type': 'result'},
    ])

    # ── Advance rates by product ────────────────────────────────────────
    custom_rates = facility_params.get('advance_rates_by_product', {})
    by_product = []
    if C_PRODUCT in active.columns and C_OUTSTANDING in active.columns:
        for prod, grp in active.groupby(C_PRODUCT):
            p_total = grp[C_OUTSTANDING].sum() * mult
            p_inelig_dpd = grp.loc[grp['_dpd'] > 60, C_OUTSTANDING].sum() * mult
            p_elig = max(p_total - p_inelig_dpd, 0)
            rate = custom_rates.get(str(prod), default_advance)
            by_product.append({
                'product': str(prod),
                'total': _safe(p_total),
                'ineligible': _safe(p_inelig_dpd),
                'eligible': _safe(p_elig),
                'elig_pct': _safe(p_elig / p_total * 100 if p_total else 0),
                'advance_rate': _safe(rate),
                'advanceable': _safe(p_elig * rate),
            })

    # ── Facility capacity ───────────────────────────────────────────────
    facility_limit = facility_params.get('facility_limit', 0)
    facility_outstanding = facility_params.get('facility_drawn', 0) * mult
    available = max(min(borrowing_base, facility_limit * mult) - facility_outstanding, 0) if facility_limit else borrowing_base
    headroom = (available / (facility_limit * mult) * 100) if facility_limit else 0

    facility = {
        'limit': _safe(facility_limit * mult) if facility_limit else 0,
        'outstanding': _safe(facility_outstanding),
        'available': _safe(available),
        'headroom_pct': _safe(headroom),
    }

    # ── KPIs ────────────────────────────────────────────────────────────
    kpis = {
        'total_ar': _safe(total_ar),
        'eligible_ar': _safe(eligible),
        'borrowing_base': _safe(borrowing_base),
        'available_to_draw': _safe(available),
        'ineligible': _safe(total_ineligible),
        'facility_limit': _safe(facility_limit * mult) if facility_limit else 0,
    }

    return {
        'waterfall': waterfall,
        'kpis': kpis,
        'advance_rates': by_product,
        'facility': facility,
        'breaching_shops': breaching_shops,
        'concentration_threshold': _safe(threshold_pct),
    }


# ── 2. Concentration Limits ─────────────────────────────────────────────────

def compute_concentration_limits(df, mult=1, ref_date=None, facility_params=None):
    """Evaluate concentration limits per loan document definition.

    Tiered single-borrower limit:
      drawn ≤ $10M  → 20% per borrower
      $10M < drawn ≤ $20M → 15%
      drawn > $20M → 10%
      Approved Recipients → 15% always

    Also computes: top-5 shop concentration, product mix, weighted avg tenure.
    """
    if facility_params is None:
        facility_params = {}

    df = _ensure_str_shop_id(df)
    active = df[df[C_STATUS] != 'Closed'].copy() if C_STATUS in df.columns else df.copy()

    facility_drawn = facility_params.get('facility_drawn', 0)
    usd_rate = facility_params.get('usd_rate', 0.2667)
    facility_drawn_usd = facility_drawn * usd_rate
    threshold_pct = _conc_threshold(facility_drawn_usd)
    approved = set(str(s) for s in facility_params.get('approved_recipients', []))

    total_outstanding = active[C_OUTSTANDING].sum() * mult if C_OUTSTANDING in active.columns else 0
    limits = []

    # ── Limit 1: Single Borrower Limit (tiered) ────────────────────────
    worst_shop_pct = 0
    worst_shop_id = None
    breaching = []
    if C_SHOP_ID in active.columns and C_OUTSTANDING in active.columns and total_outstanding > 0:
        shop_out = active.groupby(C_SHOP_ID)[C_OUTSTANDING].sum() * mult
        shop_pcts = shop_out / total_outstanding
        if len(shop_pcts) > 0:
            worst_idx = shop_pcts.idxmax()
            worst_shop_pct = float(shop_pcts.loc[worst_idx])
            worst_shop_id = str(worst_idx)
        # Check each shop
        for shop_id, pct in shop_pcts.items():
            shop_limit = APPROVED_RECIPIENT_LIMIT if str(shop_id) in approved else threshold_pct
            if pct > shop_limit:
                breaching.append({
                    'shop_id': _safe(shop_id),
                    'current': _safe(float(pct)),
                    'threshold': _safe(shop_limit),
                    'amount': _safe(float(shop_out.loc[shop_id])),
                })

    tier_label = f'{threshold_pct:.0%}'
    if facility_drawn_usd > 0:
        tier_label = f'{threshold_pct:.0%} (drawn ${facility_drawn_usd/1e6:.1f}M)'
    limits.append({
        'name': 'Single Borrower Limit',
        'current': _safe(worst_shop_pct),
        'threshold': _safe(threshold_pct),
        'compliant': bool(len(breaching) == 0),
        'unit': '%',
        'format': 'pct',
        'confidence': 'A',
        'population': 'active_outstanding',
        'tier_label': tier_label,
        'worst_shop': worst_shop_id,
        'breaching_shops': breaching,
        'breakdown': [
            {'label': f'Largest borrower ({worst_shop_id})', 'value': _safe(worst_shop_pct)},
            {'label': f'Threshold ({tier_label})', 'value': _safe(threshold_pct)},
            {'label': 'Breaching borrowers', 'value': len(breaching), 'bold': True},
        ],
    })

    # ── Limit 2: Top 5 Shop Concentration ───────────────────────────────
    top5_pct = 0
    top5_threshold = 0.50  # 50% default
    if C_SHOP_ID in active.columns and C_OUTSTANDING in active.columns and total_outstanding > 0:
        shop_out = active.groupby(C_SHOP_ID)[C_OUTSTANDING].sum() * mult
        top5 = shop_out.nlargest(5)
        top5_pct = float(top5.sum() / total_outstanding)

    limits.append({
        'name': 'Top 5 Borrower Concentration',
        'current': _safe(top5_pct),
        'threshold': _safe(top5_threshold),
        'compliant': bool(top5_pct <= top5_threshold),
        'unit': '%',
        'format': 'pct',
        'confidence': 'A',
        'population': 'active_outstanding',
        'breakdown': [
            {'label': 'Top 5 borrowers outstanding', 'value': _safe(top5.sum() if C_SHOP_ID in active.columns else 0)},
            {'label': 'Total outstanding', 'value': _safe(total_outstanding)},
            {'label': 'Top 5 share', 'value': _safe(top5_pct), 'bold': True},
        ],
    })

    # ── Limit 3: Product Mix ────────────────────────────────────────────
    product_threshold = 0.80  # no single product > 80%
    worst_product_pct = 0
    worst_product = None
    product_compliant = True
    if C_PRODUCT in active.columns and C_OUTSTANDING in active.columns and total_outstanding > 0:
        prod_out = active.groupby(C_PRODUCT)[C_OUTSTANDING].sum() * mult
        prod_pcts = prod_out / total_outstanding
        if len(prod_pcts) > 0:
            worst_product = str(prod_pcts.idxmax())
            worst_product_pct = float(prod_pcts.max())
            product_compliant = bool(worst_product_pct <= product_threshold)

    limits.append({
        'name': 'Single Product Concentration',
        'current': _safe(worst_product_pct),
        'threshold': _safe(product_threshold),
        'compliant': product_compliant,
        'unit': '%',
        'format': 'pct',
        'confidence': 'A',
        'population': 'active_outstanding',
        'breakdown': [
            {'label': f'Largest product ({worst_product})', 'value': _safe(worst_product_pct)},
            {'label': 'Threshold', 'value': _safe(product_threshold)},
        ],
    })

    # ── Limit 4: Weighted Average Tenure ────────────────────────────────
    tenure_threshold = 104  # weeks (2 years — accommodates RBF 90-week products)
    wav_tenure = 0
    if C_TENURE in active.columns and C_OUTSTANDING in active.columns and total_outstanding > 0:
        weights = active[C_OUTSTANDING] * mult
        wav_tenure = float(np.average(active[C_TENURE], weights=weights))

    limits.append({
        'name': 'Weighted Avg Tenure',
        'current': _safe(wav_tenure),
        'threshold': _safe(tenure_threshold),
        'compliant': bool(wav_tenure <= tenure_threshold),
        'unit': 'weeks',
        'format': 'weeks',
        'confidence': 'A',
        'population': 'active_outstanding',
        'breakdown': [
            {'label': 'Outstanding-weighted avg tenure', 'value': _safe(wav_tenure)},
            {'label': 'Threshold', 'value': _safe(tenure_threshold)},
        ],
    })

    # ── Summary ─────────────────────────────────────────────────────────
    compliant_count = sum(1 for l in limits if l['compliant'])
    breach_count = len(limits) - compliant_count

    return {
        'limits': limits,
        'compliant_count': compliant_count,
        'breach_count': breach_count,
        'concentration_tier': _safe(threshold_pct),
        'facility_drawn_usd': _safe(facility_drawn_usd),
    }


# ── 3. Covenants ────────────────────────────────────────────────────────────

def compute_covenants(df, mult=1, ref_date=None, facility_params=None):
    """Compute 5 covenant compliance tests matching cert methodology.

    Validated against SILQ KSA Dec 2025 compliance certificate:
    1. PAR30 ≤ 10% — cert 1.6% (Dec 31), tape ~5.5% (Jan 31, timing gap)
    2. PAR90 ≤ 5%
    3. Collection Ratio > 33% — cert 95.53% (3M avg)
    4. Repayment at Term > 95% — cert 97.33%
    5. LTV ≤ 75% — cert 74.85% (tightest, requires facility_params)
    """
    if facility_params is None:
        facility_params = {}

    if ref_date is None:
        ref_date = pd.Timestamp.now().normalize()
    else:
        ref_date = pd.to_datetime(ref_date)

    test_date_str = ref_date.strftime('%Y-%m-%d')
    covenants = []

    # ── Active loan base for PAR ────────────────────────────────────────
    active = df[df[C_STATUS] != 'Closed'] if C_STATUS in df.columns else df
    active_dpd = _dpd(active, ref_date)
    total_active_out = active[C_OUTSTANDING].sum() * mult if C_OUTSTANDING in active.columns else 0

    # ── Covenant 1: PAR30 ≤ 10% (GBV-weighted) ─────────────────────────
    out_gt30 = active.loc[active_dpd > 30, C_OUTSTANDING].sum() * mult if C_OUTSTANDING in active.columns else 0
    par30 = out_gt30 / total_active_out if total_active_out > 0 else 0

    covenants.append({
        'name': 'PAR 30 Ratio',
        'current': _safe(par30),
        'threshold': 0.10,
        'compliant': bool(par30 <= 0.10),
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
            {'label': 'Outstanding >30 DPD', 'value': _safe(out_gt30)},
            {'label': 'Total Outstanding (active)', 'value': _safe(total_active_out)},
            {'label': 'PAR 30 Ratio', 'value': _safe(par30), 'bold': True},
        ],
    })

    # ── Covenant 2: PAR90 ≤ 5% (GBV-weighted) ──────────────────────────
    out_gt90 = active.loc[active_dpd > 90, C_OUTSTANDING].sum() * mult if C_OUTSTANDING in active.columns else 0
    par90 = out_gt90 / total_active_out if total_active_out > 0 else 0

    covenants.append({
        'name': 'PAR 90 Ratio',
        'current': _safe(par90),
        'threshold': 0.05,
        'compliant': bool(par90 <= 0.05),
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
            {'label': 'Outstanding >90 DPD', 'value': _safe(out_gt90)},
            {'label': 'Total Outstanding (active)', 'value': _safe(total_active_out)},
            {'label': 'PAR 90 Ratio', 'value': _safe(par90), 'bold': True},
        ],
    })

    # ── Covenant 3: Collection Ratio > 33% (3M rolling avg) ─────────────
    # For each of the 3 months before ref_date, find loans maturing in that
    # month and compute repaid / collectable.
    monthly_ratios = []
    month_labels = []
    if C_REPAY_DEADLINE in df.columns and C_REPAID in df.columns and C_COLLECTABLE in df.columns:
        for i in range(1, 4):
            month_start = (ref_date - pd.DateOffset(months=i)).replace(day=1)
            month_end = (ref_date - pd.DateOffset(months=i - 1)).replace(day=1) - pd.Timedelta(days=1)
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

    period_str = f'{month_labels[-1] if month_labels else "N/A"} — {month_labels[0] if month_labels else "N/A"}'
    covenants.append({
        'name': 'Collection Ratio (3M Avg)',
        'current': _safe(avg_collection),
        'threshold': 0.33,
        'compliant': bool(avg_collection > 0.33),
        'operator': '>=',
        'format': 'pct',
        'period': period_str,
        'available': len(valid_ratios) > 0,
        'partial': False,
        'method': 'direct',
        'confidence': 'A',
        'population': 'specific_filter(maturing in period)',
        'note': f'{len(valid_ratios)} of 3 months have maturing loans' if len(valid_ratios) < 3 else None,
        'breakdown': breakdown_coll,
    })

    # ── Covenant 4: Repayment at Term > 95% ─────────────────────────────
    # Loans with Repayment_Deadline between ref_date-6mo and ref_date-3mo
    # (3 months seasoning window to allow full collection)
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

    rat_period = f'{(ref_date - pd.DateOffset(months=6)).strftime("%b %Y")} — {(ref_date - pd.DateOffset(months=3)).strftime("%b %Y")}'
    covenants.append({
        'name': 'Repayment at Term',
        'current': _safe(rat_ratio),
        'threshold': 0.95,
        'compliant': bool(rat_ratio >= 0.95) if rat_available else True,
        'operator': '>=',
        'format': 'pct',
        'period': rat_period,
        'available': rat_available,
        'partial': False,
        'method': 'direct',
        'confidence': 'A',
        'population': 'specific_filter(matured in 3-6mo window)',
        'note': 'No qualifying loans in measurement window' if not rat_available else None,
        'breakdown': rat_breakdown if rat_breakdown else [{'label': 'No qualifying loans', 'value': 0}],
    })

    # ── Covenant 5: LTV ≤ 75% ──────────────────────────────────────────
    # LTV = (facility_drawn - cash_balance) / (total_receivables + cash_balance)
    # Requires user-entered facility_params
    total_receivables = df[C_OUTSTANDING].sum() * mult if C_OUTSTANDING in df.columns else 0
    facility_drawn_val = facility_params.get('facility_drawn', 0) * mult
    cash_balance = facility_params.get('cash_balance', 0) * mult
    equity_injection = facility_params.get('equity_injection', 0) * mult

    ltv_available = bool(facility_drawn_val > 0)
    ltv_numerator = facility_drawn_val - cash_balance
    ltv_denominator = total_receivables + cash_balance + equity_injection
    ltv_ratio = ltv_numerator / ltv_denominator if ltv_denominator > 0 else 0

    ltv_breakdown = [
        {'label': 'Facility Drawn', 'value': _safe(facility_drawn_val)},
        {'label': 'Cash Balance', 'value': _safe(cash_balance)},
        {'label': 'Numerator (Drawn - Cash)', 'value': _safe(ltv_numerator)},
        {'label': 'Portfolio Receivables', 'value': _safe(total_receivables)},
    ]
    if equity_injection > 0:
        ltv_breakdown.append({'label': 'Equity Injection', 'value': _safe(equity_injection)})
    ltv_breakdown.extend([
        {'label': 'Denominator (Receivables + Cash + Equity)', 'value': _safe(ltv_denominator)},
        {'label': 'LTV Ratio', 'value': _safe(ltv_ratio), 'bold': True},
    ])

    covenants.append({
        'name': 'Loan-to-Value Ratio',
        'current': _safe(ltv_ratio),
        'threshold': 0.75,
        'compliant': bool(ltv_ratio <= 0.75) if ltv_available else True,
        'operator': '<=',
        'format': 'pct',
        'period': test_date_str,
        'available': ltv_available,
        'partial': not ltv_available,
        'method': 'manual',
        'confidence': 'B',  # manual input — observed off-tape, analyst-entered
        'population': 'manual(facility + cash balances)',
        'note': 'Enter facility amount and cash balances on the platform to compute LTV' if not ltv_available else None,
        'breakdown': ltv_breakdown,
    })

    # ── Summary ─────────────────────────────────────────────────────────
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


# ── 4. Portfolio Flow ───────────────────────────────────────────────────────

def compute_portfolio_flow(df, mult=1):
    """Compute monthly origination waterfall showing portfolio build-up.

    Returns monthly rows: loans originated, disbursed, repaid, outstanding,
    collection %, and cumulative totals.
    """
    monthly = []
    if C_DISB_DATE not in df.columns:
        return {'monthly': monthly, 'cumulative': {}}

    df2 = df.copy()
    df2['_month'] = df2[C_DISB_DATE].dt.to_period('M')

    for period, grp in sorted(df2.groupby('_month'), key=lambda x: x[0]):
        disbursed = grp[C_DISBURSED].sum() * mult if C_DISBURSED in grp.columns else 0
        repaid = grp[C_REPAID].sum() * mult if C_REPAID in grp.columns else 0
        outstanding = grp[C_OUTSTANDING].sum() * mult if C_OUTSTANDING in grp.columns else 0
        collectable = grp[C_COLLECTABLE].sum() * mult if C_COLLECTABLE in grp.columns else 0
        overdue = grp[C_OVERDUE].sum() * mult if C_OVERDUE in grp.columns else 0

        collection_pct = repaid / collectable * 100 if collectable > 0 else 0
        outstanding_pct = outstanding / disbursed * 100 if disbursed > 0 else 0

        monthly.append({
            'Month': str(period),
            'loans': int(len(grp)),
            'disbursed': _safe(disbursed),
            'repaid': _safe(repaid),
            'outstanding': _safe(outstanding),
            'overdue': _safe(overdue),
            'collectable': _safe(collectable),
            'collection_pct': _safe(collection_pct),
            'outstanding_pct': _safe(outstanding_pct),
        })

    # Cumulative totals
    total_disbursed = df[C_DISBURSED].sum() * mult if C_DISBURSED in df.columns else 0
    total_repaid = df[C_REPAID].sum() * mult if C_REPAID in df.columns else 0
    total_outstanding = df[C_OUTSTANDING].sum() * mult if C_OUTSTANDING in df.columns else 0
    total_collectable = df[C_COLLECTABLE].sum() * mult if C_COLLECTABLE in df.columns else 0

    cumulative = {
        'total_loans': len(df),
        'total_disbursed': _safe(total_disbursed),
        'total_repaid': _safe(total_repaid),
        'total_outstanding': _safe(total_outstanding),
        'total_collectable': _safe(total_collectable),
        'collection_pct': _safe(total_repaid / total_collectable * 100 if total_collectable else 0),
        'outstanding_pct': _safe(total_outstanding / total_disbursed * 100 if total_disbursed else 0),
    }

    return {
        'monthly': monthly,
        'cumulative': cumulative,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# KLAIM — Insurance Receivables Portfolio Analytics
# Matches Creditit platform: Borrowing Base, Portfolio Concentration, Covenants
# ═══════════════════════════════════════════════════════════════════════════════


def _klaim_outstanding(df, mult=1):
    """Outstanding = Purchase value - Collected - Denied (clipped at 0)."""
    pv = df['Purchase value'].fillna(0) * mult
    coll = df['Collected till date'].fillna(0) * mult
    denied = df['Denied by insurance'].fillna(0) * mult
    return (pv - coll - denied).clip(lower=0)


def _klaim_deal_age_days(df, ref_date=None):
    """Days since Deal date for each row."""
    if ref_date is None:
        ref_date = pd.Timestamp.now().normalize()
    else:
        ref_date = pd.to_datetime(ref_date)
    if 'Deal date' not in df.columns:
        return pd.Series(0, index=df.index)
    return (ref_date - df['Deal date']).dt.days.clip(lower=0)


def _klaim_curve_close_age(df):
    """
    Observed close-age (days) derived from the 13 cumulative collection-curve columns
    ('Actual in 30 days' … 'Actual in 390 days').

    For each row, the LAST 30-day bucket X where cumulative Actual increased (i.e.
    Actual_in_X > Actual_in_{X-30}, treating Actual_in_0 = 0) is the last observed
    cash-arrival moment. Returns X as an upper-bound close-age — honest statement of
    "closed on or before day X" at ±30d precision. Rows with no positive bucket delta
    (no curve data / no cash) return NaN so the caller can fall through.

    Returns a Series indexed like df, or None when any curve column is missing.
    """
    buckets = list(range(30, 391, 30))  # 30, 60, …, 390 (13 entries)
    cols = [f'Actual in {b} days' for b in buckets]
    if not all(c in df.columns for c in cols):
        return None
    curves = df[cols].apply(pd.to_numeric, errors='coerce').fillna(0).to_numpy()
    zero_prefix = np.zeros((curves.shape[0], 1))
    deltas = curves - np.hstack([zero_prefix, curves[:, :-1]])
    positive = deltas > 0
    any_positive = positive.any(axis=1)
    # argmax on reversed columns returns the LAST True in the original (first in reversed).
    last_idx = positive.shape[1] - 1 - positive[:, ::-1].argmax(axis=1)
    close_age = (last_idx + 1) * 30  # bucket index 0 → 30d, 12 → 390d
    return pd.Series(np.where(any_positive, close_age, np.nan), index=df.index)


def _klaim_wal_total(df, ref_date, mult):
    """
    Weighted-average life across the whole book (active + completed), PV-weighted.

    Active deals (still accumulating age):  age = snapshot_date − Deal date.
    Completed deals (bounded life):         age = close-age estimate, clipped to
                                                  [0, elapsed].

    Close-age fallback chain for completed rows (highest → lowest precision):
      Tier 1: Collection days so far (observed scalar)
      Tier 2: Curve-derived bucket — LAST 30d window where cumulative Actual
              increased; observed-via-curves, ±30d precision. Only applied when
              Tier 1 is primary (cdsf present) and has gaps curves can fill;
              tapes without curves skip Tier 2 and fall through.
      Tier 3: Expected collection days (contractual term)
      Tier 4: elapsed (ultimate)

    Weighting is Purchase value (face-value, life-of-deal) — the IC "how long is a
    dollar deployed?" view; distinct from Active WAL (outstanding-weighted, covenant).

    Active WAL is Framework Confidence A (observed); Total WAL is Confidence B
    (observed for active, observed-with-fallback for completed). Proxy choice is
    recorded in compute_methodology_log().

    Returns (wal_total_days, proxy_method) or (None, 'unavailable'). Method tag
    reports the HIGHEST-precision tier used for ≥1 row:
      - 'collection_days_so_far'                       — Tier 1 only
      - 'collection_days_so_far_with_curve_fallback'   — Tier 1 primary + Tier 2 filled gaps
      - 'expected_collection_days'                     — Tier 3 primary (cdsf absent)
      - 'unavailable'                                  — no proxy column present
    """
    if 'Deal date' not in df.columns or 'Purchase value' not in df.columns or 'Status' not in df.columns:
        return None, 'unavailable'
    has_cdsf = 'Collection days so far' in df.columns
    has_exp  = 'Expected collection days' in df.columns
    if not has_cdsf and not has_exp:
        return None, 'unavailable'

    pv = pd.to_numeric(df['Purchase value'], errors='coerce').fillna(0) * mult
    if pv.sum() <= 0:
        return None, 'unavailable'

    elapsed = _klaim_deal_age_days(df, ref_date)
    completed = df['Status'] == 'Completed'

    # Start from elapsed; override completed rows with the observed/inferred close age.
    age = elapsed.astype(float).copy()
    used_curves_as_fallback = False
    if completed.any():
        close_age = pd.Series(np.nan, index=df.index)
        # Tier 1: observed scalar — keep non-negative values.
        if has_cdsf:
            cdsf = pd.to_numeric(df['Collection days so far'], errors='coerce')
            close_age = close_age.where(~(cdsf >= 0), cdsf)
        # Tier 2: observed via curves — only kicks in when Tier 1 is primary and has gaps.
        if has_cdsf:
            curve_age = _klaim_curve_close_age(df)
            if curve_age is not None:
                gaps_before = int(close_age[completed].isna().sum())
                close_age = close_age.fillna(curve_age)
                if int(close_age[completed].isna().sum()) < gaps_before:
                    used_curves_as_fallback = True
        # Tier 3: contractual term — fill any rows still missing.
        if has_exp:
            exp = pd.to_numeric(df['Expected collection days'], errors='coerce')
            close_age = close_age.fillna(exp.where(exp >= 0))
        # Tier 4: elapsed — graceful fallback for any stray row still NaN.
        close_age = close_age.fillna(elapsed)
        # Clip so completed-deal age can never exceed the physical elapsed time.
        age.loc[completed] = np.minimum(np.maximum(close_age[completed], 0), elapsed[completed])

    wal = float(np.average(age, weights=pv))
    if has_cdsf:
        method = (
            'collection_days_so_far_with_curve_fallback'
            if used_curves_as_fallback
            else 'collection_days_so_far'
        )
    else:
        method = 'expected_collection_days'
    return wal, method


# ── Klaim Borrowing Base ────────────────────────────────────────────────────

def compute_klaim_borrowing_base(df, mult=1, ref_date=None, facility_params=None):
    """Klaim borrowing base waterfall (matching Creditit).

    Waterfall: Total A/R → Ineligible A/R → Eligible A/R
               → Concentration Adjustments → Advance Rate Discount
               → Adjusted Pool Balance + Cash = Borrowing Base

    Advance rates by region: UAE 90% (all eligible debtors must be UAE-incorporated per facility agreement)
    """
    if facility_params is None:
        facility_params = {}

    active = df[df['Status'] == 'Executed'].copy() if 'Status' in df.columns else df.copy()
    outstanding = _klaim_outstanding(active, mult)
    total_ar = float(outstanding.sum())

    # ── Ineligible: deals unpaid 91+ days after Invoice Date (MMA page 81) ──
    age = _klaim_deal_age_days(active, ref_date)
    max_age_days = facility_params.get('ineligibility_age_days', 91) if facility_params else 91
    inelig_age = float(outstanding[age > max_age_days].sum())
    # Denied > 50% of purchase value
    if 'Purchase value' in active.columns and 'Denied by insurance' in active.columns:
        denied_pct = active['Denied by insurance'].fillna(0) / active['Purchase value'].replace(0, 1)
        inelig_denied = float(outstanding[denied_pct > 0.5].sum())
    else:
        inelig_denied = 0
    total_ineligible = inelig_age + inelig_denied
    eligible = max(total_ar - total_ineligible, 0)

    # ── Concentration adjustments (payer-based) ─────────────────────
    conc_adj = 0
    payer_threshold = facility_params.get('single_payer_limit', 0.10)
    if 'Group' in active.columns and eligible > 0:
        active['_out'] = outstanding
        payer_out = active.groupby('Group')['_out'].sum()
        for payer, amount in payer_out.items():
            if amount / eligible > payer_threshold:
                excess = amount - eligible * payer_threshold
                conc_adj += excess

    eligible_after_conc = max(eligible - conc_adj, 0)

    # ── Advance rates by region ─────────────────────────────────────
    default_rate = facility_params.get('advance_rate', 0.90)
    rates_by_region = facility_params.get('advance_rates_by_region', {
        'UAE': 0.90,
    })
    adjusted_pool = eligible_after_conc * default_rate

    # Build advance rates breakdown
    advance_rates = []
    # If region column exists, compute per-region; otherwise single region
    region_col = None
    for col_candidate in ['Region', 'Country', 'Currency']:
        if col_candidate in active.columns:
            region_col = col_candidate
            break

    if region_col and eligible_after_conc > 0:
        active['_out'] = outstanding
        for region, grp in active.groupby(region_col):
            r_elig = float(grp['_out'].sum())
            r_elig = min(r_elig, eligible_after_conc * (r_elig / max(outstanding.sum(), 1)))
            rate = rates_by_region.get(str(region), default_rate)
            advance_rates.append({
                'region': str(region),
                'rate': _safe(rate),
                'eligible_ar': _safe(r_elig),
                'advanceable': _safe(r_elig * rate),
            })
    else:
        advance_rates.append({
            'region': 'All',
            'rate': _safe(default_rate),
            'eligible_ar': _safe(eligible_after_conc),
            'advanceable': _safe(adjusted_pool),
        })

    # ── Facility ────────────────────────────────────────────────────
    cash_balance = facility_params.get('cash_balance', 0) * mult
    borrowing_base = adjusted_pool + cash_balance
    facility_limit = facility_params.get('facility_limit', 0) * mult
    facility_outstanding = facility_params.get('facility_drawn', 0) * mult
    available = max(min(borrowing_base, facility_limit) - facility_outstanding, 0) if facility_limit else borrowing_base
    headroom = ((facility_limit - borrowing_base) / facility_limit * 100) if facility_limit else 0

    # ── Waterfall ───────────────────────────────────────────────────
    waterfall = [
        {'label': 'Total A/R',                'value': _safe(total_ar),              'type': 'total'},
        {'label': 'Ineligible A/R',           'value': _safe(-total_ineligible),     'type': 'deduction'},
        {'label': 'Eligible A/R',             'value': _safe(eligible),              'type': 'subtotal'},
        {'label': 'Concentration Adjustments', 'value': _safe(-conc_adj),             'type': 'deduction'},
        {'label': 'Advance Rate Discount',    'value': _safe(-(eligible_after_conc * (1 - default_rate))), 'type': 'deduction'},
        {'label': 'Adjusted Pool Balance',    'value': _safe(adjusted_pool),         'type': 'result'},
    ]

    return {
        'waterfall': waterfall,
        'kpis': {
            'total_ar': _safe(total_ar),
            'eligible_ar': _safe(eligible),
            'borrowing_base': _safe(borrowing_base),
            'available_to_draw': _safe(available),
            'ineligible': _safe(total_ineligible),
            'adjusted_pool_balance': _safe(adjusted_pool),
            'cash_balance': _safe(cash_balance),
            'facility_limit': _safe(facility_limit),
            'facility_pct': _safe(borrowing_base / facility_limit * 100 if facility_limit else 0),
        },
        'advance_rates': advance_rates,
        'facility': {
            'limit': _safe(facility_limit),
            'outstanding': _safe(facility_outstanding),
            'available': _safe(available),
            'headroom_pct': _safe(headroom),
        },
    }


# ── Klaim Portfolio Concentration ───────────────────────────────────────────

def compute_klaim_concentration_limits(df, mult=1, ref_date=None, facility_params=None):
    """Klaim concentration limits matching Creditit:
    1. Single receivable limit (0.50%)
    2. Top-10 Receivables Concentration (50%)
    3. Single customer concentration (10%)
    4. Single payer concentration (10%)
    5. Extended Age Receivables (5%, WAL ≤ 70 days, Extended Age 70-90d)
    """
    if facility_params is None:
        facility_params = {}

    active = df[df['Status'] == 'Executed'].copy() if 'Status' in df.columns else df.copy()
    outstanding = _klaim_outstanding(active, mult)
    total_ar = float(outstanding.sum())
    active['_out'] = outstanding
    limits = []

    # ── 1. Single receivable limit ──────────────────────────────────
    single_recv_threshold = facility_params.get('single_receivable_limit', 0.005)
    max_recv_pct = 0
    if total_ar > 0:
        max_recv_pct = float(outstanding.max() / total_ar)

    limits.append({
        'name': 'Single receivable limit',
        'current': _safe(max_recv_pct),
        'threshold': _safe(single_recv_threshold),
        'compliant': bool(max_recv_pct <= single_recv_threshold),
        'unit': '%',
        'format': 'pct',
        'confidence': 'A',
        'population': 'active_outstanding',
        'breakdown': [
            {'label': 'Largest single receivable', 'value': _safe(max_recv_pct)},
            {'label': 'Limit', 'value': _safe(single_recv_threshold)},
        ],
    })

    # ── 2. Top-10 Receivables Concentration ─────────────────────────
    top10_threshold = facility_params.get('top10_limit', 0.50)
    top10_pct = 0
    if total_ar > 0:
        top10 = outstanding.nlargest(10)
        top10_pct = float(top10.sum() / total_ar)

    limits.append({
        'name': 'Top-10 Receivables Concentration',
        'current': _safe(top10_pct),
        'threshold': _safe(top10_threshold),
        'compliant': bool(top10_pct <= top10_threshold),
        'unit': '%',
        'format': 'pct',
        'confidence': 'A',
        'population': 'active_outstanding',
        'breakdown': [
            {'label': 'Top 10 receivables share', 'value': _safe(top10_pct)},
            {'label': 'Limit', 'value': _safe(top10_threshold)},
        ],
    })

    # ── 3. Single customer (Group) concentration ────────────────────
    customer_threshold = facility_params.get('single_customer_limit', 0.10)
    worst_customer_pct = 0
    worst_customer = None
    customer_compliant = True
    if 'Group' in active.columns and total_ar > 0:
        cust_out = active.groupby('Group')['_out'].sum()
        cust_pcts = cust_out / total_ar
        if len(cust_pcts) > 0:
            worst_customer = str(cust_pcts.idxmax())
            worst_customer_pct = float(cust_pcts.max())
            customer_compliant = bool(worst_customer_pct <= customer_threshold)

    limits.append({
        'name': 'Single customer concentration',
        'current': _safe(worst_customer_pct),
        'threshold': _safe(customer_threshold),
        'compliant': customer_compliant,
        'unit': '%',
        'format': 'pct',
        'confidence': 'A',
        'population': 'active_outstanding',
        'breakdown': [
            {'label': f'Largest customer ({worst_customer})', 'value': _safe(worst_customer_pct)},
            {'label': 'Limit', 'value': _safe(customer_threshold)},
        ],
    })

    # ── 4. Single payer concentration ───────────────────────────────
    # Payer = insurance company (could be in 'Payer' or derived from Group)
    payer_threshold = facility_params.get('single_payer_limit', 0.10)
    worst_payer_pct = 0
    worst_payer = None
    payer_compliant = True
    payer_breaches = []
    conc_adjustment = 0
    payer_col = None
    for col_candidate in ['Payer', 'Insurance company', 'Group']:
        if col_candidate in active.columns:
            payer_col = col_candidate
            break

    if payer_col and total_ar > 0:
        payer_out = active.groupby(payer_col)['_out'].sum()
        payer_pcts = payer_out / total_ar
        if len(payer_pcts) > 0:
            worst_payer = str(payer_pcts.idxmax())
            worst_payer_pct = float(payer_pcts.max())
            payer_compliant = bool(worst_payer_pct <= payer_threshold)
        for payer, pct in payer_pcts.items():
            if pct > payer_threshold:
                excess = payer_out.loc[payer] - total_ar * payer_threshold
                conc_adjustment += excess
                payer_breaches.append({
                    'payer': str(payer),
                    'pct': _safe(float(pct)),
                })

    # Single payer: A if tape has explicit Payer column, B when using Group as proxy
    # (Klaim's current Apr 2026 tape lacks Payer — see Company Mind debtor_validation.json).
    payer_confidence = 'A' if payer_col in ('Payer', 'Insurance company') else 'B'
    limits.append({
        'name': 'Single payer concentration',
        'current': _safe(worst_payer_pct),
        'threshold': _safe(payer_threshold),
        'compliant': payer_compliant,
        'unit': '%',
        'format': 'pct',
        'confidence': payer_confidence,
        'population': 'active_outstanding',
        'method': 'direct' if payer_confidence == 'A' else 'proxy',
        'proxy_column': payer_col if payer_confidence == 'B' else None,
        'conc_adjustment': _safe(conc_adjustment),
        'breaches': payer_breaches,
        'breakdown': [
            {'label': f'Largest payer ({worst_payer})', 'value': _safe(worst_payer_pct)},
            {'label': 'Limit', 'value': _safe(payer_threshold)},
            {'label': 'Concentration adjustment', 'value': _safe(conc_adjustment), 'bold': True},
        ],
    })

    # ── 5. Extended Age Receivables (WAL ≤ 70d, carve-out 70-90d ≤ 5%) ──
    ext_age_threshold = facility_params.get('extended_age_limit', 0.05)
    wal_threshold_days = facility_params.get('wal_threshold_days', 70)
    ext_age_upper_days = facility_params.get('extended_age_upper_days', 90)
    ext_age_pct = 0
    wal_days = 0
    ext_age_adj = 0
    ext_age_breaches = 0
    age = _klaim_deal_age_days(active, ref_date)

    if total_ar > 0:
        # Extended age = receivables between WAL threshold and upper bound (70-90 days per MMA Art. 21.2)
        old_mask = (age > wal_threshold_days) & (age <= ext_age_upper_days)
        ext_age_amount = float(outstanding[old_mask].sum())
        ext_age_pct = ext_age_amount / total_ar
        ext_age_breaches = int(old_mask.sum())
        if ext_age_pct > ext_age_threshold:
            ext_age_adj = ext_age_amount - total_ar * ext_age_threshold

        # Weighted average life
        if outstanding.sum() > 0:
            wal_days = float(np.average(age, weights=outstanding))

    limits.append({
        'name': 'Extended Age Receivables Concentration Limit',
        'current': _safe(ext_age_pct),
        'threshold': _safe(ext_age_threshold),
        'compliant': bool(ext_age_pct <= ext_age_threshold),
        'unit': '%',
        'format': 'pct',
        'confidence': 'A',
        'population': 'active_outstanding',
        'conc_adjustment': _safe(ext_age_adj),
        'wal_days': _safe(wal_days),
        'breach_count': ext_age_breaches,
        'breakdown': [
            {'label': 'Extended age receivables share', 'value': _safe(ext_age_pct)},
            {'label': 'Limit', 'value': _safe(ext_age_threshold)},
            {'label': f'Weighted Average Life', 'value': f'{wal_days:.0f} days'},
            {'label': 'Concentration adjustment', 'value': _safe(ext_age_adj), 'bold': True},
        ],
    })

    compliant_count = sum(1 for l in limits if l['compliant'])
    breach_count = len(limits) - compliant_count

    return {
        'limits': limits,
        'compliant_count': compliant_count,
        'breach_count': breach_count,
    }


# ── Klaim Covenants ─────────────────────────────────────────────────────────

def compute_klaim_covenants(df, mult=1, ref_date=None, facility_params=None):
    """Klaim 6 covenants per MMA Article 18.2:
    1. Minimum Consolidated Cash Balance (Cash / max(Net Burn, 3M avg) ≥ 3.0x)
    2. Weighted Average Life of Receivables (≤ 70 days, dual-path: WAL or 5% carve-out)
    3. PAR30 (≤ 7%) — single breach NOT an EoD per MMA 18.3(i)
    4. PAR60 (≤ 5%)
    5. Collection Ratio (≥ 25%, period-based) — 2 consecutive breaches for EoD per MMA 18.3(ii)
    6. Paid vs Due Ratio (≥ 95%, period-based) — 2 consecutive breaches for EoD per MMA 18.3(iii)
    """
    if facility_params is None:
        facility_params = {}

    if ref_date is None:
        ref_date = pd.Timestamp.now().normalize()
    else:
        ref_date = pd.to_datetime(ref_date)

    test_date_str = ref_date.strftime('%Y-%m-%d')
    # Period = calendar month of ref_date
    period_start = ref_date.replace(day=1)
    period_end = (period_start + pd.DateOffset(months=1)) - pd.Timedelta(days=1)
    period_str = f'{period_start.strftime("%Y-%m-%d")} – {period_end.strftime("%Y-%m-%d")}'

    active = df[df['Status'] == 'Executed'].copy() if 'Status' in df.columns else df.copy()
    outstanding = _klaim_outstanding(active, mult)
    total_ar = float(outstanding.sum())

    covenants = []

    # ── 1. Minimum Consolidated Cash Balance ────────────────────────
    # Cash / max(Net Cash Burn prior month, 3M avg Net Cash Burn) ≥ 3.0x
    # Off-tape: requires facility_params
    cash = facility_params.get('cash_balance', 0) * mult
    net_burn = facility_params.get('net_cash_burn', 0) * mult
    net_burn_3m = facility_params.get('net_cash_burn_3m_avg', net_burn) * mult
    denominator = max(net_burn, net_burn_3m)
    cash_ratio = cash / denominator if denominator > 0 else 0
    cash_available = bool(denominator > 0)

    cash_ratio_limit = facility_params.get('cash_ratio_limit', 3.0) if facility_params else 3.0
    covenants.append({
        'name': 'Minimum Consolidated Cash Balance',
        'current': _safe(cash_ratio),
        'threshold': cash_ratio_limit,
        'compliant': bool(cash_ratio >= cash_ratio_limit) if cash_available else True,
        'operator': '>=',
        'format': 'ratio',
        'period': test_date_str,
        'available': cash_available,
        'partial': not cash_available,
        'method': 'manual',
        'confidence': 'B',  # manual — observed off-tape, analyst-entered values
        'population': 'manual(cash + net_burn)',
        'note': 'Enter cash balance and net cash burn on the platform' if not cash_available else None,
        'breakdown': [
            {'label': 'Consolidated Cash and Cash Equivalents', 'value': _safe(cash)},
            {'label': 'Net Cash Burn (prior month)', 'value': _safe(net_burn)},
            {'label': '3-month avg Net Cash Burn', 'value': _safe(net_burn_3m)},
            {'label': 'Denominator (higher of the two)', 'value': _safe(denominator), 'bold': True},
        ],
    })

    # ── 2. Weighted Average Life (≤ 70d, OR Extended Age 70-90d ≤ 5%) ──
    # MMA Art. 21: WAL test satisfied if WAL ≤ 70 days (Path A),
    # OR even if WAL > 70d, if Extended Age Receivables (70-90d) ≤ 5% of Eligible OPB (Path B).
    # The covenant is defined against the ACTIVE pool (outstanding-weighted) per the MMA, so
    # compliance keeps using wal_active. wal_total is an IC/monitoring view of life-of-deal
    # capital efficiency across the whole book (active + completed, PV-weighted).
    wal_threshold = facility_params.get('wal_threshold_days', 70)
    ext_age_limit = facility_params.get('extended_age_limit', 0.05)
    ext_age_upper = facility_params.get('extended_age_upper_days', 90)
    age = _klaim_deal_age_days(active, ref_date)
    wal_active = 0
    ext_age_pct = 0
    if total_ar > 0:
        wal_active = float(np.average(age, weights=outstanding))
        ext_age_mask = (age > wal_threshold) & (age <= ext_age_upper)
        ext_age_pct = float(outstanding[ext_age_mask].sum()) / total_ar if total_ar > 0 else 0

    wal_total, wal_total_method = _klaim_wal_total(df, ref_date, mult)

    # Dual-path compliance: Path A (WAL ≤ threshold) OR Path B (Extended Age ≤ 5%)
    # Compliance is ALWAYS decided on active WAL, per MMA definition.
    path_a = bool(wal_active <= wal_threshold)
    path_b = bool(ext_age_pct <= ext_age_limit)
    wal_compliant = path_a or path_b
    compliance_path = 'Path A (WAL)' if path_a else ('Path B (carve-out)' if path_b else 'Breach')

    wal_total_label = f'{wal_total:.0f} days' if wal_total is not None else 'n/a (needs Expected collection days)'
    dual_note = (
        'Covenant decided on Active WAL (outstanding-weighted). '
        'Total WAL is a life-of-deal view across active + completed (PV-weighted).'
    )
    compliance_note = (
        f'Compliant via carve-out (Extended Age {ext_age_pct:.1%} ≤ {ext_age_limit:.0%})'
        if (not path_a and path_b)
        else (f'{wal_active - wal_threshold:.0f} days over' if not wal_compliant else None)
    )

    covenants.append({
        'name': 'Weighted average life of receivables',
        'current': _safe(wal_active),
        'wal_active_days': _safe(wal_active),
        'wal_total_days': _safe(wal_total) if wal_total is not None else None,
        'wal_total_available': wal_total is not None,
        'wal_total_method': wal_total_method,
        'wal_active_confidence': 'A',
        'wal_total_confidence': 'B',
        'confidence': 'A',  # covenant compliance decision uses wal_active (Confidence A)
        'population': 'active_outstanding',  # WAL Active is covenant-binding per MMA Art. 21
        'wal_active_population': 'active_outstanding',
        'wal_total_population': 'total_pv',
        'threshold': _safe(wal_threshold),
        'compliant': wal_compliant,
        'operator': '<=',
        'format': 'days',
        'period': test_date_str,
        'available': True,
        'partial': False,
        'method': 'stable',
        'compliance_path': compliance_path,
        'note': compliance_note,
        'view_note': dual_note,
        'breakdown': [
            {'label': 'Active WAL (covenant, outstanding-weighted)', 'value': f'{wal_active:.0f} days'},
            {'label': 'Total WAL (book, PV-weighted)', 'value': wal_total_label},
            {'label': 'WAL Limit (Path A)', 'value': f'{wal_threshold} days'},
            {'label': f'Extended Age ({wal_threshold}-{ext_age_upper}d) share', 'value': f'{ext_age_pct:.1%}'},
            {'label': 'Extended Age Limit (Path B)', 'value': f'{ext_age_limit:.0%}'},
            {'label': 'Compliance Path', 'value': compliance_path, 'bold': True},
        ],
    })

    # ── 3. PAR30 (< 7%) ────────────────────────────────────────────
    # Receivables >30 days past expected collection / Total A/R
    par30_threshold = facility_params.get('par30_limit', 0.07)
    age_active = _klaim_deal_age_days(active, ref_date)
    par30_amount = float(outstanding[age_active > 30].sum()) if total_ar > 0 else 0
    # For Klaim, "past due" means age beyond expected term; use Pending as proxy
    # Better: use actual aging — overdue = age > some baseline (e.g. 90 days for claims)
    # Creditit shows 0% PAR30 — likely uses a different method (pending/denied based)
    # Use denied + pending > 30 days as PAR proxy
    par30_pct = par30_amount / total_ar if total_ar > 0 else 0

    # Override: if 'Pending insurance response' column exists, use pending-based PAR
    if 'Pending insurance response' in active.columns:
        pending = active['Pending insurance response'].fillna(0) * mult
        overdue_mask = (age_active > 90) & (pending > 0)  # Claims pending > 90 days
        par30_amount = float(outstanding[overdue_mask].sum())
        par30_pct = par30_amount / total_ar if total_ar > 0 else 0

    covenants.append({
        'name': 'PAR30 (Portfolio at Risk > 30 days)',
        'current': _safe(par30_pct),
        'threshold': _safe(par30_threshold),
        'compliant': bool(par30_pct < par30_threshold),
        'operator': '<',
        'format': 'pct',
        'period': test_date_str,
        'available': True,
        'partial': False,
        'method': 'age_pending',  # age_active > 90 AND Pending > 0; stable across tapes
        'confidence': 'B',  # proxy — Klaim lacks contractual DPD, uses operational-age
        'population': 'active_outstanding',
        'eod_rule': 'single_breach_not_eod',  # MMA 18.3(i): single breach is NOT an EoD
        'note': 'Single breach is not an Event of Default (MMA 18.3(i))',
        'breakdown': [
            {'label': 'At-risk receivables', 'value': _safe(par30_amount)},
            {'label': 'Total A/R', 'value': _safe(total_ar)},
            {'label': 'PAR30', 'value': _safe(par30_pct), 'bold': True},
        ],
    })

    # ── 4. PAR60 (< 5%) ────────────────────────────────────────────
    par60_threshold = facility_params.get('par60_limit', 0.05)
    if 'Pending insurance response' in active.columns:
        pending = active['Pending insurance response'].fillna(0) * mult
        overdue60_mask = (age_active > 120) & (pending > 0)
        par60_amount = float(outstanding[overdue60_mask].sum())
    else:
        par60_amount = float(outstanding[age_active > 60].sum()) if total_ar > 0 else 0
    par60_pct = par60_amount / total_ar if total_ar > 0 else 0

    covenants.append({
        'name': 'PAR60 (Portfolio at Risk > 60 days)',
        'current': _safe(par60_pct),
        'threshold': _safe(par60_threshold),
        'compliant': bool(par60_pct < par60_threshold),
        'operator': '<',
        'format': 'pct',
        'period': test_date_str,
        'available': True,
        'partial': False,
        'method': 'age_pending',  # age_active > 120 AND Pending > 0; stable across tapes
        'confidence': 'B',  # proxy — same substitution as PAR30
        'population': 'active_outstanding',
        'eod_rule': 'single_breach_is_eod',  # MMA 18.2(b)(ii): single breach IS an EoD
        'note': 'Calculated on the last day of each calendar month',
        'breakdown': [
            {'label': 'At-risk receivables', 'value': _safe(par60_amount)},
            {'label': 'Total A/R', 'value': _safe(total_ar)},
            {'label': 'PAR60', 'value': _safe(par60_pct), 'bold': True},
        ],
    })

    # ── 5. Collection Ratio (≥ 25%) ─────────────────────────────────
    # NOTE: True period ratio requires two snapshots (start vs end of period).
    # Single-tape approximation: cumulative collected / face value.
    coll_threshold = facility_params.get('collection_ratio_limit', 0.25)
    coll_ratio = 0
    if 'Deal date' in df.columns and 'Collected till date' in df.columns:
        # Deals active at start of period
        period_deals = df[
            (df['Deal date'] <= period_end) &
            (df['Status'] == 'Executed') if 'Status' in df.columns else True
        ]
        total_pv = period_deals['Purchase value'].sum() * mult if 'Purchase value' in period_deals.columns else 0
        total_coll = period_deals['Collected till date'].sum() * mult if len(period_deals) else 0
        coll_ratio = total_coll / total_pv if total_pv > 0 else 0

    covenants.append({
        'name': 'Collection Ratio (cumulative)',
        'current': _safe(coll_ratio),
        'threshold': _safe(coll_threshold),
        'compliant': bool(coll_ratio >= coll_threshold),
        'operator': '>=',
        'format': 'pct',
        'period': period_str,
        'available': True,
        'partial': True,
        'method': 'cumulative',  # single-tape approximation; stable across tapes
        'confidence': 'C',  # derived — single-snapshot approximation of a multi-snapshot definition (P0-5)
        'population': 'total_originated',
        'eod_rule': 'two_consecutive_breaches',  # MMA 18.3(ii): 2 consecutive breaches for EoD
        'note': 'Single-tape approximation: cumulative collected / face value. True period ratio requires two snapshots (Framework §17: Confidence C — derived).',
        'breakdown': [
            {'label': 'Collections (period)', 'value': _safe(total_coll if 'total_coll' in dir() else 0)},
            {'label': 'Total A/R (period)', 'value': _safe(total_pv if 'total_pv' in dir() else 0)},
            {'label': 'Collection Ratio', 'value': _safe(coll_ratio), 'bold': True},
        ],
    })

    # ── 6. Paid vs Due Ratio (≥ 95%) ───────────────────────────────
    # Amount paid in period / Amount due in period
    pvd_threshold = facility_params.get('paid_vs_due_limit', 0.95)
    pvd_ratio = 0
    amount_due = 0
    amount_paid = 0
    pvd_method = 'proxy'
    if 'Expected total' in df.columns and 'Collected till date' in df.columns:
        if 'Expected collection days' in df.columns:
            # Direct: filter to deals whose expected payment date falls within the period
            import pandas as _pd2
            exp_days = df['Expected collection days'].fillna(0).astype(float)
            df_pvd = df.copy()
            df_pvd['_exp_pay_date'] = df_pvd['Deal date'] + _pd2.to_timedelta(exp_days, unit='D')
            period_deals = df_pvd[
                (df_pvd['_exp_pay_date'] <= period_end) &
                (df_pvd['Status'] == 'Executed') if 'Status' in df_pvd.columns else True
            ]
            pvd_method = 'direct'
        else:
            period_deals = df[
                (df['Deal date'] <= period_end) &
                (df['Status'] == 'Executed') if 'Status' in df.columns else True
            ]
        amount_due = period_deals['Expected total'].sum() * mult if 'Expected total' in period_deals.columns else 0
        amount_paid = period_deals['Collected till date'].sum() * mult if len(period_deals) else 0
        pvd_ratio = amount_paid / amount_due if amount_due > 0 else 0

    # Paid vs Due: confidence tracks the method — 'direct' is A (uses Expected collection days
    # to filter deals whose payment falls in the period), 'proxy' is B (Deal date proxy).
    pvd_population = (
        'specific_filter(expected_payment_date in period)'
        if pvd_method == 'direct'
        else 'specific_filter(deal_date <= period_end)'
    )
    covenants.append({
        'name': 'Paid vs Due Ratio',
        'current': _safe(pvd_ratio),
        'threshold': _safe(pvd_threshold),
        'compliant': bool(pvd_ratio >= pvd_threshold),
        'operator': '>=',
        'format': 'pct',
        'period': period_str,
        'available': True,
        'partial': False,
        'method': pvd_method,  # 'direct' uses Expected collection days, 'proxy' uses Deal date
        'confidence': method_to_confidence(pvd_method),
        'population': pvd_population,
        'eod_rule': 'two_consecutive_breaches',  # MMA 18.3(iii): 2 consecutive breaches for EoD
        'note': 'EoD requires 2 consecutive monthly breaches (MMA 18.3(iii))',
        'breakdown': [
            {'label': 'Amount paid (period)', 'value': _safe(amount_paid if 'amount_paid' in dir() else 0)},
            {'label': 'Amount due (period)', 'value': _safe(amount_due if 'amount_due' in dir() else 0)},
            {'label': 'Paid vs Due', 'value': _safe(pvd_ratio), 'bold': True},
        ],
    })

    # ── 7. Parent Minimum Consolidated Cash Balance (≥ 3.0x) ────────
    # MMA 18.2(e): Same formula as Company cash balance, but for Parent (Klaim Holdings)
    # Requires manual input — Parent financials not in tape data
    parent_cash = facility_params.get('parent_cash_balance', 0) * mult
    parent_burn = facility_params.get('parent_net_cash_burn', 0) * mult
    parent_burn_3m = facility_params.get('parent_net_cash_burn_3m_avg', parent_burn) * mult
    parent_denom = max(parent_burn, parent_burn_3m)
    parent_ratio = parent_cash / parent_denom if parent_denom > 0 else 0
    parent_available = bool(parent_denom > 0)

    covenants.append({
        'name': 'Parent Minimum Cash Balance',
        'current': _safe(parent_ratio),
        'threshold': cash_ratio_limit,
        'compliant': bool(parent_ratio >= cash_ratio_limit) if parent_available else True,
        'operator': '>=',
        'format': 'ratio',
        'period': test_date_str,
        'available': parent_available,
        'partial': not parent_available,
        'method': 'manual',
        'confidence': 'B',  # manual — observed off-tape, analyst-entered
        'population': 'manual(parent cash + parent burn)',
        'eod_rule': 'single_breach_is_eod',
        'note': 'Requires manual input — enter Parent cash and burn data on the platform' if not parent_available else None,
        'breakdown': [
            {'label': 'Parent Consolidated Cash', 'value': _safe(parent_cash)},
            {'label': 'Parent Net Cash Burn (prior month)', 'value': _safe(parent_burn)},
            {'label': 'Parent 3M avg Net Cash Burn', 'value': _safe(parent_burn_3m)},
            {'label': 'Denominator', 'value': _safe(parent_denom), 'bold': True},
        ],
    })

    # ── BB Holiday Period check ─────────────────────────────────────
    # MMA 8.3(b): No BB cure obligation for first 5 months from agreement date
    agreement_date_str = facility_params.get('agreement_date', '2026-02-10')
    try:
        agreement_date = pd.to_datetime(agreement_date_str)
        bb_holiday_end = agreement_date + pd.DateOffset(months=5)
        bb_holiday_active = ref_date < bb_holiday_end
    except Exception:
        bb_holiday_active = False
        bb_holiday_end = None

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
        'bb_holiday_active': bb_holiday_active,
        'bb_holiday_end': bb_holiday_end.strftime('%Y-%m-%d') if bb_holiday_end else None,
    }


def annotate_covenant_eod(result, history):
    """Annotate covenants with consecutive breach tracking for EoD determination.

    Pure function: takes covenant result + history dict, returns annotated result.
    History format: {covenant_name: [{period, compliant, date}, ...]} sorted newest-first.

    Per MMA Article 18.3:
    - single_breach_not_eod: breach is a warning, not an EoD (PAR30)
    - single_breach_is_eod: any breach = immediate EoD (PAR60, Parent Cash)
    - two_consecutive_breaches: EoD only after 2 consecutive monthly breaches (Collection Ratio, Paid vs Due)
    """
    for cov in result.get('covenants', []):
        eod_rule = cov.get('eod_rule')
        if not eod_rule:
            continue

        name = cov['name']
        prev_records = history.get(name, [])
        is_breaching = not cov.get('compliant', True)

        if eod_rule == 'single_breach_not_eod':
            cov['eod_triggered'] = False
            cov['eod_status'] = 'breach_no_eod' if is_breaching else 'compliant'
            cov['consecutive_breaches'] = 1 if is_breaching else 0

        elif eod_rule == 'single_breach_is_eod':
            cov['eod_triggered'] = is_breaching
            cov['eod_status'] = 'eod_triggered' if is_breaching else 'compliant'
            cov['consecutive_breaches'] = 1 if is_breaching else 0

        elif eod_rule == 'two_consecutive_breaches':
            # Check if the most recent prior period was also a breach.
            # Requires: (a) prior period is truly the preceding month (within ~45 days),
            # AND (b) prior record used the same compute method (methodology change breaks the chain).
            prior_breach = False
            method_changed = False
            if prev_records:
                prev_period = prev_records[0].get('period', '')
                current_period = cov.get('period', '')
                is_consecutive = True
                if prev_period and current_period:
                    try:
                        import pandas as _pd
                        gap_days = (_pd.Timestamp(current_period) - _pd.Timestamp(prev_period)).days
                        is_consecutive = 15 <= gap_days <= 45  # roughly one calendar month
                    except Exception:
                        is_consecutive = True  # if date parsing fails, assume consecutive

                prev_method = prev_records[0].get('method')
                current_method = cov.get('method')
                # Treat missing method as unknown — don't penalise legacy history entries.
                method_changed = bool(prev_method and current_method and prev_method != current_method)

                prior_breach = (
                    is_consecutive
                    and not method_changed
                    and not prev_records[0].get('compliant', True)
                )

            if is_breaching and prior_breach:
                consecutive = 2
                eod_triggered = True
                eod_status = 'eod_triggered'
            elif is_breaching:
                consecutive = 1
                eod_triggered = False
                # If method changed, flag why we didn't treat this as consecutive.
                eod_status = 'first_breach_after_method_change' if method_changed else 'first_breach'
            else:
                consecutive = 0
                eod_triggered = False
                eod_status = 'compliant'

            cov['eod_triggered'] = eod_triggered
            cov['eod_status'] = eod_status
            cov['consecutive_breaches'] = consecutive
            if method_changed:
                cov['method_changed_vs_prior'] = True

    # Recount with EoD awareness
    eod_count = sum(1 for c in result['covenants'] if c.get('eod_triggered'))
    result['eod_count'] = eod_count
    return result
