# Metric Population & Denominator Audit
# Session 30 follow-up — 2026-04-22

## Executive summary

**Audit scope:** 5 companies (Klaim, SILQ, Aajil, Tamara, Ejari), 6 compute
files (`core/analysis.py`, `core/analysis_silq.py`, `core/analysis_aajil.py`,
`core/analysis_tamara.py`, `core/analysis_ejari.py`, `core/portfolio.py`). 52
public compute functions surfaced across the three live-tape companies plus
Tamara's enrichment pipeline. Ejari (read-only ODS parser) has no live
computation — audited for completeness only.

**Findings:** 6 P0 gaps (covenant correctness / confidence-grading), 8 P1 gaps
(missing dual views that analysts would likely want), 5 P2 gaps (cleanup /
harmonisation), 3 [UNCERTAIN] items flagged for user review.

**Core pattern confirmed on a second asset class.** Session 30's Klaim WAL
duality (148d covenant-Active / 137d book-wide / 79d operational / 65d
realized) surfaced the population-mismatch class. This audit found the same
class in SILQ (covenant Collection Ratio denominator ambiguity) and in Aajil
(yield averaged over Written-Off deals, no completed-only dual; PAR
computed off install-count proxy without confidence declaration). The
Framework codification candidate `6e0978f7-…` was blocked on "second data
point" — this audit provides two independent ones (SILQ + Aajil), and the
candidate is ready to promote (proposed replacement text in Section 4).

**Most consequential finding:** Confidence grading (Framework Section 10) is
mandatory on paper but only Klaim WAL actually carries the grade on its
output dict. Every other covenant + metric across the 5 companies relies on
the reader's inference. This is a discipline gap, not a correctness gap
yet — but the same kind of silent-assumption failure that surfaced the
`separate_portfolio()` need in session 24 is what lets confidence drift
propagate into IC memos.

---

## 1. Per-company audit tables

Population codes used throughout:

- `total_originated` — every row in df, irrespective of status (lifetime
  denominator; what the facility has ever touched)
- `active_outstanding` — Status≠Completed/Closed, outstanding-weighted
  (covenant / live-monitoring denominator)
- `active_pv` — Status≠Completed/Closed, face-value-weighted
- `completed_only` — Status=Completed/Closed (realised / closed-book view)
- `clean_book` — `total_originated` minus loss-subset (Klaim session 30
  separation primitive); not yet generalised to SILQ/Aajil
- `loss_subset` — defaulted deals (Klaim: Denied > 50% PV; SILQ: DPD>90 or
  charge-off; Aajil: Status='Written Off')
- `zombie_subset` — Klaim session 30: stuck_active ∪ denial_dominant_active
  ∪ loss_completed
- `snapshot_date_state` — value reflects balance at tape snapshot, not a
  rate or ratio; included for bookkeeping
