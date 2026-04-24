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
