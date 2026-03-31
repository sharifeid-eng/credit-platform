import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useCompany } from '../contexts/CompanyContext'

// level = Analytical Hierarchy level (see ANALYSIS_FRAMEWORK.md Section 7)
// L1=Size & Composition, L2=Cash Conversion, L3=Credit Quality, L4=Loss Attribution, L5=Forward Signals
const KLAIM_SECTIONS = [
  { id: 'overview', title: 'Portfolio Overview Metrics', level: 1 },
  { id: 'collection-perf', title: 'Collection Performance', level: 2 },
  { id: 'collection-analysis', title: 'Collection Analysis', level: 2 },
  { id: 'health', title: 'Health Classification', level: 3 },
  { id: 'par', title: 'Portfolio at Risk (PAR)', level: 3 },
  { id: 'cohort', title: 'Cohort Analysis', level: null },
  { id: 'returns', title: 'Returns Analysis', level: 4 },
  { id: 'denial-funnel', title: 'Denial Funnel', level: 4 },
  { id: 'loss-waterfall', title: 'Loss Waterfall', level: 4 },
  { id: 'stress', title: 'Stress Testing', level: 5 },
  { id: 'forward-signals', title: 'Forward-Looking Signals', level: 5 },
  { id: 'expected-loss', title: 'Expected Loss Model', level: 4 },
  { id: 'migration', title: 'Roll-Rate Migration', level: 3 },
  { id: 'advanced-analytics', title: 'Advanced Analytics', level: null },
  { id: 'validation', title: 'Data Quality Validation', level: null },
  { id: 'currency', title: 'Currency Conversion', level: null },
]

const SILQ_SECTIONS = [
  { id: 'overview', title: 'Portfolio Overview', level: 1 },
  { id: 'delinquency', title: 'Delinquency & PAR', level: 3 },
  { id: 'collections', title: 'Collections', level: 2 },
  { id: 'concentration', title: 'Concentration', level: 1 },
  { id: 'cohort', title: 'Cohort Analysis', level: null },
  { id: 'yield', title: 'Yield & Margins', level: 4 },
  { id: 'tenure', title: 'Tenure Analysis', level: null },
  { id: 'covenants', title: 'Covenant Monitoring', level: 5 },
  { id: 'products', title: 'Product Types', level: null },
  { id: 'backward-date', title: 'Backward-Date Caveat', level: null },
  { id: 'currency', title: 'Currency Conversion', level: null },
]

const LEVEL_LABELS = {
  1: 'L1', 2: 'L2', 3: 'L3', 4: 'L4', 5: 'L5',
}
const LEVEL_COLORS = {
  1: '#5B8DEF', 2: '#2DD4BF', 3: '#C9A84C', 4: '#F06060', 5: '#A78BFA',
}

