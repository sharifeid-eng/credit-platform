"""
Regression tests for the 2026-04-22 metric-population audit fixes.
See reports/metric_population_audit_2026-04-22.md for the full doctrine and
each gap's file/line references.

Structure: one test class per audit item (P0-1..P0-6, P1-1..P1-8, P2-x, UNCERTAIN).
Every test is a contract — if the name, field, or relational invariant
changes, the test fails with a clear message.
"""
import pandas as pd
import numpy as np
import pytest


# ══════════════════════════════════════════════════════════════════════════════
# P0-6 — Confidence grading platform-wide (Framework §10 / §17)
# ══════════════════════════════════════════════════════════════════════════════


class TestP06ConfidenceGradingMapping:
    """method_to_confidence() maps method tags to A/B/C per Framework §10."""

    def test_direct_method_maps_to_A(self):
        from core.analysis import method_to_confidence
        assert method_to_confidence('direct') == 'A'

    def test_observed_method_maps_to_A(self):
        from core.analysis import method_to_confidence
        assert method_to_confidence('observed') == 'A'

    def test_age_pending_method_maps_to_B(self):
        from core.analysis import method_to_confidence
        assert method_to_confidence('age_pending') == 'B'

    def test_proxy_method_maps_to_B(self):
        from core.analysis import method_to_confidence
        assert method_to_confidence('proxy') == 'B'

    def test_manual_method_maps_to_B(self):
        from core.analysis import method_to_confidence
        assert method_to_confidence('manual') == 'B'

    def test_cumulative_method_maps_to_C(self):
        # Single-snapshot approximation of a multi-snapshot definition.
        from core.analysis import method_to_confidence
        assert method_to_confidence('cumulative') == 'C'

    def test_derived_method_maps_to_C(self):
        from core.analysis import method_to_confidence
        assert method_to_confidence('derived') == 'C'

    def test_empirical_benchmark_maps_to_C(self):
        from core.analysis import method_to_confidence
        assert method_to_confidence('empirical_benchmark') == 'C'

    def test_unknown_method_defaults_to_B(self):
        from core.analysis import method_to_confidence
        assert method_to_confidence('some_future_method') == 'B'

    def test_none_method_defaults_to_B(self):
        from core.analysis import method_to_confidence
        assert method_to_confidence(None) == 'B'


class TestP06SILQCovenantsCarryConfidence:
    """Every SILQ covenant dict must carry confidence + population fields."""

    def _make_tape(self):
        # Minimal SILQ tape: active + closed, with DPD sources.
        today = pd.Timestamp('2026-03-01')
        rows = []
        # 50 active, 5 deep-DPD, 10 closed with RepaymentDeadline in prior 3mo
        for i in range(50):
            rows.append({
                'Deal ID': f'A{i}', 'Shop_ID': f'S{i % 5}',
                'Disbursed_Amount (SAR)': 100_000,
                'Outstanding_Amount (SAR)': 80_000,
                'Overdue_Amount (SAR)': 0,
                'Total_Collectable_Amount (SAR)': 110_000,
                'Amt_Repaid': 30_000, 'Margin Collected': 10_000,
                'Principal Collected': 20_000, 'Shop_Credit_Limit (SAR)': 500_000,
                'Tenure': 12, 'Loan_Status': 'Active',
                'Product': 'BNPL',
                'Disbursement_Date': today - pd.Timedelta(days=60),
                'Repayment_Deadline': today + pd.Timedelta(days=30),
                'Last_Collection_Date': today - pd.Timedelta(days=5),
                'Loan_Age': 60,
            })
        for i in range(5):
            rows.append({
                'Deal ID': f'B{i}', 'Shop_ID': f'S{i}',
                'Disbursed_Amount (SAR)': 50_000,
                'Outstanding_Amount (SAR)': 50_000,
                'Overdue_Amount (SAR)': 50_000,
                'Total_Collectable_Amount (SAR)': 55_000,
                'Amt_Repaid': 0, 'Margin Collected': 0, 'Principal Collected': 0,
                'Shop_Credit_Limit (SAR)': 500_000,
                'Tenure': 12, 'Loan_Status': 'Active',
                'Product': 'BNPL',
                'Disbursement_Date': today - pd.Timedelta(days=200),
                'Repayment_Deadline': today - pd.Timedelta(days=100),  # 100 DPD
                'Last_Collection_Date': None, 'Loan_Age': 200,
            })
        for i in range(10):
            rows.append({
                'Deal ID': f'C{i}', 'Shop_ID': f'S{i % 5}',
                'Disbursed_Amount (SAR)': 100_000,
                'Outstanding_Amount (SAR)': 0,
                'Overdue_Amount (SAR)': 0,
                'Total_Collectable_Amount (SAR)': 110_000,
                'Amt_Repaid': 110_000, 'Margin Collected': 10_000,
                'Principal Collected': 100_000, 'Shop_Credit_Limit (SAR)': 500_000,
                'Tenure': 12, 'Loan_Status': 'Closed',
                'Product': 'BNPL',
                'Disbursement_Date': today - pd.Timedelta(days=180),
                'Repayment_Deadline': today - pd.Timedelta(days=60),
                'Last_Collection_Date': today - pd.Timedelta(days=30),
                'Loan_Age': 180,
            })
        return pd.DataFrame(rows), today

    def test_every_silq_covenant_has_confidence_field(self):
        from core.analysis_silq import compute_silq_covenants
        df, today = self._make_tape()
        result = compute_silq_covenants(df, mult=1, ref_date=today)
        for cov in result['covenants']:
            assert 'confidence' in cov, f"Missing confidence on covenant '{cov['name']}'"
            assert cov['confidence'] in {'A', 'B', 'C'}, \
                f"Covenant '{cov['name']}' confidence={cov['confidence']!r}"

    def test_every_silq_covenant_has_population_field(self):
        from core.analysis_silq import compute_silq_covenants
        df, today = self._make_tape()
        result = compute_silq_covenants(df, mult=1, ref_date=today)
        for cov in result['covenants']:
            assert 'population' in cov, f"Missing population on covenant '{cov['name']}'"
            assert isinstance(cov['population'], str) and len(cov['population']) > 0

    def test_silq_par_covenants_are_confidence_A(self):
        from core.analysis_silq import compute_silq_covenants
        df, today = self._make_tape()
        result = compute_silq_covenants(df, mult=1, ref_date=today)
        par30 = next(c for c in result['covenants'] if 'PAR 30' in c['name'])
        par90 = next(c for c in result['covenants'] if 'PAR 90' in c['name'])
        assert par30['confidence'] == 'A'
        assert par90['confidence'] == 'A'
        assert par30['population'] == 'active_outstanding'
        assert par90['population'] == 'active_outstanding'

    def test_silq_ltv_is_confidence_B_when_manual(self):
        from core.analysis_silq import compute_silq_covenants
        df, today = self._make_tape()
        result = compute_silq_covenants(df, mult=1, ref_date=today)
        ltv = next(c for c in result['covenants'] if 'Loan-to-Value' in c['name'])
        assert ltv['method'] == 'manual'
        assert ltv['confidence'] == 'B'


