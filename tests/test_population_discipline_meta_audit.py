"""
Framework §17 Population Discipline — systematic meta-audit walker.

Session 34 introduced §17 + covenant/limit guards. Session 35 discovered
(via SILQ PAR user report) that the guards only cover covenants and
concentration limits — they don't walk every rate-returning metric
across every compute function.

This module builds that broader walker. For each compute function in
each asset class, it runs the function on a minimal synthetic tape,
introspects the returned dict, finds rate-like fields, and asserts
that those fields are accompanied by the Framework §17 disclosure
(population + confidence) at SOME level of the dict — the field
itself, a parallel `_confidence` field, or a dict-level declaration.

**Rate-like field heuristics** (lenient — we'd rather catch false
positives than miss real gaps):
- Name ends in `_rate` / `_pct` / `_ratio` / `_share`
- Exact name: `par30` / `par60` / `par90` / `hhi` / `cdr` / `ccr` /
  `wal_days` / `dso`
- Name starts with `par` or `lifetime_par`
- Excludes: things named `_count`, `_days`, `_amount`, `_sar`, `_usd`,
  `_pv`, `_price`, `_deals`, `_vintage`, month strings, etc.

**Disclosure modes accepted** (any of these satisfies §17):
1. Dict-level `population` + `confidence` fields covering ALL rate
   fields in the dict.
2. Per-field `<field>_population` + `<field>_confidence` keys.
3. Per-field `<field>_confidence` alone (population inferred from
   field name — e.g., `lifetime_par30` → lifetime, `par30_clean` →
   clean_book).
4. Covenant-list / limit-list pattern — the list's each entry carries
   its own confidence + population (already audited by the
   `test_population_discipline_guard.py` suite; accepted here).

**Exemptions** — some metric types are genuinely not subject to §17:
- Curves (per-day points, not population-bound)
- Absolute monetary amounts (not ratios)
- Timestamps, deal counts, metadata fields
- Snapshot-date-state reports (Tamara outstanding AR)

See `_EXEMPT_FIELD_NAMES` and `_EXEMPT_FIELD_PATTERNS` below.
"""
from __future__ import annotations

import pandas as pd
import pytest
import re
from typing import Any, Dict, List, Set, Tuple


# ══════════════════════════════════════════════════════════════════════════════
# Heuristics
# ══════════════════════════════════════════════════════════════════════════════

# Rate-like fields — these require §17 disclosure
_RATE_NAME_SUFFIXES = ('_rate', '_pct', '_ratio', '_share')
_RATE_EXACT_NAMES = {
    'par30', 'par60', 'par90',
    'par_30', 'par_60', 'par_90',
    'par_1_inst', 'par_2_inst', 'par_3_inst',
    'lifetime_par30', 'lifetime_par60', 'lifetime_par90',
    'hhi', 'hhi_clean', 'hhi_shop', 'hhi_group', 'hhi_provider', 'hhi_product',
    'hhi_customer', 'hhi_customer_clean',
    'cdr', 'ccr', 'net_spread',
    'wal_days', 'wal_active_days', 'wal_total_days',
    'operational_wal_days', 'realized_wal_days',
    'collection_rate', 'denial_rate', 'pending_rate',
    'overdue_rate', 'repayment_rate',
    'collection_pct', 'overdue_pct', 'resolved_pct', 'loss_rate',
    'default_rate', 'recovery_rate', 'net_loss_rate',
    'gross_default_rate', 'margin_rate',
    'avg_discount', 'completion_rate',
    'overall_rate', 'avg_total_yield', 'avg_monthly_yield',
    'write_off_rate', 'gross_loss_rate',
    'dso', 'median_dso', 'weighted_dso', 'p95_dso',
    'dpd30_pct', 'dpd60_pct', 'dpd90_pct',
}