export default function Methodology() {
  const { companyName } = useParams()
  const { analysisType } = useCompany()
  const isSilq = analysisType === 'silq'
  const SECTIONS = isSilq ? SILQ_SECTIONS : KLAIM_SECTIONS
  const [active, setActive] = useState('overview')

  useEffect(() => {
    const visibleIds = new Set()
    const observer = new IntersectionObserver(
      entries => {
        for (const e of entries) {
          if (e.isIntersecting) visibleIds.add(e.target.id)
          else visibleIds.delete(e.target.id)
        }
        // pick the first visible section in document order
        const first = SECTIONS.find(s => visibleIds.has(s.id))
        if (first) setActive(first.id)
      },
      { rootMargin: '-56px 0px -40% 0px', threshold: 0 },
    )
    for (const s of SECTIONS) {
      const el = document.getElementById(s.id)
      if (el) observer.observe(el)
    }
    return () => observer.disconnect()
  }, [])

  const scrollTo = id => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div style={{ display: 'flex', minHeight: 'calc(100vh - 56px)' }}>
      {/* Sidebar TOC */}
      <nav style={{
        width: 220,
        flexShrink: 0,
        position: 'sticky',
        top: 104,
        height: 'calc(100vh - 56px)',
        overflowY: 'auto',
        padding: '28px 0 28px 28px',
        borderRight: '1px solid var(--border)',
      }}>
        <div style={{
          fontSize: 9,
          fontWeight: 700,
          textTransform: 'uppercase',
          letterSpacing: '0.12em',
          color: 'var(--text-muted)',
          marginBottom: 16,
        }}>
          Contents
        </div>
        {SECTIONS.map(s => (
          <button
            key={s.id}
            onClick={() => scrollTo(s.id)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              width: '100%',
              textAlign: 'left',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '6px 12px',
              marginBottom: 2,
              fontSize: 11,
              fontWeight: active === s.id ? 600 : 400,
              color: active === s.id ? 'var(--gold)' : 'var(--text-muted)',
              borderLeft: active === s.id ? '2px solid var(--gold)' : '2px solid transparent',
              transition: 'all 0.15s',
              fontFamily: 'var(--font-ui)',
            }}
          >
            {s.title}
            {s.level && (
              <span style={{
                fontSize: 8,
                fontWeight: 700,
                padding: '1px 4px',
                borderRadius: 3,
                backgroundColor: LEVEL_COLORS[s.level] + '18',
                color: LEVEL_COLORS[s.level],
                letterSpacing: '0.04em',
                flexShrink: 0,
              }}>
                {LEVEL_LABELS[s.level]}
              </span>
            )}
          </button>
        ))}
      </nav>

      {/* Main content */}
      <main style={{ flex: 1, padding: '36px 40px 80px', maxWidth: 820 }}>
        {/* Back to dashboard */}
        <Link to={`/company/${companyName}`} style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          textDecoration: 'none',
          fontSize: 11, fontWeight: 600,
          color: 'var(--gold)',
          marginBottom: 16,
          transition: 'opacity 0.15s',
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 12H5" /><path d="M12 19l-7-7 7-7" />
          </svg>
          Back to {companyName?.toUpperCase()} Dashboard
        </Link>
        <h1 style={{
          fontSize: 26,
          fontWeight: 800,
          letterSpacing: '-0.03em',
          color: 'var(--text-primary)',
          margin: '0 0 6px',
        }}>
          Methodology
        </h1>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 36px', lineHeight: 1.6 }}>
          Definitions, formulas, and rationale for every analytical metric in the platform.
          This page documents <em>how</em> metrics are calculated and <em>why</em> they matter for credit analysis.
        </p>

        {isSilq ? <SilqMethodologyContent /> : <>
        {/* 1 — Portfolio Overview */}
        <Section id="overview" title="Portfolio Overview Metrics">
          <Metric
            name="Collection Rate"
            formula="Collected till date / Purchase value"
            rationale="Primary measure of asset performance. Shows the proportion of face value actually recovered. Tracked at portfolio, monthly, cohort, group, and discount-band levels."
          />
          <Metric
            name="Denial Rate"
            formula="Denied by insurance / Purchase value"
            rationale="Measures the proportion of receivables rejected by the insurer. High or rising denial rates signal deterioration in underwriting quality, insurer disputes, or provider documentation issues."
          />
          <Metric
            name="Pending Rate"
            formula="Pending insurance response / Purchase value"
            rationale="Captures receivables still awaiting insurer decision. A growing pending balance indicates slower adjudication or processing bottlenecks."
          />
          <Metric
            name="Weighted DSO (Days Sales Outstanding)"
            formula={<>DSO<sub>w</sub> = &Sigma;(Days<sub>i</sub> &times; Collected<sub>i</sub>) / &Sigma;Collected<sub>i</sub></>}
            rationale="Measures the average time to collect cash, weighted by collection amount. Larger collections carry proportionally more influence. Calculated on completed deals only. When collection curve data is available (30-day interval columns), DSO is estimated by finding when 90% of the deal's total collection arrived (curve-based). Otherwise falls back to deal age (today minus deal date). Critical for sizing financing tenor and projecting liquidity."
          />
          <Metric
            name="Median DSO"
            formula="Median of days to collect across all completed deals"
            rationale="Robust measure of typical collection timing, unaffected by outliers. The 50th percentile of days to collect. Uses curve-based estimation when available."
          />
          <Metric
            name="P95 DSO"
            formula="95th percentile of days to collect on completed deals"
            rationale="Tail-risk measure: 95% of deals resolve within this timeframe. Used to set maximum expected tenor for facility structuring."
          />
          <Metric
            name="HHI (Herfindahl-Hirschman Index)"
            formula={<>HHI = &Sigma;(Share<sub>i</sub>)<sup>2</sup> where Share<sub>i</sub> = Exposure<sub>i</sub> / Total Exposure</>}
            rationale="Standard measure of portfolio concentration. Ranges from 0 (perfectly diversified) to 1 (single counterparty). Computed separately on Group (provider) and Product dimensions. Thresholds: &lt;0.15 unconcentrated, 0.15&ndash;0.25 moderate, &gt;0.25 highly concentrated."
          />
          <Note>
            Top-1, top-5, and top-10 counterparty shares are also reported alongside HHI to identify single-name risk.
          </Note>
        </Section>

        {/* 2 — Collection Performance */}
        <Section id="collection-perf" title="Collection Performance">
          <p style={styles.body}>
            The Collection Performance chart (Actual vs Expected tab) displays three cumulative lines
            to assess whether the portfolio is collecting on schedule and how much lifetime value remains outstanding.
          </p>
          <Subsection title="Three Lines">
            <Table
              headers={['Line', 'Data Source', 'What It Answers']}
              rows={[
                ['Collected', 'Cumulative Collected till date by deal month', 'How much cash has actually been received?'],
                ['Forecast (expected by now)', 'Cumulative Expected till date by deal month', 'How much should have been collected by now based on payment schedules?'],
                ['Expected Total', 'Cumulative Expected total by deal month', 'What is the full lifetime expected collection (ceiling)?'],
              ]}
            />
          </Subsection>
          <Subsection title="Key Metrics">
            <Metric
              name="Pacing %"
              formula="Collected till date / Expected till date"
              rationale={<>Primary performance indicator. A value above 100% means collections are <em>ahead</em> of the time-based forecast.
                Below 100% signals delays relative to expected payment schedules. This is the badge shown on the chart.</>}
            />
            <Metric
              name="Recovery %"
              formula="Collected till date / Expected total"
              rationale="Measures how much of the full lifetime expected has been recovered so far. Will always be below 100% for a live portfolio with active deals. Converges toward 100% as deals complete."
            />
          </Subsection>
          <Note>
            Forecast requires the &ldquo;Expected till date&rdquo; column in the tape. When this column is unavailable, the chart
            falls back to a two-line view (Collected vs Expected Total) using recovery % as the badge.
          </Note>
        </Section>

        {/* 3 — Collection Analysis */}
        <Section id="collection-analysis" title="Collection Analysis">
          <p style={styles.body}>
            The Collection tab tracks how quickly cash is received and how collection patterns evolve over time.
          </p>
          <Subsection title="Monthly Collection Rate">
            <Metric
              name="Collection Rate"
              formula="Collected till date / Purchase value (per month)"
              rationale="Monthly collection rate with a 3-month rolling average overlay. Shows the trend of cash recovery efficiency across deal origination months. Note: recent vintages will naturally show low rates because active deals are still collecting — this does not indicate underperformance."
            />
            <Metric
              name="Expected Collection Rate"
              formula="Expected till date / Purchase value (per month)"
              rationale="Forecast benchmark showing what the portfolio model expects to have collected by now for each vintage. Rendered as a blue dashed line alongside the actual rate bars. The gap between actual and expected isolates true underperformance from normal deal seasoning — if actual tracks at or above expected, the vintage is on track regardless of absolute rate level. Available on all tapes."
            />
          </Subsection>
          <Subsection title="Cash Collection Breakdown">
            <p style={styles.body}>
              Completed deals are grouped by <strong>how long they took to collect</strong> into six time buckets
              (0{'\u2013'}30d, 31{'\u2013'}60d, 61{'\u2013'}90d, 91{'\u2013'}120d, 121{'\u2013'}180d, 181+d).
              This chart only includes completed deals; active deals still collecting are excluded.
            </p>
            <Metric
              name="Curve-Based Collection Time"
              formula="Interpolated days when actual collections reach 90% of total collected (from 30-day interval curve data)"
              rationale={<>When the tape includes collection curve columns (Actual in 30 days, Actual in 60 days, etc.),
                the system estimates true collection time by finding the interval where 90% of the deal&rsquo;s total
                was received, then interpolates. This is far more accurate than using deal age (today minus deal date),
                which conflates how old a deal is with how fast it collected. Falls back to deal age on tapes without curve data.</>}
            />
          </Subsection>
          <Subsection title="Collection Curves (Expected vs Actual)">
            <p style={styles.body}>
              When curve columns are available (30-day intervals up to 390 days), the platform plots expected vs actual
              cumulative collection as a percentage of purchase value. Available at both portfolio aggregate and per-vintage levels.
            </p>
            <Metric
              name="Model Accuracy"
              formula="Actual collection % / Expected collection % (per interval)"
              rationale="Measures how well Klaim's expected collection schedule matches reality at each 30-day checkpoint. Values above 100% indicate faster-than-expected collection; below 100% indicates delays. Chart Y-axis is capped at 200% for readability, with real values shown in tooltips."
            />
          </Subsection>
        </Section>

        {/* 4 — Health Classification */}
        <Section id="health" title="Health Classification">
          <p style={styles.body}>
            Active deals (Status = &ldquo;Executed&rdquo;) are classified by days outstanding from deal origination to the as-of date.
          </p>
          <Table
            headers={['Bucket', 'Days Outstanding', 'Interpretation']}
            rows={[
              ['Healthy', '0\u201360 days', 'Within normal collection cycle'],
              ['Watch', '61\u201390 days', 'Approaching delayed territory, warrants monitoring'],
              ['Delayed', '91\u2013120 days', 'Past expected collection window, elevated risk'],
              ['Poor', '>120 days', 'Material delinquency, likely requires remediation or provisioning'],
            ]}
          />
          <p style={styles.body}>
            <strong>Rationale:</strong> Health classification provides a snapshot of portfolio quality at any point in time.
            The thresholds are calibrated to healthcare receivables, where typical collection cycles are 30&ndash;90 days.
            Deals aging beyond 120 days have historically lower recovery rates.
          </p>
          <Note>
            Health classification is measured by <strong>outstanding amount</strong> (Purchase Value &minus; Collected &minus; Denied),
            not face value. This reflects true residual risk exposure — a deal with AED 100K face value but AED 95K already
            collected has only AED 5K outstanding, correctly contributing minimal weight to the &ldquo;Poor&rdquo; bucket even
            if it is aged beyond 120 days. The Ageing and Portfolio Health charts both use this metric.
          </Note>
        </Section>

        {/* 5 — Portfolio at Risk (PAR) */}
        <Section id="par" title="Portfolio at Risk (PAR)">
          <p style={styles.body}>
            PAR measures the share of the portfolio that is behind schedule, weighted by outstanding amount.
            Laith reports two perspectives for Klaim:
          </p>
          <Table
            headers={['Perspective', 'Denominator', 'Use Case']}
            rows={[
              ['Lifetime PAR', 'Total originated outstanding', 'IC reporting — headline metric'],
              ['Active PAR', 'Active outstanding only', 'Operational monitoring — context metric'],
            ]}
          />
          <Note>
            Active outstanding is typically only 7–9% of total originated for Klaim (most deals have collected
            or been denied). This means Active PAR can appear alarmingly high (e.g. 46%) while Lifetime PAR
            is benign (e.g. 3.6%). Always read Lifetime PAR as the headline; Active PAR provides operational context.
          </Note>
          <Subsection title="PAR Computation Methods">
            <p style={styles.body}>Three methods are applied in priority order:</p>
            <Table
              headers={['Method', 'Description', 'Confidence']}
              rows={[
                ['Primary', 'Shortfall-based estimated DPD using Expected till date column', 'B — Inferred'],
                ['Option C', 'Empirical benchmarks from 50+ completed deals — labeled "Derived"', 'C — Derived'],
                ['Unavailable', 'Returns available: false when neither method has sufficient data', '—'],
              ]}
            />
          </Subsection>
          <Subsection title="PAR Thresholds">
            <Table
              headers={['Metric', 'Threshold', 'Interpretation']}
              rows={[
                ['PAR 30+', '>2% lifetime', 'Elevated — monitor trend'],
                ['PAR 30+', '>5% lifetime', 'High — escalate to IC'],
                ['PAR 60+', '>1.5% lifetime', 'Elevated'],
                ['PAR 90+', '>1% lifetime', 'Material impairment signal'],
              ]}
            />
          </Subsection>
          <Note>
            For Klaim, there are no contractual due dates — PAR is approximated using the Expected till date
            column as a proxy for the repayment schedule. Deals where outstanding exceeds Expected till date
            by a threshold are treated as behind schedule. Option C builds empirical benchmarks from completed
            deals that collected on time, and uses those patterns to assess active deals.
          </Note>
        </Section>

        {/* 3 — Cohort Analysis */}
        <Section id="cohort" title="Cohort Analysis">
          <p style={styles.body}>
            Deals are grouped into monthly vintages by origination date (Deal date).
            Each cohort is analyzed independently to identify trends across origination periods.
          </p>
          <Subsection title="Metrics per Cohort (up to 17 columns)">
            <Table
              headers={['Metric', 'Formula / Source']}
              rows={[
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
                ['Expected Margin', '(Purchase Value \u2212 Purchase Price) / Purchase Price'],
                ['Realised Margin', '(Collected \u2212 Purchase Price) / Purchase Price (completed deals only)'],
                ['Avg Expected IRR', 'Mean of Expected IRR column (when available)'],
                ['Avg Actual IRR', 'Mean of Actual IRR column (filtered: outliers >1000% excluded)'],
                ['90D %', '% of purchase value collected within 90 days (curve-based, when available)'],
                ['180D %', '% of purchase value collected within 180 days (curve-based, when available)'],
                ['360D %', '% of purchase value collected within 360 days (curve-based, when available)'],
              ]}
            />
          </Subsection>
          <Subsection title="Collection Speed (90D / 180D / 360D)">
            <p style={styles.body}>
              When collection curve data is available, three additional columns show the percentage of purchase value
              collected within 90, 180, and 360 days respectively. These are color-coded for quick assessment:
              green for high collection speed, yellow for moderate, red for slow. These columns are hidden entirely
              on tapes that lack curve data.
            </p>
          </Subsection>
          <Subsection title="IRR Derivation">
            <p style={styles.body}>
              When tape data lacks explicit IRR columns, the backend derives an approximate IRR from
              purchase price, collected amount, and deal dates. This provides comparable return metrics across all vintages.
            </p>
          </Subsection>
          <Subsection title="Totals Row">
            <p style={styles.body}>
              A portfolio-wide totals row aggregates all cohorts. Rates (collection, denial, margins) in the totals row
              are calculated from aggregated numerators and denominators, not as averages of cohort-level rates, to avoid
              size-bias distortion.
            </p>
          </Subsection>
        </Section>

        {/* 4 — Returns Analysis */}
        <Section id="returns" title="Returns Analysis">
          <Subsection title="Portfolio Margin Metrics">
            <Metric
              name="Expected Margin"
              formula="(Purchase Value \u2212 Purchase Price) / Purchase Price"
              rationale="The theoretical return if 100% of face value is collected. Represents the discount captured at origination."
            />
            <Metric
              name="Realised Margin"
              formula="(Collected \u2212 Purchase Price) / Purchase Price — on completed deals only"
              rationale="True outcome-based return computed exclusively on deals that have fully resolved (Status = 'Completed'). Active deals are excluded because they are still collecting and would artificially depress the margin. This applies to portfolio-level, monthly, discount band, and new vs repeat margin calculations. Divergence from expected margin signals collection shortfalls or over-performance."
            />
            <Metric
              name="Capital Recovery"
              formula="Total Collected / Total Purchase Price \u00d7 100"
              rationale="Percentage of total deployed capital that has been returned as cash collections across all deals (active and completed). A rate below 100% indicates deployed capital is still outstanding; rates above 100% indicate profitable recovery. Complements Realised Margin by showing absolute capital return rather than just completed-deal profitability."
            />
            <Metric
              name="Fee Yield"
              formula="(Setup Fees + Other Fees) / Purchase Value"
              rationale="Ancillary income as a proportion of deployed capital. Captures non-discount revenue."
            />
          </Subsection>
          <Subsection title="Discount Band Analysis">
            <p style={styles.body}>Deals are grouped by discount rate into six bands to assess performance by pricing tier:</p>
            <Table
              headers={['Band', 'Range']}
              rows={[
                ['1', '\u22644%'],
                ['2', '4\u20136%'],
                ['3', '6\u20138%'],
                ['4', '8\u201310%'],
                ['5', '10\u201315%'],
                ['6', '>15%'],
              ]}
            />
            <p style={styles.body}>
              For each band: deal count, face value, cost, collected, collection rate, denial rate, and margin.
              Margins are computed on completed deals within each band to reflect true outcomes rather than
              in-progress deal distortion. Higher discount bands should theoretically compensate for higher risk;
              this analysis tests that relationship.
            </p>
          </Subsection>
          <Subsection title="New vs. Repeat Business">
            <p style={styles.body}>
              Deals are classified based on the &ldquo;New business&rdquo; column. Any non-null, non-zero, non-empty value
              indicates a new relationship; otherwise the deal is classified as repeat business.
              Performance is compared across both groups to assess whether repeat clients perform differently.
              Margins are computed on completed deals within each group for accuracy.
            </p>
          </Subsection>
        </Section>

        {/* 5 — Denial Funnel */}
        <Section id="denial-funnel" title="Denial Funnel (Resolution Pipeline)">
          <p style={styles.body}>
            A five-stage pipeline tracking how the total portfolio value resolves over time:
          </p>
          <Table
            headers={['Stage', 'Definition']}
            rows={[
              ['Total Portfolio', 'Sum of all purchase values (100% baseline)'],
              ['Collected', 'Cash received to date'],
              ['Pending Response', 'Awaiting insurer adjudication'],
              ['Denied', 'Rejected by insurer (adverse decision)'],
              ['Provisioned', 'Loss reserves set against denied amounts'],
            ]}
          />
          <Metric
            name="Net Loss"
            formula="Denied \u2212 Provisions"
            rationale="Unrecovered portion of denied receivables after provisions are applied. Represents the true economic loss to the portfolio."
          />
          <Metric
            name="Recovery Rate"
            formula="Provisions / Denied"
            rationale="Proportion of denied amounts covered by provisions. A rate below 100% indicates unprovisioned exposure."
          />
          <Note>
            Unresolved balance (Total {'\u2212'} Collected {'\u2212'} Denied {'\u2212'} Pending) is also tracked as residual exposure.
          </Note>
        </Section>

        {/* Loss Waterfall */}
        <Section id="loss-waterfall" title="Loss Waterfall">
          <p style={styles.body}>
            The Loss Waterfall tab provides a per-vintage decomposition of how originated capital flows
            through to net loss. It follows the <strong>Separation Principle</strong>: the clean portfolio
            (active + normal completed) is kept separate from the loss portfolio (denial &gt; 50% of purchase value)
            to prevent loss deals from distorting healthy portfolio metrics.
          </p>
          <Subsection title="Default Definition">
            <p style={styles.body}>
              For Klaim, there are no contractual due dates. A deal is classified as a <strong>gross default</strong> when
              the insurance denial exceeds 50% of the purchase value. This is the functional equivalent of a credit loss
              event for healthcare receivables factoring.
            </p>
          </Subsection>
          <Subsection title="Waterfall Steps (per vintage)">
            <Table
              headers={['Step', 'Definition', 'Formula']}
              rows={[
                ['Originated', 'Total purchase value of deals in the vintage', '∑ Purchase Value'],
                ['Gross Default', 'Deals where Denied > 50% of Purchase Value', '∑ PV of loss deals'],
                ['Recovery', 'Amount actually collected on default deals', '∑ Collected on loss deals'],
                ['Net Loss', 'Unrecovered portion after collections', 'Gross Default − Recovery'],
              ]}
            />
          </Subsection>
          <Subsection title="Loss Categorization (Heuristics)">
            <p style={styles.body}>
              Rules-based classification of loss deals into probable root causes. Not ML — transparent
              heuristics for analyst interpretation:
            </p>
            <ul style={styles.list}>
              <li><strong>Provider Issue:</strong> High denial concentration from a specific Group (provider_issue)</li>
              <li><strong>Coding Error:</strong> Partial denials suggesting claim coding or documentation issues</li>
              <li><strong>Credit / Underwriting:</strong> Remaining unexplained denials attributed to credit decision quality</li>
            </ul>
            <Note>
              Categories are mutually exclusive and exhaustive. They are starting points for investigation,
              not definitive classifications. Reason code analysis from the insurer is the authoritative source.
            </Note>
          </Subsection>
          <Subsection title="Recovery Analysis">
            <p style={styles.body}>
              Recovery rates and timing are tracked per vintage for deals that experienced gross default.
              Key metrics: recovery rate (% of defaulted amount recovered), average recovery days,
              and worst/best performing deals by vintage.
            </p>
          </Subsection>
        </Section>

        {/* 6 — Stress Testing */}
        <Section id="stress" title="Stress Testing">
          <p style={styles.body}>
            Three provider-shock scenarios simulate the impact of counterparty distress on portfolio collections.
            Each scenario identifies the affected provider groups, applies a haircut to their collected amounts,
            and recomputes portfolio-level metrics.
          </p>
          <Table
            headers={['Scenario', 'Counterparties', 'Haircut', 'Rationale']}
            rows={[
              ['Severe', 'Top 1 provider', '50%', 'Single-name concentration risk \u2014 largest provider halves payments'],
              ['Moderate', 'Top 3 providers', '30%', 'Sector-wide stress \u2014 top three providers simultaneously impaired'],
              ['Mild', 'Top 5 providers', '20%', 'Broad market stress \u2014 widespread but shallow reduction'],
            ]}
          />
          <Subsection title="Metrics per Scenario">
            <ul style={styles.list}>
              <li><strong>Affected exposure:</strong> Face value of deals linked to stressed providers</li>
              <li><strong>Collection loss:</strong> Affected collected amount multiplied by haircut percentage</li>
              <li><strong>Stressed collection rate:</strong> (Original collected {'\u2212'} loss) / total face value</li>
              <li><strong>Rate impact:</strong> Change in collection rate from base scenario</li>
              <li><strong>Portfolio value retained:</strong> (Face value {'\u2212'} loss) / face value</li>
            </ul>
          </Subsection>
          <Note>
            Provider ranking is based on total exposure (purchase value) to that counterparty.
            If provider names are not normalized, concentration may be understated.
          </Note>
        </Section>

        {/* 7 — Expected Loss Model */}
        <Section id="expected-loss" title="Expected Loss Model">
          <p style={styles.body}>
            The expected loss framework follows the standard credit risk formulation:
          </p>
          <Formula>EL = PD &times; LGD &times; EAD</Formula>
          <Subsection title="Components">
            <Metric
              name="Probability of Default (PD)"
              formula="Deals with denial > 1% of purchase value / Total completed deals"
              rationale="Estimated from historical outcomes on completed deals. A deal is considered 'defaulted' if it experienced material denial (>1% of face value). The 1% threshold filters out de minimis adjustments."
            />
            <Metric
              name="Loss Given Default (LGD)"
              formula="(Total Denied \u2212 Total Provisions) / Total Denied"
              rationale="Measures the unrecovered loss rate on defaulted deals. Provisions offset denials; what remains is the true economic loss per unit of default."
            />
            <Metric
              name="Exposure at Default (EAD)"
              formula="Purchase value of all active (Executed) deals"
              rationale="Current outstanding portfolio balance exposed to potential loss. Only active deals are at risk; completed deals have already resolved."
            />
            <Metric
              name="Expected Loss Rate"
              formula="EL / EAD"
              rationale="Normalised loss expectation as a percentage of exposure. Used to benchmark against advance rates and required reserves."
            />
          </Subsection>
          <Subsection title="By Vintage">
            <p style={styles.body}>
              PD, LGD, and EAD are also calculated per origination month to identify if loss is concentrated
              in specific cohorts or distributed evenly across the portfolio.
            </p>
          </Subsection>
        </Section>

        {/* Forward-Looking Signals */}
        <Section id="forward-signals" title="Forward-Looking Signals">
          <p style={styles.body}>
            Forward-looking signals are metrics that historically deteriorate <em>before</em> the collection
            rate does. They provide early warning of portfolio stress and complement lagging indicators.
          </p>
          <Subsection title="DTFC — Days to First Cash">
            <Metric
              name="DTFC (Median)"
              formula="Days from deal origination to first cash receipt — median across active deals"
              rationale="A lengthening DTFC means insurers are taking longer to make initial payments. This typically precedes a decline in collection rate by 30–60 days, making it a leading indicator of portfolio stress. Confidence grade B (curve-based) or C (estimated)."
            />
            <Metric
              name="DTFC (P90)"
              formula="90th percentile of days to first cash"
              rationale="Captures the slowest-paying tail of the portfolio. Rising P90 indicates the worst deals are getting worse faster than the median, a signal of selective non-payment."
            />
            <Table
              headers={['Method', 'How Computed', 'Grade']}
              rows={[
                ['Curve-based', 'Uses 30-day collection curve columns — finds first non-zero interval', 'B'],
                ['Estimated', 'Approximates from deal date and first collected amount date', 'C'],
              ]}
            />
          </Subsection>
          <Subsection title="HHI — Concentration Time Series">
            <Metric
              name="HHI (Herfindahl-Hirschman Index)"
              formula="HHI = ∑ (Share_i)² where Share_i = Group_i outstanding / Total outstanding"
              rationale="Measures portfolio concentration. A rising HHI across snapshots indicates the portfolio is becoming more concentrated in fewer providers — a risk factor even if current collection rates are healthy."
            />
            <Table
              headers={['HHI Range', 'Classification', 'Interpretation']}
              rows={[
                ['< 0.10', 'Diversified', 'Low concentration risk'],
                ['0.10 – 0.15', 'Moderate', 'Monitor top providers closely'],
                ['> 0.15', 'Concentrated', 'Single-name risk elevated'],
              ]}
            />
            <Note>
              HHI trend (increasing / stable / decreasing) is computed across all available snapshots.
              A warning is issued when HHI is rising and already above 0.10. Grade A — directly computed
              from tape data.
            </Note>
          </Subsection>
          <Subsection title="DSO — Dual Perspectives">
            <Metric
              name="DSO Capital"
              formula="Days from deal origination (funding date) to collection — measures capital duration"
              rationale="How long the fund's capital is tied up. Directly impacts IRR and reinvestment capacity. A rising DSO Capital means slower return of capital."
            />
            <Metric
              name="DSO Operational"
              formula="Days from Expected till date (due date) to actual collection — measures payer behaviour"
              rationale="How late insurers are paying relative to schedule. Rising DSO Operational indicates payer deterioration independent of deal maturity. The two clocks decouple: DSO Capital can be fine while Operational worsens."
            />
            <Note>
              Both DSO variants use the curve-based method when 30-day collection curve columns are available
              (Mar 2026+ tapes), finding the day when 90% of the deal's collection arrived. Falls back to
              deal-age estimation on older tapes. Curve-based = grade B, estimated = grade C.
            </Note>
          </Subsection>
        </Section>

        {/* 8 — Roll-Rate Migration */}
        <Section id="migration" title="Roll-Rate Migration">
          <p style={styles.body}>
            Migration analysis tracks how deals move between ageing buckets across two consecutive snapshots.
            This requires at least two loan tape snapshots of the same portfolio taken at different points in time.
          </p>
          <Subsection title="Ageing Buckets">
            <Table
              headers={['Bucket', 'Criteria']}
              rows={[
                ['Paid', 'Status = "Completed"'],
                ['0\u201330 days', 'Active, \u226430 days from deal date'],
                ['31\u201360 days', 'Active, 31\u201360 days'],
                ['61\u201390 days', 'Active, 61\u201390 days'],
                ['91\u2013180 days', 'Active, 91\u2013180 days'],
                ['180+ days', 'Active, >180 days'],
              ]}
            />
          </Subsection>
          <Subsection title="Deal Matching">
            <p style={styles.body}>
              Deals are matched across snapshots using the ID column (tries: ID, Deal ID, Reference, and variants).
              Only deals present in both snapshots are included in the transition matrix.
            </p>
          </Subsection>
          <Subsection title="Transition Matrix">
            <p style={styles.body}>
              A matrix where rows represent the bucket in the earlier snapshot and columns represent the bucket
              in the later snapshot. Each cell shows the count and percentage of deals making that transition.
              Diagonal entries indicate deals that stayed in the same bucket; above-diagonal indicates improvement; below-diagonal indicates deterioration.
            </p>
          </Subsection>
          <Subsection title="Cure Rates">
            <Metric
              name="Cure Rate"
              formula="Deals improving (moving to lower bucket or Paid) / Total delinquent deals"
              rationale="Measures the probability that delinquent receivables recover. Calculated for each delinquent bucket (61\u201390, 91\u2013180, 180+). High cure rates reduce required reserves and support higher advance rates."
            />
          </Subsection>
          <Subsection title="Summary Statistics">
            <ul style={styles.list}>
              <li><strong>Improved:</strong> % of deals that moved to a better bucket</li>
              <li><strong>Stable:</strong> % of deals that remained in the same bucket</li>
              <li><strong>Worsened:</strong> % of deals that moved to a worse bucket</li>
            </ul>
          </Subsection>
        </Section>

        {/* Advanced Analytics */}
        <Section id="advanced-analytics" title="Advanced Analytics">
          <p style={styles.body}>
            The following tabs provide deeper analytical cuts beyond the core performance metrics.
            All use the same underlying tape data with no additional configuration required.
          </p>
          <Subsection title="Collections Timing">
            <p style={styles.body}>
              Uses 30-day collection curve columns (Mar 2026+ tapes) to show how cash arrives over the life
              of a deal. Broken into timing buckets: 0–30d, 30–60d, 60–90d, 90–120d, 120–180d, 180d+.
              Two views: by payment month (liquidity quality) and by origination month (vintage behaviour).
              Requires curve columns — hidden on older tapes.
            </p>
          </Subsection>
          <Subsection title="Underwriting Drift">
            <p style={styles.body}>
              Tracks per-vintage origination characteristics over time: average deal size, discount rate,
              and collection rate. Computes a rolling 6-month baseline and flags vintages where any metric
              deviates beyond 1 standard deviation from the norm. Drift flags are displayed as badges.
            </p>
            <Note>
              Underwriting drift is distinct from credit quality deterioration. A vintage can have excellent
              credit quality but show underwriting drift if deal sizes are growing unusually fast.
            </Note>
          </Subsection>
          <Subsection title="Segment Analysis">
            <p style={styles.body}>
              Multi-dimensional performance cuts across four dimensions, each producing a sortable heat-map table:
            </p>
            <ul style={styles.list}>
              <li><strong>Product Type:</strong> Performance by insurance product/claim type</li>
              <li><strong>Provider Size:</strong> Bucketed by total purchase value volume (Small / Medium / Large)</li>
              <li><strong>Deal Size:</strong> Quartile-based bucketing of individual deal sizes</li>
              <li><strong>New vs Repeat:</strong> First-time vs returning counterparties</li>
            </ul>
            <p style={styles.body}>
              Each segment shows deal count, total volume, collection rate, denial rate, and realised margin.
              Heat-map colouring highlights outlier segments relative to the portfolio average.
            </p>
          </Subsection>
          <Subsection title="Seasonality">
            <p style={styles.body}>
              Groups monthly deployment by calendar month across years for year-over-year comparison.
              Computes a seasonal index (month average / overall average) to quantify seasonal patterns.
              Index &gt; 1.0 indicates above-average origination months; &lt; 1.0 below-average.
            </p>
          </Subsection>
        </Section>

        {/* 9 — Data Quality Validation */}
        <Section id="validation" title="Data Quality Validation">
          <p style={styles.body}>
            Automated checks run against each loan tape to flag data issues before analysis.
            Issues are categorised by severity.
          </p>
          <Subsection title="Critical Issues (must fix)">
            <ul style={styles.list}>
              <li><strong>Duplicate IDs:</strong> Multiple rows sharing the same deal identifier</li>
              <li><strong>Future deal dates:</strong> Origination dates after today</li>
              <li><strong>Missing required columns:</strong> Purchase value, Purchase price, Status, Collected, Denied</li>
            </ul>
          </Subsection>
          <Subsection title="Warnings (review required)">
            <ul style={styles.list}>
              <li><strong>Null deal dates:</strong> Unparseable or missing origination dates</li>
              <li><strong>Very old deal dates:</strong> Before 2018-01-01</li>
              <li><strong>Negative amounts:</strong> Negative values in financial columns</li>
              <li><strong>Over-collection:</strong> Collected exceeds 150% of purchase value</li>
              <li><strong>Completed with zero collection:</strong> Deal marked complete with no cash received</li>
              <li><strong>Discount anomalies:</strong> Discount &gt;100% or negative</li>
              <li><strong>Low column completeness:</strong> Columns with &lt;90% non-null values</li>
              <li><strong>Unexpected status values:</strong> Status not &ldquo;Executed&rdquo; or &ldquo;Completed&rdquo;</li>
            </ul>
          </Subsection>
          <Subsection title="Anomaly Detection (review required)">
            <p style={styles.body}>
              Statistical and pattern-based checks that flag unusual data signatures:
            </p>
            <ul style={styles.list}>
              <li>
                <strong>Duplicate counterparty + amount + date:</strong> Rows sharing the same Group,
                Purchase value, and Deal date — possible double-entry without a unique ID match.
              </li>
              <li>
                <strong>Identical amount concentration:</strong> A single Purchase value appearing in
                &gt;5% of all deals (minimum 10 occurrences) — may indicate templated or copy-paste entries.
              </li>
              <li>
                <strong>Deal size outliers:</strong> Purchase values outside the 3&times;IQR fence
                (Q3 + 3&times;IQR upper, Q1 − 3&times;IQR lower). Flags statistical extremes
                that warrant individual review.
              </li>
              <li>
                <strong>Discount outliers:</strong> Discount rates outside the 3&times;IQR fence
                within the valid 0–100% range. Unusual discounts may indicate pricing errors.
              </li>
              <li>
                <strong>Balance identity violations:</strong> Deals where
                Collected + Denied + Pending &gt; 105% of Purchase value.
                The 5% tolerance accommodates rounding and fee adjustments.
              </li>
            </ul>
          </Subsection>
          <Subsection title="Informational">
            <ul style={styles.list}>
              <li>Total row count</li>
              <li>Deal date range (earliest to latest)</li>
              <li>Status distribution (Executed vs Completed counts)</li>
            </ul>
          </Subsection>
        </Section>

        {/* 10 — Currency Conversion */}
        <Section id="currency" title="Currency Conversion">
          <p style={styles.body}>
            Each portfolio company reports data in a local currency configured via <Code>config.json</Code>.
            All monetary values can be toggled between the reported currency and USD.
          </p>
          <Table
            headers={['Currency', 'USD Rate', 'Notes']}
            rows={[
              ['AED', '0.2723', 'UAE Dirham \u2014 used by Klaim'],
              ['USD', '1.0000', 'Base currency'],
              ['EUR', '1.0800', 'Euro'],
              ['GBP', '1.2700', 'British Pound'],
              ['SAR', '0.2667', 'Saudi Riyal'],
              ['KWD', '3.2600', 'Kuwaiti Dinar'],
            ]}
          />
          <p style={styles.body}>
            When display currency is set to USD and the reported currency differs, all amounts are
            multiplied by the reported currency&rsquo;s USD rate. Non-monetary metrics (rates, percentages,
            days, counts) are unaffected by currency conversion.
          </p>
          <Note>
            Exchange rates are fetched live from open.er-api.com and cached for 1 hour. Falls back to static rates if the API is unavailable.
          </Note>
        </Section>
        </>}
      </main>
    </div>
  )
}


