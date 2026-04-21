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
        # Apr 15 has Collection days so far, so observed proxy should win
        assert w['wal_total_method'] == 'collection_days_so_far'
        assert w['wal_active_confidence'] == 'A'
        assert w['wal_total_confidence'] == 'B'

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

    def test_methodology_log_documents_close_date_proxy(self, apr15_df, mar03_df):
        from core.analysis import compute_methodology_log
        ml_apr = compute_methodology_log(apr15_df)
        proxy_apr = [a for a in ml_apr['adjustments'] if a.get('type') == 'close_date_proxy']
        assert len(proxy_apr) == 1
        assert proxy_apr[0]['available'] is True
        assert proxy_apr[0]['column'] == 'Collection days so far'
        assert proxy_apr[0]['target_metric'] == 'wal_total_days'

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