- `specific_filter(…)` — a bespoke filter not in the standard buckets
  (e.g., SILQ covenant's "maturing in period" subset)

### Klaim (core/analysis.py + core/portfolio.py)

| Function | Numerator | Denominator | Population | Confidence | Dual? | Gap / flag |
|---|---|---|---|---|---|---|
| `compute_summary` (analysis.py:59) | Σ PV, Σ Collected, Σ Denied, Σ Pending | Σ PV | total_originated | A | N | No confidence field on dict. Serves Overview card. |
| `compute_deployment` (analysis.py:106) | Monthly Σ PV split new/repeat | — | total_originated | A | N | Snapshot-date state; rate-free. |
| `compute_deployment_by_product` (analysis.py:128) | Monthly Σ PV by Product | — | total_originated | A | N | Rate-free. |
| `compute_collection_velocity` (analysis.py:161) | Timing buckets from completed deals + monthly collection_rate on all deals | Σ PV per month | Mixed: `completed_only` (buckets/days_to_collect, avg_days, median_days) + `total_originated` (monthly rates) | A | Partial | Denominator for monthly rate is PV of all vintage deals; for timing buckets is completed-only. Labels should make this explicit. |
| `compute_denial_trend` (analysis.py:237) | Monthly Σ Denied | Σ PV monthly | total_originated | A | N | — |
| `compute_cohorts` (analysis.py:257) | Per-vintage: Σ PV / Σ Collected / Σ Denied / realised_margin (completed_only) | Σ PV (all) for rates; Σ PP completed for margin | total_originated for rates; completed_only for margin | A | Partial | Rates blend active + completed per vintage; loss-subset not separated. See P1 gap 6. |
| `compute_actual_vs_expected` (analysis.py:316) | Cumulative Σ Collected, Σ Expected | Σ PV total | total_originated | A | N | — |
| `compute_ageing` (analysis.py:397) | Active outstanding per health bucket and ageing bucket | `total_outstanding` (active, outstanding-weighted) | **active_outstanding** | A | Y (face_value shown for reference) | Good dual (health uses outstanding as primary, shows face_value as reference). |
| `compute_revenue` (analysis.py:465) | Σ Gross revenue, fees, collected; realised_revenue = gross × coll/pv | Σ PV | total_originated | A | N | Monthly rates use total; mixes active + completed. |
| `compute_concentration` (analysis.py:518) | Per-Group/Provider/Product Σ PV | Σ PV total | total_originated | A | N | No active-only version; covenant-side lives in portfolio.py. |
| `compute_returns_analysis` (analysis.py:589) | portfolio expected_margin (all); realised_margin (completed_only); margins on completed per month/band/segment | Σ PP (all / completed_only) | Mixed: `total_originated` (expected) + `completed_only` (realised, per-band margins, per-biz-type margins) | A | **Y** | Exemplar — both populations reported side-by-side. This is the pattern other yield functions should mirror. |
| `compute_dso` (analysis.py:820) | Curve-based true-DSO on completed deals | Σ Collected × weights on completed | completed_only | A (curves) / B (proxy) | N | Graceful when curves missing. DSO Operational has direct/proxy subtypes with different confidence. |
| `compute_hhi` (analysis.py:928) | Σ PV per Group/Provider/Product, squared shares | Σ PV total | total_originated | A | N | Separate `compute_hhi_for_snapshot` for time-series. |
| `compute_denial_funnel` (analysis.py:958) | Total → Collected → Pending → Denied → Provisioned | Σ PV | total_originated | A | N | — |
| `compute_stress_test` (analysis.py:990) | Top-N group shock × collected | Σ PV total | total_originated | B (scenario-based) | N | No separation — stressed loss ON top of already-realised loss is double-counted for dominated groups. [UNCERTAIN — user review]. |
| `compute_expected_loss` (analysis.py:1090) | PD (completed_only), LGD (completed_only), EAD (active_pv) | — | Mixed by design: PD/LGD = completed_only, EAD = active_pv | B (PD inferred, LGD observed, EAD current) | Y (PV-adjusted LGD) | Good — multi-population by construction. PV-adjusted LGD = C. |
| `compute_facility_pd` (analysis.py:1171) | Markov bucket transitions over all df + calibration from completed | Total deal count | Mixed: distribution = total_originated; transition calibration = completed_only | B | N | Method field = direct/proxy. Confidence implicit. |
| `compute_loss_triangle` (analysis.py:1280) | Per-vintage cumulative denial / collection / pending | Σ PV per vintage | total_originated | A | N | Largely redundant with `compute_vintage_loss_curves`. See P2 gap 1. |
| `compute_group_performance` (analysis.py:1319) | Per-group Σ PV, Σ Collected, Σ Denied, DSO | Σ PV per group | total_originated | A | N | Group-level collection rate blends active + completed; no dual. |
| `compute_collection_curves` (analysis.py:1367) | Per-vintage expected/actual at 30d intervals | Σ PV per vintage | total_originated | A | N | Rate-free data. |
| `compute_owner_breakdown` (analysis.py:1433) | Per-owner Σ PV, Σ Collected, Σ Denied | Σ PV total | total_originated | A | N | — |
| `compute_vat_summary` (analysis.py:1476) | Σ VAT assets + VAT fees | — | total_originated | A | N | Snapshot-state totals. |
| `compute_par` (analysis.py:1533) | PAR amounts at DPD ≥30/60/90 | **Dual**: Active = `active_outstanding`; Lifetime = `total_originated` (PV) | **Dual by design** (Active + Lifetime) | B (`method=direct`: expected_days; `method=expected`: shortfall proxy; `method=derived`: empirical benchmark) | **Y** | Session 30 duality pattern — headline example of the doctrine this audit is promoting. |
| `compute_dtfc` (analysis.py:1724) | Days to first positive cash per deal | count of deals with any cash | `total_originated` (curves method); `completed_only` (estimated method) | A (curves) / C (estimated) | N | Method disclosed in output. |
| `compute_klaim_cash_duration` (analysis.py:1817) | Σ (bucket_t × t × PV) / Σ PV (PV-weighted, per-deal Macaulay-style) | — | **Dual**: `duration_days` = total_originated; `duration_days_completed_only` = completed_only | A (completed) / B (all-deals, partial-life) | **Y** | Session 30 addition — second pre-existing dual-view example. |
| `compute_cohort_loss_waterfall` (analysis.py:1935) | Per-vintage Originated → Gross Default → Recovery → Net Loss | Σ PV per vintage | total_originated (but slices loss_subset for recovery/default numerator) | A | N | Correct population for its purpose (reports defaults against origination). |
| `compute_recovery_analysis` (analysis.py:2002) | Collected on defaulted deals | Σ Denied on defaulted deals | **loss_subset** | A | N | — |
| `compute_vintage_loss_curves` (analysis.py:2054) | Per-vintage cumulative denial / collection | Σ PV per vintage | total_originated | A | N | — |
| `compute_underwriting_drift` (analysis.py:2102) | Per-cohort avg deal_size, discount, new_pct, outcome collection/denial rates | Cohort size for mix; completed_only for outcome rates | Mixed: total_originated (origination metrics); completed_only (outcome metrics) | A | N | Drift flags compare 3M recent vs 6M prior; denominator implicit. |
| `compute_segment_analysis` (analysis.py:2169) | Per-segment Σ PV, outstanding, Collected, Denied | Σ originated per segment | total_originated | A | N | — |
| `compute_collections_timing` (analysis.py:2262) | Monthly timing-bucket distribution from curves | Σ PV per month | total_originated | A | N | — |
| `compute_seasonality` (analysis.py:2326) | YoY origination volume + collection rate by calendar month | — | total_originated | A | N | Index is across-years avg / overall avg. |
| `compute_loss_categorization` (analysis.py:2381) | Categorise defaulted deals: provider_issue / coding_error / credit | Σ denied on loss_subset | **loss_subset** | C (heuristic) | N | — |
| `compute_methodology_log` (analysis.py:2436) | Meta: corrections, column availability, proxy declarations | — | — | — | — | Carries `confidence: 'B'` on close_date_proxy + stale_classification — exemplar for the pattern this audit recommends. |
| `separate_portfolio` (analysis.py:2569) | Returns (clean_df, loss_df) | — | **Primitive helper** | A | Y | Session 25 addition; not a metric. |
| `classify_klaim_deal_stale` (analysis.py:2638) | Returns 3 stale masks + union | — | **Primitive helper** | B (threshold judgement) | — | Session 30 addition; not a metric. |
| `compute_klaim_operational_wal` (analysis.py:2701) | PV-weighted age across `clean_book` | Σ PV of clean_book | **clean_book** (non-stale) | B (filter judgement); C (elapsed-only fallback) | **Y** (operational + realized) | Session 30 — the metric this audit generalises from. |
| `compute_klaim_stale_exposure` (analysis.py:2806) | Σ PV of stale deals + category breakdown | Σ PV total | **zombie_subset** | B | N | Session 30 — L5 forward signal. |
| `compute_hhi_for_snapshot` (analysis.py:2926) | Single-snapshot HHI per dim | Σ PV total | total_originated | A | N | Feeds time-series endpoint. |
| `compute_cdr_ccr` (analysis.py:2948) | Annualised default / collection rate by vintage | Σ originated per vintage, time-adjusted | total_originated | A | N | Seasoning filter skips <3 months. |
| `_klaim_wal_total` (portfolio.py:644) | Σ (age × PV) / Σ PV across active + completed | Σ PV total | `total_pv` (book-wide) | A (active rows) / B (completed-row proxy) | Y (carries method tag + confidence) | Session 30 — dual to `wal_active` in `compute_klaim_covenants`. |
| `compute_klaim_borrowing_base` (portfolio.py:729) | Waterfall: Total AR → Ineligible → Concentration → Advance rate | Σ outstanding on active | **active_outstanding** → eligible_outstanding | A | N | Populated via 3-tier facility_params merge. |
| `compute_klaim_concentration_limits` (portfolio.py:850) | 5 limits: single-receivable, top-10, single-customer, single-payer, extended-age | Σ outstanding on active | **active_outstanding** | A | N | Extended Age uses 70-90d window; ties into WAL carve-out. |
| `compute_klaim_covenants` (portfolio.py:1031) | 7 covenants: Cash, WAL (dual-path), PAR30, PAR60, Collection Ratio, Paid vs Due, Parent Cash | Active outstanding (PAR, WAL); active in period (Coll Ratio, Paid vs Due); manual (Cash covenants) | Mixed: active_outstanding (PAR, WAL); `specific_filter(active in period)` (Coll Ratio); specific_filter (Paid vs Due temporal); manual (cash covenants) | WAL is tagged A/B; others **no confidence field** | Partial (WAL carries dual) | Each covenant carries `method` and `eod_rule`. See P0 gap 4 + 5. |
| `annotate_covenant_eod` (portfolio.py:1367) | Consecutive-breach annotation | — | **Primitive helper** | — | — | Honors method changes (session 30 addition). Not a metric. |
| `compute_borrowing_base` (portfolio.py:46, SILQ) | Same structure as Klaim but keyed to SILQ columns | active_outstanding | active_outstanding → eligible | A | N | Used by SILQ too. |
| `compute_concentration_limits` (portfolio.py:171, SILQ) | 4 limits: single-borrower (tiered), top-5, product mix, weighted tenure | active_outstanding | active_outstanding | A | N | No confidence field. |
| `compute_covenants` (portfolio.py:322, SILQ) | 5 covenants: PAR30, PAR90, Collection Ratio (3M avg), Repayment at Term, LTV | active_outstanding (PAR); `specific_filter(maturing in period)` (Coll Ratio + RAT); manual (LTV) | Mixed | — | N | **Note: uses `df` (all loans) for maturing-period filter, NOT `active` — see P0 gap 1**. |

### SILQ (core/analysis_silq.py)

| Function | Numerator | Denominator | Population | Confidence | Dual? | Gap / flag |
|---|---|---|---|---|---|---|
| `compute_silq_summary` (analysis_silq.py:92) | Σ disbursed, Σ outstanding, Σ repaid; PAR (active, GBV-weighted); HHI (all) | Σ disbursed for rates; active_outstanding for PAR; Σ disbursed for HHI | Mixed | A (observed) | Partial | Serves Overview KPIs. No dual for collection_rate (total only). |
| `compute_silq_delinquency` (analysis_silq.py:158) | DPD buckets; Σ outstanding per bucket; PAR 30/60/90; top overdue shops | active_outstanding | **active_outstanding** | A (direct DPD via Repayment_Deadline) | N | Monthly trend by disbursement month uses active subset. No lifetime PAR dual. |
| `compute_silq_collections` (analysis_silq.py:235) | Σ repaid, Σ collectable, Σ margin, Σ principal; by product | Σ collectable (= repayment rate) | total_originated | A | N | No completed-only dual. See P1 gap 3. |
| `compute_silq_concentration` (analysis_silq.py:290) | Per-shop Σ disbursed; credit-limit utilisation; product mix; size bands | Σ disbursed total | total_originated | A | N | Utilisation uses active outstanding against shop limit — single-population metric. |
| `compute_silq_cohorts` (analysis_silq.py:365) | Per-vintage: disbursed, repaid, outstanding, overdue, margin, avg_tenure, active PAR30 | Σ disbursed per vintage (rates); active subset per vintage (PAR) | Mixed: total_originated + active_outstanding (PAR column) | A | Partial | Rates blend closed + active per vintage. |
| `compute_silq_yield` (analysis_silq.py:433) | total_margin (all) + closed_margin (Closed only); by product / tenure / monthly | Σ disbursed (all + closed) | **Dual**: `margin_rate` (total) + `realised_margin_rate` (completed_only) | A | **Y** | Exemplar. Other functions should mirror. |
| `compute_silq_tenure` (analysis_silq.py:512) | Per-band Σ disbursed, collection_rate, active DPD rate, margin rate | — | Mixed: total_originated (size, margin); active_outstanding (DPD rates) | A | N | — |
| `compute_silq_borrowing_base` (analysis_silq.py:565) | Active outstanding waterfall; ineligible (DPD>60) + (concentration >20%) | active_outstanding | active_outstanding → eligible | A | N | 80% advance rate hardcoded here; `compute_borrowing_base` in portfolio.py is the richer version. Legacy? |
| `compute_silq_covenants` (analysis_silq.py:625) | PAR30, PAR90 (active, GBV-weighted), Collection Ratio (3M avg maturing), RAT (>3-6mo), LTV (partial) | Mixed: active_outstanding (PAR); `specific_filter(maturing in period)` (Coll Ratio + RAT on **full df** — see P0 gap 1); off-tape (LTV) | Mixed | **No confidence fields** | N | P0 gap 1 (denominator asymmetry vs Klaim) + P0 gap 6 (no confidence). |
| `compute_silq_seasonality` (analysis_silq.py:809) | YoY monthly disbursement + overdue_rate by vintage month | — | total_originated | A | N | — |
| `compute_silq_cohort_loss_waterfall` (analysis_silq.py:876) | Per-vintage: Originated → Gross Default (DPD>90) → Recovery → Net Loss | Σ disbursed per vintage | total_originated (slices loss_subset for default/recovery numerator) | A | N | Defines SILQ default as DPD>90 OR Closed (in comment), code only uses DPD>90 — minor inconsistency. |
| `compute_silq_underwriting_drift` (analysis_silq.py:951) | Per-vintage: avg_loan_size, avg_tenure, delinquency_rate, collection_rate; z-score drift flags | Vintage size / rolling 6-vintage norms | total_originated | A | N | — |
| `compute_silq_cdr_ccr` (analysis_silq.py:1042) | Annualised default (DPD>90 on active) + collection / Σ disbursed, by vintage | Σ disbursed per vintage | total_originated | A | N | Matches Klaim's CDR/CCR pattern. |

### Aajil (core/analysis_aajil.py)

| Function | Numerator | Denominator | Population | Confidence | Dual? | Gap / flag |
|---|---|---|---|---|---|---|
| `compute_aajil_summary` (analysis_aajil.py:92) | Σ principal, Σ realised, Σ receivable, Σ written_off, Σ margin, Σ fees, Σ overdue; customer HHI | Σ principal total (collection_rate); Σ principal total (HHI) | Mixed: total_originated (Σ totals, HHI); `specific_filter(Status='Accrued')` for overdue / active PAR fraction | A (observed) | N | **Gap**: HHI includes written-off customers' historical principal — see [UNCERTAIN] 3. |
| `compute_aajil_traction` (analysis_aajil.py:158) | Monthly Σ principal (vol); monthly Σ receivable (balance); growth stats | — | total_originated (volume); `snapshot_date_state` (receivable balance per origination month) | A | N | MoM / QoQ / YoY growth skips partial current month. |
| `compute_aajil_delinquency` (analysis_aajil.py:235) | Σ outstanding per overdue-installment bucket (0/1/2/3+); PAR_1_inst / PAR_2_inst / PAR_3_inst | active_outstanding (Status='Accrued'); Σ overdue amount | **active_outstanding**, but measured in **installments overdue, not days** | **B (proxy — no true DPD on tape)**, **not declared on dict** | N | **P0 gap 3** — label is PAR but denominator is install-count-based. Pre-computed DPD time series from aux sheet gives true DPD%, but main bucket is a proxy. |
| `compute_aajil_collections` (analysis_aajil.py:325) | Per-vintage: Σ principal, Σ realised, Σ receivable, collection_rate | Σ principal per vintage | total_originated | A | N | No completed-only dual — see P1 gap 4. |
| `compute_aajil_cohorts` (analysis_aajil.py:363) | Quarterly cohort: originated, realised, outstanding, overdue_amount, written_off_count, accrued_count, overdue_pct | Σ principal per quarter | total_originated (+ overdue_pct is active count / accrued count — mixed) | A | N | Labelled "Original Balance" — correct per methodology. |
| `compute_aajil_concentration` (analysis_aajil.py:474) | Per-customer / per-industry / per-deal-type Σ principal + HHI | Σ principal total | total_originated | A | N | Same WO-inclusion concern as summary. |
| `compute_aajil_underwriting` (analysis_aajil.py:532) | Per-quarter cohort: avg_deal_size, median, tenure, yields, EMI% | Σ principal per quarter | total_originated | A | N | No drift flags (SILQ has them). |
| `compute_aajil_yield` (analysis_aajil.py:566) | total_margin + total_fees; avg yields; per-deal-type / per-vintage | Σ principal total (for revenue_over_gmv); yield averaged across all deals | total_originated | A for observed Σ, **B for avg yield** (includes WO deals) | N | **P0 gap 2** — `avg_total_yield` averaged over all deals including WO; no completed-only / active-only dual. |
| `compute_aajil_loss_waterfall` (analysis_aajil.py:625) | Originated → Realised → Accrued → Written Off; per-vintage | Σ principal per vintage | total_originated + loss_subset (WO) | A | N | Correct for its purpose. |
| `compute_aajil_customer_segments` (analysis_aajil.py:667) | By deal_type / industry / customer-size: Σ principal, deal_count, collection_rate, overdue_pct | Σ principal per segment | total_originated | A | N | — |
| `compute_aajil_seasonality` (analysis_aajil.py:729) | YoY monthly origination volume + seasonal index | — | total_originated | A | N | — |

### Tamara (core/analysis_tamara.py)

Tamara is a data-room summary loader — no live tape computation. Values are
pre-computed upstream and delivered via JSON. Populations are declared by
the source (Deloitte FDD, HSBC reports, Tamara BP) rather than computed
here. Audit entries are about what this code surfaces to the dashboard.

| Function | Numerator | Denominator | Population | Confidence | Dual? | Gap / flag |
|---|---|---|---|---|---|---|
| `parse_tamara_data` (analysis_tamara.py:16) | Dispatch helper | — | — | — | — | — |
| `_enrich_overview` (analysis_tamara.py:39) | Pulls latest DPD total_pending + DPD distribution from FDD; facility limit; registered users | — | `snapshot_date_state` (latest month, outstanding AR) | A (observed from source) | N | current_rate = 1 - not_late/total, denominator = total DPD distribution (outstanding, latest month). |
| `_enrich_covenant_status` (analysis_tamara.py:87) | Parse HSBC trigger rows vs L1/L2/L3 thresholds | — | `specific_filter(HSBC reporting pool)` | A (source-declared) | N | Does not declare what is in HSBC's pool — report-level detail. |
| `_enrich_vintage_heatmap` (analysis_tamara.py:159) | Color-scale percentile bounds (p25, p75) over all vintages | — | total_originated (all vintages mixed) | A (data) / **B (interpretation — unseasoned vintages skew scale)** | N | See [UNCERTAIN] 1. |
| `_enrich_deloitte_summary` (analysis_tamara.py:193) | Pending trend, writeoff trend, latest DPD distribution from monthly series | — | `snapshot_date_state` per month | A | N | — |
| `_enrich_hsbc_summary` (analysis_tamara.py:236) | Report count, concentration time-series | — | `specific_filter(HSBC reporting)` | A | N | Only count, no denominator detail. |
| `_enrich_repayment_behavior` (analysis_tamara.py:262) | Per-stage / per-tier quarterly totals, current%, default% | `total_by_stage` per stage (from source) | source-declared pool (Q1 2026 snapshot, Tamara monthly reporting) | A | N | Denominator per stage, not global. |
| `get_tamara_summary_kpis` (analysis_tamara.py:380) | `total_pending` surfaced as `total_purchase_value`; HSBC report count as `total_deals` | — | `snapshot_date_state` (outstanding AR, point-in-time) | A | N | Labels `Outstanding AR` / `Reports` — honest. No originated view. See P1 gap 7. |

### Ejari (core/analysis_ejari.py)

Ejari has no live computation — pure ODS parser. The workbook declares
populations in its own sheet structure (Active vs Matured, Current vs
DPD buckets). `parse_ejari_workbook` surfaces values as-is; the frontend
renders them without recomputation.

| Function | Population | Confidence | Dual? | Gap / flag |
|---|---|---|---|---|
| `parse_ejari_workbook` (analysis_ejari.py:31) | Various per-sheet — Ejari team declared `active_loans` separately from `total_contracts`, PAR per bucket, etc. | A (source) | N | Parser preserves Ejari-side declarations; downstream code should propagate those labels. See P2 gap 4. |

---

## 2. Gap list (prioritized)

### P0 — covenant / correctness

**P0-1. SILQ covenant `Collection Ratio` + `Repayment at Term` use full
`df` for maturing-period filter, not `active`.** `core/analysis_silq.py:697`
and `:743` — the `mask = (df[C_REPAY_DEADLINE] >= window_start) &
(df[C_REPAY_DEADLINE] <= window_end)` predicate is applied to the entire
DataFrame, including Closed loans. Klaim's equivalent covenant in
`core/portfolio.py:1234` filters to `Status == 'Executed'`, which is
different semantics. One or both are wrong; at minimum the denominator
is not declared in the covenant dict. Closed loans in the maturing
period almost always pay in full, so the *number* tends to match the
certificate — but the covenant semantics (period-end cash conversion on
active pool) diverge. **Fix**: decide per covenant definition whether
`specific_filter(maturing in period)` means "all loans whose due date
fell in the period" (SILQ current) or "loans that were active at
period start and had due dates in the period" (Klaim current). Document
the choice in the covenant dict as `population` field. **File/lines**:
SILQ — `core/analysis_silq.py:697-707, 743-768`; Klaim —
`core/portfolio.py:1234-1239, 1275-1286`.

**P0-2. Aajil `compute_aajil_yield.avg_total_yield` averages over all
deals including Written-Off deals.** `core/analysis_aajil.py:574, 609`.
The yield KPI reads as "portfolio yield" on the IC card, but with 19
Written-Off deals (1.5% count) still contributing their (often zero or
below-zero) realised yield to the average, the metric is neither a
realised-yield-on-closed-book view nor a pure underwritten-yield view.
Compare SILQ `compute_silq_yield`
(`core/analysis_silq.py:436-442`) which explicitly reports `margin_rate`
(total) alongside `realised_margin_rate` (Closed-only). **Fix**: add a
completed-only / active-only dual to Aajil's yield. The Aajil data has
Status='Realised' for cleanly-resolved deals — mirror SILQ's pattern.
**File/lines**: `core/analysis_aajil.py:566-622`.

**P0-3. Aajil PAR metrics (`par_1_inst`, `par_2_inst`, `par_3_inst`)
labelled as PAR but computed on overdue-installment count, not days
past due.** `core/analysis_aajil.py:243-261`. The tape has
`Overdue No of Installments` (fractional, rounded to int); the metric
uses this as a DPD proxy. For a 4-5-month instalment product this is
coarse but structurally defensible. Problem: the output dict labels the
fields `par_1_inst` / `par_2_inst` / `par_3_inst` without confidence
declaration and **no label conversion** into days for readers. The
frontend likely renders this next to Klaim's days-based PAR on the
Overview card — analyst reads "PAR" and assumes days. Separately, the
tape also carries an aux sheet `dpd_cohorts` with real DPD %, but that
time series is only surfaced via `dpd_time_series`. **Fix**: add
explicit `measurement: 'installments_overdue'` + `confidence: 'B'` +
rename KPI card labels. Consider using the aux sheet DPD% as the
primary PAR (Confidence A observed), with install-count as fallback.
**File/lines**: `core/analysis_aajil.py:235-292`.

**P0-4. Klaim covenant PAR30 / PAR60 use `age_active > 90` / `>120`
with Pending>0 filter, not "PAR30 = DPD>30".** `core/portfolio.py:1172,
1200`. The covenant is formally "PAR30 ≤ 7%" per MMA 18.2, but since
Klaim has no contractual DPD column, the implementation has chosen
"deal aged >90 days AND has pending insurance" as the "PAR30" proxy.
This is a valid methodology choice (documented as `method='age_pending'`
and `confidence` implied in comments), but the covenant dict **does not
carry a confidence field** (`wal_active_confidence: 'A'` is the only
covenant that does). Analyst-facing output shows a number labelled
"PAR30: 12%" against a threshold of "7%", with no confidence grade.
**Fix**: add `confidence: 'B'` to every covenant whose method is
`age_pending`, `cumulative`, or `proxy`; add `confidence: 'A'` to
`direct` method. This is a 5-line fix but it codifies Framework Section
10. **File/lines**: `core/portfolio.py:1176-1338`.

**P0-5. Klaim Collection Ratio covenant uses `cumulative collected /
face value` for a period-labelled test.** `core/portfolio.py:1229-1258`.
The `note` field acknowledges this: "Single-tape approximation:
cumulative collected / face value. True period ratio requires two
snapshots." Method is tagged `cumulative`. But `compliant` flag is
still set and fed to `annotate_covenant_eod` which applies the
2-consecutive-breaches rule (MMA 18.3(ii)). Because the metric is
measuring cumulative not period, a declining portfolio can still show
high cumulative collection ratio → false compliance; or a rapidly-
growing portfolio can dilute cumulative collected → false breach.
**Fix** (correctness): either require two snapshots or mark
`partial=True` / `available=False` until two snapshots are ingested
together. **Fix** (minimum): add `confidence: 'C'` (derived) +
`population: 'total_originated'` to the covenant dict. **File/lines**:
`core/portfolio.py:1226-1259`.

**P0-6. SILQ covenants (`compute_silq_covenants`) and
`compute_concentration_limits` carry no Confidence grades.**
`core/analysis_silq.py:625-804`, `core/portfolio.py:322-529`. Framework
Section 10 declares confidence grading mandatory on every metric; only
Klaim WAL carries it. Five SILQ covenants + four SILQ concentration
limits (`compute_concentration_limits`) ship without any A/B/C field.
This is the most common failure mode across the audit. **Fix**: add
`confidence` field to every covenant / limit dict, derive from method:
`A` when directly observable, `B` when inferred from proxy columns,
`C` when derived or off-tape. Same change applies in Klaim's older
non-WAL covenants (P0-4). **File/lines**: SILQ — `analysis_silq.py:651,
672, 720, 757, 773`; `core/portfolio.py:222, 247, 274, 294, 352, 374,
425, 463, 503`.

### P1 — analyst views missing

**P1-1. No `separate_portfolio()` for SILQ or Aajil.** Session 25 added
the clean/loss split primitive for Klaim. SILQ has charge-off via Status
='Closed' with outstanding > 0 (or DPD >90 on active) as a proxy default.
Aajil has Status='Written Off' directly. A parallel helper for each
would let the pattern extend to learning-metric computations (e.g.,
collection rate on clean SILQ book strips out unresolved charge-offs;
margin rate on clean Aajil book strips the 19 WO deals). **File/lines**:
follow-up — new helpers `core/analysis_silq.py` + `core/analysis_aajil.py`.

**P1-2. Aajil has no WAL / duration metric at all.** The tape has
`Expected Completion`, `Sale Due Amount`, `Sale Paid Amount`, `Overdue
No of Installments`, `Deal Tenure` — enough for both covenant-facing
and learning WAL. Session 30's Klaim lesson (Active WAL 148d / Total
WAL 137d / Operational WAL 79d / Realized WAL 65d duality) is
directly applicable. Aajil's 4.5-month average tenor means WAL is
analytically important. **File/lines**: follow-up — new function
`compute_aajil_operational_wal` in `core/analysis_aajil.py`.

