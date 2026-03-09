import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'

const SECTIONS = [
  { id: 'overview', title: 'Portfolio Overview Metrics' },
  { id: 'collection-perf', title: 'Collection Performance' },
  { id: 'collection-analysis', title: 'Collection Analysis' },
  { id: 'health', title: 'Health Classification' },
  { id: 'cohort', title: 'Cohort Analysis' },
  { id: 'returns', title: 'Returns Analysis' },
  { id: 'denial-funnel', title: 'Denial Funnel' },
  { id: 'stress', title: 'Stress Testing' },
  { id: 'expected-loss', title: 'Expected Loss Model' },
  { id: 'migration', title: 'Roll-Rate Migration' },
  { id: 'validation', title: 'Data Quality Validation' },
  { id: 'currency', title: 'Currency Conversion' },
]

export default function Methodology() {
  const { companyName } = useParams()
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
      { rootMargin: '-104px 0px -40% 0px', threshold: 0 },
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
    <div style={{ display: 'flex', minHeight: 'calc(100vh - 104px)' }}>
      {/* Sidebar TOC */}
      <nav style={{
        width: 220,
        flexShrink: 0,
        position: 'sticky',
        top: 104,
        height: 'calc(100vh - 104px)',
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
              display: 'block',
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
            Exchange rates are currently static. A future enhancement will replace these with live FX rates.
          </Note>
        </Section>
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