/* ── Reusable sub-components ───────────────────────────────── */

function Section({ id, title, children }) {
  return (
    <section id={id} style={{ marginBottom: 40, scrollMarginTop: 120 }}>
      <h2 style={{
        fontSize: 20,
        fontWeight: 700,
        color: 'var(--text-primary)',
        margin: '0 0 16px',
        paddingBottom: 10,
        borderBottom: '1px solid var(--border)',
      }}>
        {title}
      </h2>
      {children}
    </section>
  )
}

function Subsection({ title, children }) {
  return (
    <div style={{ marginTop: 20, marginBottom: 12 }}>
      <h3 style={{
        fontSize: 14,
        fontWeight: 700,
        color: 'var(--text-primary)',
        margin: '0 0 8px',
      }}>
        {title}
      </h3>
      {children}
    </div>
  )
}

function Metric({ name, formula, rationale }) {
  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)',
      padding: '14px 18px',
      marginBottom: 10,
    }}>
      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6 }}>
        {name}
      </div>
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 12,
        color: 'var(--gold)',
        background: 'var(--bg-deep)',
        borderRadius: 'var(--radius-sm)',
        padding: '6px 10px',
        marginBottom: 8,
        display: 'inline-block',
      }}>
        {formula}
      </div>
      <div style={{ fontSize: 12, lineHeight: 1.7, color: 'var(--text-muted)' }}>
        {rationale}
      </div>
    </div>
  )
}