class TestP06PortfolioPySILQCovenantsCarryConfidence:
    """Same invariants for the portfolio.py SILQ covenant path (memo engine)."""

    def _make_tape(self):
        return TestP06SILQCovenantsCarryConfidence()._make_tape()

    def test_every_portfolio_silq_covenant_has_confidence(self):
        from core.portfolio import compute_covenants
        df, today = self._make_tape()
        result = compute_covenants(df, mult=1, ref_date=today)
        for cov in result['covenants']:
            assert 'confidence' in cov, f"Missing confidence on '{cov['name']}'"
            assert cov['confidence'] in {'A', 'B', 'C'}

    def test_every_portfolio_silq_covenant_has_population(self):
        from core.portfolio import compute_covenants
        df, today = self._make_tape()
        result = compute_covenants(df, mult=1, ref_date=today)
        for cov in result['covenants']:
            assert 'population' in cov, f"Missing population on '{cov['name']}'"


class TestP06KlaimCovenantsCarryConfidence:
    """Every Klaim covenant dict must carry confidence + population fields."""

    def _make_klaim_tape(self):
        today = pd.Timestamp('2026-04-15')
        rows = []
        # 200 active deals, 50 completed
        for i in range(200):
            rows.append({
                'Deal date': today - pd.Timedelta(days=30 + (i % 120)),
                'Status': 'Executed',
                'Purchase value': 100_000,
                'Purchase price': 95_000,
                'Collected till date': 50_000 if i % 3 != 0 else 5_000,
                'Denied by insurance': 5_000,
                'Pending insurance response': 45_000 if i % 3 == 0 else 0,
                'Expected total': 100_000,
                'Expected till date': 60_000,
                'Expected collection days': 90,
                'Collection days so far': 60 + (i % 60),
                'Group': f'G{i % 10}',
                'Discount': 0.05,
            })
        for i in range(50):
            rows.append({
                'Deal date': today - pd.Timedelta(days=365 + (i % 30)),
                'Status': 'Completed',
                'Purchase value': 100_000,
                'Purchase price': 95_000,
                'Collected till date': 95_000,
                'Denied by insurance': 5_000,
                'Pending insurance response': 0,
                'Expected total': 100_000,
                'Expected till date': 100_000,
                'Expected collection days': 90,
                'Collection days so far': 90,
                'Group': f'G{i % 5}',
                'Discount': 0.05,
            })
        return pd.DataFrame(rows), today

    def test_every_klaim_covenant_has_confidence(self):
        from core.portfolio import compute_klaim_covenants
        df, today = self._make_klaim_tape()
        result = compute_klaim_covenants(df, mult=1, ref_date=today)
        for cov in result['covenants']:
            assert 'confidence' in cov, f"Missing confidence on '{cov['name']}'"
            assert cov['confidence'] in {'A', 'B', 'C'}

    def test_every_klaim_covenant_has_population(self):
        from core.portfolio import compute_klaim_covenants
        df, today = self._make_klaim_tape()
        result = compute_klaim_covenants(df, mult=1, ref_date=today)
        for cov in result['covenants']:
            assert 'population' in cov, f"Missing population on '{cov['name']}'"

    def test_klaim_par30_is_confidence_B(self):
        # Method age_pending — operational-age proxy for contractual 30d DPD
        from core.portfolio import compute_klaim_covenants
        df, today = self._make_klaim_tape()
        result = compute_klaim_covenants(df, mult=1, ref_date=today)
        par30 = next(c for c in result['covenants'] if c['name'].startswith('PAR30'))
        assert par30['method'] == 'age_pending'
        assert par30['confidence'] == 'B'
        assert par30['population'] == 'active_outstanding'

    def test_klaim_par60_is_confidence_B(self):
        from core.portfolio import compute_klaim_covenants
        df, today = self._make_klaim_tape()
        result = compute_klaim_covenants(df, mult=1, ref_date=today)
        par60 = next(c for c in result['covenants'] if c['name'].startswith('PAR60'))
        assert par60['confidence'] == 'B'

    def test_klaim_collection_ratio_is_confidence_C(self):
        # Cumulative (single-snapshot) approximation of a multi-snapshot definition.
        from core.portfolio import compute_klaim_covenants
        df, today = self._make_klaim_tape()
        result = compute_klaim_covenants(df, mult=1, ref_date=today)
        coll = next(c for c in result['covenants'] if 'Collection Ratio' in c['name'])
        assert coll['method'] == 'cumulative'
        assert coll['confidence'] == 'C'  # P0-5

    def test_klaim_wal_covenant_preserves_dual_confidence(self):
        # wal_active=A, wal_total=B (session 30), plus new top-level confidence=A
        from core.portfolio import compute_klaim_covenants
        df, today = self._make_klaim_tape()
        result = compute_klaim_covenants(df, mult=1, ref_date=today)
        wal = next(c for c in result['covenants'] if 'Weighted average life' in c['name'])
        assert wal['wal_active_confidence'] == 'A'
        assert wal['wal_total_confidence'] == 'B'
        assert wal['confidence'] == 'A'  # covenant decision uses wal_active
        assert wal['population'] == 'active_outstanding'
        assert wal['wal_active_population'] == 'active_outstanding'
        assert wal['wal_total_population'] == 'total_pv'

    def test_klaim_paid_vs_due_confidence_follows_method(self):
        # direct -> A; proxy -> B
        from core.analysis import method_to_confidence
        from core.portfolio import compute_klaim_covenants
        df, today = self._make_klaim_tape()
        result = compute_klaim_covenants(df, mult=1, ref_date=today)
        pvd = next(c for c in result['covenants'] if 'Paid vs Due' in c['name'])
        assert pvd['confidence'] == method_to_confidence(pvd['method'])


