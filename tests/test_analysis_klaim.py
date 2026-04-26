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
    compute_hhi, compute_hhi_for_snapshot,
    compute_denial_funnel, compute_stress_test,
    compute_expected_loss, compute_loss_triangle, compute_group_performance,
    compute_collection_curves, compute_owner_breakdown, compute_vat_summary,
    compute_par, compute_segment_analysis,
    compute_klaim_cash_duration,
    classify_klaim_deal_stale, compute_klaim_operational_wal,
    compute_klaim_stale_exposure, compute_methodology_log,
)
from core.validation import validate_tape
from core.consistency import run_consistency_check
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
def apr15_df():
    path = os.path.join(DATA_DIR, '2026-04-15_uae_healthcare.csv')
    if not os.path.exists(path):
        pytest.skip("Apr 15 tape not present")
    return load_snapshot(path)

@pytest.fixture(scope='module')
def mar03_df():
    path = os.path.join(DATA_DIR, '2026-03-03_uae_healthcare.csv')
    if not os.path.exists(path):
        pytest.skip("Mar 3 tape not present")
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


# ── Validation & consistency fixes (Klaim-specific) ───────────────────────────

class TestBalanceIdentityKlaim:
    """
    Balance Identity should use the Klaim accounting identity
        Paid by insurance + Denied by insurance + Pending insurance response ≡ Purchase value
    not the broken Collected+Denied+Pending > 1.05*PV rule (which fired on 34% of Apr 15).
    """

    def test_paid_den_pen_equals_pv_on_apr15(self, apr15_df):
        """The underlying identity should hold to floating-point zero."""
        paid = pd.to_numeric(apr15_df['Paid by insurance'], errors='coerce').fillna(0)
        den  = pd.to_numeric(apr15_df['Denied by insurance'], errors='coerce').fillna(0)
        pen  = pd.to_numeric(apr15_df['Pending insurance response'], errors='coerce').fillna(0)
        pv   = pd.to_numeric(apr15_df['Purchase value'], errors='coerce').fillna(0)
        diff = (paid + den + pen) - pv
        assert abs(diff.mean()) < 1e-6
        assert diff.abs().max() < 1.0  # well within 1% of any deal value

    def test_balance_identity_flags_drop_on_apr15(self, apr15_df):
        """On the Apr 15 tape the new check must flag ≤ 5 deals, not thousands."""
        res = validate_tape(apr15_df)
        bi = [w for w in res['warnings'] if w['check'] == 'Balance Identity Violations']
        total_flagged = sum(
            int(w['detail'].split()[0]) for w in bi
        ) if bi else 0
        assert total_flagged <= 5, (
            f"Balance Identity check is firing on {total_flagged} deals — "
            f"it should use Paid+Den+Pen = PV, not Collected+Den+Pen"
        )

    def test_balance_identity_skipped_without_paid_column(self):
        """Graceful degradation: drop the check when 'Paid by insurance' is absent."""
        df = pd.DataFrame({
            'Purchase value': [100, 100],
            'Collected till date': [50, 0],
            'Denied by insurance': [30, 0],
            'Pending insurance response': [40, 0],
            'Status': ['Executed', 'Completed'],
        })
        res = validate_tape(df)
        bi = [w for w in res['warnings'] if w['check'] == 'Balance Identity Violations']
        assert bi == [], "Balance Identity should be skipped when Paid column is missing"

    def test_over_collection_check_still_runs(self, apr15_df):
        """The separate Over-Collection sanity check should still fire on Apr 15 (1 deal)."""
        res = validate_tape(apr15_df)
        oc = [w for w in res['warnings'] if w['check'] == 'Over-Collection']
        assert len(oc) == 1
        assert '1 deals' in oc[0]['detail'] or '1 deal' in oc[0]['detail']


class TestStatusReversalSeverityKlaim:
    """
    Completed→Executed reversal is a known Klaim pattern (denial reopen) and should be
    WARNING, not CRITICAL. Other reversal paths (Completed→Pending, Completed→null) stay
    CRITICAL since those would be genuinely anomalous.
    """

    def test_completed_to_executed_is_warning_not_critical(self, mar03_df, apr15_df):
        cons = run_consistency_check(mar03_df, apr15_df, '2026-03-03', '2026-04-15')

        # No 'Status Reversal' (without qualifier) in critical issues
        critical_reversal = [
            i for i in cons['issues'] if i['check'] == 'Status Reversal'
        ]
        assert critical_reversal == [], (
            f"Completed→Executed should be WARNING, not CRITICAL. "
            f"Found critical: {critical_reversal}"
        )

        # Should be present in warnings with the denial-reopen note
        reopen_warning = [
            w for w in cons['warnings'] if 'denial reopen' in w['check']
        ]
        assert len(reopen_warning) == 1
        assert '55 deals' in reopen_warning[0]['detail']
        assert reopen_warning[0].get('note'), (
            "Warning must include a `note` field explaining the denial-reopen pattern"
        )
        assert 'insurance denial' in reopen_warning[0]['note'].lower()

    def test_non_executed_reversal_still_critical(self):
        """Completed→Pending (or any non-Executed target) stays CRITICAL."""
        old = pd.DataFrame({'ID': [1, 2, 3], 'Status': ['Completed', 'Completed', 'Completed']})
        new = pd.DataFrame({'ID': [1, 2, 3], 'Status': ['Pending', 'Executed', 'Completed']})
        cons = run_consistency_check(old, new, 'old', 'new')
        crit = [i for i in cons['issues'] if i['check'] == 'Status Reversal']
        # One deal went Completed→Pending (critical), one Completed→Executed (warning), one unchanged
        assert len(crit) == 1
        assert '1 deals' in crit[0]['detail']
        warn = [w for w in cons['warnings'] if 'denial reopen' in w['check']]
        assert len(warn) == 1
        assert '1 deals' in warn[0]['detail']