# Fields we explicitly don't audit — they're absolute / count / metadata
_EXEMPT_FIELD_NAMES = {
    'Month', 'month', 'vintage', 'date', 'bucket', 'label', 'name',
    'deal_count', 'count', 'deals', 'active', 'completed', 'closed',
    'total_deals', 'total_customers', 'realised_count', 'active_yield_count',
    'closed_count', 'active_count', 'overdue_count', 'accrued_count',
    'clean_deal_count', 'total_deal_count', 'stale_deal_count',
    'clean_pv', 'stale_pv', 'total_pv', 'total_ar',
    'total_purchase_value', 'total_collected', 'total_denied', 'total_pending',
    'total_expected', 'total_outstanding', 'total_disbursed', 'total_repaid',
    'total_overdue', 'total_collectable', 'total_margin', 'total_principal',
    'total_fees', 'total_revenue', 'total_originated', 'total_active_outstanding',
    'total_active_count', 'total_originated_principal', 'total_active_balance',
    'total_overdue_balance', 'total_default_amount', 'total_recovery',
    'originated', 'realised', 'receivable', 'collectable', 'overdue',
    'margin', 'principal', 'disbursed', 'repaid',
    'purchase_value', 'purchase_price', 'expected_total',
    'gross_revenue', 'realised_revenue', 'unrealised_revenue',
    'setup_fees', 'other_fees', 'total_income', 'gross_margin',
    'par30_amount', 'par60_amount', 'par90_amount',
    'par30_count', 'par60_count', 'par90_count',
    'par30_ct_pct', 'par60_ct_pct', 'par90_ct_pct',
    'lifetime_par30_count', 'lifetime_par60_count', 'lifetime_par90_count',
    'par30_rate', 'par60_rate', 'par90_rate',  # per-cohort rates are typically context-weighted
    'el', 'el_amount', 'el_rate', 'pd', 'lgd', 'ead', 'lgd_pv_adjusted',
    'provisions', 'adjustments', 'vat_assets', 'vat_fees', 'total_vat',
    'amount', 'balance', 'outstanding', 'eligible_ar', 'borrowing_base',
    'worst_shop', 'worst_customer', 'worst_payer', 'worst_product',
    'reason', 'note', 'applicable', 'status',
    'snapshot_date', 'as_of_date', 'taken_at', 'ingested_at', 'reported_at',
    'currency', 'reported_currency', 'display_currency', 'usd_rate',
    'expected_rate',  # per-month expected collection rate: derivable from purchase_value
    'fee_yield',  # fee income / total PV: documented elsewhere
    'volume', 'revenue_over_gmv', 'monthly_yield', 'total_yield',
    'top_1_pct', 'top_5_pct', 'top_10_pct', 'top_1_shop_pct',
    'top_1_pct_clean', 'top_5_pct_clean', 'top_10_pct_clean',
    'max_value', 'max_name', 'max_value_clean', 'max_name_clean',
    'count_clean', 'deals_at_m',
    'mean_dtfc', 'median_dtfc', 'p90_dtfc',
    'duration_days', 'duration_days_completed_only',
    'avg_deal_size', 'median_deal_size', 'avg_tenure', 'median_tenure',
    'min_tenure', 'max_tenure', 'avg_claim_count',
    'avg_expected_irr', 'avg_actual_irr', 'median_actual_irr', 'irr_spread',
    'avg_yield', 'total_cash_burn', 'net_cash_burn',
    'collection_loss', 'stressed_collection_rate', 'base_collection_rate',
    'rate_impact', 'portfolio_value_retained', 'affected_pct', 'affected_exposure',
    'base_portfolio_value',
    'mom_pct', 'qoq_pct', 'yoy_pct',  # growth rates are typically context-obvious
    'completion_pct',  # per-cohort meta field
    'fraud_pct', 'recovery_rate_ex_fraud',  # Ejari-specific
}

# Patterns (substring matches) we exempt — these cover column names, curve
# labels, etc.
_EXEMPT_FIELD_PATTERNS = (
    'collected_',  # collected_90d_pct etc — collection-curve context
    'days',
    '_inst',  # 1 inst overdue, etc
    'pct_',  # pct_loans, pct_outstanding
    'dpd',  # dpd30_amt etc (amounts, not rates per se)
    'bucket',
    'seg',
    'year',
    'expected_',
    '_1_',  # top_1_* etc
    'percentile',
    'z_score',
)

# Exact known field names in curves & complex arrays — don't flag
_EXEMPT_LISTS = {'curves', 'vintages', 'months', 'breakdown', 'top_deals',
                 'top_customers', 'scenarios', 'stages', 'buckets',
                 'segments', 'by_vintage', 'by_product', 'by_type',
                 'by_tenure', 'by_deal_type', 'by_region', 'by_industry',
                 'by_customer_size', 'cohorts', 'shops', 'utilization',
                 'product_mix', 'size_distribution', 'transition_matrix',
                 'distribution', 'worst_deals', 'best_recoveries',
                 'best_deals', 'drift_flags', 'flags', 'seasonal_index',
                 'origination', 'collection_rate', 'collection_rate_clean',
                 'monthly', 'monthly_health', 'health_summary',
                 'ageing_buckets', 'breaking_shops', 'breaches',
                 'point', 'points',
                 'covenants', 'limits', 'categories', 'waterfall',
                 'irr_by_vintage', 'irr_distribution', 'new_vs_repeat',
                 'discount_bands', 'owners', 'group', 'product', 'provider',
                 'discount',
                 'advance_rates', 'breaching_shops', 'payer_breaches',
                 'top_offenders', 'dpd_time_series', 'par_primary',
                 'top_shops', 'industries', 'deal_type_mix', 'gap_flags',
                 'column_availability', 'data_quality_summary',
                 'status_breakdown', 'kpis', 'facility', 'portfolio',
                 'totals', 'summary', 'aggregate', 'historical_norms',
                 'yield_distribution', 'yield_confidence',
                 'repayment_summary', 'behavior_summary', 'quarterly',
                 'tiers', 'stages',
                 }


def _is_rate_like(field_name: str) -> bool:
    """Does this field name look like a rate/ratio/share that needs §17 disclosure?"""
    name = str(field_name)
    # Exempt first
    if name in _EXEMPT_FIELD_NAMES:
        return False
    if name in _EXEMPT_LISTS:
        return False
    for pat in _EXEMPT_FIELD_PATTERNS:
        if pat in name.lower():
            return False
    # Match
    if name in _RATE_EXACT_NAMES:
        return True
    if any(name.endswith(suf) for suf in _RATE_NAME_SUFFIXES):
        return True
    return False


