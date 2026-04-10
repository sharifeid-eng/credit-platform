"""
core/legal_schemas.py
Pydantic models for legal document extraction output.

Defines the structured schema that the multi-pass Claude extraction engine
produces from facility agreement PDFs. Three tiers:
  Tier 1: Facility terms, eligibility, advance rates, covenants, concentration limits
  Tier 2: Events of default, reporting requirements, waterfall
  Tier 3: Risk flags, amendment changes
"""

from pydantic import BaseModel, Field
from typing import Optional


# ── Tier 1: Core Facility Terms ────────────────────────────────────────────

class FacilityTerms(BaseModel):
    facility_type: str = Field(description="revolving | term | warehouse")
    facility_limit: Optional[float] = Field(None, description="Total commitment amount")
    currency: Optional[str] = Field(None, description="ISO 4217 currency code")
    maturity_date: Optional[str] = Field(None, description="ISO date")
    commitment_period_end: Optional[str] = Field(None, description="ISO date")
    effective_date: Optional[str] = Field(None, description="ISO date")
    parties: list[str] = Field(default_factory=list, description="Named parties")
    governing_law: Optional[str] = None
    interest_rate_description: Optional[str] = None
    section_ref: Optional[str] = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)


class EligibilityCriterion(BaseModel):
    name: str = Field(description="Human-readable name, e.g. 'Maximum Aging'")
    description: str = Field(description="Full criterion text")
    parameter: Optional[str] = Field(None, description="facility_params key, e.g. 'ineligibility_age_days'")
    value: Optional[str | float | int] = Field(None, description="Threshold value")
    section_ref: Optional[str] = None
    page: Optional[int] = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)


class AdvanceRate(BaseModel):
    category: str = Field(description="default | UAE | Non-UAE | by_product | by_rating")
    rate: float = Field(description="Decimal rate, e.g. 0.90")
    condition: Optional[str] = Field(None, description="When this rate applies")
    section_ref: Optional[str] = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)


class ConcentrationTier(BaseModel):
    facility_min: Optional[float] = None
    facility_max: Optional[float] = None
    limit_pct: float


class ConcentrationLimit(BaseModel):
    name: str = Field(description="e.g. 'Single Borrower'")
    limit_type: str = Field(description="single_borrower | top_n | geographic | sector | single_receivable | single_payer | single_customer | extended_age")
    threshold_pct: float = Field(description="Decimal threshold, e.g. 0.10")
    tiered: Optional[list[ConcentrationTier]] = Field(None, description="Tiered thresholds by facility size")
    n_value: Optional[int] = Field(None, description="For top_n limits, the N value")
    section_ref: Optional[str] = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)


class FinancialCovenant(BaseModel):
    name: str = Field(description="e.g. 'PAR 30 Ratio'")
    covenant_type: str = Field(description="maintenance | incurrence")
    metric: Optional[str] = Field(None, description="facility_params key, e.g. 'par30_limit'")
    threshold: float = Field(description="Threshold value")
    direction: str = Field(description="<= | >= | < | >")
    test_frequency: Optional[str] = Field(None, description="monthly | quarterly | annual")
    cure_period_days: Optional[int] = None
    equity_cure_allowed: bool = False
    section_ref: Optional[str] = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)


# ── Tier 2: Risk and Obligations ──────────────────────────────────────────

class EventOfDefault(BaseModel):
    trigger: str = Field(description="Description of the trigger event")
    section_ref: Optional[str] = None
    cure_period_days: Optional[int] = None
    severity: str = Field(description="payment | covenant | cross_default | mac | operational")
    confidence: float = Field(0.0, ge=0.0, le=1.0)


class ReportingRequirement(BaseModel):
    name: str = Field(description="e.g. 'Borrowing Base Certificate'")
    frequency: str = Field(description="monthly | quarterly | annual | per_draw")
    due_days_after_period: Optional[int] = Field(None, description="Days after period end")
    description: Optional[str] = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)


class WaterfallStep(BaseModel):
    priority: int
    description: str
    applies_in: str = Field(description="normal | default | both")


# ── Tier 3: Amendment and Risk ────────────────────────────────────────────

class AmendmentChange(BaseModel):
    section: str
    field: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    material: bool = False


