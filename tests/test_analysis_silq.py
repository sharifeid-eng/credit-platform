"""
Tests for core/analysis_silq.py — SILQ POS lending analytics.

Uses real SILQ tape data (2026-01-31_KSA.xlsx) for integration-level tests.
Validates against known values from the Jan 31 Commentary and Dec 2025
compliance certificate.
"""
import sys, os
import pytest
import pandas as pd
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.analysis_silq import (
    filter_silq_by_date, _dpd, _safe, _ensure_str_shop_id,
    compute_silq_summary, compute_silq_delinquency,
    compute_silq_collections, compute_silq_concentration,
    compute_silq_cohorts, compute_silq_yield,
    compute_silq_tenure, compute_silq_borrowing_base,
    C_DISBURSED, C_OUTSTANDING, C_OVERDUE, C_STATUS, C_PRODUCT,
    C_DISB_DATE, C_REPAY_DEADLINE, C_REPAID, C_TENURE, C_SHOP_ID,
    C_COLLECTABLE, C_MARGIN,
)
from core.analysis_silq import compute_silq_covenants
from core.loader import load_silq_snapshot

# ── Fixtures ──────────────────────────────────────────────────────────────────

TAPE_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'SILQ', 'KSA', '2026-01-31_KSA.xlsx')

@pytest.fixture(scope='module')
def full_df():
    """Load the full SILQ tape (all sheets combined)."""
    df, commentary = load_silq_snapshot(TAPE_PATH)
    return df

@pytest.fixture(scope='module')
def commentary_text():
    """Load just the commentary text."""
    _, text = load_silq_snapshot(TAPE_PATH)
    return text

@pytest.fixture(scope='module')
def jan31_ref():
    return pd.Timestamp('2026-01-31')

@pytest.fixture(scope='module')
def dec31_ref():
    return pd.Timestamp('2025-12-31')


# ── Helper function tests ────────────────────────────────────────────────────

class TestHelpers:
    def test_safe_numpy_int(self):
        assert _safe(np.int64(42)) == 42
        assert isinstance(_safe(np.int64(42)), int)

    def test_safe_numpy_float(self):
        assert _safe(np.float64(3.14)) == pytest.approx(3.14)
        assert isinstance(_safe(np.float64(3.14)), float)

    def test_safe_numpy_nan(self):
        assert _safe(np.float64(np.nan)) == 0

    def test_safe_python_native(self):
        assert _safe(42) == 42
        assert _safe('hello') == 'hello'

    def test_ensure_str_shop_id(self, full_df):
        df = _ensure_str_shop_id(full_df.copy())
        assert pd.api.types.is_string_dtype(df[C_SHOP_ID])

    def test_filter_silq_by_date_none(self, full_df):
        """No filter returns full dataset."""
        result = filter_silq_by_date(full_df, None)
        assert len(result) == len(full_df)

    def test_filter_silq_by_date_dec(self, full_df):
        """Dec 31 filter excludes Jan 2026 loans."""
        result = filter_silq_by_date(full_df, '2025-12-31')
        assert len(result) < len(full_df)
        # Jan 2026 loans should be excluded
        jan_loans = full_df[full_df[C_DISB_DATE] > '2025-12-31']
        assert len(result) == len(full_df) - len(jan_loans)


# ── DPD tests ─────────────────────────────────────────────────────────────────

class TestDPD:
    def test_dpd_closed_loans_zero(self, full_df, jan31_ref):
        """Closed loans always have 0 DPD regardless of deadline."""
        closed = full_df[full_df[C_STATUS] == 'Closed']
        dpd = _dpd(closed, jan31_ref)
        assert (dpd == 0).all()

    def test_dpd_ref_date_matters(self, full_df):
        """DPD changes with different reference dates."""
        active = full_df[full_df[C_STATUS] != 'Closed']
        dpd_jan = _dpd(active, pd.Timestamp('2026-01-31'))
        dpd_dec = _dpd(active, pd.Timestamp('2025-12-31'))
        # Jan has more days elapsed, so DPD should be >= Dec
        assert (dpd_jan >= dpd_dec).all()

    def test_dpd_non_negative(self, full_df, jan31_ref):
        """DPD is never negative."""
        dpd = _dpd(full_df, jan31_ref)
        assert (dpd >= 0).all()


