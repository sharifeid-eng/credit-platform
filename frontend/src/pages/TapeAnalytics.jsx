import React, { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useCompany } from '../contexts/CompanyContext'
import { generatePDFReport, getParChart, getDtfcChart } from '../services/api'

import KpiCard       from '../components/KpiCard'
import AICommentary  from '../components/AICommentary'
import DataChat      from '../components/DataChat'
import TabInsight       from '../components/TabInsight'
import BackdatedBanner  from '../components/BackdatedBanner'

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

// New analytical charts
import CdrCcrChart              from '../components/charts/CdrCcrChart'
import CohortLossWaterfallChart from '../components/charts/CohortLossWaterfallChart'
import RecoveryAnalysisChart    from '../components/charts/RecoveryAnalysisChart'
import CollectionsTimingChart   from '../components/charts/CollectionsTimingChart'
import UnderwritingDriftChart   from '../components/charts/UnderwritingDriftChart'
import SegmentAnalysisChart     from '../components/charts/SegmentAnalysisChart'
import SeasonalityChart         from '../components/charts/SeasonalityChart'

// SILQ Charts
import SilqDelinquencyChart    from '../components/charts/silq/DelinquencyChart'
import SilqCollectionsChart    from '../components/charts/silq/SilqCollectionsChart'
import SilqConcentrationChart  from '../components/charts/silq/SilqConcentrationChart'
import SilqCohortTable         from '../components/charts/silq/SilqCohortTable'
import YieldMarginsChart       from '../components/charts/silq/YieldMarginsChart'
import TenureAnalysisChart     from '../components/charts/silq/TenureAnalysisChart'
import SilqCovenantsChart      from '../components/charts/silq/SilqCovenantsChart'
import SilqSeasonalityChart    from '../components/charts/silq/SilqSeasonalityChart'
import SilqLossWaterfallChart  from '../components/charts/silq/SilqLossWaterfallChart'
import SilqUnderwritingDriftChart from '../components/charts/silq/SilqUnderwritingDriftChart'
import SilqCdrCcrChart           from '../components/charts/silq/SilqCdrCcrChart'
import EjariDashboard          from './EjariDashboard'

import { TAPE_TABS } from '../components/Sidebar'

const SLUG_TO_LABEL = Object.fromEntries(TAPE_TABS.map(t => [t.slug, t.label]))

export default function TapeAnalytics() {
  const { tab } = useParams()

  const {
    company, product, snapshots, snapshot, setSnapshot,
    config, currency, setCurrency, localCcy,
    summary, summaryLoading,
    aiCache, setAiCache,
    asOfDate, setAsOfDate, dateRange, snapshotDate, isBackdated,
    reportGenerating, reportError, handleGenerateReport,
    analysisType, tapeTabs,
  } = useCompany()

  // Build slug→label map from config tabs or default
  const tabs = tapeTabs || TAPE_TABS
  const slugToLabel = Object.fromEntries(tabs.map(t => [t.slug, t.label]))
  const activeTab = slugToLabel[tab] || 'Overview'

  // Ejari: render read-only summary dashboard instead of normal tabs
  if (analysisType === 'ejari_summary') {
    return (
      <div style={{ padding: '16px 28px' }}>
        <EjariDashboard />
      </div>
    )
  }

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
        {isBackdated && <BackdatedBanner asOfDate={asOfDate} snapshotDate={snapshotDate} />}
        <AnimatePresence mode="wait">
        <motion.div
          key={tab}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25, ease: 'easeOut' }}
        >
        {analysisType === 'silq' ? (
          <SilqTabContent
            tab={tab} activeTab={activeTab}
            company={company} product={product}
            snapshot={snapshot} snapshots={snapshots}
            currency={currency} asOfDate={asOfDate}
            summary={summary} summaryLoading={summaryLoading}
            aiCache={aiCache} onAiCache={setAiCache}
            isBackdated={isBackdated}
          />
        ) : (
          <KlaimTabContent
            activeTab={activeTab}
            company={company} product={product}
            snapshot={snapshot} snapshots={snapshots}
            currency={currency} asOfDate={asOfDate}
            summary={summary} summaryLoading={summaryLoading}
            aiCache={aiCache} onAiCache={setAiCache}
            isBackdated={isBackdated}
          />
        )}
        </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}

