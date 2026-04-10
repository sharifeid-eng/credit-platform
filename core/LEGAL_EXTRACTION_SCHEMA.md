# Legal Extraction Schema

Companion document to the Analysis Framework (Section 16). Defines **what** to extract from facility agreement PDFs and **how** the extraction engine works.

## 1. Document Types

| Type | Code | Description |
|------|------|-------------|
| Credit Agreement | `credit_agreement` | Master facility agreement — primary extraction target |
| Amendment | `amendment` | Modification to existing agreement — tracked for version diffing |
| Security Agreement | `security_agreement` | Collateral and lien documentation |
| Fee Letter | `fee_letter` | Confidential pricing terms |
| Intercreditor | `intercreditor` | Priority agreement between lenders |
| Servicing Agreement | `servicing_agreement` | Collection and administration terms |

## 2. Extraction Architecture

### Multi-Pass Pipeline

| Pass | Target | Input Sections | Output Schema | Cost |
|------|--------|---------------|---------------|------|
| 1 | Definitions & Structure | TOC + Article I | `definitions`, `section_map` | ~$0.20 |
| 2 | Facility + Eligibility + Rates | Articles II-III + Schedules | `FacilityTerms`, `EligibilityCriterion[]`, `AdvanceRate[]` | ~$0.25 |
| 3 | Covenants + Concentration | Articles V-VI | `FinancialCovenant[]`, `ConcentrationLimit[]` | ~$0.25 |
| 4 | Default + Reporting + Waterfall | Articles VII-VIII | `EventOfDefault[]`, `ReportingRequirement[]`, `WaterfallStep[]` | ~$0.25 |
| 5 | Risk Assessment | All extracted terms | `RiskFlag[]` | ~$0.30 |

**Total: ~$1.25/document, one-time, cached forever.**

### Why Multi-Pass?

1. **Context window management** — Legal docs are 80-200 pages (60-80K tokens). Sending everything in one call would blow context limits and reduce extraction quality.
2. **Definitions-first** — Pass 1 extracts the glossary, which is prepended to all subsequent passes. This ensures terms like "Eligible Receivable" and "Advance Rate" are resolved to their contractual definitions.
3. **Targeted prompts** — Each pass has a focused JSON schema, reducing hallucination risk.
4. **Incremental caching** — If Pass 3 fails, Passes 1-2 results are still cached.

## 3. Field Schemas

### Tier 1: Core Facility Terms

#### FacilityTerms
| Field | Type | Description |
|-------|------|-------------|
| facility_type | string | "revolving" / "term" / "warehouse" |
| facility_limit | float | Total commitment amount |
| currency | string | ISO 4217 code |
| maturity_date | string | ISO date |
| effective_date | string | ISO date |
| parties | string[] | Named parties to the agreement |
| governing_law | string | Jurisdiction |
| interest_rate_description | string | Rate structure description |
| confidence | float | 0.0-1.0 |

#### EligibilityCriterion
| Field | Type | Maps To |
|-------|------|---------|
| name | string | Human-readable label |
| description | string | Full criterion text |
| parameter | string | `facility_params` key (e.g., `ineligibility_age_days`) |
| value | any | Threshold value |
| section_ref | string | Document section reference |
| confidence | float | 0.0-1.0 |

**Valid parameters:** `ineligibility_age_days`, `min_receivable_amount`, `max_receivable_amount`, `cross_default_threshold_pct`

#### AdvanceRate
| Field | Type | Maps To |
|-------|------|---------|
| category | string | "default" / "UAE" / "Non-UAE" / "by_product" / "by_rating" |
| rate | float | Decimal (0.90 = 90%) |
| condition | string | When this rate applies |
| confidence | float | 0.0-1.0 |

#### ConcentrationLimit
| Field | Type | Maps To |
|-------|------|---------|
| name | string | Human-readable label |
| limit_type | string | `single_borrower` / `single_payer` / `top_n` / etc. |
| threshold_pct | float | Decimal (0.10 = 10%) |
| tiered | object[] | For tiered limits: `[{facility_min, facility_max, limit_pct}]` |
| confidence | float | 0.0-1.0 |