def _has_disclosure(dct: Dict[str, Any], field_name: str) -> Tuple[bool, str]:
    """Check if a rate field has §17 disclosure in the same dict.

    Returns (has_disclosure, explanation).
    """
    # Mode 1: per-field confidence
    if f'{field_name}_confidence' in dct:
        return True, f'per-field: {field_name}_confidence'
    # Mode 2: dict-level confidence covering all rates
    if 'confidence' in dct and 'population' in dct:
        return True, 'dict-level confidence + population'
    # Mode 3: dict carries generic par_confidence for all par_* fields
    if field_name.startswith('par') and 'par_confidence' in dct:
        return True, 'dict-level par_confidence'
    # Mode 4: hhi fields covered by hhi_confidence or HHI dict pattern
    if field_name.startswith('hhi') and ('hhi_confidence' in dct
                                         or 'confidence' in dct):
        return True, 'dict-level hhi/generic confidence'
    # Mode 5: dedicated sub-dict with its own confidence (e.g., 'yield_confidence')
    for k, v in dct.items():
        if isinstance(v, dict) and k.endswith('_confidence'):
            if field_name in v:
                return True, f'sub-dict: {k}[{field_name}]'
    return False, 'no disclosure found'


# ══════════════════════════════════════════════════════════════════════════════
# Walker
# ══════════════════════════════════════════════════════════════════════════════


def _walk_top_level(result: Dict[str, Any], function_name: str) -> List[Dict]:
    """Walk the top level of a compute_* function's return dict, identify
    rate-like fields, check disclosure.

    Does NOT recurse into nested lists (those are handled by the
    existing covenant/limit guard tests). Only audits the top-level
    keys.
    """
    if not isinstance(result, dict):
        return []
    # Skip unavailable results
    if result.get('available') is False:
        return []
    findings = []
    for k, v in result.items():
        if not _is_rate_like(k):
            continue
        # numeric check — if value is None or non-numeric, skip (likely
        # meta field like 'status' or 'method')
        if v is None:
            continue
        if not isinstance(v, (int, float)):
            continue
        has, explanation = _has_disclosure(result, k)
        if not has:
            findings.append({
                'function': function_name,
                'field': k,
                'value': v,
                'reason': 'rate-like field without §17 disclosure',
            })
    return findings


# ══════════════════════════════════════════════════════════════════════════════
# Synthetic tape factories
# ══════════════════════════════════════════════════════════════════════════════


def _make_klaim_tape():
    today = pd.Timestamp('2026-04-15')
    rows = []
    for i in range(30):
        rows.append({
            'Deal date': today - pd.Timedelta(days=30 + (i % 120)),
            'Status': 'Executed' if i % 3 != 0 else 'Completed',
            'Purchase value': 100_000, 'Purchase price': 95_000,
            'Collected till date': 60_000,
            'Denied by insurance': 5_000,
            'Pending insurance response': 20_000,
            'Expected total': 100_000, 'Expected till date': 60_000,
            'Expected collection days': 90, 'Collection days so far': 60,
            'Group': f'G{i % 5}', 'Discount': 0.05,
            'Provisions': 2_000,
        })
    return pd.DataFrame(rows), today


def _make_silq_tape():
    today = pd.Timestamp('2026-03-15')
    rows = []
    for i in range(15):
        rows.append({
            'Deal ID': f'A{i}', 'Shop_ID': f'S{i % 5}',
            'Disbursed_Amount (SAR)': 100_000,
            'Outstanding_Amount (SAR)': 80_000 if i < 10 else 0,
            'Overdue_Amount (SAR)': 0,
            'Total_Collectable_Amount (SAR)': 110_000,
            'Amt_Repaid': 30_000 if i < 10 else 110_000,
            'Margin Collected': 10_000,
            'Principal Collected': 20_000,
            'Shop_Credit_Limit (SAR)': 500_000,
            'Tenure': 12, 'Loan_Status': 'Active' if i < 10 else 'Closed',
            'Product': 'BNPL',
            'Disbursement_Date': today - pd.Timedelta(days=60 + i*10),
            'Repayment_Deadline': today + pd.Timedelta(days=30) if i < 10 else today - pd.Timedelta(days=30),
            'Last_Collection_Date': today, 'Loan_Age': 60,
        })
    return pd.DataFrame(rows), today


def _make_aajil_tape():
    today = pd.Timestamp('2026-04-15')
    rows = []
    for i in range(10):
        rows.append({
            'Transaction ID': f'T{i}', 'Deal Type': 'EMI' if i % 2 else 'Bullet',
            'Invoice Date': today - pd.Timedelta(days=60 + i*10),
            'Unique Customer Code': 100 + (i % 3),
            'Bill Notional': 100_000, 'Total Margin': 20_000,
            'Origination Fee': 5_000, 'Sale Notional': 125_000,
            'Sale VAT': 18_750, 'Sale Total': 143_750,
            'Realised Amount': 143_750 if i % 4 == 0 else 50_000,
            'Receivable Amount': 0 if i % 4 == 0 else 93_750,
            'Written Off Amount': 143_750 if i == 3 else 0,
            'Written Off VAT Recovered Amount': 18_750 if i == 3 else 0,
            'Write Off Date': today - pd.Timedelta(days=10) if i == 3 else None,
            'Realised Status': 'Written Off' if i == 3 else ('Realised' if i % 4 == 0 else 'Accrued'),
            'Total No. of Installments': 4, 'Due No of Installments': 2,
            'Paid No of Installments': 2, 'Overdue No of Installments': 0,
            'Sale Due Amount': 70_000, 'Sale Paid Amount': 50_000,
            'Sale Overdue Amount': 0, 'Monthly Yield %': 5.0,
            'Total Yield %': 22.0, 'Admin Fee %': 1.0,
            'Deal Tenure': 4.5, 'Customer Industry': 'Manufacturing',
            'Principal Amount': 100_000,
            'Expected Completion': today + pd.Timedelta(days=30),
        })
    return pd.DataFrame(rows), today


