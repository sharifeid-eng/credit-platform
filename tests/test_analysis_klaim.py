"""
Tests for core/analysis.py — Klaim healthcare claims factoring analytics.

Uses real Klaim tape data (Mar 2026 tape — 60 columns) for integration-level tests.
"""
import sys, os
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.analysis import (
    filter_by_date, add_month_column, apply_multiplier, fmt_m,
    classify_health,
    compute_summary, compute_deployment, compute_deployment_by_product,
    compute_collection_velocity, compute_denial_trend, compute_cohorts,
    compute_actual_vs_expected, compute_ageing, compute_revenue,
    compute_concentration, compute_returns_analysis, compute_dso,
    compute_hhi, compute_denial_funnel, compute_stress_test,
    compute_expected_loss, compute_loss_triangle, compute_group_performance,
    compute_collection_curves, compute_owner_breakdown, compute_vat_summary,
    compute_par,
)
from core.loader import load_snapshot
from core.config import load_config

# ── Fixtures ──────────────────────────────────────────────────────────────────

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'klaim', 'UAE_healthcare')

def _find_latest_tape():
    """Find the latest tape file (by date prefix)."""
    files = sorted([f for f in os.listdir(DATA_DIR) if f.endswith(('.csv', '.xlsx'))])
    return os.path.join(DATA_DIR, files[-1]) if files else None

@pytest.fixture(scope='module')
def full_df():
    path = _find_latest_tape()
    assert path is not None, "No Klaim tape found"
    return load_snapshot(path)

@pytest.fixture(scope='module')
def config():
    return load_config('klaim', 'UAE_healthcare') or {'currency': 'AED', 'usd_rate': 0.2723}


# ── Helper tests ──────────────────────────────────────────────────────────────

class TestHelpers:
    def test_fmt_m_millions(self):
        assert fmt_m(5_000_000) == '5.0M'

    def test_fmt_m_thousands(self):
        assert fmt_m(500_000) == '500K'

    def test_fmt_m_small(self):
        assert fmt_m(500) == '500'

    def test_apply_multiplier_local(self, config):
        mult = apply_multiplier(config, config['currency'])
        assert mult == 1.0

    def test_apply_multiplier_usd(self, config):
        mult = apply_multiplier(config, 'USD')
        assert mult == pytest.approx(config['usd_rate'], rel=0.01)

    def test_filter_by_date_none(self, full_df):
        result = filter_by_date(full_df, None)
        assert len(result) == len(full_df)

    def test_filter_by_date_cutoff(self, full_df):
        result = filter_by_date(full_df, '2025-12-31')
        assert len(result) < len(full_df)
        assert all(result['Deal date'] <= pd.Timestamp('2025-12-31'))

    def test_add_month_column(self, full_df):
        df = add_month_column(full_df.copy())
        assert 'Month' in df.columns


# ── Summary tests ─────────────────────────────────────────────────────────────

class TestSummary:
    def test_total_deals(self, full_df, config):
        result = compute_summary(full_df, config, 'AED', '2026-03-03', None)
        assert result['total_deals'] == len(full_df)

    def test_collection_rate_bounded(self, full_df, config):
        result = compute_summary(full_df, config, 'AED', '2026-03-03', None)
        assert 0 <= result['collection_rate'] <= 100

    def test_rates_sum_roughly(self, full_df, config):
        """Collection + denial + pending should roughly sum to ~100%."""
        result = compute_summary(full_df, config, 'AED', '2026-03-03', None)
        total = result['collection_rate'] + result['denial_rate'] + result['pending_rate']
        # Allow some tolerance for rounding / partial collections
        assert 90 < total < 110

    def test_active_plus_completed(self, full_df, config):
        result = compute_summary(full_df, config, 'AED', '2026-03-03', None)
        # Active + completed <= total (may have Pending status deals)
        assert result['active_deals'] + result['completed_deals'] <= result['total_deals']
        assert result['active_deals'] + result['completed_deals'] >= result['total_deals'] - 10  # small margin for other statuses

    def test_json_serializable(self, full_df, config):
        import json
        result = compute_summary(full_df, config, 'AED', '2026-03-03', None)
        json.dumps(result, default=str)  # Should not raise


# ── Deployment tests ──────────────────────────────────────────────────────────

