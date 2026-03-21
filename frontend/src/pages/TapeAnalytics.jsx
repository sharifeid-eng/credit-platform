import { useParams } from 'react-router-dom'
import { useCompany } from '../contexts/CompanyContext'
import { generatePDFReport } from '../services/api'

import KpiCard       from '../components/KpiCard'
import AICommentary  from '../components/AICommentary'
import DataChat      from '../components/DataChat'
import TabInsight    from '../components/TabInsight'

// Klaim Charts
import DeploymentChart         from '../components/charts/DeploymentChart'
import ActualVsExpectedChart   from '../components/charts/ActualVsExpectedChart'
import CollectionVelocityChart from '../components/charts/CollectionVelocityChart'
import DenialTrendChart        from '../components/charts/DenialTrendChart'
import AgeingChart             from '../components/charts/AgeingChart'
import RevenueChart            from '../components/charts/RevenueChart'
import ConcentrationChart      from '../components/charts/ConcentrationChart'
import CohortTable             from '../components/charts/CohortTable'
import ReturnsAnalysisChart    from '../components/charts/ReturnsAnalysisChart'
import RiskMigrationChart      from '../components/charts/RiskMigrationChart'
import DenialFunnelChart       from '../components/charts/DenialFunnelChart'
import DataIntegrityChart      from '../components/charts/DataIntegrityChart'

// SILQ Charts
import SilqDelinquencyChart    from '../components/charts/silq/DelinquencyChart'
import SilqCollectionsChart    from '../components/charts/silq/SilqCollectionsChart'
import SilqConcentrationChart  from '../components/charts/silq/SilqConcentrationChart'
import SilqCohortTable         from '../components/charts/silq/SilqCohortTable'
import YieldMarginsChart       from '../components/charts/silq/YieldMarginsChart'
import TenureAnalysisChart     from '../components/charts/silq/TenureAnalysisChart'

import { TAPE_TABS } from '../components/Sidebar'

const SLUG_TO_LABEL = Object.fromEntries(TAPE_TABS.map(t => [t.slug, t.label]))