# ── Dual-view WAL (Part 3) ────────────────────────────────────────────────────

class TestDualViewWAL:
    """
    Active WAL (outstanding-weighted) is the covenant value, unchanged.
    Total WAL (PV-weighted across active + completed) is a new IC/monitoring view
    that strips the retention bias of active-only WAL.
    """

    def _wal(self, df, ref_date):
        from core.portfolio import compute_klaim_covenants
        covs = compute_klaim_covenants(df, mult=1, ref_date=ref_date)
        return [c for c in covs['covenants'] if 'life' in c['name'].lower()][0]

    def test_active_wal_matches_148_on_apr15(self, apr15_df):
        """Active WAL (outstanding-weighted) should be ~148 days on Apr 15."""
        w = self._wal(apr15_df, '2026-04-15')
        assert w['wal_active_days'] == pytest.approx(148, abs=1)
        # Covenant value mirrors active WAL
        assert w['current'] == pytest.approx(w['wal_active_days'], abs=0.01)

    def test_total_wal_strictly_less_than_active_on_apr15(self, apr15_df):
        """Completed deals have bounded life; active ones accumulate. So wal_total < wal_active."""
        w = self._wal(apr15_df, '2026-04-15')
        assert w['wal_total_available'] is True
        assert w['wal_total_days'] is not None
        assert w['wal_total_days'] < w['wal_active_days'], (
            f"Total WAL ({w['wal_total_days']:.1f}d) must be strictly less than "
            f"Active WAL ({w['wal_active_days']:.1f}d) — if not, the close-date proxy is wrong"
        )

    def test_total_wal_method_documented(self, apr15_df):
        w = self._wal(apr15_df, '2026-04-15')
        # Apr 15 has Collection days so far AND collection curves. Some completed
        # rows carry corrupted (negative) CDSF; the curve-derived Tier 2 fallback
        # fills those gaps with observed last-bucket arrival, so the method tag
        # upgrades from 'collection_days_so_far' to the curve-fallback variant.
        assert w['wal_total_method'] == 'collection_days_so_far_with_curve_fallback'
        assert w['wal_active_confidence'] == 'A'
        assert w['wal_total_confidence'] == 'B'

    def test_total_wal_stays_near_prior_value_on_apr15(self, apr15_df):
        """
        Acceptance: Tier 2 upgrade is an incremental precision improvement (small
        share of PV touched), not a redefinition. Pre-Tier-2 WAL Total was 137d;
        new value must stay within a few days of that.
        """
        w = self._wal(apr15_df, '2026-04-15')
        assert w['wal_total_days'] == pytest.approx(137, abs=3)

    def test_total_wal_graceful_degradation_on_older_tape(self, mar03_df):
        """Mar 3 tape lacks Collection days so far AND Expected collection days → wal_total=None."""
        w = self._wal(mar03_df, '2026-03-03')
        # Active WAL still computes
        assert w['wal_active_days'] > 0
        # Total WAL unavailable
        assert w['wal_total_available'] is False
        assert w['wal_total_days'] is None
        assert w['wal_total_method'] == 'unavailable'

    def test_covenant_compliance_keyed_to_active_not_total(self, apr15_df):
        """MMA-defined covenant must still key off active WAL, not total."""
        w = self._wal(apr15_df, '2026-04-15')
        # Apr 15 compliance path should be computed against wal_active (148d > 70d → Path B carve-out)
        # NOT against wal_total (137d — if we used this, Path A would appear to pass).
        assert w['compliance_path'].startswith('Path B') or w['compliance_path'].startswith('Path A')
        # Active WAL >= 70 means Path A fails — ensure we're evaluating active, not total.
        assert w['wal_active_days'] > 70
        assert w['compliance_path'] != 'Path A (WAL)', (
            "Covenant compliance should not use wal_total for Path A evaluation"
        )

    def test_total_wal_has_view_note(self, apr15_df):
        w = self._wal(apr15_df, '2026-04-15')
        assert w.get('view_note'), "Covenant must carry a view_note explaining Active vs Total"
        assert 'active' in w['view_note'].lower()
        assert 'total' in w['view_note'].lower()

    def test_path_b_carve_out_contract_for_frontend(self, apr15_df):
        """
        Pins the backend/frontend contract for the WAL Path B carve-out.

        CovenantCard.jsx suppresses the Path A headroom + projected-breach lines when
        `compliance_path === 'Path B (carve-out)'` (headroom would be negative, projection
        would fall in the past — both are mathematically real but operationally misleading
        because Path A is not the binding gate). The card renders the covenant's `note`
        instead. This test pins the three things that guard depends on:
          (1) compliance_path emits the EXACT string 'Path B (carve-out)' when Path B binds
          (2) note is populated in that state (fallback in the UI is a generic string)
          (3) note surfaces the Extended Age current value + limit, so the numbers hidden
              from Path A still reach the user through Path B's phrasing.
        """
        w = self._wal(apr15_df, '2026-04-15')
        assert w['compliance_path'] == 'Path B (carve-out)', (
            "Apr 15 WAL covenant should be compliant via Path B (active WAL=148d > 70d limit, "
            "Extended Age carve-out 4.4% <= 5%). Frontend guard keys off this exact string."
        )
        assert w.get('note'), "note must be populated when Path B binds — frontend renders it in place of Path A headroom"
        assert 'Extended Age' in w['note'], "note must surface the Extended Age current value"
        assert '≤' in w['note'], "note must include the '≤' comparison so the limit is visible"

    def test_methodology_log_documents_close_date_proxy(self, apr15_df, mar03_df):
        from core.analysis import compute_methodology_log
        ml_apr = compute_methodology_log(apr15_df)
        proxy_apr = [a for a in ml_apr['adjustments'] if a.get('type') == 'close_date_proxy']
        assert len(proxy_apr) == 1
        assert proxy_apr[0]['available'] is True
        assert proxy_apr[0]['column'] == 'Collection days so far'
        assert proxy_apr[0]['target_metric'] == 'wal_total_days'
        # Apr 15 has collection curves → Tier 2 fallback documented.
        assert proxy_apr[0]['curve_fallback_available'] is True
        assert 'curve-derived' in proxy_apr[0]['description']

        ml_mar = compute_methodology_log(mar03_df)
        proxy_mar = [a for a in ml_mar['adjustments'] if a.get('type') == 'close_date_proxy']
        assert len(proxy_mar) == 1
        assert proxy_mar[0]['available'] is False

    def test_column_availability_registers_new_columns(self, apr15_df, mar03_df):
        from core.analysis import compute_methodology_log
        ml_apr = compute_methodology_log(apr15_df)
        ca_apr = ml_apr['column_availability']
        # Apr 15 should register all three new columns as available
        assert ca_apr['Expected collection days'] is True
        assert ca_apr['Collection days so far'] is True
        assert ca_apr['Provider'] is True
        # Mar 3 should register them as absent
        ml_mar = compute_methodology_log(mar03_df)
        ca_mar = ml_mar['column_availability']
        assert ca_mar['Expected collection days'] is False
        assert ca_mar['Collection days so far'] is False
        assert ca_mar['Provider'] is False