**P1-3. SILQ `compute_silq_collections` has no completed-only dual.**
`core/analysis_silq.py:241, 259, 273` all use totals. The `by_product`
and monthly rate are `total_originated` only. Mirror
`compute_silq_yield`'s pattern (realised_margin_rate) here. **File/lines**:
`core/analysis_silq.py:235-285`.

**P1-4. Aajil `compute_aajil_collections.overall_rate` mixes
populations.** `core/analysis_aajil.py:352` — `total_collected /
total_originated`. Numerator includes collections from Accrued (still
active) AND Realised (closed) deals; denominator is Σ principal of all
three statuses (Realised + Accrued + Written Off). A deal funded in Jan
with 50% collected is averaged with a deal funded in Mar with 10%
collected and a WO deal with 20% recovered. Analytical signal is
ambiguous. Options: (a) report separately for each status, (b) report
the 3 rates individually and an overall rate, (c) compute on
completed_only. **File/lines**: `core/analysis_aajil.py:325-361`.

**P1-5. Aajil PAR has only active-pool denominator, no lifetime dual.**
Session 30's Klaim pattern (`active_outstanding` + `total_originated`
dual) would serve Aajil's IC view well — Aajil has a cleanly separable
loss tail (1.5% count, structural shift to EMI lowering future risk).
**File/lines**: `core/analysis_aajil.py:282-288`.