export default function TapeAnalytics() {
  const { tab } = useParams()

  const {
    company, product, snapshots, snapshot, setSnapshot,
    config, currency, setCurrency, localCcy,
    summary, summaryLoading,
    aiCache, setAiCache,
    asOfDate, setAsOfDate, dateRange,
    reportGenerating, reportError, handleGenerateReport,
    analysisType, tapeTabs,
  } = useCompany()

  // Build slug→label map from config tabs or default
  const tabs = tapeTabs || TAPE_TABS
  const slugToLabel = Object.fromEntries(tabs.map(t => [t.slug, t.label]))
  const activeTab = slugToLabel[tab] || 'Overview'

  return (
    <div>
      {/* Controls bar */}
      <div style={{ padding: '16px 28px 0', display: 'flex', gap: 10, alignItems: 'flex-end', flexWrap: 'wrap' }}>
        {/* Snapshot selector */}
        <ControlGroup label="Tape">
          <DarkSelect value={snapshot ?? ''} onChange={v => { setSnapshot(v); setAiCache(null) }}>
            {snapshots.map(s => <option key={s} value={s}>{s}</option>)}
          </DarkSelect>
        </ControlGroup>

        {/* As-of Date picker */}
        <ControlGroup label="As-of Date">
          <input
            type="date"
            value={asOfDate}
            min={dateRange.min}
            max={dateRange.max}
            onChange={e => setAsOfDate(e.target.value)}
            style={{
              fontSize: 11, padding: '5px 10px',
              background: 'var(--bg-surface)', border: '1px solid var(--border)',
              borderRadius: 7, color: 'var(--text-primary)',
              fontFamily: 'var(--font-mono)', outline: 'none',
              colorScheme: 'dark',
            }}
          />
        </ControlGroup>

        {/* Currency toggle */}
        <ControlGroup label="Currency">
          <CurrencyToggle localCcy={localCcy} value={currency} onChange={setCurrency} />
        </ControlGroup>

        {/* Divider */}
        <div style={{ width: 1, height: 32, background: 'var(--border)', alignSelf: 'flex-end', marginBottom: 2 }} />

        {/* PDF Report button — only for Klaim (SILQ PDF not yet supported) */}
        {analysisType !== 'silq' && (
          <div style={{ alignSelf: 'flex-end' }}>
            <button
              disabled={reportGenerating || !product || !snapshot}
              onClick={handleGenerateReport}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                fontSize: 11, fontWeight: 600, padding: '6px 14px',
                borderRadius: 7, cursor: reportGenerating ? 'not-allowed' : 'pointer',
                transition: 'all 0.15s',
                fontFamily: 'inherit',
                ...(reportError
                  ? { background: 'transparent', border: '1px solid var(--accent-red)', color: 'var(--accent-red)' }
                  : reportGenerating
                  ? { background: 'var(--bg-surface)', border: '1px solid var(--border)', color: 'var(--text-muted)' }
                  : { background: 'transparent', border: '1px solid var(--gold)', color: 'var(--gold)' }
                ),
              }}
            >
              {reportGenerating ? (
                <>
                  <SpinnerIcon />
                  Generating…
                </>
              ) : reportError ? (
                <>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
                  </svg>
                  Retry
                </>
              ) : (
                <>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                    <line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" />
                  </svg>
                  PDF Report
                </>
              )}
            </button>
          </div>
        )}
      </div>

      {/* Tab content */}
      <div style={{ padding: '20px 28px 40px' }}>
        {analysisType === 'silq' ? (
          <SilqTabContent
            tab={tab} activeTab={activeTab}
            company={company} product={product}
            snapshot={snapshot} snapshots={snapshots}
            currency={currency} asOfDate={asOfDate}
            summary={summary} summaryLoading={summaryLoading}
            aiCache={aiCache} onAiCache={setAiCache}
          />
        ) : (
          <KlaimTabContent
            activeTab={activeTab}
            company={company} product={product}
            snapshot={snapshot} snapshots={snapshots}
            currency={currency} asOfDate={asOfDate}
            summary={summary} summaryLoading={summaryLoading}
            aiCache={aiCache} onAiCache={setAiCache}
          />
        )}
      </div>
    </div>
  )
}

/* ── SILQ Tab Content ── */
function SilqTabContent({ tab, activeTab, company, product, snapshot, snapshots, currency, asOfDate, summary, summaryLoading, aiCache, onAiCache }) {
  const chartProps = { company, product, snapshot, currency, asOfDate }

  if (tab === 'overview') {
    return (
      <SilqOverviewTab
        summary={summary} summaryLoading={summaryLoading}
        company={company} product={product}
        snapshot={snapshot} currency={currency} asOfDate={asOfDate}
        aiCache={aiCache} onAiCache={onAiCache}
      />
    )
  }
  if (tab === 'data-integrity') {
    return <DataIntegrityChart company={company} product={product} snapshots={snapshots} currency={currency} />
  }
  // Map tab slugs to components
  const SILQ_TABS = {
    'delinquency':     <ChartTab tab="delinquency" {...chartProps}><SilqDelinquencyChart {...chartProps} /></ChartTab>,
    'collections':     <ChartTab tab="collections" {...chartProps}><SilqCollectionsChart {...chartProps} /></ChartTab>,
    'concentration':   <ChartTab tab="concentration" {...chartProps}><SilqConcentrationChart {...chartProps} /></ChartTab>,
    'cohort-analysis': <ChartTab tab="cohort" {...chartProps}><SilqCohortTable {...chartProps} /></ChartTab>,
    'yield-margins':   <ChartTab tab="yield-margins" {...chartProps}><YieldMarginsChart {...chartProps} /></ChartTab>,
    'tenure':          <ChartTab tab="tenure" {...chartProps}><TenureAnalysisChart {...chartProps} /></ChartTab>,
  }
  return SILQ_TABS[tab] || <div style={{ color: 'var(--text-muted)' }}>Tab not found</div>
}