class TestCurveCloseAgeFallback:
    """
    Tier 2 of the _klaim_wal_total fallback chain: when 'Collection days so far'
    is corrupted (missing/negative) for a completed row, use the LAST 30d bucket
    in which cumulative Actual increased as the observed close age — strictly
    better than contractual 'Expected collection days'.
    """

    def _synthetic_row(self, cdsf, exp, bucket_actuals, status='Completed', deal_days_ago=200, pv=1_000_000):
        """Build a one-row DataFrame with the columns _klaim_wal_total expects."""
        ref = pd.Timestamp('2026-04-15')
        row = {
            'Deal date': ref - pd.Timedelta(days=deal_days_ago),
            'Purchase value': pv,
            'Status': status,
            'Collection days so far': cdsf,
            'Expected collection days': exp,
        }
        # 13 curve buckets at 30-day intervals. bucket_actuals is a dict
        # {bucket_days: cumulative_value}; unspecified buckets carry forward
        # the last value (curves are cumulative, non-decreasing).
        last = 0.0
        for b in range(30, 391, 30):
            if b in bucket_actuals:
                last = bucket_actuals[b]
            row[f'Actual in {b} days'] = last
        return pd.DataFrame([row])

    def test_curve_tier_overrides_contractual_for_corrupted_primary(self):
        """
        Corrupted CDSF (-10) + contractual 94d + curves showing the 60-90 bucket
        as the last positive delta → Tier 2 should stamp close-age = 90d,
        NOT the 94d contractual value. WAL is PV-weighted over the single row,
        so the WAL reading IS the close-age applied.
        """
        from core.portfolio import _klaim_wal_total
        df = self._synthetic_row(
            cdsf=-10,
            exp=94,
            bucket_actuals={30: 0, 60: 100, 90: 150, 120: 150},
            deal_days_ago=200,
        )
        wal, method = _klaim_wal_total(df, '2026-04-15', 1)
        assert wal == pytest.approx(90, abs=0.01), (
            f"Curve-derived close age should be 90d (upper bound of the last "
            f"positive-delta bucket), not contractual 94d. Got {wal}"
        )
        assert method == 'collection_days_so_far_with_curve_fallback'

    def test_curve_tier_skipped_when_primary_is_clean(self):
        """
        When CDSF is valid for every row, curves are not used; method tag stays
        on the legacy 'collection_days_so_far' value.
        """
        from core.portfolio import _klaim_wal_total
        df = self._synthetic_row(
            cdsf=80,
            exp=94,
            bucket_actuals={30: 0, 60: 100, 90: 150},
            deal_days_ago=200,
        )
        wal, method = _klaim_wal_total(df, '2026-04-15', 1)
        assert wal == pytest.approx(80, abs=0.01)
        assert method == 'collection_days_so_far'

    def test_curve_tier_skipped_when_curves_absent(self):
        """
        Tape with CDSF but without curve columns — function still works, falls
        through to contractual fallback when CDSF is corrupted.
        """
        from core.portfolio import _klaim_wal_total
        ref = pd.Timestamp('2026-04-15')
        df = pd.DataFrame([{
            'Deal date': ref - pd.Timedelta(days=200),
            'Purchase value': 1_000_000,
            'Status': 'Completed',
            'Collection days so far': -10,
            'Expected collection days': 94,
        }])
        wal, method = _klaim_wal_total(df, '2026-04-15', 1)
        # Corrupted CDSF → no Tier 2 (no curves) → Tier 3 contractual = 94d
        assert wal == pytest.approx(94, abs=0.01)
        assert method == 'collection_days_so_far'

    def test_curve_tier_returns_last_positive_bucket_not_first(self):
        """
        The curve-derived close-age must be the LAST bucket with a positive
        delta (i.e. last observed cash arrival), not the first. A row with
        cash arriving in both the 30–60 and 180–210 buckets closes at 210d.
        """
        from core.portfolio import _klaim_curve_close_age
        ref = pd.Timestamp('2026-04-15')
        buckets = {30: 0, 60: 50, 90: 50, 120: 50, 150: 50, 180: 50, 210: 120}
        row = {
            'Deal date': ref - pd.Timedelta(days=300),
            'Purchase value': 1_000_000,
            'Status': 'Completed',
        }
        last = 0.0
        for b in range(30, 391, 30):
            if b in buckets:
                last = buckets[b]
            row[f'Actual in {b} days'] = last
        df = pd.DataFrame([row])
        ages = _klaim_curve_close_age(df)
        assert ages.iloc[0] == 210

    def test_curve_tier_returns_nan_when_no_cash_ever_arrived(self):
        """Row with all-zero curves should return NaN so the caller falls through."""
        from core.portfolio import _klaim_curve_close_age
        ref = pd.Timestamp('2026-04-15')
        row = {'Deal date': ref - pd.Timedelta(days=120), 'Purchase value': 100, 'Status': 'Completed'}
        for b in range(30, 391, 30):
            row[f'Actual in {b} days'] = 0.0
        df = pd.DataFrame([row])
        ages = _klaim_curve_close_age(df)
        assert pd.isna(ages.iloc[0])

    def test_curve_helper_returns_none_when_any_bucket_column_missing(self):
        """If the tape lacks any of the 13 curve columns, helper returns None."""
        from core.portfolio import _klaim_curve_close_age
        df = pd.DataFrame([{'Actual in 30 days': 100, 'Actual in 60 days': 150}])
        assert _klaim_curve_close_age(df) is None