**P1-6. Klaim `compute_cohorts` / `compute_cohort_loss_waterfall` don't
apply separation principle.** Each vintage's collection/denial rate is
computed across all deals in that vintage, including loss-subset. A
vintage with 3 large denial-dominated deals looks like the whole
vintage has poor performance, when 97% of the vintage is healthy.
`compute_cohort_loss_waterfall` explicitly reports default + recovery,
but `compute_cohorts` (Cohort Analysis tab) mixes the two views. **Fix**
(minimum): add `collection_rate_clean` column to cohort rows alongside
the current blended one. **File/lines**: `core/analysis.py:257-311`.

**P1-7. Tamara has no `total_originated` concept.** The FDD data
delivers outstanding balances and DPD distributions by reporting month.
Vintage heatmaps cover defaults, delinquency, dilution but not
origination volume. For L1 (Size & Composition), Tamara shows
"Outstanding AR" + "Data Points" — honest per the label but the
analytical frame is incomplete. **Fix**: either accept this is a
structural data limitation (Tamara data room ≠ raw tape, cannot compute
lifetime originated) and document in the methodology, or look for
cumulative disbursement in the Deloitte FDD. **File/lines**: follow-up
— add methodology note; possibly `core/analysis_tamara.py:380`.

**P1-8. SILQ `compute_silq_summary` reports both `total_outstanding`
(all statuses) and PAR% (active only denominator), without explaining
the population mismatch.** Analyst sees the two numbers on the same KPI
block, may assume PAR is over total_outstanding. **Fix**: add a one-liner
subtitle to the KPI card or rename field to `par30_active`. **File/lines**:
`core/analysis_silq.py:134-153`.