/* ── Klaim Tab Content ── */
function KlaimTabContent({ activeTab, company, product, snapshot, snapshots, currency, asOfDate, summary, summaryLoading, aiCache, onAiCache }) {
  return (
    <>
      {activeTab === 'Overview' && (
        <OverviewTab
          summary={summary} summaryLoading={summaryLoading}
          company={company} product={product}
          snapshot={snapshot} currency={currency} asOfDate={asOfDate}
          aiCache={aiCache} onAiCache={onAiCache}
        />
      )}
      {activeTab === 'Actual vs Expected' && (
        <ChartTab tab="actual-vs-expected" company={company} product={product} snapshot={snapshot} currency={currency}>
          <ActualVsExpectedChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Deployment' && (
        <ChartTab tab="deployment" company={company} product={product} snapshot={snapshot} currency={currency}>
          <DeploymentChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Collection' && (
        <ChartTab tab="collection-velocity" company={company} product={product} snapshot={snapshot} currency={currency}>
          <CollectionVelocityChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Denial Trend' && (
        <ChartTab tab="denial-trend" company={company} product={product} snapshot={snapshot} currency={currency}>
          <DenialFunnelChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
          <DenialTrendChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Ageing' && (
        <ChartTab tab="ageing" company={company} product={product} snapshot={snapshot} currency={currency}>
          <AgeingChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Revenue' && (
        <ChartTab tab="revenue" company={company} product={product} snapshot={snapshot} currency={currency}>
          <RevenueChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Portfolio' && (
        <ChartTab tab="concentration" company={company} product={product} snapshot={snapshot} currency={currency}>
          <ConcentrationChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Cohort Analysis' && (
        <ChartTab tab="cohort" company={company} product={product} snapshot={snapshot} currency={currency}>
          <CohortTable company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Returns' && (
        <ChartTab tab="returns" company={company} product={product} snapshot={snapshot} currency={currency}>
          <ReturnsAnalysisChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Risk & Migration' && (
        <ChartTab tab="risk-migration" company={company} product={product} snapshot={snapshot} currency={currency}>
          <RiskMigrationChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Data Integrity' && (
        <DataIntegrityChart company={company} product={product} snapshots={snapshots} currency={currency} />
      )}
    </>
  )
}