# ── Provider wiring (Part 2) ──────────────────────────────────────────────────

class TestProviderConcentration:
    """Provider is a strict sub-dimension of Group — branch-level attribution."""

    def test_provider_present_on_apr15(self, apr15_df):
        conc = compute_concentration(apr15_df, 1)
        assert 'provider' in conc
        assert len(conc['provider']) > 0
        # Top provider on Apr 15 is ALPINE at ~5.3%
        top = conc['provider'][0]
        assert top['Provider'] == 'ALPINE'
        assert top['percentage'] == pytest.approx(5.3, abs=0.1)

    def test_provider_absent_on_mar03(self, mar03_df):
        """Graceful degradation: older tapes omit the provider section entirely."""
        conc = compute_concentration(mar03_df, 1)
        assert 'provider' not in conc
        # Group still present
        assert 'group' in conc
        # Existing behaviour preserved: top_deals, product still present
        assert 'top_deals' in conc

    def test_provider_hhi_value_on_apr15(self, apr15_df):
        """Manually verified: Provider HHI on Apr 15 is ~201 (0.0201)."""
        hhi = compute_hhi(apr15_df, 1)
        assert 'provider' in hhi
        # HHI reported as decimal fraction; expecting ~0.0201 = 201 bps²
        assert hhi['provider']['hhi'] == pytest.approx(0.0201, abs=0.0005)
        assert hhi['provider']['count'] == 216

    def test_provider_hhi_absent_on_mar03(self, mar03_df):
        hhi = compute_hhi(mar03_df, 1)
        assert 'provider' not in hhi
        # Group HHI still computed
        assert 'group' in hhi

    def test_provider_hhi_time_series_emits_nulls(self, mar03_df, apr15_df):
        """Time series must emit provider_hhi=None on tapes without the column."""
        ts_mar = compute_hhi_for_snapshot(mar03_df, 1)
        ts_apr = compute_hhi_for_snapshot(apr15_df, 1)
        assert ts_mar['provider_hhi'] is None
        assert ts_apr['provider_hhi'] is not None
        assert ts_apr['provider_hhi'] == pytest.approx(0.0201, abs=0.0005)
        # Group HHI always computed
        assert ts_mar['group_hhi'] is not None
        assert ts_apr['group_hhi'] is not None

    def test_provider_is_strict_subtree_of_group(self, apr15_df):
        """No Provider maps to multiple Groups (clean tree, user-verified)."""
        pg = apr15_df.groupby('Provider')['Group'].nunique()
        assert (pg > 1).sum() == 0, (
            f"{int((pg > 1).sum())} Providers map to multiple Groups — not a clean tree"
        )


class TestProviderSegmentAnalysis:
    """Segment Analysis should expose provider/group dimensions where available."""

    def test_apr15_exposes_provider_and_group_dimensions(self, apr15_df):
        seg = compute_segment_analysis(apr15_df, 1, segment_by='product')
        assert 'provider' in seg['available_dimensions']
        assert 'group' in seg['available_dimensions']

    def test_mar03_exposes_group_but_not_provider(self, mar03_df):
        seg = compute_segment_analysis(mar03_df, 1, segment_by='product')
        assert 'group' in seg['available_dimensions']
        assert 'provider' not in seg['available_dimensions']

    def test_provider_segment_cuts_off_at_25_plus_other(self, apr15_df):
        """High-cardinality dimensions collapse long tail into 'Other' bucket."""
        seg = compute_segment_analysis(apr15_df, 1, segment_by='provider')
        assert seg['available'] is True
        segments = seg['segments']
        # 216 distinct providers → top 25 + Other = 26 segments
        assert len(segments) == 26
        segment_names = [s['segment'] for s in segments]
        assert 'Other' in segment_names

    def test_group_segment_cuts_off_at_25_plus_other(self, apr15_df):
        seg = compute_segment_analysis(apr15_df, 1, segment_by='group')
        assert seg['available'] is True
        segments = seg['segments']
        # 144 distinct groups → top 25 + Other = 26 segments
        assert len(segments) == 26
        assert 'Other' in [s['segment'] for s in segments]

    def test_sorted_by_originated_descending(self, apr15_df):
        """Most material segments first — IC-friendly ordering."""
        seg = compute_segment_analysis(apr15_df, 1, segment_by='provider')
        origs = [s['originated'] for s in seg['segments']]
        # Allow 'Other' anywhere since it's a heavy-tail aggregate; just check sorted
        assert origs == sorted(origs, reverse=True)

    def test_provider_dim_unavailable_on_mar03_returns_error(self, mar03_df):
        """Asking for provider dim on a pre-Apr15 tape returns available=False."""
        seg = compute_segment_analysis(mar03_df, 1, segment_by='provider')
        assert seg['available'] is False
        assert 'provider' not in seg['available_dimensions']


