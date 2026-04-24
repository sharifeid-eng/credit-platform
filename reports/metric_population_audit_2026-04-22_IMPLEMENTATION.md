# Audit Implementation Summary — 2026-04-24
# reports/metric_population_audit_2026-04-22.md

Implementation of the 2026-04-22 metric-population audit (commit `4e14b59`).
All 11 commits on branch `claude/objective-mendel-7c5b74` from `4e14b59`
through `ab5773e`, no pushes.

## Tally

| Bucket | Complete | Blocked | Notes |
|---|---|---|---|
| **P0 (covenant / correctness)** | **6 / 6** | 0 | — |
| **P1 (analyst views missing)** | **8 / 8** | 0 | — |
| **P2 (cleanup)** | **5 / 5** | 0 | All via docstring notes or additive dict fields |
| **UNCERTAIN** | **3 / 3** | 0 | Resolved per resolution matrix below |
| **Framework codification** | 1 / 1 | 0 | §17 added + renumber 17-21 → 18-22 |
| **Methodology pages** | 2 / 2 | 0 | `methodology_klaim.py` + `methodology_silq.py` |
| **Mind entry codified** | 1 / 1 | 0 | Both platform-standard AND user-spec field names |

**Tests:** 627 passing (baseline 548 + 79 new audit tests), 82 skipped (DB
tests with no DATABASE_URL), 0 warnings, 0 regressions across the entire
suite at every commit.

**Diff budget:** 2,173 implementation lines + 732 audit report lines =
2,905 total. Well within the 2,000-4,000 target, nowhere near the 6,000
ceiling.

## Commit-by-commit breakdown