/* ── SILQ Overview Tab ── */
function SilqOverviewTab({ summary, summaryLoading, company, product, snapshot, currency, asOfDate, aiCache, onAiCache }) {
  const ccy = summary?.display_currency ?? 'SAR'
  const fmt  = (v) => v == null ? '—' : v >= 1_000_000 ? `${ccy} ${(v/1_000_000).toFixed(1)}M` : `${ccy} ${(v/1_000).toFixed(0)}K`
  const pct  = (v) => v == null ? '—' : `${v.toFixed(1)}%`

  const kpis = summary ? [
    { label: 'Total Disbursed',  value: fmt(summary.total_disbursed),  sub: `${summary.total_deals} loans`,        color: 'gold' },
    { label: 'Outstanding',      value: fmt(summary.total_outstanding),sub: 'current exposure',                     color: 'blue' },
    { label: 'Total Overdue',    value: fmt(summary.total_overdue),    sub: pct(summary.overdue_rate) + ' of outst.',color: 'red'  },
    { label: 'Collection Rate',  value: pct(summary.collection_rate),  sub: 'repaid vs collectable',                color: 'teal' },
    { label: 'PAR30',            value: pct(summary.par30),            sub: `PAR60: ${pct(summary.par60)}`,          color: summary.par30 > 20 ? 'red' : 'gold' },
    { label: 'PAR90',            value: pct(summary.par90),            sub: 'serious delinquency',                   color: summary.par90 > 5 ? 'red' : 'teal' },
    { label: 'Active Loans',     value: String(summary.active_deals),  sub: `${summary.completed_deals} closed`,    color: 'blue' },
    { label: 'Avg Tenure',       value: `${summary.avg_tenure?.toFixed(0) ?? '—'}w`, sub: 'weeks',                  color: 'gold' },
    { label: 'HHI (Shop)',       value: summary.hhi_shop?.toFixed(4) ?? '—', sub: `Top shop: ${pct(summary.top_1_shop_pct)}`, color: summary.hhi_shop > 0.15 ? 'red' : 'teal' },
    { label: 'Total Repaid',     value: fmt(summary.total_repaid),     sub: 'cumulative collections',               color: 'teal' },
  ] : Array(10).fill(null)

  const showSkeleton = summaryLoading || !summary

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {summaryLoading && <LoadingBar />}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10 }}>
        {showSkeleton
          ? Array(10).fill(null).map((_, i) => <SkeletonKpi key={i} />)
          : kpis.map((k, i) => <KpiCard key={i} {...k} />)
        }
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <AICommentary company={company} product={product} snapshot={snapshot} currency={currency} cached={aiCache} onCache={onAiCache} />
        <DataChat company={company} product={product} snapshot={snapshot} currency={currency} />
      </div>
    </div>
  )
}

/* ── Klaim Overview Tab ── */
function OverviewTab({ summary, summaryLoading, company, product, snapshot, currency, asOfDate, aiCache, onAiCache }) {
  const ccy = summary?.display_currency ?? 'AED'
  const fmt  = (v) => v == null ? '—' : v >= 1_000_000 ? `${ccy} ${(v/1_000_000).toFixed(1)}M` : `${ccy} ${(v/1_000).toFixed(0)}K`
  const pct  = (v) => v == null ? '—' : `${v.toFixed(1)}%`
  const hhiFmt = (v) => v == null ? '—' : v.toFixed(4)

  const kpis = summary ? [
    { label: 'Purchase Value',  value: fmt(summary.total_purchase_value), sub: `${summary.total_deals} deals`,    color: 'gold' },
    { label: 'Collection Rate', value: pct(summary.collection_rate),      sub: 'vs Purchase Value',               color: 'teal' },
    { label: 'Denial Rate',     value: pct(summary.denial_rate),          sub: 'vs Purchase Value',               color: 'red'  },
    { label: 'Pending Exposure',value: fmt(summary.total_pending),        sub: pct(summary.pending_rate),         color: 'blue' },
    { label: 'Active Deals',    value: String(summary.active_deals),      sub: 'currently executing',             color: 'blue' },
    { label: 'Completed Deals', value: String(summary.completed_deals),   sub: 'fully collected',                 color: 'teal' },
    { label: 'Total Collected', value: fmt(summary.total_collected),      sub: 'cumulative collections',          color: 'teal' },
    { label: 'Total Denied',    value: fmt(summary.total_denied),         sub: 'denied by insurance',             color: 'red'  },
    ...(summary.dso_available ? [{ label: 'Wtd Avg DSO', value: summary.dso != null ? `${summary.dso.toFixed(0)}d` : '—', sub: `Median: ${summary.median_dso != null ? summary.median_dso.toFixed(0) + 'd' : '—'}`, color: 'gold' }] : []),
    { label: 'HHI (Group)',     value: hhiFmt(summary.hhi_group), sub: `Top provider: ${pct(summary.top_1_group_pct)}`, color: summary.hhi_group > 0.15 ? 'red' : summary.hhi_group > 0.10 ? 'gold' : 'teal' },
  ] : Array(10).fill(null)

  const showSkeleton = summaryLoading || !summary

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {summaryLoading && <LoadingBar />}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10 }}>
        {showSkeleton
          ? Array(10).fill(null).map((_, i) => <SkeletonKpi key={i} />)
          : kpis.map((k, i) => <KpiCard key={i} {...k} />)
        }
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <AICommentary company={company} product={product} snapshot={snapshot} currency={currency} cached={aiCache} onCache={onAiCache} />
        <DataChat company={company} product={product} snapshot={snapshot} currency={currency} />
      </div>
    </div>
  )
}