class TestP06KlaimConcentrationLimitsCarryConfidence:
    """Klaim concentration limits must carry confidence + population."""

    def _make_klaim_tape(self):
        return TestP06KlaimCovenantsCarryConfidence()._make_klaim_tape()

    def test_every_klaim_limit_has_confidence(self):
        from core.portfolio import compute_klaim_concentration_limits
        df, today = self._make_klaim_tape()
        result = compute_klaim_concentration_limits(df, mult=1, ref_date=today)
        for lim in result['limits']:
            assert 'confidence' in lim, f"Missing confidence on '{lim['name']}'"
            assert lim['confidence'] in {'A', 'B'}

    def test_every_klaim_limit_has_population_active_outstanding(self):
        from core.portfolio import compute_klaim_concentration_limits
        df, today = self._make_klaim_tape()
        result = compute_klaim_concentration_limits(df, mult=1, ref_date=today)
        for lim in result['limits']:
            assert lim['population'] == 'active_outstanding'

    def test_single_payer_limit_is_B_when_using_group_proxy(self):
        # Klaim tapes today have no Payer column — limit uses Group as proxy -> B
        from core.portfolio import compute_klaim_concentration_limits
        df, today = self._make_klaim_tape()
        result = compute_klaim_concentration_limits(df, mult=1, ref_date=today)
        payer = next(l for l in result['limits'] if 'Single payer' in l['name'])
        assert payer['confidence'] == 'B'
        assert payer['proxy_column'] == 'Group'


class TestP06SILQConcentrationLimitsCarryConfidence:
    def _make_tape(self):
        return TestP06SILQCovenantsCarryConfidence()._make_tape()

    def test_every_silq_limit_has_confidence(self):
        from core.portfolio import compute_concentration_limits
        df, today = self._make_tape()
        result = compute_concentration_limits(df, mult=1, ref_date=today)
        for lim in result['limits']:
            assert 'confidence' in lim, f"Missing confidence on '{lim['name']}'"
            assert lim['confidence'] == 'A'
            assert lim['population'] == 'active_outstanding'


# ══════════════════════════════════════════════════════════════════════════════
# P0-1 — SILQ covenant maturing-period denominator doctrine
# ══════════════════════════════════════════════════════════════════════════════