/* ── SILQ Tab Content ── */
function SilqTabContent({ tab, activeTab, company, product, snapshot, snapshots, currency, asOfDate, summary, summaryLoading, aiCache, onAiCache, isBackdated }) {
  const chartProps = { company, product, snapshot, currency, asOfDate }

  if (tab === 'overview') {
    return (
      <SilqOverviewTab
        summary={summary} summaryLoading={summaryLoading}
        company={company} product={product}
        snapshot={snapshot} currency={currency} asOfDate={asOfDate}
        aiCache={aiCache} onAiCache={onAiCache}
        isBackdated={isBackdated}
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
    'covenants':          <ChartTab tab="covenants" {...chartProps}><SilqCovenantsChart {...chartProps} /></ChartTab>,
    'seasonality':        <ChartTab tab="seasonality" {...chartProps}><SilqSeasonalityChart {...chartProps} /></ChartTab>,
    'loss-waterfall':     <ChartTab tab="loss-waterfall" {...chartProps}><SilqLossWaterfallChart {...chartProps} /></ChartTab>,
    'underwriting-drift': <ChartTab tab="underwriting-drift" {...chartProps}><SilqUnderwritingDriftChart {...chartProps} /></ChartTab>,
    'cdr-ccr':            <ChartTab tab="cdr-ccr" {...chartProps}><SilqCdrCcrChart {...chartProps} /></ChartTab>,
  }
  return SILQ_TABS[tab] || <div style={{ color: 'var(--text-muted)' }}>Tab not found</div>
}

/* ── Klaim Tab Content ── */
function KlaimTabContent({ activeTab, company, product, snapshot, snapshots, currency, asOfDate, summary, summaryLoading, aiCache, onAiCache, isBackdated }) {
  return (
    <>
      {activeTab === 'Overview' && (
        <OverviewTab
          summary={summary} summaryLoading={summaryLoading}
          company={company} product={product}
          snapshot={snapshot} currency={currency} asOfDate={asOfDate}
          aiCache={aiCache} onAiCache={onAiCache}
          isBackdated={isBackdated}
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
      {activeTab === 'Collections Timing' && (
        <ChartTab tab="collections-timing" company={company} product={product} snapshot={snapshot} currency={currency}>
          <CollectionsTimingChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Loss Waterfall' && (
        <ChartTab tab="loss-waterfall" company={company} product={product} snapshot={snapshot} currency={currency}>
          <CohortLossWaterfallChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Recovery Analysis' && (
        <ChartTab tab="recovery-analysis" company={company} product={product} snapshot={snapshot} currency={currency}>
          <RecoveryAnalysisChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Underwriting Drift' && (
        <ChartTab tab="underwriting-drift" company={company} product={product} snapshot={snapshot} currency={currency}>
          <UnderwritingDriftChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Segment Analysis' && (
        <ChartTab tab="segment-analysis" company={company} product={product} snapshot={snapshot} currency={currency}>
          <SegmentAnalysisChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Seasonality' && (
        <ChartTab tab="seasonality" company={company} product={product} snapshot={snapshot} currency={currency}>
          <SeasonalityChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'CDR / CCR' && (
        <ChartTab tab="cdr-ccr" company={company} product={product} snapshot={snapshot} currency={currency}>
          <CdrCcrChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
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
function SilqOverviewTab({ summary, summaryLoading, company, product, snapshot, currency, asOfDate, aiCache, onAiCache, isBackdated }) {
  const ccy = summary?.display_currency ?? 'SAR'
  const fmt  = (v) => v == null ? '—' : v >= 1_000_000 ? `${ccy} ${(v/1_000_000).toFixed(1)}M` : `${ccy} ${(v/1_000).toFixed(0)}K`
  const pct  = (v) => v == null ? '—' : `${v.toFixed(1)}%`

  const bd = isBackdated  // shorthand
  const kpis = summary ? [
    { label: 'Total Disbursed',  value: fmt(summary.total_disbursed),  sub: `${summary.total_deals} loans`,        color: 'gold' },
    { label: 'Outstanding',      value: fmt(summary.total_outstanding),sub: 'current exposure',                     color: 'blue', stale: bd },
    { label: 'Total Overdue',    value: fmt(summary.total_overdue),    sub: 'past repayment deadline',                                  color: 'red', stale: bd },
    { label: 'Collection Rate',  value: pct(summary.collection_rate),  sub: 'repaid vs collectable',                color: 'teal', stale: bd },
    { label: 'Overdue Rate',     value: pct(summary.overdue_rate),     sub: 'of outstanding',                       color: summary.overdue_rate > 15 ? 'red' : 'gold', stale: bd },
    { label: 'Active Loans',     value: String(summary.active_deals),  sub: 'currently open',                       color: 'blue' },
    { label: 'Completed Loans',  value: String(summary.completed_deals), sub: 'closed',                             color: 'teal' },
    { label: 'Avg Tenure',       value: `${summary.avg_tenure?.toFixed(0) ?? '—'}w`, sub: 'weeks',                  color: 'gold' },
    { label: 'HHI (Shop)',       value: summary.hhi_shop?.toFixed(4) ?? '—', sub: `Top shop: ${pct(summary.top_1_shop_pct)}`, color: summary.hhi_shop > 0.15 ? 'red' : 'teal' },
    { label: 'Total Repaid',     value: fmt(summary.total_repaid),     sub: 'cumulative collections',               color: 'teal', stale: bd },
  ] : Array(10).fill(null)

  // Credit Quality — PAR as dedicated section (consistent with Klaim)
  const parKpis = summary ? [
    { label: 'PAR 30+', value: pct(summary.par30), sub: `${ccy} ${((summary.par30 ?? 0) * (summary.total_outstanding ?? 0) / 100 / 1000).toFixed(0)}K at risk`, color: summary.par30 > 20 ? 'red' : summary.par30 > 10 ? 'gold' : 'teal', stale: bd },
    { label: 'PAR 60+', value: pct(summary.par60), sub: `${ccy} ${((summary.par60 ?? 0) * (summary.total_outstanding ?? 0) / 100 / 1000).toFixed(0)}K at risk`, color: summary.par60 > 10 ? 'red' : summary.par60 > 5 ? 'gold' : 'teal', stale: bd },
    { label: 'PAR 90+', value: pct(summary.par90), sub: `${ccy} ${((summary.par90 ?? 0) * (summary.total_outstanding ?? 0) / 100 / 1000).toFixed(0)}K at risk`, color: summary.par90 > 5 ? 'red' : summary.par90 > 2 ? 'gold' : 'teal', stale: bd },
  ] : []

  const showSkeleton = summaryLoading || !summary

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {summaryLoading && <LoadingBar />}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10 }}>
        {showSkeleton
          ? Array(10).fill(null).map((_, i) => <SkeletonKpi key={i} />)
          : kpis.map((k, i) => <KpiCard key={i} {...k} index={i} />)
        }
      </div>

      {/* Credit Quality — PAR section */}
      {summary && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)' }}>
              Credit Quality
            </span>
            <span style={{ fontSize: 9, fontWeight: 500, color: 'var(--text-muted)', opacity: 0.7 }}>
              vs Active Outstanding
            </span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10 }}>
            {parKpis.map((k, i) => <KpiCard key={`par-${i}`} {...k} index={i} />)}
          </div>
        </div>
      )}

      {summary?.portfolio_commentary && (
        <PortfolioCommentaryPanel text={summary.portfolio_commentary} />
      )}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <AICommentary company={company} product={product} snapshot={snapshot} currency={currency} cached={aiCache} onCache={onAiCache} />
        <DataChat company={company} product={product} snapshot={snapshot} currency={currency} />
      </div>
    </div>
  )
}

/* ── Portfolio Commentary Panel ── */
function PortfolioCommentaryPanel({ text }) {
  const [expanded, setExpanded] = React.useState(false)
  const preview = text.length > 280 ? text.slice(0, 280) + '...' : text

  return (
    <div style={{
      background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 8,
      padding: '12px 16px', borderLeft: '3px solid var(--accent-gold)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--accent-gold)' }}>Portfolio Commentary</span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)', fontStyle: 'italic' }}>from tape</span>
      </div>
      <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--text-primary)', whiteSpace: 'pre-wrap' }}>
        {expanded ? text : preview}
      </div>
      {text.length > 280 && (
        <button
          onClick={() => setExpanded(e => !e)}
          style={{
            marginTop: 6, background: 'none', border: 'none', color: 'var(--accent-gold)',
            fontSize: 12, cursor: 'pointer', padding: 0,
          }}
        >{expanded ? 'Show less' : 'Read more'}</button>
      )}
    </div>
  )
}