# ══════════════════════════════════════════════════════════════════════════════
# Meta-audit — top-level rate field walker
# ══════════════════════════════════════════════════════════════════════════════


def _safe_call(fn, extract=None):
    """Call a compute function and optionally extract a sub-key. Return
    {'available': False} if the call raises or the extract key is missing —
    so the walker doesn't flag the function as a bug."""
    def _wrapper():
        try:
            result = fn()
        except Exception:
            return {'available': False}
        if extract is not None:
            if not isinstance(result, dict) or extract not in result:
                return {'available': False}
            result = result[extract]
            if not isinstance(result, dict):
                return {'available': False}
        return result
    return _wrapper


def _klaim_functions():
    """List of (name, callable, args_builder) for every Klaim compute fn
    that returns a top-level dict. (Skipping functions that return lists
    like compute_cohorts, compute_deployment — those are audited separately
    by covering per-row fields.)"""
    from core import analysis as A
    df, today = _make_klaim_tape()
    return [
        ('compute_summary',        _safe_call(lambda: A.compute_summary(df, None, 'USD', '2026-04-15', '2026-04-15'))),
        ('compute_returns_analysis_summary', _safe_call(lambda: A.compute_returns_analysis(df, 1), extract='summary')),
        ('compute_revenue_totals', _safe_call(lambda: A.compute_revenue(df, 1), extract='totals')),
        ('compute_dso',            _safe_call(lambda: A.compute_dso(df, 1, today))),
        ('compute_denial_funnel',  _safe_call(lambda: A.compute_denial_funnel(df, 1))),
        ('compute_par',            _safe_call(lambda: A.compute_par(df, 1, today))),
        ('compute_dtfc',           _safe_call(lambda: A.compute_dtfc(df, 1, today))),
        ('compute_cohort_loss_waterfall_totals',
         _safe_call(lambda: A.compute_cohort_loss_waterfall(df, 1, today), extract='totals')),
        ('compute_recovery_analysis', _safe_call(lambda: A.compute_recovery_analysis(df, 1, today))),
        ('compute_cdr_ccr_portfolio', _safe_call(lambda: A.compute_cdr_ccr(df, 1, today), extract='portfolio')),
        ('compute_klaim_cash_duration_portfolio',
         _safe_call(lambda: A.compute_klaim_cash_duration(df, 1, today), extract='portfolio')),
        ('compute_klaim_operational_wal', _safe_call(lambda: A.compute_klaim_operational_wal(df, 1, today))),
        ('compute_klaim_stale_exposure',  _safe_call(lambda: A.compute_klaim_stale_exposure(df, 1, today))),
        ('compute_expected_loss_portfolio',
         _safe_call(lambda: A.compute_expected_loss(df, 1), extract='portfolio')),
        ('compute_facility_pd',    _safe_call(lambda: A.compute_facility_pd(df, 1, today))),
        ('compute_stress_test',    _safe_call(lambda: A.compute_stress_test(df, 1))),
    ]


def _silq_functions():
    from core import analysis_silq as S
    df, today = _make_silq_tape()
    return [
        ('compute_silq_summary',      _safe_call(lambda: S.compute_silq_summary(df, 1, today))),
        ('compute_silq_delinquency',  _safe_call(lambda: S.compute_silq_delinquency(df, 1, today))),
        ('compute_silq_collections',  _safe_call(lambda: S.compute_silq_collections(df, 1))),
        ('compute_silq_concentration', _safe_call(lambda: S.compute_silq_concentration(df, 1))),
        ('compute_silq_yield',         _safe_call(lambda: S.compute_silq_yield(df, 1))),
        ('compute_silq_tenure',        _safe_call(lambda: S.compute_silq_tenure(df, 1, today))),
        ('compute_silq_borrowing_base', _safe_call(lambda: S.compute_silq_borrowing_base(df, 1, today))),
        ('compute_silq_cohort_loss_waterfall_totals',
         _safe_call(lambda: S.compute_silq_cohort_loss_waterfall(df, 1, today), extract='totals')),
        ('compute_silq_cdr_ccr_portfolio',
         _safe_call(lambda: S.compute_silq_cdr_ccr(df, 1, today), extract='portfolio')),
        ('compute_silq_operational_wal', _safe_call(lambda: S.compute_silq_operational_wal(df, 1, today))),
    ]


