"""Tests for Aajil SME trade credit analysis functions."""

import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.loader import load_aajil_snapshot
from core.analysis_aajil import (
    compute_aajil_summary, compute_aajil_traction, compute_aajil_delinquency,
    compute_aajil_collections, compute_aajil_cohorts, compute_aajil_concentration,
    compute_aajil_underwriting, compute_aajil_yield, compute_aajil_loss_waterfall,
    compute_aajil_customer_segments, compute_aajil_seasonality,
    filter_aajil_by_date, _safe, _bucket_industry,
)
from core.validation_aajil import validate_aajil_tape

TAPE_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'Aajil', 'KSA', '2026-04-13_aajil_ksa.xlsx')

# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope='module')
def tape_data():
    """Load the full Aajil tape (Deals + auxiliary sheets)."""
    if not os.path.exists(TAPE_PATH):
        pytest.skip('Aajil tape not found')
    df, aux = load_aajil_snapshot(TAPE_PATH)
    return df, aux

@pytest.fixture(scope='module')
def df(tape_data):
    return tape_data[0]

@pytest.fixture(scope='module')
def aux(tape_data):
    return tape_data[1]


# ── Loader Tests ─────────────────────────────────────────────────────────────

class TestLoader:
    def test_deals_row_count(self, df):
        # 1,246 rows in tape minus 1 null row = 1,245
        assert len(df) >= 1240
        assert len(df) <= 1250

    def test_deals_columns(self, df):
        required = ['Transaction ID', 'Deal Type', 'Invoice Date',
                     'Unique Customer Code', 'Bill Notional', 'Realised Status']
        for col in required:
            assert col in df.columns, f"Missing column: {col}"

    def test_no_unnamed_columns(self, df):
        unnamed = [c for c in df.columns if 'Unnamed' in str(c)]
        assert len(unnamed) == 0, f"Found unnamed columns: {unnamed}"

    def test_date_parsing(self, df):
        assert pd.api.types.is_datetime64_any_dtype(df['Invoice Date'])

    def test_aux_sheets(self, aux):
        assert 'dpd_cohorts' in aux
        assert 'collections' in aux
        assert 'payments' in aux
        assert aux['dpd_cohorts'] is not None
        assert aux['collections'] is not None


# ── Helper Tests ─────────────────────────────────────────────────────────────

class TestHelpers:
    def test_safe_nan(self):
        assert _safe(float('nan')) is None

    def test_safe_inf(self):
        assert _safe(float('inf')) is None

    def test_safe_int(self):
        assert _safe(np.int64(42)) == 42

    def test_safe_float(self):
        result = _safe(np.float64(3.14159))
        assert isinstance(result, float)
        assert round(result, 4) == 3.1416

    def test_filter_by_date(self, df):
        filtered = filter_aajil_by_date(df, '2024-01-01')
        assert len(filtered) < len(df)
        assert filtered['Invoice Date'].max() <= pd.Timestamp('2024-01-01')

    def test_filter_none(self, df):
        filtered = filter_aajil_by_date(df, None)
        assert len(filtered) == len(df)

    def test_bucket_industry(self, df):
        bucketed = _bucket_industry(df['Customer Industry'])
        unique = bucketed.unique()
        # Should have top-10 + Other + Unknown
        assert 'Unknown' in unique
        assert 'Other' in unique
        assert len(unique) <= 13


# ── Summary Tests ────────────────────────────────────────────────────────────

class TestSummary:
    def test_total_deals(self, df, aux):
        result = compute_aajil_summary(df, aux=aux)
        assert result['total_deals'] >= 1240

    def test_status_counts(self, df, aux):
        result = compute_aajil_summary(df, aux=aux)
        assert result['realised_count'] == 883
        assert result['accrued_count'] == 342
        assert result['written_off_count'] == 19

    def test_deal_type_counts(self, df, aux):
        result = compute_aajil_summary(df, aux=aux)
        assert result['emi_count'] == 641
        assert result['bullet_count'] == 603

    def test_customer_count(self, df, aux):
        result = compute_aajil_summary(df, aux=aux)
        assert result['total_customers'] == 227

    def test_collection_rate(self, df, aux):
        result = compute_aajil_summary(df, aux=aux)
        assert 0 < result['collection_rate'] < 1

    def test_hhi(self, df, aux):
        result = compute_aajil_summary(df, aux=aux)
        assert 0 < result['hhi_customer'] < 1