class TestP01SILQCollectionRatioIncludesClosedLoans:
    """The SILQ Collection Ratio covenant MUST include Closed-repaid-in-full
    loans in the denominator. Excluding them (filtering to active only) biases
    the metric toward delinquent-dominated months. Validated against Dec 2025
    cert — P0-1 resolution is documentation + regression guard, not code
    change."""

    def _make_tape_with_matured_closed(self, today):
        # 5 closed-repaid-in-full loans matured in prior month.
        prior_month = (today - pd.DateOffset(months=1)).replace(day=15)
        rows = []
        for i in range(5):
            rows.append({
                'Deal ID': f'C{i}', 'Shop_ID': f'S{i}',
                'Disbursed_Amount (SAR)': 100_000,
                'Outstanding_Amount (SAR)': 0,
                'Overdue_Amount (SAR)': 0,
                'Total_Collectable_Amount (SAR)': 110_000,
                'Amt_Repaid': 110_000, 'Margin Collected': 10_000,
                'Principal Collected': 100_000, 'Shop_Credit_Limit (SAR)': 500_000,
                'Tenure': 12, 'Loan_Status': 'Closed',
                'Product': 'BNPL',
                'Disbursement_Date': prior_month - pd.Timedelta(days=180),
                'Repayment_Deadline': prior_month,  # MATURED in prior month
                'Last_Collection_Date': prior_month,
                'Loan_Age': 180,
            })
        # 1 still-active-delinquent loan also matured in same prior month.
        rows.append({
            'Deal ID': 'D1', 'Shop_ID': 'S9',
            'Disbursed_Amount (SAR)': 100_000,
            'Outstanding_Amount (SAR)': 100_000,
            'Overdue_Amount (SAR)': 100_000,
            'Total_Collectable_Amount (SAR)': 110_000,
            'Amt_Repaid': 0, 'Margin Collected': 0, 'Principal Collected': 0,
            'Shop_Credit_Limit (SAR)': 500_000,
            'Tenure': 12, 'Loan_Status': 'Active',
            'Product': 'BNPL',
            'Disbursement_Date': prior_month - pd.Timedelta(days=180),
            'Repayment_Deadline': prior_month,
            'Last_Collection_Date': None, 'Loan_Age': 180,
        })
        return pd.DataFrame(rows)

    def test_closed_loans_contribute_to_coll_ratio_denominator(self):
        """If we excluded Closed loans, the ratio would be 0/110K=0%. With
        them included (correct per P0-1 doctrine), the ratio is
        550K/660K ≈ 83%."""
        from core.analysis_silq import compute_silq_covenants
        today = pd.Timestamp('2026-03-15')
        df = self._make_tape_with_matured_closed(today)
        result = compute_silq_covenants(df, mult=1, ref_date=today)
        coll = next(c for c in result['covenants'] if 'Collection Ratio' in c['name'])
        # 5 closed × 110K repaid + 1 delinquent × 0 = 550K repaid;
        # 5 closed × 110K collectable + 1 delinquent × 110K = 660K collectable.
        # Only one of the three measurement months has maturing loans, so
        # avg_collection = 550/660 ≈ 0.833.
        assert coll['current'] > 0.5, (
            f"Closed loans should contribute to denominator. Got {coll['current']!r}. "
            "If this is near 0, the filter was changed to exclude Closed — that's wrong per P0-1."
        )
        # And the population field documents the semantics.
        assert coll['population'] == 'specific_filter(maturing in period)'

    def test_portfolio_py_silq_coll_ratio_same_doctrine(self):
        """The memo-engine path (portfolio.py compute_covenants) uses the
        same filter — guard against one path diverging from the other."""
        from core.portfolio import compute_covenants
        today = pd.Timestamp('2026-03-15')
        df = self._make_tape_with_matured_closed(today)
        result = compute_covenants(df, mult=1, ref_date=today)
        coll = next(c for c in result['covenants'] if 'Collection Ratio' in c['name'])
        assert coll['current'] > 0.5
        assert coll['population'] == 'specific_filter(maturing in period)'


# ══════════════════════════════════════════════════════════════════════════════
# P0-2 — Aajil yield completed-only dual
# ══════════════════════════════════════════════════════════════════════════════


def _make_aajil_yield_tape():
    """5 realised + 3 accrued + 1 WO — yields diverge across populations."""
    today = pd.Timestamp('2026-04-15')
    rows = []
    # Realised: clean yield ~25%
    for i in range(5):
        rows.append({
            'Transaction ID': f'R{i}',
            'Deal Type': 'EMI', 'Invoice Date': today - pd.Timedelta(days=180),
            'Unique Customer Code': 100 + i,
            'Bill Notional': 100_000, 'Total Margin': 20_000,
            'Origination Fee': 5_000, 'Sale Notional': 125_000,
            'Sale VAT': 18_750, 'Sale Total': 143_750,
            'Realised Amount': 143_750, 'Receivable Amount': 0,
            'Written Off Amount': 0, 'Written Off VAT Recovered Amount': 0,
            'Write Off Date': None, 'Realised Status': 'Realised',
            'Total No. of Installments': 4, 'Due No of Installments': 4,
            'Paid No of Installments': 4, 'Overdue No of Installments': 0,
            'Sale Due Amount': 143_750, 'Sale Paid Amount': 143_750,
            'Sale Overdue Amount': 0, 'Monthly Yield %': 5.5,
            'Total Yield %': 25.0, 'Admin Fee %': 1.0,
            'Deal Tenure': 4.5, 'Customer Industry': 'Manufacturing',
            'Principal Amount': 100_000,
            'Expected Completion': today - pd.Timedelta(days=30),
        })
    # Active: mid-life, not yet closed; contractual yield ~22%
    for i in range(3):
        rows.append({
            'Transaction ID': f'A{i}',
            'Deal Type': 'EMI', 'Invoice Date': today - pd.Timedelta(days=60),
            'Unique Customer Code': 200 + i,
            'Bill Notional': 100_000, 'Total Margin': 22_000,
            'Origination Fee': 3_000, 'Sale Notional': 125_000,
            'Sale VAT': 18_750, 'Sale Total': 143_750,
            'Realised Amount': 50_000, 'Receivable Amount': 93_750,
            'Written Off Amount': 0, 'Written Off VAT Recovered Amount': 0,
            'Write Off Date': None, 'Realised Status': 'Accrued',
            'Total No. of Installments': 4, 'Due No of Installments': 2,
            'Paid No of Installments': 2, 'Overdue No of Installments': 0,
            'Sale Due Amount': 70_000, 'Sale Paid Amount': 50_000,
            'Sale Overdue Amount': 0, 'Monthly Yield %': 4.9,
            'Total Yield %': 22.0, 'Admin Fee %': 1.0,
            'Deal Tenure': 4.5, 'Customer Industry': 'Contracting',
            'Principal Amount': 100_000,
            'Expected Completion': today + pd.Timedelta(days=60),
        })
    # Written-off: realised yield 0
    rows.append({
        'Transaction ID': 'WO1', 'Deal Type': 'Bullet',
        'Invoice Date': today - pd.Timedelta(days=300),
        'Unique Customer Code': 999, 'Bill Notional': 100_000,
        'Total Margin': 20_000, 'Origination Fee': 5_000,
        'Sale Notional': 125_000, 'Sale VAT': 18_750,
        'Sale Total': 143_750, 'Realised Amount': 0,
        'Receivable Amount': 0, 'Written Off Amount': 143_750,
        'Written Off VAT Recovered Amount': 18_750,
        'Write Off Date': today - pd.Timedelta(days=30),
        'Realised Status': 'Written Off',
        'Total No. of Installments': 1, 'Due No of Installments': 1,
        'Paid No of Installments': 0, 'Overdue No of Installments': 1,
        'Sale Due Amount': 143_750, 'Sale Paid Amount': 0,
        'Sale Overdue Amount': 143_750, 'Monthly Yield %': 0.0,
        'Total Yield %': 0.0, 'Admin Fee %': 1.0,
        'Deal Tenure': 6, 'Customer Industry': 'Wholesale',
        'Principal Amount': 100_000,
        'Expected Completion': today - pd.Timedelta(days=150),
    })
    return pd.DataFrame(rows)