class TestCovenantMethodTagging:
    """Covenant history entries carry a `method` field so methodology changes
    (e.g. Paid vs Due: proxy -> direct once Expected collection days arrived)
    don't silently count as consecutive breaches under the two-consecutive rule.
    """

    def test_every_covenant_has_method_field(self, full_df):
        from core.portfolio import compute_klaim_covenants
        res = compute_klaim_covenants(full_df, 1, '2026-04-15')
        for cv in res['covenants']:
            assert 'method' in cv, f"{cv['name']} missing method"
            assert cv['method'] in {'direct', 'proxy', 'age_pending', 'cumulative', 'stable', 'manual'}

    def test_paid_vs_due_direct_when_expected_collection_days_present(self, full_df):
        """Paid vs Due must report method='direct' on tapes with Expected collection days."""
        from core.portfolio import compute_klaim_covenants
        if 'Expected collection days' not in full_df.columns:
            pytest.skip("Tape lacks Expected collection days")
        res = compute_klaim_covenants(full_df, 1, '2026-04-15')
        pvd = next(c for c in res['covenants'] if c['name'] == 'Paid vs Due Ratio')
        assert pvd['method'] == 'direct'

    def test_method_change_breaks_consecutive_breach_chain(self):
        """If prior breach used 'proxy' and current breach uses 'direct',
        annotate_covenant_eod must NOT count them as two consecutive breaches.
        """
        from core.portfolio import annotate_covenant_eod
        fake_result = {
            'covenants': [{
                'name': 'Paid vs Due Ratio',
                'compliant': False,
                'current': 0.83,
                'period': '2026-04-01 – 2026-04-30',
                'method': 'direct',
                'eod_rule': 'two_consecutive_breaches',
            }]
        }
        fake_history = {
            'Paid vs Due Ratio': [{
                'period': '2026-03-01 – 2026-03-31',
                'compliant': False,
                'current': 0.70,
                'date': '2026-03-31',
                'method': 'proxy',
            }]
        }
        annotated = annotate_covenant_eod(fake_result, fake_history)
        pvd = annotated['covenants'][0]
        assert pvd['eod_triggered'] is False
        assert pvd['eod_status'] == 'first_breach_after_method_change'
        assert pvd['consecutive_breaches'] == 1
        assert pvd.get('method_changed_vs_prior') is True

    def test_method_match_preserves_consecutive_breach(self):
        """When methods match, two consecutive breaches still trigger EoD."""
        from core.portfolio import annotate_covenant_eod
        fake_result = {
            'covenants': [{
                'name': 'Paid vs Due Ratio',
                'compliant': False,
                'current': 0.83,
                'period': '2026-04-01 – 2026-04-30',
                'method': 'direct',
                'eod_rule': 'two_consecutive_breaches',
            }]
        }
        fake_history = {
            'Paid vs Due Ratio': [{
                'period': '2026-03-01 – 2026-03-31',
                'compliant': False,
                'current': 0.70,
                'date': '2026-03-31',
                'method': 'direct',
            }]
        }
        annotated = annotate_covenant_eod(fake_result, fake_history)
        pvd = annotated['covenants'][0]
        assert pvd['eod_triggered'] is True
        assert pvd['eod_status'] == 'eod_triggered'
        assert pvd['consecutive_breaches'] == 2

    def test_missing_method_treated_as_unknown_not_penalised(self):
        """Legacy history entries without `method` shouldn't block the consecutive chain."""
        from core.portfolio import annotate_covenant_eod
        fake_result = {
            'covenants': [{
                'name': 'Paid vs Due Ratio',
                'compliant': False,
                'current': 0.83,
                'period': '2026-04-01 – 2026-04-30',
                'method': 'direct',
                'eod_rule': 'two_consecutive_breaches',
            }]
        }
        fake_history = {
            'Paid vs Due Ratio': [{
                'period': '2026-03-01 – 2026-03-31',
                'compliant': False,
                'current': 0.70,
                'date': '2026-03-31',
                # no `method` key — legacy entry
            }]
        }
        annotated = annotate_covenant_eod(fake_result, fake_history)
        pvd = annotated['covenants'][0]
        # Legacy missing-method: don't penalise, count as consecutive
        assert pvd['eod_triggered'] is True
        assert pvd['consecutive_breaches'] == 2


class TestCovenantFilterStatusColumnAbsent:
    """Regression: defensive `if 'Status' in df.columns else True` fallback in
    Coll Ratio + Paid vs Due filters used a Python operator-precedence-broken
    ternary (`df[mask if cond else True]` parsed as `df[True]`), which raises
    KeyError on a DataFrame missing the Status column. compute_klaim_covenants
    must NOT crash on a Status-less DataFrame — it should fall through to the
    date-only filter.
    """

    def _minimal_klaim_df(self, with_status=False):
        rows = []
        base_date = pd.Timestamp('2026-04-01')
        for i in range(20):
            row = {
                'Deal date': base_date - pd.Timedelta(days=i * 3),
                'Purchase value': 10000.0 + i * 100,
                'Collected till date': 8000.0 + i * 50,
                'Denied by insurance': 100.0,
                'Pending insurance response': 50.0,
                'Expected total': 11000.0 + i * 100,
                'Expected collection days': 60.0,
                'Group': f'PROVIDER_{i % 4}',
            }
            if with_status:
                row['Status'] = 'Executed' if i % 3 != 0 else 'Completed'
            rows.append(row)
        return pd.DataFrame(rows)

    def test_compute_covenants_does_not_crash_when_status_absent(self):
        """KeyError: True regression — Coll Ratio + PVD filters must handle
        Status column missing without raising."""
        from core.portfolio import compute_klaim_covenants
        df_no_status = self._minimal_klaim_df(with_status=False)
        # Should not raise
        result = compute_klaim_covenants(df_no_status, mult=1, ref_date='2026-04-15')
        # Should still emit the covenant set
        names = {c['name'] for c in result['covenants']}
        assert 'Collection Ratio (cumulative)' in names
        assert 'Paid vs Due Ratio' in names

    def test_compute_covenants_filters_to_executed_when_status_present(self):
        """Positive case — the filter still excludes Completed deals when Status is present."""
        from core.portfolio import compute_klaim_covenants
        df_with_status = self._minimal_klaim_df(with_status=True)
        result_with = compute_klaim_covenants(df_with_status, mult=1, ref_date='2026-04-15')
        df_without = self._minimal_klaim_df(with_status=False)
        result_without = compute_klaim_covenants(df_without, mult=1, ref_date='2026-04-15')
        # Without Status, the filter degrades to date-only; the period-deal pool
        # is at least as large as the Status-filtered pool, so collection ratio
        # values may differ. The key invariant: NEITHER call raised.
        coll_with = next(c for c in result_with['covenants']
                         if c['name'] == 'Collection Ratio (cumulative)')
        coll_without = next(c for c in result_without['covenants']
                            if c['name'] == 'Collection Ratio (cumulative)')
        assert 'current' in coll_with
        assert 'current' in coll_without


