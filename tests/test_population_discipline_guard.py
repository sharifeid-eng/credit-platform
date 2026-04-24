"""
Framework §17 Population Discipline — audit guard meta-test.

Walks every covenant and concentration-limit dict emitted by the 3 live
compute functions (compute_silq_covenants, compute_klaim_covenants,
compute_klaim_concentration_limits, compute_concentration_limits) and
asserts the §17 contract: every output dict carries confidence AND
population fields in the allowed value sets.

Goal: prevent silent regression when a new covenant lands or an existing
one is refactored. If someone adds a new covenant dict without the §17
fields, this test fails with the covenant name in the error message so
the fix target is obvious.

Tapes are minimal synthetic — just enough to make the compute functions
emit all their covenant dicts; NOT checking numerical correctness here
(that's in the other test modules).
"""
import pandas as pd
import pytest


_VALID_CONFIDENCE = {'A', 'B', 'C'}
_ALLOWED_POPULATIONS_PREFIX = (
    'total_originated', 'active_outstanding', 'active_pv', 'completed_only',
    'clean_book', 'loss_subset', 'zombie_subset', 'snapshot_date_state',
    'specific_filter(', 'manual(',
)


def _population_allowed(pop: str) -> bool:
    """Matches against the §17 taxonomy with prefix allowance for
    `specific_filter(...)` and `manual(...)` wrapper-forms."""
    if not isinstance(pop, str):
        return False
    return pop.startswith(_ALLOWED_POPULATIONS_PREFIX)


def _make_silq_tape():
    today = pd.Timestamp('2026-03-01')
    rows = []
    for i in range(10):
        rows.append({
            'Deal ID': f'A{i}', 'Shop_ID': f'S{i}',
            'Disbursed_Amount (SAR)': 100_000,
            'Outstanding_Amount (SAR)': 80_000,
            'Overdue_Amount (SAR)': 0,
            'Total_Collectable_Amount (SAR)': 110_000,
            'Amt_Repaid': 50_000, 'Margin Collected': 10_000,
            'Principal Collected': 40_000, 'Shop_Credit_Limit (SAR)': 500_000,
            'Tenure': 12, 'Loan_Status': 'Active', 'Product': 'BNPL',
            'Disbursement_Date': today - pd.Timedelta(days=60),
            'Repayment_Deadline': today - pd.Timedelta(days=30),  # past → fills matured-period filter
            'Last_Collection_Date': today - pd.Timedelta(days=5),
            'Loan_Age': 60,
        })
    return pd.DataFrame(rows), today


def _make_klaim_tape():
    today = pd.Timestamp('2026-04-15')
    rows = []
    for i in range(30):
        rows.append({
            'Deal date': today - pd.Timedelta(days=30 + (i % 60)),
            'Status': 'Executed',
            'Purchase value': 100_000,
            'Purchase price': 95_000,
            'Collected till date': 50_000,
            'Denied by insurance': 5_000,
            'Pending insurance response': 20_000 if i % 3 == 0 else 0,
            'Expected total': 100_000,
            'Expected till date': 60_000,
            'Expected collection days': 90,
            'Collection days so far': 60,
            'Group': f'G{i % 5}',
            'Discount': 0.05,
        })
    return pd.DataFrame(rows), today


# ══════════════════════════════════════════════════════════════════════════════
# Covenant dicts — §17 shape contract
# ══════════════════════════════════════════════════════════════════════════════


class TestSILQCovenantShapeContract:
    """Every dict in compute_silq_covenants.covenants must carry
    confidence ∈ {A,B,C} and a population string matching the §17 taxonomy."""

    def test_silq_analysis_module_covenants(self):
        from core.analysis_silq import compute_silq_covenants
        df, today = _make_silq_tape()
        res = compute_silq_covenants(df, mult=1, ref_date=today)
        for cov in res['covenants']:
            assert 'confidence' in cov, f"SILQ covenant '{cov['name']}' missing 'confidence'"
            assert cov['confidence'] in _VALID_CONFIDENCE, \
                f"SILQ covenant '{cov['name']}' has invalid confidence={cov['confidence']!r}"
            assert 'population' in cov, f"SILQ covenant '{cov['name']}' missing 'population'"
            assert _population_allowed(cov['population']), \
                f"SILQ covenant '{cov['name']}' has non-§17 population={cov['population']!r}"

    def test_silq_portfolio_module_covenants(self):
        from core.portfolio import compute_covenants
        df, today = _make_silq_tape()
        res = compute_covenants(df, mult=1, ref_date=today)
        for cov in res['covenants']:
            assert 'confidence' in cov, f"SILQ(portfolio) covenant '{cov['name']}' missing 'confidence'"
            assert cov['confidence'] in _VALID_CONFIDENCE
            assert 'population' in cov, f"SILQ(portfolio) covenant '{cov['name']}' missing 'population'"
            assert _population_allowed(cov['population']), \
                f"SILQ(portfolio) '{cov['name']}' population={cov['population']!r}"


class TestKlaimCovenantShapeContract:
    def test_klaim_covenants(self):
        from core.portfolio import compute_klaim_covenants
        df, today = _make_klaim_tape()
        res = compute_klaim_covenants(df, mult=1, ref_date=today)
        for cov in res['covenants']:
            assert 'confidence' in cov, f"Klaim covenant '{cov['name']}' missing 'confidence'"
            assert cov['confidence'] in _VALID_CONFIDENCE, \
                f"Klaim covenant '{cov['name']}' has invalid confidence={cov['confidence']!r}"
            assert 'population' in cov, f"Klaim covenant '{cov['name']}' missing 'population'"
            assert _population_allowed(cov['population']), \
                f"Klaim covenant '{cov['name']}' has non-§17 population={cov['population']!r}"