/* ── Klaim Overview Tab ── */
function OverviewTab({ summary, summaryLoading, company, product, snapshot, currency, asOfDate, aiCache, onAiCache, isBackdated }) {
  const ccy = summary?.display_currency ?? 'AED'
  const fmt  = (v) => v == null ? '—' : v >= 1_000_000 ? `${ccy} ${(v/1_000_000).toFixed(1)}M` : `${ccy} ${(v/1_000).toFixed(0)}K`
  const pct  = (v) => v == null ? '—' : `${v.toFixed(1)}%`
  const hhiFmt = (v) => v == null ? '—' : v.toFixed(4)
  const bd = isBackdated

  // Fetch PAR and DTFC data
  const [par, setPar] = useState(null)
  const [dtfc, setDtfc] = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    getParChart(company, product, snapshot, currency, asOfDate).then(setPar).catch(() => setPar(null))
    getDtfcChart(company, product, snapshot, currency, asOfDate).then(setDtfc).catch(() => setDtfc(null))
  }, [company, product, snapshot, currency, asOfDate])

  const kpis = summary ? [
    { label: 'Purchase Value',  value: fmt(summary.total_purchase_value), sub: `${summary.total_deals} deals`,    color: 'gold', confidence: 'A' },
    { label: 'Collection Rate', value: pct(summary.collection_rate),      sub: 'vs Purchase Value',               color: 'teal', stale: bd, confidence: 'A' },
    { label: 'Denial Rate',     value: pct(summary.denial_rate),          sub: 'vs Purchase Value',               color: 'red',  stale: bd, confidence: 'A' },
    { label: 'Pending Exposure',value: fmt(summary.total_pending),        sub: pct(summary.pending_rate),         color: 'blue', stale: bd, confidence: 'A' },
    { label: 'Active Deals',    value: String(summary.active_deals),      sub: 'currently executing',             color: 'blue', confidence: 'A' },
    { label: 'Completed Deals', value: String(summary.completed_deals),   sub: 'fully collected',                 color: 'teal', confidence: 'A' },
    { label: 'Total Collected', value: fmt(summary.total_collected),      sub: 'cumulative collections',          color: 'teal', stale: bd, confidence: 'A' },
    { label: 'Total Denied',    value: fmt(summary.total_denied),         sub: 'denied by insurance',             color: 'red',  stale: bd, confidence: 'A' },
    ...(summary.dso_available ? [{ label: 'Wtd Avg DSO', value: summary.dso != null ? `${summary.dso.toFixed(0)}d` : '—', sub: `Median: ${summary.median_dso != null ? summary.median_dso.toFixed(0) + 'd' : '—'}`, color: 'gold', stale: bd, confidence: 'B' }] : []),
    { label: 'HHI (Group)',     value: hhiFmt(summary.hhi_group), sub: `Top provider: ${pct(summary.top_1_group_pct)}`, color: summary.hhi_group > 0.15 ? 'red' : summary.hhi_group > 0.10 ? 'gold' : 'teal', confidence: 'A' },
  ] : Array(10).fill(null)

  // PAR KPIs — dual perspective: lifetime (IC view) as headline, active as context
  const parConfidence = par?.method === 'primary' ? 'B' : 'C'
  const parKpis = par?.available ? [
    { label: 'PAR 30+', value: pct(par.lifetime_par30 ?? par.par30), sub: `${ccy} ${(par.par30_amount / 1000).toFixed(0)}K at risk`, color: (par.lifetime_par30 ?? par.par30) > 2 ? 'red' : (par.lifetime_par30 ?? par.par30) > 1 ? 'gold' : 'teal', derived: par.method === 'derived', confidence: parConfidence },
    { label: 'PAR 60+', value: pct(par.lifetime_par60 ?? par.par60), sub: `${ccy} ${(par.par60_amount / 1000).toFixed(0)}K at risk`, color: (par.lifetime_par60 ?? par.par60) > 1.5 ? 'red' : (par.lifetime_par60 ?? par.par60) > 0.75 ? 'gold' : 'teal', derived: par.method === 'derived', confidence: parConfidence },
    { label: 'PAR 90+', value: pct(par.lifetime_par90 ?? par.par90), sub: `${ccy} ${(par.par90_amount / 1000).toFixed(0)}K at risk`, color: (par.lifetime_par90 ?? par.par90) > 1 ? 'red' : (par.lifetime_par90 ?? par.par90) > 0.5 ? 'gold' : 'teal', derived: par.method === 'derived', confidence: parConfidence },
  ] : []

  // DTFC KPIs — only shown when available
  const dtfcConfidence = dtfc?.method === 'curve_based' ? 'B' : 'C'
  const dtfcKpis = dtfc?.available ? [
    { label: 'DTFC (Median)', value: `${dtfc.median_dtfc.toFixed(0)}d`, sub: `${dtfc.total_deals} deals`, color: 'blue', confidence: dtfcConfidence },
    { label: 'DTFC (P90)',    value: `${dtfc.p90_dtfc.toFixed(0)}d`, sub: 'slowest 10%',                  color: dtfc.p90_dtfc > 90 ? 'red' : 'gold', confidence: dtfcConfidence },
  ] : []

  const showSkeleton = summaryLoading || !summary

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {summaryLoading && <LoadingBar />}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10 }}>
        {showSkeleton
          ? Array(10).fill(null).map((_, i) => <SkeletonKpi key={i} />)
          : kpis.map((k, i) => <KpiCard key={i} {...k} index={i} />)
        }
      </div>

      {/* Credit Quality — PAR section */}
      {parKpis.length > 0 && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)' }}>
              Credit Quality
            </span>
            <span style={{ fontSize: 9, fontWeight: 500, color: 'var(--text-muted)', opacity: 0.7 }}>
              vs Total Originated
            </span>
            {par?.method === 'derived' && (
              <span style={{
                fontSize: 9, fontWeight: 600, padding: '2px 6px', borderRadius: 4,
                background: 'rgba(201,168,76,0.1)', color: 'var(--gold)',
                border: '1px dashed rgba(201,168,76,0.3)',
              }}>
                Derived from historical patterns
              </span>
            )}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10 }}>
            {parKpis.map((k, i) => (
              <div key={`par-${i}`} style={k.derived ? { borderStyle: 'dashed' } : undefined}>
                <KpiCard {...k} index={i} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Leading Indicators — DTFC section */}
      {dtfcKpis.length > 0 && (
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: 8 }}>
            Leading Indicators
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10 }}>
            {dtfcKpis.map((k, i) => <KpiCard key={`dtfc-${i}`} {...k} index={i} />)}
          </div>
        </div>
      )}

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
          background: 'linear-gradient(90deg, var(--border) 25%, #243A50 50%, var(--border) 75%)',
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