class TestDeployment:
    def test_monthly_data(self, full_df):
        result = compute_deployment(full_df, 1)
        assert len(result) > 0
        assert all('Month' in r for r in result)
        assert all('purchase_value' in r for r in result)

    def test_deployment_by_product(self, full_df):
        result = compute_deployment_by_product(full_df, 1)
        assert 'monthly' in result
        assert 'products' in result
        assert len(result['monthly']) > 0


# ── Collection velocity tests ─────────────────────────────────────────────────

class TestCollectionVelocity:
    def test_monthly_rates(self, full_df):
        result = compute_collection_velocity(full_df, 1)
        assert 'monthly' in result
        assert len(result['monthly']) > 0

    def test_buckets_exist(self, full_df):
        result = compute_collection_velocity(full_df, 1)
        assert 'buckets' in result

    def test_avg_days_positive(self, full_df):
        result = compute_collection_velocity(full_df, 1)
        if result['total_completed'] > 0:
            assert result['avg_days'] > 0


# ── Denial trend tests ───────────────────────────────────────────────────────

class TestDenialTrend:
    def test_monthly_data(self, full_df):
        result = compute_denial_trend(full_df, 1)
        assert len(result) > 0
        assert all('denial_rate' in r for r in result)

    def test_denial_rate_bounded(self, full_df):
        result = compute_denial_trend(full_df, 1)
        for r in result:
            assert 0 <= r['denial_rate'] <= 100


# ── Cohort tests ──────────────────────────────────────────────────────────────

class TestCohorts:
    def test_has_vintages(self, full_df):
        result = compute_cohorts(full_df, 1)
        assert len(result) > 0
        assert all('month' in c for c in result)

    def test_vintages_sorted(self, full_df):
        result = compute_cohorts(full_df, 1)
        months = [c['month'] for c in result]
        assert months == sorted(months)

    def test_collection_rate_bounded(self, full_df):
        result = compute_cohorts(full_df, 1)
        for c in result:
            assert 0 <= c['collection_rate'] <= 200


# ── Ageing tests ──────────────────────────────────────────────────────────────

class TestAgeing:
    def test_health_summary(self, full_df):
        result = compute_ageing(full_df, 1)
        assert 'health_summary' in result
        assert len(result['health_summary']) > 0

    def test_outstanding_not_face_value(self, full_df):
        """Ageing should use outstanding (PV - Collected - Denied), not face value."""
        result = compute_ageing(full_df, 1)
        assert result['total_outstanding'] < result['total_active_value']


# ── Revenue tests ─────────────────────────────────────────────────────────────

class TestRevenue:
    def test_monthly_data(self, full_df):
        result = compute_revenue(full_df, 1)
        assert 'monthly' in result
        assert 'totals' in result
        assert len(result['monthly']) > 0

    def test_gross_margin_bounded(self, full_df):
        result = compute_revenue(full_df, 1)
        assert -100 <= result['totals']['gross_margin'] <= 100


# ── Concentration tests ───────────────────────────────────────────────────────

class TestConcentration:
    def test_group_data(self, full_df):
        result = compute_concentration(full_df, 1)
        assert 'group' in result
        assert len(result['group']) > 0

    def test_top_deals(self, full_df):
        result = compute_concentration(full_df, 1)
        assert 'top_deals' in result
        assert len(result['top_deals']) <= 10


# ── Returns analysis tests ────────────────────────────────────────────────────

class TestReturns:
    def test_summary_keys(self, full_df):
        result = compute_returns_analysis(full_df, 1)
        assert 'summary' in result
        assert 'capital_recovery' in result['summary']

    def test_completed_only_margins(self, full_df):
        """Margins should be calculated on completed deals only."""
        result = compute_returns_analysis(full_df, 1)
        # Capital recovery should be a meaningful percentage
        assert 80 < result['summary']['capital_recovery'] < 110


# ── HHI tests ─────────────────────────────────────────────────────────────────

class TestHHI:
    def test_hhi_bounded(self, full_df):
        result = compute_hhi(full_df, 1)
        assert 0 < result['group']['hhi'] < 1
        assert 0 < result['product']['hhi'] <= 1


# ── Denial funnel tests ──────────────────────────────────────────────────────

class TestDenialFunnel:
    def test_stages(self, full_df):
        result = compute_denial_funnel(full_df, 1)
        assert 'stages' in result
        assert len(result['stages']) > 0

    def test_recovery_rate(self, full_df):
        result = compute_denial_funnel(full_df, 1)
        assert 0 <= result['recovery_rate'] <= 100