class TestConcentrationLimitShapeContract:
    def test_silq_concentration_limits(self):
        from core.portfolio import compute_concentration_limits
        df, today = _make_silq_tape()
        res = compute_concentration_limits(df, mult=1, ref_date=today)
        for lim in res['limits']:
            assert 'confidence' in lim, f"SILQ limit '{lim['name']}' missing 'confidence'"
            assert lim['confidence'] in _VALID_CONFIDENCE
            assert 'population' in lim, f"SILQ limit '{lim['name']}' missing 'population'"
            assert _population_allowed(lim['population'])

    def test_klaim_concentration_limits(self):
        from core.portfolio import compute_klaim_concentration_limits
        df, today = _make_klaim_tape()
        res = compute_klaim_concentration_limits(df, mult=1, ref_date=today)
        for lim in res['limits']:
            assert 'confidence' in lim, f"Klaim limit '{lim['name']}' missing 'confidence'"
            assert lim['confidence'] in _VALID_CONFIDENCE
            assert 'population' in lim, f"Klaim limit '{lim['name']}' missing 'population'"
            assert _population_allowed(lim['population'])


class TestMethodToConfidenceRegression:
    """The method→confidence mapping is the single source of truth for
    covenant confidence inference. A regression here silently degrades
    grades across the platform, so freeze the known-good mapping."""

    def test_all_documented_methods_map_correctly(self):
        from core.analysis import method_to_confidence
        expected = {
            'direct': 'A', 'observed': 'A',
            'collection_days_so_far': 'A',
            'collection_days_so_far_with_curve_fallback': 'A',
            'age_pending': 'B', 'proxy': 'B', 'stable': 'B',
            'expected_collection_days': 'B', 'elapsed_only': 'B',
            'manual': 'B', 'empirical_proxy': 'B',
            'cumulative': 'C', 'derived': 'C', 'empirical_benchmark': 'C',
        }
        for method, grade in expected.items():
            assert method_to_confidence(method) == grade, \
                f"method_to_confidence('{method}') != '{grade}'"


class TestPopulationTaxonomyCoverage:
    """Ensure the §17 taxonomy prefix set itself is the expected 10 tokens.
    If someone adds a new population code (e.g. 'eligible_pool'), the
    platform-wide conversation starts here."""

    def test_taxonomy_prefix_set(self):
        from tests.test_population_discipline_guard import _ALLOWED_POPULATIONS_PREFIX
        assert set(_ALLOWED_POPULATIONS_PREFIX) == {
            'total_originated', 'active_outstanding', 'active_pv',
            'completed_only', 'clean_book', 'loss_subset', 'zombie_subset',
            'snapshot_date_state', 'specific_filter(', 'manual(',
        }


# ══════════════════════════════════════════════════════════════════════════════
# Top-level output dicts — partial §17 coverage
# ══════════════════════════════════════════════════════════════════════════════


class TestToplevelDictConfidenceFields:
    """Compute functions that introduced §17 dict-level (not per-entry)
    confidence fields must continue to emit them. Spot-checks the
    highest-risk rollout candidates."""

    def test_aajil_yield_dict_confidence_present(self):
        from core.analysis_aajil import compute_aajil_yield, C_INVOICE_DATE
        import pandas as pd
        today = pd.Timestamp('2026-04-15')
        df = pd.DataFrame([{
            'Transaction ID': 'T1', 'Deal Type': 'EMI',
            'Invoice Date': today - pd.Timedelta(days=90),
            'Unique Customer Code': 1,
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
            'Total Yield %': 22.0, 'Admin Fee %': 1.0,
            'Deal Tenure': 4.5, 'Customer Industry': 'Manufacturing',
            'Principal Amount': 100_000,
            'Expected Completion': today + pd.Timedelta(days=30),
        }])
        res = compute_aajil_yield(df, mult=1)
        assert res['yield_confidence']['avg_total_yield'] == 'B'
        assert res['yield_confidence']['avg_total_yield_realised'] == 'A'
        assert res['yield_confidence']['avg_total_yield_active']   == 'A'

    def test_aajil_collections_dict_declares_populations(self):
        from core.analysis_aajil import compute_aajil_collections
        today = pd.Timestamp('2026-04-15')
        df = pd.DataFrame([{
            'Transaction ID': 'R1', 'Deal Type': 'EMI',
            'Invoice Date': today - pd.Timedelta(days=180),
            'Unique Customer Code': 1,
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
            'Deal Tenure': 4.5, 'Customer Industry': 'Mfg',
            'Principal Amount': 100_000,
            'Expected Completion': today - pd.Timedelta(days=30),
        }])
        res = compute_aajil_collections(df, mult=1)
        assert res['overall_rate_population'] == 'total_originated'
        assert res['overall_rate_realised_population'] == 'completed_only'
        assert res['overall_rate_clean_population'] == 'clean_book'
        # Each has a confidence grade
        assert res['overall_rate_confidence'] in _VALID_CONFIDENCE
        assert res['overall_rate_realised_confidence'] in _VALID_CONFIDENCE
        assert res['overall_rate_clean_confidence'] in _VALID_CONFIDENCE