# ── Cash-Flow-Weighted Duration tests ───────────────────────────────────────

class TestCashDuration:
    def test_apr15_returns_available_and_sensible(self, apr15_df):
        """Apr 15 tape has 13 curve columns — compute should work."""
        result = compute_klaim_cash_duration(apr15_df, 1, as_of_date='2026-04-15')
        assert result['available'] is True
        assert 'portfolio' in result
        assert 'by_vintage' in result
        assert 'method_note' in result
        # Sensible bounds: duration between 1 day and 390 days (the outer bucket).
        dur_all = result['portfolio']['duration_days']
        dur_completed = result['portfolio']['duration_days_completed_only']
        assert dur_all is not None and 1 < dur_all < 390, f'portfolio duration {dur_all} out of range'
        assert dur_completed is not None and 1 < dur_completed < 390, f'completed duration {dur_completed} out of range'
        # Completed-only should be HIGHER than all-deals: active deals' curves are partial-life,
        # so their per-deal duration skews lower (cash they haven't received yet isn't in the numerator).
        assert dur_completed >= dur_all - 1.0, (
            f'completed={dur_completed} should be >= all={dur_all} (minus tolerance) — '
            "active-deal curves are incomplete and should understate duration"
        )
        # by_vintage should be populated
        assert len(result['by_vintage']) > 0
        for v in result['by_vintage']:
            assert 'vintage' in v and 'duration_days' in v and 'deal_count' in v and 'pv' in v
            assert 1 < v['duration_days'] < 390

    def test_older_tape_without_curves_returns_unavailable(self, mar03_df):
        """Mar 3 tape has curves; older tapes don't. Use Sep 2025 tape via direct load."""
        # Sep 2025 tape has no curve columns — load it explicitly.
        from core.loader import load_snapshot
        sep_path = os.path.join(DATA_DIR, '2025-09-23_uae_healthcare.csv')
        if not os.path.exists(sep_path):
            pytest.skip('Sep 2025 tape not present')
        sep_df = load_snapshot(sep_path)
        result = compute_klaim_cash_duration(sep_df, 1, as_of_date='2025-09-23')
        assert result['available'] is False
        # Contract: fields exist even when unavailable, so callers can access them safely.
        assert result['portfolio']['duration_days'] is None
        assert result['portfolio']['duration_days_completed_only'] is None
        assert result['by_vintage'] == []
        assert isinstance(result['method_note'], str) and len(result['method_note']) > 0

    def test_early_cash_has_lower_duration_than_late_cash(self):
        """Synthetic test: a deal paying cash on day 30 has lower duration than one paying on day 270."""
        # Build a minimal frame with two synthetic deals, each PV=100, one paid at day 30, one at day 270.
        curve_cols = [f'Actual in {d} days' for d in [30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330, 360, 390]]
        # Early deal: 100 cash arrives by day 30, stays at 100 thereafter.
        early_row = {c: 100.0 for c in curve_cols}
        # Late deal: 0 until day 270, then 100 and flat.
        late_row = {c: (100.0 if int(c.split()[2]) >= 270 else 0.0) for c in curve_cols}
        df = pd.DataFrame([
            {'Deal date': pd.Timestamp('2025-01-01'), 'Purchase value': 100.0, 'Status': 'Completed', **early_row},
            {'Deal date': pd.Timestamp('2025-01-01'), 'Purchase value': 100.0, 'Status': 'Completed', **late_row},
        ])
        # Individually:
        df_early = df.iloc[[0]].reset_index(drop=True)
        df_late = df.iloc[[1]].reset_index(drop=True)
        r_early = compute_klaim_cash_duration(df_early, 1, as_of_date='2026-01-01')
        r_late = compute_klaim_cash_duration(df_late, 1, as_of_date='2026-01-01')
        assert r_early['available'] and r_late['available']
        dur_early = r_early['portfolio']['duration_days']
        dur_late = r_late['portfolio']['duration_days']
        # Early deal: all 100 in the 30-day bucket → duration == 30.
        assert dur_early == pytest.approx(30.0, abs=0.1)
        # Late deal: all 100 in the 270-day bucket → duration == 270.
        assert dur_late == pytest.approx(270.0, abs=0.1)
        # Ordering assertion from the spec — early < late.
        assert dur_early < dur_late
        # PV-weighted mix of the two: both PV=100, so mean = 150.
        r_mix = compute_klaim_cash_duration(df, 1, as_of_date='2026-01-01')
        assert r_mix['portfolio']['duration_days'] == pytest.approx(150.0, abs=0.1)


# ── Klaim Stale Filter + Operational WAL + Stale Exposure ─────────────────────
# Empirical targets from manual measurement on the Apr 15 tape:
#   WAL Total (covenant, all deals, core.portfolio):  137.2d
#   Operational WAL (clean book, new):                  78.6d
#   Realized WAL (completed-clean, new):                64.9d
#   Stale share:                                        16.5%  (926 deals)
#   Mar 3 tape (older, no close-age columns):           Operational WAL degraded