| # | SHA | Title | Scope |
|---|---|---|---|
| 1 | `a4d0d34` | P0-6 confidence grading on every covenant + limit | SILQ + Klaim covenants + all concentration limits; new `method_to_confidence()` helper in `core/analysis.py`; 27 tests |
| 2 | `f782b44` | P0-1 SILQ covenant maturing-period doctrine | Documentation-only: inline comments + regression tests asserting closed-repaid loans contribute to denominator. 4 tests. Audit resolution: SILQ and Klaim Coll Ratio measure DIFFERENT things (not an inconsistency). |
| 3 | `ac93cdf` | P0-2 + P2-3 Aajil yield dual + PV-weighted deal-type margin | `compute_aajil_yield` — 3-population dual (all / realised / active) + confidence per view + PV-weighted margin rate on `by_deal_type`. 5 tests. |
| 4 | `eae201c` | P0-3 + P1-5 Aajil PAR — install-count declaration + lifetime dual | `compute_aajil_delinquency` — new `par_measurement` + `par_confidence='B'` + `par_primary` (days-based DPD from aux sheet, Confidence A) + `par_{1,2,3}_inst_lifetime` dual. 7 tests. |
| 5 | **(bundled into #1)** | P0-4 + P0-5 Klaim covenant confidence + Coll Ratio C grade | Klaim PAR30/PAR60 → Confidence B; Collection Ratio (cumulative) → Confidence C. Landed as part of #1 since it's the same cross-platform pass. |
| 6 | `f04523b` | P1-1 `separate_portfolio()` primitives for SILQ + Aajil | Two new helpers: `separate_silq_portfolio` (loss = Closed-with-outstanding OR active-DPD>90) + `separate_aajil_portfolio` (loss = Status='Written Off'). 8 tests. |
| 7 | `0eb466a` | P1-2 Aajil Operational WAL + stale classifier | `classify_aajil_deal_stale` (3 rules + any_stale) + `compute_aajil_operational_wal` (clean-book PV-weighted + realized WAL). Confidence B (direct) / C (elapsed_only degraded mode). 10 tests. |
| 8 | `def244a` | P1-3 SILQ collections dual + P1-4 Aajil collections dual | SILQ `repayment_rate_realised` (completed_only); Aajil `overall_rate_realised` + `overall_rate_clean` with population + confidence tags. 7 tests. |
| 9 | `58f8ca5` | P1-6 Cohort clean dual + P1-7 + P1-8 + all P2 + all UNCERTAIN | Bundle: Klaim `compute_cohorts.collection_rate_clean/denial_rate_clean`; Tamara structural_data_limitation; SILQ summary PAR labels; stress test population declaration; loss_triangle/silq_cohort_loss_waterfall docstring cleanup; Tamara heatmap scale_type note; Aajil HHI clean-book dual. 11 tests. |
| 10 | `0dec8ae` | Codify §17 Population Discipline into Framework | NEW §17 in ANALYSIS_FRAMEWORK.md; renumber 17-21 → 18-22; FRAMEWORK_INDEX updated; LEGAL_EXTRACTION_SCHEMA.md ref updated; new methodology sections in methodology_klaim.py + methodology_silq.py. |
| 11 | `ab5773e` | Mark Mind entry `6e0978f7-…` codified | Platform-standard fields (codified_in_framework, codification_commit, codification_section, codified_at, codified_by) + user-spec alias fields (codified, codified_commit, codified_section) + promoted=true + audit_report ref + second_data_point_sources array. |

## UNCERTAIN resolutions

| # | Finding | Resolution |
|---|---|---|
| 1 | Tamara vintage heatmap percentile scale — flat or age-bucketed? | Kept flat (matches HSBC investor report IC-view semantics). Added `scale_type='flat_percentile_all_vintages'` + interpretation note to `_color_scale` so frontend/AI can disclose to analyst. Age-normalised variant deferred — no active consumer. |
| 2 | Klaim stress test on full book or clean book? | Kept on full book (intentional: facility exposure view). Added `population='total_originated'` + `confidence='B'` + `separation_note` pointing callers at `separate_portfolio(df)[0]` for clean-book stress. |
| 3 | Aajil HHI inclusion of WO customer principal? | Dual view. `hhi_customer` (total_originated, Confidence A) preserved + `hhi_customer_clean` added (clean_book = Realised+Accrued, Confidence B). Platform-wide HHI harmonisation (Klaim + SILQ) deferred to a separate task — no immediate analyst impact; Aajil is the WO-dominant case. |

## New tests (all in `tests/test_population_audit_2026_04_22.py`)

79 new tests spanning:

- **TestP06ConfidenceGradingMapping** (10) — `method_to_confidence()` helper
- **TestP06SILQCovenantsCarryConfidence** (4) — SILQ covenant schema
- **TestP06PortfolioPySILQCovenantsCarryConfidence** (2)
- **TestP06KlaimCovenantsCarryConfidence** (7) — Klaim covenant schema + dual WAL
- **TestP06KlaimConcentrationLimitsCarryConfidence** (3) — including single-payer B-vs-A logic
- **TestP06SILQConcentrationLimitsCarryConfidence** (1)
- **TestP01SILQCollectionRatioIncludesClosedLoans** (2) — closed-repaid must contribute to denominator
- **TestP01KlaimCollRatioDifferentDefinition** (2) — locks in method=cumulative (C) vs direct (A)
- **TestP02AajilYieldDual** (5) — realised rate, active rate, blended lower, BC, PV-weighted
- **TestP03AajilPARMeasurementSemantics** (3) — measurement, confidence=B, populations
- **TestP15AajilPARLifetimeDual** (2) — lifetime < active, numerator invariant
- **TestP03AajilPARPrimarySurfacesWhenAuxPresent** (2) — None without aux, populated with aux
- **TestP11SeparateSilqPortfolio** (4) — partitioning
- **TestP11SeparateAajilPortfolio** (4) — partitioning
- **TestP12AajilStaleClassifier** (4) — 3 rules + union
- **TestP12AajilOperationalWAL** (6) — confidence grading, populations, degraded mode
- **TestP13SILQCollectionsDual** (3) — realised rate closed-only
- **TestP14AajilCollectionsDual** (4) — 3 populations with synthetic tape
- **TestP16KlaimCohortsCleanDual** (3) — blended vs clean per vintage
- **TestP17TamaraPopulationDeclaration** (1) — structural_data_limitation surface
- **TestP18SILQSummaryPopulationLabels** (2)
- **TestU3AajilHHIDual** (3) — clean HHI differs from blended
- **TestU2KlaimStressTestPopulation** (2)

## Backwards compatibility

Every pre-existing dict key is preserved verbatim. New fields are additive.
Frontend code that reads only `avg_total_yield` (pre-existing) keeps
rendering the blended value; code that wants the realised-only view now
has `avg_total_yield_realised` to consume directly.

Per user's binding rule: "renamed X→Y, both populated for compat; next
cleanup session removes X" — applicable once a next-session cleanup pass
audits which dual-view fields are the IC-facing primary and relabels the
blended ones as `{field}_blended` (or similar). This session does not do
the relabel; it ships the duals.

## Files touched

- `core/analysis.py` — `method_to_confidence` helper; `compute_cohorts`
  clean dual; `compute_stress_test` + `compute_loss_triangle` docstrings
- `core/analysis_silq.py` — covenant confidence/population; collections
  dual; `separate_silq_portfolio` primitive; `compute_silq_cohort_loss_waterfall`
  docstring
- `core/analysis_aajil.py` — yield dual + PV-weighted; PAR measurement
  declaration + lifetime dual + par_primary; summary HHI dual;
  `classify_aajil_deal_stale`, `compute_aajil_operational_wal`,
  `separate_aajil_portfolio` primitives; collections 3-population dual
- `core/analysis_tamara.py` — vintage heatmap scale_type; summary
  structural_data_limitation
- `core/portfolio.py` — Klaim + SILQ covenant confidence/population;
  Klaim + SILQ limit confidence/population; Collection Ratio doctrine
  note; import of `method_to_confidence`
- `core/ANALYSIS_FRAMEWORK.md` — NEW §17 Population Discipline;
  renumber 17-21 → 18-22
- `core/FRAMEWORK_INDEX.md` — Section Map; Core Principles list (10→12)
- `core/LEGAL_EXTRACTION_SCHEMA.md` — Section 16 → 18 stale reference
- `core/methodology_klaim.py` — NEW Population & Confidence Declarations
  static section
- `core/methodology_silq.py` — same pattern, plus order bump for Currency
- `data/_master_mind/framework_evolution.jsonl` — entry 6e0978f7-… marked
  codified
- `tests/test_population_audit_2026_04_22.py` — 79 new tests

## New Mind entries

None written this session beyond the existing 6e0978f7 entry being
marked codified. Three Aajil-specific lessons surfaced during
implementation would be good next-session `/thesis` or Company Mind
entries:

1. **Aajil data note:** EMI deals (51% by count) show ~22% underwritten
   yield vs Bullet deals' ~20% (all 19 WO are Bullet); yield dual view
   now exposes this structurally.
2. **Aajil PAR disclosure:** 3+ installments overdue correlates strongly
   with Written-Off progression (2/2 examples in synthetic tape match
   the audit pattern). Operational WAL's `overdue_dominant_active` rule
   catches this before formal write-off.
3. **SILQ Collection Ratio cert reconciliation:** Dec 2025 cert 95.53%
   matches `df`-filter (all statuses) method; deviating to
   active-only would produce a different number. This is now locked in
   by regression test `TestP01SILQCollectionRatioIncludesClosedLoans`.

These are not yet written to Company Mind JSONL files — follow-up
through `/thesis` slash commands would be the right path.

## Known follow-ups (not blocking this audit)

1. **SILQ `classify_silq_deal_stale`** — Framework §17 suggests every
   asset class should have its own stale classifier. SILQ's
   `separate_silq_portfolio` handles the clean/loss split but the
   full 3-rule classifier (like Klaim's `classify_klaim_deal_stale`
   and Aajil's `classify_aajil_deal_stale`) isn't implemented yet. Low
   priority — SILQ has no stuck-active equivalent issue today.

2. **Platform-wide HHI harmonisation** — UNCERTAIN 3 was resolved for
   Aajil only. Klaim and SILQ HHI are still `total_originated` only.
   Deferred to a separate task per audit P2 classification.

3. **Aajil methodology page** — Aajil doesn't yet have a
   `core/methodology_aajil.py` structured methodology file (uses inline
   dashboard rendering). Next `/extend-framework` pass could bring Aajil
   methodology inline with the SILQ/Klaim pattern.

4. **Frontend disclosure** — Every new `confidence` + `population` field
   is carried through compute outputs but not yet surfaced on dashboard
   KPI cards. A `KpiCard` prop (`confidence`, `populationTooltip`) +
   subtle badges (A/B/C) would close the analyst-visibility loop. No
   backend work needed — this is a pure frontend task.