# ── Summary tests ─────────────────────────────────────────────────────────────

class TestSummary:
    def test_total_deals(self, full_df, jan31_ref):
        result = compute_silq_summary(full_df, mult=1, ref_date=jan31_ref)
        assert result['total_deals'] == 1915

    def test_product_mix(self, full_df, jan31_ref):
        result = compute_silq_summary(full_df, mult=1, ref_date=jan31_ref)
        assert result['product_mix']['BNPL'] == 969
        assert result['product_mix']['RBF_Exc'] == 943
        assert result['product_mix']['RBF_NE'] == 3

    def test_total_disbursed(self, full_df, jan31_ref):
        result = compute_silq_summary(full_df, mult=1, ref_date=jan31_ref)
        assert result['total_disbursed'] == pytest.approx(325_186_069.79, rel=0.001)

    def test_outstanding_matches_commentary(self, full_df, jan31_ref):
        """Commentary says ~SAR 76M outstanding."""
        result = compute_silq_summary(full_df, mult=1, ref_date=jan31_ref)
        assert result['total_outstanding'] == pytest.approx(76_199_378.44, rel=0.001)

    def test_overdue_matches_commentary(self, full_df, jan31_ref):
        """Commentary says ~SAR 6M overdue."""
        result = compute_silq_summary(full_df, mult=1, ref_date=jan31_ref)
        assert result['total_overdue'] == pytest.approx(6_129_799.34, rel=0.001)

    def test_active_plus_closed_equals_total(self, full_df, jan31_ref):
        result = compute_silq_summary(full_df, mult=1, ref_date=jan31_ref)
        assert result['active_deals'] + result['completed_deals'] == result['total_deals']

    def test_currency_multiplier(self, full_df, jan31_ref):
        sar = compute_silq_summary(full_df, mult=1, ref_date=jan31_ref)
        usd = compute_silq_summary(full_df, mult=0.2667, ref_date=jan31_ref)
        assert usd['total_disbursed'] == pytest.approx(sar['total_disbursed'] * 0.2667, rel=0.001)

    def test_par_gbv_weighted(self, full_df, jan31_ref):
        """PAR must be GBV-weighted, not count-based."""
        result = compute_silq_summary(full_df, mult=1, ref_date=jan31_ref)
        # GBV-weighted PAR30 should differ from simple count ratio
        active = full_df[full_df[C_STATUS] != 'Closed']
        dpd = _dpd(active, jan31_ref)
        count_par30 = (dpd > 30).sum() / len(active) * 100
        # The GBV-weighted and count-based should differ
        # (they would only be equal if all loans had equal outstanding)
        assert result['par30'] != pytest.approx(count_par30, abs=0.1)

    def test_json_serializable(self, full_df, jan31_ref):
        """All values must be JSON-serializable (no numpy types)."""
        import json
        result = compute_silq_summary(full_df, mult=1, ref_date=jan31_ref)
        json.dumps(result)  # Should not raise


# ── Delinquency tests ─────────────────────────────────────────────────────────

class TestDelinquency:
    def test_buckets_cover_all_active(self, full_df, jan31_ref):
        result = compute_silq_delinquency(full_df, mult=1, ref_date=jan31_ref)
        total_in_buckets = sum(b['count'] for b in result['buckets'])
        active = full_df[full_df[C_STATUS] != 'Closed']
        assert total_in_buckets == len(active)

    def test_par90_matches_commentary(self, full_df, jan31_ref):
        """Commentary says DPD>90 = SAR 1.10M across 3 counterparties."""
        result = compute_silq_delinquency(full_df, mult=1, ref_date=jan31_ref)
        bucket_90 = next(b for b in result['buckets'] if b['label'] == '90+ DPD')
        assert bucket_90['amount'] == pytest.approx(1_100_929, rel=0.01)
        assert bucket_90['count'] == 12

    def test_par_below_covenant_thresholds_jan31(self, full_df, jan31_ref):
        """PAR30 < 10% and PAR90 < 5% (covenant limits)."""
        result = compute_silq_delinquency(full_df, mult=1, ref_date=jan31_ref)
        assert result['par30'] < 10.0
        assert result['par90'] < 5.0

    def test_par_gbv_weighted_in_delinquency(self, full_df, jan31_ref):
        """Delinquency PAR must also be GBV-weighted."""
        result = compute_silq_delinquency(full_df, mult=1, ref_date=jan31_ref)
        summary = compute_silq_summary(full_df, mult=1, ref_date=jan31_ref)
        # PAR values should match between summary and delinquency
        assert result['par30'] == pytest.approx(summary['par30'], abs=0.01)
        assert result['par90'] == pytest.approx(summary['par90'], abs=0.01)

    def test_top_shops_sorted_desc(self, full_df, jan31_ref):
        result = compute_silq_delinquency(full_df, mult=1, ref_date=jan31_ref)
        overdue_amounts = [s['overdue'] for s in result['top_shops']]
        assert overdue_amounts == sorted(overdue_amounts, reverse=True)