class RiskFlag(BaseModel):
    category: str = Field(description="missing_provision | below_market | unusual_term | deviation")
    description: str
    severity: str = Field(description="high | medium | low")
    recommendation: Optional[str] = None


# ── Aggregate Result ──────────────────────────────────────────────────────

class LegalExtractionResult(BaseModel):
    """Complete extraction output from a legal document."""

    # Tier 1
    facility_terms: FacilityTerms
    eligibility_criteria: list[EligibilityCriterion] = Field(default_factory=list)
    advance_rates: list[AdvanceRate] = Field(default_factory=list)
    concentration_limits: list[ConcentrationLimit] = Field(default_factory=list)
    covenants: list[FinancialCovenant] = Field(default_factory=list)

    # Tier 2
    events_of_default: list[EventOfDefault] = Field(default_factory=list)
    reporting_requirements: list[ReportingRequirement] = Field(default_factory=list)
    waterfall_normal: list[WaterfallStep] = Field(default_factory=list)
    waterfall_default: list[WaterfallStep] = Field(default_factory=list)

    # Tier 3
    risk_flags: list[RiskFlag] = Field(default_factory=list)

    # Metadata
    definitions: dict[str, str] = Field(default_factory=dict, description="Defined terms glossary")
    section_map: dict[str, str] = Field(default_factory=dict, description="Section number → title")
    overall_confidence: float = Field(0.0, ge=0.0, le=1.0)
    extraction_model: str = ""
    extraction_cost_usd: float = 0.0
    extracted_at: str = ""

    # Document metadata
    document_type: str = ""
    filename: str = ""
    page_count: int = 0


# ── Facility Params Mapping ───────────────────────────────────────────────

def extraction_to_facility_params(result: LegalExtractionResult) -> dict:
    """Convert extracted legal terms to facility_params dict format.

    This is the bridge between legal extraction and portfolio computation.
    Returns a dict compatible with facility_params.json structure.
    """
    params = {}
    sources = {}

    # Facility limit
    if result.facility_terms.facility_limit:
        params['facility_limit'] = result.facility_terms.facility_limit
        sources['facility_limit'] = 'document'

    # Advance rates
    ar_by_region = {}
    default_rate = None
    for ar in result.advance_rates:
        if ar.category == 'default':
            default_rate = ar.rate
        elif ar.category in ('UAE', 'Non-UAE'):
            ar_by_region[ar.category] = ar.rate
    if default_rate is not None:
        params['advance_rate'] = default_rate
        sources['advance_rate'] = 'document'
    if ar_by_region:
        params['advance_rates_by_region'] = ar_by_region
        sources['advance_rates_by_region'] = 'document'

    # Eligibility criteria
    for ec in result.eligibility_criteria:
        if ec.parameter and ec.value is not None:
            try:
                params[ec.parameter] = float(ec.value) if isinstance(ec.value, (int, float)) else ec.value
                sources[ec.parameter] = 'document'
            except (ValueError, TypeError):
                pass

    # Concentration limits
    for cl in result.concentration_limits:
        key_map = {
            'single_borrower': 'single_borrower_limit',
            'single_payer': 'single_payer_limit',
            'single_customer': 'single_customer_limit',
            'single_receivable': 'single_receivable_limit',
            'top_n': 'top10_limit',
            'extended_age': 'extended_age_limit',
        }
        key = key_map.get(cl.limit_type)
        if key:
            params[key] = cl.threshold_pct
            sources[key] = 'document'
        # Tiered limits
        if cl.tiered and cl.limit_type == 'single_borrower':
            params['conc_tiers'] = [
                {'facility_min': t.facility_min, 'facility_max': t.facility_max, 'limit_pct': t.limit_pct}
                for t in cl.tiered
            ]
            sources['conc_tiers'] = 'document'

    # Covenants
    for cov in result.covenants:
        if cov.metric:
            params[cov.metric] = cov.threshold
            sources[cov.metric] = 'document'

    # WAL threshold (from eligibility or covenant)
    for ec in result.eligibility_criteria:
        if ec.parameter == 'wal_threshold_days' and ec.value is not None:
            try:
                params['wal_threshold_days'] = int(ec.value)
                sources['wal_threshold_days'] = 'document'
            except (ValueError, TypeError):
                pass

    params['_sources'] = sources
    return params