#### FinancialCovenant
| Field | Type | Maps To |
|-------|------|---------|
| name | string | Human-readable label |
| metric | string | `facility_params` key (e.g., `par30_limit`) |
| threshold | float | Threshold value |
| direction | string | "<=" / ">=" |
| test_frequency | string | "monthly" / "quarterly" / "annual" |
| cure_period_days | int | Days to cure breach |
| confidence | float | 0.0-1.0 |

**Valid metrics:** `par30_limit`, `par60_limit`, `collection_ratio_limit`, `paid_vs_due_limit`, `cash_ratio_limit`, `wal_threshold_days`, `ltv_limit`

### Tier 2: Risk and Obligations

#### EventOfDefault
| Field | Type | Description |
|-------|------|-------------|
| trigger | string | Description of what causes default |
| severity | string | "payment" / "covenant" / "cross_default" / "mac" / "operational" |
| cure_period_days | int | Days to cure, null if no cure |
| confidence | float | 0.0-1.0 |

#### ReportingRequirement
| Field | Type | Description |
|-------|------|-------------|
| name | string | Report name |
| frequency | string | "monthly" / "quarterly" / "annual" / "per_draw" |
| due_days_after_period | int | Days after period end |

### Tier 3: Risk Flags

#### RiskFlag
| Field | Type | Description |
|-------|------|-------------|
| category | string | "missing_provision" / "below_market" / "unusual_term" / "deviation" |
| severity | string | "high" / "medium" / "low" |
| description | string | What the risk is |
| recommendation | string | Suggested action |

## 4. Confidence Grading

| Grade | Score | Meaning | Example |
|-------|-------|---------|---------|
| HIGH | >= 0.85 | Exact numeric value found in text | "Advance Rate shall be 90%" |
| MEDIUM | 0.70-0.84 | Inferred from context or schedule | Rate found in a table but not explicitly labeled |
| LOW | < 0.70 | Ambiguous, multiple interpretations possible | Reference to "applicable rate" without definition |

## 5. Facility Params Mapping

When extraction completes, `extraction_to_facility_params()` converts extracted terms to the `facility_params` dict format used by portfolio computation:

| Extraction | facility_params Key | Compute Function |
|------------|-------------------|-----------------|
| FacilityTerms.facility_limit | `facility_limit` | All portfolio functions |
| AdvanceRate[default] | `advance_rate` | `compute_klaim_borrowing_base()` |
| AdvanceRate[by region] | `advance_rates_by_region` | `compute_klaim_borrowing_base()` |
| EligibilityCriterion[max_aging] | `ineligibility_age_days` | `compute_klaim_borrowing_base()` |
| ConcentrationLimit[single_payer] | `single_payer_limit` | `compute_klaim_concentration_limits()` |
| ConcentrationLimit[top_n] | `top10_limit` | `compute_klaim_concentration_limits()` |
| FinancialCovenant[PAR30] | `par30_limit` | `compute_klaim_covenants()` |
| FinancialCovenant[PAR60] | `par60_limit` | `compute_klaim_covenants()` |
| FinancialCovenant[Collection] | `collection_ratio_limit` | `compute_klaim_covenants()` |
| FinancialCovenant[Paid vs Due] | `paid_vs_due_limit` | `compute_klaim_covenants()` |
| FinancialCovenant[Cash Ratio] | `cash_ratio_limit` | `compute_klaim_covenants()` |

## 6. 3-Tier Priority

When portfolio compute functions read facility params:

1. **Document-extracted** (from `data/{co}/{prod}/legal/*_extracted.json`) — baseline
2. **Manual override** (from `facility_params.json` or FacilityParamsPanel) — takes precedence
3. **Hardcoded default** (in compute function via `facility_params.get(key, default)`) — last fallback

The `_sources` dict tracks provenance: `{key: "document" | "manual"}`.

## 7. File Storage

```
data/{company}/{product}/legal/
  {document_name}.pdf              # Original uploaded PDF
  {document_name}_extracted.json   # Cached extraction result
  {document_name}_markdown.md      # Cached markdown (debug)
```

Extraction results are cached forever. Use `?refresh=true` or the re-extract endpoint to regenerate.