# ── Stress test ───────────────────────────────────────────────────────────────

class TestStressTest:
    def test_scenarios(self, full_df):
        result = compute_stress_test(full_df, 1)
        assert 'scenarios' in result
        assert len(result['scenarios']) > 0

    def test_base_collection_rate(self, full_df):
        result = compute_stress_test(full_df, 1)
        assert 0 < result['base_collection_rate'] < 100


# ── Expected loss tests ──────────────────────────────────────────────────────

class TestExpectedLoss:
    def test_portfolio_el(self, full_df):
        result = compute_expected_loss(full_df, 1)
        assert 'portfolio' in result
        assert 'pd' in result['portfolio']
        assert 'lgd' in result['portfolio']
        assert 'el_rate' in result['portfolio']

    def test_el_rate_bounded(self, full_df):
        result = compute_expected_loss(full_df, 1)
        assert 0 <= result['portfolio']['el_rate'] <= 100


# ── Group performance tests ───────────────────────────────────────────────────

class TestGroupPerformance:
    def test_groups_exist(self, full_df):
        result = compute_group_performance(full_df, 1)
        assert 'groups' in result
        assert len(result['groups']) > 0

    def test_groups_sorted_by_size(self, full_df):
        result = compute_group_performance(full_df, 1)
        values = [g['purchase_value'] for g in result['groups']]
        assert values == sorted(values, reverse=True)


# ── Actual vs Expected tests ─────────────────────────────────────────────────

class TestActualVsExpected:
    def test_data_structure(self, full_df):
        result = compute_actual_vs_expected(full_df, 1)
        assert 'data' in result
        assert len(result['data']) > 0
        row = result['data'][0]
        assert 'Month' in row
        assert 'cumulative_collected' in row
        assert 'cumulative_expected' in row

    def test_cumulative_increases(self, full_df):
        result = compute_actual_vs_expected(full_df, 1)
        collected = [m['cumulative_collected'] for m in result['data']]
        # Cumulative should be non-decreasing
        for i in range(1, len(collected)):
            assert collected[i] >= collected[i-1]

    def test_overall_performance(self, full_df):
        result = compute_actual_vs_expected(full_df, 1)
        assert 'overall_performance' in result
        assert result['overall_performance'] > 0


# ── Deployment by Product tests ──────────────────────────────────────────────

class TestDeploymentByProduct:
    def test_has_monthly_and_products(self, full_df):
        result = compute_deployment_by_product(full_df, 1)
        assert 'monthly' in result
        assert 'products' in result
        assert len(result['monthly']) > 0
        assert len(result['products']) > 0

    def test_monthly_has_product_keys(self, full_df):
        result = compute_deployment_by_product(full_df, 1)
        products = result['products']
        row = result['monthly'][0]
        assert 'Month' in row
        for p in products:
            assert p in row


# ── classify_health tests ────────────────────────────────────────────────────

class TestClassifyHealth:
    def test_healthy(self):
        assert classify_health(0) == 'Healthy'
        assert classify_health(30) == 'Healthy'
        assert classify_health(60) == 'Healthy'

    def test_watch(self):
        assert classify_health(61) == 'Watch'
        assert classify_health(90) == 'Watch'

    def test_delayed(self):
        assert classify_health(91) == 'Delayed'
        assert classify_health(120) == 'Delayed'

    def test_poor(self):
        assert classify_health(121) == 'Poor'
        assert classify_health(365) == 'Poor'

    def test_unknown(self):
        assert classify_health(np.nan) == 'Unknown'


# ── DSO tests ────────────────────────────────────────────────────────────────

class TestDSO:
    def test_available_flag(self, full_df):
        result = compute_dso(full_df, 1)
        assert 'available' in result
        # Mar 2026 tape has curve columns → should be available
        if result['available']:
            assert result['weighted_dso'] > 0
            assert result['median_dso'] > 0
            assert result['p95_dso'] > 0
            assert result['p95_dso'] >= result['median_dso']

    def test_by_vintage(self, full_df):
        result = compute_dso(full_df, 1)
        if result['available']:
            assert 'by_vintage' in result
            assert len(result['by_vintage']) > 0
            v = result['by_vintage'][0]
            assert 'month' in v
            assert 'median_dso' in v


