"""
Klaim Methodology Registration
Registers all Klaim (healthcare receivables) compute functions with methodology metadata.
This file is imported by backend/main.py at startup to populate the METRIC_REGISTRY.

Content extracted from the hardcoded Methodology.jsx KLAIM_SECTIONS.
"""
from core.metric_registry import register_static_section

# We register metadata AFTER importing analysis functions.
# This avoids circular imports and keeps analysis.py clean.


def register_klaim_methodology():
    """Register all Klaim methodology metadata. Called once at startup."""
    from core.metric_registry import METRIC_REGISTRY

    # Import all compute functions
    from core.analysis import (
        compute_summary, compute_deployment, compute_deployment_by_product,
        compute_collection_velocity, compute_collection_curves,
        compute_actual_vs_expected, compute_ageing, compute_par,
        compute_cohorts, compute_returns_analysis, compute_revenue,
        compute_vat_summary, compute_denial_trend, compute_denial_funnel,
        compute_cohort_loss_waterfall, compute_recovery_analysis,
        compute_vintage_loss_curves, compute_loss_categorization,
        compute_loss_triangle, compute_stress_test, compute_expected_loss,
        compute_dtfc, compute_dso, compute_hhi_for_snapshot,
        compute_concentration, compute_group_performance,
        compute_owner_breakdown, compute_collections_timing,
        compute_underwriting_drift, compute_segment_analysis,
        compute_seasonality, compute_cdr_ccr, compute_methodology_log,
        compute_hhi, compute_facility_pd,
        compute_klaim_operational_wal, compute_klaim_stale_exposure,
    )

    SECTIONS = [
        # ── 1. Portfolio Overview Metrics (L1) ──
        {
            'function': 'compute_summary',
            'section': 'Portfolio Overview Metrics',
            'title': 'Portfolio Summary',
            'level': 1,
            'tab': 'overview',
            'analysis_type': 'klaim',
            'order': 1,
            'required_columns': ['Deal date', 'Status', 'Purchase value', 'Purchase price', 'Collected till date', 'Denied by insurance'],
            'optional_columns': ['Pending insurance response', 'Expected total', 'Discount'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': None,
            'metrics': [
                {'name': 'Collection Rate', 'formula': 'Collected till date / Purchase value', 'rationale': 'Primary measure of asset performance. Shows the proportion of face value actually recovered. Tracked at portfolio, monthly, cohort, group, and discount-band levels.'},
                {'name': 'Denial Rate', 'formula': 'Denied by insurance / Purchase value', 'rationale': 'Measures the proportion of receivables rejected by the insurer. High or rising denial rates signal deterioration in underwriting quality, insurer disputes, or provider documentation issues.'},
                {'name': 'Pending Rate', 'formula': 'Pending insurance response / Purchase value', 'rationale': 'Captures receivables still awaiting insurer decision. A growing pending balance indicates slower adjudication or processing bottlenecks.'},
                {'name': 'Weighted DSO (Days Sales Outstanding)', 'formula': 'DSO_w = Sum(Days_i x Collected_i) / Sum(Collected_i)', 'rationale': 'Measures the average time to collect cash, weighted by collection amount. Larger collections carry proportionally more influence. Calculated on completed deals only. When collection curve data is available (30-day interval columns), DSO is estimated by finding when 90% of the deal\'s total collection arrived (curve-based). Otherwise falls back to deal age (today minus deal date). Critical for sizing financing tenor and projecting liquidity.'},
                {'name': 'Median DSO', 'formula': 'Median of days to collect across all completed deals', 'rationale': 'Robust measure of typical collection timing, unaffected by outliers. The 50th percentile of days to collect. Uses curve-based estimation when available.'},
                {'name': 'P95 DSO', 'formula': '95th percentile of days to collect on completed deals', 'rationale': 'Tail-risk measure: 95% of deals resolve within this timeframe. Used to set maximum expected tenor for facility structuring.'},
                {'name': 'HHI (Herfindahl-Hirschman Index)', 'formula': 'HHI = Sum(Share_i)^2 where Share_i = Exposure_i / Total Exposure', 'rationale': 'Standard measure of portfolio concentration. Ranges from 0 (perfectly diversified) to 1 (single counterparty). Computed separately on Group (provider) and Product dimensions. Thresholds: <0.15 unconcentrated, 0.15-0.25 moderate, >0.25 highly concentrated.'},
            ],
            'tables': [],
            'notes': ['Top-1, top-5, and top-10 counterparty shares are also reported alongside HHI to identify single-name risk.'],
            'subsections': [],
        },
        # ── 2. Collection Performance (L2) ──
        {
            'function': 'compute_actual_vs_expected',
            'section': 'Collection Performance',
            'title': 'Actual vs Expected',
            'level': 2,
            'tab': 'actual-vs-expected',
            'analysis_type': 'klaim',
            'order': 2,
            'required_columns': ['Deal date', 'Purchase value', 'Collected till date', 'Expected total'],
            'optional_columns': ['Expected till date'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': 'The Collection Performance chart (Actual vs Expected tab) displays three cumulative lines to assess whether the portfolio is collecting on schedule and how much lifetime value remains outstanding.',
            'metrics': [
                {'name': 'Pacing %', 'formula': 'Collected till date / Expected till date', 'rationale': 'Primary performance indicator. A value above 100% means collections are ahead of the time-based forecast. Below 100% signals delays relative to expected payment schedules. This is the badge shown on the chart.'},
                {'name': 'Recovery %', 'formula': 'Collected till date / Expected total', 'rationale': 'Measures how much of the full lifetime expected has been recovered so far. Will always be below 100% for a live portfolio with active deals. Converges toward 100% as deals complete.'},
            ],
            'tables': [
                {'title': 'Three Lines', 'headers': ['Line', 'Data Source', 'What It Answers'], 'rows': [
                    ['Collected', 'Cumulative Collected till date by deal month', 'How much cash has actually been received?'],
                    ['Forecast (expected by now)', 'Cumulative Expected till date by deal month', 'How much should have been collected by now based on payment schedules?'],
                    ['Expected Total', 'Cumulative Expected total by deal month', 'What is the full lifetime expected collection (ceiling)?'],
                ]},
            ],
            'notes': ['Forecast requires the "Expected till date" column in the tape. When this column is unavailable, the chart falls back to a two-line view (Collected vs Expected Total) using recovery % as the badge.'],
            'subsections': [],
        },
        # ── 3. Collection Analysis (L2) ──
        {
            'function': 'compute_collection_velocity',
            'section': 'Collection Analysis',
            'title': 'Collection Velocity',
            'level': 2,
            'tab': 'collection',
            'analysis_type': 'klaim',
            'order': 3,
            'required_columns': ['Deal date', 'Purchase value', 'Collected till date', 'Status'],
            'optional_columns': ['Expected till date', 'Actual in 30 days', 'Actual in 90 days'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': 'The Collection tab tracks how quickly cash is received and how collection patterns evolve over time.',
            'metrics': [
                {'name': 'Collection Rate', 'formula': 'Collected till date / Purchase value (per month)', 'rationale': 'Monthly collection rate with a 3-month rolling average overlay. Shows the trend of cash recovery efficiency across deal origination months. Note: recent vintages will naturally show low rates because active deals are still collecting -- this does not indicate underperformance.'},
                {'name': 'Expected Collection Rate', 'formula': 'Expected till date / Purchase value (per month)', 'rationale': 'Forecast benchmark showing what the portfolio model expects to have collected by now for each vintage. Rendered as a blue dashed line alongside the actual rate bars. The gap between actual and expected isolates true underperformance from normal deal seasoning.'},
                {'name': 'Curve-Based Collection Time', 'formula': 'Interpolated days when actual collections reach 90% of total collected (from 30-day interval curve data)', 'rationale': 'When the tape includes collection curve columns (Actual in 30 days, Actual in 60 days, etc.), the system estimates true collection time by finding the interval where 90% of the deal\'s total was received, then interpolates. This is far more accurate than using deal age (today minus deal date). Falls back to deal age on tapes without curve data.'},
                {'name': 'Model Accuracy', 'formula': 'Actual collection % / Expected collection % (per interval)', 'rationale': 'Measures how well Klaim\'s expected collection schedule matches reality at each 30-day checkpoint. Values above 100% indicate faster-than-expected collection; below 100% indicates delays.'},
            ],
            'tables': [],
            'notes': [],
            'subsections': [
                {'title': 'Cash Collection Breakdown', 'prose': 'Completed deals are grouped by how long they took to collect into six time buckets (0-30d, 31-60d, 61-90d, 91-120d, 121-180d, 181+d). This chart only includes completed deals; active deals still collecting are excluded.', 'metrics': [], 'tables': [], 'notes': []},
                {'title': 'Collection Curves (Expected vs Actual)', 'prose': 'When curve columns are available (30-day intervals up to 390 days), the platform plots expected vs actual cumulative collection as a percentage of purchase value. Available at both portfolio aggregate and per-vintage levels.', 'metrics': [], 'tables': [], 'notes': []},
            ],
        },
        # ── 4. Health Classification (L3) ──
        {
            'function': 'compute_ageing',
            'section': 'Health Classification',
            'title': 'Health & Ageing',
            'level': 3,
            'tab': 'ageing',
            'analysis_type': 'klaim',
            'order': 4,
            'required_columns': ['Deal date', 'Status', 'Purchase value', 'Collected till date', 'Denied by insurance'],
            'denominator': 'active',
            'confidence': 'A',
            'prose': 'Active deals (Status = "Executed") are classified by days outstanding from deal origination to the as-of date.',
            'metrics': [],
            'tables': [
                {'title': 'Health Buckets', 'headers': ['Bucket', 'Days Outstanding', 'Interpretation'], 'rows': [
                    ['Healthy', '0-60 days', 'Within normal collection cycle'],
                    ['Watch', '61-90 days', 'Approaching delayed territory, warrants monitoring'],
                    ['Delayed', '91-120 days', 'Past expected collection window, elevated risk'],
                    ['Poor', '>120 days', 'Material delinquency, likely requires remediation or provisioning'],
                ]},
            ],
            'notes': ['Health classification is measured by outstanding amount (Purchase Value - Collected - Denied), not face value. This reflects true residual risk exposure -- a deal with AED 100K face value but AED 95K already collected has only AED 5K outstanding, correctly contributing minimal weight to the "Poor" bucket even if it is aged beyond 120 days.'],
            'subsections': [],
        },
        # ── 5. Portfolio at Risk (L3) ──
        {
            'function': 'compute_par',
            'section': 'Portfolio at Risk (PAR)',
            'title': 'PAR Computation',
            'level': 3,
            'tab': 'overview',
            'analysis_type': 'klaim',
            'order': 5,
            'required_columns': ['Status', 'Purchase value', 'Collected till date', 'Denied by insurance'],
            'optional_columns': ['Expected till date'],
            'denominator': 'active',
            'confidence': 'B',
            'prose': 'PAR measures the share of the portfolio that is behind schedule, weighted by outstanding amount. Laith reports two perspectives for Klaim:',
            'metrics': [],
            'tables': [
                {'title': 'PAR Perspectives', 'headers': ['Perspective', 'Denominator', 'Use Case'], 'rows': [
                    ['Lifetime PAR', 'Total originated outstanding', 'IC reporting -- headline metric'],
                    ['Active PAR', 'Active outstanding only', 'Operational monitoring -- context metric'],
                ]},
                {'title': 'PAR Computation Methods', 'headers': ['Method', 'Description', 'Confidence'], 'rows': [
                    ['Primary', 'Shortfall-based estimated DPD using Expected till date column', 'B -- Inferred'],
                    ['Option C', 'Empirical benchmarks from 50+ completed deals -- labeled "Derived"', 'C -- Derived'],
                    ['Unavailable', 'Returns available: false when neither method has sufficient data', '--'],
                ]},
                {'title': 'PAR Thresholds', 'headers': ['Metric', 'Threshold', 'Interpretation'], 'rows': [
                    ['PAR 30+', '>2% lifetime', 'Elevated -- monitor trend'],
                    ['PAR 30+', '>5% lifetime', 'High -- escalate to IC'],
                    ['PAR 60+', '>1.5% lifetime', 'Elevated'],
                    ['PAR 90+', '>1% lifetime', 'Material impairment signal'],
                ]},
            ],
            'notes': [
                'Active outstanding is typically only 7-9% of total originated for Klaim (most deals have collected or been denied). This means Active PAR can appear alarmingly high (e.g. 46%) while Lifetime PAR is benign (e.g. 3.6%). Always read Lifetime PAR as the headline; Active PAR provides operational context.',
                'For Klaim, there are no contractual due dates -- PAR is approximated using the Expected till date column as a proxy for the repayment schedule. Option C builds empirical benchmarks from completed deals that collected on time.',
            ],
            'subsections': [],
        },
        # ── 6. Cohort Analysis ──
        {
            'function': 'compute_cohorts',
            'section': 'Cohort Analysis',
            'title': 'Vintage Cohorts',
            'level': None,
            'tab': 'cohort-analysis',
            'analysis_type': 'klaim',
            'order': 6,
            'required_columns': ['Deal date', 'Purchase value', 'Purchase price', 'Collected till date', 'Denied by insurance', 'Pending insurance response', 'Status'],
            'optional_columns': ['Expected IRR', 'Actual IRR', 'Actual in 90 days', 'Actual in 180 days', 'Actual in 360 days'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': 'Deals are grouped into monthly vintages by origination date (Deal date). Each cohort is analyzed independently to identify trends across origination periods.',
            'metrics': [],
            'tables': [
                {'title': 'Metrics per Cohort (up to 17 columns)', 'headers': ['Metric', 'Formula / Source'], 'rows': [
                    ['Total Deals', 'Count of all deals in vintage'],
                    ['Completed Deals', 'Count where Status = "Completed"'],
                    ['Completion Rate', 'Completed / Total'],
                    ['Purchase Value', 'Sum of face values'],
                    ['Purchase Price', 'Sum of cost basis (price paid)'],
                    ['Collected', 'Sum of collections to date'],
                    ['Denied', 'Sum of insurance denials'],
                    ['Pending', 'Sum awaiting response'],
                    ['Collection Rate', 'Collected / Purchase Value'],
                    ['Denial Rate', 'Denied / Purchase Value'],
                    ['Expected Margin', '(Purchase Value - Purchase Price) / Purchase Price'],
                    ['Realised Margin', '(Collected - Purchase Price) / Purchase Price (completed deals only)'],
                    ['Avg Expected IRR', 'Mean of Expected IRR column (when available)'],
                    ['Avg Actual IRR', 'Mean of Actual IRR column (filtered: outliers >1000% excluded)'],
                    ['90D %', '% of purchase value collected within 90 days (curve-based, when available)'],
                    ['180D %', '% of purchase value collected within 180 days (curve-based, when available)'],
                    ['360D %', '% of purchase value collected within 360 days (curve-based, when available)'],
                ]},
            ],
            'notes': [],
            'subsections': [
                {'title': 'Collection Speed (90D / 180D / 360D)', 'prose': 'When collection curve data is available, three additional columns show the percentage of purchase value collected within 90, 180, and 360 days respectively. These are color-coded for quick assessment. Hidden entirely on tapes that lack curve data.', 'metrics': [], 'tables': [], 'notes': []},
                {'title': 'IRR Derivation', 'prose': 'When tape data lacks explicit IRR columns, the backend derives an approximate IRR from purchase price, collected amount, and deal dates.', 'metrics': [], 'tables': [], 'notes': []},
                {'title': 'Totals Row', 'prose': 'A portfolio-wide totals row aggregates all cohorts. Rates in the totals row are calculated from aggregated numerators and denominators, not as averages of cohort-level rates, to avoid size-bias distortion.', 'metrics': [], 'tables': [], 'notes': []},
            ],
        },
        # ── 7. Returns Analysis (L4) ──
        {
            'function': 'compute_returns_analysis',
            'section': 'Returns Analysis',
            'title': 'Returns & Margins',
            'level': 4,
            'tab': 'returns',
            'analysis_type': 'klaim',
            'order': 7,
            'required_columns': ['Purchase value', 'Purchase price', 'Collected till date', 'Status'],
            'optional_columns': ['Discount', 'New business', 'Setup fee', 'Other fee'],
            'denominator': 'completed',
            'confidence': 'A',
            'prose': None,
            'metrics': [
                {'name': 'Expected Margin', 'formula': '(Purchase Value - Purchase Price) / Purchase Price', 'rationale': 'The theoretical return if 100% of face value is collected. Represents the discount captured at origination.'},
                {'name': 'Realised Margin', 'formula': '(Collected - Purchase Price) / Purchase Price -- on completed deals only', 'rationale': 'True outcome-based return computed exclusively on deals that have fully resolved. Active deals are excluded because they are still collecting and would artificially depress the margin. This applies to portfolio-level, monthly, discount band, and new vs repeat margin calculations.'},
                {'name': 'Capital Recovery', 'formula': 'Total Collected / Total Purchase Price x 100', 'rationale': 'Percentage of total deployed capital that has been returned as cash collections across all deals (active and completed). Rates above 100% indicate profitable recovery.'},
                {'name': 'Fee Yield', 'formula': '(Setup Fees + Other Fees) / Purchase Value', 'rationale': 'Ancillary income as a proportion of deployed capital. Captures non-discount revenue.'},
            ],
            'tables': [
                {'title': 'Discount Bands', 'headers': ['Band', 'Range'], 'rows': [
                    ['1', '<=4%'], ['2', '4-6%'], ['3', '6-8%'], ['4', '8-10%'], ['5', '10-15%'], ['6', '>15%'],
                ]},
            ],
            'notes': [],
            'subsections': [
                {'title': 'Discount Band Analysis', 'prose': 'Deals are grouped by discount rate into six bands. For each band: deal count, face value, cost, collected, collection rate, denial rate, and margin. Margins are computed on completed deals within each band. Higher discount bands should theoretically compensate for higher risk; this analysis tests that relationship.', 'metrics': [], 'tables': [], 'notes': []},
                {'title': 'New vs. Repeat Business', 'prose': 'Deals are classified based on the "New business" column. Performance is compared across both groups. Margins are computed on completed deals within each group for accuracy.', 'metrics': [], 'tables': [], 'notes': []},
            ],
        },
        # ── 8. Denial Funnel (L4) ──
        {
            'function': 'compute_denial_funnel',
            'section': 'Denial Funnel',
            'title': 'Resolution Pipeline',
            'level': 4,
            'tab': 'denial-trend',
            'analysis_type': 'klaim',
            'order': 8,
            'required_columns': ['Purchase value', 'Collected till date', 'Pending insurance response', 'Denied by insurance', 'Provisions'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': 'A five-stage pipeline tracking how the total portfolio value resolves over time:',
            'metrics': [
                {'name': 'Net Loss', 'formula': 'Denied - Provisions', 'rationale': 'Unrecovered portion of denied receivables after provisions are applied. Represents the true economic loss to the portfolio.'},
                {'name': 'Recovery Rate', 'formula': 'Provisions / Denied', 'rationale': 'Proportion of denied amounts covered by provisions. A rate below 100% indicates unprovisioned exposure.'},
            ],
            'tables': [
                {'title': 'Pipeline Stages', 'headers': ['Stage', 'Definition'], 'rows': [
                    ['Total Portfolio', 'Sum of all purchase values (100% baseline)'],
                    ['Collected', 'Cash received to date'],
                    ['Pending Response', 'Awaiting insurer adjudication'],
                    ['Denied', 'Rejected by insurer (adverse decision)'],
                    ['Provisioned', 'Loss reserves set against denied amounts'],
                ]},
            ],
            'notes': ['Unresolved balance (Total - Collected - Denied - Pending) is also tracked as residual exposure.'],
            'subsections': [],
        },
        # ── 9. Loss Waterfall (L4) ──
        {
            'function': 'compute_cohort_loss_waterfall',
            'section': 'Loss Waterfall',
            'title': 'Loss Decomposition',
            'level': 4,
            'tab': 'loss-waterfall',
            'analysis_type': 'klaim',
            'order': 9,
            'required_columns': ['Deal date', 'Purchase value', 'Denied by insurance', 'Collected till date'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': 'The Loss Waterfall tab provides a per-vintage decomposition of how originated capital flows through to net loss. It follows the Separation Principle: the clean portfolio (active + normal completed) is kept separate from the loss portfolio (denial > 50% of purchase value).',
            'metrics': [],
            'tables': [
                {'title': 'Waterfall Steps (per vintage)', 'headers': ['Step', 'Definition', 'Formula'], 'rows': [
                    ['Originated', 'Total purchase value of deals in the vintage', 'Sum(Purchase Value)'],
                    ['Gross Default', 'Deals where Denied > 50% of Purchase Value', 'Sum(PV of loss deals)'],
                    ['Recovery', 'Amount actually collected on default deals', 'Sum(Collected on loss deals)'],
                    ['Net Loss', 'Unrecovered portion after collections', 'Gross Default - Recovery'],
                ]},
            ],
            'notes': ['Categories in loss categorization are mutually exclusive and exhaustive. They are starting points for investigation, not definitive classifications.'],
            'subsections': [
                {'title': 'Default Definition', 'prose': 'For Klaim, there are no contractual due dates. A deal is classified as a gross default when the insurance denial exceeds 50% of the purchase value. This is the functional equivalent of a credit loss event for healthcare receivables factoring.', 'metrics': [], 'tables': [], 'notes': []},
                {'title': 'Loss Categorization (Heuristics)', 'prose': 'Rules-based classification: Provider Issue (high denial from specific Group), Coding Error (partial denials suggesting claim issues), Credit/Underwriting (remaining unexplained denials).', 'metrics': [], 'tables': [], 'notes': []},
                {'title': 'Recovery Analysis', 'prose': 'Recovery rates and timing are tracked per vintage for deals that experienced gross default. Key metrics: recovery rate, average recovery days, and worst/best performing deals by vintage.', 'metrics': [], 'tables': [], 'notes': []},
            ],
        },
        # ── 10. Stress Testing (L5) ──
        {
            'function': 'compute_stress_test',
            'section': 'Stress Testing',
            'title': 'Provider Shock Scenarios',
            'level': 5,
            'tab': 'risk-migration',
            'analysis_type': 'klaim',
            'order': 10,
            'required_columns': ['Group', 'Purchase value', 'Collected till date'],
            'denominator': 'total',
            'confidence': 'B',
            'prose': 'Three provider-shock scenarios simulate the impact of counterparty distress on portfolio collections.',
            'metrics': [],
            'tables': [
                {'title': 'Scenarios', 'headers': ['Scenario', 'Counterparties', 'Haircut', 'Rationale'], 'rows': [
                    ['Severe', 'Top 1 provider', '50%', 'Single-name concentration risk -- largest provider halves payments'],
                    ['Moderate', 'Top 3 providers', '30%', 'Sector-wide stress -- top three providers simultaneously impaired'],
                    ['Mild', 'Top 5 providers', '20%', 'Broad market stress -- widespread but shallow reduction'],
                ]},
            ],
            'notes': ['Provider ranking is based on total exposure (purchase value). If provider names are not normalized, concentration may be understated.'],
            'subsections': [],
        },
        # ── 11. Forward-Looking Signals (L5) ──
        {
            'function': 'compute_dtfc',
            'section': 'Forward-Looking Signals',
            'title': 'Leading Indicators',
            'level': 5,
            'tab': 'overview',
            'analysis_type': 'klaim',
            'order': 11,
            'required_columns': ['Deal date', 'Collected till date'],
            'optional_columns': ['Actual in 30 days'],
            'denominator': 'active',
            'confidence': 'B',
            'prose': 'Forward-looking signals are metrics that historically deteriorate before the collection rate does. They provide early warning of portfolio stress.',
            'metrics': [
                {'name': 'DTFC (Median)', 'formula': 'Days from deal origination to first cash receipt -- median across active deals', 'rationale': 'A lengthening DTFC means insurers are taking longer to make initial payments. This typically precedes a decline in collection rate by 30-60 days, making it a leading indicator of portfolio stress.'},
                {'name': 'DTFC (P90)', 'formula': '90th percentile of days to first cash', 'rationale': 'Captures the slowest-paying tail. Rising P90 indicates the worst deals are getting worse faster than the median.'},
                {'name': 'DSO Capital', 'formula': 'Days from deal origination (funding date) to collection -- measures capital duration', 'rationale': 'How long the fund\'s capital is tied up. Directly impacts IRR and reinvestment capacity.'},
                {'name': 'DSO Operational', 'formula': 'Days from Expected till date (due date) to actual collection -- measures payer behaviour', 'rationale': 'How late insurers are paying relative to schedule. Rising DSO Operational indicates payer deterioration independent of deal maturity.'},
                {'name': 'HHI Time Series', 'formula': 'HHI = Sum(Share_i)^2 computed across all snapshots', 'rationale': 'A rising HHI across snapshots indicates the portfolio is becoming more concentrated in fewer providers -- a risk factor even if current collection rates are healthy.'},
            ],
            'tables': [
                {'title': 'DTFC Methods', 'headers': ['Method', 'How Computed', 'Grade'], 'rows': [
                    ['Curve-based', 'Uses 30-day collection curve columns -- finds first non-zero interval', 'B'],
                    ['Estimated', 'Approximates from deal date and first collected amount date', 'C'],
                ]},
                {'title': 'HHI Classification', 'headers': ['HHI Range', 'Classification', 'Interpretation'], 'rows': [
                    ['< 0.10', 'Diversified', 'Low concentration risk'],
                    ['0.10 - 0.15', 'Moderate', 'Monitor top providers closely'],
                    ['> 0.15', 'Concentrated', 'Single-name risk elevated'],
                ]},
            ],
            'notes': [
                'Both DSO variants use the curve-based method when 30-day collection curve columns are available (Mar 2026+ tapes). Falls back to deal-age estimation on older tapes.',
                'HHI trend (increasing / stable / decreasing) is computed across all available snapshots. A warning is issued when HHI is rising and already above 0.10.',
            ],
            'subsections': [],
        },
        # ── 12. Expected Loss Model (L4) ──
        {
            'function': 'compute_expected_loss',
            'section': 'Expected Loss Model',
            'title': 'EL Model',
            'level': 4,
            'tab': 'risk-migration',
            'analysis_type': 'klaim',
            'order': 12,
            'required_columns': ['Status', 'Purchase value', 'Collected till date', 'Denied by insurance'],
            'optional_columns': ['Provisions'],
            'denominator': 'active',
            'confidence': 'B',
            'prose': 'The expected loss framework follows the standard credit risk formulation: EL = PD x LGD x EAD',
            'metrics': [
                {'name': 'Probability of Default (PD)', 'formula': 'Deals with denial > 1% of purchase value / Total completed deals', 'rationale': 'Estimated from historical outcomes on completed deals. The 1% threshold filters out de minimis adjustments.'},
                {'name': 'Loss Given Default (LGD)', 'formula': '(Total Denied - Total Provisions) / Total Denied', 'rationale': 'Measures the unrecovered loss rate on defaulted deals.'},
                {'name': 'Exposure at Default (EAD)', 'formula': 'Purchase value of all active (Executed) deals', 'rationale': 'Current outstanding portfolio balance exposed to potential loss.'},
                {'name': 'Expected Loss Rate', 'formula': 'EL / EAD', 'rationale': 'Normalised loss expectation as a percentage of exposure. Used to benchmark against advance rates and required reserves.'},
            ],
            'tables': [],
            'notes': [],
            'subsections': [
                {'title': 'By Vintage', 'prose': 'PD, LGD, and EAD are also calculated per origination month to identify if loss is concentrated in specific cohorts or distributed evenly.', 'metrics': [], 'tables': [], 'notes': []},
            ],
        },
        # ── 13. Roll-Rate Migration (L3) ──
        {
            'function': 'compute_roll_rates',
            'section': 'Roll-Rate Migration',
            'title': 'Migration Analysis',
            'level': 3,
            'tab': 'risk-migration',
            'analysis_type': 'klaim',
            'order': 13,
            'required_columns': ['Deal date', 'Status'],
            'denominator': 'active',
            'confidence': 'B',
            'prose': 'Migration analysis tracks how deals move between ageing buckets across two consecutive snapshots. This requires at least two loan tape snapshots.',
            'metrics': [
                {'name': 'Cure Rate', 'formula': 'Deals improving (moving to lower bucket or Paid) / Total delinquent deals', 'rationale': 'Measures the probability that delinquent receivables recover. High cure rates reduce required reserves and support higher advance rates.'},
            ],
            'tables': [
                {'title': 'Ageing Buckets', 'headers': ['Bucket', 'Criteria'], 'rows': [
                    ['Paid', 'Status = "Completed"'],
                    ['0-30 days', 'Active, <=30 days from deal date'],
                    ['31-60 days', 'Active, 31-60 days'],
                    ['61-90 days', 'Active, 61-90 days'],
                    ['91-180 days', 'Active, 91-180 days'],
                    ['180+ days', 'Active, >180 days'],
                ]},
            ],
            'notes': [],
            'subsections': [
                {'title': 'Deal Matching', 'prose': 'Deals are matched across snapshots using the ID column (tries: ID, Deal ID, Reference, and variants). Only deals present in both snapshots are included.', 'metrics': [], 'tables': [], 'notes': []},
                {'title': 'Transition Matrix', 'prose': 'Rows = bucket in earlier snapshot, columns = bucket in later snapshot. Diagonal = stable; above-diagonal = improvement; below-diagonal = deterioration.', 'metrics': [], 'tables': [], 'notes': []},
            ],
        },
        # ── 14. Advanced Analytics ──
        {
            'function': 'compute_collections_timing',
            'section': 'Advanced Analytics',
            'title': 'Advanced Cuts',
            'level': None,
            'tab': 'collections-timing',
            'analysis_type': 'klaim',
            'order': 14,
            'required_columns': ['Deal date', 'Purchase value'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': 'The following tabs provide deeper analytical cuts beyond the core performance metrics. All use the same underlying tape data with no additional configuration required.',
            'metrics': [],
            'tables': [],
            'notes': ['Underwriting drift is distinct from credit quality deterioration. A vintage can have excellent credit quality but show underwriting drift if deal sizes are growing unusually fast.'],
            'subsections': [
                {'title': 'Collections Timing', 'prose': 'Uses 30-day collection curve columns (Mar 2026+ tapes) to show how cash arrives over the life of a deal. Broken into timing buckets: 0-30d, 30-60d, 60-90d, 90-120d, 120-180d, 180d+. Two views: by payment month and by origination month. Requires curve columns -- hidden on older tapes.', 'metrics': [], 'tables': [], 'notes': []},
                {'title': 'Underwriting Drift', 'prose': 'Tracks per-vintage origination characteristics over time: average deal size, discount rate, and collection rate. Computes a rolling 6-month baseline and flags vintages where any metric deviates beyond 1 standard deviation.', 'metrics': [], 'tables': [], 'notes': []},
                {'title': 'Segment Analysis', 'prose': 'Multi-dimensional performance cuts across four dimensions (product type, provider size, deal size, new vs repeat), each producing a sortable heat-map table with deal count, volume, collection rate, denial rate, and realised margin.', 'metrics': [], 'tables': [], 'notes': []},
                {'title': 'Seasonality', 'prose': 'Groups monthly deployment by calendar month across years for year-over-year comparison. Computes a seasonal index (month average / overall average) to quantify seasonal patterns. Index > 1.0 indicates above-average origination months.', 'metrics': [], 'tables': [], 'notes': []},
            ],
        },
        # ── 15. CDR / CCR (L3) ──
        {
            'function': 'compute_cdr_ccr',
            'section': 'CDR / CCR',
            'title': 'Conditional Rates',
            'level': 3,
            'tab': 'cdr-ccr',
            'analysis_type': 'klaim',
            'order': 15,
            'required_columns': ['Deal date', 'Purchase value', 'Collected till date'],
            'optional_columns': ['Denied by insurance'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': 'Conditional Default Rate (CDR) and Conditional Collection Rate (CCR) annualize cumulative rates by vintage age so that cohorts of different maturities are directly comparable on a monthly basis. This strips out the age effect: a 6-month vintage with 5% cumulative defaults has CDR = 10%, higher than a 12-month vintage at 8% (CDR = 8%).',
            'metrics': [
                {'name': 'CDR (Conditional Default Rate)', 'formula': 'CDR = (Total Denied / Originated) / months_outstanding * 12', 'rationale': 'Annualized default intensity per vintage. Enables apples-to-apples comparison across vintages of different ages. For Klaim, "default" is measured by insurance denial amount.'},
                {'name': 'CCR (Conditional Collection Rate)', 'formula': 'CCR = (Total Collected / Originated) / months_outstanding * 12', 'rationale': 'Annualized collection intensity per vintage. A declining CCR across recent vintages signals deteriorating collection velocity independent of maturity.'},
                {'name': 'Net Spread', 'formula': 'Net Spread = CCR - CDR', 'rationale': 'The net annualized rate at which the portfolio generates value. A narrowing spread (rising CDR, stable CCR) is an early warning of deterioration.'},
            ],
            'tables': [
                {'title': 'Seasoning Filter', 'headers': ['Rule', 'Threshold', 'Rationale'], 'rows': [
                    ['Minimum vintage age', '3 months', 'Vintages younger than 3 months are excluded because annualizing a small cumulative rate over a short period produces misleadingly large numbers.'],
                ]},
            ],
            'notes': [
                'Portfolio-level CDR and CCR use a volume-weighted average vintage age for annualization, not a simple average of per-vintage rates.',
                'All rates are expressed as annualized percentages. A CDR of 10% means that at the current run-rate, 10% of originated value would be denied per year.',
            ],
            'subsections': [],
        },
        # ── 16. Facility-Mode PD (L5) ──
        {
            'function': 'compute_facility_pd',
            'section': 'Facility-Mode PD',
            'title': 'Markov Chain PD',
            'level': 5,
            'tab': 'facility-pd',
            'analysis_type': 'klaim',
            'order': 16,
            'required_columns': ['Deal date', 'Status', 'Purchase value'],
            'optional_columns': ['Expected collection days', 'Expected till date', 'Collected till date', 'Denied by insurance'],
            'denominator': 'active',
            'confidence': 'B',
            'prose': 'Facility-mode PD measures the probability that a receivable ages from its current DPD bucket into default. Uses a Markov chain approach: observe the default rate of completed deals at each DPD depth, then weight by the current active portfolio distribution to derive a facility-level forward PD.',
            'metrics': [
                {'name': 'Facility PD', 'formula': 'PD = Sum(weight_i * default_rate_i) across DPD buckets, where weight_i = active deals in bucket / total active', 'rationale': 'Weighted-average probability of default for the active portfolio based on its current DPD distribution. A higher PD indicates more deals are sitting in deeper delinquency buckets with historically worse outcomes.'},
                {'name': 'Transition-to-Default Rate', 'formula': 'For each DPD bucket: completed deals with denial > 50% PV / total completed deals at that depth', 'rationale': 'Calibrated from historical outcomes of completed deals. Shows how default probability escalates with DPD depth -- critical for setting ineligibility thresholds.'},
            ],
            'tables': [
                {'title': 'DPD Buckets', 'headers': ['Bucket', 'DPD Range', 'Interpretation'], 'rows': [
                    ['Current', '0 days', 'On schedule -- no estimated delinquency'],
                    ['1-30', '1-30 days past due', 'Early stage -- may self-cure'],
                    ['31-60', '31-60 days past due', 'Watch list territory'],
                    ['61-90', '61-90 days past due', 'Approaching ineligibility threshold'],
                    ['91-120', '91-120 days past due', 'High risk of default'],
                    ['120+', '>120 days past due', 'Likely default -- aligns with facility ineligibility cut-off'],
                ]},
                {'title': 'DPD Computation Methods', 'headers': ['Method', 'When Used', 'Grade'], 'rows': [
                    ['Direct', 'Expected collection days column available (Apr 2026+ tapes)', 'B -- DPD = max(0, deal_age - expected_collection_days)'],
                    ['Proxy', 'Only Expected till date or Purchase value available', 'C -- Estimated from shortfall ratio applied to deal age'],
                ]},
            ],
            'notes': [
                'Default is defined as denial exceeding 50% of purchase value, consistent with the Loss Waterfall definition.',
                'Without multi-snapshot transition data, the matrix is estimated from completed deal outcomes at each DPD depth rather than observed bucket-to-bucket movements.',
                'This endpoint has a backend computation but no dedicated frontend tab component yet. The methodology is documented for completeness and future rendering.',
            ],
            'subsections': [],
        },
        # ── 16a. Operational WAL (L2 Cash Conversion — Tape-side Capital Life) ──
        {
            'function': 'compute_klaim_operational_wal',
            'section': 'Capital Life (Operational WAL)',
            'title': 'Operational WAL & Realized WAL',
            'level': 2,
            'tab': 'overview',
            'analysis_type': 'klaim',
            'order': 16.5,
            'required_columns': ['Deal date', 'Status', 'Purchase value', 'Collected till date', 'Denied by insurance'],
            'optional_columns': ['Collection days so far', 'Expected collection days'],
            'denominator': 'clean-book PV',
            'confidence': 'B',
            'prose': ('Operational WAL is the PV-weighted age of the Klaim book after '
                      'filtering out stale/zombie deals — the deals that would never be '
                      'pledged to the ACP facility but keep drifting time-based metrics '
                      'upward. It answers "how long is capital deployed in the live '
                      'product?" rather than "how long does the operational tail take to '
                      'clean up?". Distinct from the covenant-facing WAL in Portfolio '
                      'Analytics (which includes every deal per MMA Art. 21).'),
            'metrics': [],
            'tables': [
                {'title': 'Two Views', 'headers': ['Metric', 'Subset', 'Use Case'], 'rows': [
                    ['Operational WAL', 'Clean book (active + completed, stale excluded)', 'Primary Tape-side capital-life signal'],
                    ['Realized WAL',    'Completed-clean only, PV-weighted close-age',       'How long did the clean book actually take to resolve'],
                ]},
                {'title': 'Stale Filter Rules', 'headers': ['Rule', 'Condition', 'Intent'], 'rows': [
                    ['loss_completed',          'Status=Completed AND Denied > 50% of PV',                                           'Resolved writeoffs'],
                    ['stuck_active',            'Status=Executed AND elapsed > 91d AND outstanding < 10% of PV',                     'Economically done but status open'],
                    ['denial_dominant_active',  'Status=Executed AND Denied > 50% of PV',                                            'Still open but mostly denied'],
                ]},
                {'title': 'Age Construction', 'headers': ['Deal State', 'Age Formula', 'Fallback Chain'], 'rows': [
                    ['Active (Executed)',  'elapsed = snapshot − Deal date',                                    '—'],
                    ['Completed',          'Collection days so far (observed), clipped to [0, elapsed]',       'Expected collection days → elapsed'],
                ]},
            ],
            'notes': [
                'On Apr 15 Klaim: Operational WAL ≈ 79d, Realized WAL ≈ 65d, vs WAL Total (covenant) ≈ 137d. The 58-day gap is the zombie tail — 16.5% of book PV sitting in stale status that drifts the covenant metric upward but tells you nothing about live product behaviour.',
                '91 days is the contractual ineligibility threshold from the MMA (Page 81). Reusing it keeps Tape-side "what is stale" aligned with Portfolio-side "what is ineligible".',
                'Confidence B — the three stale rules introduce judgement thresholds. Methodology log records every threshold in use so IC can audit.',
                'Degraded mode: tapes before Apr 2026 lack Collection days so far and Expected collection days. In this case Operational WAL is restricted to the active-clean subset (active-deal age = elapsed is unambiguous) and Realized WAL is unavailable. Method tag becomes elapsed_only with Confidence C.',
            ],
            'subsections': [],
        },
        # ── 16b. Stale Exposure (L5 Forward Signals — unresolved tail) ──
        {
            'function': 'compute_klaim_stale_exposure',
            'section': 'Stale Exposure',
            'title': 'Zombie-tail PV + Top-25 Offenders',
            'level': 5,
            'tab': 'overview',
            'analysis_type': 'klaim',
            'order': 16.6,
            'required_columns': ['Deal date', 'Status', 'Purchase value', 'Collected till date', 'Denied by insurance'],
            'optional_columns': ['ID', 'Reference', 'Group', 'Provider'],
            'denominator': 'total originated PV',
            'confidence': 'B',
            'prose': ('Stale Exposure surfaces the PV of deals classified as stale under '
                      'the three-rule filter (see Operational WAL). It is a forward signal '
                      'because unresolved tails convert into writeoffs, denials, or '
                      'recoveries — they do not stay ambiguous forever. Share > 10% is an '
                      'amber signal; > 20% is red (the active tail is dwarfing new '
                      'origination).'),
            'metrics': [],
            'tables': [
                {'title': 'Category Precedence (when a deal hits multiple rules)', 'headers': ['Priority', 'Category', 'Reason'], 'rows': [
                    ['1', 'loss_completed',          'Resolved writeoffs are the cleanest classification'],
                    ['2', 'stuck_active',            'Status inertia — most common stale cause'],
                    ['3', 'denial_dominant_active',  'Open but denied — hardest to forecast outcome'],
                ]},
                {'title': 'Thresholds', 'headers': ['Metric', 'Amber', 'Red'], 'rows': [
                    ['stale_pv_share', '> 10%', '> 20%'],
                ]},
            ],
            'notes': [
                'Top-25 offenders are the largest stale deals by Purchase value, tagged with Group and Provider attribution when those columns are on the tape. On Apr 15: the largest stuck_active offender is a 1,184-day-old (3.2 year) deal worth AED 4M still flagged Executed.',
                'ineligibility_age_days is read from facility_params when available (MMA default = 91). Changing the parameter changes the stuck_active boundary — a smaller threshold surfaces more deals as stale.',
                'This endpoint exists on the Tape side only. Portfolio Analytics covenants are unaffected — the Total WAL covenant card continues to compute on the full book per MMA Art. 21.',
            ],
            'subsections': [],
        },
        # ── 17. Data Quality Validation ──
        {
            'function': 'compute_methodology_log',
            'section': 'Data Quality Validation',
            'title': 'Validation Checks',
            'level': None,
            'tab': 'data-integrity',
            'analysis_type': 'klaim',
            'order': 17,
            'required_columns': [],
            'denominator': None,
            'confidence': None,
            'prose': 'Automated checks run against each loan tape to flag data issues before analysis. Issues are categorised by severity.',
            'metrics': [],
            'tables': [],
            'notes': [],
            'subsections': [
                {'title': 'Critical Issues (must fix)', 'prose': 'Duplicate IDs, future deal dates, missing required columns (Purchase value, Purchase price, Status, Collected, Denied).', 'metrics': [], 'tables': [], 'notes': []},
                {'title': 'Warnings (review required)', 'prose': 'Null deal dates, very old dates (before 2018), negative amounts, over-collection (>150% PV), completed with zero collection, discount anomalies (>100% or negative), low column completeness (<90%), unexpected status values.', 'metrics': [], 'tables': [], 'notes': []},
                {'title': 'Anomaly Detection', 'prose': 'Duplicate counterparty+amount+date combos, identical amount concentration (>5% of deals), deal size outliers (3xIQR fence), discount outliers (3xIQR fence), balance identity violations (Collected+Denied+Pending > 105% PV).', 'metrics': [], 'tables': [], 'notes': []},
            ],
        },
    ]

    # Register each section
    for sec in SECTIONS:
        fn_name = sec.pop('function')
        METRIC_REGISTRY.append(sec)

    # ── 18. Currency Conversion (static section) ──
    register_static_section(
        section='Currency Conversion',
        analysis_type='klaim',
        order=18,
        prose='Each portfolio company reports data in a local currency configured via config.json. All monetary values can be toggled between the reported currency and USD.',
        tables=[
            {'title': 'Supported Currencies', 'headers': ['Currency', 'USD Rate', 'Notes'], 'rows': [
                ['AED', '0.2723', 'UAE Dirham -- used by Klaim'],
                ['USD', '1.0000', 'Base currency'],
                ['EUR', '1.0800', 'Euro'],
                ['GBP', '1.2700', 'British Pound'],
                ['SAR', '0.2667', 'Saudi Riyal'],
                ['KWD', '3.2600', 'Kuwaiti Dinar'],
            ]},
        ],
        notes=['Exchange rates are fetched live from open.er-api.com and cached for 1 hour. Falls back to static rates if the API is unavailable.'],
    )