# ── Traction Tests ───────────────────────────────────────────────────────────

class TestTraction:
    def test_volume_months(self, df, aux):
        result = compute_aajil_traction(df, aux=aux)
        assert len(result['volume_monthly']) > 40  # ~48 months

    def test_total_disbursed(self, df, aux):
        result = compute_aajil_traction(df, aux=aux)
        assert result['total_disbursed'] > 300_000_000  # SAR 300M+

    def test_deal_types(self, df, aux):
        result = compute_aajil_traction(df, aux=aux)
        assert 'EMI' in result['deal_types']
        assert 'Bullet' in result['deal_types']


# ── Delinquency Tests ────────────────────────────────────────────────────────

class TestDelinquency:
    def test_buckets(self, df, aux):
        result = compute_aajil_delinquency(df, aux=aux)
        assert len(result['buckets']) == 4

    def test_par_range(self, df, aux):
        result = compute_aajil_delinquency(df, aux=aux)
        assert 0 <= result['par_1_inst'] <= 1
        assert 0 <= result['par_2_inst'] <= 1

    def test_by_deal_type(self, df, aux):
        result = compute_aajil_delinquency(df, aux=aux)
        assert len(result['by_deal_type']) >= 2


# ── Collections Tests ────────────────────────────────────────────────────────

class TestCollections:
    def test_monthly(self, df, aux):
        result = compute_aajil_collections(df, aux=aux)
        assert len(result['monthly']) > 40

    def test_overall_rate(self, df, aux):
        result = compute_aajil_collections(df, aux=aux)
        assert 0 < result['overall_rate'] < 2  # Can exceed 1 if margin collected


# ── Concentration Tests ──────────────────────────────────────────────────────

class TestConcentration:
    def test_top_customers(self, df, aux):
        result = compute_aajil_concentration(df, aux=aux)
        assert len(result['top_customers']) == 15

    def test_hhi(self, df, aux):
        result = compute_aajil_concentration(df, aux=aux)
        assert 0 < result['hhi_customer'] < 1

    def test_industries(self, df, aux):
        result = compute_aajil_concentration(df, aux=aux)
        assert len(result['industries']) > 3


# ── Yield Tests ──────────────────────────────────────────────────────────────

class TestYield:
    def test_total_revenue(self, df, aux):
        result = compute_aajil_yield(df, aux=aux)
        assert result['total_revenue'] > 0

    def test_yield_range(self, df, aux):
        result = compute_aajil_yield(df, aux=aux)
        assert 0 < result['avg_total_yield'] < 1  # Should be ~0.10


# ── Loss Waterfall Tests ─────────────────────────────────────────────────────

class TestLossWaterfall:
    def test_waterfall_stages(self, df, aux):
        result = compute_aajil_loss_waterfall(df, aux=aux)
        assert len(result['waterfall']) == 4
        stages = [s['stage'] for s in result['waterfall']]
        assert 'Originated' in stages
        assert 'Written Off' in stages

    def test_written_off_count(self, df, aux):
        result = compute_aajil_loss_waterfall(df, aux=aux)
        wo = [s for s in result['waterfall'] if s['stage'] == 'Written Off'][0]
        assert wo['count'] == 19

    def test_loss_rate(self, df, aux):
        result = compute_aajil_loss_waterfall(df, aux=aux)
        assert 0 <= result['gross_loss_rate'] < 0.1  # <10% loss


# ── Validation Tests ─────────────────────────────────────────────────────────

class TestValidation:
    def test_runs_on_tape(self, df):
        result = validate_aajil_tape(df)
        assert result['total_rows'] >= 1240
        # Known tape issue: 1 row with missing Invoice Date
        assert len(result['critical']) <= 1

    def test_has_info(self, df):
        result = validate_aajil_tape(df)
        assert len(result['info']) > 0

    def test_status_in_info(self, df):
        result = validate_aajil_tape(df)
        info_text = ' '.join(result['info'])
        assert 'Realised' in info_text

    def test_catches_duplicates(self, df):
        # Inject a duplicate
        bad_df = pd.concat([df, df.head(1)], ignore_index=True)
        result = validate_aajil_tape(bad_df)
        assert len(result['critical']) > 0
        assert 'duplicate' in result['critical'][0].lower()