# ── Loss Triangle tests ─────────────────────────────────────────────────────

class TestLossTriangle:
    def test_triangle_returned(self, full_df):
        result = compute_loss_triangle(full_df, 1)
        assert 'triangle' in result
        assert len(result['triangle']) > 0

    def test_triangle_structure(self, full_df):
        result = compute_loss_triangle(full_df, 1)
        v = result['triangle'][0]
        assert 'denial_rate' in v
        assert 'deal_count' in v
        assert 'avg_age_months' in v

    def test_values_non_negative(self, full_df):
        result = compute_loss_triangle(full_df, 1)
        for v in result['triangle']:
            for key, val in v.items():
                if key != 'month' and isinstance(val, (int, float)):
                    assert val >= 0, f"Negative value {val} for {key} in {v['month']}"


# ── Collection Curves tests ──────────────────────────────────────────────────

class TestCollectionCurves:
    def test_available_flag(self, full_df):
        result = compute_collection_curves(full_df, 1)
        assert 'available' in result

    def test_curves_structure(self, full_df):
        result = compute_collection_curves(full_df, 1)
        if result['available']:
            assert 'curves' in result
            assert len(result['curves']) > 0
            curve = result['curves'][0]
            assert 'month' in curve
            assert 'points' in curve
            assert len(curve['points']) > 0


# ── Owner Breakdown tests ────────────────────────────────────────────────────

class TestOwnerBreakdown:
    def test_available_flag(self, full_df):
        result = compute_owner_breakdown(full_df, 1)
        assert 'available' in result

    def test_owners_when_available(self, full_df):
        result = compute_owner_breakdown(full_df, 1)
        if result['available']:
            assert 'owners' in result
            assert len(result['owners']) > 0
            owner = result['owners'][0]
            assert 'owner' in owner
            assert 'purchase_value' in owner


# ── VAT Summary tests ────────────────────────────────────────────────────────

class TestVatSummary:
    def test_available_flag(self, full_df):
        result = compute_vat_summary(full_df, 1)
        assert 'available' in result

    def test_values_when_available(self, full_df):
        result = compute_vat_summary(full_df, 1)
        if result['available']:
            assert isinstance(result['vat_assets'], (int, float))
            assert isinstance(result['vat_fees'], (int, float))
            assert isinstance(result['total_vat'], (int, float))
            assert result['total_vat'] == pytest.approx(
                result['vat_assets'] + result['vat_fees'], rel=0.01
            )


# ── PAR Dual Perspective tests ──────────────────────────────────────────────

class TestPAR:
    def test_available(self, full_df):
        result = compute_par(full_df, 1)
        assert 'available' in result

    def test_dual_perspective_keys(self, full_df):
        result = compute_par(full_df, 1)
        if result['available']:
            # Active perspective keys
            assert 'par30' in result
            assert 'par60' in result
            assert 'par90' in result
            # Lifetime perspective keys
            assert 'lifetime_par30' in result
            assert 'lifetime_par60' in result
            assert 'lifetime_par90' in result
            assert 'total_originated' in result
            assert 'total_deal_count' in result

    def test_lifetime_leq_active(self, full_df):
        """Lifetime PAR should always be <= active PAR (larger denominator)."""
        result = compute_par(full_df, 1)
        if result['available']:
            assert result['lifetime_par30'] <= result['par30'] + 0.001
            assert result['lifetime_par60'] <= result['par60'] + 0.001
            assert result['lifetime_par90'] <= result['par90'] + 0.001

    def test_lifetime_denominator_is_total(self, full_df):
        """Lifetime denominator should equal total purchase value of all deals."""
        result = compute_par(full_df, 1)
        if result['available']:
            total_pv = float(full_df['Purchase value'].sum())
            assert result['total_originated'] == pytest.approx(total_pv, rel=0.01)
            assert result['total_deal_count'] == len(full_df)

    def test_active_denominator_is_outstanding(self, full_df):
        """Active denominator should equal outstanding of Executed deals only."""
        result = compute_par(full_df, 1)
        if result['available']:
            active = full_df[full_df['Status'] == 'Executed']
            outstanding = (
                active['Purchase value'] - active['Collected till date'] -
                active.get('Denied by insurance', pd.Series(0, index=active.index))
            ).clip(lower=0).sum()
            assert result['total_active_outstanding'] == pytest.approx(outstanding, rel=0.01)