### P2 — cleanup

**P2-1. `compute_loss_triangle` largely redundant with
`compute_vintage_loss_curves`.** Both report per-vintage cumulative
denial rates. Consolidate or document the distinction. **File/lines**:
`core/analysis.py:1280-1314`, `:2054-2097`.

**P2-2. SILQ `compute_silq_cohort_loss_waterfall` defines "default" as
DPD>90 OR Closed in docstring but code only uses DPD>90.**
`core/analysis_silq.py:879, 903`. Minor inconsistency — either update
the docstring or include the Closed-with-outstanding case.

**P2-3. Aajil `compute_aajil_yield.by_deal_type` uses unweighted means.**
`core/analysis_aajil.py:583`. Bullet vs EMI yield comparison should be
PV-weighted; current per-deal average is dominated by the count-heavier
product (51% EMI count but smaller deals pull the mean).

**P2-4. Ejari parser does not propagate population labels to frontend.**
`core/analysis_ejari.py:31-…`. The ODS sheet carries e.g. "Active
Loans" vs "Total Contracts" distinctions explicitly, but the parser
records raw numbers. Frontend reads numbers without those labels.
Minor but an IC-ready deliverable should carry the labels.

**P2-5. No company's `compute_stress_test` / `compute_concentration_*`
checks for `classify_*_deal_stale()`-style stale-subset filtering.**
Stress scenarios on top of already-resolved loss are double-counts when
the top-exposure group has many zombie deals. Klaim specifically —
`compute_stress_test` applies a 50%/30%/20% haircut to "collected" on
top-N groups; if those groups are dominated by loss-completed zombies,
the scenario simulates loss *additional to* already-booked loss, which
overstates impact. **File/lines**: `core/analysis.py:990-1039`. [See
also [UNCERTAIN] 2.]