class TestP02AajilYieldDual:
    def test_avg_total_yield_realised_reports_completed_only(self):
        from core.analysis_aajil import compute_aajil_yield
        df = _make_aajil_yield_tape()
        res = compute_aajil_yield(df, mult=1)
        # 5 realised at 25%, 3 active at 22%, 1 WO at 0%.
        # Realised-only → 25.0; Active-only → 22.0; All → ~21.1
        assert res['avg_total_yield_realised'] == pytest.approx(25.0, abs=0.01)
        assert res['avg_total_yield_active']   == pytest.approx(22.0, abs=0.01)
        # Pre-existing mixed view — verifies WO drags it down
        assert res['avg_total_yield'] < res['avg_total_yield_realised']

    def test_realised_yield_confidence_is_A(self):
        from core.analysis_aajil import compute_aajil_yield
        df = _make_aajil_yield_tape()
        res = compute_aajil_yield(df, mult=1)
        assert res['yield_confidence']['avg_total_yield_realised'] == 'A'
        assert res['yield_confidence']['avg_total_yield_active']   == 'A'
        assert res['yield_confidence']['avg_total_yield']          == 'B'  # mixes WO

    def test_realised_and_active_counts_present(self):
        from core.analysis_aajil import compute_aajil_yield
        df = _make_aajil_yield_tape()
        res = compute_aajil_yield(df, mult=1)
        assert res['realised_yield_count'] == 5
        assert res['active_yield_count']   == 3

    def test_backward_compat_all_prior_fields_preserved(self):
        from core.analysis_aajil import compute_aajil_yield
        df = _make_aajil_yield_tape()
        res = compute_aajil_yield(df, mult=1)
        for field in (
            'total_margin', 'total_fees', 'total_revenue', 'revenue_over_gmv',
            'avg_total_yield', 'median_total_yield', 'avg_monthly_yield',
            'yield_distribution', 'by_deal_type', 'by_vintage', 'available',
        ):
            assert field in res, f"BC broken: '{field}' missing"

    def test_by_deal_type_adds_pv_weighted_margin_rate(self):
        """P2-3 cleanup — by_deal_type now carries PV-weighted margin rate."""
        from core.analysis_aajil import compute_aajil_yield
        df = _make_aajil_yield_tape()
        res = compute_aajil_yield(df, mult=1)
        for entry in res['by_deal_type']:
            assert 'margin_rate_pv_weighted' in entry
            assert entry['margin_rate_pv_weighted'] is not None


# ══════════════════════════════════════════════════════════════════════════════
# P1-1 — separate_portfolio() primitives for SILQ + Aajil
# ══════════════════════════════════════════════════════════════════════════════