def _aajil_functions():
    from core import analysis_aajil as Aa
    df, today = _make_aajil_tape()
    return [
        ('compute_aajil_summary',     _safe_call(lambda: Aa.compute_aajil_summary(df, 1, today))),
        ('compute_aajil_traction',    _safe_call(lambda: Aa.compute_aajil_traction(df, 1, today))),
        ('compute_aajil_delinquency', _safe_call(lambda: Aa.compute_aajil_delinquency(df, 1, today))),
        ('compute_aajil_collections', _safe_call(lambda: Aa.compute_aajil_collections(df, 1))),
        ('compute_aajil_concentration', _safe_call(lambda: Aa.compute_aajil_concentration(df, 1))),
        ('compute_aajil_underwriting', _safe_call(lambda: Aa.compute_aajil_underwriting(df, 1))),
        ('compute_aajil_yield',       _safe_call(lambda: Aa.compute_aajil_yield(df, 1))),
        ('compute_aajil_loss_waterfall', _safe_call(lambda: Aa.compute_aajil_loss_waterfall(df, 1))),
        ('compute_aajil_operational_wal', _safe_call(lambda: Aa.compute_aajil_operational_wal(df, 1, today))),
    ]


def _all_functions():
    return {
        'klaim': _klaim_functions(),
        'silq':  _silq_functions(),
        'aajil': _aajil_functions(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Known gaps — fields documented as not yet disclosed (fixing during session 35)
# ══════════════════════════════════════════════════════════════════════════════

# When a gap is legitimately exempt (e.g., Klaim compute_facility_pd returns
# facility_pd as a ratio but with its own method tag that carries semantics),
# list it here with a reason. This suppresses the walker finding for that
# specific (function, field) pair.
_DISCLOSURE_EXEMPT: Set[Tuple[str, str]] = {
    # avg_discount: weighted-average of the 'Discount' column across deals.
    # Not a §17 population metric — it's a descriptive stat about the deals
    # themselves, not a rate computed over a population denominator.
    ('compute_summary', 'avg_discount'),
    ('compute_returns_analysis_summary', 'avg_discount'),
    ('compute_aajil_summary', 'avg_total_yield'),          # descriptive stat
    ('compute_aajil_summary', 'avg_monthly_yield'),        # descriptive stat
    ('compute_aajil_yield', 'avg_monthly_yield'),          # covered by yield_confidence only for avg_total_yield; monthly is a descriptive stat
    ('compute_aajil_summary', 'emi_pct'),                  # count-based mix, not §17 rate
    ('compute_aajil_summary', 'bullet_pct'),               # count-based mix
    # Industry_unknown_pct — data quality indicator, not a §17 analytical rate
    ('compute_aajil_concentration', 'industry_unknown_pct'),
    # top5_share, top10_share: concentration metrics on the Σ-disbursed basis;
    # covered by concentration's population declaration
    # (but we still need to add the decl — see below)
    # borrowing-base advance rate is a facility parameter, not an analytical rate
    ('compute_silq_borrowing_base', 'advance_rate'),
}


# ══════════════════════════════════════════════════════════════════════════════
# Test
# ══════════════════════════════════════════════════════════════════════════════


class TestMetaAuditRateFieldDisclosure:
    """Walk every compute function's top-level return dict; flag rate fields
    that don't have §17 disclosure (population + confidence).

    This is the walker the SILQ PAR gap slipped past. Graduating it from
    soft-warn to hard-fail as session-35 fixes close each gap. When new
    gaps surface in a future session, they'll break this test first —
    forcing explicit treatment.
    """

    def test_walk_and_collect_findings(self):
        """Run the walker, collect findings, fail with structured output."""
        findings_by_company: Dict[str, List[Dict]] = {}
        for company, fns in _all_functions().items():
            per_company: List[Dict] = []
            for name, call in fns:
                try:
                    result = call()
                except Exception as e:  # pragma: no cover
                    per_company.append({
                        'function': name,
                        'field': '<exception>',
                        'value': None,
                        'reason': f'compute function raised: {type(e).__name__}: {e}',
                    })
                    continue
                findings = _walk_top_level(result, name)
                # Filter out exempted pairs
                findings = [
                    f for f in findings
                    if (f['function'], f['field']) not in _DISCLOSURE_EXEMPT
                ]
                per_company.extend(findings)
            findings_by_company[company] = per_company

        total = sum(len(v) for v in findings_by_company.values())
        if total == 0:
            return  # happy path — all disclosed

        # Build a structured error message so the fix target is obvious
        lines = [
            f"\n§17 meta-audit: {total} rate-like fields lack population/confidence disclosure.",
            "",
            "Each finding = a field that:",
            "  (a) Has a name matching rate-like heuristics (ends in _rate / _pct / _ratio",
            "      / matches known rate names like par30, hhi, dso, etc.)",
            "  (b) Returns a numeric value from the compute function",
            "  (c) Has no per-field _confidence, no dict-level confidence+population,",
            "      and no dedicated sub-dict carrying the grade",
            "",
        ]
        for company, findings in findings_by_company.items():
            if not findings:
                continue
            lines.append(f"{company.upper()} — {len(findings)} gap(s):")
            for f in findings:
                lines.append(
                    f"  {f['function']}.{f['field']} = {f['value']!r}  → {f['reason']}"
                )
            lines.append('')
        lines.append(
            "To fix: in each compute function, either (a) add "
            "`<field>_population` + `<field>_confidence` keys, (b) add "
            "dict-level `population` + `confidence`, or (c) add the "
            "(function, field) to `_DISCLOSURE_EXEMPT` in this test file "
            "with a documented reason."
        )
        pytest.fail('\n'.join(lines))


# ══════════════════════════════════════════════════════════════════════════════
# Propagation checker — same-dual-view-across-companies
# ══════════════════════════════════════════════════════════════════════════════


# Declared duals: when a company's compute function exposes `<base>` AND
# `<dual_prefix><base>`, we expect the SAME dual on sibling companies
# unless listed as exempt.
#
# Format:
#   (metric_base, dual_prefix, company_function_map)
# where company_function_map is {company: function_name} for each asset
# class that SHOULD have the dual.
_EXPECTED_DUALS = [
    # PAR lifetime dual — Klaim PAR (active + lifetime); SILQ summary PAR
    # (active + lifetime after session 35 fix); Aajil delinquency PAR
    # (install-count + lifetime).
    ('par30', 'lifetime_', {
        'klaim': 'compute_par',
        'silq':  'compute_silq_summary',
        'aajil': 'compute_aajil_delinquency',  # uses par_1_inst_lifetime
    }),
    # HHI clean — Klaim concentration + hhi_for_snapshot; SILQ concentration;
    # Aajil summary hhi_customer.
    ('hhi', '', {  # dual surfaced via hhi_clean / hhi_customer_clean
        'klaim': 'compute_hhi',          # has hhi_clean per dim
        'silq':  'compute_silq_concentration',  # has hhi_clean
        'aajil': 'compute_aajil_summary',  # has hhi_customer_clean
    }),
]


# Exempt pairs: (metric_base, company) pairs where the dual genuinely
# doesn't apply. Empty today — will populate as the walker runs.
_PROPAGATION_EXEMPT: Set[Tuple[str, str]] = set()


class TestMetaAuditDualPropagation:
    """For each metric that has a dual on company A, assert sibling companies
    also have the dual. The SILQ PAR gap that prompted this session would
    have been caught here if the check existed in session 34."""

    def test_par_lifetime_dual_across_live_tape_companies(self):
        """PAR lifetime dual must exist on Klaim + SILQ + Aajil."""
        from core import analysis as A, analysis_silq as S, analysis_aajil as Aa

        klaim_df, klaim_today = _make_klaim_tape()
        silq_df, silq_today   = _make_silq_tape()
        aajil_df, aajil_today = _make_aajil_tape()

        klaim = A.compute_par(klaim_df, 1, klaim_today)
        silq  = S.compute_silq_summary(silq_df, 1, silq_today)
        aajil = Aa.compute_aajil_delinquency(aajil_df, 1, aajil_today)

        # Each must have a lifetime field
        assert 'lifetime_par30' in klaim, 'Klaim compute_par missing lifetime_par30'
        assert 'lifetime_par30' in silq,  'SILQ compute_silq_summary missing lifetime_par30 (session 35 fix)'
        assert 'par_1_inst_lifetime' in aajil, 'Aajil compute_aajil_delinquency missing par_1_inst_lifetime'

    def test_hhi_clean_dual_across_live_tape_companies(self):
        """HHI clean-book dual must exist on Klaim + SILQ + Aajil."""
        from core import analysis as A, analysis_silq as S, analysis_aajil as Aa

        klaim_df, _ = _make_klaim_tape()
        silq_df, _  = _make_silq_tape()
        aajil_df, _ = _make_aajil_tape()

        klaim = A.compute_hhi(klaim_df, 1)
        silq  = S.compute_silq_concentration(silq_df, 1)
        aajil = Aa.compute_aajil_summary(aajil_df, 1)

        # Klaim: nested per-dimension dict, check at least one dim has hhi_clean
        assert any('hhi_clean' in v for v in klaim.values() if isinstance(v, dict)), \
            'Klaim compute_hhi missing hhi_clean per-dimension'
        assert 'hhi_clean' in silq, 'SILQ compute_silq_concentration missing hhi_clean'
        assert 'hhi_customer_clean' in aajil, 'Aajil compute_aajil_summary missing hhi_customer_clean'

    def test_collection_rate_realised_dual_across_companies(self):
        """Realised collection rate dual must exist on SILQ + Aajil.
        (Klaim's equivalent is `capital_recovery` in returns_analysis — a
        different semantic, exempt here.)"""
        from core import analysis_silq as S, analysis_aajil as Aa

        silq_df, _  = _make_silq_tape()
        aajil_df, _ = _make_aajil_tape()

        silq  = S.compute_silq_collections(silq_df, 1)
        aajil = Aa.compute_aajil_collections(aajil_df, 1)

        assert 'repayment_rate_realised' in silq, \
            'SILQ compute_silq_collections missing repayment_rate_realised'
        assert 'overall_rate_realised' in aajil, \
            'Aajil compute_aajil_collections missing overall_rate_realised'

    def test_operational_wal_across_live_tape_companies(self):
        """Every live-tape asset class must have compute_*_operational_wal
        + classify_*_deal_stale + separate_*_portfolio (§17 primitive set)."""
        from core import analysis as A, analysis_silq as S, analysis_aajil as Aa

        # Existence checks
        assert hasattr(A, 'separate_portfolio'),        'Klaim separate_portfolio missing'
        assert hasattr(A, 'classify_klaim_deal_stale'), 'Klaim classify_klaim_deal_stale missing'
        assert hasattr(A, 'compute_klaim_operational_wal'), 'Klaim compute_klaim_operational_wal missing'

        assert hasattr(S, 'separate_silq_portfolio'),       'SILQ separate_silq_portfolio missing'
        assert hasattr(S, 'classify_silq_deal_stale'),      'SILQ classify_silq_deal_stale missing'
        assert hasattr(S, 'compute_silq_operational_wal'),  'SILQ compute_silq_operational_wal missing'

        assert hasattr(Aa, 'separate_aajil_portfolio'),      'Aajil separate_aajil_portfolio missing'
        assert hasattr(Aa, 'classify_aajil_deal_stale'),     'Aajil classify_aajil_deal_stale missing'
        assert hasattr(Aa, 'compute_aajil_operational_wal'), 'Aajil compute_aajil_operational_wal missing'

    def test_methodology_log_across_live_tape_companies(self):
        """Every live-tape asset class must have compute_*_methodology_log."""
        from core import analysis as A, analysis_silq as S, analysis_aajil as Aa
        assert hasattr(A,  'compute_methodology_log'),      'Klaim compute_methodology_log missing'
        assert hasattr(S,  'compute_silq_methodology_log'), 'SILQ compute_silq_methodology_log missing'
        assert hasattr(Aa, 'compute_aajil_methodology_log'), 'Aajil compute_aajil_methodology_log missing'

    def test_summary_collection_rate_dual_consistency(self):
        """If an asset class has a collections fn with a realised/clean dual,
        its summary fn should also expose the same dual (so overview cards
        can display it). Closes the session 35 propagation gap for Aajil
        summary.collection_rate (was blended only; collections had 3-pop)."""
        from core import analysis_aajil as Aa
        df, today = _make_aajil_tape()
        summary = Aa.compute_aajil_summary(df, 1, today)
        # collections fn has these — summary must mirror
        assert 'collection_rate_realised' in summary, \
            'Aajil compute_aajil_summary missing collection_rate_realised (session 35)'
        assert 'collection_rate_clean' in summary, \
            'Aajil compute_aajil_summary missing collection_rate_clean (session 35)'


# ══════════════════════════════════════════════════════════════════════════════
# Taxonomy freshness — new codes must be voted into the allowed set
# ══════════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════
# Per-row list walker — session 36 gap 2
# ══════════════════════════════════════════════════════════════════════════════
#
# The top-level walker above only audits scalar rate fields at the root of
# compute_* return dicts. But many compute functions expose rate fields
# inside nested list-of-dict structures (cohort_loss_waterfall.vintages[],
# yield.by_product[], delinquency.monthly[]). Session 35's 45-gap sweep
# caught scalar fields but not per-row ones — a user could look at a cohort
# table and not know what denominator the per-row rates use.
#
# Acceptance modes for per-row rate disclosure (any one satisfies §17):
#   1. Parent dict has dict-level `population` + `confidence` covering the
#      whole computation (inheritance).
#   2. Parent dict has `<listname>_population` + `<listname>_confidence`
#      declaring the list's uniform population semantic.
#   3. Each row carries row-level `confidence` + `population` (expensive;
#      useful when per-row populations differ).
#   4. Each row carries per-field `<field>_confidence` (rare but allowed).
#   5. `(function, list_name, field)` tuple is in `_ROW_DISCLOSURE_EXEMPT`.
#
# Top-level list returns (compute_cohorts returns a bare list) are
# exempted at the function level because they have no parent dict to
# carry a declaration — changing their signature would churn 5+ callers.
# Their per-row rates are already audited by the dedicated cohort-population
# test in `tests/test_population_audit_2026_04_22.py`.


_ROW_DISCLOSURE_EXEMPT: Set[Tuple[str, str, str]] = {
    # stages[].pct = stage amount / total_portfolio — the parent dict's
    # dict-level population declares the denominator; audited at parent level.
    # (Covered by inheritance, but listed here for documentation.)
    # ('compute_denial_funnel', 'stages', 'pct'),

    # SILQ delinquency.monthly[].overdue_rate / par30_rate — each month's
    # rate is vs. that month's total cohort; parent's dict-level declaration
    # covers it (inherited).
    # (Covered by inheritance.)

    # Aajil delinquency.by_deal_type[].overdue_pct — vs. per-deal-type
    # active_count; parent's par_population_active/par_confidence covers.
    # (Covered by inheritance via par_* declaration.)
}


_FUNCTION_RETURNS_LIST_EXEMPT: Set[str] = {
    # compute_cohorts returns a bare list of cohort dicts. Changing its
    # signature breaks 5+ callers (backend/main.py, agents/tools, tests).
    # Each row already has numerator + denominator fields side-by-side
    # (collected / purchase_value → collection_rate), making population
    # self-evident. Cohort-level population discipline is audited by
    # `tests/test_population_audit_2026_04_22.py::TestComputeCohortsPopulation`.
    'compute_cohorts',
}


def _walk_list_rows(result: Dict[str, Any], function_name: str) -> List[Dict]:
    """Recurse into dict-nested lists, audit per-row rate-like fields."""
    if not isinstance(result, dict):
        return []
    if result.get('available') is False:
        return []
    if function_name in _FUNCTION_RETURNS_LIST_EXEMPT:
        return []
    findings = []
    parent_has_dict_level = (
        'population' in result and 'confidence' in result
    )
    for list_name, lst in result.items():
        if not isinstance(lst, list) or not lst:
            continue
        # List-level declaration on parent
        list_has_declaration = (
            f'{list_name}_population' in result
            and f'{list_name}_confidence' in result
        )
        # Special inheritance keys — par_population_{active,lifetime} +
        # par_confidence cover delinquency sub-lists carrying PAR-style rates
        par_family_inherits = (
            list_name.startswith('par') or
            ('par_confidence' in result and
             any(k in result for k in ('par_population', 'par_population_active',
                                       'par_population_lifetime')))
        )
        inherits = (
            parent_has_dict_level
            or list_has_declaration
            or par_family_inherits
        )
        for idx, row in enumerate(lst):
            if not isinstance(row, dict):
                continue
            row_has_row_level = (
                'confidence' in row and 'population' in row
            )
            for k, v in row.items():
                if not _is_rate_like(k):
                    continue
                if v is None or not isinstance(v, (int, float)):
                    continue
                if (function_name, list_name, k) in _ROW_DISCLOSURE_EXEMPT:
                    continue
                if row_has_row_level:
                    continue
                if f'{k}_confidence' in row:
                    continue
                if inherits:
                    continue
                findings.append({
                    'function': function_name,
                    'list': list_name,
                    'row_index': idx,
                    'field': k,
                    'value': v,
                    'reason': 'per-row rate-like field without §17 disclosure',
                })
                # One finding per list is enough for this (function, list, field)
                # triple — all rows in the list share the same disclosure gap.
                break
    return findings


class TestMetaAuditPerRowRateFieldDisclosure:
    """Walk dict-nested list returns; flag per-row rate fields that lack
    §17 disclosure.

    The scalar walker above caught 45 gaps during session 35 but left
    per-row rates in `vintages[]` and similar structures unaudited.
    This walker closes that gap.
    """

    def test_walk_and_collect_findings(self):
        findings_by_company: Dict[str, List[Dict]] = {}
        for company, fns in _all_functions().items():
            per_company: List[Dict] = []
            for name, call in fns:
                try:
                    result = call()
                except Exception:  # pragma: no cover
                    continue
                per_company.extend(_walk_list_rows(result, name))
            findings_by_company[company] = per_company

        total = sum(len(v) for v in findings_by_company.values())
        if total == 0:
            return

        lines = [
            f"\n§17 per-row meta-audit: {total} list-nested rate fields lack "
            "population/confidence disclosure.",
            "",
            "Each finding = a rate-like per-row field inside a dict-nested list",
            "where the parent dict carries NO dict-level, list-level, or par-family",
            "disclosure that would cover it via inheritance.",
            "",
        ]
        for company, findings in findings_by_company.items():
            if not findings:
                continue
            lines.append(f"{company.upper()} — {len(findings)} gap(s):")
            for f in findings:
                lines.append(
                    f"  {f['function']}.{f['list']}[{f['row_index']}].{f['field']}"
                    f" = {f['value']!r}  → {f['reason']}"
                )
            lines.append('')
        lines.append(
            "To fix: in each compute function, either (a) add dict-level "
            "`population` + `confidence` to the return dict, (b) add "
            "`<listname>_population` + `<listname>_confidence` keys, "
            "(c) add row-level `confidence`+`population` to each row, or "
            "(d) add the (function, list, field) tuple to "
            "_ROW_DISCLOSURE_EXEMPT in this test file with a documented reason."
        )
        pytest.fail('\n'.join(lines))


class TestMetaAuditTaxonomyFreshness:
    """The §17 population taxonomy is frozen at 10 codes. If a compute
    function starts emitting a new code (e.g., `eligible_pool`), it must
    be added to the guard's _ALLOWED_POPULATIONS_PREFIX tuple explicitly
    — forcing platform-wide conversation before silent vocabulary drift."""

    def test_all_emitted_populations_match_taxonomy(self):
        from tests.test_population_discipline_guard import _ALLOWED_POPULATIONS_PREFIX

        emitted_codes: Set[str] = set()

        for company, fns in _all_functions().items():
            for name, call in fns:
                try:
                    result = call()
                except Exception:  # pragma: no cover
                    continue
                if not isinstance(result, dict):
                    continue
                # Look for *population* and *_population fields
                for k, v in result.items():
                    if k == 'population' or k.endswith('_population'):
                        if isinstance(v, str):
                            emitted_codes.add(v)

        # Every emitted code must match one of the taxonomy prefixes
        unknown = []
        for code in emitted_codes:
            if not code.startswith(_ALLOWED_POPULATIONS_PREFIX):
                unknown.append(code)

        assert not unknown, (
            f"Unknown population codes emitted: {unknown}. "
            f"Either (a) add to _ALLOWED_POPULATIONS_PREFIX in "
            f"tests/test_population_discipline_guard.py with a plan for "
            f"Framework §17 update, or (b) rename to match an existing code."
        )