### [UNCERTAIN — user review]

**[UNCERTAIN] 1. Tamara `_enrich_vintage_heatmap` percentile color
scale.** `core/analysis_tamara.py:159-190`. Computes p25/p75 over all
vintage-MOB values flat. Newer vintages have fewer MOB cells; older
vintages dominate the distribution. Maybe the right IC-view behavior
(showing where a new vintage sits against the long-run average) but
for "is this vintage worse than its same-age peers" the scale should
be age-bucketed. User: keep as-is or add age-normalised variant?

**[UNCERTAIN] 2. Klaim `compute_stress_test` denominator for stressed
collection rate.** Uses `total_pv` as denominator, which is correct for
"what rate does the book drop to". But numerator = `total_collected -
loss_on_top_N`, where loss_on_top_N = affected_collected × haircut. If
the top-N group is dominated by loss-subset (already-realised loss),
applying a *further* 50% haircut is a double-count. Question: should
stress-test run on `clean_book` (session 30 primitive) rather than
full book? User: I can see arguments both ways — stressing what's
already stressed is analytically misleading, but stressing on clean
book hides the downside risk. Which view is IC-facing?

**[UNCERTAIN] 3. Aajil `compute_aajil_summary.hhi_customer` includes
Written-Off customer principal.** `core/analysis_aajil.py:119-121`.
HHI is a current-state concentration measure — IC reading is "how
concentrated is my current exposure". Including a WO customer's
historical principal in that HHI says "that customer had 5% of total
history" which is true but not "that customer is 5% of current
exposure". Question: HHI on `clean_book` vs total_originated? User
review: I don't have strong intuition. The same question applies to
Klaim's `compute_hhi` (no separation) and SILQ's `compute_silq_summary
.hhi_shop`. A consistent platform-wide answer is better than piecemeal.

---

## 3. Proposed Framework section (DRAFT for review)

*Intended home: new Section 17 after legal extraction + data room
sections, OR extension to Section 6 (Denominator Discipline). Section
naming to be decided at codification time.*

---

### § 17. Population Discipline & the Tape-vs-Portfolio Duality

Every Laith metric that expresses a rate, ratio, share, or weighted
average must declare which **population** it computes over. "Population"
is a deliberately stronger word than "denominator" — two metrics with
the same denominator value can be measuring very different subsets (e.g.
active outstanding on active_eligible vs active_outstanding itself). A
population is a set of deals + the filter predicate that produced it.

#### The seven standard populations

| Code | Definition | The question it answers |
|---|---|---|
| `total_originated` | Every deal in the tape, regardless of Status | "What has this product ever touched? What is its lifetime exposure?" |
| `active_outstanding` | Status ≠ Closed/Completed, outstanding-weighted | "What is the current risk on the live book?" |
| `active_pv` | Status ≠ Closed/Completed, face-value-weighted | "What is the current book at underwritten face value?" |
| `completed_only` | Status = Closed/Completed (resolved) | "What has actually realised? What is the closed-book performance?" |
| `clean_book` | `total_originated` minus loss-subset minus zombie-subset | "How does the product behave when stale tail is filtered out? (learning metric)" |
| `loss_subset` | Deals resolved as defaults (asset-class-specific definition) | "What went wrong and why?" |
| `zombie_subset` | Deals economically resolved but still on-book (stuck active / denial-dominant / loss-completed) | "How much of my exposure is operationally parked, not live?" |

A metric reports on *one* of these. When the same conceptual metric is
useful on two populations, the function returns a **dual view** (two
fields on the same output dict — e.g., `wal_active_days` +
`wal_total_days`; `par_active` + `par_lifetime`). Dual views are not
optional ornamentation — they are the defence against the
population-mismatch failure mode.

#### The Tape-vs-Portfolio duality

Every metric that appears on both Tape Analytics and Portfolio Analytics
answers different questions on each surface. The discipline is:

- **Portfolio Analytics is covenant-bound and unfiltered.** Its metrics
  use the population the facility document requires — typically
  `active_outstanding` or `active_outstanding → eligible`. No stale
  filter, no clean-book split. These metrics must match a compliance
  certificate if one were produced from the same data.
- **Tape Analytics is the lens for learning about the product.** Its
  metrics should report a **stale-filtered version** that strips
  operationally-resolved-but-still-flagged deals. The learning metric
  answers "how does this product behave?", not "how exposed is the
  facility right now?".

Session 30's Klaim WAL is the canonical illustration:

- **Active WAL = 148d** (covenant, `active_outstanding`, Confidence A). MMA
  Art. 21 requires this. Path A ≤ 70d OR Path B (Extended Age ≤ 5%).
- **Total WAL = 137d** (IC / book-wide view, `total_pv`, Confidence B via
  completed-deal close-age proxy). "How long does a dollar tie up,
  life-of-deal?"
- **Operational WAL = 79d** (`clean_book`, PV-weighted, Confidence B).
  Strips zombie cohort. "How long does the live product actually take?"
- **Realized WAL = 65d** (`completed_clean`, close-age-weighted,
  Confidence B). "How long did the clean book actually take to resolve?"