/* ── Loading Bar ── */
function LoadingBar() {
  return (
    <div style={{ height: 3, borderRadius: 2, overflow: 'hidden', background: 'var(--border)' }}>
      <div style={{ height: '100%', width: '40%', borderRadius: 2, background: 'var(--gold)', animation: 'loadSlide 1s ease-in-out infinite' }} />
      <style>{`@keyframes loadSlide { 0% { transform: translateX(-100%); } 100% { transform: translateX(350%); } }`}</style>
    </div>
  )
}

/* ── Chart Tab wrapper ── */
function ChartTab({ tab, company, product, snapshot, currency, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <TabInsight company={company} product={product} snapshot={snapshot} currency={currency} tab={tab} />
      {children}
    </div>
  )
}

/* ── Skeleton KPI ── */
function SkeletonKpi() {
  return (
    <div style={{
      background: 'var(--bg-surface)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)', padding: '16px', position: 'relative', overflow: 'hidden',
      minHeight: 90,
    }}>
      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 3, background: 'var(--border)', borderRadius: '10px 0 0 10px' }} />
      {[40, 70, 50].map((w, i) => (
        <div key={i} style={{
          height: i === 1 ? 18 : 8, borderRadius: 4, marginBottom: i === 1 ? 8 : 6,
          background: 'linear-gradient(90deg, var(--border) 25%, #1E2D40 50%, var(--border) 75%)',
          backgroundSize: '200% 100%',
          animation: 'shimmer 1.4s infinite',
          width: `${w}%`,
        }} />
      ))}
      <style>{`@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }`}</style>
    </div>
  )
}

/* ── Small UI primitives ── */
function ControlGroup({ label, children }) {
  return (
    <div>
      <div style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: 4 }}>
        {label}
      </div>
      {children}
    </div>
  )
}

function DarkSelect({ value, onChange, children }) {
  return (
    <select
      value={value ?? ''}
      onChange={e => onChange(e.target.value)}
      style={{
        fontSize: 11, padding: '6px 10px',
        background: 'var(--bg-surface)', border: '1px solid var(--border)',
        borderRadius: 7, color: 'var(--text-primary)',
        fontFamily: 'var(--font-mono)', outline: 'none',
      }}
    >
      {children}
    </select>
  )
}

function SpinnerIcon() {
  return (
    <>
      <div style={{
        width: 12, height: 12,
        border: '2px solid var(--border)',
        borderTopColor: 'var(--gold)',
        borderRadius: '50%',
        animation: 'reportSpin 0.8s linear infinite',
      }} />
      <style>{`@keyframes reportSpin { to { transform: rotate(360deg); } }`}</style>
    </>
  )
}

function CurrencyToggle({ localCcy, value, onChange }) {
  const opts = [localCcy, 'USD'].filter((v, i, a) => a.indexOf(v) === i)
  return (
    <div style={{ display: 'flex', borderRadius: 7, overflow: 'hidden', border: '1px solid var(--border)' }}>
      {opts.map(opt => (
        <button key={opt} onClick={() => onChange(opt)} style={{
          fontSize: 11, padding: '6px 12px',
          background: value === opt ? 'var(--gold)' : 'var(--bg-surface)',
          color: value === opt ? '#000' : 'var(--text-muted)',
          border: 'none', cursor: 'pointer',
          fontFamily: 'var(--font-mono)', fontWeight: value === opt ? 700 : 400,
          transition: 'all 0.15s',
        }}>
          {opt}
        </button>
      ))}
    </div>
  )
}
