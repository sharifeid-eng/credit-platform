"""
Aajil Methodology Registration
Registers all Aajil (SME trade credit) compute functions with methodology
metadata. Imported by backend/main.py at startup to populate METRIC_REGISTRY.

Structure mirrors methodology_klaim.py + methodology_silq.py — one SECTIONS
entry per compute function, plus trailing static sections for Population &
Confidence Declarations (Framework §17), Data Notes, and Currency Conversion.
"""
from core.metric_registry import register_static_section


def register_aajil_methodology():
    """Register all Aajil methodology metadata. Called once at startup."""
    from core.metric_registry import METRIC_REGISTRY

    # ATTENTION: DO NOT import Aajil compute functions here — they pull pandas
    # and force-load dataroom I/O at module import. Registration is purely
    # declarative; the `function` field below is a string reference.

    SECTIONS = [
        # ── 1. Portfolio Overview (L1) ──
        {
            'function': 'compute_aajil_summary',
            'section': 'Portfolio Overview',
            'title': 'Aajil Portfolio Summary',
            'level': 1,
            'tab': 'overview',
            'analysis_type': 'aajil',
            'order': 1,
            'required_columns': ['Transaction ID', 'Invoice Date', 'Unique Customer Code',
                                 'Principal Amount', 'Sale Total', 'Realised Amount',
                                 'Receivable Amount', 'Realised Status', 'Deal Type'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': (
                'Portfolio summary aggregates Aajil\'s live loan tape (single multi-sheet '
                'Excel file from Cascade Debt). A "deal" is one Transaction ID — one '
                'funded SME trade-credit facility. The tape carries three realised-status '
                'values: Realised (closed, principal recovered), Accrued (active, still '
                'collecting), and Written Off (irrecoverable loss).'
            ),
            'metrics': [
                {'name': 'Total Originated (Principal)', 'formula': 'Σ Principal Amount',
                 'rationale': 'Face/GMV of all deals ever originated — Lifetime L1 view. Validated against Cascade Debt Volume (SAR 381M, 99.9% match).'},
                {'name': 'Collection Rate', 'formula': 'Σ Realised Amount / Σ Principal',
                 'rationale': 'Primary performance KPI (87.3% on Apr 2026 tape). Matches Cascade Debt Realised/Principal — cert-reconciled.'},
                {'name': 'Write-off Rate', 'formula': 'Written Off deal count / Total deal count',
                 'rationale': '1.5% on Apr 2026 tape (19 deals). ALL write-offs are Bullet deals — structural shift to EMI is reducing forward risk.'},
                {'name': 'Customer HHI', 'formula': 'Σ (customer_share²) on Principal',
                 'rationale': 'Concentration among 227 unique customers. Dual view per Framework §17: hhi_customer (total_originated, A) + hhi_customer_clean (clean_book excluding WO, B).'},
                {'name': 'Deal Type Mix', 'formula': 'EMI count / total + Bullet count / total',
                 'rationale': 'EMI 51% / Bullet 49% on Apr 2026. Loss tail is 100% Bullet — forward trajectory favours EMI.'},
            ],
            'tables': [
                {'title': 'Status Taxonomy',
                 'headers': ['Status', 'Meaning', 'Frozen?'],
                 'rows': [
                    ['Realised',    'Deal closed, Principal fully collected',              'Yes'],
                    ['Accrued',     'Deal active, collection ongoing',                     'No'],
                    ['Written Off', 'Principal irrecoverable; loss booked',                'Yes'],
                 ]},
            ],
            'notes': [
                'Validated against Cascade Debt (app.cascadedebt.com) reports 2026-04-13.',
                'Tape lacks contractual DPD column — delinquency measured via Overdue Installment Count.',
            ],
            'subsections': [],
        },
        # ── 2. Volume & Growth (L1) ──
        {
            'function': 'compute_aajil_traction',
            'section': 'Volume & Growth',
            'title': 'Monthly Volume + Balance',
            'level': 1,
            'tab': 'traction',
            'analysis_type': 'aajil',
            'order': 2,
            'required_columns': ['Invoice Date', 'Principal Amount', 'Deal Type', 'Receivable Amount', 'Realised Status'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': 'Monthly origination volume (Principal) and running outstanding (Receivable Amount per Accrued). MoM / QoQ / YoY growth rates skip the most recent month if < 25 days of data (partial-month detection).',
            'metrics': [
                {'name': 'MoM Growth', 'formula': '(last_month - prev_month) / prev_month', 'rationale': '+32.36% on last full month (matches Cascade Debt exact).'},
                {'name': 'Volume by Deal Type', 'formula': 'Monthly Σ Principal pivoted by EMI/Bullet', 'rationale': 'Detects shift in origination mix over time.'},
                {'name': 'Latest Balance', 'formula': 'Σ Receivable Amount on Status==Accrued', 'rationale': 'Current live exposure (SAR 80M on Apr 2026).'},
            ],
            'tables': [],
            'notes': [],
            'subsections': [],
        },
        # ── 3. Delinquency & PAR (L3) ──
        {
            'function': 'compute_aajil_delinquency',
            'section': 'Delinquency & PAR',
            'title': 'Overdue Installment Distribution',
            'level': 3,
            'tab': 'delinquency',
            'analysis_type': 'aajil',
            'order': 3,
            'required_columns': ['Realised Status', 'Overdue No of Installments', 'Receivable Amount', 'Sale Overdue Amount', 'Deal Type', 'Principal Amount'],
            'denominator': 'active',
            'confidence': 'B',
            'prose': (
                'Aajil tape lacks a contractual DPD column. PAR is proxied via '
                'Overdue Installment Count (rounded integer). Audit P0-3: the '
                'output dict declares par_measurement = "installments_overdue" '
                'and par_confidence = "B" explicitly so analysts can\'t mistake '
                'this for days-based PAR.'
            ),
            'metrics': [
                {'name': 'PAR 1+ Installments (Active)', 'formula': 'Σ Sale Overdue on (Accrued AND Overdue Installments ≥ 1) / Σ Receivable on Accrued',
                 'rationale': 'Outstanding-weighted active PAR. Confidence B — install-count proxy.'},
                {'name': 'PAR 1+ Installments (Lifetime)', 'formula': 'Same numerator / Σ Principal across all statuses',
                 'rationale': 'Session 30 Klaim dual-perspective pattern applied to Aajil. IC-view denominator.'},
                {'name': 'PAR Primary (days-based, when aux sheet present)', 'formula': 'DPD 30+/60+/90+ % from Current_DPD_New Cohorts sheet',
                 'rationale': 'Confidence A — direct days-based DPD. Preferred when aux sheet available; install-count as fallback.'},
            ],
            'tables': [
                {'title': 'Bucket Taxonomy',
                 'headers': ['Bucket', 'Overdue Installments', 'Status'],
                 'rows': [
                    ['Current',             '0',       'Accrued AND Overdue Installments rounds to 0'],
                    ['1 inst overdue',      '1',       'Accrued AND Overdue Installments rounds to 1'],
                    ['2 inst overdue',      '2',       'Accrued AND Overdue Installments rounds to 2'],
                    ['3+ inst overdue',     '≥ 3',     'Accrued AND Overdue Installments rounds to ≥ 3 — effective default indicator'],
                 ]},
            ],
            'notes': [
                'Overdue Installment Count can be fractional on Aajil tape (proportional overdue). Values are rounded to nearest integer for bucketing.',
                'DPD 30+ from aux Current_DPD_New Cohorts sheet is preferred when available — Confidence A vs install-count Confidence B.',
            ],
            'subsections': [],
        },
        # ── 4. Collections (L2) ──
        {
            'function': 'compute_aajil_collections',
            'section': 'Collections',
            'title': 'Per-Vintage Collection Rates (3-Population Dual)',
            'level': 2,
            'tab': 'collections',
            'analysis_type': 'aajil',
            'order': 4,
            'required_columns': ['Invoice Date', 'Principal Amount', 'Realised Amount', 'Receivable Amount', 'Realised Status', 'Transaction ID'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': (
                'P1-4 audit: compute_aajil_collections emits three collection-rate '
                'populations per Framework §17 to prevent the analytical ambiguity '
                'of blending Realised (closed) with Accrued (active) and Written Off '
                'collections into a single metric.'
            ),
            'metrics': [
                {'name': 'overall_rate (blended)', 'formula': 'Σ Realised / Σ Principal (all statuses)',
                 'rationale': 'Pre-existing blended view — total_originated, Confidence B (mixes WO).'},
                {'name': 'overall_rate_realised', 'formula': 'Σ Realised (Status==Realised) / Σ Principal (Status==Realised)',
                 'rationale': '"What fraction of underwritten capital on CLOSED deals came back?" — completed_only population, Confidence A.'},
                {'name': 'overall_rate_clean', 'formula': 'Σ Realised (Realised+Accrued) / Σ Principal (Realised+Accrued)',
                 'rationale': 'Clean-book view — strips WO denominator. Confidence B (judgement filter).'},
            ],
            'tables': [],
            'notes': [],
            'subsections': [],
        },
        # ── 5. Vintage Cohorts (--) ──
        {
            'function': 'compute_aajil_cohorts',
            'section': 'Vintage Cohorts',
            'title': 'Quarterly Cohort Analysis',
            'level': None,
            'tab': 'cohort-analysis',
            'analysis_type': 'aajil',
            'order': 5,
            'required_columns': ['Invoice Date', 'Principal Amount', 'Realised Amount', 'Receivable Amount', 'Sale Overdue Amount', 'Overdue No of Installments', 'Realised Status'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': 'Quarterly cohorts (one row per vintage-quarter). Supplemented with monthly DPD time series from aux Current_DPD_New Cohorts sheet when available.',
            'metrics': [
                {'name': 'Per-vintage: originated, realised, outstanding, overdue_amount, overdue_pct, collection_rate, WO count, accrued count',
                 'formula': 'Standard group-by-vintage sums/ratios', 'rationale': 'Vintage-level view of collection + delinquency progression.'},
            ],
            'tables': [],
            'notes': [],
            'subsections': [],
        },
        # ── 6. Concentration (L1) ──
        {
            'function': 'compute_aajil_concentration',
            'section': 'Concentration',
            'title': 'Customer + Industry + Deal-Type Concentration',
            'level': 1,
            'tab': 'concentration',
            'analysis_type': 'aajil',
            'order': 6,
            'required_columns': ['Unique Customer Code', 'Principal Amount', 'Transaction ID', 'Customer Industry', 'Deal Type'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': 'HHI + top-15 customers + industry buckets + deal-type mix. Customer HHI carries a §17 clean_book dual (hhi_customer_clean, UNCERTAIN 3 resolution).',
            'metrics': [
                {'name': 'Customer HHI (total_originated)', 'formula': 'Σ (customer_share²) across all 227 customers', 'rationale': 'Lifetime concentration measure. Confidence A.'},
                {'name': 'Customer HHI (clean_book)', 'formula': 'Same, with WO customers stripped', 'rationale': 'Current-exposure measure. Confidence B (judgement filter).'},
                {'name': 'Top-5 Share', 'formula': 'Σ (top-5 customer shares)', 'rationale': 'Single-name-risk headline.'},
                {'name': 'Industry Concentration', 'formula': 'Bucketed into top-10 + Other + Unknown', 'rationale': '39% of deals have null Customer Industry — bucket handles gracefully.'},
            ],
            'tables': [],
            'notes': [],
            'subsections': [],
        },
        # ── 7. Underwriting Drift (L5) ──
        {
            'function': 'compute_aajil_underwriting',
            'section': 'Underwriting Drift',
            'title': 'Per-Quarter Cohort Quality',
            'level': 5,
            'tab': 'underwriting',
            'analysis_type': 'aajil',
            'order': 7,
            'required_columns': ['Invoice Date', 'Principal Amount', 'Deal Tenure', 'Total Yield %', 'Monthly Yield %', 'Deal Type', 'Transaction ID'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': 'Quarterly origination-quality metrics — deal size, tenure, yields, EMI %. Deviations from rolling norms surface underwriting shifts.',
            'metrics': [
                {'name': 'Avg Deal Size (per vintage)', 'formula': 'Mean(Principal) grouped by quarter', 'rationale': 'Detects migration to larger/smaller tickets.'},
                {'name': 'Avg Yield % (per vintage)', 'formula': 'Mean(Total Yield %) grouped by quarter', 'rationale': 'Pricing trend indicator.'},
                {'name': 'EMI %', 'formula': 'Count(EMI) / Count(total) per vintage', 'rationale': 'EMI share trending up is strong positive signal — all WO are Bullet.'},
            ],
            'tables': [],
            'notes': [],
            'subsections': [],
        },
        # ── 8. Yield & Margins (L4) ──
        {
            'function': 'compute_aajil_yield',
            'section': 'Yield & Margins',
            'title': 'Yield Decomposition — 3-Population Dual',
            'level': 4,
            'tab': 'yield',
            'analysis_type': 'aajil',
            'order': 8,
            'required_columns': ['Total Margin', 'Origination Fee', 'Principal Amount', 'Total Yield %', 'Monthly Yield %', 'Deal Type', 'Invoice Date'],
            'denominator': 'completed',
            'confidence': 'A',
            'prose': (
                'P0-2 audit resolution: three populations of avg yield to prevent '
                'blending realised and underwritten views. by_deal_type gains '
                'margin_rate_pv_weighted (P2-3) so EMI vs Bullet is comparable on '
                'PV-weighted basis, not unweighted mean.'
            ),
            'metrics': [
                {'name': 'avg_total_yield (blended)', 'formula': 'Mean(Total Yield %) across all deals incl. WO', 'rationale': 'Pre-existing — Confidence B; blends WO low-yield with healthy book.'},
                {'name': 'avg_total_yield_realised', 'formula': 'Mean(Total Yield %) on Status==Realised', 'rationale': 'completed_only — Confidence A. True realised-yield view.'},
                {'name': 'avg_total_yield_active', 'formula': 'Mean(Total Yield %) on Status==Accrued', 'rationale': 'active_outstanding — Confidence A. Underwritten-yield on live book.'},
                {'name': 'margin_rate_pv_weighted (by deal type)', 'formula': 'Σ Total Margin / Σ Principal per deal type', 'rationale': 'P2-3 cleanup: PV-weighted so EMI (count-heavy) vs Bullet (size-heavy) is comparable.'},
            ],
            'tables': [],
            'notes': [],
            'subsections': [],
        },
        # ── 9. Loss Waterfall (L4) ──
        {
            'function': 'compute_aajil_loss_waterfall',
            'section': 'Loss Waterfall',
            'title': 'Originated → Realised → Accrued → Written Off',
            'level': 4,
            'tab': 'loss-waterfall',
            'analysis_type': 'aajil',
            'order': 9,
            'required_columns': ['Principal Amount', 'Realised Status', 'Written Off Amount', 'Written Off VAT Recovered Amount', 'Invoice Date', 'Transaction ID'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': 'Per-vintage loss cascade. Gross loss rate on Apr 2026 tape: 19 deals / 1,245 = 1.5%. VAT recovered amount offsets gross loss.',
            'metrics': [
                {'name': 'Gross Loss Rate', 'formula': 'Σ Principal on (Status==Written Off) / Σ Principal (all)', 'rationale': '1.5% on Apr 2026.'},
                {'name': 'Net Loss', 'formula': 'Written Off Amount - VAT Recovered', 'rationale': 'Post-VAT economic loss.'},
            ],
            'tables': [],
            'notes': [],
            'subsections': [],
        },
        # ── 10. Customer Segments (--) ──
        {
            'function': 'compute_aajil_customer_segments',
            'section': 'Customer Segments',
            'title': 'Deal Type + Industry + Customer Size Tiers',
            'level': None,
            'tab': 'segments',
            'analysis_type': 'aajil',
            'order': 10,
            'required_columns': ['Deal Type', 'Customer Industry', 'Unique Customer Code', 'Principal Amount', 'Realised Amount', 'Deal Tenure', 'Total Yield %', 'Realised Status'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': 'Three segmentation lenses: Deal Type (EMI vs Bullet), Industry (bucketed top-10 + Other + Unknown), Customer Size Tier (Small <500K, Medium 500K-2M, Large 2M-5M, Enterprise 5M+).',
            'metrics': [],
            'tables': [],
            'notes': [],
            'subsections': [],
        },
        # ── 11. Seasonality (L5) ──
        {
            'function': 'compute_aajil_seasonality',
            'section': 'Seasonality',
            'title': 'YoY Monthly Origination Patterns',
            'level': 5,
            'tab': 'seasonality',
            'analysis_type': 'aajil',
            'order': 11,
            'required_columns': ['Invoice Date', 'Principal Amount', 'Transaction ID'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': 'YoY monthly volume + seasonal index (month avg / overall avg). Detects Ramadan / Eid / fiscal-year-end patterns.',
            'metrics': [],
            'tables': [],
            'notes': [],
            'subsections': [],
        },
        # ── 12. Operational WAL (L2, §17 follow-up) ──
        {
            'function': 'compute_aajil_operational_wal',
            'section': 'Cash Duration',
            'title': 'Operational WAL + Realized WAL (Framework §17)',
            'level': 2,
            'tab': 'overview',
            'analysis_type': 'aajil',
            'order': 12,
            'required_columns': ['Invoice Date', 'Principal Amount', 'Realised Status'],
            'optional_columns': ['Expected Completion'],
            'denominator': 'clean_book',
            'confidence': 'B',
            'prose': (
                'Session 30 Klaim pattern applied to Aajil. PV-weighted age across '
                'clean_book (non-stale) loans — Tape-side learning metric per '
                'Framework §17 Tape-vs-Portfolio duality. Excludes loss_written_off, '
                'stuck_active (all installments overdue), overdue_dominant_active '
                '(Sale Overdue > 50% of Principal).'
            ),
            'metrics': [
                {'name': 'Operational WAL', 'formula': 'PV-weighted mean(age) across clean_book', 'rationale': 'Strips zombie cohort — "how long does the live product actually take?"'},
                {'name': 'Realized WAL', 'formula': 'PV-weighted mean(close_age) across closed-clean', 'rationale': 'Stricter: "how long did the clean book actually take to resolve?"'},
            ],
            'tables': [
                {'title': 'Confidence Grades (Framework §17)',
                 'headers': ['View', 'Grade', 'Rationale'],
                 'rows': [
                    ['operational_wal_days (direct method)',     'B', 'Clean-book filter introduces judgement on 3 stale thresholds'],
                    ['realized_wal_days (direct method)',        'B', 'Same filter + closed-clean subset'],
                    ['operational_wal_days (elapsed_only mode)', 'C', 'Degraded when Expected Completion missing — age proxied by elapsed only'],
                 ]},
            ],
            'notes': [],
            'subsections': [],
        },
    ]

    # Register each section
    for sec in SECTIONS:
        fn_name = sec.pop('function')
        METRIC_REGISTRY.append(sec)

    # ── 13. Population & Confidence Declarations (Framework §17) ──
    register_static_section(
        section='Population & Confidence Declarations',
        analysis_type='aajil',
        order=13,
        prose=(
            'Per Framework §17 (Population Discipline & Tape-vs-Portfolio Duality), '
            'every Aajil compute output carries a `confidence` grade (A observed / '
            'B inferred / C derived) and a `population` code. Dual views are emitted '
            'where the same metric serves two different analytical questions.'
        ),
        tables=[
            {'title': 'Aajil Dual Views',
             'headers': ['Metric', 'Primary view', 'Dual view(s)'],
             'rows': [
                ['Yield',           'avg_total_yield (total_originated, B)', 'avg_total_yield_realised (completed_only, A) + avg_total_yield_active (active_outstanding, A)'],
                ['Collection rate', 'overall_rate (total_originated, B)',     'overall_rate_realised (completed_only, A) + overall_rate_clean (clean_book, B)'],
                ['PAR',             'par_{1,2,3}_inst (active_outstanding, B, install-count proxy)', 'par_{1,2,3}_inst_lifetime (total_originated, B) + par_primary (active_outstanding, A, days-based from aux)'],
                ['HHI',             'hhi_customer (total_originated, A)',    'hhi_customer_clean (clean_book, B)'],
                ['WAL',              'n/a (no covenant-side WAL)',            'operational_wal_days + realized_wal_days (both clean_book, B)'],
             ]},
            {'title': 'Primitives & Helpers',
             'headers': ['Helper', 'Purpose'],
             'rows': [
                ['separate_aajil_portfolio(df)',                'Returns (clean_df, loss_df) — loss = Status=="Written Off"'],
                ['classify_aajil_deal_stale(df, ref_date)',     'Returns 3 masks + any_stale union for stale classification'],
                ['compute_aajil_operational_wal(df, mult, ref_date)', 'Clean-book PV-weighted WAL'],
                ['compute_aajil_methodology_log(df)',           'Audit trail: adjustments, column availability, null rates'],
             ]},
        ],
        notes=[
            'Aajil loss classification is DIRECT via Status flag (no heuristic threshold), so separate_aajil_portfolio earns Confidence A unlike Klaim/SILQ which use judgement thresholds (B).',
            'Tape-side learning metrics use clean_book population; portfolio-side covenant metrics use active_outstanding (no facility document for Aajil today — see Data Notes).',
        ],
    )

    # ── 14. Data Notes ──
    register_static_section(
        section='Data Notes',
        analysis_type='aajil',
        order=14,
        prose=(
            'Aajil (Buildnow) SME trade credit — Saudi Arabia (SAR). Data sourced '
            'from Cascade Debt platform (app.cascadedebt.com) as of 2026-04-13: '
            '1,245 deals across 7 sheets (Deals, Payments, DPD Cohorts, Collections, '
            'and 3 others). Company-overview/underwriting/trust-scores from Mar 2026 '
            'investor deck.'
        ),
        tables=[
            {'title': 'Data Caveats',
             'headers': ['Caveat', 'Impact'],
             'rows': [
                ['No contractual DPD column on tape', 'PAR proxied via Overdue Installment Count (Confidence B). par_primary surfaces Confidence A days-based DPD from aux Current_DPD_New Cohorts sheet when available.'],
                ['Customer Industry null on 39% of deals', 'Bucketed into top-10 + Other + Unknown — Other dominates lower buckets.'],
                ['All 19 Written-Off deals are Bullet type', 'Structural shift to EMI (51% of count) is reducing forward default risk. Surfaced in compute_aajil_summary (wo_bullet_only finding).'],
                ['Overdue Installments can be fractional', 'Rounded to nearest integer for bucketing — documented in compute_aajil_methodology_log.'],
                ['No facility document ingested', 'Covenant monitoring + Borrowing Base not computed for Aajil. Active-outstanding covenant-facing population has no consumer today.'],
             ]},
        ],
        notes=[
            'Validated against Cascade Debt (Volume = Principal 99.9% match, MoM +32.36% exact, Collection rate 87.3%).',
        ],
    )

    # ── 15. Currency Conversion ──
    register_static_section(
        section='Currency Conversion',
        analysis_type='aajil',
        order=15,
        prose='Aajil data is reported in Saudi Riyal (SAR). Dashboard supports SAR ↔ USD toggle. Non-monetary metrics (rates, percentages, counts) are FX-invariant.',
        notes=['Exchange rates fetched from open.er-api.com, 1-hour cache. Fallback to static SAR 0.2667 if API unavailable.'],
    )