class TestP11SeparateSilqPortfolio:
    """SILQ loss = Closed-with-outstanding OR active-DPD>90."""

    def _make_tape(self):
        today = pd.Timestamp('2026-03-01')
        rows = []
        # 3 clean active
        for i in range(3):
            rows.append({
                'Deal ID': f'A{i}', 'Shop_ID': f'S{i}',
                'Disbursed_Amount (SAR)': 100_000,
                'Outstanding_Amount (SAR)': 80_000,
                'Overdue_Amount (SAR)': 0,
                'Total_Collectable_Amount (SAR)': 110_000,
                'Amt_Repaid': 30_000, 'Margin Collected': 10_000,
                'Principal Collected': 20_000, 'Shop_Credit_Limit (SAR)': 500_000,
                'Tenure': 12, 'Loan_Status': 'Active', 'Product': 'BNPL',
                'Disbursement_Date': today - pd.Timedelta(days=30),
                'Repayment_Deadline': today + pd.Timedelta(days=60),
                'Last_Collection_Date': today, 'Loan_Age': 30,
            })
        # 2 closed-repaid (clean)
        for i in range(2):
            rows.append({
                'Deal ID': f'C{i}', 'Shop_ID': f'S{i}',
                'Disbursed_Amount (SAR)': 100_000,
                'Outstanding_Amount (SAR)': 0,  # cleanly closed
                'Overdue_Amount (SAR)': 0,
                'Total_Collectable_Amount (SAR)': 110_000,
                'Amt_Repaid': 110_000, 'Margin Collected': 10_000,
                'Principal Collected': 100_000, 'Shop_Credit_Limit (SAR)': 500_000,
                'Tenure': 12, 'Loan_Status': 'Closed', 'Product': 'BNPL',
                'Disbursement_Date': today - pd.Timedelta(days=300),
                'Repayment_Deadline': today - pd.Timedelta(days=60),
                'Last_Collection_Date': today - pd.Timedelta(days=30),
                'Loan_Age': 300,
            })
        # 1 closed with outstanding (charged off — LOSS)
        rows.append({
            'Deal ID': 'L1', 'Shop_ID': 'S9',
            'Disbursed_Amount (SAR)': 100_000,
            'Outstanding_Amount (SAR)': 90_000,  # outstanding despite closed
            'Overdue_Amount (SAR)': 90_000,
            'Total_Collectable_Amount (SAR)': 110_000,
            'Amt_Repaid': 20_000, 'Margin Collected': 0,
            'Principal Collected': 20_000, 'Shop_Credit_Limit (SAR)': 500_000,
            'Tenure': 12, 'Loan_Status': 'Closed', 'Product': 'BNPL',
            'Disbursement_Date': today - pd.Timedelta(days=300),
            'Repayment_Deadline': today - pd.Timedelta(days=60),
            'Last_Collection_Date': today - pd.Timedelta(days=200),
            'Loan_Age': 300,
        })
        # 1 active DPD > 90 (delinquent — LOSS)
        rows.append({
            'Deal ID': 'L2', 'Shop_ID': 'S10',
            'Disbursed_Amount (SAR)': 100_000,
            'Outstanding_Amount (SAR)': 100_000,
            'Overdue_Amount (SAR)': 100_000,
            'Total_Collectable_Amount (SAR)': 110_000,
            'Amt_Repaid': 0, 'Margin Collected': 0, 'Principal Collected': 0,
            'Shop_Credit_Limit (SAR)': 500_000,
            'Tenure': 12, 'Loan_Status': 'Active', 'Product': 'BNPL',
            'Disbursement_Date': today - pd.Timedelta(days=200),
            'Repayment_Deadline': today - pd.Timedelta(days=120),  # DPD 120
            'Last_Collection_Date': None, 'Loan_Age': 200,
        })
        return pd.DataFrame(rows), today

    def test_loss_classification_two_deals(self):
        from core.analysis_silq import separate_silq_portfolio
        df, today = self._make_tape()
        clean, loss = separate_silq_portfolio(df, ref_date=today)
        assert len(loss) == 2  # closed-with-outstanding + active-DPD>90
        assert set(loss['Deal ID']) == {'L1', 'L2'}

    def test_clean_includes_closed_repaid(self):
        from core.analysis_silq import separate_silq_portfolio
        df, today = self._make_tape()
        clean, loss = separate_silq_portfolio(df, ref_date=today)
        # Closed loans with outstanding == 0 are CLEAN (repaid, no loss)
        assert len(clean) == 5
        assert {'C0', 'C1'} <= set(clean['Deal ID'])

    def test_partition_preserves_all_rows(self):
        from core.analysis_silq import separate_silq_portfolio
        df, today = self._make_tape()
        clean, loss = separate_silq_portfolio(df, ref_date=today)
        assert len(clean) + len(loss) == len(df)

    def test_returns_copies_not_views(self):
        from core.analysis_silq import separate_silq_portfolio
        df, today = self._make_tape()
        clean, loss = separate_silq_portfolio(df, ref_date=today)
        clean.loc[clean.index[0], 'Deal ID'] = 'MUTATED'
        assert df.loc[clean.index[0], 'Deal ID'] != 'MUTATED'


class TestP11SeparateAajilPortfolio:
    """Aajil loss = Status == 'Written Off'. Direct, unambiguous."""

    def test_loss_subset_is_written_off_only(self):
        from core.analysis_aajil import separate_aajil_portfolio
        df = _make_aajil_yield_tape()  # 5 realised + 3 accrued + 1 WO
        clean, loss = separate_aajil_portfolio(df)
        assert len(loss) == 1
        assert (loss['Realised Status'] == 'Written Off').all()

    def test_clean_includes_realised_and_accrued(self):
        from core.analysis_aajil import separate_aajil_portfolio
        df = _make_aajil_yield_tape()
        clean, loss = separate_aajil_portfolio(df)
        assert len(clean) == 8
        statuses = set(clean['Realised Status'].unique())
        assert statuses == {'Realised', 'Accrued'}

    def test_partition_preserves_all_rows(self):
        from core.analysis_aajil import separate_aajil_portfolio
        df = _make_aajil_yield_tape()
        clean, loss = separate_aajil_portfolio(df)
        assert len(clean) + len(loss) == len(df)

    def test_returns_copies_not_views(self):
        from core.analysis_aajil import separate_aajil_portfolio
        df = _make_aajil_yield_tape()
        clean, loss = separate_aajil_portfolio(df)
        clean.loc[clean.index[0], 'Transaction ID'] = 'MUTATED'
        assert df.loc[clean.index[0], 'Transaction ID'] != 'MUTATED'


# ══════════════════════════════════════════════════════════════════════════════
# P0-3 + P1-5 — Aajil PAR relabel + lifetime dual
# ══════════════════════════════════════════════════════════════════════════════