function Formula({ children }) {
  return (
    <div style={{
      fontFamily: 'var(--font-mono)',
      fontSize: 16,
      fontWeight: 700,
      color: 'var(--gold)',
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)',
      padding: '16px 20px',
      marginBottom: 16,
      textAlign: 'center',
      letterSpacing: '0.02em',
    }}>
      {children}
    </div>
  )
}

function Table({ headers, rows }) {
  return (
    <div style={{ overflowX: 'auto', marginBottom: 12 }}>
      <table style={{
        width: '100%',
        borderCollapse: 'collapse',
        fontSize: 12,
        fontFamily: 'var(--font-ui)',
      }}>
        <thead>
          <tr>
            {headers.map((h, i) => (
              <th key={i} style={{
                textAlign: 'left',
                padding: '8px 12px',
                borderBottom: '1px solid var(--border)',
                color: 'var(--text-muted)',
                fontWeight: 600,
                fontSize: 10,
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                background: 'var(--bg-surface)',
              }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri}>
              {row.map((cell, ci) => (
                <td key={ci} style={{
                  padding: '8px 12px',
                  borderBottom: '1px solid var(--border-faint)',
                  color: ci === 0 ? 'var(--text-primary)' : 'var(--text-muted)',
                  fontWeight: ci === 0 ? 600 : 400,
                  fontFamily: ci === 0 ? 'var(--font-mono)' : 'var(--font-ui)',
                }}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Note({ children }) {
  return (
    <div style={{
      fontSize: 11,
      lineHeight: 1.6,
      color: 'var(--text-muted)',
      background: 'rgba(201,168,76,0.06)',
      border: '1px solid rgba(201,168,76,0.15)',
      borderRadius: 'var(--radius-sm)',
      padding: '10px 14px',
      marginTop: 8,
      marginBottom: 12,
    }}>
      {children}
    </div>
  )
}

function Code({ children }) {
  return (
    <code style={{
      fontFamily: 'var(--font-mono)',
      fontSize: 11,
      background: 'var(--bg-deep)',
      borderRadius: 3,
      padding: '2px 5px',
      color: 'var(--gold)',
    }}>
      {children}
    </code>
  )
}


/* ── SILQ Methodology Content ────────────────────────────────── */

function SilqMethodologyContent() {
  const styles = {
    body: { fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.7, margin: '0 0 10px' },
  }

  return (
    <>
      <Section id="overview" title="Portfolio Overview">
        <Metric
          name="Total Disbursed"
          formula="sum(Disbursed_Amount) across all loans"
          rationale="Total capital deployed into the market. Includes all products (BNPL, RBF). This is the principal amount lent, not including accrued margin."
        />
        <Metric
          name="Outstanding Amount"
          formula="sum(Outstanding_Amount) for active loans"
          rationale="Current exposure at risk. Can exceed Disbursed Amount because it includes accrued margin — this is expected, not a data error."
        />
        <Metric
          name="Collection Rate"
          formula="sum(Amt_Repaid) / sum(Total_Collectable_Amount)"
          rationale="Proportion of collectable amount actually recovered. Denominator includes principal plus expected margin. Tracks overall portfolio recovery effectiveness."
        />
        <Metric
          name="HHI (Shop)"
          formula="sum((shop_disbursed / total_disbursed)^2) for each shop"
          rationale="Herfindahl-Hirschman Index measuring shop concentration. Ranges from 0 (perfectly diversified) to 1 (single counterparty). Values below 0.15 indicate low concentration."
        />
      </Section>

      <Section id="delinquency" title="Delinquency & PAR">
        <Metric
          name="Days Past Due (DPD)"
          formula="max(0, ref_date - Repayment_Deadline)"
          rationale="Number of days a loan is overdue. Closed loans always have DPD = 0 regardless of deadline. The reference date is the tape date or as-of date — never today's date. This ensures point-in-time accuracy."
        />
        <Metric
          name="PAR30 / PAR60 / PAR90"
          formula="Outstanding of loans with DPD > X / Total Outstanding of active loans"
          rationale="Portfolio at Risk — GBV-weighted, not count-based. This means a single large overdue loan contributes more to PAR than many small ones. GBV weighting reflects actual risk exposure and aligns with the compliance certificate methodology."
        />
        <Note>
          <strong>Why GBV-weighted, not count-based?</strong> Count-based PAR treats every loan equally regardless of size.
          A SAR 10M overdue loan counts the same as a SAR 1K one. GBV weighting reflects the actual capital at risk,
          which is what matters for credit decisions and covenant compliance.
        </Note>
        <Metric
          name="DPD Buckets"
          formula="Current (0), 1-30, 31-60, 61-90, 90+"
          rationale="Distribution of active loans by days past due. Amount shown is Outstanding Amount per bucket, giving a view of where delinquent capital is concentrated."
        />
      </Section>

      <Section id="collections" title="Collections">
        <Metric
          name="Repayment Rate"
          formula="sum(Amt_Repaid) / sum(Total_Collectable_Amount)"
          rationale="Overall collection effectiveness. Shown at portfolio level and broken down by product (BNPL vs RBF). Monthly trend shows collections momentum."
        />
        <Metric
          name="Margin Collected"
          formula="sum(Margin Collected)"
          rationale="Revenue component of collections (interest/fees earned). Only available for BNPL products — RBF revenue is structured differently (baked into repayment, not separated as a distinct column)."
        />
        <Metric
          name="Principal Collected"
          formula="sum(Principal Collected)"
          rationale="Capital return component. Principal + Margin = Total Repaid."
        />
      </Section>

      <Section id="concentration" title="Concentration">
        <Metric
          name="Shop Concentration"
          formula="Top N shops by disbursed amount / total disbursed"
          rationale="Measures counterparty risk. High concentration in a single shop means a default there would materially impact the portfolio."
        />
        <Metric
          name="Credit Utilization"
          formula="Outstanding_Amount / Shop_Credit_Limit per shop"
          rationale="How much of each shop's approved credit line is currently drawn. High utilization may signal stress or upcoming capacity limits."
        />
        <Metric
          name="Loan Size Distribution"
          formula="Count of loans in size bands: <50K, 50-100K, 100-250K, 250-500K, 500K-1M, >1M"
          rationale="Shows the granularity of the book. A portfolio concentrated in large tickets has different risk characteristics than one with many small loans."
        />
      </Section>

      <Section id="cohort" title="Cohort Analysis">
        <Metric
          name="Vintage Cohort"
          formula="Group loans by Disbursement_Date month"
          rationale="Track each origination vintage's performance independently. Newer vintages have less time to collect, so lower collection rates are expected. PAR30 by vintage reveals whether delinquency is improving or deteriorating with each batch."
        />
        <p style={styles.body}>
          Heat-coded cells highlight outliers: green for high collection rates, red for high PAR.
          The totals row aggregates across all vintages for a portfolio-level view.
        </p>
      </Section>

      <Section id="yield" title="Yield & Margins">
        <Metric
          name="Portfolio Margin Rate"
          formula="sum(Margin Collected) / sum(Disbursed_Amount)"
          rationale="Revenue yield on deployed capital. Measured on all loans (active + closed)."
        />
        <Metric
          name="Realised Margin Rate"
          formula="sum(Margin Collected) / sum(Disbursed_Amount) — closed loans only"
          rationale="Margin on fully matured loans. Excludes active loans still collecting, giving a cleaner view of actual return."
        />
        <Note>
          <strong>RCL Margin = 0%:</strong> The RCL data sheet does not include a separate
          Margin Collected column. RCL revenue is priced at 3% monthly on the assigned limit, invoiced separately at month-end,
          not broken out in the loan tape. This does not mean RCL earns zero revenue — it means margin is not separately trackable from the tape.
        </Note>
      </Section>

      <Section id="tenure" title="Tenure Analysis">
        <Metric
          name="Tenure"
          formula="Tenure column (weeks) from loan tape"
          rationale="Contractual loan duration. BNPL tenures range from 4-90 weeks. RBF loans are typically 90 weeks. Shorter tenures turn over faster, generating more fee income per unit of capital."
        />
        <Metric
          name="Performance by Tenure Band"
          formula="Collection rate, DPD rate, margin rate per tenure band"
          rationale="Reveals whether shorter or longer loans perform better. Bands: 1-4w, 5-9w, 10-14w, 15-19w, 20-29w, 30w+."
        />
      </Section>

      <Section id="covenants" title="Covenant Monitoring">
        <p style={styles.body}>
          Covenants are contractual financial tests defined in the SILQ KSA facility agreement.
          The platform auto-checks compliance from loan tape data, using the exact formulas from the compliance certificate.
        </p>
        <Metric
          name="PAR 30 Ratio"
          formula="Outstanding of DPD > 30 loans / Total Outstanding of active loans  ≤  10%"
          rationale="Portfolio quality gate. Ensures delinquency by exposure remains controlled. Uses GBV-weighted methodology matching the compliance certificate."
        />
        <Metric
          name="PAR 90 Ratio"
          formula="Outstanding of DPD > 90 loans / Total Outstanding of active loans  ≤  5%"
          rationale="Serious delinquency threshold. Loans past 90 days are at elevated loss risk."
        />
        <Metric
          name="Collection Ratio (3-Month Average)"
          formula="Average of (Amt_Repaid / Total_Collectable_Amount) for loans maturing in each of the prior 3 months  >  33%"
          rationale="Measures whether maturing loans are being collected. Each month looks at loans whose Repayment_Deadline fell in that month. The 3-month rolling average smooths seasonal variation."
        />
        <Metric
          name="Repayment at Term"
          formula="Total collections / Total GBV for loans reaching maturity + 3 months  >  95%"
          rationale="Tests whether loans that had enough time to fully collect actually did. Looks at loans whose Repayment_Deadline was 3-6 months before the test date, giving them a 3-month grace period."
        />
        <Metric
          name="Loan-to-Value Ratio"
          formula="Facility Amount / (Receivables + Cash Balances)  ≤  75%"
          rationale="Leverage test. Partially computable from tape (receivables = total outstanding). Facility amount and cash balances are corporate-level data not in the loan tape — shown as partial."
        />
      </Section>

      <Section id="products" title="Product Types">
        <Subsection title="BNPL (Buy Now Pay Later)">
          <p style={styles.body}>
            The buyer submits a purchase order to FINA. FINA pays the supplier upfront and issues a sales
            invoice to the buyer with a due date based on the selected tenor (4–90 days). The buyer repays
            principal plus ~3% monthly markup on the due date. Credit limits are set at ~50% of the buyer's
            sales quantum. Serves SMEs in grocery, FMCG, mini-markets, wholesalers, and HoReCa.
            Origination can be buyer-led or supplier-led — both flow through the same product rails.
            Margin is explicitly tracked via the Margin Collected column.
          </p>
        </Subsection>
        <Subsection title="RCL (Revolving Credit Line)">
          <p style={styles.body}>
            A dedicated committed revolving facility. The partner routes all procurement through FINA exclusively
            and uses OMNI for sales visibility. FINA assigns a committed limit (typically 2–3x monthly revenue),
            and the partner draws down as needed — each drawdown carries a max 90-day tenor. Repayments follow
            the partner's incoming collections (no fixed instalments), and the limit resets as amounts are repaid.
            Pricing is 3% monthly on the assigned limit, invoiced separately at month-end. Margin is not separately
            tracked in the loan tape — the loader fills Margin Collected with 0.0 and flags these rows as synthetic.
          </p>
        </Subsection>
        <Subsection title="RBF (Revenue-Based Financing)">
          <p style={styles.body}>
            Same underlying mechanics as RCL. No exclusivity requirement — the merchant is not required to route
            all procurement through FINA or use OMNI. Margin is explicitly tracked via the Margin Collected column.
          </p>
        </Subsection>
      </Section>

      <Section id="backward-date" title="Backward-Date Caveat">
        <p style={styles.body}>
          When the as-of date is set before the tape date (e.g., viewing Dec 31 on a Jan 31 tape),
          the dashboard applies deal-level filtering — only loans disbursed by that date are included.
          However, <strong>balance columns</strong> (outstanding, collected, overdue, margins) still reflect
          the tape snapshot date, not the as-of date.
        </p>
        <p style={styles.body}>
          This means DPD-based metrics (PAR, delinquency buckets) are recalculated correctly using the
          as-of date as the reference. But balance-derived metrics are stale. The dashboard shows a gold
          warning banner and marks affected KPIs with a ⚠ indicator.
        </p>
        <Table
          headers={['Metric Type', 'Accurate?', 'Examples']}
          rows={[
            ['Deal selection / counts', 'Yes', 'Total deals, active loans, product mix'],
            ['Disbursement amounts', 'Yes', 'Total disbursed (only includes filtered deals)'],
            ['DPD / PAR ratios', 'Yes', 'Recalculated with as-of date as reference'],
            ['Balance columns', 'Stale ⚠', 'Outstanding, collected, overdue, margins, rates'],
            ['Tenure / HHI', 'Yes', 'Based on deal attributes, not balances'],
          ]}
        />
      </Section>

      <Section id="currency" title="Currency Conversion">
        <p style={styles.body}>
          SILQ data is reported in Saudi Riyal (SAR). The dashboard supports toggling between SAR and USD.
          When USD is selected, all monetary amounts are multiplied by the live FX rate.
          Non-monetary metrics (rates, percentages, days, counts) are unaffected.
        </p>
        <Note>
          Exchange rates are fetched live from open.er-api.com and cached for 1 hour.
          Falls back to static rates (SAR 0.2667) if the API is unavailable.
        </Note>
      </Section>
    </>
  )
}

const styles = {
  body: {
    fontSize: 13,
    lineHeight: 1.7,
    color: 'var(--text-muted)',
    margin: '0 0 12px',
  },
  list: {
    fontSize: 12,
    lineHeight: 1.8,
    color: 'var(--text-muted)',
    margin: '0 0 12px',
    paddingLeft: 20,
  },
}