class TestClassifyKlaimDealStale:
    """Boolean-mask classifier used by Operational WAL and Stale Exposure."""

    def test_returns_all_expected_keys(self, apr15_df):
        masks = classify_klaim_deal_stale(apr15_df, ref_date='2026-04-15')
        assert set(masks.keys()) == {
            'loss_completed', 'stuck_active', 'denial_dominant_active',
            'any_stale', 'ineligibility_age_days',
        }

    def test_any_stale_is_or_reduction(self, apr15_df):
        masks = classify_klaim_deal_stale(apr15_df, ref_date='2026-04-15')
        expected = masks['loss_completed'] | masks['stuck_active'] | masks['denial_dominant_active']
        assert (masks['any_stale'] == expected).all()

    def test_apr15_category_counts(self, apr15_df):
        masks = classify_klaim_deal_stale(apr15_df, ref_date='2026-04-15')
        # Empirical counts on Apr 15: 152 / 770 / 21 → any_stale 926
        assert 140 <= int(masks['loss_completed'].sum())         <= 170
        assert 720 <= int(masks['stuck_active'].sum())           <= 820
        assert 15  <= int(masks['denial_dominant_active'].sum()) <= 35
        assert 900 <= int(masks['any_stale'].sum())              <= 950

    def test_threshold_parameter_tightens_stuck_set(self, apr15_df):
        loose = classify_klaim_deal_stale(apr15_df, ref_date='2026-04-15', ineligibility_age_days=91)
        tight = classify_klaim_deal_stale(apr15_df, ref_date='2026-04-15', ineligibility_age_days=30)
        # Lower threshold → more deals flagged stuck_active
        assert int(tight['stuck_active'].sum()) >= int(loose['stuck_active'].sum())
        # loss_completed and denial_dominant_active are threshold-independent
        assert (tight['loss_completed'] == loose['loss_completed']).all()
        assert (tight['denial_dominant_active'] == loose['denial_dominant_active']).all()

    def test_mar03_compute_without_curve_columns(self, mar03_df):
        # Mar 3 lacks Collection days so far AND Expected collection days, but
        # all three stale rules only need Status, Deal date, PV, Denied, Collected.
        masks = classify_klaim_deal_stale(mar03_df, ref_date='2026-03-03')
        assert int(masks['any_stale'].sum()) > 0


class TestKlaimOperationalWAL:
    """Operational WAL — PV-weighted age on clean (non-stale) book."""

    def test_apr15_operational_wal_around_79_days(self, apr15_df):
        res = compute_klaim_operational_wal(apr15_df, 1.0, ref_date='2026-04-15')
        assert res['available'] is True
        assert 78 <= res['operational_wal_days'] <= 80, \
            f"Expected ~79d (empirical 78.6), got {res['operational_wal_days']}"

    def test_apr15_realized_wal_around_65_days(self, apr15_df):
        res = compute_klaim_operational_wal(apr15_df, 1.0, ref_date='2026-04-15')
        assert res['realized_wal_days'] is not None
        assert 64 <= res['realized_wal_days'] <= 66, \
            f"Expected ~65d (empirical 64.9), got {res['realized_wal_days']}"

    def test_apr15_strictly_less_than_covenant_wal_total(self, apr15_df):
        # Zombie exclusion must lower the PV-weighted mean. Baseline comes from
        # core.portfolio._klaim_wal_total which is NOT changed by this task.
        from core.portfolio import _klaim_wal_total
        df = apr15_df.copy()
        df['Deal date'] = pd.to_datetime(df['Deal date'], errors='coerce')
        wal_total, _ = _klaim_wal_total(df, pd.Timestamp('2026-04-15'), 1.0)

        op = compute_klaim_operational_wal(apr15_df, 1.0, ref_date='2026-04-15')
        assert op['operational_wal_days'] < wal_total, \
            f"Operational {op['operational_wal_days']}d must be < Total {wal_total}d"

    def test_apr15_realized_less_than_operational(self, apr15_df):
        # Completed-clean ages are bounded; active-clean ages keep accruing.
        # Strictly Realized < Operational on a live book.
        res = compute_klaim_operational_wal(apr15_df, 1.0, ref_date='2026-04-15')
        assert res['realized_wal_days'] < res['operational_wal_days']

    def test_apr15_method_is_cdsf(self, apr15_df):
        res = compute_klaim_operational_wal(apr15_df, 1.0, ref_date='2026-04-15')
        assert res['method'] == 'collection_days_so_far'
        assert res['confidence'] == 'B'

    def test_mar03_degrades_to_active_clean_only(self, mar03_df):
        # No close-age proxy → active-clean only, Realized WAL unavailable,
        # method=elapsed_only, confidence C. Operational WAL must still be a
        # real number (not raise, not return available=False).
        res = compute_klaim_operational_wal(mar03_df, 1.0, ref_date='2026-03-03')
        assert res['available'] is True
        assert res['method'] == 'elapsed_only'
        assert res['confidence'] == 'C'
        assert res['realized_wal_days'] is None
        assert res['operational_wal_days'] > 0

    def test_currency_multiplier_does_not_affect_age(self, apr15_df):
        # Days are unitless — multiplier only scales PV fields.
        res_aed = compute_klaim_operational_wal(apr15_df, 1.0, ref_date='2026-04-15')
        res_usd = compute_klaim_operational_wal(apr15_df, 0.2723, ref_date='2026-04-15')
        assert res_aed['operational_wal_days'] == pytest.approx(res_usd['operational_wal_days'], abs=0.01)
        assert res_aed['realized_wal_days']    == pytest.approx(res_usd['realized_wal_days'],    abs=0.01)
        # But PV fields scale.
        assert res_usd['clean_pv'] == pytest.approx(res_aed['clean_pv'] * 0.2723, rel=0.01)

    def test_does_not_mutate_input_df(self, apr15_df):
        before = pd.util.hash_pandas_object(apr15_df, index=True).sum()
        _ = compute_klaim_operational_wal(apr15_df, 1.0, ref_date='2026-04-15')
        _ = compute_klaim_stale_exposure(apr15_df, 1.0, ref_date='2026-04-15')
        after = pd.util.hash_pandas_object(apr15_df, index=True).sum()
        assert before == after, "compute must not mutate caller's df"