def _make_aajil_delinquency_tape():
    today = pd.Timestamp('2026-04-15')
    rows = []
    # 10 active current (overdue=0), 5 one-inst overdue, 2 three-plus overdue.
    for i in range(10):
        rows.append({
            'Transaction ID': f'A{i}', 'Deal Type': 'EMI',
            'Invoice Date': today - pd.Timedelta(days=60),
            'Unique Customer Code': 100 + i,
            'Bill Notional': 100_000, 'Total Margin': 20_000,
            'Origination Fee': 5_000, 'Sale Notional': 125_000,
            'Sale VAT': 18_750, 'Sale Total': 143_750,
            'Realised Amount': 50_000, 'Receivable Amount': 93_750,
            'Written Off Amount': 0, 'Written Off VAT Recovered Amount': 0,
            'Write Off Date': None, 'Realised Status': 'Accrued',
            'Total No. of Installments': 4, 'Due No of Installments': 2,
            'Paid No of Installments': 2, 'Overdue No of Installments': 0,
            'Sale Due Amount': 70_000, 'Sale Paid Amount': 50_000,
            'Sale Overdue Amount': 0, 'Monthly Yield %': 5.0,
            'Total Yield %': 22.0, 'Admin Fee %': 1.0, 'Deal Tenure': 4.5,
            'Customer Industry': 'Manufacturing', 'Principal Amount': 100_000,
            'Expected Completion': today + pd.Timedelta(days=60),
        })
    for i in range(5):
        rows.append({
            'Transaction ID': f'B{i}', 'Deal Type': 'EMI',
            'Invoice Date': today - pd.Timedelta(days=90),
            'Unique Customer Code': 200 + i,
            'Bill Notional': 100_000, 'Total Margin': 20_000,
            'Origination Fee': 5_000, 'Sale Notional': 125_000,
            'Sale VAT': 18_750, 'Sale Total': 143_750,
            'Realised Amount': 30_000, 'Receivable Amount': 113_750,
            'Written Off Amount': 0, 'Written Off VAT Recovered Amount': 0,
            'Write Off Date': None, 'Realised Status': 'Accrued',
            'Total No. of Installments': 4, 'Due No of Installments': 2,
            'Paid No of Installments': 1, 'Overdue No of Installments': 1,
            'Sale Due Amount': 70_000, 'Sale Paid Amount': 30_000,
            'Sale Overdue Amount': 40_000, 'Monthly Yield %': 5.0,
            'Total Yield %': 22.0, 'Admin Fee %': 1.0, 'Deal Tenure': 4.5,
            'Customer Industry': 'Contracting', 'Principal Amount': 100_000,
            'Expected Completion': today + pd.Timedelta(days=30),
        })
    for i in range(2):
        rows.append({
            'Transaction ID': f'C{i}', 'Deal Type': 'Bullet',
            'Invoice Date': today - pd.Timedelta(days=180),
            'Unique Customer Code': 300 + i,
            'Bill Notional': 100_000, 'Total Margin': 20_000,
            'Origination Fee': 5_000, 'Sale Notional': 125_000,
            'Sale VAT': 18_750, 'Sale Total': 143_750,
            'Realised Amount': 0, 'Receivable Amount': 143_750,
            'Written Off Amount': 0, 'Written Off VAT Recovered Amount': 0,
            'Write Off Date': None, 'Realised Status': 'Accrued',
            'Total No. of Installments': 3, 'Due No of Installments': 3,
            'Paid No of Installments': 0, 'Overdue No of Installments': 3,
            'Sale Due Amount': 143_750, 'Sale Paid Amount': 0,
            'Sale Overdue Amount': 143_750, 'Monthly Yield %': 5.0,
            'Total Yield %': 22.0, 'Admin Fee %': 1.0, 'Deal Tenure': 6,
            'Customer Industry': 'Wholesale', 'Principal Amount': 100_000,
            'Expected Completion': today - pd.Timedelta(days=60),
        })
    # Plus 3 realised (closed successfully) to exercise lifetime denom
    for i in range(3):
        rows.append({
            'Transaction ID': f'R{i}', 'Deal Type': 'EMI',
            'Invoice Date': today - pd.Timedelta(days=300),
            'Unique Customer Code': 400 + i,
            'Bill Notional': 100_000, 'Total Margin': 20_000,
            'Origination Fee': 5_000, 'Sale Notional': 125_000,
            'Sale VAT': 18_750, 'Sale Total': 143_750,
            'Realised Amount': 143_750, 'Receivable Amount': 0,
            'Written Off Amount': 0, 'Written Off VAT Recovered Amount': 0,
            'Write Off Date': None, 'Realised Status': 'Realised',
            'Total No. of Installments': 4, 'Due No of Installments': 4,
            'Paid No of Installments': 4, 'Overdue No of Installments': 0,
            'Sale Due Amount': 143_750, 'Sale Paid Amount': 143_750,
            'Sale Overdue Amount': 0, 'Monthly Yield %': 5.5,
            'Total Yield %': 25.0, 'Admin Fee %': 1.0, 'Deal Tenure': 4.5,
            'Customer Industry': 'Manufacturing', 'Principal Amount': 100_000,
            'Expected Completion': today - pd.Timedelta(days=120),
        })
    return pd.DataFrame(rows)


