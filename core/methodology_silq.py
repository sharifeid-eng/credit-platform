"""
SILQ Methodology Registration
Registers all SILQ (POS lending) compute functions with methodology metadata.
Imported by backend/main.py at startup to populate the METRIC_REGISTRY.

Content extracted from the hardcoded Methodology.jsx SILQ_SECTIONS.
"""
from core.metric_registry import register_static_section


def register_silq_methodology():
    """Register all SILQ methodology metadata. Called once at startup."""
    from core.metric_registry import METRIC_REGISTRY

    SECTIONS = [
        # ── 1. Portfolio Overview (L1) ──
        {
            'function': 'compute_silq_summary',
            'section': 'Portfolio Overview',
            'title': 'Portfolio Summary',
            'level': 1,
            'tab': 'overview',
            'analysis_type': 'silq',
            'order': 1,
            'required_columns': ['Agreement_ID', 'Disbursed_Amount (SAR)', 'Outstanding_Amount (SAR)', 'Status', 'Shop_Name'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': None,
            'metrics': [
                {'name': 'Total Disbursed', 'formula': 'sum(Disbursed_Amount) across all loans', 'rationale': 'Total capital deployed into the market. Includes all products (BNPL, RBF). This is the principal amount lent, not including accrued margin.'},
                {'name': 'Outstanding Amount', 'formula': 'sum(Outstanding_Amount) for active loans', 'rationale': 'Current exposure at risk. Can exceed Disbursed Amount because it includes accrued margin -- this is expected, not a data error.'},
                {'name': 'Collection Rate', 'formula': 'sum(Amt_Repaid) / sum(Total_Collectable_Amount)', 'rationale': 'Proportion of collectable amount actually recovered. Denominator includes principal plus expected margin.'},
                {'name': 'HHI (Shop)', 'formula': 'sum((shop_disbursed / total_disbursed)^2) for each shop', 'rationale': 'Herfindahl-Hirschman Index measuring shop concentration. Values below 0.15 indicate low concentration.'},
            ],
            'tables': [],
            'notes': [],
            'subsections': [],
        },
        # ── 2. Delinquency & PAR (L3) ──
        {
            'function': 'compute_silq_delinquency',
            'section': 'Delinquency & PAR',
            'title': 'Delinquency',
            'level': 3,
            'tab': 'delinquency',
            'analysis_type': 'silq',
            'order': 2,
            'required_columns': ['Repayment_Deadline', 'Outstanding_Amount (SAR)', 'Status'],
            'denominator': 'active',
            'confidence': 'A',
            'prose': None,
            'metrics': [
                {'name': 'Days Past Due (DPD)', 'formula': 'max(0, ref_date - Repayment_Deadline)', 'rationale': 'Number of days a loan is overdue. Closed loans always have DPD = 0 regardless of deadline. The reference date is the tape date or as-of date -- never today\'s date.'},
                {'name': 'PAR30 / PAR60 / PAR90', 'formula': 'Outstanding of loans with DPD > X / Total Outstanding of active loans', 'rationale': 'Portfolio at Risk -- GBV-weighted, not count-based. A single large overdue loan contributes more to PAR than many small ones.'},
                {'name': 'DPD Buckets', 'formula': 'Current (0), 1-30, 31-60, 61-90, 90+', 'rationale': 'Distribution of active loans by days past due. Amount is Outstanding Amount per bucket.'},
            ],
            'tables': [],
            'notes': ['Why GBV-weighted, not count-based? Count-based PAR treats every loan equally regardless of size. A SAR 10M overdue loan counts the same as a SAR 1K one. GBV weighting reflects the actual capital at risk.'],
            'subsections': [],
        },
        # ── 3. Collections (L2) ──
        {
            'function': 'compute_silq_collections',
            'section': 'Collections',
            'title': 'Collection Performance',
            'level': 2,
            'tab': 'collections',
            'analysis_type': 'silq',
            'order': 3,
            'required_columns': ['Disbursement_Date', 'Amt_Repaid (SAR)', 'Total_Collectable_Amount (SAR)'],
            'optional_columns': ['Margin Collected (SAR)', 'Principal Collected (SAR)'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': None,
            'metrics': [
                {'name': 'Repayment Rate', 'formula': 'sum(Amt_Repaid) / sum(Total_Collectable_Amount)', 'rationale': 'Overall collection effectiveness. Shown at portfolio level and broken down by product (BNPL vs RBF). Monthly trend shows collections momentum.'},
                {'name': 'Margin Collected', 'formula': 'sum(Margin Collected)', 'rationale': 'Revenue component of collections (interest/fees earned). Only available for BNPL products -- RBF revenue is structured differently.'},
                {'name': 'Principal Collected', 'formula': 'sum(Principal Collected)', 'rationale': 'Capital return component. Principal + Margin = Total Repaid.'},
            ],
            'tables': [],
            'notes': [],
            'subsections': [],
        },
        # ── 4. Concentration (L1) ──
        {
            'function': 'compute_silq_concentration',
            'section': 'Concentration',
            'title': 'Shop Concentration',
            'level': 1,
            'tab': 'concentration',
            'analysis_type': 'silq',
            'order': 4,
            'required_columns': ['Shop_Name', 'Disbursed_Amount (SAR)', 'Outstanding_Amount (SAR)'],
            'optional_columns': ['Shop_Credit_Limit (SAR)'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': None,
            'metrics': [
                {'name': 'Shop Concentration', 'formula': 'Top N shops by disbursed amount / total disbursed', 'rationale': 'Measures counterparty risk. High concentration in a single shop means a default there would materially impact the portfolio.'},
                {'name': 'Credit Utilization', 'formula': 'Outstanding_Amount / Shop_Credit_Limit per shop', 'rationale': 'How much of each shop\'s approved credit line is currently drawn. High utilization may signal stress.'},
                {'name': 'Loan Size Distribution', 'formula': 'Count of loans in size bands: <50K, 50-100K, 100-250K, 250-500K, 500K-1M, >1M', 'rationale': 'Shows the granularity of the book. Different risk characteristics for large vs small tickets.'},
            ],
            'tables': [],
            'notes': [],
            'subsections': [],
        },
        # ── 5. Cohort Analysis ──
        {
            'function': 'compute_silq_cohorts',
            'section': 'Cohort Analysis',
            'title': 'Vintage Cohorts',
            'level': None,
            'tab': 'cohort-analysis',
            'analysis_type': 'silq',
            'order': 5,
            'required_columns': ['Disbursement_Date', 'Disbursed_Amount (SAR)', 'Amt_Repaid (SAR)', 'Outstanding_Amount (SAR)'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': None,
            'metrics': [
                {'name': 'Vintage Cohort', 'formula': 'Group loans by Disbursement_Date month', 'rationale': 'Track each origination vintage\'s performance independently. Newer vintages have less time to collect, so lower collection rates are expected. PAR30 by vintage reveals whether delinquency is improving or deteriorating.'},
            ],
            'tables': [],
            'notes': ['Heat-coded cells highlight outliers: green for high collection rates, red for high PAR. The totals row aggregates across all vintages.'],
            'subsections': [],
        },
        # ── 6. Yield & Margins (L4) ──
        {
            'function': 'compute_silq_yield',
            'section': 'Yield & Margins',
            'title': 'Revenue Analysis',
            'level': 4,
            'tab': 'yield-margins',
            'analysis_type': 'silq',
            'order': 6,
            'required_columns': ['Disbursed_Amount (SAR)', 'Margin Collected (SAR)', 'Status'],
            'denominator': 'completed',
            'confidence': 'A',
            'prose': None,
            'metrics': [
                {'name': 'Portfolio Margin Rate', 'formula': 'sum(Margin Collected) / sum(Disbursed_Amount)', 'rationale': 'Revenue yield on deployed capital. Measured on all loans (active + closed).'},
                {'name': 'Realised Margin Rate', 'formula': 'sum(Margin Collected) / sum(Disbursed_Amount) -- closed loans only', 'rationale': 'Margin on fully matured loans. Excludes active loans still collecting, giving a cleaner view of actual return.'},
            ],
            'tables': [],
            'notes': ['RCL Margin = 0%: The RCL data sheet does not include a separate Margin Collected column. RCL revenue is priced at 3% monthly on the assigned limit, invoiced separately at month-end, not broken out in the loan tape.'],
            'subsections': [],
        },
        # ── 7. Tenure Analysis ──
        {
            'function': 'compute_silq_tenure',
            'section': 'Tenure Analysis',
            'title': 'Tenure',
            'level': None,
            'tab': 'tenure',
            'analysis_type': 'silq',
            'order': 7,
            'required_columns': ['Tenure_Days', 'Disbursed_Amount (SAR)', 'Status'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': None,
            'metrics': [
                {'name': 'Tenure', 'formula': 'Tenure column (weeks) from loan tape', 'rationale': 'Contractual loan duration. BNPL tenures range from 4-90 weeks. RBF loans are typically 90 weeks. Shorter tenures turn over faster.'},
                {'name': 'Performance by Tenure Band', 'formula': 'Collection rate, DPD rate, margin rate per tenure band', 'rationale': 'Reveals whether shorter or longer loans perform better. Bands: 1-4w, 5-9w, 10-14w, 15-19w, 20-29w, 30w+.'},
            ],
            'tables': [],
            'notes': [],
            'subsections': [],
        },
        # ── 8. Covenant Monitoring (L5) ──
        {
            'function': 'compute_silq_covenants',
            'section': 'Covenant Monitoring',
            'title': 'Covenants',
            'level': 5,
            'tab': 'covenants',
            'analysis_type': 'silq',
            'order': 8,
            'required_columns': ['Repayment_Deadline', 'Outstanding_Amount (SAR)', 'Amt_Repaid (SAR)', 'Status'],
            'denominator': 'eligible',
            'confidence': 'A',
            'prose': 'Covenants are contractual financial tests defined in the SILQ KSA facility agreement. The platform auto-checks compliance from loan tape data.',
            'metrics': [
                {'name': 'PAR 30 Ratio', 'formula': 'Outstanding of DPD > 30 loans / Total Outstanding of active loans <= 10%', 'rationale': 'Portfolio quality gate. Ensures delinquency by exposure remains controlled. Uses GBV-weighted methodology.'},
                {'name': 'PAR 90 Ratio', 'formula': 'Outstanding of DPD > 90 loans / Total Outstanding of active loans <= 5%', 'rationale': 'Serious delinquency threshold. Loans past 90 days are at elevated loss risk.'},
                {'name': 'Collection Ratio (3-Month Average)', 'formula': 'Average of (Amt_Repaid / Total_Collectable_Amount) for loans maturing in each of the prior 3 months > 33%', 'rationale': 'Measures whether maturing loans are being collected. The 3-month rolling average smooths seasonal variation.'},
                {'name': 'Repayment at Term', 'formula': 'Total collections / Total GBV for loans reaching maturity + 3 months > 95%', 'rationale': 'Tests whether loans that had enough time to fully collect actually did. Gives a 3-month grace period.'},
                {'name': 'Loan-to-Value Ratio', 'formula': 'Facility Amount / (Receivables + Cash Balances) <= 75%', 'rationale': 'Leverage test. Partially computable from tape (receivables = total outstanding). Facility amount and cash balances are corporate-level data.'},
            ],
            'tables': [],
            'notes': [],
            'subsections': [],
        },
        # ── Extra tabs (not in original Methodology.jsx but exist as tabs) ──
        {
            'function': 'compute_silq_seasonality',
            'section': 'Seasonality',
            'title': 'Seasonal Patterns',
            'level': 5,
            'tab': 'seasonality',
            'analysis_type': 'silq',
            'order': 20,
            'required_columns': ['Disbursement_Date', 'Disbursed_Amount (SAR)'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': 'Groups monthly deployment by calendar month across years for year-over-year comparison. Computes a seasonal index (month average / overall average).',
            'metrics': [],
            'tables': [],
            'notes': [],
            'subsections': [],
        },
        {
            'function': 'compute_silq_cohort_loss_waterfall',
            'section': 'Loss Waterfall',
            'title': 'Loss Decomposition',
            'level': 4,
            'tab': 'loss-waterfall',
            'analysis_type': 'silq',
            'order': 21,
            'required_columns': ['Disbursement_Date', 'Disbursed_Amount (SAR)', 'Repayment_Deadline', 'Amt_Repaid (SAR)'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': 'Per-vintage loss waterfall: Disbursed -> DPD>90 Default -> Recovery -> Net Loss.',
            'metrics': [],
            'tables': [],
            'notes': [],
            'subsections': [],
        },
        {
            'function': 'compute_silq_underwriting_drift',
            'section': 'Underwriting Drift',
            'title': 'Origination Quality',
            'level': 5,
            'tab': 'underwriting-drift',
            'analysis_type': 'silq',
            'order': 22,
            'required_columns': ['Disbursement_Date', 'Disbursed_Amount (SAR)', 'Tenure_Days', 'Product'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': 'Per-vintage quality metrics compared against 6-month rolling norms. Z-score drift flags when metrics deviate beyond 1 standard deviation.',
            'metrics': [],
            'tables': [],
            'notes': [],
            'subsections': [],
        },
        {
            'function': 'compute_silq_cdr_ccr',
            'section': 'CDR / CCR',
            'title': 'Conditional Rates',
            'level': 4,
            'tab': 'cdr-ccr',
            'analysis_type': 'silq',
            'order': 23,
            'required_columns': ['Disbursement_Date', 'Disbursed_Amount (SAR)', 'Repayment_Deadline', 'Amt_Repaid (SAR)'],
            'denominator': 'total',
            'confidence': 'A',
            'prose': 'Conditional Default Rate and Conditional Collection Rate by vintage, annualized by vintage age to strip out maturity effects.',
            'metrics': [],
            'tables': [],
            'notes': [],
            'subsections': [],
        },
    ]

    for sec in SECTIONS:
        sec.pop('function')
        METRIC_REGISTRY.append(sec)

    # ── Static sections ──
    register_static_section(
        section='Product Types',
        analysis_type='silq',
        order=9,
        prose=None,
        subsections=[
            {'title': 'BNPL (Buy Now Pay Later)', 'prose': 'The buyer submits a purchase order to FINA. FINA pays the supplier upfront and issues a sales invoice with a due date based on the selected tenor (4-90 days). The buyer repays principal plus ~3% monthly markup. Credit limits are set at ~50% of the buyer\'s sales quantum. Margin is explicitly tracked via the Margin Collected column.', 'metrics': [], 'tables': [], 'notes': []},
            {'title': 'RCL (Revolving Credit Line)', 'prose': 'A dedicated committed revolving facility. The partner routes all procurement through FINA exclusively. FINA assigns a committed limit (typically 2-3x monthly revenue). Pricing is 3% monthly on the assigned limit, invoiced separately at month-end. Margin is not separately tracked in the loan tape.', 'metrics': [], 'tables': [], 'notes': []},
            {'title': 'RBF (Revenue-Based Financing)', 'prose': 'Same underlying mechanics as RCL. No exclusivity requirement. Margin is explicitly tracked via the Margin Collected column.', 'metrics': [], 'tables': [], 'notes': []},
        ],
    )

    register_static_section(
        section='Backward-Date Caveat',
        analysis_type='silq',
        order=10,
        prose='When the as-of date is set before the tape date, deal-level filtering is applied. However, balance columns still reflect the tape snapshot date. DPD-based metrics are recalculated correctly using the as-of date as reference, but balance-derived metrics are stale.',
        tables=[
            {'title': 'Accuracy by Metric Type', 'headers': ['Metric Type', 'Accurate?', 'Examples'], 'rows': [
                ['Deal selection / counts', 'Yes', 'Total deals, active loans, product mix'],
                ['Disbursement amounts', 'Yes', 'Total disbursed (only includes filtered deals)'],
                ['DPD / PAR ratios', 'Yes', 'Recalculated with as-of date as reference'],
                ['Balance columns', 'Stale', 'Outstanding, collected, overdue, margins, rates'],
                ['Tenure / HHI', 'Yes', 'Based on deal attributes, not balances'],
            ]},
        ],
    )

    # ── Population Discipline & Confidence Grading (Framework §17) ──
    register_static_section(
        section='Population & Confidence Declarations',
        analysis_type='silq',
        order=11,
        prose=(
            'Per Framework §17 (Population Discipline & Tape-vs-Portfolio Duality), '
            'every SILQ compute output now carries `confidence` (A observed / B inferred '
            '/ C derived) and a `population` code. Dual views emitted where the same '
            'conceptual metric serves two different analytical questions.'
        ),
        tables=[
            {'title': 'SILQ Covenants — Confidence + Population (compute_silq_covenants)',
             'headers': ['Covenant', 'Method', 'Confidence', 'Population'],
             'rows': [
                ['PAR 30 Ratio',              'direct', 'A', 'active_outstanding'],
                ['PAR 90 Ratio',              'direct', 'A', 'active_outstanding'],
                ['Collection Ratio (3M Avg)', 'direct', 'A', 'specific_filter(maturing in period)'],
                ['Repayment at Term',         'direct', 'A', 'specific_filter(matured 3-6mo window)'],
                ['Loan-to-Value',             'manual', 'B', 'manual(facility + cash)'],
             ]},
            {'title': 'SILQ Concentration Limits — all Confidence A',
             'headers': ['Limit', 'Population'],
             'rows': [
                ['Single Borrower Limit (tiered)', 'active_outstanding'],
                ['Top 5 Borrower Concentration',    'active_outstanding'],
                ['Single Product Concentration',    'active_outstanding'],
                ['Weighted Avg Tenure',             'active_outstanding'],
             ]},
            {'title': 'SILQ Dual Views',
             'headers': ['Metric', 'Primary view', 'Dual view'],
             'rows': [
                ['Collections',  'repayment_rate (total_originated, A)',      'repayment_rate_realised (completed_only, A)'],
                ['Yield',        'margin_rate (total, pre-existing)',          'realised_margin_rate (Closed-only, pre-existing)'],
             ]},
            {'title': 'SILQ Summary Card (Overview) — Population Labels',
             'headers': ['Field', 'Population', 'Confidence'],
             'rows': [
                ['par30 / par60 / par90',   'active_outstanding', 'A'],
                ['total_outstanding',       'total_originated',   'A'],
                ['collection_rate',         'total_originated',   'A'],
                ['hhi_shop',                'total_originated',   'A'],
             ]},
        ],
        notes=[
            'Collection Ratio covenant maturing-period filter intentionally includes all statuses — closed-repaid loans must contribute to denominator (audit P0-1).',
            'Primitive: separate_silq_portfolio(df, ref_date) returns (clean_df, loss_df). Loss = (Closed AND outstanding>0) OR (Active AND DPD>90).',
            'Session 31 audit additions: see reports/metric_population_audit_2026-04-22.md.',
        ],
    )

    register_static_section(
        section='Currency Conversion',
        analysis_type='silq',
        order=12,
        prose='SILQ data is reported in Saudi Riyal (SAR). The dashboard supports toggling between SAR and USD. Non-monetary metrics (rates, percentages, days, counts) are unaffected.',
        notes=['Exchange rates are fetched live from open.er-api.com and cached for 1 hour. Falls back to static rates (SAR 0.2667) if the API is unavailable.'],
    )