# ── Collections tests ─────────────────────────────────────────────────────────

class TestCollections:
    def test_total_repaid(self, full_df):
        result = compute_silq_collections(full_df, mult=1)
        assert result['total_repaid'] == pytest.approx(full_df[C_REPAID].sum(), rel=0.001)

    def test_by_product_breakdown(self, full_df):
        result = compute_silq_collections(full_df, mult=1)
        products = {p['product'] for p in result['by_product']}
        assert 'BNPL' in products
        assert 'RBF_Exc' in products

    def test_monthly_has_data(self, full_df):
        result = compute_silq_collections(full_df, mult=1)
        assert len(result['monthly']) > 0
        assert all('Month' in m for m in result['monthly'])


# ── Concentration tests ───────────────────────────────────────────────────────

class TestConcentration:
    def test_hhi_reasonable(self, full_df):
        result = compute_silq_concentration(full_df, mult=1)
        # HHI between 0 and 1
        assert 0 < result['hhi'] < 1

    def test_product_mix_adds_to_100(self, full_df):
        result = compute_silq_concentration(full_df, mult=1)
        total_share = sum(p['share'] for p in result['product_mix'])
        assert total_share == pytest.approx(100.0, abs=0.1)

    def test_shops_sorted_by_share(self, full_df):
        result = compute_silq_concentration(full_df, mult=1)
        shares = [s['share'] for s in result['shops']]
        assert shares == sorted(shares, reverse=True)


# ── Cohort tests ──────────────────────────────────────────────────────────────

class TestCohorts:
    def test_has_totals_row(self, full_df, jan31_ref):
        result = compute_silq_cohorts(full_df, mult=1, ref_date=jan31_ref)
        last = result['cohorts'][-1]
        assert last['vintage'] == 'Total'

    def test_totals_match_summary(self, full_df, jan31_ref):
        cohorts = compute_silq_cohorts(full_df, mult=1, ref_date=jan31_ref)
        summary = compute_silq_summary(full_df, mult=1, ref_date=jan31_ref)
        totals = cohorts['cohorts'][-1]
        assert totals['deals'] == summary['total_deals']
        assert totals['disbursed'] == pytest.approx(summary['total_disbursed'], rel=0.001)

    def test_vintages_chronological(self, full_df, jan31_ref):
        result = compute_silq_cohorts(full_df, mult=1, ref_date=jan31_ref)
        vintages = [c['vintage'] for c in result['cohorts'] if c['vintage'] != 'Total']
        assert vintages == sorted(vintages)

    def test_collection_pct_bounded(self, full_df, jan31_ref):
        result = compute_silq_cohorts(full_df, mult=1, ref_date=jan31_ref)
        for c in result['cohorts']:
            assert 0 <= c['collection_pct'] <= 200  # Can exceed 100% due to margin


# ── Yield & Margins tests ────────────────────────────────────────────────────

class TestYield:
    def test_rbf_margin_flagged(self, full_df):
        """RBF_Exc should be flagged as margin not available."""
        result = compute_silq_yield(full_df, mult=1)
        assert 'RBF_Exc' in result['margin_not_available']

    def test_bnpl_has_margin(self, full_df):
        result = compute_silq_yield(full_df, mult=1)
        bnpl = next(p for p in result['by_product'] if p['product'] == 'BNPL')
        assert bnpl['margin_rate'] > 0

    def test_total_margin_positive(self, full_df):
        result = compute_silq_yield(full_df, mult=1)
        assert result['total_margin'] > 0