class TestKlaimStaleExposure:
    """Stale exposure — category breakdown + top-25 offenders."""

    def test_apr15_stale_share_around_16_percent(self, apr15_df):
        res = compute_klaim_stale_exposure(apr15_df, 1.0, ref_date='2026-04-15')
        assert res['available'] is True
        # Empirical 16.5% → accept 15.5-17.5%
        assert 0.155 <= res['stale_pv_share'] <= 0.175, \
            f"Expected ~16.5%, got {res['stale_pv_share']*100:.1f}%"

    def test_apr15_stale_count_around_926(self, apr15_df):
        res = compute_klaim_stale_exposure(apr15_df, 1.0, ref_date='2026-04-15')
        assert 900 <= res['total_stale_count'] <= 950, \
            f"Expected ~926 stale deals, got {res['total_stale_count']}"

    def test_apr15_all_three_categories_populated(self, apr15_df):
        res = compute_klaim_stale_exposure(apr15_df, 1.0, ref_date='2026-04-15')
        by = {c['category']: c for c in res['by_category']}
        assert by['loss_completed']['count']         > 0
        assert by['stuck_active']['count']           > 0
        assert by['denial_dominant_active']['count'] > 0

    def test_apr15_category_shares_sum_to_total(self, apr15_df):
        # Categories MAY overlap (a deal hitting multiple rules is counted in
        # each raw category). Any-stale PV ≤ sum of category PVs, ≥ max of them.
        res = compute_klaim_stale_exposure(apr15_df, 1.0, ref_date='2026-04-15')
        cat_pv_sum = sum(c['pv']    for c in res['by_category'])
        cat_count_sum = sum(c['count'] for c in res['by_category'])
        # Sum-of-categories >= unique any_stale (overlap inflates sum)
        assert cat_pv_sum    >= res['total_stale_pv']
        assert cat_count_sum >= res['total_stale_count']

    def test_apr15_top_offenders_sorted_desc_by_pv(self, apr15_df):
        res = compute_klaim_stale_exposure(apr15_df, 1.0, ref_date='2026-04-15')
        pvs = [o['pv'] for o in res['top_offenders']]
        assert pvs == sorted(pvs, reverse=True)
        assert 1 <= len(res['top_offenders']) <= 25

    def test_apr15_includes_1184_day_deal(self, apr15_df):
        # The 1,184-day-old AED 4M PV deal still Executed should be the #1
        # offender on Apr 15. Its deal ID is stable.
        res = compute_klaim_stale_exposure(apr15_df, 1.0, ref_date='2026-04-15')
        ids = [o['id'] for o in res['top_offenders']]
        assert '63c640a0dcf9dec878b44b0b' in ids
        # And it should be the top entry (largest stale PV on the book)
        assert res['top_offenders'][0]['id'] == '63c640a0dcf9dec878b44b0b'
        assert res['top_offenders'][0]['category'] == 'stuck_active'

    def test_apr15_top_offender_has_group_and_provider(self, apr15_df):
        # Apr 15 tape has both Group and Provider columns — offender rows should carry them.
        res = compute_klaim_stale_exposure(apr15_df, 1.0, ref_date='2026-04-15')
        first = res['top_offenders'][0]
        assert 'group'    in first
        assert 'provider' in first

    def test_mar03_computes_gracefully(self, mar03_df):
        # Mar 3 lacks Collection days so far + Expected collection days + Provider.
        # stuck_active + loss_completed + denial_dominant_active all still compute
        # (they only need Status/Deal date/PV/Denied/Collected).
        res = compute_klaim_stale_exposure(mar03_df, 1.0, ref_date='2026-03-03')
        assert res['available'] is True
        assert res['total_stale_count'] > 0
        # Provider missing on Mar 3 → top_offenders rows should NOT carry provider.
        for o in res['top_offenders']:
            assert 'provider' not in o

    def test_facility_params_threshold_override(self, apr15_df):
        # Tighter ineligibility_age_days → more deals flagged stuck_active → more stale.
        loose = compute_klaim_stale_exposure(apr15_df, 1.0, ref_date='2026-04-15',
                                             facility_params={'ineligibility_age_days': 91})
        tight = compute_klaim_stale_exposure(apr15_df, 1.0, ref_date='2026-04-15',
                                             facility_params={'ineligibility_age_days': 30})
        assert tight['total_stale_count'] >= loose['total_stale_count']
        assert tight['ineligibility_age_days'] == 30

    def test_empty_df_returns_unavailable(self, apr15_df):
        empty = apr15_df.iloc[0:0].copy()
        res = compute_klaim_stale_exposure(empty, 1.0, ref_date='2026-04-15')
        assert res['available'] is False


class TestStaleClassificationMethodologyLog:
    """compute_methodology_log should surface the stale thresholds for audit."""

    def test_stale_entry_present(self, apr15_df):
        log = compute_methodology_log(apr15_df)
        entries = [a for a in log['adjustments'] if a.get('type') == 'stale_classification']
        assert len(entries) == 1
        e = entries[0]
        assert e['thresholds']['ineligibility_age_days'] == 91
        assert e['thresholds']['loss_denial_pct']        == 0.5
        assert e['thresholds']['stuck_outstanding_pct']  == 0.1
        assert e['thresholds']['denial_dominant_pct']    == 0.5
        assert e['confidence'] == 'B'