class TestP03AajilPARMeasurementSemantics:
    def test_par_measurement_field_declares_install_count(self):
        from core.analysis_aajil import compute_aajil_delinquency
        df = _make_aajil_delinquency_tape()
        res = compute_aajil_delinquency(df, mult=1)
        assert res['par_measurement'] == 'installments_overdue'
        assert 'not contractual DPD days' in res['par_measurement_note'].lower() or \
               'not contractual dpd' in res['par_measurement_note'].lower()

    def test_par_confidence_is_B(self):
        from core.analysis_aajil import compute_aajil_delinquency
        df = _make_aajil_delinquency_tape()
        res = compute_aajil_delinquency(df, mult=1)
        assert res['par_confidence'] == 'B'

    def test_par_population_fields_declare_active_and_lifetime(self):
        from core.analysis_aajil import compute_aajil_delinquency
        df = _make_aajil_delinquency_tape()
        res = compute_aajil_delinquency(df, mult=1)
        assert res['par_population_active']   == 'active_outstanding'
        assert res['par_population_lifetime'] == 'total_originated'


class TestP15AajilPARLifetimeDual:
    def test_lifetime_denominator_is_total_originated(self):
        from core.analysis_aajil import compute_aajil_delinquency
        df = _make_aajil_delinquency_tape()
        res = compute_aajil_delinquency(df, mult=1)
        # 20 deals × 100K principal = 2M originated.
        # Active denom = 17 active × receivable amounts; smaller than originated.
        # So lifetime PAR < active PAR (for same overdue set).
        assert res['total_originated_principal'] == pytest.approx(2_000_000, abs=1)
        assert res['par_1_inst'] > 0
        # Active denom (receivables) is smaller than originated (principal),
        # so active-denominator PAR rate > lifetime PAR rate.
        assert res['par_1_inst'] > res['par_1_inst_lifetime']

    def test_lifetime_par_same_numerator_different_denom(self):
        from core.analysis_aajil import compute_aajil_delinquency
        df = _make_aajil_delinquency_tape()
        res = compute_aajil_delinquency(df, mult=1)
        # par_1_inst * total_active_balance == par_1_inst_lifetime * total_originated
        # Tolerance looser than default because _safe() rounds ratios to 4dp,
        # which translates to thousands of SAR of rounding error when multiplied
        # back out by multi-million denominators.
        active_numer   = res['par_1_inst']          * res['total_active_balance']
        lifetime_numer = res['par_1_inst_lifetime'] * res['total_originated_principal']
        assert active_numer == pytest.approx(lifetime_numer, rel=1e-3)


class TestP03AajilPARPrimarySurfacesWhenAuxPresent:
    def test_par_primary_none_when_aux_missing(self):
        from core.analysis_aajil import compute_aajil_delinquency
        df = _make_aajil_delinquency_tape()
        res = compute_aajil_delinquency(df, mult=1, aux=None)
        assert res['par_primary'] is None

    def test_par_primary_populated_when_aux_has_cohorts(self):
        """When aux['dpd_cohorts'] is present with a valid monthly layout,
        par_primary surfaces with Confidence A + measurement='days_past_due'."""
        from core.analysis_aajil import compute_aajil_delinquency
        df = _make_aajil_delinquency_tape()
        # Build a minimal aux DPD cohort sheet matching _parse_dpd_monthly's layout.
        # Needs shape[1] >= 10; row 0 has dates in cols 8+; rows 2,4,5,7,8,10,11
        # carry deployed / DPD amounts and percentages.
        data = [[None] * 12 for _ in range(15)]
        data[0][8]  = pd.Timestamp('2026-03-01')
        data[0][9]  = pd.Timestamp('2026-04-01')
        data[2][8]  = 1_000_000; data[2][9]  = 1_200_000
        data[4][8]  = 50_000;    data[4][9]  = 70_000       # DPD30+ amt
        data[5][8]  = 0.05;      data[5][9]  = 0.058        # DPD30+ %
        data[7][8]  = 20_000;    data[7][9]  = 30_000       # DPD60+ amt
        data[8][8]  = 0.02;      data[8][9]  = 0.025        # DPD60+ %
        data[10][8] = 10_000;    data[10][9] = 12_000       # DPD90+ amt
        data[11][8] = 0.01;      data[11][9] = 0.01         # DPD90+ %
        aux = {'dpd_cohorts': pd.DataFrame(data)}
        res = compute_aajil_delinquency(df, mult=1, aux=aux)
        assert res['par_primary'] is not None
        assert res['par_primary']['confidence'] == 'A'
        assert res['par_primary']['measurement'] == 'days_past_due'
        assert res['par_primary']['as_of'] == '2026-04'


class TestP01KlaimCollRatioDifferentDefinition:
    """Klaim's Collection Ratio is a CUMULATIVE approximation (method=
    'cumulative', Confidence C), not the same 'maturing in period' covenant
    that SILQ implements. The audit's P0-1 flagged them as asymmetric; the
    resolution is that they measure different things. This test locks in
    the distinction."""

    def test_klaim_coll_ratio_method_is_cumulative(self):
        from core.portfolio import compute_klaim_covenants
        today = pd.Timestamp('2026-04-15')
        df = TestP06KlaimCovenantsCarryConfidence()._make_klaim_tape()[0]
        result = compute_klaim_covenants(df, mult=1, ref_date=today)
        coll = next(c for c in result['covenants'] if 'Collection Ratio' in c['name'])
        assert coll['method'] == 'cumulative'
        assert coll['confidence'] == 'C'

    def test_silq_coll_ratio_method_is_direct(self):
        from core.analysis_silq import compute_silq_covenants
        df, today = TestP06SILQCovenantsCarryConfidence()._make_tape()
        result = compute_silq_covenants(df, mult=1, ref_date=today)
        coll = next(c for c in result['covenants'] if 'Collection Ratio' in c['name'])
        assert coll['method'] == 'direct'
        assert coll['confidence'] == 'A'