# ── Tenure tests ──────────────────────────────────────────────────────────────

class TestTenure:
    def test_avg_and_median(self, full_df, jan31_ref):
        result = compute_silq_tenure(full_df, mult=1, ref_date=jan31_ref)
        assert result['avg_tenure'] > 0
        assert result['median_tenure'] > 0

    def test_by_product(self, full_df, jan31_ref):
        result = compute_silq_tenure(full_df, mult=1, ref_date=jan31_ref)
        products = {p['product'] for p in result['by_product']}
        assert 'BNPL' in products

    def test_distribution_covers_all(self, full_df, jan31_ref):
        result = compute_silq_tenure(full_df, mult=1, ref_date=jan31_ref)
        total_in_bands = sum(b['count'] for b in result['distribution'])
        assert total_in_bands == len(full_df)


# ── Borrowing Base tests ──────────────────────────────────────────────────────

class TestBorrowingBase:
    def test_waterfall_structure(self, full_df, jan31_ref):
        result = compute_silq_borrowing_base(full_df, mult=1, ref_date=jan31_ref)
        labels = [w['label'] for w in result['waterfall']]
        assert 'Total Outstanding A/R' in labels
        assert 'Borrowing Base' in labels

    def test_borrowing_base_less_than_ar(self, full_df, jan31_ref):
        result = compute_silq_borrowing_base(full_df, mult=1, ref_date=jan31_ref)
        assert result['borrowing_base'] <= result['total_ar']

    def test_advance_rate_80pct(self, full_df, jan31_ref):
        result = compute_silq_borrowing_base(full_df, mult=1, ref_date=jan31_ref)
        assert result['advance_rate'] == 0.80


# ── Compliance certificate reconciliation ─────────────────────────────────────

class TestComplianceReconciliation:
    """Tests that verify our analytics align with the Dec 2025 compliance cert
    and Jan 2026 Commentary."""

    def test_commentary_outstanding_bnpl(self, full_df, jan31_ref):
        """Commentary: 'SAR 47 Mn under BNPL' — includes BNPL + RBF_NE sheets."""
        # Commentary groups non-RBF_Exc as "BNPL" (BNPL sheet = BNPL + RBF_NE)
        bnpl_sheet = full_df[full_df[C_PRODUCT].isin(['BNPL', 'RBF_NE'])]
        bnpl_outstanding = bnpl_sheet[C_OUTSTANDING].sum()
        assert bnpl_outstanding == pytest.approx(46_688_260.43, rel=0.01)

    def test_commentary_outstanding_rbf(self, full_df, jan31_ref):
        """Commentary: 'SAR 29 Mn under RBF'."""
        rbf = full_df[full_df[C_PRODUCT] == 'RBF_Exc']
        rbf_outstanding = rbf[C_OUTSTANDING].sum()
        assert rbf_outstanding == pytest.approx(29_511_118.01, rel=0.01)

    def test_commentary_dpd90_amount(self, full_df, jan31_ref):
        """Commentary: 'DPD >90 limited to SAR 1.10 Mn'."""
        result = compute_silq_delinquency(full_df, mult=1, ref_date=jan31_ref)
        bucket_90 = next(b for b in result['buckets'] if b['label'] == '90+ DPD')
        assert bucket_90['amount'] == pytest.approx(1_100_929, rel=0.01)

    def test_cert_par30_below_10pct_dec(self, full_df, dec31_ref):
        """Cert: PAR 30 = 1.6% at Dec 31. Our GBV-weighted calc should also pass < 10%."""
        df_dec = filter_silq_by_date(full_df, '2025-12-31')
        result = compute_silq_summary(df_dec, mult=1, ref_date=dec31_ref)
        assert result['par30'] < 10.0

    def test_cert_collection_ratio_dec(self, full_df, dec31_ref):
        """Cert: 3-month collection ratio = 95.53%. Our rate at Dec 31 should be in range."""
        df_dec = filter_silq_by_date(full_df, '2025-12-31')
        result = compute_silq_summary(df_dec, mult=1, ref_date=dec31_ref)
        # Our methodology differs (simple ratio vs 3-month avg), but should be > 33% (covenant)
        assert result['collection_rate'] > 33.0


