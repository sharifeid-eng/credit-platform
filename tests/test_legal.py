"""
Tests for legal analysis module.

Tests Pydantic schemas, facility params mapping, compliance comparison,
and parser utilities. Does NOT test actual PDF parsing or Claude API calls.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.legal_schemas import (
    LegalExtractionResult, FacilityTerms, EligibilityCriterion,
    AdvanceRate, ConcentrationLimit, FinancialCovenant,
    EventOfDefault, ReportingRequirement, RiskFlag,
    extraction_to_facility_params,
)
from core.legal_compliance import (
    build_compliance_comparison,
    _compare_covenants,
    _compare_advance_rates,
    _compare_concentration,
)
from core.legal_parser import _normalize_section_key, _chunk_by_section


# ── Schema Validation ─────────────────────────────────────────────────────

class TestLegalSchemas:
    def test_facility_terms_minimal(self):
        ft = FacilityTerms(facility_type="revolving")
        assert ft.facility_type == "revolving"
        assert ft.facility_limit is None

    def test_facility_terms_full(self):
        ft = FacilityTerms(
            facility_type="revolving",
            facility_limit=50_000_000,
            currency="AED",
            maturity_date="2027-06-30",
            effective_date="2025-06-01",
            parties=["Klaim", "ACP Fund"],
            governing_law="DIFC",
            confidence=0.95,
        )
        assert ft.facility_limit == 50_000_000
        assert ft.confidence == 0.95

    def test_eligibility_criterion(self):
        ec = EligibilityCriterion(
            name="Maximum Aging",
            description="Receivable not older than 365 days",
            parameter="ineligibility_age_days",
            value=365,
            confidence=0.90,
        )
        assert ec.parameter == "ineligibility_age_days"

    def test_advance_rate(self):
        ar = AdvanceRate(category="UAE", rate=0.90, confidence=0.95)
        assert ar.rate == 0.90

    def test_concentration_limit_tiered(self):
        from core.legal_schemas import ConcentrationTier
        cl = ConcentrationLimit(
            name="Single Borrower",
            limit_type="single_borrower",
            threshold_pct=0.20,
            tiered=[
                ConcentrationTier(facility_min=0, facility_max=10_000_000, limit_pct=0.20),
                ConcentrationTier(facility_min=10_000_000, facility_max=20_000_000, limit_pct=0.15),
            ],
            confidence=0.85,
        )
        assert len(cl.tiered) == 2

    def test_financial_covenant(self):
        cov = FinancialCovenant(
            name="PAR 30",
            covenant_type="maintenance",
            metric="par30_limit",
            threshold=0.07,
            direction="<=",
            test_frequency="monthly",
            confidence=0.95,
        )
        assert cov.threshold == 0.07

    def test_event_of_default(self):
        eod = EventOfDefault(
            trigger="Failure to pay within 5 business days",
            severity="payment",
            cure_period_days=5,
            confidence=0.95,
        )
        assert eod.cure_period_days == 5

    def test_risk_flag(self):
        rf = RiskFlag(
            category="missing_provision",
            description="No dilution reserve",
            severity="high",
            recommendation="Add 2% reserve",
        )
        assert rf.severity == "high"

    def test_full_extraction_result(self):
        result = LegalExtractionResult(
            facility_terms=FacilityTerms(facility_type="revolving", facility_limit=50e6, currency="AED", confidence=0.9),
            eligibility_criteria=[EligibilityCriterion(name="Age", description="Max 365d", parameter="ineligibility_age_days", value=365, confidence=0.9)],
            advance_rates=[AdvanceRate(category="default", rate=0.90, confidence=0.95)],
            covenants=[FinancialCovenant(name="PAR30", covenant_type="maintenance", metric="par30_limit", threshold=0.07, direction="<=", confidence=0.9)],
            overall_confidence=0.90,
        )
        assert result.overall_confidence == 0.90
        assert len(result.covenants) == 1


# ── Facility Params Mapping ───────────────────────────────────────────────

class TestFacilityParamsMapping:
    def _make_result(self):
        return LegalExtractionResult(
            facility_terms=FacilityTerms(facility_type="revolving", facility_limit=50e6, currency="AED", confidence=0.9),
            eligibility_criteria=[
                EligibilityCriterion(name="Max Age", description="365 days", parameter="ineligibility_age_days", value=365, confidence=0.9),
            ],
            advance_rates=[
                AdvanceRate(category="default", rate=0.90, confidence=0.95),
                AdvanceRate(category="UAE", rate=0.90, confidence=0.9),
                AdvanceRate(category="Non-UAE", rate=0.85, confidence=0.85),
            ],
            concentration_limits=[
                ConcentrationLimit(name="Single Payer", limit_type="single_payer", threshold_pct=0.10, confidence=0.9),
                ConcentrationLimit(name="Top 10", limit_type="top_n", threshold_pct=0.50, confidence=0.85),
            ],
            covenants=[
                FinancialCovenant(name="PAR30", covenant_type="maintenance", metric="par30_limit", threshold=0.07, direction="<=", confidence=0.95),
                FinancialCovenant(name="Collection", covenant_type="maintenance", metric="collection_ratio_limit", threshold=0.25, direction=">=", confidence=0.90),
            ],
            overall_confidence=0.90,
        )

    def test_maps_facility_limit(self):
        params = extraction_to_facility_params(self._make_result())
        assert params['facility_limit'] == 50e6
        assert params['_sources']['facility_limit'] == 'document'

    def test_maps_advance_rates(self):
        params = extraction_to_facility_params(self._make_result())
        assert params['advance_rate'] == 0.90
        assert params['advance_rates_by_region']['UAE'] == 0.90
        assert params['advance_rates_by_region']['Non-UAE'] == 0.85

    def test_maps_eligibility(self):
        params = extraction_to_facility_params(self._make_result())
        assert params['ineligibility_age_days'] == 365.0

    def test_maps_concentration_limits(self):
        params = extraction_to_facility_params(self._make_result())
        assert params['single_payer_limit'] == 0.10
        assert params['top10_limit'] == 0.50

    def test_maps_covenants(self):
        params = extraction_to_facility_params(self._make_result())
        assert params['par30_limit'] == 0.07
        assert params['collection_ratio_limit'] == 0.25

    def test_sources_tracking(self):
        params = extraction_to_facility_params(self._make_result())
        assert all(v == 'document' for v in params['_sources'].values())


# ── Compliance Comparison ─────────────────────────────────────────────────

class TestComplianceComparison:
    def _extraction(self):
        return {
            'covenants': [
                {'name': 'PAR 30 Ratio', 'metric': 'par30_limit', 'threshold': 0.10, 'direction': '<=', 'confidence': 0.9},
            ],
            'concentration_limits': [
                {'name': 'Single Payer', 'limit_type': 'single_payer', 'threshold_pct': 0.10, 'confidence': 0.9},
            ],
            'advance_rates': [
                {'category': 'default', 'rate': 0.90, 'confidence': 0.95},
            ],
            'eligibility_criteria': [],
            'facility_terms': {},
            'filename': 'test.pdf',
            'extracted_at': '2026-01-01',
            'overall_confidence': 0.9,
        }

    def test_covenant_comparison_compliant(self):
        live = [{'name': 'PAR 30 Ratio', 'current': 0.05, 'threshold': 0.07, 'compliant': True}]
        result = _compare_covenants(self._extraction(), live)
        assert len(result) == 1
        assert result[0]['matched'] is True
        assert result[0]['breach_distance_pct'] is not None

    def test_covenant_comparison_breach(self):
        live = [{'name': 'PAR 30 Ratio', 'current': 0.12, 'threshold': 0.07, 'compliant': False}]
        result = _compare_covenants(self._extraction(), live)
        assert result[0]['breach_distance_pct'] < 0  # Negative = breaching

    def test_covenant_discrepancy(self):
        live = [{'name': 'PAR 30 Ratio', 'current': 0.05, 'threshold': 0.07, 'compliant': True}]
        result = _compare_covenants(self._extraction(), live)
        # Doc says 0.10, platform says 0.07 → discrepancy
        assert result[0]['discrepancy'] is True

    def test_full_comparison(self):
        live_covs = [{'name': 'PAR 30 Ratio', 'current': 0.05, 'threshold': 0.07, 'compliant': True}]
        result = build_compliance_comparison(self._extraction(), live_covenants=live_covs)
        assert 'summary' in result
        assert result['summary']['total_terms_compared'] >= 1


# ── Parser Utilities ──────────────────────────────────────────────────────

class TestParserUtils:
    def test_normalize_section_key(self):
        assert _normalize_section_key("DEFINITIONS AND INTERPRETATION") == "DEFINITIONS_AND_INTERPRETATION"
        assert _normalize_section_key("I. The Facility") == "THE_FACILITY"

    def test_chunk_by_section_basic(self):
        md = """# ARTICLE I — DEFINITIONS

Some definitions here.

# ARTICLE II — THE FACILITY

Facility terms here.
"""
        sections = _chunk_by_section(md)
        assert len(sections) >= 2

    def test_chunk_empty(self):
        sections = _chunk_by_section("")
        assert isinstance(sections, dict)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