All four are correct. They answer four different questions. Labelling
any one of them as "WAL" on the IC card would mislead. The duality is:

- Portfolio surface ships 148d (covenant-binding).
- Tape surface ships 79d operational + 65d realized (learning).
- Both surfaces display 137d total_book for reconciliation — "if you are
  reading both cards, here is the unfiltered number".

#### Diagnostic ratio — first-pass population triage

When auditing a metric on a new subgroup (a company, a vintage, a
customer segment), compute the diagnostic ratio:

```
diagnostic_ratio = Σ outstanding on subgroup / Σ PV on subgroup
```

And classify:

| Ratio | Interpretation | Right population for that subgroup |
|---|---|---|
| < 1% | Fully resolved (completed or written off) | `completed_only` or `loss_subset` |
| 1% - 5% | Nearly-resolved, operational tail | `zombie_subset` candidate |
| 5% - 30% | Active in collection / distress | `active_outstanding` |
| 30% - 70% | Fresh-to-mid-life active | `active_outstanding` |
| > 70% | Very fresh origination | `active_outstanding` but thin denominator, annualise carefully |

The ratio is diagnostic, not definitional — but a cohort with
diagnostic_ratio < 2% computing a "collection rate" through standard
`total_originated` math is almost certainly producing a number that
understates the realised outcome (because outstanding → 0 means most of
the denominator has resolved in one direction or another, and the
"collection rate" is indistinguishable from the "write-off rate" at the
aggregate level).

#### Confidence grading is mandatory (Framework §10 extension)

Every compute function return dict must carry a `confidence` field (or
per-metric sub-fields when the function returns a bundle). Grading:

- **A — Observed.** Numerator + denominator + filter are all directly
  observed on the tape, no proxy or model substitution. Example:
  `compute_ageing.total_outstanding` — outstanding = PV − Collected −
  Denied, all observed, no proxy.
- **B — Inferred.** One of: (a) close-age/DPD derived from a proxy
  (e.g., Klaim completed-deal age via Collection days so far observed
  scalar → curve → Expected collection days); (b) denominator requires
  cross-snapshot reconstruction (e.g., roll rates); (c) filter uses a
  judgement threshold (e.g., `separate_portfolio` denial > 50% PV;
  `classify_klaim_deal_stale` stuck_active outstanding < 10% PV).
- **C — Derived.** Value comes from a model, empirical benchmark, or
  estimation. Example: `compute_par` method='derived' builds empirical
  benchmark from completed deals; `_compute_pv_adjusted_lgd`; Klaim
  `compute_expected_loss` PD.

Dual-view functions carry per-view grades. Example: `compute_klaim_cash_
duration.portfolio.duration_days_completed_only` = A;
`compute_klaim_cash_duration.portfolio.duration_days` = B.

Covenants specifically: the `method` field is necessary but not
sufficient. `method='age_pending'` on Klaim PAR30 is tape-specific
methodology, and the analyst reading "PAR30 = 12%, threshold = 7%"
cannot tell from the method name that the PAR is computed off an
operational-age proxy. **The covenant dict must carry `confidence`
alongside `method`.** Binding after this doctrine lands.

#### Platform primitives

Two helpers exist today for the Klaim clean-book / zombie split:

- `separate_portfolio(df)` — `(clean_df, loss_df)` where loss =
  Denied > 50% PV. `core/analysis.py:2569`. Extend to SILQ (charge-off
  or DPD>90 with outstanding > 0) and Aajil (Status='Written Off').
- `classify_klaim_deal_stale(df, ref_date, ineligibility_age_days=91)`
  — returns `{loss_completed, stuck_active, denial_dominant_active,
  any_stale}` masks. `core/analysis.py:2638`. Generalise to SILQ
  (DPD>180 with outstanding < 10% of disbursed = stuck) and Aajil
  (Overdue Installments ≥ tenure, or Status='Written Off', or Status=
  'Accrued' with overdue = total installments − paid).

Every asset class should end up with its own `classify_{type}_deal_stale`
and a set of Tape-side learning metrics that consume it. This audit
does not prescribe which metrics — it prescribes the discipline of
declaring, not the plumbing.

#### Decision table — picking a population for a new metric

| Question the metric answers | Population to use | Confidence starter | Example |
|---|---|---|---|
| "How long does a dollar tie up on this product?" | `clean_book` PV-weighted | B | Klaim Operational WAL |
| "What is the covenant-bound delinquency right now?" | `active_outstanding`, eligible-filtered if covenant says so | A (if direct DPD) / B (if proxy) | SILQ Covenant PAR30 |
| "What is the IC-grade realised loss rate on closed deals?" | `completed_only` or `loss_subset` | A | Klaim Returns `completed_loss_rate` |
| "How concentrated is current exposure?" | `active_outstanding` | A | Klaim `active` HHI (does not yet exist — see P1) |
| "How concentrated has the product been historically?" | `total_originated` | A | Klaim `compute_hhi` today |
| "Which vintages went worst?" | `total_originated` (per-vintage slice), then `loss_subset` for attribution | A | `compute_cohort_loss_waterfall` |
| "What is the book behaving like — not what is the facility bound to?" | `clean_book` or `completed_only` | B | Proposed SILQ clean-book collection rate |
| "Is the unresolved operational tail growing?" | `zombie_subset` | B | Klaim `compute_klaim_stale_exposure` |
| "What is the forward PD on a healthy deal?" | `clean_book` for cohort; calibration on `completed_only` | B | Klaim `compute_facility_pd` (partially) |
| "Vintage × MOB performance heatmap — is this vintage behaving like its peers?" | Age-normalised subset; NOT flat `total_originated` percentile. | B | [UNCERTAIN] 1 — pending user decision |

---

## 4. Proposed update to `framework_evolution.jsonl` entry `6e0978f7-…`

The current entry declared the pattern and set `codification_status:
"pending_second_data_point"`, gating promotion on at least one other
asset class case. This audit provides two: SILQ (covenant-denominator
asymmetry — P0-1) and Aajil (yield over WO — P0-2 — and install-count-
PAR — P0-3). Proposed replacement content for the `content` field (do
NOT write the file in this task — provide text for manual promotion):