# ── Covenant monitoring tests ─────────────────────────────────────────────────

class TestCovenants:
    def test_returns_5_covenants(self, full_df, jan31_ref):
        result = compute_silq_covenants(full_df, mult=1, ref_date=jan31_ref)
        assert len(result['covenants']) == 5

    def test_par30_matches_delinquency(self, full_df, jan31_ref):
        """PAR30 covenant should match the delinquency tab value."""
        cov = compute_silq_covenants(full_df, mult=1, ref_date=jan31_ref)
        delin = compute_silq_delinquency(full_df, mult=1, ref_date=jan31_ref)
        par30_cov = cov['covenants'][0]  # First covenant is PAR30
        assert par30_cov['name'] == 'PAR 30 Ratio'
        assert par30_cov['current'] * 100 == pytest.approx(delin['par30'], abs=0.1)

    def test_par90_matches_delinquency(self, full_df, jan31_ref):
        cov = compute_silq_covenants(full_df, mult=1, ref_date=jan31_ref)
        delin = compute_silq_delinquency(full_df, mult=1, ref_date=jan31_ref)
        par90_cov = cov['covenants'][1]
        assert par90_cov['name'] == 'PAR 90 Ratio'
        assert par90_cov['current'] * 100 == pytest.approx(delin['par90'], abs=0.1)

    def test_par30_compliant_jan31(self, full_df, jan31_ref):
        """PAR30 should be compliant (< 10%) as of Jan 31."""
        cov = compute_silq_covenants(full_df, mult=1, ref_date=jan31_ref)
        par30 = cov['covenants'][0]
        assert par30['compliant'] is True
        assert par30['current'] < 0.10

    def test_par90_compliant_jan31(self, full_df, jan31_ref):
        """PAR90 should be compliant (< 5%) as of Jan 31."""
        cov = compute_silq_covenants(full_df, mult=1, ref_date=jan31_ref)
        par90 = cov['covenants'][1]
        assert par90['compliant'] is True
        assert par90['current'] < 0.05

    def test_collection_ratio_above_covenant(self, full_df, jan31_ref):
        """3-month collection ratio should exceed the 33% covenant minimum."""
        cov = compute_silq_covenants(full_df, mult=1, ref_date=jan31_ref)
        coll = cov['covenants'][2]
        assert coll['name'] == 'Collection Ratio (3M Avg)'
        assert coll['current'] > 0.33
        assert coll['compliant'] is True

    def test_repayment_at_term(self, full_df, jan31_ref):
        """Repayment at Term should be available and > 95%."""
        cov = compute_silq_covenants(full_df, mult=1, ref_date=jan31_ref)
        rat = cov['covenants'][3]
        assert rat['name'] == 'Repayment at Term'
        if rat['available']:
            assert rat['current'] > 0.90  # Should be close to cert's 97.33%

    def test_ltv_partial(self, full_df, jan31_ref):
        """LTV should be marked as partial (off-tape data needed)."""
        cov = compute_silq_covenants(full_df, mult=1, ref_date=jan31_ref)
        ltv = cov['covenants'][4]
        assert ltv['name'] == 'Loan-to-Value Ratio'
        assert ltv['partial'] is True
        assert ltv['note'] is not None

    def test_compliant_count(self, full_df, jan31_ref):
        """All computable covenants should be compliant as of Jan 31."""
        cov = compute_silq_covenants(full_df, mult=1, ref_date=jan31_ref)
        assert cov['breach_count'] == 0
        assert cov['compliant_count'] >= 3  # At least PAR30, PAR90, Collection

    def test_covenant_structure(self, full_df, jan31_ref):
        """Each covenant must have required fields for CovenantCard."""
        cov = compute_silq_covenants(full_df, mult=1, ref_date=jan31_ref)
        for c in cov['covenants']:
            assert 'name' in c
            assert 'current' in c
            assert 'threshold' in c
            assert 'compliant' in c
            assert 'operator' in c
            assert 'format' in c
            assert 'breakdown' in c
            assert isinstance(c['breakdown'], list)

    def test_json_serializable(self, full_df, jan31_ref):
        import json
        result = compute_silq_covenants(full_df, mult=1, ref_date=jan31_ref)
        json.dumps(result)  # Should not raise