```
Tape vs Portfolio metric duality (general principle, ready for
ANALYSIS_FRAMEWORK.md Section 17 or extension of Section 6). Metrics
grounded in face value over a long history (WAL, vintage rates,
lifetime PAR, concentration HHI) drift over time as old positions
accumulate. For Tape Analytics — the lens for learning about a company
/ product — metrics should report a stale-filtered version that strips
operationally-resolved-but-still-flagged deals. For Portfolio
Analytics — the lens for direct facility risk under covenant — metrics
report the unfiltered covenant-binding version. This duality is now a
default for any metric where the tape and the facility-eligible pool
are different sets.

Session 30 surfaced this on Klaim with WAL Total (137d unfiltered vs
79d operational vs 65d realized vs 148d covenant-active). The April
2026-04-22 platform-wide audit (reports/metric_population_audit_2026
-04-22.md) confirmed the pattern extends to: (a) SILQ covenant
Collection Ratio + Repayment at Term, where the maturing-period filter
applies to the entire DataFrame including Closed loans — population
asymmetry vs Klaim's equivalent covenant (P0-1 in the audit); (b)
Aajil compute_aajil_yield.avg_total_yield, which averages yields
across Written-Off deals without a completed-only dual, producing an
IC-facing "yield" KPI that blends underwritten vs realised views
(P0-2); and (c) Aajil PAR metrics labelled "PAR" but computed on
overdue-installment count, Confidence B by construction but with no
confidence field on the output dict (P0-3). Three independent cases,
different asset classes, same structural pattern.

Same audit also identified that Confidence grading (Framework §10) is
mandatory but only Klaim WAL actually carries the field on its output
dict. Every SILQ covenant + every Klaim non-WAL covenant +
every concentration limit dict ships without A/B/C declaration. This
is a separate but related discipline gap (P0-4 through P0-6 in the
audit).

Recommended elevation: new Framework Section 17 "Population Discipline
& the Tape-vs-Portfolio Duality" — full draft in the audit report
Section 3. Alternative: extend existing Section 6 (Denominator
Discipline) with the seven-population table + duality rule.

Prereqs for codification resolved — two additional data points
documented. Ready to promote via /extend-framework. No code fixes
required for codification; the doctrine is a discipline the audit
recommends and the P0/P1/P2 gap list provides the fix-follow-up
agenda.
```

Update the metadata fields:

- `codification_status`: `pending_second_data_point` → `ready_for_codification`
- add `related_audit`: `reports/metric_population_audit_2026-04-22.md`
- add `audit_date`: `2026-04-22`
- add `second_data_point_sources`:
  `["silq_collection_ratio_denominator_asymmetry",
    "aajil_yield_over_writeoffs", "aajil_par_installment_count_proxy"]`

The `promoted` field stays `false` until the /extend-framework command
runs and the framework_section field is populated on the entry via the
/api/framework/codify/{entry_id} endpoint.

---

## 5. Next-session task candidates

Ranked by user impact. Each is pitched as a self-contained spawn_task
prompt that the user could edit and fire.

**Task 1 — Add Confidence grading to every covenant + limit dict
platform-wide (P0-4, P0-6; unblocks Framework §17 cite contract).**
Covers: `compute_covenants` (SILQ & Klaim entry-point in portfolio.py),
`compute_silq_covenants`, `compute_silq_concentration_limits`,
`compute_klaim_concentration_limits`, `compute_concentration_limits`.
Add `confidence: 'A' | 'B' | 'C'` field driven off the existing
`method` tag per covenant: `direct` → A; `age_pending`, `cumulative`,
`proxy`, `stable` → B; `manual` → B (manual input, observed off-tape);
`derived` → C. ~12 files touched, ~50 lines net. Write 4-6 regression
tests pinning the grade-per-method mapping. **Why this is the first
task**: it's a binding prerequisite for the Framework §17 promotion,
and the lowest-risk fix in the gap list.

**Task 2 — Fix SILQ covenant maturing-period filter to use active pool,
not full df (P0-1).** The covenant is "Collection Ratio on loans
maturing in the period". Session 30 logic says: loans that were active
at period start AND had due dates in the period. SILQ today filters on
the full df. Make SILQ match Klaim's pattern (`portfolio.py:1234`) — or
Klaim matches SILQ, whichever is closer to the cert methodology. Cross-
reference SILQ KSA Dec 2025 certificate: cert shows 95.53% 3M-avg
Collection Ratio. Compute both ways, pick the one that matches.
Document the choice as a Framework-level rule.

**Task 3 — Add `realised_yield_rate` (completed-only) dual to Aajil
yield (P0-2).** Mirror SILQ's `compute_silq_yield` pattern. Add
`total_yield_all` + `total_yield_realised_only` to output. Keep the
current overall `avg_total_yield` (labelled as Confidence B) for
backward compatibility; promote the new realised-only field as the
primary KPI-card number. Add one regression test with a fixture tape
containing 5 realised deals + 1 WO deal and verify the two numbers
diverge. ~25 lines, ~3 tests.

**Task 4 — Relabel Aajil PAR metrics (P0-3).** Rename `par_1_inst` →
`par_1_inst` (keep field, but add explicit `measurement:
'installments_overdue'`, `confidence: 'B'`, and update the dashboard
label to say "PAR 1+ Inst" not "PAR 30+"). Surface the pre-computed
DPD time series from `aux['dpd_cohorts']` as the primary PAR card when
available. Aajil's aux sheet has true DPD% — Confidence A — which is
the right field for the covenant-style PAR. ~40 lines, ~4 tests.

**Task 5 — Extend `separate_portfolio()` helper to SILQ and Aajil
(P1-1).** Add `separate_silq_portfolio(df)` with definition: loss = (
Status='Closed' AND outstanding > 0) OR (DPD > 90) — tuned to match
SILQ facility doc default definition. Add `separate_aajil_portfolio(df)
` with definition: loss = Status='Written Off'. Export both from the
respective analysis modules. No immediate rewiring of existing
functions — just provide the primitive so future tasks can consume it.
~60 lines, ~6 tests.

**Task 6 — Add `classify_aajil_deal_stale()` and
`compute_aajil_operational_wal()` (P1-2).** Port Klaim session 30's
pattern to Aajil. Stale rules for Aajil: (a) loss_written_off (Status
='Written Off'); (b) stuck_active (Status='Accrued' AND
overdue_installments ≥ tenure AND receivable < 10% of Principal); (c)
overdue_dominant (Status='Accrued' AND Sale_Overdue > 50% of Principal).
Then WAL: PV-weighted elapsed + Expected Completion proxy close-age.
~120 lines, ~8 tests. Highest-effort P1, highest analyst-visible payoff
(Aajil currently has no duration metric at all).

**Task 7 — Harmonise HHI across the 5 companies [UNCERTAIN 3 gets
decided].** Decide whether HHI is reported on `total_originated` (lifetime
concentration, what the product has ever been concentrated in) or
`active_outstanding` / `clean_book` (current-state concentration). Apply
the answer uniformly. Currently Klaim, SILQ, Aajil all use
`total_originated` — consistent but arguably wrong for the IC-facing
"how concentrated am I now" reading. Low-priority, platform-wide
harmonisation. ~30 lines per company, ~5 tests.

**Task 8 — Cohort Analysis clean-book dual view (P1-6).** Klaim
`compute_cohorts` currently blends loss-subset into per-vintage rates.
Add a `collection_rate_clean` column that applies `separate_portfolio`
per vintage. Keep the existing `collection_rate` for backward
compatibility. Frontend: add a toggle on Cohort tab. ~40 lines, ~3
tests.

Tasks 1-4 are P0 correctness fixes. Task 5 is the enabling primitive
for Tasks 6, 8 (and future ones). Suggested cadence: Task 1 in a solo
session (confidence grading is a single binding discipline change),
then Task 5 as the next primitive, then Tasks 2-8 as independent
spawn_tasks depending on user priority.
